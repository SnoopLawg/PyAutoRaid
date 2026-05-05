#!/usr/bin/env python3
"""Unified champion manager — coordinates skill-ups + rank-ups + leveling.

Runs the pipeline in the right order so the same dup never gets double-counted:

  1. **Skill-up phase**: for each named primary, sacrifice same-name dups until
     skills are maxed (or dups run out). Highest-priority champs first.
  2. **Rank-up phase**: with remaining dups added back to the food pool, plan
     rank-ups for level-capped heroes (highest rarity first).
  3. **Leveling phase** (planned, not yet wired): identify which heroes still
     need leveling to reach next rank.

All three pipelines share the same protected/reserved gates from
`data/protected_heroes.json` and `data/reserved_heroes.json`.

Read-only by default. --execute runs `/skill-up` then `/rank-up` against
the live mod.

Usage:
    python3 tools/champ_manager.py                 # full plan
    python3 tools/champ_manager.py --skill-only    # only skill-up phase
    python3 tools/champ_manager.py --rank-only     # only rank-up phase
    python3 tools/champ_manager.py --execute       # actually run mod calls
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"


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


def load_skills_db() -> dict:
    p = PROJECT_ROOT / "skills_db.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def is_food_eligible(h: dict, reserved: set[int], protected: dict) -> bool:
    if h.get("id") in reserved or h.get("locked") or h.get("in_storage"):
        return False
    # Faction Guardian assignment makes the hero un-sacrificeable — the
    # rank-up cmd hard-fails with AcademyGuardians_HeroAlreadyInSlot. Hard
    # exclusion regardless of any opt-in flag.
    if h.get("is_faction_guardian"):
        return False
    # Empowered heroes (empower > 0) represent invested duplicates for stat
    # boosts; opt-in exclusion via protected_heroes.json. Defaults to true.
    if protected.get("exclude_empowered", True) and (h.get("empower") or 0) > 0:
        return False
    # Fusion ingredients — heroes whose TypeId appears in any active or
    # upcoming fusion recipe (read from the live mod). HARD exclude.
    if h.get("is_fusion_ingredient"):
        return False
    # in_bathhouse is Plarium's internal name for what the game UI shows as
    # "Reserve Vault". Opt-in exclusion via protected_heroes.json.
    if protected.get("exclude_reserve_vault", False) and h.get("in_bathhouse"):
        return False
    rarity = h.get("rarity", 0)
    if protected.get("exclude_all_legendaries", True) and rarity == 5:
        return False
    if protected.get("exclude_all_epics", False) and rarity == 4:
        return False
    name = h.get("name", "")
    return (name not in protected.get("protected_names", [])
            and name not in protected.get("fusion_targets", []))


MAX_GRADE = 6  # Raid star cap; sacred-ascend is a separate flow


def is_maxed(h: dict) -> bool:
    """At level cap AND below G6 (G6 has no further rank-up)."""
    grade = h.get("grade", 0)
    if grade >= MAX_GRADE:
        return False
    return h.get("level", 0) >= grade * 10


def hero_skill_levels(name: str, hero_id: int, skills_db: dict,
                      hero_skills_live: list[dict]) -> list[dict]:
    rows = [r for r in skills_db.get(name, []) if r.get("hero_id") == hero_id]
    by_type = {r.get("skill_type_id"): r for r in rows}
    out = []
    for s in hero_skills_live:
        tid = s.get("type_id")
        cur = s.get("level", 1)
        row = by_type.get(tid, {})
        max_level = 1 + len(row.get("level_bonuses", []))
        out.append({
            "name": row.get("name", "?"),
            "current": cur, "max": max_level,
            "remaining": max(0, max_level - cur),
        })
    return out


def plan_skill_ups(heroes: list[dict], reserved: set[int], protected: dict,
                   skills_db: dict, max_feeds_per: int = 0) -> tuple[list[dict], set[int]]:
    """Returns (plans, consumed_ids). Each plan: {primary, feeds, total_remaining}."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for h in heroes:
        if h.get("locked"):
            continue
        groups[h.get("name", "?")].append(h)
    plans = []
    consumed: set[int] = set()
    for name, hs in groups.items():
        if len(hs) < 2:
            continue
        hs_sorted = sorted(hs, key=lambda h: (
            -h.get("grade", 0), -h.get("level", 0),
            -h.get("rarity", 0), h.get("id", 0)))
        primary = hs_sorted[0]
        dups = [d for d in hs_sorted[1:] if is_food_eligible(d, reserved, protected)]
        if not dups:
            continue
        skill_levels = hero_skill_levels(name, primary.get("id"), skills_db,
                                          primary.get("skills", []))
        total_remaining = sum(s["remaining"] for s in skill_levels)
        if total_remaining <= 0:
            continue
        feeds = dups[:max_feeds_per] if max_feeds_per > 0 else dups
        # Cap feeds at total_remaining (each dup gives ~1 level on average)
        feeds = feeds[:max(total_remaining, 1)]
        plans.append({
            "primary": primary, "feeds": feeds,
            "skill_levels": skill_levels,
            "total_remaining": total_remaining,
        })
        for f in feeds:
            consumed.add(f["id"])
    plans.sort(key=lambda p: (
        -p["total_remaining"], -p["primary"].get("rarity", 0),
        -p["primary"].get("grade", 0)))
    return plans, consumed


