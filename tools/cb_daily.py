#!/usr/bin/env python3
"""
Daily CB Runner — replaces PyAutoRaid's screen-based CB automation.

Runs CB via mod API (no UI), captures battle log, calibrates sim,
stores results to DB. Designed to run from Linux cron.

Usage:
    python3 tools/cb_daily.py                    # run all available keys
    python3 tools/cb_daily.py --keys 1           # run exactly 1 key
    python3 tools/cb_daily.py --cb-element force  # specify today's affinity

Cron (replaces the old PyAutoRaid scheduled task):
    0 7,13,19 * * * cd /home/snoop/projects/pyautoraid && python3 tools/cb_daily.py >> logs/cb_daily.log 2>&1
"""

import json
import sys
import time
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from cb_run import check_ready, check_keys, start_battle, poll_battle, save_battle_log


def wait_for_mod(timeout=300):
    """Wait for the mod API to be ready."""
    print(f"Waiting for mod API (up to {timeout}s)...")
    for i in range(timeout // 5):
        if check_ready():
            return True
        time.sleep(5)
    return False


def store_result(log_info, cb_element, sim_result=None):
    """Store battle result in SQLite database."""
    db_path = PROJECT_ROOT / "pyautoraid.db"
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""INSERT INTO battle_sessions
                        (boss_difficulty, scene, total_turns, total_damage, source_file, recorded_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     ("UNM", "Dungeon_Clan", log_info.get("boss_turns", 0),
                      log_info.get("total_damage", 0), log_info.get("filename", ""),
                      datetime.now().isoformat()))

        if sim_result:
            conn.execute("""INSERT INTO sim_runs
                            (boss_difficulty, cb_element, force_affinity, max_turns,
                             total_damage, turns_survived, run_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                         ("UNM", cb_element, 0, 50,
                          int(sim_result.get("sim_total", 0)),
                          sim_result.get("boss_turns", 50),
                          datetime.now().isoformat()))

        conn.commit()
        print(f"  Result stored in DB")
    except Exception as ex:
        print(f"  DB store failed: {ex}")
    finally:
        conn.close()


def run_one_key(cb_element, run_calibration=True):
    """Run one CB key and return results."""
    print(f"\n{'='*60}")
    print(f"CB RUN — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    if not start_battle():
        print("Failed to start battle!")
        return None

    final_dmg, final_turn = poll_battle()
    print(f"Battle complete: {final_dmg:,} damage, {final_turn} turns")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_info = save_battle_log(f"battle_logs_cb_{ts}.json")
    if not log_info:
        return None

    sim_result = None
    if run_calibration:
        try:
            from cb_run import run_calibration as run_cal
            sim_result = run_cal(log_info["filename"], cb_element)
        except Exception as ex:
            print(f"Calibration failed: {ex}")

    store_result(log_info, cb_element, sim_result)

    return {
        "damage": log_info.get("total_damage", final_dmg),
        "turns": log_info.get("boss_turns", final_turn),
        "log": log_info.get("filename"),
        "sim_error": sim_result.get("error_pct") if sim_result else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Daily CB Runner")
    parser.add_argument("--keys", type=int, default=0,
                        help="Number of keys to use (0=all available)")
    parser.add_argument("--cb-element", default="void",
                        choices=["magic", "force", "spirit", "void"])
    parser.add_argument("--no-calibrate", action="store_true")
    parser.add_argument("--wait", action="store_true",
                        help="Wait for mod to be ready (for cron use)")
    args = parser.parse_args()

    print(f"CB Daily Runner — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Element: {args.cb_element}")

    if args.wait:
        if not wait_for_mod():
            print("Mod not ready after timeout!")
            return 1
    elif not check_ready():
        return 1

    available_keys = check_keys()
    if available_keys < 1:
        print("No CB keys available!")
        return 0

    keys_to_use = args.keys if args.keys > 0 else available_keys
    keys_to_use = min(keys_to_use, available_keys)
    print(f"Running {keys_to_use} key(s)")

    results = []
    for i in range(keys_to_use):
        print(f"\n--- Key {i+1}/{keys_to_use} ---")
        result = run_one_key(args.cb_element, not args.no_calibrate)
        if result:
            results.append(result)
        else:
            print(f"Key {i+1} failed!")
            break

        # Wait between keys
        if i < keys_to_use - 1:
            print("Waiting 10s before next key...")
            time.sleep(10)

    # Summary
    print(f"\n{'='*60}")
    print(f"DAILY SUMMARY")
    print(f"{'='*60}")
    total_dmg = sum(r["damage"] for r in results)
    for i, r in enumerate(results, 1):
        err = f" (sim: {r['sim_error']:+.1f}%)" if r.get("sim_error") is not None else ""
        print(f"  Key {i}: {r['damage']:>12,} ({r['turns']} turns){err}")
    print(f"  Total: {total_dmg:>12,}")
    print(f"  Top chest (72M): {'YES' if total_dmg >= 72_000_000 else 'NO'} ({total_dmg/72_000_000*100:.0f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
