#!/usr/bin/env python3
"""
Clan check-in + treasure collection (mod API only).

    python3 tools/daily_clan.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_common import Session, main_wrapper


def run(s: Session, args):
    s.navigate("village", wait=1.5)
    if not s.click_village("clan", wait=2.5):
        return False

    # Open members panel if a dedicated tab is present
    s.click_any(["ClanMembers", "Members", "Alliance"], wait=1.2, max_clicks=1)

    # Daily check-in
    if s.click_any(["CheckIn", "DailyCheckIn", "ClanCheckIn"], wait=1.5, max_clicks=1):
        s.log("checked in")

    # Clan treasure chest
    if s.click_any(["Treasure", "ClanTreasure"], wait=1.5, max_clicks=1):
        s.log("opened treasure")
        s.click_until_gone(["Claim", "Collect", "Open"], wait=1.0, max_iter=6)

    time.sleep(1.0)
    s.dismiss()
    s.dismiss()
    return True


if __name__ == "__main__":
    sys.exit(main_wrapper("clan", run))
