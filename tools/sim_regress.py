#!/usr/bin/env python3
"""
Sim regression — runs the calibrated sim against every replayable
fixture, prints the per-affinity calibration table. Zero CB keys
spent. This is the CI check for sim code changes.

The recommendation gate from MISSION.md is +-5% sim accuracy
per-affinity-per-tune-per-run. This tool surfaces every fixture
violating that gate so we can investigate.

Usage:
  python3 tools/sim_regress.py                       # all fixtures
  python3 tools/sim_regress.py --affinity magic      # one affinity
  python3 tools/sim_regress.py --json results.json   # save full data
  python3 tools/sim_regress.py --gate 5.0            # set pass/fail threshold (default +-5%)
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from fixture_archive import load_manifest
from sim_replay import replay_fixture, format_summary


def run_regression(affinity_filter=None, max_cb_turns=50, min_real_bt=0,
                   compare_at_bt=None):
    manifest = load_manifest()
    if not manifest:
        return None, "No manifest. Run `tools/fixture_archive.py rebuild` first."

    fixtures = [
        f for f in manifest["fixtures"]
        if f.get("poll_log") and f.get("affinity") and f.get("real_damage_peak")
        and len(f.get("hero_team_names") or []) == 5
        and (f.get("real_boss_turns") or 0) >= min_real_bt
    ]
    if affinity_filter:
        fixtures = [f for f in fixtures if f.get("affinity") == affinity_filter]

    results = []
    for f in fixtures:
        t0 = time.time()
        r = replay_fixture(f, max_cb_turns=max_cb_turns, compare_at_bt=compare_at_bt)
        r["wall_seconds"] = round(time.time() - t0, 2)
        results.append(r)
    return results, None


def print_per_fixture(results):
    print("Per-fixture detail:")
    for r in results:
        print(f"  {format_summary(r)}  ({r.get('wall_seconds',0)}s)")


def print_summary_table(results, gate_pct):
    by_aff = {}
    for r in results:
        if r.get("error"):
            continue
        a = r.get("affinity") or "unknown"
        by_aff.setdefault(a, []).append(r)

    print(f"\n{'AFFINITY':<8} {'N':>3} {'AVG':>8} {'MEDIAN':>8} {'WORST':>8} {'PASS':>4} {'FAIL':>4}")
    for aff in sorted(by_aff.keys()):
        rs = by_aff[aff]
        deltas = [r["delta_pct"] for r in rs if r.get("delta_pct") is not None]
        if not deltas:
            continue
        avg = statistics.mean(deltas)
        med = statistics.median(deltas)
        worst = max(deltas, key=abs)
        passing = sum(1 for d in deltas if abs(d) <= gate_pct)
        failing = len(deltas) - passing
        print(f"{aff:<8} {len(rs):>3} {avg:>+7.1f}% {med:>+7.1f}% "
              f"{worst:>+7.1f}% {passing:>4} {failing:>4}")

    total = sum(len(rs) for rs in by_aff.values())
    deltas = [r["delta_pct"] for rs in by_aff.values()
              for r in rs if r.get("delta_pct") is not None]
    if deltas:
        passing = sum(1 for d in deltas if abs(d) <= gate_pct)
        print(f"\nGate: +-{gate_pct}%  ->  {passing}/{len(deltas)} fixtures pass")

    errors = [r for r in results if r.get("error")]
    if errors:
        print(f"\n{len(errors)} fixture(s) errored:")
        for r in errors:
            print(f"  {r['fixture']}: {r['error']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--affinity", choices=["magic", "force", "spirit", "void"],
                    help="Filter to one affinity.")
    ap.add_argument("--max-cb-turns", type=int, default=50)
    ap.add_argument("--gate", type=float, default=5.0,
                    help="Pass threshold (abs delta percent). Default 5.0.")
    ap.add_argument("--min-bt", type=int, default=5,
                    help="Skip fixtures with real_boss_turns < this. Default 5 (now "
                         "that --at-bt comparison handles partial captures, the "
                         "filter is just to drop noise <5 turns).")
    ap.add_argument("--at-bt", type=int, default=None,
                    help="Compare every fixture at boss turn N. Default: each "
                         "fixture compared at its own real_boss_turns "
                         "(apples-to-apples for partial captures).")
    ap.add_argument("--json", metavar="PATH",
                    help="Write full results JSON to PATH.")
    ap.add_argument("--quiet", action="store_true",
                    help="Skip per-fixture detail; summary table only.")
    args = ap.parse_args()

    results, err = run_regression(args.affinity, args.max_cb_turns,
                                   args.min_bt, args.at_bt)
    if err:
        print(err)
        return 1
    if not results:
        print("No replayable fixtures. Check `tools/fixture_archive.py list --with-poll`.")
        return 1

    if not args.quiet:
        print_per_fixture(results)
    print_summary_table(results, args.gate)

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nFull results: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
