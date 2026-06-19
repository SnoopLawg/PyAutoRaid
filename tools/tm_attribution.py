"""TM attribution analyzer — derives per-unit TM-per-tick rate from a
captured tick log and identifies any extra TM gains beyond what natural
accumulation explains.

The approach:
1. Walk all unit_states polls; for each unit, build a series of
   (game_tick, TM, turn_count) tuples.
2. Between consecutive polls (no acts in between), TM should grow at
   exactly StaminaByTick × SPD × elapsed_ticks. Compute the empirical
   rate; compare to the static rate.
3. When a unit acts (tn increments), TM resets to (TM_prev_observed -
   threshold + overflow). The reset hides whatever bonus they got during
   that turn — so we only care about polls in-between actions.
4. Aggregate all "between-action" rate samples per unit. Report mean +
   std dev. Compare to gameplay.json's 0.07.

This lets us nail down whether:
  - Each hero has a constant TM-rate boost (→ effectively higher SPD)
  - The boost depends on specific events (→ COM/Methodical etc.)

Usage:
    python3 tools/tm_attribution.py tick_log_cb_20260619_082925.json
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tick_log")
    args = ap.parse_args()

    d = json.loads(Path(args.tick_log).read_text(encoding="utf-8"))
    ticks = d.get("ticks") or []

    # Build per-unit (tick, tm, tn, s_spd) timeline
    timelines: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
    for t in ticks:
        if "units" not in t:
            continue
        tk = t.get("tick", 0)
        for u in t["units"]:
            if u.get("s") not in ("p", "e"):
                continue
            uid = u.get("id")
            tm = u.get("tm")
            tn = u.get("tn", 0)
            spd = u.get("s_spd", 0)
            if tm is not None and spd:
                timelines[uid].append((tk, tm, tn, spd))

    # For each unit, find runs where tn is constant (no acts) and
    # compute TM delta per tick delta = empirical rate.
    print(f"Analyzing {len(timelines)} units")
    print()
    for uid, series in sorted(timelines.items()):
        if len(series) < 5:
            continue
        # SPD is constant per unit
        spd = series[0][3]
        # Walk pairs where tn stayed the same
        rates = []
        for i in range(len(series) - 1):
            tk1, tm1, tn1, _ = series[i]
            tk2, tm2, tn2, _ = series[i + 1]
            if tn1 != tn2:
                continue  # an action occurred — skip
            dt = tk2 - tk1
            dTM = tm2 - tm1
            if dt <= 0 or dTM <= 0:
                continue
            rate = dTM / (dt * spd)  # this should equal StaminaByTick
            rates.append(rate)
        if not rates:
            print(f"  unit {uid} SPD {spd}: no clean between-act samples")
            continue
        mean = sum(rates) / len(rates)
        # variance
        var = sum((r - mean) ** 2 for r in rates) / len(rates)
        sd = var ** 0.5
        side = "BOSS" if uid == 5 else f"hero{uid}"
        print(f"  {side:8s} SPD {spd:4d}: {len(rates):4d} samples, "
              f"rate = {mean:.4f} +/- {sd:.4f}  "
              f"(vs gameplay 0.07: {mean/0.07*100:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
