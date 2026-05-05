#!/usr/bin/env python3
"""Recursive rank-up chain planner — pick a target, get the full resource cost.

NOTE: this is RANK-UP (1*->6* via same-grade fodder), not "Ascension"
(Sacred Ascend / post-6* in Raid is a separate mechanic).

User selects a target hero (or several) to take to a higher grade. Tool walks
the rank-up cost down through every grade, recursing when there's not enough
fodder at a grade and computing how many heroes at the grade BELOW need to
be promoted.

  Rank-up cost: G_a -> G_{a+1} consumes `a` copies of grade-a as fodder.
  Producing 1 G_a hero from G_{a-1} = `a` heroes at G_{a-1}
                                       (1 promoter + (a-1) fodder).
  Shortfall at grade `g` -> additional demand at grade `g-1` = short * g.

Examples:
  Goal: 6-star Weregren (currently G5)
    Step 1: rank-up G5->G6 needs 5 G5 fodder
    Step 2: short 1 G5 -> need 1 G4->G5 promotion = 5 G4 heroes
    Step 3: 25 G4 available -> feasible

CLI:
    python3 tools/rank_up_chain.py --target HERO_ID
    python3 tools/rank_up_chain.py --target-name Weregren
    python3 tools/rank_up_chain.py --targets 19560,19150 --to-grade 6
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"

MAX_GRADE = 6  # Raid star cap; sacred-ascend is a separate mechanic


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
    # Faction Guardian assignment hard-blocks rank-up.
    if h.get("is_faction_guardian"):
        return False
    # Empowered heroes — opt-in exclusion (default true).
    if protected.get("exclude_empowered", True) and (h.get("empower") or 0) > 0:
        return False
    # Fusion ingredients — hard exclude.
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
    return (name not in protected.get("protected_names", [])
            and name not in protected.get("fusion_targets", []))


def plan_one_target(heroes: list[dict], target: dict, to_grade: int,
                    reserved: set[int], protected: dict,
                    pre_consumed: set[int] | None = None) -> dict:
    """Recursive ascension cost for a single target.

    Returns:
      {
        target: {id, name, current_grade, current_level, to_grade},
        chain: [
          {grade, demand, available, short, recurses_to_grade_below: int},
          ...
        ],
        feasible: bool,
        stuck_grade: int | None,  # the grade we ran out at
        consumed_ids: set[int],    # ids ear-marked (NOT removed yet)
      }
    """
    pre_consumed = set(pre_consumed or [])
    target_id = target.get("id")
    cur_grade = target.get("grade", 0)
    cur_level = target.get("level", 0)
    if to_grade > MAX_GRADE:
        return {"target": _summary(target) | {"to_grade": to_grade},
                "error": f"to_grade {to_grade} exceeds max {MAX_GRADE}",
                "feasible": False}
    if cur_grade >= to_grade:
        return {"target": _summary(target) | {"to_grade": to_grade},
                "already_at_grade": True, "feasible": True,
                "chain": [], "consumed_ids": set()}

    # Eligible pool excludes the target, anything pre-consumed by other
    # planned ascensions in this session, and the protection layer.
    excluded = pre_consumed | {target_id}
    pool = [h for h in heroes
            if h.get("id") not in excluded
            and is_food_eligible(h, reserved, protected)]
    eligible_by_grade = Counter(h.get("grade") for h in pool)

    # Demand walk:
    #   1. Add target's own rank-up costs (g fodder at G_g for each step)
    #   2. Walk grades top-down; shortfall at grade g cascades to grade g-1.
    demand: dict[int, int] = {g: 0 for g in range(1, MAX_GRADE + 1)}
    for g in range(cur_grade, to_grade):
        demand[g] += g  # rank-up from G_g to G_{g+1} consumes g G_g fodder

    chain = []
    feasible = True
    stuck_grade = None
    for g in range(to_grade - 1, 0, -1):
        need = demand[g]
        if need == 0:
            continue
        avail = eligible_by_grade.get(g, 0)
        short = max(0, need - avail)
        chain.append({
            "grade": g, "demand": need,
            "available": avail, "short": short,
            "covered_by_existing": min(need, avail),
            "covered_by_promotion": short,
        })
        if short > 0:
            if g <= 1:
                feasible = False
                stuck_grade = 1
                break
            # short G_g heroes still needed -> promote that many G_{g-1} -> G_g
            # Each promotion costs `g` G_{g-1} heroes (1 promoter + (g-1) fodder)
            demand[g - 1] += short * g

    # Earmark eligible heroes as "consumed" so multi-target planners don't
    # double-count them. We pick the LOWEST-rarity, lowest-level first to
    # match what rank_up_plan would do.
    consumed_ids: set[int] = set()
    if feasible:
        for c in chain:
            g = c["grade"]
            n_to_take = c["covered_by_existing"]
            same = sorted(
                [h for h in pool if h.get("grade") == g and h["id"] not in consumed_ids],
                key=lambda h: (h.get("rarity", 99), h.get("level", 0), h.get("name", "")),
            )
            for h in same[:n_to_take]:
                consumed_ids.add(h["id"])

    return {
        "target": _summary(target) | {"to_grade": to_grade},
        "chain": chain,
        "feasible": feasible,
        "stuck_grade": stuck_grade,
        "consumed_ids": consumed_ids,
        "level_ready": cur_level >= cur_grade * 10,
    }


def _summary(h: dict) -> dict:
    return {
        "id": h.get("id"), "name": h.get("name"),
        "rarity": h.get("rarity"), "grade": h.get("grade"),
        "level": h.get("level"),
    }


def materialize_call_sequence(heroes: list[dict], target: dict, to_grade: int,
                              reserved: set[int], protected: dict,
                              pre_consumed: set[int] | None = None
                              ) -> list[dict]:
    """Turn a feasibility plan into the ordered sequence of `/rank-up` calls.
    Bottom-up: grade-3 promotions first (so they exist as G4 fodder for the
    next layer), then G4 promotions, ..., then the target's own rank-up.

    Each call: {"hero_id": int, "hero_name": str, "from_grade", "to_grade",
                "food_ids": [int]}.
    Returns [] if infeasible. Caller should check feasibility separately."""
    pre_consumed = set(pre_consumed or [])
    target_id = target.get("id")
    cur_grade = target.get("grade", 0)
    if cur_grade >= to_grade or to_grade > MAX_GRADE:
        return []

    # Walk plan_one_target to get the demand at each grade, then pick
    # specific heroes bottom-up.
    pool = [h for h in heroes
            if h.get("id") not in (pre_consumed | {target_id})
            and is_food_eligible(h, reserved, protected)]
    by_grade: dict[int, list[dict]] = {g: [] for g in range(1, MAX_GRADE + 1)}
    for h in pool:
        by_grade[h.get("grade", 0)].append(h)
    for g in by_grade:
        by_grade[g].sort(key=lambda h: (h.get("rarity", 99),
                                         h.get("level", 0),
                                         h.get("name", "")))

    # demand[g] = total G_g heroes consumed in this chain (fodder + promoters
    # produced at G_{g-1}+1 for the layer above).
    plan = plan_one_target(heroes, target, to_grade, reserved, protected,
                           pre_consumed=pre_consumed)
    if not plan.get("feasible"):
        return []

    # Rebuild the demand walk so we know how many promotions per grade.
    # promotions[g] = how many G_g heroes we need to produce by promoting from G_{g-1}.
    # promotions[g] starts at 0 for the target's terminal grade
    # (the target IS its own promoter for the topmost step), and equals
    # the shortfall recorded in the chain for lower grades.
    promotions: dict[int, int] = {}
    for c in plan["chain"]:
        promotions[c["grade"]] = c["short"]

    sequence: list[dict] = []
    # We model a "promoted_pool" of heroes synthesized at each grade by lower-
    # grade promotions; they're available for higher-grade promotion or as
    # fodder/feedstock for the next layer.
    promoted_pool: dict[int, list[dict]] = {g: [] for g in range(1, MAX_GRADE + 1)}

    # Process bottom-up: G2 promotions feed G3 demand, G3 promotions feed G4, etc.
    for g in range(2, to_grade):
        n_promote = promotions.get(g, 0)
        if n_promote == 0:
            continue
        # Each promotion: pick 1 promoter at G_{g-1} + (g-1) fodder at G_{g-1}.
        # All G_{g-1} heroes come from existing `by_grade[g-1]` plus
        # `promoted_pool[g-1]` (newly created in the previous layer).
        donors = by_grade[g - 1] + promoted_pool[g - 1]
        # Promoters: prefer LEVELED heroes (closer to L_cap = (g-1)*10) so the
        # rank-up succeeds in-game without further leveling. If none leveled,
        # we still pick — caller will see the level warning.
        donors_sorted = sorted(donors, key=lambda h: (
            -((h.get("level", 0) >= (g - 1) * 10)),  # leveled first
            h.get("rarity", 99),                       # lowest rarity first
            -h.get("level", 0),                        # among non-leveled, highest level
            h.get("name", ""),
        ))
        # Fodder: lowest rarity, lowest level (least invested) first.
        fodder_sorted = sorted(donors, key=lambda h: (
            h.get("rarity", 99), h.get("level", 0), h.get("name", "")))
        used: set[int] = set()
        for _ in range(n_promote):
            promoter = next((h for h in donors_sorted if h["id"] not in used), None)
            if promoter is None:
                return []  # ran out — should not happen if feasible
            used.add(promoter["id"])
            food = []
            for h in fodder_sorted:
                if h["id"] in used:
                    continue
                food.append(h)
                used.add(h["id"])
                if len(food) >= g - 1:
                    break
            if len(food) < g - 1:
                return []
            sequence.append({
                "hero_id": promoter["id"], "hero_name": promoter.get("name"),
                "from_grade": g - 1, "to_grade": g,
                "food_ids": [f["id"] for f in food],
                "food_names": [f.get("name") for f in food],
            })
            # The promoter becomes a G_g hero post-rank-up, available to
            # the next layer.
            promoted_pool[g].append({**promoter, "grade": g, "level": 1})
        # Drop used IDs from `by_grade[g-1]` and `promoted_pool[g-1]` so
        # later passes don't reuse them.
        by_grade[g - 1] = [h for h in by_grade[g - 1] if h["id"] not in used]
        promoted_pool[g - 1] = [h for h in promoted_pool[g - 1] if h["id"] not in used]

    # Finally, the target's own rank-up steps (cur_grade -> cur_grade+1 -> ... -> to_grade).
    for g in range(cur_grade, to_grade):
        donors = by_grade[g] + promoted_pool[g]
        fodder_sorted = sorted(donors, key=lambda h: (
            h.get("rarity", 99), h.get("level", 0), h.get("name", "")))
        food = fodder_sorted[:g]
        if len(food) < g:
            return []
        sequence.append({
            "hero_id": target_id, "hero_name": target.get("name"),
            "from_grade": g, "to_grade": g + 1,
            "food_ids": [f["id"] for f in food],
            "food_names": [f.get("name") for f in food],
        })
        used = {f["id"] for f in food}
        by_grade[g] = [h for h in by_grade[g] if h["id"] not in used]
        promoted_pool[g] = [h for h in promoted_pool[g] if h["id"] not in used]

    return sequence


def plan_session(heroes: list[dict], targets: list[dict], to_grade: int,
                 reserved: set[int], protected: dict) -> dict:
    """Plan a SESSION of ascensions: multiple targets, no double-counting fodder.

    Targets are processed in input order. Each ascension's consumed pool is
    fed into the next so a hero used as fodder for target #1 isn't reused
    for target #2."""
    consumed: set[int] = set()
    plans = []
    for t in targets:
        p = plan_one_target(heroes, t, to_grade, reserved, protected,
                            pre_consumed=consumed)
        if p.get("feasible") and not p.get("already_at_grade"):
            seq = materialize_call_sequence(heroes, t, to_grade, reserved,
                                            protected, pre_consumed=consumed)
            p["call_sequence"] = seq
            # Earmark every hero touched by the sequence:
            #   - All food IDs are consumed (sacrificed)
            #   - Promoters become higher-grade and are no longer eligible
            #     at any lower grade — including the target herself, who
            #     ends up at to_grade and shouldn't appear as fodder for
            #     subsequent session targets.
            for call in seq:
                consumed.add(call["hero_id"])  # promoter (target or stepping-stone)
                consumed.update(call["food_ids"])
        else:
            p["call_sequence"] = []
            consumed |= p.get("consumed_ids", set())
        plans.append(p)
    return {
        "to_grade": to_grade,
        "plans": plans,
        "total_consumed": len(consumed),
        "feasible_count": sum(1 for p in plans if p.get("feasible")),
        "infeasible_count": sum(1 for p in plans if not p.get("feasible")
                                and not p.get("already_at_grade")),
        "total_calls": sum(len(p.get("call_sequence", [])) for p in plans),
    }


