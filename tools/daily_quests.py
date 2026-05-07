#!/usr/bin/env python3
"""
Claim daily + advanced/weekly quests (mod API only).

    python3 tools/daily_quests.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_common import Session, main_wrapper


def run(s: Session, args):
    s.navigate("village", wait=1.5)
    if not s.click_village("quests", wait=2.5):
        return False

    # Daily tab - claim every pending quest
    daily = s.click_until_gone(["QuestClaim", "ClaimButton", "Claim"],
                               wait=1.2, max_iter=24)
    s.log(f"claimed {daily} daily quest(s)")

    # Switch to advanced / weekly tab (button path usually contains "Advanced" or "Weekly")
    if s.click_any(["AdvancedQuests", "Advanced", "Weekly"], wait=1.5, max_clicks=1):
        advanced = s.click_until_gone(["QuestClaim", "ClaimButton", "Claim"],
                                      wait=1.2, max_iter=24)
        s.log(f"claimed {advanced} advanced/weekly quest(s)")

    time.sleep(1.0)
    s.dismiss()
    s.dismiss()
    return True


if __name__ == "__main__":
    sys.exit(main_wrapper("quests", run))
