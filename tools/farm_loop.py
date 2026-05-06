#!/usr/bin/env python3
"""Campaign farm loop: drives squad rotation + battle replay + auto rank-up.

Pre-conditions:
  - Game is on a campaign battle-setup dialog (StoryHeroesSelectionDialog).
    For now you navigate there manually (Campaign -> chapter -> stage tile).
    Auto-open is a follow-up — needs StageId discovery.

Workflow each iteration:
  1. Read /all-heroes — find food champs at level cap (L = grade*10) and
     same-grade fodder needed for rank-ups.
  2. Set the squad: carry in slot 1 + 4 lowest-rarity unleveled food in
     slots 2-5 via /squad-set.
  3. Start battle (StartBattle on the active dialog context).
  4. Poll until finish dialog appears, read win/loss.
  5. After battle: re-fetch /all-heroes; for any food now at cap ->
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
    """Hit Replay on the BattleFinish dialog. Newer dialogs (Story) use
    OnQuickRestartPressed; older (Campaign) might use the same. Skips going
    back to battle-setup, replays the same battle directly."""
    dlgs = list_active_dialogs()
    finish_dialog = next((d for d in dlgs if "BattleFinish" in d), None)
    if not finish_dialog:
        return {"error": "no battle-finish dialog active"}
    path = f"UIManager/Canvas (Ui Root)/Dialogs/{finish_dialog}"
    return _get(f"/context-call?path={urllib.parse.quote(path)}&method=OnQuickRestartPressed")


def is_on_finish() -> bool:
    return any("BattleFinish" in d for d in list_active_dialogs())


def is_on_loading() -> bool:
    return any("BattleLoading" in d for d in list_active_dialogs())


def wait_for_battle_active(timeout_s: int = 120) -> str:
    """After a quick-restart we expect Loading -> BattleHUD. Returns the
    state we landed on."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        dlgs = list_active_dialogs()
        if any("BattleHUD" in d for d in dlgs): return "battle"
        if any("MessageBox" in d for d in dlgs): return "block"
        time.sleep(2)
    return "timeout"


def close_finish_dialog() -> dict:
    """Close the BattleFinish dialog -> returns to battle setup. Different
    BattleFinish variants expose different close-methods; try in order."""
    dlgs = list_active_dialogs()
    finish_dialog = next((d for d in dlgs if "BattleFinish" in d), None)
    if not finish_dialog:
        return {"error": "no battle-finish dialog active"}
    path = f"UIManager/Canvas (Ui Root)/Dialogs/{finish_dialog}"
    last = None
    # Close = generic; OnLobbyPressed for Story; OnContinue for Campaign.
    for method in ("Close", "OnLobbyPressed", "OnContinue"):
        last = _get(f"/context-call?path={urllib.parse.quote(path)}&method={method}")
        if last and not last.get("error"):
            return last
    return last or {"error": "no close method matched"}


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


def fetch_artifact_ids() -> set[int]:
    """Snapshot of every artifact instance id the user owns. We diff this
    snapshot before/after each battle to find newly-dropped artifacts."""
    try:
        r = _get("/all-artifacts?limit=20000", timeout=30)
        return {a.get("id") for a in r.get("artifacts", []) if a.get("id")}
    except Exception:
        return set()


