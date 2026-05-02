"""Damage analysis v2 — designed for the post-fix capture.

Uses the new fields the mod now captures per damage event:
- p_elem / t_elem: producer/target element (1=Magic 2=Force 3=Spirit 4=Void)
- p_eff / t_eff: list of active StatusEffectTypeIds at hit time
- hit: HitType enum string (Normal/Crushing/Critical/Glancing)
- kind_id: EffectKindId int (6000=Damage, 5000=Poison apply, etc.)
- skill: SkillTypeId

Stratifies by hit type AND element pair so the DEF mitigation
coefficient solve isn't confounded by affinity bonuses.

Usage:
    python3 tools/analyze_damage_v2.py <tick_log.json>
    python3 tools/analyze_damage_v2.py --latest
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

ELEM_NAME = {1: "Magic", 2: "Force", 3: "Spirit", 4: "Void"}
HIT_BONUS = {"Normal": 1.0, "Crushing": 1.3, "Glancing": 0.7}  # crit handled per-hero CD


def relation(p_elem: int, t_elem: int) -> str:
    """Magic→Spirit advantage, Spirit→Force, Force→Magic. Void = neutral."""
    if p_elem == 4 or t_elem == 4:
        return "Neutral"
    cycle = {1: 3, 3: 2, 2: 1}  # winner -> loser (Magic beats Spirit, etc.)
    if cycle.get(p_elem) == t_elem:
        return "Advantage"
    if cycle.get(t_elem) == p_elem:
        return "Disadvantage"
    return "Neutral"


def affinity_dmg_mult(rel: str) -> float:
    return {"Neutral": 1.0, "Advantage": 1.0, "Disadvantage": 0.8}[rel]


def load_events(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [t for t in raw.get("ticks", []) if isinstance(t, dict) and t.get("kind") == "damage"]


def field_coverage(events: list[dict]) -> None:
    n = len(events)
    print(f"=== {n} damage events ===\n")
    fields = ("p_atk", "p_cd", "p_cr", "p_elem", "p_typeid", "p_eff",
              "t_def", "t_hp", "t_hp_max", "t_elem", "t_typeid", "t_eff",
              "calc_raw", "calc", "mul", "def_mod",
              "hit", "kind_id", "skill", "crit", "blocked")
    print("Field coverage:")
    for f in fields:
        c = sum(1 for e in events if f in e and e[f] not in (None, -1, ""))
        if c:
            print(f"  {f:10s}: {c}/{n} ({100*c/n:.0f}%)")
    print()
    # Boss element
    boss_elems = Counter(e.get("t_elem") for e in events if e.get("target") == 5)
    if boss_elems:
        print(f"Boss element this battle: {dict(boss_elems)} → "
              f"{ELEM_NAME.get(max(boss_elems, key=boss_elems.get), '?')}")
    print()


def hit_type_check(events: list[dict]) -> None:
    """Per hit type: ratio of post-hit-type damage to pre-hit-type."""
    print("=== Hit-type multiplier observed ===\n")
    # We don't have pre-hit-type damage directly, but for crit events with
    # known CD, we can solve: calc_raw * (1+CD) = post-crit pre-DEF.
    # For Crushing: calc_raw * 1.3
    # For Glancing: calc_raw * 0.7
    # Since `mul` (=MultiplierValuePositive) is the DamageContext-level
    # value AFTER hit-type modifier and BEFORE DEF, we compute:
    #     mul / calc_raw   should == hit_type_mult
    print(f"  {'Hit':<10s} {'n':>4s} {'median mul/raw':>16s} {'mean':>10s}")
    by_hit = {}
    for e in events:
        h = e.get("hit")
        if not h or e.get("blocked"):
            continue
        raw = e.get("calc_raw", 0)
        mul = e.get("mul", 0)
        if raw <= 0 or mul <= 0:
            continue
        ratio = mul / raw
        by_hit.setdefault(h, []).append(ratio)
    for h in sorted(by_hit, key=lambda x: -len(by_hit[x])):
        ratios = by_hit[h]
        med = statistics.median(ratios)
        avg = statistics.mean(ratios)
        print(f"  {h:<10s} {len(ratios):>4d} {med:>16.4f} {avg:>10.4f}")
    print()


def def_mitigation(events: list[dict]) -> None:
    """Empirical DEF mitigation factors stratified by element relation
    so affinity advantage doesn't confound the result."""
    print("=== DEF mitigation factor by (target DEF, attacker→target affinity) ===\n")
    on_boss = [e for e in events
               if e.get("target") == 5
               and not e.get("blocked")
               and e.get("kind_id") == 6000  # Damage events only
               and e.get("mul", 0) > 0
               and e.get("calc", 0) > 0
               and e.get("hit") == "Normal"]  # exclude crit / crush
    print(f"  Normal-hit Damage events on boss: {len(on_boss)}")
    if not on_boss:
        return
    # Group by (t_def, relation)
    groups = {}
    for e in on_boss:
        rel = relation(e.get("p_elem", 0), e.get("t_elem", 0))
        key = (e["t_def"], rel)
        groups.setdefault(key, []).append(e["calc"] / e["mul"])
    print(f"\n  {'t_def':>6s} {'rel':<14s} {'n':>4s} {'median':>9s} {'mean':>9s} {'min':>9s} {'max':>9s}")
    for (deff, rel), vals in sorted(groups.items()):
        med = statistics.median(vals)
        avg = statistics.mean(vals)
        print(f"  {deff:>6d} {rel:<14s} {len(vals):>4d} "
              f"{med:>9.4f} {avg:>9.4f} {min(vals):>9.4f} {max(vals):>9.4f}")
    print()
    # If we have multiple t_def values at same relation, fit a formula.
    by_rel = {}
    for (deff, rel), vals in groups.items():
        by_rel.setdefault(rel, {})[deff] = statistics.median(vals)
    for rel, factor_by_def in by_rel.items():
        if len(factor_by_def) < 2:
            continue
        print(f"  Trying formulas for {rel}:")
        # candidate 1: factor = C / (C + DEF)
        Cs = [(d, f, d * f / (1 - f)) for d, f in factor_by_def.items()]
        for d, f, C in Cs:
            print(f"    DEF={d}: factor={f:.4f}, C={C:.2f}")
        if all(abs(C - Cs[0][2]) / Cs[0][2] < 0.05 for _, _, C in Cs):
            avg_C = sum(C for _, _, C in Cs) / len(Cs)
            print(f"    ✅ formula: factor = {avg_C:.0f} / ({avg_C:.0f} + DEF)")


