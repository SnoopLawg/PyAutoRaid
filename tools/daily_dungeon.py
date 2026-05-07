#!/usr/bin/env python3
"""
Dungeon farming via mod API (no pyautogui).

    python3 tools/daily_dungeon.py --dungeon dragon --stage 20 --runs 5
    python3 tools/daily_dungeon.py --dungeon spider --stage 20 --runs 3
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_common import Session, main_wrapper


def _battle_done(mod, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            st = mod._get("/battle-state") or {}
            if not st.get("active", False):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def run(s: Session, args):
    s.navigate("dungeon", wait=3.0)

    # Dungeons screen: find the target dungeon tile (Dragon, Spider, etc.)
    target = args.dungeon.lower()
    matches = s.find_paths(target, target.capitalize())
    if not matches:
        s.log(f"no '{args.dungeon}' dungeon tile found on /buttons")
        return False
    s.log(f"open {args.dungeon}")
    try:
        s.mod.click_path(matches[0])
        time.sleep(2.5)
    except Exception as e:
        s.log(f"open err: {e}")
        return False

    # Select the stage button (e.g. "20" for Dragon 20). Stages are typically
    # named by number in the path.
    stage = str(args.stage)
    stage_paths = s.find_paths(f"Stage{stage}", f"_{stage}_", f"/{stage}/")
    if stage_paths:
        s.log(f"select stage {stage}")
        try:
            s.mod.click_path(stage_paths[0])
            time.sleep(2.0)
        except Exception as e:
            s.log(f"stage err: {e}")

    ran = 0
    for i in range(args.runs):
        # Start battle
        if not s.click_any(["StartBattle", "Battle", "Start"], wait=2.5, max_clicks=1):
            s.log(f"start button not found on run {i+1}")
            break

        if not _battle_done(s.mod, timeout=args.timeout):
            s.log("battle timed out")
            break

        # Dismiss result dialog - mod's /dismiss covers most victory screens
        time.sleep(1.5)
        s.dismiss()
        time.sleep(1.0)
        ran += 1
        s.log(f"completed run {ran}/{args.runs}")

    s.log(f"ran {ran}/{args.runs} dungeon battle(s)")
    return ran > 0


def _args(p):
    p.add_argument("--dungeon", default="dragon",
                   help="dungeon key: dragon, spider, fire_knight, ice_golem, minotaur (default: dragon)")
    p.add_argument("--stage", type=int, default=20, help="stage number (default 20)")
    p.add_argument("--runs", type=int, default=5, help="how many battles to run (default 5)")
    p.add_argument("--timeout", type=int, default=180, help="per-battle timeout seconds (default 180)")


if __name__ == "__main__":
    sys.exit(main_wrapper("dungeon", run, extra_args=_args))