def pick_optimal_food(food_pool: list[dict], target_grade: int,
                      n_needed: int) -> list[dict]:
    same = [h for h in food_pool if h.get("grade") == target_grade]
    same.sort(key=lambda h: (h.get("rarity", 99), h.get("level", 0), h.get("name", "")))
    return same[:n_needed]


def plan_rank_ups(heroes: list[dict], reserved: set[int], protected: dict,
                  pre_consumed: set[int]) -> tuple[list[dict], list[dict]]:
    food_pool = [h for h in heroes
                 if is_food_eligible(h, reserved, protected)
                 and h.get("id") not in pre_consumed]
    target_pool = [h for h in heroes
                   if h.get("id") not in reserved
                   and not h.get("locked") and not h.get("in_storage")
                   and not h.get("is_faction_guardian")
                   and not (protected.get("exclude_empowered", True)
                            and (h.get("empower") or 0) > 0)
                   and h.get("id") not in pre_consumed]
    targets = [h for h in target_pool if is_maxed(h)]
    targets.sort(key=lambda h: (-h.get("rarity", 0), -h.get("grade", 0), -h.get("level", 0)))
    consumed: set[int] = set()
    plans = []
    bottlenecked = []
    for t in targets:
        if t.get("id") in consumed:
            continue
        n_needed = t.get("grade", 0)
        avail = [h for h in food_pool
                 if h.get("id") != t.get("id")
                 and h.get("id") not in consumed
                 and h.get("id") not in {p["target"]["id"] for p in plans}]
        food = pick_optimal_food(avail, t.get("grade", 0), n_needed)
        if len(food) < n_needed:
            bottlenecked.append({"target": t, "needed": n_needed,
                                 "available": len(food), "missing": n_needed - len(food)})
            continue
        plans.append({"target": t, "food": food})
        for f in food:
            consumed.add(f["id"])
    return plans, bottlenecked


def _print_skill_plans(plans: list[dict], limit: int = 0) -> None:
    print(f"\n=== Skill-Up Phase: {len(plans)} primaries ===")
    show = plans if limit == 0 else plans[:limit]
    for i, p in enumerate(show, 1):
        pri = p["primary"]
        print(f"[{i:>2}] {pri['name']} (id {pri['id']}, "
              f"R{pri['rarity']}/G{pri['grade']}/L{pri['level']})  "
              f"+{p['total_remaining']} skill levels possible, "
              f"{len(p['feeds'])} feed(s)")
        for s in p["skill_levels"]:
            if s["remaining"] > 0:
                print(f"     {s['name']:<28} {s['current']}/{s['max']}")
    if limit and len(plans) > limit:
        print(f"     ... and {len(plans) - limit} more (use --skill-only to see all)")


