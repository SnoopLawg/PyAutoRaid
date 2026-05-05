#!/usr/bin/env python3
"""Campaign farm loop: drives squad rotation + battle replay + auto rank-up.

Pre-conditions:
  - Game is on a campaign battle-setup dialog (StoryHeroesSelectionDialog).
    For now you navigate there manually (Campaign → chapter → stage tile).
    Auto-open is a follow-up — needs StageId discovery.

Workflow each iteration:
  1. Read /all-heroes — find food champs at level cap (L = grade*10) and
     same-grade fodder needed for rank-ups.
  2. Set the squad: carry in slot 1 + 4 lowest-rarity unleveled food in
     slots 2-5 via /squad-set.
  3. Start battle (StartBattle on the active dialog context).
  4. Poll until finish dialog appears, read win/loss.
  5. After battle: re-fetch /all-heroes; for any food now at cap →
     rank up using same-grade fodder; replace promoted hero in the
     squad with a fresh low-level food on the next iteration.
  6. Close finish dialog (continues back to battle setup).
  7. Repeat until --runs exhausted, --until-energy hit, or no more
     food candidates.

Usage:
    python3 tools/farm_loop.py --carry 19150 --runs 50
    python3 tools/farm_loop.py --carry-name Heiress --until-energy 0
    python3 tools/farm_loop.py --carry 19150 --dry-run     # plan only

Hard exclusions on every food/fodder pick (mirrors champ_manager):
  legendaries, fusion ingredients, faction guardians, empowered, named-
  protected, locked, in Master Vault. Read protected_heroes.json for tweaks.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"

# Squad layout: 1 carry + N food slots = N+1 total heroes (5 max in Raid)
DEFAULT_FOOD_SLOTS = 4


def _get(path: str, timeout: int = 30) -> dict:
    with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def load_reserved() -> set[int]:
    p = PROJECT_ROOT / "data" / "reserved_heroes.json"
    if not p.exists():
        return set()
    try:
        return set(int(x) for x in json.loads(p.read_text()).get("reserved", []))
    except Exception:
        return set()


def load_protected() -> dict:
    p = PROJECT_ROOT / "data" / "protected_heroes.json"
    if not p.exists():
        return {"exclude_all_legendaries": True, "exclude_all_epics": True,
                "exclude_empowered": True, "exclude_reserve_vault": False,
                "protected_names": [], "fusion_targets": []}
    return json.loads(p.read_text())


def is_food_eligible(h: dict, reserved: set[int], protected: dict,
                     max_rarity: int = 3) -> bool:
    """Same gates as champ_manager.is_food_eligible but with a rarity cap
    so we farm with cheap (Common/Uncommon/Rare) fodder."""
    if h.get("id") in reserved or h.get("locked") or h.get("in_storage"):
        return False
    if h.get("is_faction_guardian"):
        return False
    if h.get("is_fusion_ingredient"):
        return False
    if protected.get("exclude_empowered", True) and (h.get("empower") or 0) > 0:
        return False
    if protected.get("exclude_reserve_vault", False) and h.get("in_bathhouse"):
        return False
    rarity = h.get("rarity", 0)
    if protected.get("exclude_all_legendaries", True) and rarity == 5:
        return False
    if protected.get("exclude_all_epics", True) and rarity == 4:
        return False
    if rarity > max_rarity:
        return False
    name = h.get("name", "")
    if name in protected.get("protected_names", []):
        return False
    if name in protected.get("fusion_targets", []):
        return False
    return True


def at_level_cap(h: dict) -> bool:
    return (h.get("level") or 0) >= (h.get("grade") or 0) * 10


def pick_food_slot(pool: list[dict], excluded_ids: set[int],
                   max_rarity: int = 3) -> dict | None:
    """Pick the next-best food champ: lowest rarity, most XP runway."""
    candidates = []
    for h in pool:
        if h.get("id") in excluded_ids:
            continue
        if (h.get("rarity") or 0) > max_rarity:
            continue
        if at_level_cap(h):
            continue  # already maxed; rank-up phase will eat them
        candidates.append(h)
    if not candidates:
        return None
    candidates.sort(key=lambda h: (
        h.get("rarity", 99),                       # lowest rarity first
        -(((h.get("grade") or 0) * 10) - (h.get("level") or 0)),  # most runway (NEGATIVE so larger comes first)
        h.get("grade", 99),                        # lowest grade
        h.get("level", 0),                         # lowest level
        h.get("name", ""),
    ))
    return candidates[0]


def squad_set(hero_ids: list[int]) -> dict:
    return _get(f"/squad-set?ids={','.join(str(i) for i in hero_ids)}")


def squad_swap(remove_id: int, add_id: int) -> tuple[dict, dict]:
    r = _get(f"/squad-remove?hero_id={remove_id}")
    a = _get(f"/squad-add?hero_id={add_id}")
    return r, a


def squad_current() -> list[int]:
    r = _get("/squad-current")
    return r.get("hero_ids", [])


def list_active_dialogs() -> list[str]:
    try:
        d = _get("/view-contexts", timeout=5)
        return [c.get("dialog", "") for c in d.get("contexts", [])]
    except Exception:
        return []


def is_on_battle_setup() -> bool:
    return any("HeroesSelectionDialog" in d for d in list_active_dialogs())


def is_on_finish_dialog() -> bool:
    return any("BattleFinish" in d for d in list_active_dialogs())


def start_battle() -> dict:
    """StartBattle on the active battle-setup dialog. Mirrors what
    level_food.py does — the path varies by dialog type, so we try the
    common one first, then any matching alternative."""
    dlgs = list_active_dialogs()
    setup_dialog = next((d for d in dlgs if "HeroesSelectionDialog" in d), None)
    if not setup_dialog:
        return {"error": "no battle-setup dialog active"}
    # context-call expects the path including the dialog name
    path = f"UIManager/Canvas (Ui Root)/Dialogs/{setup_dialog}"
    return _get(f"/context-call?path={urllib.parse.quote(path)}&method=StartBattle")


def quick_restart() -> dict:
    """Hit Replay on the BattleFinish dialog to start the same fight again."""
    dlgs = list_active_dialogs()
    finish_dialog = next((d for d in dlgs if "BattleFinish" in d), None)
    if not finish_dialog:
        return {"error": "no battle-finish dialog active"}
    path = f"UIManager/Canvas (Ui Root)/Dialogs/{finish_dialog}"
    return _get(f"/context-call?path={urllib.parse.quote(path)}&method=OnQuickRestartPressed")


def close_finish_dialog() -> dict:
    """Continue/close the BattleFinish dialog → returns to battle setup."""
    dlgs = list_active_dialogs()
    finish_dialog = next((d for d in dlgs if "BattleFinish" in d), None)
    if not finish_dialog:
        return {"error": "no battle-finish dialog active"}
    path = f"UIManager/Canvas (Ui Root)/Dialogs/{finish_dialog}"
    return _get(f"/context-call?path={urllib.parse.quote(path)}&method=OnContinue")


def wait_for_finish(timeout_s: int = 300) -> str:
    """Poll until BattleFinish dialog opens. Returns 'finish' / 'timeout' /
    'block' (some other dialog blocked us, e.g. MessageBox)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        dlgs = list_active_dialogs()
        if any("BattleFinish" in d for d in dlgs):
            return "finish"
        if any("MessageBox" in d for d in dlgs):
            return "block"
        time.sleep(2)
    return "timeout"


