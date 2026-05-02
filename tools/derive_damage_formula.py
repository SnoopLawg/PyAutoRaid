"""Derive game-truth damage formulas from captured tick_log damage events.

Stops the back-solving game. The mod's `_tickLog` records every damage
event with the GAME's exact intermediate values (p_atk, p_cd, p_cr,
t_def, calc_raw, calc, def_mod, mul, hit type, affinity). This tool
reads them and back-derives the formulas Plarium uses, so the sim can
stop guessing constants and compute them deterministically from
known stats.

Outputs analysis to stdout. Run on any `tick_log_cb_*.json` file.

Usage:
    python3 tools/derive_damage_formula.py tick_log_cb_20260501_221440.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, stdev


def load_events(path: str) -> list[dict]:
    """Read damage events from a tick log."""
    with open(path) as f:
        d = json.load(f)
    ticks = d.get("ticks", [])
    return [t for t in ticks if isinstance(t, dict) and t.get("kind") == "damage"]


def analyze_def_mitigation(events: list[dict]) -> None:
    """Derive the DEF mitigation formula from captured (calc_raw, calc, t_def) tuples.

    Game formula (Plarium): damage = calc_raw × C / (C + DEF)
    where C is a level-based constant. For level 60 the typical fit
    is C ≈ 200 ± a few. Equivalent: damage = raw / (1 + DEF/C).

    For each event, compute:
        mitigation_factor = calc / calc_raw
        implied_C = DEF * m / (1 - m)

    Filter to clean events: same hit type, no def_mod (no DEF Down/Weaken)
    so the captured DEF matches the formula's input.
    """
    by_hit_defmod = defaultdict(list)
    for e in events:
        cr = e.get("calc_raw", 0)
        ca = e.get("calc", 0)
        td = e.get("t_def", -1)
        absorbed = e.get("calc_absorbed", 0) or 0
        def_mod = e.get("def_mod", 0)
        if cr <= 0 or ca <= 0 or td <= 0:
            continue
        if absorbed > 0:
            continue
        m_factor = ca / cr
        if m_factor <= 0 or m_factor >= 1:
            continue
        implied_C = td * m_factor / (1 - m_factor)
        hit = e.get("hit") or "_unspecified"
        by_hit_defmod[(hit, def_mod)].append((td, m_factor, implied_C))

    print("=== DEF mitigation analysis ===")
    print(f"  formula: damage = calc_raw * C / (C + DEF)  -->  C = DEF * m / (1 - m)")
    print()
    for (hit, dm), samples in sorted(by_hit_defmod.items()):
        if len(samples) < 5:
            continue
        Cs = [s[2] for s in samples]
        Cs.sort()
        # Trimmed mean — drop top/bottom 10% to remove outliers
        n = len(Cs)
        trim = max(1, n // 10)
        trimmed = Cs[trim:n - trim] if n > 2 * trim else Cs
        print(f"  hit={hit:<10s} def_mod={dm:>5}  n={n:>3}  "
              f"C=mean {mean(Cs):.0f}, median {median(Cs):.0f}, "
              f"trimmed-mean {mean(trimmed):.0f}, "
              f"stdev {stdev(Cs):.0f}")


def analyze_boss_atk(events: list[dict]) -> None:
    """Compare captured boss ATK (p_atk) to sim's CB_ATK constant.

    The boss's ATK is captured per-event including Gathering Fury
    scaling. Earliest events (low fury) reveal the base ATK; later
    events show the cumulative fury bonus.
    """
    boss_events = [e for e in events if e.get("producer") == 5
                   and e.get("p_atk", -1) > 0]
    if not boss_events:
        print("=== Boss ATK ===")
        print("  no boss-source damage events with p_atk")
        return
    by_tick = defaultdict(list)
    for e in boss_events:
        by_tick[e.get("tick", 0)].append(e["p_atk"])
    ticks_sorted = sorted(by_tick.keys())
    earliest = mean(by_tick[ticks_sorted[0]])
    latest = mean(by_tick[ticks_sorted[-1]])
    all_atks = [a for samples in by_tick.values() for a in samples]
    print("=== Boss ATK (p_atk) ===")
    print(f"  events: {len(boss_events)}, ticks: {len(ticks_sorted)}")
    print(f"  earliest (tick {ticks_sorted[0]}): {earliest:.0f}")
    print(f"  latest (tick {ticks_sorted[-1]}): {latest:.0f}")
    print(f"  range: {min(all_atks)}–{max(all_atks)}")
    print(f"  sim's CB_ATK constant should match the EARLIEST value (pre-fury).")


def analyze_hit_type_factors(events: list[dict]) -> None:
    """Derive crit/crush/glance damage factors from captured events.

    For events with the same producer/skill but different hit types,
    the calc_raw ratio reveals the hit-type multiplier.
    """
    # Group by skill, find tuples of {hit: damage_for_this_hit}
    by_skill_atk = defaultdict(list)
    for e in events:
        sk = e.get("skill_type_id") or e.get("skill_id") or 0
        atk = e.get("p_atk", 0)
        cr = e.get("calc_raw", 0)
        hit = e.get("hit", "Normal")
        if sk and atk and cr > 0:
            by_skill_atk[(sk, atk)].append((hit, cr))
    # For each (skill, atk) group, find mean calc_raw per hit type
    by_hit = defaultdict(list)
    for (sk, atk), pairs in by_skill_atk.items():
        for hit, cr in pairs:
            by_hit[hit].append(cr / atk)
    print("=== Hit-type damage factors (calc_raw / p_atk) ===")
    print("  Each hit type's average ratio reveals the skill multiplier × hit factor.")
    for hit, ratios in sorted(by_hit.items()):
        if len(ratios) < 5:
            continue
        print(f"  hit={hit}  n={len(ratios)}  mean ratio={mean(ratios):.4f}, "
              f"median={median(ratios):.4f}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tick_log", help="Path to tick_log_cb_*.json")
    args = ap.parse_args()
    path = Path(args.tick_log)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 1
    events = load_events(str(path))
    print(f"# Loaded {len(events)} damage events from {path.name}\n")
    if not events:
        print("no damage events found")
        return 0
    analyze_boss_atk(events)
    print()
    analyze_def_mitigation(events)
    print()
    analyze_hit_type_factors(events)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