def boss_skills_observed(events: list[dict]) -> None:
    """Which boss skills hit which heroes, with what damage?"""
    print("=== Boss attacks on heroes ===\n")
    boss_attacks = [e for e in events
                    if e.get("producer") == 5
                    and e.get("kind_id") == 6000
                    and e.get("calc", 0) > 0]
    by_skill = {}
    for e in boss_attacks:
        skid = e.get("skill", 0)
        by_skill.setdefault(skid, []).append(e)
    for skid, evs in sorted(by_skill.items(), key=lambda kv: -len(kv[1])):
        damages = [e["calc"] for e in evs]
        print(f"  skill {skid}: n={len(evs)}, dmg median={statistics.median(damages):,.0f} "
              f"min={min(damages):,.0f} max={max(damages):,.0f}")
    print()


def per_hero_summary(events: list[dict]) -> None:
    """Per attacker hero: total damage on boss + crit rate."""
    print("=== Per-hero damage on boss ===\n")
    on_boss = [e for e in events if e.get("target") == 5 and not e.get("blocked")
               and e.get("kind_id") in (6000,)]
    by_hero = {}
    for e in on_boss:
        atk = e.get("p_atk", 0)
        if atk == 0:
            continue
        by_hero.setdefault(atk, []).append(e)
    print(f"  {'p_atk':>6s} {'p_elem':<8s} {'p_cd/1k':>8s} {'p_cr/1k':>8s} {'n':>4s} {'total dmg':>14s} {'crit %':>7s}")
    for atk, evs in sorted(by_hero.items()):
        total = sum(e.get("calc", 0) for e in evs)
        crits = sum(1 for e in evs if e.get("crit"))
        elem = next((e.get("p_elem") for e in evs if e.get("p_elem")), 0)
        cd = next((e.get("p_cd") for e in evs if e.get("p_cd") not in (None, -1)), 0)
        cr = next((e.get("p_cr") for e in evs if e.get("p_cr") not in (None, -1)), 0)
        crit_pct = (crits / len(evs) * 100) if evs else 0
        print(f"  {atk:>6} {ELEM_NAME.get(elem, '?'):<8s} "
              f"{cd:>8d} {cr:>8d} {len(evs):>4d} {total:>14,d} {crit_pct:>6.1f}%")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?")
    ap.add_argument("--latest", action="store_true")
    args = ap.parse_args()

    if args.latest:
        cands = sorted(glob.glob(str(PROJECT_ROOT / "tick_log_cb_*.json")),
                       key=os.path.getmtime, reverse=True)
        if not cands:
            print("no tick logs found", file=sys.stderr)
            return 1
        path = Path(cands[0])
    elif args.path:
        path = Path(args.path)
    else:
        ap.error("provide path or --latest")

    print(f"Loading {path.name}\n")
    events = load_events(path)
    if not events:
        print("no damage events", file=sys.stderr)
        return 1

    field_coverage(events)
    per_hero_summary(events)
    hit_type_check(events)
    def_mitigation(events)
    boss_skills_observed(events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
