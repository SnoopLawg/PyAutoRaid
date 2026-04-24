#!/usr/bin/env python3
"""Capture per-tick TM snapshots from the mod's /tick-log endpoint and
summarize them. Each snapshot = one ProcessStartTurn fire, which is the
moment the game is about to resolve a unit's TM cycle. Real ground truth
for sim calibration.

Usage:
    python3 tools/cb_tick_capture.py                 # fetch + save + summarize
    python3 tools/cb_tick_capture.py --clear         # also clear mod's buffer
    python3 tools/cb_tick_capture.py --file x.json   # load existing capture
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"

NAME_BY_TYPE = {
    1070: "Maneater", 6510: "Demytha", 6200: "Ninja",
    4880: "Geomancer", 6280: "Venomage",
}

# The tick log emits battle-scoped Id (0-4 players, 5 boss). Map via battle-state.
def fetch_id_to_name():
    try:
        with urllib.request.urlopen(f"{MOD_BASE}/battle-state", timeout=10) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}
    mapping = {}
    for i, h in enumerate(d.get("heroes", [])):
        tid = h.get("type_id")
        nm = NAME_BY_TYPE.get(tid, f"type{tid}")
        side = h.get("side", "?")
        mapping[i] = f"{nm}({side[0]})"
    return mapping


def fetch_tick_log(clear: bool = False):
    url = f"{MOD_BASE}/tick-log?clear={'true' if clear else 'false'}"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def id_to_name(uid: int, mapping=None) -> str:
    if mapping and uid in mapping:
        return mapping[uid]
    return f"id{uid}"


def summarize(data, id_map=None):
    ticks = data.get("ticks", [])
    if not ticks:
        print("No ticks captured.")
        return
    print(f"Total ticks: {len(ticks)}")

    # Trace each unit's TM over time
    per_unit_turns = {}    # uid -> list[(tick, tm)]
    per_unit_turn_n = {}   # uid -> last turn_n seen
    boss_tn_at_tick = {}   # tick -> boss turn_n (for alignment)
    for entry in ticks:
        tick = entry.get("tick")
        for u in entry.get("units", []):
            uid = u.get("id")
            tm = u.get("tm")
            tn = u.get("tn")
            side = u.get("s")
            per_unit_turns.setdefault(uid, []).append((tick, tm, tn, side))
            if side == "e":
                boss_tn_at_tick[tick] = tn

    # Per-unit turn events (when turn_n bumped) — that's their cast moments.
    print("\nPer-unit cast ticks (turn_n increments):")
    for uid, seq in sorted(per_unit_turns.items()):
        nm = id_to_name(uid, id_map)
        casts = []
        last_tn = 0
        for tick, tm, tn, side in seq:
            if tn > last_tn:
                casts.append((tick, boss_tn_at_tick.get(tick, "?"), tm))
                last_tn = tn
        cast_str = ", ".join(f"tk{t}(BT{bt},tm={tm})" for t, bt, tm in casts[:15])
        extra = f" ... +{len(casts)-15}" if len(casts) > 15 else ""
        print(f"  {nm:<12} ({uid}): casts={len(casts)}  [{cast_str}{extra}]")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--clear", action="store_true",
                   help="Clear mod's tick log buffer after fetching")
    p.add_argument("--file", help="Load existing capture instead of fetching")
    p.add_argument("--save", help="Save capture to file (default: auto-name)")
    p.add_argument("--summary-only", action="store_true",
                   help="Print summary only, don't save")
    args = p.parse_args()

    id_map = {}
    if args.file:
        data = json.loads(Path(args.file).read_text())
        print(f"Loaded {args.file}")
        id_map = data.get("id_map", {})
        id_map = {int(k): v for k, v in id_map.items()}
    else:
        id_map = fetch_id_to_name()
        data = fetch_tick_log(args.clear)
        if not args.summary_only:
            out = args.save or f"tick_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            data["id_map"] = {str(k): v for k, v in id_map.items()}
            Path(out).write_text(json.dumps(data))
            print(f"Saved {out}")

    summarize(data, id_map)
    return 0


if __name__ == "__main__":
    sys.exit(main())