def _format_chain(plan: dict) -> str:
    out = []
    t = plan["target"]
    out.append(f"\n=== {t['name']} (id {t['id']}, "
               f"R{t['rarity']}/G{t['grade']}/L{t['level']}) -> G{t['to_grade']} ===")
    if plan.get("already_at_grade"):
        out.append(f"  Already at G{t['to_grade']} or higher.")
        return "\n".join(out)
    if plan.get("error"):
        out.append(f"  ERROR: {plan['error']}")
        return "\n".join(out)
    if not plan.get("level_ready"):
        out.append(f"  WARN: target at L{t['level']} but G{t['grade']} cap is L{t['grade']*10}; "
                   f"level her up before rank-up.")
    out.append(f"  Feasibility: {'OK' if plan['feasible'] else 'INFEASIBLE'}")
    if not plan["feasible"]:
        out.append(f"  Stuck at G{plan['stuck_grade']} — not enough fodder at the bottom.")
    for c in plan["chain"]:
        emoji = "OK " if c["short"] == 0 else "!! "
        promote_note = ""
        if c["short"] > 0:
            promote_note = (f" -> promote {c['short']} from G{c['grade']-1} "
                            f"({c['short']} * {c['grade']} = "
                            f"{c['short']*c['grade']} G{c['grade']-1} heroes)")
        out.append(f"  {emoji}G{c['grade']}: need {c['demand']:>3}, have "
                   f"{c['available']:>3}, short {c['short']:>3}{promote_note}")
    seq = plan.get("call_sequence") or []
    if seq:
        out.append(f"  Call sequence ({len(seq)} /rank-up calls, bottom-up):")
        for i, call in enumerate(seq, 1):
            food_str = ", ".join(f"{n}({i_})" for n, i_ in
                                 zip(call["food_names"], call["food_ids"]))
            out.append(f"    {i:>2}. {call['hero_name']} (id {call['hero_id']}) "
                       f"G{call['from_grade']}->G{call['to_grade']}  "
                       f"<- [{food_str}]")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=None,
                    help="Hero instance id to ascend")
    ap.add_argument("--target-name", default=None,
                    help="Hero NAME (first match wins). Use --target for explicit id.")
    ap.add_argument("--targets", default=None,
                    help="CSV of hero ids: 19560,19150,...")
    ap.add_argument("--to-grade", type=int, default=6,
                    help="Goal grade (default 6)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--execute", action="store_true",
                    help="Walk the call_sequence on the live mod (DESTRUCTIVE)")
    ap.add_argument("--no-move", action="store_true",
                    help="Skip auto-moving planned heroes to Champion list before execution")
    args = ap.parse_args()

    if args.to_grade > MAX_GRADE:
        print(f"ERROR: --to-grade {args.to_grade} exceeds max {MAX_GRADE}",
              file=sys.stderr)
        return 1

    heroes = _get("/all-heroes").get("heroes", [])
    reserved = load_reserved()
    protected = load_protected()
    by_id = {h.get("id"): h for h in heroes}
    by_name = {}
    for h in heroes:
        by_name.setdefault(h.get("name", ""), h)

    targets = []
    if args.target:
        if args.target not in by_id:
            print(f"ERROR: hero id {args.target} not in roster", file=sys.stderr)
            return 1
        targets = [by_id[args.target]]
    elif args.target_name:
        if args.target_name not in by_name:
            print(f"ERROR: no hero named '{args.target_name}'", file=sys.stderr)
            return 1
        targets = [by_name[args.target_name]]
    elif args.targets:
        ids = [int(x) for x in args.targets.split(",") if x.strip()]
        targets = [by_id[i] for i in ids if i in by_id]
        missing = [i for i in ids if i not in by_id]
        if missing:
            print(f"WARN: ids not in roster: {missing}", file=sys.stderr)
    else:
        ap.error("Specify --target, --target-name, or --targets CSV")

    result = plan_session(heroes, targets, args.to_grade, reserved, protected)

    if args.format == "json":
        # Convert sets to lists for JSON serialization
        for p in result["plans"]:
            if "consumed_ids" in p:
                p["consumed_ids"] = sorted(p["consumed_ids"])
        print(json.dumps(result, indent=2))
        return 0

    print(f"=== Rank-up chain (session) ===")
    print(f"Targets: {len(result['plans'])}, to G{result['to_grade']}, "
          f"feasible: {result['feasible_count']}/{len(result['plans'])}")
    print(f"Reserved: {len(reserved)} heroes, "
          f"Protected: legendaries={protected.get('exclude_all_legendaries')}, "
          f"epics={protected.get('exclude_all_epics')}, "
          f"named={protected.get('protected_names', [])}")
    for p in result["plans"]:
        print(_format_chain(p))
    if result["plans"] and any(p.get("feasible") for p in result["plans"]):
        print(f"\nTotal heroes earmarked across session: {result['total_consumed']}")

    if args.execute:
        feasible_plans = [p for p in result["plans"]
                          if p.get("feasible") and not p.get("already_at_grade")]
        if not feasible_plans:
            print("\n(no feasible plans to execute)")
            return 0

        # Pre-step: move every hero referenced in any call_sequence to Champion list.
        if not args.no_move:
            move_ids: list[int] = []
            seen: set[int] = set()
            by_id_local = {h.get("id"): h for h in heroes}
            for p in feasible_plans:
                for call in p.get("call_sequence", []):
                    for hid in [call["hero_id"]] + list(call["food_ids"]):
                        if hid in seen:
                            continue
                        seen.add(hid)
                        h = by_id_local.get(hid, {})
                        if h.get("in_storage") or h.get("in_bathhouse"):
                            move_ids.append(hid)
            if move_ids:
                print(f"\n=== MOVING {len(move_ids)} heroes to Champion list ===")
                ids_csv = ",".join(str(i) for i in move_ids)
                try:
                    r = _get(f"/move-heroes?dest=inventory&ids={ids_csv}")
                    if r.get("ok"):
                        print(f"  + moved {r.get('count', '?')} heroes")
                    else:
                        print(f"  ! move failed: {r.get('error')}")
                        return 1
                except Exception as ex:
                    print(f"  ERR move: {ex}")
                    return 1

        # Walk every call in order, across every feasible plan.
        print("\n=== EXECUTING /rank-up calls (DESTRUCTIVE) ===")
        ok_count = 0
        fail_count = 0
        for p in feasible_plans:
            for call in p.get("call_sequence", []):
                food_csv = ",".join(str(x) for x in call["food_ids"])
                try:
                    r = _get(f"/rank-up?hero_id={call['hero_id']}&food={food_csv}")
                except Exception as ex:
                    print(f"  ERR {call['hero_name']}: {ex}")
                    fail_count += 1
                    continue
                if r.get("ok"):
                    print(f"  + {call['hero_name']} G{call['from_grade']}->G{call['to_grade']}")
                    ok_count += 1
                else:
                    print(f"  ! {call['hero_name']}: {r.get('error')}")
                    fail_count += 1
        print(f"\nExecuted {ok_count} ok, {fail_count} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
