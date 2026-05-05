#!/usr/bin/env python3
"""Auto-level food champions on a campaign stage, with optional rank-up.

Pipeline (mirrors RSL Helper's Multi-Level XP):
  1. Pick a campaign stage (default 12-3 Brutal)
  2. Apply a saved preset whose lead slot has the leveling farmer
  3. Run N battles back-to-back (auto-replay via dungeon_run primitives)
  4. After each victory, scan /all-heroes for food champs at target level
  5. If --auto-rank-up, sacrifice them via /rank-up
  6. Refresh squad and continue until stop condition

Reserved-hero filter (`data/reserved_heroes.json`) prevents sacrificing
champs that are slotted in CB / Dragon / Spider / Iron Twins presets, or
flagged as future-team-buildable. RSL Helper requires manual locking;
we read it from preset state automatically.

Usage:
    # Level Common-rarity food on 12-3 Brutal until energy runs out
    python3 tools/level_food.py --stage 12 --substage 3 --difficulty brutal \\
        --preset 1 --food-rarity-max common --food-level-target 7 \\
        --until-energy 0

    # Same but with auto-rank-up + auto-sell after rank 2
    python3 tools/level_food.py --stage 12 --substage 3 --difficulty brutal \\
        --preset 1 --food-level-target 6 --auto-rank-up

Status: MVP. Stages, rank-up logic, and stop conditions wired. Smart
stage selection (--auto-stage) and skill-book feeding to come in
phase 4.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"

RARITY_RANK = {"common": 1, "uncommon": 2, "rare": 3, "epic": 4, "legendary": 5}
# /all-heroes returns rarity as int (Plarium internal: 1=Common, 2=Uncommon,
# 3=Rare, 4=Epic, 5=Legendary). The CLI takes a string; this is the bridge.
RARITY_INT_TO_RANK = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
# Per RSL Helper community advice (and AyumiLove's leveling guide):
# food champs cap their leveling at the "max useful" level for their rank,
# beyond which XP/energy is wasted.
LEVEL_TARGETS_DEFAULT = {1: 7, 2: 13, 3: 19, 4: 25, 5: 31, 6: 37}


def _get(path: str, timeout: int = 15) -> dict:
    with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def _post_lite(path: str, timeout: int = 30) -> dict:
    """Mod doesn't distinguish GET vs POST — same urlopen call."""
    return _get(path, timeout)


def load_reserved_set() -> set[int]:
    """Read data/reserved_heroes.json (instance ids) — these are NEVER
    sacrificed as food. Auto-built by tools/build_reserved_set.py from
    preset memberships + HH wishlist. Falls back to empty set if missing."""
    p = PROJECT_ROOT / "data" / "reserved_heroes.json"
    if not p.exists():
        return set()
    try:
        d = json.loads(p.read_text())
        return set(int(x) for x in d.get("reserved", []))
    except Exception as e:
        print(f"  WARN: reserved_heroes.json unreadable ({e}); treating as empty",
              file=sys.stderr)
        return set()


def load_protected_set() -> dict:
    """Read data/protected_heroes.json — config of heroes never to sacrifice.
    Schema: { exclude_all_legendaries: bool, exclude_all_epics: bool,
              protected_names: [str], fusion_targets: [str] }."""
    p = PROJECT_ROOT / "data" / "protected_heroes.json"
    if not p.exists():
        return {"exclude_all_legendaries": True, "exclude_all_epics": False,
                "protected_names": [], "fusion_targets": []}
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"  WARN: protected_heroes.json unreadable ({e}); using defaults",
              file=sys.stderr)
        return {"exclude_all_legendaries": True, "exclude_all_epics": False,
                "protected_names": [], "fusion_targets": []}


def fetch_heroes() -> list[dict]:
    return _get("/all-heroes").get("heroes", [])


