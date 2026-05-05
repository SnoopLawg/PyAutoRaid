#!/usr/bin/env python3
"""Plan the optimal rank-up sequence for currently-maxed heroes.

Reads /all-heroes + reserved-set, finds heroes at level cap, and computes:
  - Which targets we can rank up RIGHT NOW (have enough fodder)
  - Which targets are bottlenecked (need more fodder of grade N first)
  - Optimal sacrifice picks (lowest-level + lowest-rarity fodder first)
  - Cumulative food consumption preview

Read-only. No mod calls except /all-heroes.

Usage:
    python3 tools/rank_up_plan.py                  # full plan
    python3 tools/rank_up_plan.py --execute        # actually run /rank-up calls
                                                    # (dest: REQUIRES user consent)
    python3 tools/rank_up_plan.py --target HEROID  # plan one hero only
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"

# Real Raid level caps: grade * 10 (verified empirically from roster)
RARITY_NAME = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary"}


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=20) as r:
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
        return {"exclude_all_legendaries": True, "exclude_all_epics": False,
                "protected_names": [], "fusion_targets": []}
    return json.loads(p.read_text())


def is_food_eligible(h: dict, reserved: set[int], protected: dict) -> bool:
    if h.get("id") in reserved or h.get("locked") or h.get("in_storage"):
        return False
    # Faction Guardian assignment hard-blocks rank-up (server returns
    # AcademyGuardians_HeroAlreadyInSlot). Always exclude.
    if h.get("is_faction_guardian"):
        return False
    # Empowered heroes — opt-in exclusion (default true).
    if protected.get("exclude_empowered", True) and (h.get("empower") or 0) > 0:
        return False
    # Fusion ingredients — hard exclude (mod-derived from FuseSettings).
    if h.get("is_fusion_ingredient"):
        return False
    # in_bathhouse = "Reserve Vault" in the game UI. Opt-in exclusion.
    if protected.get("exclude_reserve_vault", False) and h.get("in_bathhouse"):
        return False
    rarity = h.get("rarity", 0)
    if protected.get("exclude_all_legendaries", True) and rarity == 5:
        return False
    if protected.get("exclude_all_epics", False) and rarity == 4:
        return False
    name = h.get("name", "")
    if name in protected.get("protected_names", []):
        return False
    if name in protected.get("fusion_targets", []):
        return False
    return True


MAX_GRADE = 6  # Raid star cap; sacred-ascend is a separate flow


def is_maxed(h: dict) -> bool:
    """At level cap AND below G6 (G6 has no further rank-up)."""
    grade = h.get("grade", 0)
    if grade >= MAX_GRADE:
        return False
    return h.get("level", 0) >= grade * 10


def pick_optimal_food(food_pool: list[dict], target_grade: int,
                      n_needed: int) -> list[dict]:
    """Pick `n_needed` food champs of the same grade as target.
    Prefer lowest-rarity (commons first), then lowest-level (so we don't
    waste XP-invested champs)."""
    same_grade = [h for h in food_pool if h.get("grade") == target_grade]
    same_grade.sort(key=lambda h: (
        h.get("rarity", 99),     # lowest rarity first (Common < Uncommon < Rare < Epic < Legendary)
        h.get("level", 0),        # lowest level first (waste least XP)
        h.get("name", ""),        # stable order
    ))
    return same_grade[:n_needed]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=None,
                    help="Plan rank-up for one specific hero id only")
    ap.add_argument("--execute", action="store_true",
                    help="Actually call /rank-up (DESTRUCTIVE — needs explicit consent)")
    ap.add_argument("--max", type=int, default=0,
                    help="Cap to N rank-ups even in --execute mode (0 = all)")
    ap.add_argument("--no-move", action="store_true",
                    help="Skip auto-moving planned heroes to Champion list before execution")
    args = ap.parse_args()

    heroes = _get("/all-heroes").get("heroes", [])
    reserved = load_reserved()
    protected = load_protected()
    by_id = {h.get("id"): h for h in heroes}

    # Build the pool of ALL food-eligible heroes (excludes legendaries/fusions/protected)
    food_pool = [h for h in heroes if is_food_eligible(h, reserved, protected)]
    # Targets = ALL maxed heroes worth ranking up — INCLUDING legendaries/protected
    # (we want to rank them UP, just not USE them as food). But exclude
    # Faction Guardians: the rank-up cmd fails for them too until they're
    # removed from their slot.
    target_pool = [h for h in heroes
                   if h.get("id") not in reserved
                   and not h.get("locked")
                   and not h.get("in_storage")
                   and not h.get("is_faction_guardian")
                   and not (protected.get("exclude_empowered", True)
                            and (h.get("empower") or 0) > 0)]
    if args.target:
        if args.target not in by_id:
            print(f"ERROR: hero id {args.target} not in roster")
            return 1
        targets = [by_id[args.target]]
    else:
        targets = [h for h in target_pool if is_maxed(h)]

    if not targets:
        print("No maxed-level rank-up targets found.")
        return 0

    # Sort targets: highest-grade first (rarer fodder, prioritize)
    targets.sort(key=lambda h: (-h.get("rarity", 0), -h.get("grade", 0), -h.get("level", 0)))

    print(f"=== Rank-Up Plan ({len(targets)} target{'s' if len(targets)!=1 else ''}) ===\n")
    print(f"Reserved (won't sacrifice):  {len(reserved)} heroes")
    excl = []
    if protected.get("exclude_all_legendaries"): excl.append("legendaries")
    if protected.get("exclude_all_epics"): excl.append("epics")
    if protected.get("fusion_targets"): excl.append(f"fusions={protected['fusion_targets']}")
    if protected.get("protected_names"): excl.append(f"protected={protected['protected_names']}")
    if excl:
        print(f"Protected (won't sacrifice): {', '.join(excl)}")
    print(f"Food pool: {len(food_pool)} eligible heroes\n")

    # Run-tracking: as we plan/execute, food gets consumed
    consumed: set[int] = set()  # hero ids removed from pool

    plans = []
    bottlenecked = []
    for t in targets:
        # Skip targets already consumed as food for an earlier (higher-priority) target
        if t.get("id") in consumed:
            continue
        target_grade = t.get("grade", 0)
        n_needed = target_grade  # rank-up cost: N copies of grade N
        # Don't use the target itself or already-planned-for-rank-up heroes as fodder
        avail = [h for h in food_pool
                 if h.get("id") != t.get("id")
                 and h.get("id") not in consumed
                 and h.get("id") not in {p["target"]["id"] for p in plans}]
        food = pick_optimal_food(avail, target_grade, n_needed)
        if len(food) < n_needed:
            bottlenecked.append({
                "target": t,
                "needed": n_needed,
                "available": len(food),
                "missing": n_needed - len(food),
            })
            continue
        plans.append({"target": t, "food": food})
        for f in food:
            consumed.add(f.get("id"))

    print(f"Plannable rank-ups:  {len(plans)}")
    print(f"Bottlenecked:        {len(bottlenecked)}\n")

    for i, p in enumerate(plans, 1):
        t = p["target"]
        food = p["food"]
        print(f"[{i:>2}] Rank up {t.get('name')} (id {t.get('id')}, "
              f"R{t.get('rarity')}/G{t.get('grade')}/L{t.get('level')})")
        for f in food:
            mark = ""
            if f.get("name") == t.get("name"):
                mark = "  <-- SAME NAME (also useful as skill-up after rank-up)"
            print(f"     food: id={f.get('id'):<6} R{f.get('rarity')}/G{f.get('grade')}/L{f.get('level'):<3} {f.get('name','?')}{mark}")

    if bottlenecked:
        print(f"\nBottlenecked targets ({len(bottlenecked)}):")
        for b in bottlenecked:
            t = b["target"]
            print(f"  {t.get('name')} (id {t.get('id')}, G{t.get('grade')}): "
                  f"need {b['needed']} grade-{t.get('grade')} food, "
                  f"have {b['available']} (short {b['missing']})")

    if args.execute and plans:
        executed = 0
        max_to_run = args.max if args.max > 0 else len(plans)

        # Step 1: gather every hero involved (targets + their food) and move
        # them into the Champion list. The MultiRankUpHeroesCmd accepts heroes
        # from any vault, but the user wants them visible/manageable in the
        # main roster — Plarium's `Bathhouse` field = the "Reserve Vault" UI tab.
        if not args.no_move:
            move_ids: list[int] = []
            for p in plans[:max_to_run]:
                t_loc = (p["target"].get("in_storage")
                         or p["target"].get("in_bathhouse"))
                if t_loc:
                    move_ids.append(p["target"]["id"])
                for f in p["food"]:
                    if f.get("in_storage") or f.get("in_bathhouse"):
                        move_ids.append(f["id"])
            if move_ids:
                ids_csv = ",".join(str(i) for i in move_ids)
                print(f"\n=== MOVING {len(move_ids)} heroes to Champion list (so plan is visible) ===")
                try:
                    r = _get(f"/move-heroes?dest=inventory&ids={ids_csv}")
                    if r.get("ok"):
                        print(f"  + moved {r.get('count', '?')} heroes to Champion list")
                    else:
                        print(f"  ! move failed: {r.get('error')}")
                except Exception as ex:
                    print(f"  ERR move: {ex}")

        print(f"\n=== EXECUTING {min(len(plans), max_to_run)} rank-ups ===")
        for p in plans[:max_to_run]:
            t = p["target"]
            food_csv = ",".join(str(f["id"]) for f in p["food"])
            try:
                r = _get(f"/rank-up?hero_id={t['id']}&food={food_csv}")
            except Exception as ex:
                print(f"  ERR rank-up {t.get('name')}: {ex}")
                continue
            if r.get("ok"):
                print(f"  + ranked up {t.get('name')} (sacrificed {len(p['food'])} food)")
                executed += 1
            else:
                print(f"  ! failed for {t.get('name')}: {r.get('error')}")
        print(f"\nExecuted {executed}/{min(len(plans), max_to_run)} rank-ups")
    elif plans:
        print(f"\n(plan only — pass --execute to actually rank up)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
