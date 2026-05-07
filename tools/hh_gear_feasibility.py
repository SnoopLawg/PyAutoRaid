"""HH-team gear feasibility: per-hero, can the user's vault hit the target stats?

Reads:
  - all_artifacts_local.json (from /all-artifacts)  — the user's vault
  - HH-derived target stats per hero (passed in via args or inline)

Computes per-stat MAX achievable assuming this hero hogs all the best gear in
the vault, then compares to target. This is the upper bound — it ignores
team-wide gear contention. If the upper bound doesn't meet target, the build
is infeasible regardless of how you allocate.

Usage:
    python3 tools/hh_gear_feasibility.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Stat IDs: 1=HP 2=ATK 3=DEF 4=SPD 5=RES 6=ACC 7=CR 8=CD
# Slot kinds: 1=Helmet 2=Chest 3=Gloves 4=Boots 5=Weapon 6=Shield 7=Ring 8=Amulet 9=Banner

# Set bonuses (CB-relevant; not exhaustive)
SET_BONUS_SPD_PCT = 0.30  # 4pc Speed
SET_BONUS_HP_PCT  = 0.15  # 4pc HP (or 2pc HP+2pc HP)


def _load_vault(path: Path) -> list[dict]:
    return json.loads(path.read_text()).get("artifacts", [])


def max_primary(arts: list[dict], stat_id: int, slots: set[int] | None = None) -> float:
    best = 0.0
    for a in arts:
        if slots and a.get("kind") not in slots:
            continue
        p = a.get("primary") or {}
        if p.get("stat") == stat_id:
            best = max(best, p.get("value", 0))
    return best


def top_substats(arts: list[dict], stat_id: int, n: int,
                 flat: bool | None = None) -> list[float]:
    vals = []
    for a in arts:
        for s in (a.get("substats") or []):
            if s.get("stat") != stat_id:
                continue
            if flat is not None and s.get("flat", True) != flat:
                continue
            vals.append(s.get("value", 0))
    vals.sort(reverse=True)
    return vals[:n]


def achievable_spd(arts: list[dict], base: int) -> tuple[int, dict]:
    set_b = base * SET_BONUS_SPD_PCT
    boots = max_primary(arts, 4, slots={4})
    subs = top_substats(arts, 4, 5)  # 5 substats (assumes Boots primary, others have substats)
    total = base + set_b + boots + sum(subs)
    return int(total), {"base": base, "set_bonus": int(set_b),
                        "boots_primary": boots, "top_subs": subs}


def achievable_hp(arts: list[dict], base: int) -> tuple[int, dict]:
    # 4pc HP set: +15%; assume single 4pc.
    set_b = base * SET_BONUS_HP_PCT
    chest_pct = max_primary(arts, 1, slots={2}) / 100  # HP% on chest
    chest_b = base * chest_pct
    banner = max_primary(arts, 1, slots={9})
    accessory_hp = max_primary(arts, 1, slots={7, 8})  # ring or amulet
    pct_subs = top_substats(arts, 1, 4, flat=False)
    flat_subs = top_substats(arts, 1, 2, flat=True)
    total = (base + set_b + chest_b + banner + accessory_hp
             + base * (sum(pct_subs) / 100) + sum(flat_subs))
    return int(total), {"base": base, "set": int(set_b), "chest_pct": int(chest_b),
                        "banner": int(banner), "acc_hp": int(accessory_hp),
                        "pct_subs": pct_subs, "flat_subs": flat_subs}


def achievable_def(arts: list[dict], base: int) -> tuple[int, dict]:
    set_b = base * SET_BONUS_HP_PCT
    chest_pct = max_primary(arts, 3, slots={2}) / 100
    chest_b = base * chest_pct
    banner = max_primary(arts, 3, slots={9})
    accessory = max_primary(arts, 3, slots={7, 8})
    pct_subs = top_substats(arts, 3, 4, flat=False)
    total = base + set_b + chest_b + banner + accessory + base * (sum(pct_subs) / 100)
    return int(total), {"chest": int(chest_b), "banner": int(banner)}


def achievable_cd(arts: list[dict], base_pct: float = 0.50) -> tuple[int, dict]:
    val = base_pct * 100  # 50%
    val += max_primary(arts, 8, slots={3, 8})  # gloves (CD%) or amulet (rare)
    cd_subs = top_substats(arts, 8, 5)
    val += sum(cd_subs)
    return int(val), {"base": 50, "primary": int(max_primary(arts, 8, slots={3, 8})),
                      "subs": cd_subs}


def achievable_cr(arts: list[dict], base_pct: float = 0.15) -> tuple[int, dict]:
    val = base_pct * 100
    val += max_primary(arts, 7, slots={3})  # CR% gloves
    val += 12  # 2pc CR set assumed
    cr_subs = top_substats(arts, 7, 5)
    val += sum(cr_subs)
    return int(val), {"primary": int(max_primary(arts, 7, slots={3})), "subs": cr_subs}


def achievable_acc(arts: list[dict]) -> tuple[int, dict]:
    val = 0
    val += max_primary(arts, 6, slots={2})  # chest
    val += max_primary(arts, 6, slots={9})  # banner (Crystal banner)
    acc_subs = top_substats(arts, 6, 5)
    val += sum(acc_subs)
    return int(val), {"primary_chest": int(max_primary(arts, 6, slots={2})),
                      "primary_banner": int(max_primary(arts, 6, slots={9})),
                      "subs": acc_subs}


def achievable_atk(arts: list[dict], base: int) -> tuple[int, dict]:
    set_b = base * 0.30  # 4pc Offense (or 2pc ATK)
    weapon = max_primary(arts, 2, slots={5})  # flat ATK
    chest_pct = max_primary(arts, 2, slots={2}) / 100
    glove_pct = max_primary(arts, 2, slots={3}) / 100
    banner_pct = max_primary(arts, 2, slots={9}) / 100
    accessory = max_primary(arts, 2, slots={7, 8})
    pct_subs = top_substats(arts, 2, 4, flat=False)
    flat_subs = top_substats(arts, 2, 2, flat=True)
    total = (base + set_b + weapon + accessory + base * (chest_pct + glove_pct + banner_pct)
             + base * (sum(pct_subs) / 100) + sum(flat_subs))
    return int(total), {"weapon_flat": int(weapon)}


def achievable_res(arts: list[dict]) -> tuple[int, dict]:
    val = max_primary(arts, 5, slots={2})  # chest RES
    val += max_primary(arts, 5, slots={9})  # banner
    val += sum(top_substats(arts, 5, 5))
    return int(val), {}


# Hero base stats at 6*60 (+ classic-arena bonus). Pulled from /hero-computed-stats.
HERO_BASE = {
    'Demytha': dict(SPD=102, HP=15915, ATK=1058, DEF=1014, CR=0.15, CD=0.50),
    'Heiress': dict(SPD=102, HP=14955, ATK=826,  DEF=1190, CR=0.15, CD=0.50),
    'Ninja':   dict(SPD=100, HP=15705, ATK=1255, DEF=826,  CR=0.15, CD=0.50),
    'Seeker':  dict(SPD=103, HP=15225, ATK=826,  DEF=1124, CR=0.15, CD=0.50),
    'Gnut':    dict(SPD=99,  HP=15705, ATK=815,  DEF=1267, CR=0.15, CD=0.50),
}

# HH-derived target for the mid-tier reliable variation (~159M average, 8 battles)
TARGETS = {
    'Demytha': dict(SPD=316, HP=72783, DEF=4938, CR=43, CD=202, RES=175, ACC=141),
    'Heiress': dict(SPD=284, HP=41898, DEF=2669, CR=105, CD=204, RES=206, ACC=140),
    'Ninja':   dict(SPD=163, HP=44905, DEF=1715, CR=105, CD=272, RES=151, ACC=412, ATK=6324),
    'Seeker':  dict(SPD=210, HP=51566, DEF=4259, CR=109, CD=267, RES=289, ACC=336, ATK=3328),
    'Gnut':    dict(SPD=219, HP=50778, DEF=3851, CR=100, CD=287, RES=207, ACC=501, ATK=2510),
}

# Game-truth caps & gear-priority weights, based on actual mechanics.
# - ACC: UNM boss RES = 250. Anything above is wasted on the boss.
# - CR:  game caps at 100% — substats above that don't proc.
# - SPD: strict requirement (defines the turn-order tune).
# - HP/DEF/RES: STRICT only on teams that take damage. UK-chain teams (with
#   Demytha/Mikage Unkillable, or Wixwell shield-block) are immune to HP loss
#   while the chain holds — so survivability stats become "comfort buffer".
# - CD:  damage multiplier; nice but not gating. Treat as soft.
GAME_CAPS = {
    'ACC': 250,    # UNM boss RES
    'CR':  100,    # crit chance hard cap
}

# CB UNM teams that rely on Unkillable / shield-block chains. For these,
# HP/DEF/RES are "soft" — failing them isn't a blocker.
UK_RELIANT_HEROES = {
    'Demytha',     # A2 Unkillable
    'Mithrala Lifebane',  # A3 Inevitable Death (UK + remove debuffs)
    'Lady Mikage', # similar
    'Vault Keeper Wixwell',  # Shield + Block Damage
    'Underpriest Brogni',    # shield chain
    'Ma\'Shalled',  # team protect (block damage)
}

STAT_PRIORITY = {
    'SPD': 'STRICT',   # always must hit (turn-order)
    'ACC': 'CAPPED',   # at GAME_CAPS['ACC']
    'CR':  'CAPPED',   # at GAME_CAPS['CR']
    'CD':  'SOFT',     # nice-to-have damage
    'ATK': 'SOFT',     # damage scaling
    'HP':  'SOFT_IF_UK',   # strict only if NOT UK-team
    'DEF': 'SOFT_IF_UK',
    'RES': 'SOFT_IF_UK',
}


def is_uk_team(hero_names: list[str]) -> bool:
    """Team is 'UK-reliant' if any member provides UK / shield-block chain."""
    return any(h in UK_RELIANT_HEROES for h in hero_names)


def effective_target(stat: str, target_value: int) -> int:
    """Apply game caps. ACC > 250 → 250 (UNM); CR > 100 → 100."""
    cap = GAME_CAPS.get(stat)
    if cap is not None:
        return min(target_value, cap)
    return target_value


def priority_label(stat: str, uk_team: bool) -> str:
    """How strict is this stat for this team? STRICT/CAPPED/SOFT."""
    p = STAT_PRIORITY.get(stat, 'SOFT')
    if p == 'SOFT_IF_UK':
        return 'SOFT' if uk_team else 'STRICT'
    return p


def evaluate(arts: list[dict]):
    team_heroes = list(TARGETS.keys())
    uk_team = is_uk_team(team_heroes)
    print(f"Team type: {'UK-RELIANT (survivability is comfort buffer)' if uk_team else 'no UK chain — survivability strict'}\n")
    print(f"{'hero':10}  {'stat':4}  {'target':>6}  {'eff_target':>10}  {'max':>6}  {'priority':>8}  result")
    print('-' * 80)
    blockers = []  # STRICT or CAPPED stats that fail
    for hero, t in TARGETS.items():
        base = HERO_BASE[hero]
        for stat in ['SPD', 'HP', 'DEF', 'CD', 'CR', 'RES', 'ACC', 'ATK']:
            if stat not in t:
                continue
            target = t[stat]
            eff = effective_target(stat, target)
            pri = priority_label(stat, uk_team)
            if stat == 'SPD':
                m, _ = achievable_spd(arts, base['SPD'])
            elif stat == 'HP':
                m, _ = achievable_hp(arts, base['HP'])
            elif stat == 'DEF':
                m, _ = achievable_def(arts, base['DEF'])
            elif stat == 'CD':
                m, _ = achievable_cd(arts, base['CD'])
            elif stat == 'CR':
                m, _ = achievable_cr(arts, base['CR'])
            elif stat == 'RES':
                m, _ = achievable_res(arts)
            elif stat == 'ACC':
                m, _ = achievable_acc(arts)
            elif stat == 'ATK':
                m, _ = achievable_atk(arts, base['ATK'])
            ok = m >= eff
            if ok:
                verdict = 'OK'
            elif pri in ('STRICT', 'CAPPED'):
                verdict = f'BLOCKER ({eff-m:+d})'
                blockers.append((hero, stat, eff, m))
            else:
                verdict = f'soft-miss ({eff-m:+d})'
            note = ''
            if eff != target:
                note = f' (capped from {target})'
            print(f"  {hero:10}  {stat:4}  {target:>6}  {eff:>10}{note}  {m:>6}  {pri:>8}  {verdict}")
        print()
    print('=' * 80)
    if not blockers:
        print("VERDICT: feasible — no STRICT/CAPPED stat fails. Soft misses are damage trade-offs.")
    else:
        print(f"VERDICT: NOT feasible — {len(blockers)} hard blockers:")
        for h, s, t, m in blockers:
            print(f"  {h} {s}: target {t}, max {m} (gap {t-m:+d})")


def main():
    vault_path = PROJECT_ROOT / "all_artifacts_local.json"
    if not vault_path.exists():
        print(f"vault not found at {vault_path}; run: "
              f"curl -s 'http://localhost:6790/all-artifacts?limit=20000' -o all_artifacts_local.json"
              f"\nNOTE: must use ?limit=20000 — endpoint defaults to 200 artifacts which masks 90%+ of vault",
              file=sys.stderr)
        return 2
    arts = _load_vault(vault_path)
    print(f"vault: {len(arts)} artifacts\n")
    print("Targets: Heiress + Seeker + Ninja + Demytha + Gnut "
          "(mid-tier reliable variation, ~159M avg)\n")
    evaluate(arts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
