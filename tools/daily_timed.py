#!/usr/bin/env python3
"""
Claim timed rewards (5m/20m/40m/60m/90m/180m) via mod API.

    python3 tools/daily_timed.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_common import Session, main_wrapper


def run(s: Session, args):
    s.navigate("village", wait=1.5)

    # Timed rewards live on a top-bar button. Path typically contains
    # "TimeRewards" or "TimedRewards".
    if not s.click_any(["TimeRewards", "TimedRewards", "TimeReward"],
                       wait=2.0, max_clicks=1):
        s.log("timed-rewards button not found on village HUD")
        return False

    # Each available tier shows a red-dot button. Claim all.
    claimed = s.click_until_gone(["RedDot", "RedNotification", "Claim",
                                   "Collect", "Receive"], wait=1.2, max_iter=10)
    s.log(f"claimed {claimed} timed tier(s)")

    time.sleep(1.0)
    s.dismiss()
    s.dismiss()
    return True


if __name__ == "__main__":
    sys.exit(main_wrapper("timed", run))
