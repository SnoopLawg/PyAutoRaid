#!/usr/bin/env python3
"""Infer effective in-battle SPD per hero from captured tick log.

The mod's tick log samples TM at every ProcessStartTurn event. Between
two consecutive samples, some number of internal game-ticks elapsed.
The boss gains a fixed amount of TM per tick (13 display units = 190
SPD under the standard CB 32.32 formula), so we use boss TM deltas as
the shared clock.

For any hero, effective_SPD = (hero_tm_delta / boss_tm_delta) * BOSS_SPD
averaged over all adjacent pairs where neither unit cast (TM reset)
between samples.

Usage:
    python3 tools/cb_infer_spd.py tick_log_*.json
"""
import argparse
import json
import sys
from pathlib import Path

BOSS_SPD = 190
BOSS_ID = 5

DEFAULT_NAMES = {
    0: "Maneater", 1: "Demytha", 2: "Ninja",
    3: "Geomancer", 4: "Venomage", 5: "Boss",
}


def infer(tick_file):
    data = json.loads(Path(tick_file).read_text())
    ticks = data.get("ticks", [])
    id_map = data.get("id_map") or {}
    id_map = {int(k): v for k, v in id_map.items()} if id_map else DEFAULT_NAMES

    # Walk adjacent snapshots; only use pairs where:
    #   (a) both hero and boss did NOT cast (tn unchanged)
    #   (b) boss TM strictly increased (not 0→reset)
    # effective_gain_ratio = hero_tm_delta / boss_tm_delta
    gains = {uid: [] for uid in id_map}
    for a, b in zip(ticks, ticks[1:]):
        boss_a = next((u for u in a.get("units", []) if u.get("id") == BOSS_ID), None)
        boss_b = next((u for u in b.get("units", []) if u.get("id") == BOSS_ID), None)
        if not boss_a or not boss_b:
            continue
        if boss_b.get("tn", 0) != boss_a.get("tn", 0):
            continue  # boss casted between a and b
        d_boss = boss_b.get("tm", 0) - boss_a.get("tm", 0)
        if d_boss <= 0:
            continue
        for ua in a.get("units", []):
            uid = ua.get("id")
            if uid == BOSS_ID:
                continue
            ub = next((u for u in b.get("units", []) if u.get("id") == uid), None)
            if not ub:
                continue
            if ub.get("tn", 0) != ua.get("tn", 0):
                continue  # hero casted between a and b
            d = ub.get("tm", 0) - ua.get("tm", 0)
            if d < 0:
                continue
            gains[uid].append(d / d_boss)

    out = {}
    for uid, ratios in gains.items():
        if not ratios:
            continue
        # Use median to avoid outliers (buffs applied mid-sample, etc.)
        ratios_sorted = sorted(ratios)
        n = len(ratios_sorted)
        median = ratios_sorted[n // 2]
        spd = median * BOSS_SPD
        name = id_map.get(uid, f"id{uid}")
        out[name] = {
            "inferred_spd": round(spd, 1),
            "samples": n,
            "min_ratio": round(ratios_sorted[0], 3),
            "max_ratio": round(ratios_sorted[-1], 3),
        }
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tick_file")
    p.add_argument("--save", help="Save effective-SPD table to JSON")
    args = p.parse_args()
    result = infer(args.tick_file)
    print(f"Effective in-battle SPD (inferred from tick log):")
    print(f"{'Hero':<12} {'SPD':>6}  {'samples':>7}  ratio_range")
    for name, r in sorted(result.items(), key=lambda kv: -kv[1]["inferred_spd"]):
        print(f"  {name:<10} {r['inferred_spd']:>6}  {r['samples']:>7}  [{r['min_ratio']}, {r['max_ratio']}]")
    if args.save:
        Path(args.save).write_text(json.dumps(result, indent=2))
        print(f"\nSaved: {args.save}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