def sell_artifacts(ids: list[int]) -> dict:
    if not ids:
        return {"ok": True, "sold": []}
    csv = ",".join(str(i) for i in ids)
    return _get(f"/sell-artifacts?ids={csv}", timeout=60)


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
    ap.add_argument("--auto-rank-up", action="store_true", default=False,
                    help="Auto-rank-up maxed food after each battle (default OFF — "
                         "preferred workflow: accumulate maxed food, batch rank-up "
                         "via champ_manager.py).")
    ap.add_argument("--no-auto-rank-up", dest="auto_rank_up", action="store_false")
    ap.add_argument("--auto-sell-drops", action="store_true", default=True,
                    help="Auto-sell artifacts dropped during the loop (default ON). "
                         "Anything new since the loop started is treated as farm junk.")
    ap.add_argument("--no-auto-sell-drops", dest="auto_sell_drops", action="store_false")
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

    # Sanity: we should be on either battle setup OR a finish dialog
    # (resuming from a paused loop). If on finish, the main loop will detect
    # it and use OnQuickRestartPressed for the first iteration.
    dlgs = list_active_dialogs()
    print(f"  active dialogs: {dlgs}")
    if not is_on_battle_setup() and not is_on_finish():
        print("\nERROR: not on a campaign battle-setup OR battle-finish dialog. "
              "Navigate to a campaign stage in-game first "
              "(Campaign -> chapter -> stage tile).",
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

    # Initial squad set. Preserve any existing squad members that are still
    # un-maxed eligible food — saves their accumulated XP from earlier
    # battles. Only pick fresh food for empty slots.
    food_pool = [h for h in heroes if is_food_eligible(h, reserved, protected, args.max_rarity)]
    cur_by_id_init = {h["id"]: h for h in heroes}
    pre_squad = squad_current()
    excluded = {carry["id"]}
    food = []
    # First pass: keep existing food that's still good.
    for hid in pre_squad:
        if hid == carry["id"]: continue
        if hid in excluded: continue
        h = cur_by_id_init.get(hid)
        if not h: continue
        if at_level_cap(h): continue  # maxed, will be ranked-up later
        if not is_food_eligible(h, reserved, protected, args.max_rarity): continue
        food.append(h)
        excluded.add(hid)
        if len(food) >= args.food_slots: break
    # Second pass: fill remaining slots with fresh picks.
    while len(food) < args.food_slots:
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

    # If we're starting on a finish dialog (resumed mid-session), the
    # underlying battle-setup dialog has been removed and we cannot
    # /squad-set. Trust whatever is in the squad and just skip squad-set
    # — OnQuickRestartPressed will replay with the existing setup.
    skip_initial_squad_set = is_on_finish() and not is_on_battle_setup()
    if skip_initial_squad_set:
        print(f"\n--- iter 0: starting on finish dialog, skipping initial squad-set ---")
        print(f"  (loop will replay with whatever squad was last set)")
    else:
        print(f"\n--- iter 0: prepping squad {initial_team} ---")

        # Pre-step: move any team member from Reserve Vault / Master Vault to
        # Champion list. The server rejects CreateBattle if the squad has any
        # non-Inventory hero. Plus, AddHero silently no-ops on Reserve Vault
        # heroes — they need to be in Inventory first.
        by_id = {h["id"]: h for h in heroes}
        move_ids = []
        for hid in initial_team:
            h = by_id.get(hid, {})
            if h.get("in_storage") or h.get("in_bathhouse"):
                move_ids.append(hid)
        if move_ids:
            ids_csv = ",".join(str(i) for i in move_ids)
            print(f"  moving {len(move_ids)} squad members to Champion list...")
            try:
                r = _get(f"/move-heroes?dest=inventory&ids={ids_csv}")
                print(f"  move: {r}")
            except Exception as ex:
                print(f"  ERR move: {ex}")
            time.sleep(2)  # let server commit

        print(f"  setting squad {initial_team}")
        r = squad_set(initial_team)
        print(f"  squad-set: {r}")
        if not r.get("ok"):
            print(f"ERROR: failed to set initial squad", file=sys.stderr)
            return 1

    completed = 0
    failures = 0
    rank_ups = 0
    consumed_food: set[int] = set()  # food sacrificed by rank-ups; need replacements
    sold_total = 0

    # Snapshot artifacts BEFORE the first battle so we can identify drops.
    pre_artifacts = fetch_artifact_ids() if args.auto_sell_drops else set()
    if args.auto_sell_drops:
        print(f"  artifact baseline: {len(pre_artifacts)} owned")

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

        # Decide how to start this iteration based on current dialog state:
        # - finish dialog up:        OnQuickRestartPressed (in-place replay)
        # - battle setup up:         StartBattle
        # - battle already running:  the auto-replay or game's auto-battle
        #                            kicked in; just wait for it to finish
        # - anything else:           one-shot retry, then bail
        if is_on_finish():
            print(f"\n--- iter {completed+1}: quick-restart from finish dialog ---")
            r = quick_restart()
        elif is_on_battle_setup():
            print(f"\n--- iter {completed+1}: starting battle ---")
            r = start_battle()
        elif is_on_loading() or any("BattleHUD" in d for d in list_active_dialogs()):
            print(f"\n--- iter {completed+1}: battle already running (auto-restart caught it) ---")
            r = {"ok": True}  # nothing to do; just wait for finish
        else:
            print(f"\n--- iter {completed+1}: unexpected state {list_active_dialogs()}, aborting ---")
            failures += 1
            if failures >= 3:
                print(f"  3 consecutive failures; aborting.")
                break
            time.sleep(3)
            continue
        if r.get("error"):
            print(f"  start-battle err: {r}")
            failures += 1
            if failures >= 3:
                print(f"  3 consecutive start failures; aborting.")
                break
            continue
        # After QuickRestart, we expect to leave the finish dialog and enter
        # BattleLoading -> BattleHUD. After StartBattle, same path.
        outcome = wait_for_finish(timeout_s=300)
        if outcome != "finish":
            print(f"  battle wait: {outcome}")
            failures += 1
            if failures >= 3: break
            continue
        completed += 1

        # Auto-sell any newly-dropped artifacts. The campaign farm stage
        # gives low-rarity drops we don't want to keep — sell everything
        # that's appeared since the loop started.
        if args.auto_sell_drops:
            cur_artifacts = fetch_artifact_ids()
            new_drops = list(cur_artifacts - pre_artifacts)
            if new_drops:
                print(f"  selling {len(new_drops)} new artifact drop(s)")
                try:
                    sr = sell_artifacts(new_drops)
                    n_sold = len(sr.get("sold", []))
                    sold_total += n_sold
                    if n_sold > 0:
                        print(f"  + sold {n_sold}")
                    skipped = sr.get("skipped") or []
                    if skipped:
                        print(f"  - skipped {len(skipped)}: {skipped[:3]}")
                except Exception as ex:
                    print(f"  ERR sell: {ex}")
                # Update baseline to current to avoid re-trying skipped drops.
                pre_artifacts = cur_artifacts - set(sr.get("sold", []))

        # Re-read state & rank-up any maxed food. (Squad context is still
        # accessible while finish dialog is open — the dialog underneath stays.)
        if args.auto_rank_up:
            heroes = fetch_heroes()
            results = auto_rank_up_maxed(heroes, reserved, protected, args.max_rarity)
            for r in results:
                if r.get("from_grade"):
                    print(f"  + ranked up {r['target']} G{r['from_grade']}->G{r['to_grade']} "
                          f"(consumed {len(r['consumed'])})")
                    rank_ups += 1
                    consumed_food.update(r["consumed"])

        # NOTE: while finish dialog is up, the underlying battle-setup
        # dialog is REMOVED from the scene tree (verified: only
        # BattleFinishStoryDialog remains). So we cannot /squad-set
        # mid-loop. If food has maxed out, exit and let the user reset
        # by going back to battle setup manually.
        heroes = fetch_heroes()
        squad_ids = {f["id"] for f in food}
        squad_at_cap = [h for h in heroes if h.get("id") in squad_ids and at_level_cap(h)]
        if squad_at_cap:
            print(f"  food at level cap: {[h['name']+'/'+str(h['id']) for h in squad_at_cap]}")
            print(f"  exiting loop so you can rank-up + reset squad")
            break
        # End of iteration. Loop back to top — quick-restart from the
        # finish dialog will fire next iter.

    print(f"\n=== Summary ===")
    print(f"  battles: {completed}")
    print(f"  rank-ups: {rank_ups}")
    print(f"  artifacts sold: {sold_total}")
    print(f"  failures: {failures}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
