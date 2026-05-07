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


def finish_edit_team() -> dict:
    """From a BattleFinish dialog, invoke OpenSelectionDialog (Edit Team
    button) which closes the finish dialog and re-opens battle setup
    with the same squad — restoring the squad context for /squad-set."""
    return _get("/finish-edit-team", timeout=15)


def open_stage(stage_id: int) -> dict:
    """Open the heroes-selection dialog for a stage by replicating the
    user's tile-tap. Requires the chapter map (StorylineRegionDialog or
    DungeonRegionDialog) to already be open — the StageContext only
    exists while the chapter is rendered.
    NOTE: the older /open-stage cmd path is dead — OpenStageCmd returns
    server-side 404 since Plarium retired the endpoint. /open-stage-tile
    walks the active scene tree and invokes StageContext.OpenSelectionDialog
    directly, the same way the user's tap does."""
    return _get(f"/open-stage-tile?id={stage_id}", timeout=20)


def goto_stage(stage_meta: dict) -> dict:
    """One-command Village->heroes-selection navigation. `stage_meta`
    must include `stage_id`, `chapter`. Calls in order:
       1. /open-campaign-map (Village -> BattleMode dialog -> world MapHUD)
       2. /open-chapter?n=<chapter>           -> chapter map (RegionDialog)
       3. /open-stage-tile?id=<stage_id>      -> heroes-selection dialog
    Each step polls the resulting dialog before returning. Failures bail
    early with the offending step name."""
    sid = stage_meta["stage_id"]
    chap = stage_meta.get("chapter")
    if not chap:
        return {"error": "stage_meta missing 'chapter' (1..12)"}
    # Step 1a: fire OpenWorldMap (non-blocking — dialog opens async).
    # /open-campaign-map handles both phases:
    #   first call (no BattleMode dialog yet) -> queues OpenWorldMap, returns
    #   second call (BattleMode dialog open)  -> invokes Adventure.OpenMap
    # Loop the call up to 3 times with polls between to ride the async cmds.
    for attempt in range(3):
        r = _get("/open-campaign-map", timeout=15)
        if r.get("error"):
            return {"error": f"step1 open-campaign-map (try {attempt+1}): {r['error']}"}
        # Poll for dialog progression
        deadline = time.time() + 8
        while time.time() < deadline:
            dlgs = list_active_dialogs()
            if any("MapHUD" in d or "RegionDialog" in d
                   or "StoryHeroesSelectionDialog" in d for d in dlgs):
                break
            time.sleep(0.5)
        # If we reached MapHUD or beyond, done with step 1
        dlgs = list_active_dialogs()
        if any("MapHUD" in d or "RegionDialog" in d
               or "StoryHeroesSelectionDialog" in d for d in dlgs):
            break
        # else: BattleModeSelection probably open; loop will re-invoke
        # to advance to MapHUD
    else:
        return {"error": "step1: world map didn't open after 3 /open-campaign-map calls"}
    # Step 2: chapter
    dlgs = list_active_dialogs()
    if not any("RegionDialog" in d or "StoryHeroesSelectionDialog" in d for d in dlgs):
        r = _get(f"/open-chapter?n={chap}", timeout=15)
        if r.get("error"):
            return {"error": f"step2 open-chapter n={chap}: {r['error']}"}
        deadline = time.time() + 8
        while time.time() < deadline:
            if any("RegionDialog" in d or "StoryHeroesSelectionDialog" in d
                   for d in list_active_dialogs()):
                break
            time.sleep(0.5)
    # Step 3: stage tile (skip if already at heroes-selection)
    if not any("StoryHeroesSelectionDialog" in d for d in list_active_dialogs()):
        r = _get(f"/open-stage-tile?id={sid}", timeout=15)
        if r.get("error"):
            return {"error": f"step3 open-stage-tile id={sid}: {r['error']}"}
        deadline = time.time() + 8
        while time.time() < deadline:
            if any("StoryHeroesSelectionDialog" in d for d in list_active_dialogs()):
                break
            time.sleep(0.5)
    return {"ok": True, "stage_id": sid, "chapter": chap}


