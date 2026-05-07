#!/usr/bin/env python3
"""
Daily gem mine collection (mod API only, no pyautogui).

    python3 tools/daily_gem_mine.py
    python3 tools/daily_gem_mine.py --quiet
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_common import Session, main_wrapper


def run(s: Session, args):
    s.navigate("village", wait=2.0)

    # The Gem Mine building appears in /buttons as "Crystal_Mine"; its clickable
    # collect target is named "GemsCounter_h" on the building itself. A single
    # click collects the ready pile (no separate claim button).
    if not s.click_any(["GemsCounter_h", "GemsCounter"], wait=2.0, max_clicks=1):
        s.log("GemsCounter not visible (mine on cooldown or not yet unlocked)")
        return False

    # Post-collect: a reward popup may appear. Dismiss it.
    time.sleep(1.0)
    s.dismiss()
    time.sleep(0.8)
    s.dismiss()
    return True


if __name__ == "__main__":
    sys.exit(main_wrapper("gem_mine", run))
