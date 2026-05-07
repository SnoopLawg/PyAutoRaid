#!/usr/bin/env python3
"""One-shot 6-star a hero — plans the rank-up cascade and either
executes it directly (if roster has enough fodder) or starts the
farm_loop in target mode to bootstrap from commons.

Honors all protection rules in data/protected_heroes.json — no
legendaries / epics / fusion targets / locked heroes are touched.

Examples:
    python3 tools/six_star.py Harima
    python3 tools/six_star.py Harima --to-grade 6 --carry 6864 \\
        --stage-name campaign-12-3-nightmare
    python3 tools/six_star.py Harima --plan-only      # show plan, don't run

If feasible from current roster: walks the cascade bottom-up, firing
/rank-up calls to promote G_n heroes through to G_5, then ascends the
target. If NOT feasible: launches farm_loop unattended — every battle
levels food, the cascade auto-runs, and the target ranks up the moment
fodder threshold is reached. You only need to summon more commons via
Mystery Shards as the bottleneck.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"

sys.path.insert(0, str(PROJECT_ROOT / "tools"))
from rank_up_chain import (
    plan_one_target, materialize_call_sequence, load_reserved, load_protected,
    is_food_eligible, _summary, MAX_GRADE,
)


def _get(path: str, timeout: int = 20) -> dict:
    with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def fetch_heroes() -> list[dict]:
    return _get("/all-heroes?offset=0&limit=20000").get("heroes", [])


def find_hero(heroes: list[dict], name_or_id: str) -> dict | None:
    try:
        hid = int(name_or_id)
        return next((h for h in heroes if h["id"] == hid), None)
    except ValueError:
        return next((h for h in heroes if h.get("name") == name_or_id), None)


def execute_call_sequence(seq: list[dict]) -> int:
    """Fire /rank-up calls in order (bottom-up). Returns number completed."""
    done = 0
    for i, call in enumerate(seq, 1):
        food_csv = ",".join(str(x) for x in call["food_ids"])
        url = f"/rank-up?hero_id={call['hero_id']}&food={food_csv}"
        print(f"  [{i}/{len(seq)}] {call['hero_name']} G{call['from_grade']}->G{call['to_grade']}"
              f" (consume {len(call['food_ids'])} G{call['from_grade']})")
        r = _get(url, timeout=30)
        if not r.get("ok"):
            print(f"    !! /rank-up failed: {r}")
            return done
        done += 1
        time.sleep(0.3)  # let the cmd queue settle
    return done


def main() -> int:
    ap = argparse.ArgumentParser(description="6-star a hero, autonomously")
    ap.add_argument("hero", help="Target hero name (or id) to rank up. "
                                  "e.g. 'Harima' or 19864.")
    ap.add_argument("--to-grade", type=int, default=6,
                    help="Final grade (default 6 = max).")
    ap.add_argument("--carry", type=int, default=6864,
                    help="Carry hero id for farm_loop fallback (default 6864 Ma'Shalled).")
    ap.add_argument("--stage-name", default="campaign-12-3-nightmare",
                    help="Stage key from data/farm_stages.json for farm_loop fallback.")
    ap.add_argument("--max-rarity", type=int, default=3,
                    help="Max food rarity for cascade (1-3, default 3 = Rare).")
    ap.add_argument("--plan-only", action="store_true",
                    help="Show plan + feasibility but don't execute or farm.")
    ap.add_argument("--no-farm", action="store_true",
                    help="If infeasible, just print shortfall — don't launch farm_loop.")
    ap.add_argument("--no-execute", action="store_true",
                    help="If feasible, print the rank-up sequence but don't fire /rank-up.")
    args = ap.parse_args()

    heroes = fetch_heroes()
    target = find_hero(heroes, args.hero)
    if not target:
        print(f"ERROR: hero '{args.hero}' not in roster", file=sys.stderr)
        return 1

    reserved = load_reserved()
    protected = load_protected()

    print(f"=== 6-star {target['name']} ===")
    print(f"  current: R{target['rarity']}/G{target['grade']}/L{target['level']}")
    print(f"  goal:    G{args.to_grade}")
    print(f"  protections: legendaries={protected.get('exclude_all_legendaries')}"
          f" epics={protected.get('exclude_all_epics')}"
          f" fusion_targets={protected.get('fusion_targets')}"
          f" named={protected.get('protected_names')}")

    if (target.get("grade") or 0) >= args.to_grade:
        print(f"\n*** Already at G{target['grade']} (>= G{args.to_grade}). Nothing to do.")
        return 0

    plan = plan_one_target(heroes, target, args.to_grade, reserved, protected)
    print(f"\n=== Cascade plan ===")
    for c in plan["chain"]:
        flag = "OK" if c["short"] == 0 else f"SHORT {c['short']}"
        print(f"  G{c['grade']}: need {c['demand']:>3} fodder, have "
              f"{c['available']:>3}, promote {c['covered_by_promotion']:>3}  [{flag}]")
    print(f"  feasible: {plan['feasible']}")

    if not plan["feasible"]:
        # Estimate G0 commons needed at the bottom of the chain.
        # The "stuck_grade" tells us where we ran out. The shortfall
        # cascades all the way down to G1, where each shortfall maps
        # 1:1 to a G0 common (G0->G1 doesn't take fodder; the unit
        # IS its own promoter once farmed to L<g*10>).
        stuck_short = next((c["short"] for c in plan["chain"] if c["grade"] == 1), 0)
        print(f"\n  shortfall at G1: {stuck_short} commons needed")
        print(f"  Each new G0 common (Mystery Shard pull) -> 1 G1 fodder after farming.")

    if args.plan_only:
        return 0

    # If feasible, execute the cascade right now — no farming needed.
    if plan["feasible"]:
        seq = materialize_call_sequence(heroes, target, args.to_grade,
                                         reserved, protected)
        if not seq:
            print(f"\nWARN: feasibility says yes but no call sequence — bug?")
            return 1
        print(f"\n=== Rank-up sequence ({len(seq)} calls) ===")
        if args.no_execute:
            for i, call in enumerate(seq, 1):
                print(f"  [{i}] {call['hero_name']} G{call['from_grade']}->G{call['to_grade']}"
                      f" food={call['food_ids']}")
            print("(--no-execute set, not firing)")
            return 0
        # Sanity: target must be at level cap to rank up. If not, bail —
        # caller has to level it manually first (or via farm_loop).
        if (target.get("level") or 0) < (target.get("grade") or 0) * 10:
            print(f"\nWARN: {target['name']} is L{target['level']} but G{target['grade']}"
                  f" needs L{target['grade']*10} to rank up. "
                  f"Run farm_loop with this hero in the squad first, or use "
                  f"the slow farm path via --no-execute.")
            return 1
        print(f"\nExecuting cascade...")
        n = execute_call_sequence(seq)
        print(f"\n=== Done: {n}/{len(seq)} rank-ups fired ===")
        # Re-read target
        heroes = fetch_heroes()
        cur = next((h for h in heroes if h["id"] == target["id"]), None)
        if cur:
            print(f"  {cur['name']} now: R{cur['rarity']}/G{cur['grade']}/L{cur['level']}")
        return 0 if n == len(seq) else 1

    # Infeasible: launch farm_loop to slowly build fodder. Every battle
    # levels new food + cascades up. The target auto-ranks the moment
    # threshold is reached. User keeps pulling shards in the background.
    if args.no_farm:
        print(f"\n--no-farm set; not launching farm_loop. Pull more commons via "
              f"Mystery Shards and re-run.")
        return 1

    print(f"\n=== Launching farm_loop (unlimited runs) ===")
    print(f"  carry: {args.carry}  stage: {args.stage_name}")
    print(f"  Each battle levels squad food + cascades. Pull Mystery Shards "
          f"in the background — every new common feeds.")
    print(f"  Press Ctrl-C to stop. Loop also auto-stops when {target['name']} "
          f"reaches G{args.to_grade}.\n")

    cmd = [
        sys.executable, "-u",  # unbuffered stdout for live progress
        str(PROJECT_ROOT / "tools" / "farm_loop.py"),
        "--carry", str(args.carry),
        "--stage-name", args.stage_name,
        "--target-id", str(target["id"]),
        "--target-grade", str(args.to_grade),
        "--max-rarity", str(args.max_rarity),
        "--runs", "0",  # unlimited
    ]
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
