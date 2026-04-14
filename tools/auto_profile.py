#!/usr/bin/env python3
"""
Auto-generate CB HeroProfile objects from skills_db.json.

Reads the full game-extracted skill database and creates a profile for every hero,
detecting: damage scaling, poisons, HP burn, DEF down, weaken, dec_atk, counterattack,
ally_attack, unkillable, block_damage, and passives.

Usage:
    # As module:
    from auto_profile import auto_generate_profiles
    profiles = auto_generate_profiles()

    # CLI: print all profiles
    python3 tools/auto_profile.py
    python3 tools/auto_profile.py --hero Venus
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from cb_optimizer import HeroProfile
from status_effect_map import STATUS_EFFECT_MAP

# Status effect type IDs relevant to CB
SE_POISON_5PCT = 80
SE_POISON_25PCT = 81
SE_HP_BURN = 470
SE_DEF_DOWN_60 = 151
SE_DEF_DOWN_30 = 150
SE_WEAKEN_25 = 350
SE_WEAKEN_15 = 351
SE_DEC_ATK_50 = 131
SE_DEC_ATK_25 = 130
SE_COUNTERATTACK = 50
SE_UNKILLABLE = 320
SE_BLOCK_DAMAGE = 60
SE_BLOCK_DEBUFFS = 100
SE_ALLY_PROTECT = 310
SE_POISON_SENSITIVITY = 500
SE_LEECH = 460
SE_STRENGTHEN = 511
SE_INC_ATK = 121
SE_INC_DEF = 141
SE_INC_SPD = 161
SE_CONT_HEAL = 90
SE_CONT_HEAL_15 = 91

# Effect kinds
KIND_DAMAGE = 6000
KIND_DEBUFF = 5000
KIND_BUFF = 4000
KIND_HEAL = 1000
KIND_TM_MANIP = 5001
KIND_ALLY_ATTACK = 4006
KIND_COUNTERATTACK = 4007
KIND_PASSIVE = 4009
KIND_ALLY_PROTECT = 4010
KIND_PASSIVE_DMG_REDUCTION = 7004
KIND_PASSIVE_EXTRA = 4017
KIND_EXTEND_DEBUFFS = 5003


def parse_formula(formula):
    """Extract multiplier and stat from formula like '3.9*ATK' or '0.25*HP'."""
    if not formula:
        return 0, "ATK"
    formula = formula.strip()
    parts = formula.split("*")
    if len(parts) == 2:
        try:
            mult = float(parts[0])
        except ValueError:
            mult = 0
        stat = parts[1].strip()
        return mult, stat
    return 0, "ATK"


def auto_generate_profiles(skills_db_path=None, hero_profiles_path=None):
    """Generate HeroProfile for every hero in skills_db.json."""
    if skills_db_path is None:
        skills_db_path = PROJECT_ROOT / "skills_db.json"
    if hero_profiles_path is None:
        hero_profiles_path = PROJECT_ROOT / "hero_profiles_game.json"

    skills_db = json.loads(Path(skills_db_path).read_text())

    # Load game profiles for richer data where available
    game_profiles = {}
    if Path(hero_profiles_path).exists():
        game_profiles = json.loads(Path(hero_profiles_path).read_text())

    profiles = {}

    for hero_name, skill_list in skills_db.items():
        # Separate A1, actives, passives
        a1_skills = [s for s in skill_list if s.get("is_a1")]
        active_skills = [s for s in skill_list if not s.get("is_a1") and s.get("cooldown")]
        passive_skills = [s for s in skill_list if not s.get("is_a1") and not s.get("cooldown")]

        # A1 analysis
        a1_hits = 1
        a1_mult = 3.0
        a1_stat = "ATK"
        a1_poisons = 0
        a1_poison_chance = 0

        if a1_skills:
            a1 = a1_skills[0]
            for eff in a1.get("effects", []):
                if eff.get("kind") == KIND_DAMAGE:
                    mult, stat = parse_formula(eff.get("formula"))
                    if mult > 0:
                        a1_mult = mult
                        a1_stat = stat
                    a1_hits = max(a1_hits, eff.get("count", 1))
                for se in eff.get("status_effects", []):
                    if se.get("type") == SE_POISON_5PCT:
                        a1_poisons += eff.get("count", 1)
                        a1_poison_chance = se.get("chance", 100)

        # Active skills analysis
        poisons_per_turn = a1_poisons * (a1_poison_chance / 100)
        hp_burn_uptime = 0
        def_down = False
        weaken = False
        dec_atk = False
        inc_atk = False
        inc_def = False
        strengthen = False
        counterattack = False
        ally_attack = 0
        unkillable = False
        block_damage = False
        poison_sensitivity = False
        needs_acc = False
        breaks_speed_tune = False
        passive_dmg = 0
        has_ally_protect = False

        for sk in active_skills:
            cd = sk.get("cooldown", 4)
            booked_cd = cd
            # Apply book reductions
            for lb in sk.get("level_bonuses", []):
                if lb.get("type") == 3:
                    booked_cd -= 1
            booked_cd = max(booked_cd, 1)

            for eff in sk.get("effects", []):
                kind = eff.get("kind", 0)

                # Count poisons from active skills
                for se in eff.get("status_effects", []):
                    se_type = se.get("type", 0)
                    chance = se.get("chance", 100)
                    duration = se.get("duration", 2)
                    count = eff.get("count", 1)

                    if se_type == SE_POISON_5PCT:
                        # Poisons per turn = count * (chance/100) * (duration / booked_cd)
                        uptime = min(1.0, duration / booked_cd)
                        poisons_per_turn += count * (chance / 100) * uptime
                        needs_acc = True
                    elif se_type == SE_HP_BURN:
                        hp_burn_uptime = max(hp_burn_uptime, min(1.0, duration / booked_cd))
                        needs_acc = True
                    elif se_type == SE_DEF_DOWN_60:
                        def_down = True
                        needs_acc = True
                    elif se_type == SE_DEF_DOWN_30:
                        def_down = True  # treat 30% as def_down too
                        needs_acc = True
                    elif se_type in (SE_WEAKEN_25, SE_WEAKEN_15):
                        weaken = True
                        needs_acc = True
                    elif se_type in (SE_DEC_ATK_50, SE_DEC_ATK_25):
                        dec_atk = True
                        needs_acc = True
                    elif se_type == SE_COUNTERATTACK:
                        counterattack = True
                    elif se_type == SE_UNKILLABLE:
                        unkillable = True
                    elif se_type == SE_BLOCK_DAMAGE:
                        block_damage = True
                    elif se_type == SE_INC_ATK:
                        inc_atk = True
                    elif se_type == SE_INC_DEF:
                        inc_def = True
                    elif se_type in (SE_STRENGTHEN,):
                        strengthen = True
                    elif se_type == SE_POISON_SENSITIVITY:
                        poison_sensitivity = True
                        needs_acc = True
                    elif se_type == SE_LEECH:
                        needs_acc = True
                    elif se_type == SE_ALLY_PROTECT:
                        has_ally_protect = True

                # Ally attack
                if kind == KIND_ALLY_ATTACK:
                    ally_attack = max(ally_attack, eff.get("count", 1))

                # TM manipulation detection (breaks speed tunes)
                if kind == KIND_TM_MANIP:
                    formula = eff.get("formula", "")
                    if formula and "MAX_STAMINA" in formula:
                        mult, _ = parse_formula(formula.replace("MAX_STAMINA", "1"))
                        if mult > 0.1:  # >10% TM fill is disruptive
                            breaks_speed_tune = True

        # Passive analysis
        for sk in passive_skills:
            for eff in sk.get("effects", []):
                kind = eff.get("kind", 0)
                for se in eff.get("status_effects", []):
                    se_type = se.get("type", 0)
                    if se_type == SE_POISON_5PCT:
                        # Passive poison (like Occult Brawler)
                        poisons_per_turn += eff.get("count", 1) * (se.get("chance", 100) / 100)
                    elif se_type == SE_HP_BURN:
                        hp_burn_uptime = max(hp_burn_uptime, 0.5)
                    elif se_type == SE_COUNTERATTACK:
                        counterattack = True
                    elif se_type == SE_ALLY_PROTECT:
                        has_ally_protect = True

                if kind == KIND_PASSIVE_DMG_REDUCTION:
                    formula = eff.get("formula", "")
                    if "DMG_MUL" in formula or "TRG_HP" in formula:
                        passive_dmg = max(passive_dmg, 50000)  # Geomancer-class passive

        # Cap poisons to debuff bar reality (max ~7 slots for poisons)
        poisons_per_turn = min(poisons_per_turn, 5.0)

        # Build notes
        notes_parts = []
        if def_down and weaken:
            notes_parts.append("DD+WK")
        elif def_down:
            notes_parts.append("DD")
        elif weaken:
            notes_parts.append("WK")
        if poisons_per_turn > 0:
            notes_parts.append(f"Poi×{poisons_per_turn:.1f}")
        if hp_burn_uptime > 0:
            notes_parts.append(f"Burn {hp_burn_uptime:.0%}")
        if counterattack:
            notes_parts.append("CA")
        if ally_attack > 0:
            notes_parts.append(f"AA×{ally_attack}")
        if unkillable:
            notes_parts.append("UK")
        if block_damage:
            notes_parts.append("BD")
        if poison_sensitivity:
            notes_parts.append("PSens")

        profile = HeroProfile(
            hero_name,
            a1_hits=a1_hits,
            a1_mult=a1_mult,
            a1_stat=a1_stat,
            poisons_per_turn=poisons_per_turn,
            hp_burn_uptime=hp_burn_uptime,
            passive_dmg=passive_dmg,
            unkillable=unkillable,
            counterattack=counterattack,
            ally_attack=ally_attack,
            def_down=def_down,
            weaken=weaken,
            dec_atk=dec_atk,
            inc_atk=inc_atk,
            inc_def=inc_def,
            strengthen=strengthen,
            needs_acc=needs_acc,
            breaks_speed_tune=breaks_speed_tune,
            notes=", ".join(notes_parts) if notes_parts else None,
        )
        profiles[hero_name] = profile

    return profiles


def get_leader_skills(heroes_all_path=None):
    """Extract leader skill auras from heroes_all.json.
    Returns dict: hero_name -> {stat, amount, absolute, area}."""
    if heroes_all_path is None:
        heroes_all_path = PROJECT_ROOT / "heroes_all.json"

    data = json.loads(Path(heroes_all_path).read_text())
    leaders = {}
    for h in data.get("heroes", []):
        name = h.get("name", "")
        ls = h.get("leader_skills", [])
        if ls and name not in leaders:
            # Take first leader skill
            skill = ls[0]
            leaders[name] = {
                "stat": skill.get("stat", 0),
                "amount": skill.get("amount", 0),
                "absolute": skill.get("absolute", False),
                "area": skill.get("area", 0),
            }
    return leaders


# =============================================================================
# CLI
# =============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto-generate CB profiles from skills_db")
    parser.add_argument("--hero", help="Show profile for specific hero")
    parser.add_argument("--cb-relevant", action="store_true",
                        help="Only show heroes with CB-relevant abilities")
    args = parser.parse_args()

    profiles = auto_generate_profiles()
    leaders = get_leader_skills()

    if args.hero:
        p = profiles.get(args.hero)
        if not p:
            print(f"Hero '{args.hero}' not found in skills_db")
            return
        print(f"{args.hero}:")
        print(f"  A1: {p.a1_hits}×{p.a1_mult:.1f}×{p.a1_stat}")
        print(f"  Poisons/turn: {p.poisons_per_turn:.1f}")
        print(f"  HP Burn: {p.hp_burn_uptime:.0%}")
        print(f"  DEF Down: {p.def_down}, Weaken: {p.weaken}, Dec ATK: {p.dec_atk}")
        print(f"  UK: {p.unkillable}, CA: {p.counterattack}, AA: {p.ally_attack}")
        print(f"  Needs ACC: {p.needs_acc}, Breaks tune: {p.breaks_speed_tune}")
        print(f"  Notes: {p.notes}")
        ls = leaders.get(args.hero)
        if ls:
            stat_names = {1:'HP', 2:'ATK', 3:'DEF', 4:'SPD', 5:'RES', 6:'ACC', 7:'CR', 8:'CD'}
            sn = stat_names.get(ls['stat'], '?')
            flat = 'flat' if ls['absolute'] else '%'
            print(f"  Leader: +{ls['amount']}{flat} {sn}")
        return

    # Summary
    cb_heroes = []
    for name, p in sorted(profiles.items()):
        is_relevant = (p.poisons_per_turn > 0 or p.hp_burn_uptime > 0 or
                       p.def_down or p.weaken or p.unkillable or
                       p.counterattack or p.ally_attack > 0 or
                       p.dec_atk or p.passive_dmg > 0)
        if args.cb_relevant and not is_relevant:
            continue
        cb_heroes.append((name, p))

    print(f"{'Hero':25s} {'A1':15s} {'Poi':>5s} {'Burn':>5s} {'DD':>3s} {'WK':>3s} "
          f"{'DA':>3s} {'CA':>3s} {'AA':>3s} {'UK':>3s} {'Notes'}")
    print("-" * 100)
    for name, p in cb_heroes:
        a1_str = f"{p.a1_hits}×{p.a1_mult:.1f}×{p.a1_stat}"
        print(f"{name:25s} {a1_str:15s} {p.poisons_per_turn:>5.1f} "
              f"{p.hp_burn_uptime:>4.0%}  "
              f"{'Y' if p.def_down else '.':>2s} {'Y' if p.weaken else '.':>2s} "
              f"{'Y' if p.dec_atk else '.':>2s} {'Y' if p.counterattack else '.':>2s} "
              f"{p.ally_attack:>2d}  {'Y' if p.unkillable else '.':>2s} "
              f"{p.notes or ''}")

    print(f"\nTotal: {len(cb_heroes)} heroes")
    print(f"Leader skills: {len(leaders)} heroes")


if __name__ == "__main__":
    main()
