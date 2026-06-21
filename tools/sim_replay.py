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


def replay_fixture(fixture, max_cb_turns=50, verbose=False):
    """Run the calibrated sim against the fixture's team + affinity.

    Returns dict: {fixture, real, sim, delta, delta_pct, error}."""
    out = {
        "fixture": fixture["timestamp"],
        "affinity": fixture.get("affinity"),
        "team": fixture.get("hero_team_names", []),
        "real_damage": fixture.get("real_damage_peak"),
        "real_boss_turns": fixture.get("real_boss_turns"),
        "sim_damage": None,
        "sim_cb_turns": None,
        "delta": None,
        "delta_pct": None,
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
    from cb_sim import evaluate_team_calibrated
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
    out["sim_damage"] = sim_total
    out["sim_cb_turns"] = result.get("cb_turns")
    if out["real_damage"] and out["sim_damage"]:
        out["delta"] = out["sim_damage"] - out["real_damage"]
        out["delta_pct"] = (out["delta"] / out["real_damage"]) * 100.0
    return out


def format_summary(r):
    if r["error"]:
        return f"FAIL {r['fixture']}  {r.get('affinity','?'):<6}  {r['error']}"
    real = r["real_damage"] or 0
    sim = r["sim_damage"] or 0
    dp = r["delta_pct"]
    dp_s = f"{dp:+6.1f}%" if dp is not None else "   n/a "
    return (f"{r['fixture']}  {r['affinity']:<6}  "
            f"real={real:>11,}  sim={sim:>11,}  delta={dp_s}  "
            f"(real_bt={r['real_boss_turns']}, sim_bt={r['sim_cb_turns']})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("timestamp", help="Fixture timestamp (YYYYMMDD_HHMMSS).")
    ap.add_argument("--json", action="store_true", help="JSON output.")
    ap.add_argument("--quiet", action="store_true", help="One-line summary only.")
    ap.add_argument("--max-cb-turns", type=int, default=50)
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
                            verbose=args.verbose)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_summary(result))
    return 0 if not result.get("error") else 3


if __name__ == "__main__":
    sys.exit(main())