def is_food_eligible(h: dict, *, rarity_max: str, reserved: set[int],
                     skip_locked: bool, skip_vault: bool,
                     skip_in_storage: bool = True,
                     protected: dict | None = None) -> bool:
    """Decide whether a hero can be used as food."""
    if h.get("id") in reserved:
        return False
    if skip_locked and h.get("locked"):
        return False
    if skip_vault and h.get("in_storage"):
        # `in_storage` = Master Vault.
        return False
    if skip_in_storage and h.get("in_storage"):
        return False
    if h.get("is_faction_guardian"):
        # Always exclude — server cmd hard-fails on guardian heroes.
        return False
    # Empowered heroes (opt-in via protected_heroes.json, default true)
    if (protected is not None
            and protected.get("exclude_empowered", True)
            and (h.get("empower") or 0) > 0):
        return False
    # Fusion ingredients — hard exclude.
    if h.get("is_fusion_ingredient"):
        return False
    rarity_val = h.get("rarity")
    if rarity_val is not None and rarity_max:
        max_rank = RARITY_RANK.get(rarity_max.lower(), 99)
        cur_rank = (RARITY_INT_TO_RANK.get(rarity_val, 99)
                    if isinstance(rarity_val, int)
                    else RARITY_RANK.get(str(rarity_val).lower(), 99))
        if cur_rank > max_rank:
            return False
    if protected is not None:
        # in_bathhouse = "Reserve Vault" in the game UI. Opt-in exclusion.
        if protected.get("exclude_reserve_vault", False) and h.get("in_bathhouse"):
            return False
        if protected.get("exclude_all_legendaries", True) and rarity_val == 5:
            return False
        if protected.get("exclude_all_epics", False) and rarity_val == 4:
            return False
        name = h.get("name", "")
        if name in protected.get("protected_names", []):
            return False
        if name in protected.get("fusion_targets", []):
            return False
    return True


def is_at_level_target(h: dict, target_overrides: dict[int, int] | None) -> bool:
    """True if hero has reached their per-rank level cap (i.e. is "done")."""
    grade = h.get("grade", 1)
    targets = target_overrides or LEVEL_TARGETS_DEFAULT
    cap = targets.get(grade, 99)
    return h.get("level", 0) >= cap


def pick_rank_up_food(food_pool: list[dict], target_grade: int,
                      reserved: set[int]) -> list[int] | None:
    """Pick `target_grade` food heroes of the right rarity to rank up
    a target. Rank-up rules: need N (= target_grade) heroes of the SAME
    grade as the target. Returns instance ids, or None if not enough."""
    candidates = [h for h in food_pool
                  if h.get("grade", 0) == target_grade
                  and h.get("id") not in reserved
                  and not h.get("locked")]
    if len(candidates) < target_grade:
        return None
    candidates.sort(key=lambda h: h.get("level", 0))
    return [h["id"] for h in candidates[:target_grade]]


def open_campaign_stage(chapter: int, substage: int, difficulty: str) -> bool:
    """Navigate to a campaign stage. Difficulty: normal/hard/brutal/nightmare.
    NOTE: This requires a campaign-open mod endpoint. The current mod has
    `/navigate?target=campaign` (opens the campaign HUD) but no stage-tile
    invoker yet. For the MVP, we expect the caller to have manually
    opened the right hero-selection screen in-game (or to have run
    dungeon_run.py to set it up). The food-loop then drives StartBattle
    + replay via the same primitives dungeon_run uses."""
    print(f"  (expecting campaign {chapter}-{substage} {difficulty} hero-selection dialog open)")
    return any('HeroesSelection' in d for d in _list_dialogs())


def _list_dialogs() -> list[str]:
    try:
        d = _get('/view-contexts')
    except Exception:
        return []
    return [c.get('dialog', '') for c in d.get('contexts', [])]


