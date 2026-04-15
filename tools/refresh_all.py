#!/usr/bin/env python3
"""
Full data refresh + rebuild pipeline.

One command: fetch all data from mod → rebuild skills_db → rebuild DB →
regenerate auto-profiles → recalibrate sim (optional).

Usage:
    python3 tools/refresh_all.py                # full refresh from live mod
    python3 tools/refresh_all.py --offline      # rebuild from existing JSON (no mod needed)
    python3 tools/refresh_all.py --calibrate    # also run sim calibration
"""

import sys
import time
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))


def refresh_from_mod():
    """Fetch fresh data from the live mod API."""
    print("=" * 60)
    print("STEP 1: Fetch data from mod API")
    print("=" * 60)
    from refresh_data import main as refresh_main
    # Monkey-patch sys.argv for refresh_data
    old_argv = sys.argv
    sys.argv = ["refresh_data.py"]
    try:
        result = refresh_main()
        if result != 0:
            print("WARNING: refresh_data had issues (continuing)")
    except Exception as ex:
        print(f"WARNING: refresh_data failed: {ex}")
    finally:
        sys.argv = old_argv


def rebuild_db():
    """Rebuild SQLite database from JSON files."""
    print("\n" + "=" * 60)
    print("STEP 2: Rebuild SQLite database")
    print("=" * 60)
    from db_init import import_all
    import_all(data_dir=PROJECT_ROOT)


def verify_profiles():
    """Verify auto-profiles load correctly."""
    print("\n" + "=" * 60)
    print("STEP 3: Verify skill profiles")
    print("=" * 60)
    from load_game_profiles import load_profiles
    sd, se, pd = load_profiles()
    print(f"  Skill data: {len(sd)} heroes")
    print(f"  Skill effects: {len(se)} heroes")
    print(f"  Passive data: {len(pd)} heroes")

    # Check desc-profiler integration
    try:
        from desc_profiler import parse_all_descriptions, compare_with_sim
        dp = parse_all_descriptions()
        print(f"  Descriptions parsed: {len(dp)} heroes")

        # Count remaining discrepancies
        diffs = 0
        for name in sd:
            d = compare_with_sim(name, dp, sd, se)
            diffs += len(d)
        print(f"  Sim discrepancies: {diffs} (CB-irrelevant CC/utility excluded)")
    except Exception as ex:
        print(f"  Desc-profiler check failed: {ex}")

    # Auto-profile stats
    try:
        from auto_profile import auto_generate_profiles
        ap = auto_generate_profiles()
        print(f"  Auto-profiles: {ap and len(ap) or 0} heroes")
    except Exception as ex:
        print(f"  Auto-profile check failed: {ex}")


def run_calibration():
    """Run sim calibration against latest battle log."""
    print("\n" + "=" * 60)
    print("STEP 4: Sim calibration")
    print("=" * 60)

    # Find the most recent battle log
    import glob
    logs = sorted(glob.glob(str(PROJECT_ROOT / "battle_logs_cb_*.json")),
                  key=lambda f: Path(f).stat().st_mtime, reverse=True)
    if not logs:
        print("  No battle logs found, skipping calibration")
        return

    latest = Path(logs[0]).name
    print(f"  Latest log: {latest}")

    from cb_calibrate import extract_real_data, run_sim_for_team, calibrate
    from cb_sim import apply_leader_aura
    from auto_profile import get_leader_skills

    log_path = PROJECT_ROOT / latest
    real_data = extract_real_data(log_path)
    print(f"  Real damage: {real_data['total_damage']:,} ({real_data['boss_turns']} turns)")

    team = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
    sim_result = run_sim_for_team(team, cb_element=4, force_affinity=False,
                                  max_cb_turns=50, use_current_gear=True)

    diff = (sim_result["total"] - real_data["total_damage"]) / max(real_data["total_damage"], 1) * 100
    print(f"  Sim damage: {sim_result['total']:,.0f}")
    print(f"  Error: {diff:+.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Full data refresh + rebuild pipeline")
    parser.add_argument("--offline", action="store_true",
                        help="Skip mod fetch, rebuild from existing JSON")
    parser.add_argument("--calibrate", action="store_true",
                        help="Run sim calibration after rebuild")
    args = parser.parse_args()

    t0 = time.time()

    if not args.offline:
        refresh_from_mod()

    rebuild_db()
    verify_profiles()

    if args.calibrate:
        run_calibration()

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"ALL DONE in {elapsed:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
