#!/usr/bin/env python3
"""Hands-off daily Raid runner. Sequences the day's high-priority tasks:

  1. Refresh reserved-hero set from current presets
  2. Run CB daily (both keys, calibrate)
  3. Spider Hard 6 grind (preset 7 SpiderH9 -- 100% WR proven)
  4. Dragon Hard 3 grind (preset 5 DH3v3 -- 96.6% WR proven)
  5. (TODO) Iron Twins Force 6-7 with whatever team is slotted (cleared
     stages, reliable)
  6. Optional food-leveling on remaining energy (--food)

Stop conditions: any phase with --max-fails N exceeded -> skip to next.
Energy threshold guard prevents draining below `--reserve-energy` so
event-points runs are still possible.

Usage:
    python3 tools/daily_run.py                    # CB + Spider 5 + Dragon 3
    python3 tools/daily_run.py --skip-cb          # if CB already run
    python3 tools/daily_run.py --spider-runs 30 --dragon-runs 10
    python3 tools/daily_run.py --food --food-runs 50

Reads the current preset list at startup so it never refers to a stale id.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"


def _get(path: str, timeout: int = 15) -> dict:
    with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def find_preset_id_by_name(name: str) -> int | None:
    try:
        d = _get("/presets")
    except Exception:
        return None
    for p in d.get("presets", []):
        if p.get("name") == name:
            return p.get("id")
    return None


def energy() -> int:
    try:
        return _get("/all-resources").get("Energy", 0)
    except Exception:
        return -1


def cb_keys() -> int:
    try:
        return _get("/all-resources").get("AllianceBossKey", 0)
    except Exception:
        return 0


def run_cmd(args: list[str], label: str, log_path: str = None) -> int:
    """Run a tool subprocess and stream output."""
    print(f"\n{'='*60}")
    print(f"  PHASE: {label}")
    print(f"  cmd: {' '.join(args)}")
    print(f"{'='*60}\n")
    proc = subprocess.run(args, capture_output=False)
    return proc.returncode


def phase_refresh_reserved() -> int:
    return run_cmd(
        ["python3", "tools/build_reserved_set.py"],
        "Refresh reserved-hero set from presets",
    )


def phase_cb_daily(args) -> int:
    if args.skip_cb or cb_keys() <= 0:
        print("\n[SKIP CB] no keys or --skip-cb")
        return 0
    return run_cmd(
        ["python3", "tools/cb_daily.py", "--wait"],
        f"Daily CB ({cb_keys()} keys)",
    )


def phase_spider(args) -> int:
    if args.spider_runs <= 0:
        return 0
    pid = find_preset_id_by_name("SpiderH9")
    if pid is None:
        print("\n[SKIP Spider] preset 'SpiderH9' not found")
        return 0
    return run_cmd(
        ["python3", "tools/dungeon_run.py",
         "--dungeon", "spider", "--hard", "--stage", "6",
         "--preset", str(pid), "--runs", str(args.spider_runs),
         "--max-fails", str(args.max_fails), "--no-auto-sell", "--wait"],
        f"Spider Hard 6 x {args.spider_runs}",
    )


def phase_dragon(args) -> int:
    if args.dragon_runs <= 0:
        return 0
    pid = find_preset_id_by_name("DH3v3")
    if pid is None:
        print("\n[SKIP Dragon] preset 'DH3v3' not found")
        return 0
    return run_cmd(
        ["python3", "tools/dungeon_run.py",
         "--dungeon", "dragon", "--hard", "--stage", "3",
         "--preset", str(pid), "--runs", str(args.dragon_runs),
         "--max-fails", str(args.max_fails), "--no-auto-sell", "--wait"],
        f"Dragon Hard 3 x {args.dragon_runs}",
    )


def phase_food(args) -> int:
    if not args.food or args.food_runs <= 0:
        return 0
    print("\n[FOOD] Note: requires manual nav to a campaign hero-selection")
    print("       dialog before running. Tool will drive StartBattle + Replay.")
    cmd = ["python3", "tools/level_food.py",
           "--runs", str(args.food_runs),
           "--food-rarity-max", args.food_rarity,
           "--max-fails", str(args.max_fails)]
    if args.auto_rank_up:
        cmd.append("--auto-rank-up")
    return run_cmd(cmd, f"Food leveling x {args.food_runs}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-cb", action="store_true")
    ap.add_argument("--spider-runs", type=int, default=10)
    ap.add_argument("--dragon-runs", type=int, default=5)
    ap.add_argument("--food", action="store_true",
                    help="Run food-leveling phase (requires manual campaign nav)")
    ap.add_argument("--food-runs", type=int, default=20)
    ap.add_argument("--food-rarity", default="uncommon",
                    choices=["common", "uncommon", "rare"])
    ap.add_argument("--auto-rank-up", action="store_true",
                    help="Pass-through to level_food.py -- sacrifices food at level cap")
    ap.add_argument("--max-fails", type=int, default=3)
    ap.add_argument("--reserve-energy", type=int, default=5000,
                    help="Stop a phase early if energy drops below this (default 5000)")
    args = ap.parse_args()

    print(f"=== Daily Run starting at {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"Energy: {energy()}, CB keys: {cb_keys()}")

    phase_refresh_reserved()

    rc = phase_cb_daily(args)
    if rc != 0:
        print(f"  CB phase rc={rc}, continuing")

    if energy() < args.reserve_energy:
        print(f"\n[STOP] Energy {energy()} < reserve {args.reserve_energy}, halting before Spider")
        return 0
    rc = phase_spider(args)
    if rc != 0:
        print(f"  Spider phase rc={rc}, continuing")

    if energy() < args.reserve_energy:
        print(f"\n[STOP] Energy {energy()} < reserve {args.reserve_energy}, halting before Dragon")
        return 0
    rc = phase_dragon(args)
    if rc != 0:
        print(f"  Dragon phase rc={rc}, continuing")

    rc = phase_food(args)

    print(f"\n=== Daily Run done at {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"Final energy: {energy()}, CB keys: {cb_keys()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
