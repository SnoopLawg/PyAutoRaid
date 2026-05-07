"""Greedy gear optimizer for an HH-recommended team.

Takes a target team's per-hero stat targets (from HH /details data),
the user's full vault, and a "locked" hero set (e.g., CB team — gear
on those heroes is reserved). Picks the best available artifact for
each slot of each team hero to maximize SPD-first stat coverage.

This is NOT a global sim-in-the-loop optimizer like
tools/global_gear_solver.py — it's a per-hero greedy pass intended
for "what's my best assemble RIGHT NOW given fixed roster constraints"
rather than "find the global optimum across multiple stat tradeoffs".
Use the global solver for CB tunes; use this for one-shot Dragon /
Spider / Iron Twins gear-up sessions.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Stat IDs: 1=HP 2=ATK 3=DEF 4=SPD 5=RES 6=ACC 7=CR 8=CD
# Slots: 1=Helm 2=Chest 3=Glove 4=Boots 5=Weapon 6=Shield 7=Ring 8=Amulet 9=Banner
STAT = {1:'HP',2:'ATK',3:'DEF',4:'SPD',5:'RES',6:'ACC',7:'CR',8:'CD'}
SLOT = {1:'Helm',2:'Chest',3:'Glove',4:'Boots',5:'Weapon',6:'Shield',7:'Ring',8:'Amulet',9:'Banner'}

# Hero base stats at 6*60 — minimal set for compute
HERO_BASE = {
    'Teodor the Savant': dict(HP=20505, ATK=1090, DEF=1140, SPD=102),
    'Corvis the Corruptor': dict(HP=18420, ATK=1377, DEF=1003, SPD=104),
}


def hero_score(stats_total: dict, target: dict, weights: dict) -> float:
    """Weighted percent-of-target score. Stats over target are clamped (no benefit)."""
    score = 0.0
    for stat, t in target.items():
        if t <= 0: continue
        w = weights.get(stat, 1.0)
        cur = stats_total.get(stat, 0)
        # ACC > 250 wasteful, CR > 100 wasteful (game caps)
        if stat == 'ACC' and t > 250: t = 250
        if stat == 'CR' and t > 100: t = 100
        ratio = min(1.0, cur / t)
        score += w * ratio
    return score


def assemble_greedy(hero_name: str, target: dict, available: list[dict],
                    pri_weights: dict) -> tuple[dict, list[dict]]:
    """Pick the best one artifact per slot from `available`. Returns (totals, picks).

    Strategy: per slot, score every candidate by how much it advances priority stats,
    pick the highest-scoring one, remove it from the pool. Slot order: Boots first
    (SPD primary is critical), then Helm/Chest/Glove (substat-heavy), then Weapon/
    Shield (rigid primaries), then accessories (Ring/Amulet/Banner).
    """
    base = dict(HERO_BASE.get(hero_name, {}))
    base.setdefault('CR', 15)   # base 15% CR
    base.setdefault('CD', 50)   # base 50% CD
    base.setdefault('RES', 30)
    base.setdefault('ACC', 0)

    pool = list(available)
    picks = []
    totals = dict(base)

    def candidate_score(art: dict) -> float:
        """How much would this art advance us toward target? Sum primary + substats × weight."""
        s = 0.0
        p = art.get('primary') or {}
        if p.get('stat'):
            stat = STAT.get(p['stat'], '?')
            v = p.get('value', 0)
            w = pri_weights.get(stat, 1.0)
            tgt = target.get(stat, 0)
            if tgt > 0:
                s += w * min(1.0, v / max(1, tgt - totals.get(stat, 0))) * v
        for sub in (art.get('substats') or []):
            stat = STAT.get(sub.get('stat'), '?')
            w = pri_weights.get(stat, 0.5)
            v = sub.get('value', 0)
            tgt = target.get(stat, 0)
            if tgt > 0:
                # substat values are smaller; weight per-unit
                s += w * v
        return s

    # Slot priority order (higher impact first for SPD-focused tune)
    slot_order = [4, 9, 7, 8, 1, 2, 3, 5, 6]  # Boots, Banner, Ring, Amulet, Helm, Chest, Glove, Weapon, Shield
    for slot_id in slot_order:
        candidates = [a for a in pool if a.get('kind') == slot_id]
        if not candidates: continue
        candidates.sort(key=candidate_score, reverse=True)
        best = candidates[0]
        picks.append(best)
        pool.remove(best)
        # Update totals
        p = best.get('primary') or {}
        if p.get('stat'):
            stat = STAT.get(p['stat'], '?')
            v = p.get('value', 0)
            if p.get('flat', True):
                totals[stat] = totals.get(stat, 0) + v
            else:
                # %-based primary applied to BASE stat
                bv = base.get(stat, 0)
                totals[stat] = totals.get(stat, 0) + bv * v / 100
        for sub in (best.get('substats') or []):
            stat = STAT.get(sub.get('stat'), '?')
            v = sub.get('value', 0)
            if sub.get('flat', True):
                totals[stat] = totals.get(stat, 0) + v
            else:
                bv = base.get(stat, 0)
                totals[stat] = totals.get(stat, 0) + bv * v / 100

    return totals, picks


def main():
    arts_path = PROJECT_ROOT / 'all_artifacts_local.json'
    if not arts_path.exists():
        print(f"vault not found at {arts_path}", file=sys.stderr)
        return 2
    arts = json.loads(arts_path.read_text()).get('artifacts', [])

    # CB team hero instance IDs (lock their gear)
    CB_HERO_IDS = {15120, 18607, 2643, 13615, 5692}
    available = [a for a in arts if a.get('hero_id') not in CB_HERO_IDS]
    print(f"vault total: {len(arts)},  CB-locked: {len(arts) - len(available)},  available: {len(available)}\n")

    # Dragon Hard 10 targets (from HH top reliable variation: 1d4ded51 / 407 victories)
    TARGETS = {
        'Teodor the Savant': dict(HP=97310, ATK=2645, DEF=3684, SPD=292,
                                   CR=15, CD=86, RES=385, ACC=454),
        'Corvis the Corruptor': dict(HP=81771, ATK=2658, DEF=4776, SPD=272,
                                      CR=31, CD=145, RES=481, ACC=356),
    }
    # SPD-first weights for Dragon
    WEIGHTS = {'SPD': 5.0, 'ACC': 2.0, 'HP': 1.5, 'CD': 1.5, 'CR': 1.0,
                'DEF': 1.0, 'ATK': 1.5, 'RES': 0.5}

    pool = list(available)
    for hero_name, target in TARGETS.items():
        print(f"=== {hero_name} ===")
        print(f"  target: SPD={target['SPD']} ACC≤{min(target['ACC'],250)} HP={target['HP']} "
              f"DEF={target['DEF']} CR≤{min(target['CR'],100)}% CD={target['CD']}%")
        totals, picks = assemble_greedy(hero_name, target, pool, WEIGHTS)
        # Remove picks from pool so the next hero doesn't reuse
        for p in picks: pool.remove(p)

        print(f"  achieved: SPD={totals['SPD']:.0f} ACC={totals['ACC']:.0f} HP={totals['HP']:.0f} "
              f"DEF={totals['DEF']:.0f} CR={totals['CR']:.0f}% CD={totals['CD']:.0f}% "
              f"RES={totals['RES']:.0f} ATK={totals['ATK']:.0f}")
        print(f"  picks (one per slot):")
        for a in sorted(picks, key=lambda a: a.get('kind', 0)):
            slot = SLOT.get(a.get('kind'), '?')
            p = a.get('primary') or {}
            ps = STAT.get(p.get('stat'), '?')
            pv = p.get('value', 0)
            subs = ', '.join(f"{STAT.get(s.get('stat'),'?')}+{s.get('value',0):.0f}"
                              for s in (a.get('substats') or []))
            cur_owner = a.get('hero_id') or 'vault'
            print(f"    {slot:7}  art#{a.get('id'):>5}  {ps}+{pv:.0f}  rank {a.get('rank')}  "
                  f"sub:[{subs}]  current: {cur_owner}")

        # Gap report
        print(f"  GAPS (target vs achieved):")
        for stat in ['SPD', 'ACC', 'HP', 'CD', 'DEF']:
            t = target.get(stat, 0)
            if stat == 'ACC' and t > 250: t = 250
            if stat == 'CR' and t > 100: t = 100
            achieved = totals.get(stat, 0)
            gap = t - achieved
            verdict = '✓' if gap <= 0 else f'-{gap:.0f}'
            print(f"    {stat}: target {t}, achieved {achieved:.0f}  {verdict}")
        print()


if __name__ == "__main__":
    raise SystemExit(main())
