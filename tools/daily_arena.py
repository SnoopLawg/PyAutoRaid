#!/usr/bin/env python3
"""
Classic arena 10-battle sweep (mod API + memory reader, no pyautogui).

    python3 tools/daily_arena.py                # runs up to 10 battles
    python3 tools/daily_arena.py --battles 3
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_common import Session, main_wrapper


def _battle_done(mod, timeout=90):
    """Poll /battle-state until inactive."""
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
    s.navigate("arena", wait=3.0)

    # Load memory reader for opponent selection
    reader = None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Modules"))
        from memory_reader import MemoryReader
        reader = MemoryReader()
        if not reader.attach(max_retries=2, retry_delay=2):
            reader = None
    except Exception as e:
        s.log(f"memory reader unavailable: {e}")
        reader = None

    battles_target = args.battles
    ran = 0
    for i in range(battles_target):
        # Pick weakest available opponent (memory), else opponent 0 as fallback
        idx = 0
        if reader is not None:
            try:
                opps = reader.get_arena_opponents() or []
                available = [(j, o) for j, o in enumerate(opps)
                             if o.get("available")]
                if not available:
                    s.log("no available opponents - stopping")
                    break
                available.sort(key=lambda t: t[1].get("power", 0))
                idx = available[0][0]
                s.log(f"battle {i+1}: opponent {idx} power={available[0][1].get('power')}")
            except Exception as e:
                s.log(f"opponent scan err: {e}")

        try:
            s.mod.arena_start_fight(idx)
            time.sleep(1.5)
            s.mod.arena_start_battle()
        except Exception as e:
            s.log(f"start-battle err: {e}")
            break

        if not _battle_done(s.mod, timeout=120):
            s.log("battle timed out")
            break

        try:
            s.mod.dismiss_battle_finish()
        except Exception:
            s.dismiss()
        time.sleep(2.0)
        ran += 1

    s.log(f"ran {ran}/{battles_target} arena battle(s)")
    return ran > 0


def _args(p):
    p.add_argument("--battles", type=int, default=10, help="max battles to run (default 10)")


if __name__ == "__main__":
    sys.exit(main_wrapper("arena", run, extra_args=_args))
