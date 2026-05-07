#!/usr/bin/env python3
"""
Collect inbox rewards (mod API only).

    python3 tools/daily_inbox.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_common import Session, main_wrapper


def run(s: Session, args):
    s.navigate("village", wait=1.5)
    if not s.click_village("inbox", wait=2.5):
        return False

    # "Collect all" sweeps the whole inbox in one action when present
    if s.click_any(["CollectAll", "ClaimAll"], wait=2.0, max_clicks=1):
        s.log("clicked collect-all")
    else:
        # Fall back to per-message claim
        collected = s.click_until_gone(["Collect", "Claim"], wait=1.2, max_iter=30)
        s.log(f"collected {collected} message(s)")

    time.sleep(1.0)
    s.dismiss()
    s.dismiss()
    return True


if __name__ == "__main__":
    sys.exit(main_wrapper("inbox", run))
