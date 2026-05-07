#!/usr/bin/env python3
"""
Claim free daily shop offers (mod API only).

    python3 tools/daily_shop.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_common import Session, main_wrapper


def run(s: Session, args):
    s.navigate("village", wait=1.5)
    if not s.click_village("shop", wait=2.5):
        return False

    # Shop opens with several free-offer tiles. Claim any button whose path
    # contains "Free", "Claim", or "Collect". Loop because each claim may
    # refresh the dialog state.
    total = s.click_until_gone(["FreeGift", "ClaimFree", "ClaimButton",
                                 "FreeOffer", "Free "], wait=1.5, max_iter=12)
    s.log(f"claimed {total} offer(s)")

    # Also try a generic pass in case button names differ slightly
    total += s.click_until_gone(["Claim", "Collect"], wait=1.0, max_iter=6)

    time.sleep(1.0)
    # Back out of shop
    s.dismiss()
    s.dismiss()
    return True


if __name__ == "__main__":
    sys.exit(main_wrapper("shop", run))
