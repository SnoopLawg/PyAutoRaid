#!/usr/bin/env python3
"""
CB Battle Runner — one command to run a CB fight and capture results.

Navigates to CB, starts battle via mod API (no UI), polls until complete,
saves battle log, runs calibration, stores results.

Usage:
    python3 tools/cb_run.py                          # run with current team
    python3 tools/cb_run.py --cb-element force       # specify today's affinity
    python3 tools/cb_run.py --calibrate              # also run sim calibration
    python3 tools/cb_run.py --team "ME,Demytha,..."  # override team for calibration
"""

import json
import sys
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

MOD_BASE = "http://localhost:6790"
POLL_INTERVAL = 20  # seconds between battle state polls
MAX_POLLS = 50      # ~16 minutes max


def mod_get(endpoint, params=None, timeout=15):
    """GET request to mod API."""
    try:
        r = requests.get(f"{MOD_BASE}{endpoint}", params=params, timeout=timeout)
        return r.json()
    except Exception as ex:
        return {"error": str(ex)}


def check_ready():
    """Check if mod is up and game is logged in."""
    status = mod_get("/status")
    if "error" in status:
        print(f"Mod not reachable: {status['error']}")
        return False
    if not status.get("logged_in"):
        print(f"Not logged in: scene={status.get('scene')}")
        return False
    print(f"Mod ready: scene={status.get('scene')}")
    return True


def check_keys():
    """Check available CB keys."""
    res = mod_get("/resources")
    keys = res.get("cb_keys", 0)
    print(f"CB keys: {keys}")
    return keys


def start_battle():
    """Navigate to CB and start battle via context-calls. Returns True if battle started."""
    print("Navigating to CB...")
    r = mod_get("/navigate", {"target": "cb"})
    if "error" in r:
        print(f"  Navigate failed: {r['error']}")
        return False
    time.sleep(3)

    print("Opening team selection (OnStartClick)...")
    # Use curl-style URL (spaces as %20, brackets as %5B%5D)
    try:
        r = requests.get(
            f"{MOD_BASE}/context-call?"
            "path=UIManager/Canvas%20(Ui%20Root)/Dialogs/"
            "%5BDV%5D%20AllianceEnemiesDialog/Workspace/Content/RightPanel"
            "&method=OnStartClick",
            timeout=15
        )
        d = r.json()
        if "error" in d:
            print(f"  OnStartClick failed: {d['error']}")
            return False
        print(f"  OK: {d.get('invoked')}")
    except Exception as ex:
        print(f"  OnStartClick error: {ex}")
        return False

    time.sleep(5)

    print("Starting battle (StartBattle)...")
    try:
        r = requests.get(
            f"{MOD_BASE}/context-call?"
            "path=UIManager/Canvas%20(Ui%20Root)/Dialogs/"
            "%5BDV%5D%20AllianceBossHeroesSelectionDialog"
            "&method=StartBattle",
            timeout=15
        )
        d = r.json()
        if "error" in d:
            print(f"  StartBattle failed: {d['error']}")
            return False
        print(f"  OK: {d.get('invoked')}")
    except Exception as ex:
        print(f"  StartBattle error: {ex}")
        return False

    # Wait for battle to actually start
    time.sleep(10)
    status = mod_get("/status")
    scene = status.get("scene", "")
    if "Dungeon_Clan" in scene or "Battle" in scene:
        print(f"Battle started! Scene: {scene}")
        return True

    # Check battle state as fallback
    bs = mod_get("/battle-state")
    if "error" not in bs:
        print("Battle started! (detected via battle-state)")
        return True

    print(f"Battle did not start. Scene: {scene}")
    return False


def poll_battle():
    """Poll battle until complete. Returns final boss damage and turn count."""
    print("\nPolling battle progress...")
    prev_turn = 0
    final_dmg = 0
    final_turn = 0

    for i in range(MAX_POLLS):
        bs = mod_get("/battle-state")
        if "error" in bs:
            print(f"  Battle ended at poll {i}")
            break

        for h in bs.get("heroes", []):
            if h.get("side") == "enemy":
                turn = h.get("turn_n", 0)
                dmg = h.get("dmg_taken", 0)
                if turn > prev_turn:
                    print(f"  Turn {turn:>2d}: {dmg:>12,}")
                    prev_turn = turn
                final_dmg = max(final_dmg, dmg)
                final_turn = max(final_turn, turn)
                break

        time.sleep(POLL_INTERVAL)
    else:
        print("  WARNING: Max polls reached, battle may still be running")

    return final_dmg, final_turn