def _print_rank_plans(plans: list[dict], bottlenecked: list[dict]) -> None:
    print(f"\n=== Rank-Up Phase: {len(plans)} plannable, {len(bottlenecked)} bottlenecked ===")
    for i, p in enumerate(plans, 1):
        t = p["target"]
        print(f"[{i:>2}] {t['name']} (id {t['id']}, "
              f"R{t['rarity']}/G{t['grade']}/L{t['level']})  "
              f"<- {len(p['food'])} fodder")
        for f in p["food"]:
            print(f"     food: id={f['id']:<6} R{f['rarity']}/G{f['grade']}/L{f['level']:<3} {f['name']}")
    if bottlenecked:
        print(f"\nBottlenecked (need more grade-N fodder):")
        for b in bottlenecked:
            t = b["target"]
            print(f"  {t['name']} (G{t['grade']}): need {b['needed']}, "
                  f"have {b['available']} (short {b['missing']})")


def simulate_rank_up(heroes: list[dict], target: dict, food_ids: set[int]) -> list[dict]:
    """Return a NEW heroes list with `food_ids` removed and `target` promoted
    by 1 grade (level reset to 1). The promoted hero might now be food-eligible
    at the next grade — multi-pass planner needs that."""
    out = []
    for h in heroes:
        if h.get("id") in food_ids:
            continue
        if h.get("id") == target.get("id"):
            promoted = dict(h)
            promoted["grade"] = h.get("grade", 0) + 1
            promoted["level"] = 1
            out.append(promoted)
        else:
            out.append(h)
    return out


