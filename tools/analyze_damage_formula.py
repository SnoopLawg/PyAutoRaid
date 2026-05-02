"""Back-solve the game's damage formula from a tick log.

The mod's damage hook captures these fields per event:
- p_atk:    attacker's in-battle ATK
- p_cd:     attacker's CritDamage % (× 100)
- p_cr:     attacker's CritChance % (× 100)
- t_def:    target's in-battle DEF
- t_hp_max: target's MAX HP
- calc_raw: pre-mitigation damage (MultiplierValuePositive)
- calc:     post-mitigation damage (ActualValue)
- def_mod:  resolved defence modifier (post-DEFDown / Weaken / IgnoreDef)
- mul:      multiplier value used in the calc
- hit:      "Normal" / "Crushing" / "Critical" / "Glancing"

Goal: find the constant K in:
    DEF_FACTOR = ATK / (ATK + DEF * K)
    calc = calc_raw * DEF_FACTOR

Different community sources cite K = 600, 350, 1100, or "level × C".
We solve K empirically across all events.

Usage:
    python3 tools/analyze_damage_formula.py tick_log_cb_<timestamp>.json
    python3 tools/analyze_damage_formula.py --latest    # auto-pick newest
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_ticks(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("ticks") or []


def damage_events(ticks: list[dict]) -> list[dict]:
    return [t for t in ticks if isinstance(t, dict) and t.get("kind") == "damage"]


def event_summary(events: list[dict]) -> None:
    print(f"=== {len(events)} damage events ===\n")
    if not events:
        return

    # Field coverage
    fields = ("p_atk", "p_cd", "p_cr", "t_def", "t_hp_max", "t_hp",
              "calc_raw", "calc", "def_mod", "mul", "hit", "kind_id",
              "skill", "crit", "blocked", "evaded")
    print("Field coverage:")
    for f in fields:
        n = sum(1 for e in events if f in e and e[f] not in (None, -1))
        if n:
            print(f"  {f:10s}: {n}/{len(events)}")

    # Hit-type distribution
    hits = Counter(e.get("hit") for e in events if e.get("hit"))
    print(f"\nHit type distribution: {dict(hits)}")

    # Skill distribution
    sks = Counter(e.get("skill") for e in events if e.get("skill"))
    print(f"Top skills (by id): {dict(sks.most_common(8))}")


def back_solve_def_coef(events: list[dict]) -> None:
    """Empirical DEF mitigation factor by target DEF.

    Strategy: for capped procs (mul ∈ {75000, 93750, 50000} on the
    boss), the pre-DEF damage is fixed by the cap. The ratio
    `calc / mul` then directly reveals the DEF mitigation factor for
    that DEF value, independent of attacker ATK.

    Once we have factor(DEF) for several DEF values, we can fit any
    candidate formula:
        factor = ATK / (ATK + DEF * K)   (community standard)
        factor = LEVEL² / (LEVEL² + DEF * K)
        factor = 1 / (1 + DEF * K)
    """
    print("\n=== DEF mitigation factor by target DEF ===\n")
    on_boss_unblocked = [e for e in events
                         if e.get("target") == 5 and not e.get("blocked")
                         and e.get("mul", 0) > 0 and e.get("calc", 0) > 0]
    if not on_boss_unblocked:
        print("  (no unblocked attacks on the boss)")
        return

    # Group by (mul, t_def). The mul=cap-value events give clean
    # signal because their pre-DEF damage is fixed across all attackers.
    cap_buckets: dict[tuple[int, int], list[int]] = {}
    for e in on_boss_unblocked:
        mul = e["mul"]
        deff = e["t_def"]
        if mul in (75000, 93750, 50000, 250000):
            cap_buckets.setdefault((mul, deff), []).append(e["calc"])

    print(f"  cap-proc events grouped by (mul, t_def):\n")
    print(f"  {'mul':>7s} {'t_def':>6s} {'n':>4s} {'calc unique values':<60s} {'factor (calc/mul)':>20s}")
    print(f"  {'-'*7} {'-'*6} {'-'*4} {'-'*60} {'-'*20}")
    for (mul, deff), calcs in sorted(cap_buckets.items()):
        unique = sorted(set(calcs))
        # The "factor" we want is the median calc / mul of NON-CRIT hits,
        # which present as the smallest unique calc value (no crit boost).
        min_calc = unique[0]
        factor = min_calc / mul
        print(f"  {mul:>7d} {deff:>6d} {len(calcs):>4d} {str(unique[:4]):<60s} {factor:>20.4f}")

    # If we have multiple DEF values, fit a few candidate formulas.
    # Use min(calcs) per (mul, t_def) bucket as the no-buff/no-crit damage.
    factor_by_def: dict[int, float] = {}
    for (mul, deff), calcs in cap_buckets.items():
        f = min(calcs) / mul
        # Average across mul-values for the same DEF (should agree).
        factor_by_def.setdefault(deff, [])
        factor_by_def[deff].append(f)
    factor_by_def = {d: sum(fs) / len(fs) for d, fs in factor_by_def.items()}
    print(f"\n  Aggregate factor by DEF: {factor_by_def}\n")

    if len(factor_by_def) < 2:
        print("  (need >=2 different DEF values to fit a formula)")
        return

    # Candidate formula 1: factor = C / (C + DEF) where C is a per-level constant
    print(f"  Candidate: factor = C / (C + DEF)")
    Cs = []
    for deff, f in factor_by_def.items():
        # f = C / (C + DEF) → C = DEF * f / (1 - f)
        C = deff * f / (1 - f)
        Cs.append((deff, f, C))
        print(f"    DEF={deff}: C = {C:.2f}")

    if len(Cs) >= 2 and abs(Cs[0][2] - Cs[1][2]) / Cs[0][2] < 0.05:
        avg_C = sum(c for _, _, c in Cs) / len(Cs)
        print(f"    ✅ C ≈ {avg_C:.0f} (consistent across DEF values)")
        print(f"    Predicted factor at DEF=4878 (sim's old back-fit): "
              f"{avg_C / (avg_C + 4878):.4f}")
    else:
        print(f"    ❌ C varies — formula isn't C/(C+DEF)")

    # Try formula 2: factor = (LEVEL × C) / (LEVEL × C + DEF), assume level=60
    print(f"\n  Candidate: factor = (60 × C) / (60 × C + DEF)")
    for deff, f in factor_by_def.items():
        # f * (60C + DEF) = 60C → 60C(1-f) = f*DEF → C = f*DEF / (60*(1-f))
        C = f * deff / (60 * (1 - f))
        print(f"    DEF={deff}: C = {C:.4f}")

    # Old-school Brave Frontier-like formula
    print(f"\n  Candidate: factor = 1 - DEF / (DEF + base) — same as #1, just framing")

    return


def show_def_down_evidence(events: list[dict]) -> None:
    """Boss DEF appears in two values across a battle: native + DEF Down 60%.
    Confirm the multiplicative structure: 1520 × 0.4 = 608."""
    print("\n=== Boss DEF observations ===\n")
    boss_defs = sorted(set(e["t_def"] for e in events
                           if e.get("target") == 5 and e.get("t_def", 0) > 0))
    print(f"  Distinct boss DEF values seen: {boss_defs}")
    if len(boss_defs) >= 2:
        a, b = boss_defs[0], boss_defs[-1]
        ratio = a / b
        print(f"  Ratio {a}/{b} = {ratio:.4f}")
        if abs(ratio - 0.4) < 0.01:
            print(f"  ✅ matches DEF Down 60% (×0.4)")
        elif abs(ratio - 0.7) < 0.02:
            print(f"  ✅ matches DEF Down 30% (×0.7)")



def back_solve_hit_type_bonus(events: list[dict]) -> None:
    """If calc_raw is pre-hit-type and calc is post-hit-type-and-DEF,
    we might need to factor out the hit-type multiplier first.

    Crit:     ratio_after_crit = (1 + CD/100) — depends on attacker CD
    Crush:    ratio_after_crush = 1.30
    Glance:   ratio_after_glance = 0.70
    Normal:   ratio = 1.0
    """
    print("\n=== Hit-type multiplier check ===\n")
    bands = {"Normal": [], "Crushing": [], "Critical": [], "Glancing": []}
    for e in events:
        hit = e.get("hit")
        if hit not in bands:
            continue
        if e.get("blocked") or e.get("evaded"):
            continue
        raw = e.get("calc_raw", -1)
        post = e.get("calc", -1)
        if raw <= 0 or post <= 0:
            continue
        bands[hit].append(post / raw)

    for hit, ratios in bands.items():
        if not ratios:
            continue
        med = statistics.median(ratios)
        print(f"  {hit:<10s} n={len(ratios):>4d}  median post/pre = {med:.4f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="Path to a tick_log_cb_*.json")
    ap.add_argument("--latest", action="store_true",
                    help="Auto-pick the most recent tick_log_cb_*.json")
    args = ap.parse_args()

    if args.latest:
        candidates = sorted(glob.glob(str(PROJECT_ROOT / "tick_log_cb_*.json")),
                            key=os.path.getmtime, reverse=True)
        if not candidates:
            print("No tick_log_cb_*.json found in project root.", file=sys.stderr)
            return 1
        path = Path(candidates[0])
    elif args.path:
        path = Path(args.path)
    else:
        ap.error("provide a tick log path or use --latest")

    print(f"Loading {path.name}\n")
    ticks = load_ticks(path)
    events = damage_events(ticks)
    event_summary(events)
    back_solve_hit_type_bonus(events)
    show_def_down_evidence(events)
    back_solve_def_coef(events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
