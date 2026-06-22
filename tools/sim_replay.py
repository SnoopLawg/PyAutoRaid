#!/usr/bin/env python3
"""
Sim replay — runs the calibrated CB sim against an archived fixture
and reports the delta vs the real game. No CB key spent.

Used by sim_regress.py to grade sim changes across the full fixture
library. Single-fixture mode for debugging individual divergences.

Usage:
  python3 tools/sim_replay.py 20260619_082925              # one fixture
  python3 tools/sim_replay.py 20260619_082925 --json       # machine output
  python3 tools/sim_replay.py 20260619_082925 --quiet      # one-line summary
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from fixture_archive import load_manifest


def find_fixture(manifest, timestamp):
    for f in manifest.get("fixtures", []):
        if f.get("timestamp") == timestamp:
            return f
    return None


def replay_fixture(fixture, max_cb_turns=50, verbose=False, compare_at_bt=None,
                   trials=0):
    """Run the calibrated sim against the fixture's team + affinity.

    By default, compares sim's cumulative damage at the SAME boss turn
    the fixture ended on (fixture.real_boss_turns) — apples-to-apples
    even for partial captures from cb_harvest. Pass `compare_at_bt` to
    override (e.g. compare at boss turn 21 across all fixtures).

    Args:
      trials: 0 = deterministic single-shot (default). >0 = Monte Carlo
        with that many trials; populates `mc` block with distribution
        stats and reports whether real_damage falls within the
        5-95th percentile band.

    Returns dict with point-comparison fields plus optional `mc` block
    when trials > 0."""
    out = {
        "fixture": fixture["timestamp"],
        "affinity": fixture.get("affinity"),
        "team": fixture.get("hero_team_names", []),
        "real_damage": fixture.get("real_damage_peak"),
        "real_boss_turns": fixture.get("real_boss_turns"),
        "sim_damage": None,
        "sim_total": None,         # sim final total (end of sim run)
        "sim_cb_turns": None,
        "compared_at_bt": None,    # the boss turn used for comparison
        "delta": None,
        "delta_pct": None,
        "mc": None,                # populated when trials > 0
        "error": None,
    }
    team = fixture.get("hero_team_names") or []
    if len(team) != 5:
        out["error"] = f"need 5 heroes, got {len(team)}"
        return out
    boss_element = fixture.get("boss_element")
    if not boss_element:
        out["error"] = "missing boss_element"
        return out

    # Import lazily — cb_sim is heavy
    from cb_sim import evaluate_team_calibrated, evaluate_team_mc
    try:
        result = evaluate_team_calibrated(
            hero_names=team,
            cb_element=boss_element,
            use_current_gear=True,
            max_cb_turns=max_cb_turns,
            verbose=verbose,
        )
    except Exception as ex:
        out["error"] = f"sim crashed: {ex}"
        return out

    if "error" in result:
        out["error"] = f"sim returned error: {result['error']}"
        return out

    sim_total = result.get("total")
    if sim_total is not None:
        sim_total = int(round(sim_total))
    out["sim_total"] = sim_total
    out["sim_cb_turns"] = result.get("cb_turns")

    # Default comparison turn = real_boss_turns from the fixture so
    # partial captures (e.g. cb_harvest --kill-at-turn 15) compare
    # against sim at the same turn, not sim at end.
    target_bt = compare_at_bt or out["real_boss_turns"]
    sim_at_bt = _sim_damage_at_bt(result.get("turn_snapshots") or [], target_bt)
    if sim_at_bt is not None:
        sim_at_bt = int(round(sim_at_bt))
    out["sim_damage"] = sim_at_bt
    out["compared_at_bt"] = target_bt

    if out["real_damage"] and out["sim_damage"]:
        out["delta"] = out["sim_damage"] - out["real_damage"]
        out["delta_pct"] = (out["delta"] / out["real_damage"]) * 100.0

    # Monte Carlo block — distribution at the same comparison BT.
    if trials > 0:
        try:
            mc = evaluate_team_mc(
                hero_names=team,
                cb_element=boss_element,
                n_trials=trials,
                use_current_gear=True,
                max_cb_turns=max_cb_turns,
            )
        except Exception as ex:
            out["mc"] = {"error": f"mc crashed: {ex}"}
            return out
        if "error" in mc:
            out["mc"] = mc
            return out

        # Per-BT distribution at the target BT
        per_bt = (mc.get("turn_distributions") or {}).get(target_bt) or []
        if not per_bt:
            # No exact snapshot at target_bt across trials — fall back
            # to totals (rare; means sim died before target_bt every trial)
            per_bt = mc.get("samples", [])
        sorted_bt = sorted(per_bt)
        n = len(sorted_bt)
        def _pct(p):
            if n == 0:
                return None
            idx = max(0, min(n - 1, int(round(p / 100.0 * (n - 1)))))
            return sorted_bt[idx]
        mc_at_bt = {
            "trials": n,
            "at_bt": target_bt,
            "min": sorted_bt[0] if n else None,
            "max": sorted_bt[-1] if n else None,
            "median": sorted_bt[n // 2] if n else None,
            "mean": (sum(sorted_bt) / n) if n else None,
            "p5": _pct(5),
            "p25": _pct(25),
            "p75": _pct(75),
            "p95": _pct(95),
        }
        real = out["real_damage"] or 0
        if real and n:
            mc_at_bt["real_in_p5_p95"] = mc_at_bt["p5"] <= real <= mc_at_bt["p95"]
            mc_at_bt["real_vs_median_pct"] = (
                (real - mc_at_bt["median"]) / mc_at_bt["median"] * 100.0
                if mc_at_bt["median"] else None
            )
        out["mc"] = mc_at_bt
    return out


def _sim_damage_at_bt(turn_snapshots, target_bt):
    """Return sim cumulative_damage at the snapshot where cb_turn == target_bt.

    Falls back to the snapshot just below target_bt if there's no exact
    match (sim may have died earlier). Returns the LAST snapshot's
    cumulative_damage if the sim never reached target_bt."""
    if not turn_snapshots or target_bt is None:
        return None
    exact = next((s for s in turn_snapshots if s.get("cb_turn") == target_bt), None)
    if exact:
        return exact.get("cumulative_damage")
    # Sim ended before target_bt — return the final cumulative damage
    return turn_snapshots[-1].get("cumulative_damage") if turn_snapshots else None


def format_summary(r):
    if r["error"]:
        return f"FAIL {r['fixture']}  {r.get('affinity','?'):<6}  {r['error']}"
    real = r["real_damage"] or 0
    sim = r["sim_damage"] or 0
    dp = r["delta_pct"]
    dp_s = f"{dp:+6.1f}%" if dp is not None else "   n/a "
    bt = r.get("compared_at_bt") or r["real_boss_turns"]
    base = (f"{r['fixture']}  {r['affinity']:<6}  "
            f"real={real:>11,}  sim={sim:>11,}  delta={dp_s}  @BT{bt}")
    mc = r.get("mc") or {}
    if mc and not mc.get("error"):
        in_band = mc.get("real_in_p5_p95")
        flag = "IN" if in_band else "OUT"
        rv = mc.get("real_vs_median_pct")
        rv_s = f"{rv:+6.1f}%" if rv is not None else "   n/a "
        base += (f"  | MC[{mc.get('trials')}]"
                 f" p5={int(round(mc.get('p5') or 0)):>11,}"
                 f" med={int(round(mc.get('median') or 0)):>11,}"
                 f" p95={int(round(mc.get('p95') or 0)):>11,}"
                 f"  real{rv_s} vs med  ({flag})")
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timestamp", help="Fixture timestamp (YYYYMMDD_HHMMSS).")
    ap.add_argument("--json", action="store_true", help="JSON output.")
    ap.add_argument("--quiet", action="store_true", help="One-line summary only.")
    ap.add_argument("--max-cb-turns", type=int, default=50)
    ap.add_argument("--at-bt", type=int, default=None,
                    help="Compare sim damage at boss turn N (default: "
                         "fixture's real_boss_turns).")
    ap.add_argument("--trials", type=int, default=0,
                    help="Monte Carlo: run N stochastic trials and report "
                         "distribution (p5/median/p95) + whether real "
                         "damage falls in the 5-95 band. 0 = single "
                         "deterministic run (default).")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    manifest = load_manifest()
    if not manifest:
        print("No manifest. Run `tools/fixture_archive.py rebuild` first.")
        return 1

    fixture = find_fixture(manifest, args.timestamp)
    if not fixture:
        print(f"No fixture for timestamp {args.timestamp!r}")
        return 2

    if not args.quiet and not args.json:
        print(f"Replaying {fixture['timestamp']} "
              f"({fixture.get('affinity','?')} UNM, "
              f"team={','.join(fixture.get('hero_team_names',[]))})")
        print(f"Real: {fixture.get('real_damage_peak') or 0:,} damage at boss turn "
              f"{fixture.get('real_boss_turns')}")
        print("Running sim...")

    result = replay_fixture(fixture, max_cb_turns=args.max_cb_turns,
                            verbose=args.verbose, compare_at_bt=args.at_bt,
                            trials=args.trials)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_summary(result))
    return 0 if not result.get("error") else 3


if __name__ == "__main__":
    sys.exit(main())