def plan_multi_pass(heroes: list[dict], reserved: set[int], protected: dict,
                    skills_db: dict, max_passes: int = 10) -> dict:
    """Iteratively plan skill-ups + rank-ups, simulating each pass so newly-
    promoted heroes can become food for higher-grade targets in the next pass.
    Returns {passes: [...], total_skill_plans, total_rank_plans, final_bottlenecked}."""
    cur_heroes = list(heroes)
    passes = []
    total_skill = 0
    total_rank = 0
    final_bot: list[dict] = []
    for pass_n in range(1, max_passes + 1):
        skill_plans, skill_consumed = plan_skill_ups(
            cur_heroes, reserved, protected, skills_db)
        rank_plans, bottlenecked = plan_rank_ups(
            cur_heroes, reserved, protected, pre_consumed=skill_consumed)
        passes.append({
            "pass": pass_n,
            "skill_plans": len(skill_plans),
            "skill_consumed": len(skill_consumed),
            "rank_plans": len(rank_plans),
            "rank_targets": [p["target"]["name"] for p in rank_plans],
            "bottlenecked": [b["target"]["name"] for b in bottlenecked],
        })
        total_skill += len(skill_plans)
        total_rank += len(rank_plans)
        final_bot = bottlenecked
        if not rank_plans:
            break
        # Apply rank-ups: remove food + promote target
        consumed_this_pass: set[int] = set(skill_consumed)
        promoted_targets = []
        for p in rank_plans:
            food_ids = {f["id"] for f in p["food"]}
            consumed_this_pass.update(food_ids)
            promoted_targets.append((p["target"], food_ids))
        # Apply all promotions to cur_heroes
        next_heroes = []
        promoted_ids = {t["id"] for t, _ in promoted_targets}
        for h in cur_heroes:
            if h.get("id") in consumed_this_pass:
                continue
            if h.get("id") in promoted_ids:
                bumped = dict(h)
                bumped["grade"] = h.get("grade", 0) + 1
                bumped["level"] = 1
                next_heroes.append(bumped)
            else:
                next_heroes.append(h)
        cur_heroes = next_heroes
    return {
        "passes": passes,
        "total_skill_plans": total_skill,
        "total_rank_plans": total_rank,
        "final_bottlenecked": [
            {"name": b["target"]["name"], "grade": b["target"]["grade"],
             "needed": b["needed"], "available": b["available"]}
            for b in final_bot
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-only", action="store_true", help="Only skill-up phase")
    ap.add_argument("--rank-only", action="store_true", help="Only rank-up phase")
    ap.add_argument("--execute", action="store_true",
                    help="Actually run mod calls (DESTRUCTIVE)")
    ap.add_argument("--max-rank-ups", type=int, default=0,
                    help="Cap rank-up executions (0 = all)")
    ap.add_argument("--max-skill-ups", type=int, default=0,
                    help="Cap skill-up executions (0 = all)")
    ap.add_argument("--show-skill-limit", type=int, default=15,
                    help="Show top-N skill-up plans (0 = all)")
    ap.add_argument("--multi-pass", action="store_true",
                    help="Simulate iterative rank-ups (newly-promoted heroes "
                         "feed bigger targets in the next pass)")
    ap.add_argument("--max-passes", type=int, default=10,
                    help="Cap multi-pass iterations (default 10)")
    ap.add_argument("--no-move", action="store_true",
                    help="Skip auto-moving planned heroes to Champion list before execution")
    args = ap.parse_args()

    heroes = _get("/all-heroes").get("heroes", [])
    reserved = load_reserved()
    protected = load_protected()
    skills_db = load_skills_db()

    print(f"=== Champion Manager ===")
    print(f"Roster: {len(heroes)} heroes  |  Reserved: {len(reserved)}")
    excl = []
    if protected.get("exclude_all_legendaries"): excl.append("legendaries")
    if protected.get("exclude_all_epics"): excl.append("epics")
    if protected.get("fusion_targets"): excl.append(f"fusions={protected['fusion_targets']}")
    if protected.get("protected_names"): excl.append(f"named={protected['protected_names']}")
    if excl: print(f"Protected: {', '.join(excl)}")

    if args.multi_pass:
        result = plan_multi_pass(heroes, reserved, protected, skills_db,
                                 max_passes=args.max_passes)
        print(f"\n=== Multi-pass simulation ({len(result['passes'])} passes) ===")
        for p in result["passes"]:
            tlist = ", ".join(p["rank_targets"][:5])
            if len(p["rank_targets"]) > 5: tlist += f", +{len(p['rank_targets'])-5}"
            print(f"  Pass {p['pass']:>2}: {p['rank_plans']:>2} rank-ups "
                  f"({p['skill_plans']} skill plans, "
                  f"{p['skill_consumed']} dups consumed) "
                  f"-> {tlist}")
        print(f"\nCumulative: {result['total_rank_plans']} rank-ups across "
              f"{len(result['passes'])} passes ({result['total_skill_plans']} skill plans)")
        if result["final_bottlenecked"]:
            print(f"\nBottlenecked after all passes:")
            for b in result["final_bottlenecked"]:
                print(f"  {b['name']} (G{b['grade']}): "
                      f"need {b['needed']}, have {b['available']}")
        else:
            print(f"\nNo bottlenecks after all passes — every maxed hero is reachable.")
        return 0

    skill_plans, skill_consumed = ([], set())
    rank_plans, bottlenecked = ([], [])

    if not args.rank_only:
        skill_plans, skill_consumed = plan_skill_ups(
            heroes, reserved, protected, skills_db)
        _print_skill_plans(skill_plans, limit=args.show_skill_limit)
        print(f"\nSkill-up phase will consume {len(skill_consumed)} dups")

    if not args.skill_only:
        rank_plans, bottlenecked = plan_rank_ups(
            heroes, reserved, protected, pre_consumed=skill_consumed)
        _print_rank_plans(rank_plans, bottlenecked)

    print("\n=== Summary ===")
    print(f"Skill-up plans:  {len(skill_plans)}  (consumes {len(skill_consumed)} dups)")
    print(f"Rank-up plans:   {len(rank_plans)}  (consumes "
          f"{sum(len(p['food']) for p in rank_plans)} fodder)")
    print(f"Bottlenecked:    {len(bottlenecked)}")

    if not args.execute:
        print("\n(plan only -- pass --execute to run /skill-up + /rank-up live)")
        return 0

    # === EXECUTE ===
    print("\n=== EXECUTING (DESTRUCTIVE) ===")

    # Pre-step: move every planned hero (primaries + feeds + targets + food)
    # into the Champion list so the user can see them in their normal vault.
    # `in_storage` = Master Vault, `in_bathhouse` = "Reserve Vault" in the UI.
    if not args.no_move:
        move_ids: list[int] = []
        n_skill_to_run = (args.max_skill_ups if args.max_skill_ups > 0 else len(skill_plans))
        n_rank_to_run = (args.max_rank_ups if args.max_rank_ups > 0 else len(rank_plans))
        if not args.rank_only:
            for p in skill_plans[:n_skill_to_run]:
                pri = p["primary"]
                if pri.get("in_storage") or pri.get("in_bathhouse"):
                    move_ids.append(pri["id"])
                for f in p.get("feeds", []):
                    if f.get("in_storage") or f.get("in_bathhouse"):
                        move_ids.append(f["id"])
        if not args.skill_only:
            for p in rank_plans[:n_rank_to_run]:
                t = p["target"]
                if t.get("in_storage") or t.get("in_bathhouse"):
                    move_ids.append(t["id"])
                for f in p["food"]:
                    if f.get("in_storage") or f.get("in_bathhouse"):
                        move_ids.append(f["id"])
        # Dedup, preserve order
        seen = set()
        move_ids = [i for i in move_ids if not (i in seen or seen.add(i))]
        if move_ids:
            print(f"\n-- Moving {len(move_ids)} heroes to Champion list --")
            ids_csv = ",".join(str(i) for i in move_ids)
            try:
                r = _get(f"/move-heroes?dest=inventory&ids={ids_csv}")
                if r.get("ok"):
                    print(f"  + moved {r.get('count', '?')} heroes")
                else:
                    print(f"  ! move failed: {r.get('error')}")
            except Exception as ex:
                print(f"  ERR move: {ex}")

    if not args.rank_only:
        print(f"\n-- Skill-up phase --")
        n_to_run = args.max_skill_ups if args.max_skill_ups > 0 else len(skill_plans)
        executed = 0
        for p in skill_plans[:n_to_run]:
            pri = p["primary"]
            food_csv = ",".join(str(f["id"]) for f in p["feeds"])
            try:
                r = _get(f"/skill-up?hero_id={pri['id']}&food={food_csv}")
            except Exception as ex:
                print(f"  ERR {pri['name']}: {ex}")
                continue
            if r.get("ok"):
                print(f"  + {pri['name']}: fed {len(p['feeds'])}")
                executed += 1
            else:
                print(f"  ! {pri['name']}: {r.get('error')}")
        print(f"Skill-ups executed: {executed}/{n_to_run}")

    if not args.skill_only:
        print(f"\n-- Rank-up phase --")
        n_to_run = args.max_rank_ups if args.max_rank_ups > 0 else len(rank_plans)
        executed = 0
        for p in rank_plans[:n_to_run]:
            t = p["target"]
            food_csv = ",".join(str(f["id"]) for f in p["food"])
            try:
                r = _get(f"/rank-up?hero_id={t['id']}&food={food_csv}")
            except Exception as ex:
                print(f"  ERR {t['name']}: {ex}")
                continue
            if r.get("ok"):
                print(f"  + {t['name']}: ranked up using {len(p['food'])}")
                executed += 1
            else:
                print(f"  ! {t['name']}: {r.get('error')}")
        print(f"Rank-ups executed: {executed}/{n_to_run}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