def wait_for_setup(timeout_s: int = 60) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if is_on_battle_setup():
            return "setup"
        time.sleep(1)
    return "timeout"


def fetch_heroes() -> list[dict]:
    return _get("/all-heroes?offset=0&limit=20000").get("heroes", [])


def auto_rank_up_maxed(heroes: list[dict], reserved: set[int],
                       protected: dict, max_rarity: int = 3) -> list[dict]:
    """For each food champ at level cap, attempt /rank-up using same-grade
    fodder from the eligible pool. Returns list of rank-up results."""
    results = []
    by_id = {h["id"]: h for h in heroes}
    food_pool = [h for h in heroes if is_food_eligible(h, reserved, protected, max_rarity)]
    consumed: set[int] = set()
    # Targets: food champs at cap, sorted by (lowest grade first — easier to feed)
    targets = sorted(
        [h for h in food_pool if at_level_cap(h)],
        key=lambda h: (h.get("grade", 99), h.get("rarity", 99)))
    for t in targets:
        if t.get("id") in consumed:
            continue
        # Skip if at G6 (cap; no further rank-up).
        if (t.get("grade") or 0) >= 6:
            continue
        n_needed = t.get("grade", 0)
        same_grade = [h for h in food_pool
                      if h.get("grade") == n_needed
                      and h.get("id") != t["id"]
                      and h.get("id") not in consumed]
        # Prefer non-leveled fodder (waste less XP).
        same_grade.sort(key=lambda h: (h.get("level", 0), h.get("rarity", 99), h.get("name", "")))
        food = same_grade[:n_needed]
        if len(food) < n_needed:
            continue
        food_csv = ",".join(str(f["id"]) for f in food)
        try:
            r = _get(f"/rank-up?hero_id={t['id']}&food={food_csv}", timeout=30)
        except Exception as ex:
            results.append({"target": t["name"], "ok": False, "error": str(ex)})
            continue
        if r.get("ok"):
            results.append({"target": t["name"], "from_grade": t["grade"],
                            "to_grade": t["grade"] + 1,
                            "consumed": [f["id"] for f in food]})
            consumed.update(f["id"] for f in food)
            consumed.add(t["id"])  # promoted out of original grade
        else:
            results.append({"target": t["name"], "ok": False, "error": r.get("error")})
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--carry", type=int, default=None,
                    help="Carry hero instance id (slot 1)")
    ap.add_argument("--carry-name", default=None,
                    help="Carry hero name (first match wins)")
    ap.add_argument("--food-slots", type=int, default=DEFAULT_FOOD_SLOTS,
                    help=f"Food slots (default {DEFAULT_FOOD_SLOTS} = 5-hero team)")
    ap.add_argument("--max-rarity", type=int, default=3,
                    help="Max food rarity 1-3 (default 3 = Rare)")
    ap.add_argument("--runs", type=int, default=0,
                    help="Stop after N battles (0 = unlimited)")
    ap.add_argument("--until-energy", type=int, default=None,
                    help="Stop when /all-resources Energy <= N")
    ap.add_argument("--auto-rank-up", action="store_true", default=True,
                    help="Auto-rank-up maxed food after each battle (default ON)")
    ap.add_argument("--no-auto-rank-up", dest="auto_rank_up", action="store_false")
    ap.add_argument("--dry-run", action="store_true",
                    help="Plan + show team but don't fire battles")
    args = ap.parse_args()

    reserved = load_reserved()
    protected = load_protected()

    # Resolve carry.
    heroes = fetch_heroes()
    by_id = {h["id"]: h for h in heroes}
    by_name = {}
    for h in heroes:
        by_name.setdefault(h.get("name", ""), h)
    if args.carry:
        carry = by_id.get(args.carry)
    elif args.carry_name:
        carry = by_name.get(args.carry_name)
    else:
        ap.error("Specify --carry HEROID or --carry-name NAME")
    if not carry:
        print("ERROR: carry not found in roster", file=sys.stderr)
        return 1

    print(f"=== Farm Loop ===")
    print(f"  carry: id={carry['id']} R{carry['rarity']}/G{carry['grade']}/L{carry['level']} {carry['name']}")
    print(f"  food slots: {args.food_slots} (max rarity: {args.max_rarity})")

    # Sanity: are we on a battle setup screen?
    dlgs = list_active_dialogs()
    print(f"  active dialogs: {dlgs}")
    if not is_on_battle_setup():
        print("\nERROR: no battle-setup dialog open. Navigate to a campaign stage "
              "battle setup screen in-game first (Campaign → chapter → stage tile).",
              file=sys.stderr)
        return 1

    if args.dry_run:
        # Just show the initial team plan
        food_pool = [h for h in heroes if is_food_eligible(h, reserved, protected, args.max_rarity)]
        excluded = {carry["id"]}
        food = []
        for _ in range(args.food_slots):
            f = pick_food_slot(food_pool, excluded, args.max_rarity)
            if f is None: break
            food.append(f)
            excluded.add(f["id"])
        print(f"  initial food picks:")
        for i, f in enumerate(food, 1):
            cap = (f.get("grade") or 0) * 10
            runway = max(0, cap - (f.get("level") or 0))
            print(f"    slot {i}: id={f['id']} R{f['rarity']}/G{f['grade']}/L{f['level']} {f['name']} (runway: {runway})")
        return 0

    # Initial squad set.
    food_pool = [h for h in heroes if is_food_eligible(h, reserved, protected, args.max_rarity)]
    excluded = {carry["id"]}
    food = []
    for _ in range(args.food_slots):
        f = pick_food_slot(food_pool, excluded, args.max_rarity)
        if f is None:
            print("WARN: ran out of food candidates before filling all slots")
            break
        food.append(f)
        excluded.add(f["id"])
    if not food:
        print("ERROR: no food candidates available", file=sys.stderr)
        return 1

    initial_team = [carry["id"]] + [f["id"] for f in food]
    print(f"\n--- iter 0: setting squad {initial_team} ---")
    r = squad_set(initial_team)
    print(f"  squad-set: {r}")
    if not r.get("ok"):
        print(f"ERROR: failed to set initial squad", file=sys.stderr)
        return 1

    completed = 0
    failures = 0
    rank_ups = 0
    consumed_food: set[int] = set()  # food sacrificed by rank-ups; need replacements

    while True:
        # Stop conditions
        if args.runs and completed >= args.runs:
            print(f"\nDONE: hit --runs target ({completed}/{args.runs})")
            break
        if args.until_energy is not None:
            try:
                res = _get("/all-resources", timeout=10)
                e = res.get("Energy", 0)
                if e <= args.until_energy:
                    print(f"\nDONE: energy {e} <= --until-energy {args.until_energy}")
                    break
            except Exception:
                pass

        # Start battle.
        print(f"\n--- iter {completed+1}: starting battle ---")
        r = start_battle()
        if r.get("error"):
            print(f"  start-battle err: {r}")
            failures += 1
            if failures >= 3:
                print(f"  3 consecutive start failures; aborting.")
                break
            continue
        outcome = wait_for_finish(timeout_s=300)
        if outcome != "finish":
            print(f"  battle wait: {outcome}")
            failures += 1
            if failures >= 3: break
            continue
        completed += 1
        # Close finish dialog → back to battle setup.
        close_finish_dialog()
        time.sleep(2)
        if not is_on_battle_setup():
            # Wait a bit longer for setup to re-appear.
            wait_for_setup(timeout_s=30)

        # Re-read state & rank-up any maxed food.
        if args.auto_rank_up:
            heroes = fetch_heroes()
            results = auto_rank_up_maxed(heroes, reserved, protected, args.max_rarity)
            for r in results:
                if r.get("from_grade"):
                    print(f"  + ranked up {r['target']} G{r['from_grade']}→G{r['to_grade']} "
                          f"(consumed {len(r['consumed'])})")
                    rank_ups += 1
                    consumed_food.update(r["consumed"])

        # Refresh squad: replace consumed/maxed food with fresh picks.
        heroes = fetch_heroes()
        cur_squad = squad_current()
        new_food: list[int] = []
        food_pool = [h for h in heroes if is_food_eligible(h, reserved, protected, args.max_rarity)]
        excluded = {carry["id"]} | set(consumed_food)
        # Keep food from current squad if still un-maxed and eligible.
        cur_by_id = {h["id"]: h for h in heroes}
        for hid in cur_squad:
            if hid == carry["id"]: continue
            h = cur_by_id.get(hid)
            if not h: continue
            if at_level_cap(h) or not is_food_eligible(h, reserved, protected, args.max_rarity):
                continue  # skip this slot, will refill
            new_food.append(hid)
            excluded.add(hid)
        # Fill remaining slots.
        while len(new_food) < args.food_slots:
            f = pick_food_slot(food_pool, excluded, args.max_rarity)
            if f is None:
                print(f"  no more food candidates; ending loop with {len(new_food)} food slots filled")
                break
            new_food.append(f["id"])
            excluded.add(f["id"])

        target_team = [carry["id"]] + new_food
        if target_team != [carry["id"]] + cur_squad[1:] if cur_squad else True:
            print(f"  squad change → {target_team}")
            squad_set(target_team)

        if not new_food:
            print(f"  no food left — stopping")
            break

    print(f"\n=== Summary ===")
    print(f"  battles: {completed}")
    print(f"  rank-ups: {rank_ups}")
    print(f"  failures: {failures}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