def get_current_stage_id() -> int | None:
    """Read the live Stage.Id from the open Heroes*Selection dialog.
    Returns None if no dialog is open."""
    try:
        r = _get("/current-stage", timeout=5)
        if r.get("ok"):
            return r.get("stage_id")
    except Exception:
        pass
    return None


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


def fodder_count_by_grade(heroes: list[dict], reserved: set[int],
                           protected: dict, max_rarity: int = 3) -> dict[int, int]:
    """Count of food-eligible heroes at each grade (1..6). Excludes
    legendaries/epics per protection rules — i.e. only commons/uncommons/
    rares contribute. Used to log cascade progress and decide if target
    rank-up has enough fodder."""
    pool = [h for h in heroes if is_food_eligible(h, reserved, protected, max_rarity)]
    out = {g: 0 for g in range(1, 7)}
    for h in pool:
        g = h.get("grade") or 0
        if 1 <= g <= 6:
            out[g] = out.get(g, 0) + 1
    return out


def try_rank_up_target(target_id: int, heroes: list[dict],
                       reserved: set[int], protected: dict,
                       max_rarity: int = 3) -> dict | None:
    """If `target_id` exists, has grade<6, and has N=current_grade same-grade
    non-protected fodder available, fire /rank-up. Returns the rank-up result
    dict (or None if not eligible / not enough fodder)."""
    by_id = {h["id"]: h for h in heroes}
    t = by_id.get(target_id)
    if not t:
        return None
    cur_g = t.get("grade") or 0
    if cur_g >= 6:
        return None  # already maxed
    if not at_level_cap(t):
        return None  # must be at L_g*10 to rank up
    n_needed = cur_g
    pool = [h for h in heroes
            if is_food_eligible(h, reserved, protected, max_rarity)
            and h.get("grade") == cur_g
            and h.get("id") != target_id]
    if len(pool) < n_needed:
        return None
    # Prefer non-leveled fodder (waste less XP)
    pool.sort(key=lambda h: (h.get("level", 0), h.get("rarity", 99), h.get("name", "")))
    food = pool[:n_needed]
    food_csv = ",".join(str(f["id"]) for f in food)
    try:
        r = _get(f"/rank-up?hero_id={target_id}&food={food_csv}", timeout=30)
    except Exception as ex:
        return {"target": t["name"], "ok": False, "error": str(ex)}
    if r.get("ok"):
        return {"target": t["name"], "from_grade": cur_g,
                "to_grade": cur_g + 1,
                "consumed": [f["id"] for f in food]}
    return {"target": t["name"], "ok": False, "error": r.get("error")}


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
    ap.add_argument("--stage-id", type=int, default=None,
                    help="Programmatic Village->battle-setup. If set, the loop "
                         "calls /open-stage?id=N when state-machine lands "
                         "outside of battle-setup/finish/battle (e.g. game "
                         "drops to Village after a 'no replays left' msgbox "
                         "or after losing battle). Capture once via "
                         "/current-stage with the dialog open. Examples: "
                         "1123003 = Campaign 12-3 NM.")
    ap.add_argument("--stage-name", default=None,
                    help="Lookup key in data/farm_stages.json (overrides "
                         "--stage-id when set). e.g. 'campaign-12-3-nightmare'.")
    ap.add_argument("--target-id", type=int, default=None,
                    help="Target hero id to auto-rank-up after each battle's "
                         "cascade. e.g. 19864 for Harima. Implies --auto-rank-up.")
    ap.add_argument("--target-name", default=None,
                    help="Target hero name (resolved at startup). e.g. 'Harima'.")
    ap.add_argument("--target-grade", type=int, default=6,
                    help="Stop when target reaches this grade (default 6 = max).")
    args = ap.parse_args()
    stage_meta = None
    if args.stage_name and not args.stage_id:
        try:
            with open(PROJECT_ROOT / "data" / "farm_stages.json") as f:
                fs = json.load(f)
            stage_meta = fs["stages"][args.stage_name]
            args.stage_id = stage_meta["stage_id"]
            print(f"resolved --stage-name '{args.stage_name}' -> stage_id={args.stage_id} chapter={stage_meta.get('chapter')}")
        except (KeyError, FileNotFoundError) as ex:
            ap.error(f"--stage-name '{args.stage_name}' not in data/farm_stages.json: {ex}")

    # --target-name implies --auto-rank-up (cascade builds fodder)
    if args.target_name or args.target_id:
        args.auto_rank_up = True

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

    # Resolve --target-name / --target-id
    target_hero = None
    if args.target_id:
        target_hero = by_id.get(args.target_id)
        if not target_hero:
            ap.error(f"--target-id {args.target_id} not in roster")
    elif args.target_name:
        target_hero = by_name.get(args.target_name)
        if not target_hero:
            ap.error(f"--target-name '{args.target_name}' not in roster")
        args.target_id = target_hero["id"]

    print(f"=== Farm Loop ===")
    print(f"  carry: id={carry['id']} R{carry['rarity']}/G{carry['grade']}/L{carry['level']} {carry['name']}")
    print(f"  food slots: {args.food_slots} (max rarity: {args.max_rarity})")
    if target_hero:
        print(f"  target: id={target_hero['id']} R{target_hero['rarity']}/"
              f"G{target_hero['grade']}/L{target_hero['level']} {target_hero['name']} "
              f"-> G{args.target_grade}")
        # Initial cascade snapshot
        counts = fodder_count_by_grade(heroes, reserved, protected, args.max_rarity)
        print(f"  fodder by grade (food-eligible only): "
              f"G1={counts.get(1,0)} G2={counts.get(2,0)} G3={counts.get(3,0)} "
              f"G4={counts.get(4,0)} G5={counts.get(5,0)}")

    # Sanity: we should be on either battle setup OR a finish dialog
    # (resuming from a paused loop). If on finish, the main loop will detect
    # it and use OnQuickRestartPressed for the first iteration.
    dlgs = list_active_dialogs()
    print(f"  active dialogs: {dlgs}")
    on_battle_running = (any("BattleHUD" in d for d in dlgs)
                         or any("BattleLoading" in d for d in dlgs))
    if not is_on_battle_setup() and not is_on_finish() and not on_battle_running:
        if stage_meta:
            print(f"\nNot at battle-setup; navigating Village -> chapter "
                  f"{stage_meta.get('chapter')} -> stage {args.stage_id}...")
            nav = goto_stage(stage_meta)
            if nav.get("error"):
                print(f"  goto-stage err: {nav}", file=sys.stderr)
                return 1
            ws = wait_for_setup(timeout_s=20)
            if ws != "setup":
                print(f"  navigation didn't reach setup ({ws})", file=sys.stderr)
                return 1
            dlgs = list_active_dialogs()
            print(f"  navigation OK; now at {dlgs}")
        else:
            print("\nERROR: not on a campaign battle-setup OR battle-finish OR running "
                  "battle. Pass --stage-name <key> from data/farm_stages.json to enable "
                  "auto-navigation, or navigate manually first "
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
    skip_initial_squad_set = (is_on_finish() or on_battle_running) and not is_on_battle_setup()
    # If we're resuming from finish dialog, click "Edit Team" up-front so
    # we land back on battle setup. squad_current can read the live squad
    # there, which is the only way to drive the swap-on-cap logic later.
    if is_on_finish():
        print(f"\n--- iter 0: starting on finish dialog, clicking Edit Team ---")
        r = finish_edit_team()
        print(f"  edit-team: {r}")
        if r.get("ok"):
            time.sleep(2)
            # Re-fetch dialog state — should now be on battle setup.
            if is_on_battle_setup():
                skip_initial_squad_set = False
    if skip_initial_squad_set:
        print(f"\n--- iter 0: starting on running battle, skipping initial squad-set ---")
        print(f"  (loop will continue with whatever squad was last set)")
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
        elif stage_meta:
            # Recovery navigation: full Village -> heroes-selection chain.
            # /goto_stage handles BattleMode dialog -> MapHUD -> RegionDialog
            # -> StoryHeroesSelectionDialog in one call (idempotent at each
            # step — skips stages already past).
            print(f"\n--- iter {completed+1}: recovering via goto_stage(chapter={stage_meta['chapter']}, stage={args.stage_id}) ---")
            nav = goto_stage(stage_meta)
            if nav.get("error"):
                print(f"  goto-stage err: {nav}")
                failures += 1
                if failures >= 3: break
                time.sleep(3)
                continue
            ws = wait_for_setup(timeout_s=20)
            if ws != "setup":
                print(f"  goto-stage didn't reach setup ({ws}); aborting")
                failures += 1
                if failures >= 3: break
                time.sleep(3)
                continue
            r = start_battle()
        elif args.stage_id:
            # Backwards-compat: stage_id without full meta — try tile-only nav.
            print(f"\n--- iter {completed+1}: recovering via /open-stage-tile?id={args.stage_id} ---")
            nav = open_stage(args.stage_id)
            if nav.get("error"):
                print(f"  open-stage err: {nav}")
                failures += 1
                if failures >= 3: break
                time.sleep(3)
                continue
            ws = wait_for_setup(timeout_s=20)
            if ws != "setup":
                print(f"  open-stage didn't reach setup ({ws}); aborting")
                failures += 1
                if failures >= 3: break
                time.sleep(3)
                continue
            r = start_battle()
        else:
            print(f"\n--- iter {completed+1}: unexpected state {list_active_dialogs()}, "
                  f"aborting (pass --stage-id N or --stage-name X to enable recovery) ---")
            failures += 1
            if failures >= 3:
                print(f"  3 consecutive failures; aborting.")
                break
            time.sleep(3)
            continue
        if r.get("error"):
            # Race: game's auto-replay may have advanced state under us
            # (finish->battle). If we now see Loading or BattleHUD, treat
            # as a successful start and ride the wait_for_finish below.
            time.sleep(2)
            dlgs_now = list_active_dialogs()
            if any("BattleHUD" in d or "BattleLoading" in d for d in dlgs_now):
                print(f"  (start-battle err but battle now running — riding it)")
                failures = 0  # reset; auto-replay is working for us
            else:
                print(f"  start-battle err: {r}; current dialogs={dlgs_now}")
                failures += 1
                if failures >= 3:
                    print(f"  3 consecutive start failures; aborting.")
                    break
                time.sleep(3)
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

            # Target-aware: try ranking up the target with same-grade fodder.
            # Loop in case multiple ranks are reachable in one battle.
            if target_hero:
                # Retry fetch — finish-dialog state occasionally returns
                # stale/empty heroes list briefly.
                heroes = []
                for _attempt in range(3):
                    heroes = fetch_heroes()
                    if heroes:
                        break
                    time.sleep(1.5)
            if target_hero and heroes:
                while True:
                    cur = next((h for h in heroes if h["id"] == target_hero["id"]), None)
                    if not cur or (cur.get("grade") or 0) >= args.target_grade:
                        break
                    tr = try_rank_up_target(target_hero["id"], heroes,
                                             reserved, protected, args.max_rarity)
                    if not tr or not tr.get("from_grade"):
                        break
                    print(f"  *** {tr['target']} ranked G{tr['from_grade']}->G{tr['to_grade']} "
                          f"(consumed {len(tr['consumed'])} G{tr['from_grade']} fodder)")
                    rank_ups += 1
                    consumed_food.update(tr["consumed"])
                    heroes = fetch_heroes()
                # Snapshot cascade
                counts = fodder_count_by_grade(heroes, reserved, protected, args.max_rarity)
                cur = next((h for h in heroes if h["id"] == target_hero["id"]), None)
                cg = (cur.get("grade") or 0) if cur else 0
                cl = (cur.get("level") or 0) if cur else 0
                need_grade = cg
                short = max(0, cg - counts.get(cg, 0))
                progress_bar = (f"  target {target_hero['name']} G{cg}/L{cl} -> G{args.target_grade}; "
                               f"need {need_grade} G{cg} fodder ({counts.get(cg,0)} ready"
                               + (f", short {short})" if short else ")"))
                print(progress_bar)
                print(f"  fodder by grade: G1={counts.get(1,0)} G2={counts.get(2,0)} "
                      f"G3={counts.get(3,0)} G4={counts.get(4,0)} G5={counts.get(5,0)}")
                if cg >= args.target_grade:
                    print(f"\n*** TARGET REACHED: {target_hero['name']} is G{cg} (>= G{args.target_grade}) ***")
                    break

        # If any food in the squad has hit level cap, swap them out for
        # fresh L1 fodder. The /finish-edit-team mod endpoint clicks the
        # in-game "Edit Team" button (OpenSelectionDialog), which closes
        # the finish dialog and re-opens battle setup with the current
        # squad — squad-context becomes addressable again.
        heroes = fetch_heroes()
        squad_ids = {f["id"] for f in food}
        cur_by_id = {h["id"]: h for h in heroes}
        maxed = [cur_by_id[hid] for hid in squad_ids
                 if hid in cur_by_id and at_level_cap(cur_by_id[hid])]
        if maxed:
            print(f"  food at level cap: {[h['name']+'/'+str(h['id']) for h in maxed]}")
            # Pick replacements from the same eligible pool, excluding what's
            # already in the squad (un-maxed) and any previously-consumed.
            food_pool = [h for h in heroes if is_food_eligible(
                            h, reserved, protected, args.max_rarity)]
            keep = [hid for hid in squad_ids
                    if hid in cur_by_id
                    and not at_level_cap(cur_by_id[hid])
                    and is_food_eligible(cur_by_id[hid], reserved, protected, args.max_rarity)]
            excluded = {carry["id"]} | set(keep) | set(consumed_food) | squad_ids
            new_picks = []
            for _ in range(len(maxed)):
                p = pick_food_slot(food_pool, excluded, args.max_rarity)
                if p is None:
                    print(f"  no more fresh food left; ending loop")
                    break
                new_picks.append(p)
                excluded.add(p["id"])
            if not new_picks:
                break
            target_team = [carry["id"]] + keep + [p["id"] for p in new_picks]
            print(f"  swapping {len(maxed)} maxed for fresh: -> {target_team}")

            # Pre-move any Reserve Vault picks to Inventory.
            move_ids = [p["id"] for p in new_picks
                        if p.get("in_storage") or p.get("in_bathhouse")]
            if move_ids:
                ids_csv = ",".join(str(i) for i in move_ids)
                try:
                    _get(f"/move-heroes?dest=inventory&ids={ids_csv}")
                    time.sleep(1)
                except Exception:
                    pass

            # Click "Edit Team" — re-opens battle setup.
            r = finish_edit_team()
            print(f"  edit-team: {r}")
            if not r.get("ok"):
                print(f"  exiting (couldn't re-open battle setup)")
                break
            time.sleep(2)  # let the dialog transition

            # Now squad-set works. Push the new squad.
            r = squad_set(target_team)
            print(f"  squad-set: {r}")
            if not r.get("ok"):
                print(f"  exiting (squad-set failed: {r.get('error')})")
                break

            # Update local food tracking for the next iter check.
            food = [cur_by_id[hid] for hid in keep if hid in cur_by_id] + new_picks
            # Next iter: is_on_battle_setup() will be true, StartBattle path.
        # End of iteration. Loop back to top — quick-restart fires when
        # we're still on the finish dialog (no swap), or StartBattle when
        # we just edited the team.

    print(f"\n=== Summary ===")
    print(f"  battles: {completed}")
    print(f"  rank-ups: {rank_ups}")
    print(f"  artifacts sold: {sold_total}")
    print(f"  failures: {failures}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
