#!/usr/bin/env python3
"""Derive per-tick DoT caps from ground-truth tick-log captures.

The mod's BattleHook_DamageChange hook (deployed 2026-04-24) emits
per-hit `dealt` / `calc` damage values via DamageResult.ActualValue.
We can use a captured battle's tick-log to derive what the game
actually applies as caps on DoT damage (poison, HP burn, mastery
procs) — replacing the hardcoded constants in `raid_data.py`.

Heuristic: clusters of hits at the same value indicate a per-tick
cap was applied. The mode of each producer's "DoT-shaped" hits gives
the cap for that DoT type.

Usage:
    python3 tools/calibrate_dot_caps.py cb_magic_final.json
    python3 tools/calibrate_dot_caps.py /path/to/tick-log.json --write

The `--write` flag updates `data/observed_dot_caps.json` which
`raid_data.py` loads at import time.

Limitations:
- Producer ID → hero name mapping requires the team composition; we
  infer from the 5 hero IDs (0-4) and ask the caller to map them.
- Mastery procs (Warmaster) aren't distinguishable from HP burn ticks
  by value alone (both at 75K cap on the team tested) — we treat them
  as the same cap until we observe distinct values.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median, mode


def load_tick_log(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    ticks = data.get("ticks", [])
    return [t for t in ticks if isinstance(t, dict) and t.get("kind") == "damage"]


def cluster_caps(damage_events: list[dict], tolerance: int = 200) -> dict[int, int]:
    """For each producer, find the most-common cluster of hits ≥ 1000 dealt.

    Returns {producer_id: observed_cap}. Hits below 1K are skill-damage
    fragments, not DoT/mastery caps.
    """
    out = {}
    by_producer: dict[int, list[int]] = {}
    for e in damage_events:
        if e.get("target") != 5:  # only damage TO boss
            continue
        d = e.get("dealt", 0)
        if d < 1000:
            continue
        by_producer.setdefault(e.get("producer", -1), []).append(d)

    for pid, hits in by_producer.items():
        # Bucket into 1K-wide buckets, find the mode bucket — that's the
        # most-frequent cluster, almost certainly the per-tick DoT cap.
        buckets = Counter((h // 1000) * 1000 for h in hits)
        if not buckets:
            continue
        top_bucket, top_count = buckets.most_common(1)[0]
        # Compute the median value WITHIN that bucket — that's the cap.
        in_bucket = [h for h in hits if top_bucket <= h < top_bucket + 1000]
        out[pid] = int(median(in_bucket)) if in_bucket else top_bucket
    return out


def derive_named_caps(damage_events: list[dict],
                      producer_to_hero_role: dict[int, str]) -> dict[str, int]:
    """Map producer cluster caps to debuff-type names.

    `producer_to_hero_role` maps producer_id → role like
    "poison_source" / "hp_burn_source". Multiple producers can map to
    the same role (e.g. two poison heroes); we take the median cap.
    """
    pid_caps = cluster_caps(damage_events)
    by_role: dict[str, list[int]] = {}
    for pid, cap in pid_caps.items():
        role = producer_to_hero_role.get(pid)
        if role:
            by_role.setdefault(role, []).append(cap)
    return {role: int(median(caps)) for role, caps in by_role.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tick_log", help="path to a captured /tick-log JSON")
    ap.add_argument("--write", action="store_true",
                    help="overwrite data/observed_dot_caps.json with derived caps")
    ap.add_argument("--poison-producer", type=int, default=4,
                    help="producer ID of the poison-source hero (default 4 = Venomage)")
    ap.add_argument("--burn-producer", type=int, default=2,
                    help="producer ID of the HP-burn-source hero (default 2 = Ninja)")
    args = ap.parse_args()

    events = load_tick_log(Path(args.tick_log))
    print(f"Loaded {len(events)} damage events")

    pid_caps = cluster_caps(events)
    print("Per-producer dominant cluster cap (likely DoT cap):")
    for pid, cap in sorted(pid_caps.items()):
        # Count hits within ±100 of the cap
        hits = [e["dealt"] for e in events
                if e.get("producer") == pid and e.get("target") == 5]
        cluster_hits = sum(1 for h in hits if abs(h - cap) < 200)
        print(f"  producer {pid}: cap = {cap:,}  ({cluster_hits} of {len(hits)} hits cluster here)")

    poison_cap = pid_caps.get(args.poison_producer)
    burn_cap = pid_caps.get(args.burn_producer)
    if poison_cap is None or burn_cap is None:
        print("\nWARNING: could not identify both poison + burn caps. "
              "Pass --poison-producer / --burn-producer manually.", file=sys.stderr)
        return

    # Producers WITHOUT a DoT source (don't place poison/burn) but WITH
    # offense masteries cluster their dominant hits at the Warmaster cap
    # (4% × CB phase soft-HP — typically ~67.6K on UNM). Use the median
    # of those non-DoT producers as the WM/GS cap.
    dot_producers = {args.poison_producer, args.burn_producer}
    wm_caps = [cap for pid, cap in pid_caps.items() if pid not in dot_producers]
    if wm_caps:
        from statistics import median as _med
        wm_cap = int(_med(wm_caps))
    else:
        wm_cap = burn_cap

    derived = {
        "poison_5pct": poison_cap,
        "poison_2_5pct": poison_cap // 2,
        "hp_burn": burn_cap,
        "warmaster": wm_cap,
        "giant_slayer": wm_cap,
    }
    print(f"\nDerived caps: {derived}")

    if args.write:
        out_path = Path(__file__).parent.parent / "data" / "observed_dot_caps.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(derived, indent=2), encoding="utf-8")
        print(f"\nWrote {out_path}")
        print("(raid_data.py loads this on import — restart any running sim)")


if __name__ == "__main__":
    main()