def save_battle_log(filename=None):
    """Fetch and save the battle log from the mod."""
    time.sleep(3)
    r = mod_get("/battle-log", timeout=30)
    if "error" in r:
        print(f"Failed to fetch battle log: {r['error']}")
        return None

    entries = r.get("log", [])
    print(f"\nBattle log: {len(entries)} entries")

    # Find final damage
    max_dmg = 0
    max_turn = 0
    has_final = False
    has_end = False
    team_types = []

    for entry in entries:
        if entry.get("scene") == "final":
            has_final = True
        if entry.get("event") == "battle_end":
            has_end = True
        if "heroes" in entry:
            if not team_types:
                team_types = [h.get("type_id") for h in entry["heroes"] if h.get("side") == "player"]
            for h in entry["heroes"]:
                if h.get("side") == "enemy":
                    max_dmg = max(max_dmg, h.get("dmg_taken", 0))
                    max_turn = max(max_turn, h.get("turn_n", 0))

    print(f"  Final snapshot captured: {has_final}")
    print(f"  Battle end event: {has_end}")
    print(f"  Boss turns: {max_turn}")
    print(f"  Total damage: {max_dmg:,}")

    # Save
    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"battle_logs_cb_{ts}.json"

    filepath = PROJECT_ROOT / filename
    with open(filepath, "w") as f:
        json.dump(r, f)
    print(f"  Saved: {filepath.name}")

    return {
        "filepath": str(filepath),
        "filename": filepath.name,
        "entries": len(entries),
        "boss_turns": max_turn,
        "total_damage": max_dmg,
        "has_final": has_final,
        "team_type_ids": team_types,
    }


def run_calibration(log_filename, cb_element="void", team=None):
    """Run sim calibration against the battle log."""
    print(f"\n{'='*60}")
    print(f"CALIBRATION")
    print(f"{'='*60}")

    from cb_calibrate import extract_real_data, run_sim_for_team, calibrate

    log_path = PROJECT_ROOT / log_filename
    real_data = extract_real_data(log_path)

    ELEMENT_MAP = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
    element = ELEMENT_MAP.get(cb_element, 4)

    if team is None:
        team = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]

    sim_result = run_sim_for_team(team, element, False, max_cb_turns=50, use_current_gear=True)
    calibrate(real_data, sim_result)

    return {
        "real_total": real_data["total_damage"],
        "sim_total": sim_result["total"],
        "error_pct": (sim_result["total"] - real_data["total_damage"]) / max(real_data["total_damage"], 1) * 100,
    }


def main():
    parser = argparse.ArgumentParser(description="CB Battle Runner")
    parser.add_argument("--cb-element", default="void",
                        choices=["magic", "force", "spirit", "void"],
                        help="Today's CB affinity (default: void)")
    parser.add_argument("--calibrate", action="store_true",
                        help="Run sim calibration after battle")
    parser.add_argument("--team", default=None,
                        help="Team for calibration (comma-separated)")
    parser.add_argument("--log-name", default=None,
                        help="Custom filename for battle log")
    parser.add_argument("--skip-battle", default=None,
                        help="Skip battle, calibrate existing log file")
    args = parser.parse_args()

    if args.skip_battle:
        # Just calibrate an existing log
        team = [n.strip() for n in args.team.split(",")] if args.team else None
        run_calibration(args.skip_battle, args.cb_element, team)
        return

    # Pre-checks
    if not check_ready():
        return 1

    keys = check_keys()
    if keys < 1:
        print("No CB keys available!")
        return 1

    # Start battle
    if not start_battle():
        return 1

    # Poll until complete
    final_dmg, final_turn = poll_battle()
    print(f"\nBattle complete: {final_dmg:,} damage over {final_turn} boss turns")

    # Save log
    log_info = save_battle_log(args.log_name)
    if not log_info:
        return 1

    # Calibrate
    if args.calibrate and log_info:
        team = [n.strip() for n in args.team.split(",")] if args.team else None
        cal = run_calibration(log_info["filename"], args.cb_element, team)
        print(f"\nSim accuracy: {cal['error_pct']:+.1f}%")

    print(f"\n{'='*60}")
    print(f"DONE — {final_dmg:,} damage, log saved to {log_info['filename']}")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