def _wait_for_finish_or_block(timeout_s: int = 600) -> str:
    """Local copy of dungeon_run's finish-detector — kept inline to
    avoid making level_food import-bound on dungeon_run's module-level
    LoopController state."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        dlgs = _list_dialogs()
        if any('MessageBox' in d for d in dlgs):
            return 'blocked'
        if any('BattleFinish' in d for d in dlgs):
            return 'finish'
        time.sleep(2)
    return 'timeout'


def run_one_battle(preset_id: int | None) -> tuple[bool, str]:
    """Apply preset (if given), start campaign battle, wait for finish,
    return (won, status)."""
    # Apply preset on the hero-selection dialog if requested
    if preset_id is not None:
        try:
            r = _get(f'/apply-preset?id={preset_id}')
        except Exception as ex:
            return False, f'apply_preset_err:{ex}'
        if 'error' in r:
            return False, f'apply_preset_err:{r["error"]}'

    # Find the selection dialog and StartBattle
    dlgs = _list_dialogs()
    sel = next((d for d in dlgs if 'HeroesSelection' in d), None)
    if not sel:
        return False, 'no_hero_selection_dialog'
    sel_path = f'UIManager/Canvas (Ui Root)/Dialogs/{sel}'
    try:
        urllib.request.urlopen(
            f'{MOD_BASE}/context-call?path={urllib.parse.quote(sel_path)}&method=StartBattle',
            timeout=15
        ).read()
    except Exception as ex:
        return False, f'start_battle_err:{ex}'

    # Some hero comps trigger NoAuraSkillConfirmationOverlay — handle it
    time.sleep(2)
    for d in _list_dialogs():
        if 'NoAuraSkillConfirmation' in d:
            ov_path = f'UIManager/Canvas (Ui Root)/OverlayDialogs/{d}'
            urllib.request.urlopen(
                f'{MOD_BASE}/context-call?path={urllib.parse.quote(ov_path)}&method=OnContinue',
                timeout=10
            ).read()

    outcome = _wait_for_finish_or_block(timeout_s=300)
    if outcome != 'finish':
        return False, f'wait_{outcome}'
    # Read verdict from the finish dialog text
    try:
        r = _get(f'/get-text?path={urllib.parse.quote("UIManager/Canvas (Ui Root)/Dialogs/[DV] BattleFinishCampaignDialog")}')
    except Exception:
        r = {'texts': []}
    text = ' | '.join(t.get('text', '') for t in r.get('texts', []))
    won = 'VICTORY' in text or 'Victory' in text
    return won, 'victory' if won else 'defeat'


def replay_battle() -> tuple[bool, str]:
    """Hit the in-game Replay button on the BattleFinishCampaignDialog.
    Returns same (won, status) shape."""
    fin_path = 'UIManager/Canvas (Ui Root)/Dialogs/[DV] BattleFinishCampaignDialog'
    try:
        urllib.request.urlopen(
            f'{MOD_BASE}/context-call?path={urllib.parse.quote(fin_path)}&method=OnQuickRestartPressed',
            timeout=10
        ).read()
    except Exception as ex:
        return False, f'replay_err:{ex}'
    # Wait for the OLD finish dialog to clear before polling
    time.sleep(3)
    outcome = _wait_for_finish_or_block(timeout_s=300)
    if outcome != 'finish':
        return False, f'wait_{outcome}'
    try:
        r = _get(f'/get-text?path={urllib.parse.quote(fin_path)}')
    except Exception:
        r = {'texts': []}
    text = ' | '.join(t.get('text', '') for t in r.get('texts', []))
    won = 'VICTORY' in text or 'Victory' in text
    return won, 'victory' if won else 'defeat'


def run_loop(args, reserved: set[int], protected: dict | None = None) -> dict:
    """Main pipeline. Returns summary dict."""
    completed = 0
    ranked = 0
    failures = 0

    while True:
        # Stop conditions
        if args.runs and completed >= args.runs:
            print(f"  loop end: hit --runs target ({completed}/{args.runs})")
            break

        # Energy gate
        try:
            res = _get("/all-resources")
            energy = res.get("Energy", 0)
        except Exception:
            energy = -1
        if args.until_energy is not None and energy <= args.until_energy:
            print(f"  loop end: energy {energy} <= --until-energy {args.until_energy}")
            break

        # Snapshot the pool of food before the run
        all_heroes = fetch_heroes()
        food_pool = [h for h in all_heroes
                     if is_food_eligible(h, rarity_max=args.food_rarity_max,
                                         reserved=reserved,
                                         skip_locked=args.skip_locked,
                                         skip_vault=args.skip_vault,
                                         protected=protected)]
        if not food_pool:
            print(f"  loop end: no food champs match filter")
            break

        print(f"  iter {completed+1}: {len(food_pool)} food candidates, energy={energy}")

        # On the first iteration, we're sitting on the hero-selection
        # dialog (caller manually navigated). Use StartBattle. After
        # that, hit Replay from the finish dialog.
        if completed == 0:
            won, status = run_one_battle(args.preset)
        else:
            won, status = replay_battle()
        print(f"    {status}")
        if not won:
            failures += 1
            if failures >= args.max_fails:
                print(f"  loop end: {failures} failures hit --max-fails")
                break
        completed += 1

        # Auto-rank-up step
        if args.auto_rank_up:
            # Re-fetch after the (manual) battle
            all_heroes = fetch_heroes()
            food_pool = [h for h in all_heroes
                         if is_food_eligible(h, rarity_max=args.food_rarity_max,
                                             reserved=reserved,
                                             skip_locked=args.skip_locked,
                                             skip_vault=args.skip_vault,
                                             protected=protected)]
            target_overrides = (
                {1: args.food_level_target} if args.food_level_target else None
            )
            done = [h for h in food_pool
                    if is_at_level_target(h, target_overrides)]
            for h in done:
                food_for_rank_up = pick_rank_up_food(food_pool, h["grade"], reserved)
                if not food_for_rank_up:
                    print(f"    skip rank-up of hero {h['id']}: not enough "
                          f"grade-{h['grade']} food")
                    continue
                food_csv = ",".join(str(x) for x in food_for_rank_up)
                try:
                    r = _get(f"/rank-up?hero_id={h['id']}&food={food_csv}")
                except Exception as ex:
                    print(f"    rank-up err: {ex}")
                    continue
                if r.get("ok"):
                    ranked += 1
                    print(f"    ranked up hero {h['id']} ({h.get('name')}) "
                          f"using food {food_csv}")
                    # After rank-up, the food champs are gone — refresh.
                    all_heroes = fetch_heroes()
                    food_pool = [h2 for h2 in all_heroes
                                 if is_food_eligible(h2, rarity_max=args.food_rarity_max,
                                                     reserved=reserved,
                                                     skip_locked=args.skip_locked,
                                                     skip_vault=args.skip_vault,
                                                     protected=protected)]
                else:
                    print(f"    rank-up failed: {r.get('error')}")

    return {"completed": completed, "ranked_up": ranked, "failures": failures}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", type=int, default=12, help="Campaign chapter")
    ap.add_argument("--substage", type=int, default=3, help="Campaign substage")
    ap.add_argument("--difficulty", choices=["normal", "hard", "brutal", "nightmare"],
                    default="brutal")
    ap.add_argument("--preset", type=int, default=None,
                    help="Saved preset ID for the leveling team (lead + food slots)")
    ap.add_argument("--food-rarity-max", default="uncommon",
                    choices=list(RARITY_RANK.keys()),
                    help="Highest rarity allowed as food (default: uncommon)")
    ap.add_argument("--food-level-target", type=int, default=None,
                    help="Override level cap for food (default: per-rank table)")
    ap.add_argument("--skip-locked", action="store_true", default=True,
                    help="Skip locked champs (default ON)")
    ap.add_argument("--no-skip-locked", dest="skip_locked", action="store_false")
    ap.add_argument("--skip-vault", action="store_true", default=True,
                    help="Skip vaulted champs (default ON)")
    ap.add_argument("--no-skip-vault", dest="skip_vault", action="store_false")
    ap.add_argument("--auto-rank-up", action="store_true",
                    help="Auto-sacrifice food champs at level cap to rank-up")
    ap.add_argument("--runs", type=int, default=0,
                    help="Run N battles then stop (0 = run until --until-energy)")
    ap.add_argument("--until-energy", type=int, default=None,
                    help="Stop when energy drops to this level (e.g. 0)")
    ap.add_argument("--poll-interval", type=float, default=2.0,
                    help="Seconds between iterations in MVP placeholder loop")
    ap.add_argument("--max-fails", type=int, default=3,
                    help="Tolerate up to N defeats before aborting (default 3)")
    ap.add_argument("--list-only", action="store_true",
                    help="Just print the food candidate list and exit. No battles.")
    ap.add_argument("--show-targets", action="store_true",
                    help="List which heroes WOULD be ranked up right now "
                         "(those at level cap) and exit.")
    args = ap.parse_args()

    # Sanity
    if not args.list_only and not args.show_targets:
        if not args.runs and args.until_energy is None:
            ap.error("Specify --runs N or --until-energy 0 (otherwise this loops forever)")

    reserved = load_reserved_set()
    protected = load_protected_set()
    print(f"Reserved-set: {len(reserved)} hero ids "
          f"(from data/reserved_heroes.json)")
    excl = []
    if protected.get("exclude_all_legendaries"): excl.append("legendaries")
    if protected.get("exclude_all_epics"): excl.append("epics")
    if protected.get("fusion_targets"): excl.append(f"fusions={protected['fusion_targets']}")
    if protected.get("protected_names"): excl.append(f"named={protected['protected_names']}")
    if excl:
        print(f"Protected: {', '.join(excl)}")

    # Snapshot before
    heroes = fetch_heroes()
    food_pool = [h for h in heroes
                 if is_food_eligible(h, rarity_max=args.food_rarity_max,
                                     reserved=reserved,
                                     skip_locked=args.skip_locked,
                                     skip_vault=args.skip_vault,
                                     protected=protected)]
    print(f"Food candidates: {len(food_pool)} "
          f"(rarity <= {args.food_rarity_max}, "
          f"reserved excluded: {len(reserved)})")

    rarities = Counter(h.get("rarity") for h in food_pool)
    grades = Counter(h.get("grade") for h in food_pool)
    print(f"  by rarity: {dict(rarities)}")
    print(f"  by grade:  {dict(grades)}")

    if args.list_only:
        print("\nFood candidate list (rarity / grade / level / id / name):")
        food_pool.sort(key=lambda h: (h.get("rarity", 0), h.get("grade", 0), h.get("level", 0)))
        for h in food_pool:
            print(f"  rarity={h.get('rarity')} grade={h.get('grade')} "
                  f"level={h.get('level')} id={h.get('id')} {h.get('name','?')}")
        return 0

    if args.show_targets:
        target_overrides = (
            {1: args.food_level_target} if args.food_level_target else None
        )
        ready = [h for h in food_pool if is_at_level_target(h, target_overrides)]
        print(f"\nReady to rank up ({len(ready)} heroes):")
        for h in ready:
            print(f"  grade={h.get('grade')} level={h.get('level')} "
                  f"id={h.get('id')} {h.get('name','?')}")
        # Show what food would be picked for each
        print("\nFood available per grade:")
        by_grade = Counter(h.get("grade") for h in food_pool)
        for g, c in sorted(by_grade.items()):
            print(f"  grade {g}: {c} candidates")
        return 0

    # Stage open is currently a placeholder until /open-campaign ships
    if not open_campaign_stage(args.stage, args.substage, args.difficulty):
        print("  ERROR: failed to open campaign stage", file=sys.stderr)
        return 1

    summary = run_loop(args, reserved, protected)
    print(f"\nDONE: {summary['completed']} iterations, "
          f"{summary['ranked_up']} rank-ups, "
          f"{summary['failures']} failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
