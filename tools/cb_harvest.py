#!/usr/bin/env python3
"""
CB harvest loop — runs back-to-back partial CB battles using the
kill-Raid-mid-fight protocol so a single CB key produces N fixture
captures instead of one.

Each iteration:
  1. Launch cb_watcher.py in --kill-at-turn N mode (background subprocess)
  2. Launch cb_run.py to fire the battle (background subprocess)
  3. Wait for watcher to fire taskkill (Raid dies)
  4. Relaunch PlariumPlay / Raid
  5. Wait for mod attach + login
  6. Repeat

Stops early if: keys hit 0, mod unreachable after relaunch, or any
iteration takes longer than --iter-timeout.

Usage:
  python3 tools/cb_harvest.py --iterations 5 --kill-at-turn 10
  python3 tools/cb_harvest.py --iterations 20 --kill-at-turn 5 --tag opening-rng
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"
PYTHON = sys.executable or "python3"


def mod_get(endpoint, timeout=5):
    try:
        return requests.get(f"{MOD_BASE}{endpoint}", timeout=timeout).json()
    except Exception as ex:
        return {"error": str(ex)}


def keys_remaining():
    r = mod_get("/resources")
    return r.get("cb_keys") if isinstance(r, dict) else None


def mod_ready_for_battle(timeout_s=120):
    """Wait for mod attached + logged in + scene != Main."""
    waited = 0
    while waited < timeout_s:
        st = mod_get("/status")
        if (st.get("logged_in") is True
                and st.get("scene") not in (None, "Main")
                and "error" not in st):
            return True, st
        time.sleep(3)
        waited += 3
    return False, st


def relaunch_raid():
    """Fire PlariumPlay with the standard Raid launch args. Async."""
    local_app = os.environ.get("LOCALAPPDATA", "")
    pp = Path(local_app) / "PlariumPlay" / "PlariumPlay.exe"
    if not pp.exists():
        return False, f"PP not found at {pp}"
    try:
        subprocess.Popen(
            [str(pp), "--args", "-gameid=101", "-tray-start"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        )
        return True, None
    except Exception as ex:
        return False, str(ex)


def harvest_iter(i, args, harvest_dir):
    """Run one harvest iteration. Returns dict with status + telemetry."""
    iter_tag = f"{args.tag}-i{i:02d}" if args.tag else f"harvest-i{i:02d}"
    t0 = time.time()
    out = {
        "i": i,
        "tag": iter_tag,
        "started_at": datetime.now().isoformat(),
        "keys_before": keys_remaining(),
    }

    # Pre-flight: mod ready and key available
    if out["keys_before"] is None or out["keys_before"] <= 0:
        out["result"] = "stop_no_keys"
        return out
    ready, st = mod_ready_for_battle(timeout_s=120)
    if not ready:
        out["result"] = "stop_mod_not_ready"
        out["mod_status"] = st
        return out

    # Spawn watcher (background)
    watcher_log = harvest_dir / f"{iter_tag}.watcher.log"
    watcher_args = [
        PYTHON, "-u", str(PROJECT_ROOT / "tools" / "cb_watcher.py"),
        "--tag", iter_tag,
        "--kill-at-turn", str(args.kill_at_turn),
        "--snapshot-dir", str(harvest_dir),
    ]
    watcher_proc = subprocess.Popen(
        watcher_args,
        stdout=open(watcher_log, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )

    # Brief pause so watcher establishes its wait-for-battle loop
    time.sleep(2)

    # Spawn cb_run (background) to fire the battle
    cb_run_log = harvest_dir / f"{iter_tag}.cb_run.log"
    cb_run_args = [
        PYTHON, "-u", str(PROJECT_ROOT / "tools" / "cb_run.py"),
        "--cb-element", args.cb_element,
    ]
    cb_run_proc = subprocess.Popen(
        cb_run_args,
        stdout=open(cb_run_log, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )

    # Wait for watcher to exit (its kill ends the battle and Raid).
    # Timeout = iter_timeout overall budget.
    try:
        watcher_rc = watcher_proc.wait(timeout=args.iter_timeout)
    except subprocess.TimeoutExpired:
        watcher_proc.kill()
        cb_run_proc.kill()
        out["result"] = "stop_iter_timeout"
        out["elapsed_s"] = round(time.time() - t0, 1)
        return out
    out["watcher_rc"] = watcher_rc

    # cb_run will hang polling the dead mod — kill it
    if cb_run_proc.poll() is None:
        cb_run_proc.kill()

    # If watcher exited code 0 (killed cleanly), Raid is dead.
    # If exit code 1 (battle ended naturally), Raid is alive but
    # the key WAS debited. Either way relaunch to re-sync.
    relaunched, err = relaunch_raid()
    if not relaunched:
        out["result"] = "stop_relaunch_failed"
        out["error"] = err
        return out

    # Wait for the new session
    ready, st = mod_ready_for_battle(timeout_s=120)
    if not ready:
        out["result"] = "stop_post_relaunch_not_ready"
        out["mod_status"] = st
        return out

    out["keys_after"] = keys_remaining()
    out["elapsed_s"] = round(time.time() - t0, 1)
    out["result"] = "kill_clean" if watcher_rc == 0 else "natural_end"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=5,
                    help="How many partial captures to harvest. Default 5.")
    ap.add_argument("--kill-at-turn", type=int, default=10,
                    help="Boss turn to fire taskkill at. Default 10.")
    ap.add_argument("--cb-element", default="force",
                    help="Affinity to run. Default force (only calibrated one).")
    ap.add_argument("--tag", default="harvest",
                    help="Snapshot filename prefix. Default 'harvest'.")
    ap.add_argument("--iter-timeout", type=int, default=300,
                    help="Max seconds per iteration. Default 300.")
    ap.add_argument("--snapshot-dir", default=str(PROJECT_ROOT / "data" / "harvest"),
                    help="Where to write snapshots + per-iter logs.")
    args = ap.parse_args()

    harvest_dir = Path(args.snapshot_dir)
    harvest_dir.mkdir(parents=True, exist_ok=True)
    run_log = harvest_dir / f"harvest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    print(f"Harvest log: {run_log}")
    print(f"Iterations={args.iterations}, kill-at-turn={args.kill_at_turn}, "
          f"element={args.cb_element}")
    print()

    results = []
    for i in range(args.iterations):
        print(f"=== iter {i+1}/{args.iterations} ===")
        r = harvest_iter(i, args, harvest_dir)
        results.append(r)
        with open(run_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(r) + "\n")
        print(f"  -> {r['result']}  "
              f"keys: {r.get('keys_before')} -> {r.get('keys_after')}  "
              f"({r.get('elapsed_s', '?')}s)")
        if r["result"].startswith("stop_"):
            print(f"  ABORTING after iter {i+1}: {r['result']}")
            break

    # Summary
    kept = sum(1 for r in results if r["result"] in ("kill_clean", "natural_end"))
    keys_spent = (results[0].get("keys_before") or 0) - (results[-1].get("keys_after") or 0)
    print(f"\n=== HARVEST DONE ===")
    print(f"Iterations completed: {len(results)}")
    print(f"Successful captures: {kept}")
    print(f"Keys spent: {keys_spent}")
    print(f"Run log: {run_log}")
    print(f"Next step: python3 tools/fixture_archive.py rebuild")
    return 0


if __name__ == "__main__":
    sys.exit(main())
