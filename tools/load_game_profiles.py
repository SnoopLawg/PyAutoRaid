"""
Load game-accurate hero skill profiles from hero_profiles_game.json.

Replaces the manually-coded SKILL_DATA and SKILL_EFFECTS dicts in cb_sim.py
with data extracted directly from the live game via BepInEx mod API.

Source: hero_profiles_game.json (137 heroes, exact game data)
Secondary: skills_db.json (for book cooldown reductions)
"""

import json
import re
from pathlib import Path

# StatusEffectTypeId -> sim debuff/buff name
SE_TO_SIM = {
    80: "poison_5pct",
    81: "poison_2pct",
    470: "hp_burn",
    151: "def_down",
    152: "def_down_30",
    131: "dec_atk",
    132: "dec_atk_25",
    350: "weaken",
    351: "weaken_15",
    500: "poison_sensitivity",
    501: "poison_sensitivity_50",
    50: "counterattack",
    60: "block_damage",
    100: "block_debuffs",
    310: "ally_protect",
    311: "ally_protect_25",
    320: "unkillable",
    121: "atk_up",
    122: "atk_up_25",
    141: "inc_def",
    142: "inc_def_30",
    161: "inc_spd",
    171: "dec_spd",
    90: "cont_heal_75",
    91: "cont_heal_15",
    460: "leech",
    511: "strengthen",
    510: "strengthen_15",
    360: "block_revive",
    10: "stun",
    20: "freeze",
}

# Which SE types are team buffs (applied to allies) vs debuffs (applied to enemies)
BUFF_SES = {
    "counterattack", "block_damage", "block_debuffs", "ally_protect",
    "ally_protect_25", "unkillable", "atk_up", "atk_up_25", "inc_def",
    "inc_def_30", "inc_spd", "cont_heal_75", "cont_heal_15", "strengthen",
    "strengthen_15",
}

# SE types that go on the CB debuff bar
DEBUFF_SES = {
    "poison_5pct", "poison_2pct", "hp_burn", "def_down", "def_down_30",
    "dec_atk", "dec_atk_25", "weaken", "weaken_15", "poison_sensitivity",
    "poison_sensitivity_50", "leech", "dec_spd", "block_revive",
    "stun", "freeze",
}


def _eff(effect_type, **params):
    """Helper to build effect dicts matching cb_sim's expected format."""
    return {"effect_type": effect_type, "params": params}


def _get_book_cd_reductions(skills_db_path):
    """Get cooldown reductions from skill books (level_bonuses type=3)."""
    reductions = {}  # {skill_type_id: total_cd_reduction}
    try:
        with open(skills_db_path) as f:
            db = json.load(f)
        for name, skills in db.items():
            if isinstance(skills, list):
                for sk in skills:
                    sid = sk.get('skill_type_id', 0)
                    cd_red = sum(1 for b in sk.get('level_bonuses', []) if b.get('type') == 3)
                    if cd_red > 0:
                        reductions[sid] = cd_red
    except Exception:
        pass
    return reductions


def load_profiles():
    """
    Load hero_profiles_game.json and produce SKILL_DATA, SKILL_EFFECTS, and
    PASSIVE_DATA dicts compatible with cb_sim.py.

    Returns: (skill_data, skill_effects, passive_data)
    """
    base = Path(__file__).parent.parent
    profiles_path = base / "hero_profiles_game.json"
    skills_db_path = base / "skills_db.json"

    with open(profiles_path) as f:
        profiles = json.load(f)

    # Get book CD reductions
    cd_reductions = _get_book_cd_reductions(skills_db_path)

    skill_data = {}    # {hero_name: {"A1": {...}, "A2": {...}, "A3": {...}}}
    skill_effects = {} # {hero_name: {"A1": [...], "A2": [...], "A3": [...]}}
    passive_data = {}  # {hero_name: {flag: value, ...}}

    for name, hero in profiles.items():
        skills = hero.get('skills', [])

        # Separate skills by type
        a1_skills = [s for s in skills if s.get('type') == 'A1']
        active_skills = sorted(
            [s for s in skills if s.get('type') == 'active'],
            key=lambda s: s.get('cooldown', 99)
        )
        passive_skills = [s for s in skills if s.get('type') == 'passive']

        # Assign labels: A1, A2, A3
        labeled = {}
        if a1_skills:
            labeled['A1'] = a1_skills[0]
        if len(active_skills) >= 1:
            labeled['A2'] = active_skills[0]
        if len(active_skills) >= 2:
            labeled['A3'] = active_skills[1]
        # Some heroes have 3+ active skills — take the 3rd as A4 (rare, usually ignore)

        hero_sd = {}
        hero_eff = {}

        for label, sk in labeled.items():
            sid = sk.get('id', 0)
            base_cd = sk.get('cooldown', 0)
            booked_cd = base_cd - cd_reductions.get(sid, 0)
            if booked_cd < 0:
                booked_cd = 0

            # Extract damage info
            mult = sk.get('mult', 0)
            stat = sk.get('stat', 'ATK')
            hits = sk.get('hits', 1)

            # For multi-damage skills, sum multipliers
            dmg_effects = [e for e in sk.get('effects', []) if e.get('tag') == 'damage']
            extra_dmg = [e for e in sk.get('effects', []) if e.get('tag') == 'extra_damage']

            # Fix hit count: use max of count field on damage or number of damage effects
            actual_hits = max(
                sk.get('hits', 1),
                max((e.get('count', 1) for e in dmg_effects), default=1),
                len(dmg_effects)
            )
            hits = actual_hits

            if len(dmg_effects) > 1 and mult > 0:
                # Multiple damage effects = multi-hit (e.g., Ninja A2: 3x 2*ATK)
                total_mult = 0
                for d in dmg_effects:
                    f = d.get('formula', '')
                    if '*ATK' in f:
                        try: total_mult += float(f.split('*ATK')[0])
                        except: pass
                    elif '*DEF' in f:
                        try: total_mult += float(f.split('*DEF')[0])
                        except: pass
                    elif '*HP' in f:
                        try: total_mult += float(f.split('*HP')[0])
                        except: pass
                if total_mult > 0:
                    mult = total_mult
            # Add extra damage
            for ed in extra_dmg:
                f = ed.get('formula', '')
                if '*ATK' in f:
                    try: mult += float(f.split('*ATK')[0])
                    except: pass
                elif '*DEF' in f:
                    try: mult += float(f.split('*DEF')[0])
                    except: pass

            # Extract team buffs and self TM fill
            team_buffs = []
            team_tm_fill = 0.0
            self_tm_fill = 0.0
            grants_extra_turn = False
            ignore_def_pct = 0.0

            effects_list = []

            for eff in sk.get('effects', []):
                kind = eff.get('kind', 0)
                count = eff.get('count', 1)
                formula = eff.get('formula', '')
                ses = eff.get('status_effects', [])

                # Buff placement (kind=4000) — team buffs
                if kind == 4000:
                    for se in ses:
                        se_type = se.get('type', 0)
                        se_name = SE_TO_SIM.get(se_type)
                        dur = se.get('duration', 0)
                        if se_name and se_name in BUFF_SES and dur > 0:
                            team_buffs.append((se_name, dur))

                # Debuff placement (kind=5000)
                elif kind == 5000:
                    for se in ses:
                        se_type = se.get('type', 0)
                        se_name = SE_TO_SIM.get(se_type)
                        dur = se.get('duration', 0)
                        chance = se.get('chance', 100) / 100.0
                        if se_name and se_name in DEBUFF_SES and dur > 0:
                            for _ in range(count):
                                effects_list.append(_eff("debuff",
                                    debuff=se_name, duration=dur, chance=chance))

                # TM boost (kind=4001)
                elif kind == 4001 and formula:
                    if "MAX_STAMINA" in formula:
                        m = re.match(r'([\d.]+)\*MAX_STAMINA', formula)
                        if m:
                            val = float(m.group(1))
                            if label == 'A1':
                                self_tm_fill = val
                            else:
                                team_tm_fill = val

                # Extra turn (kind=4007)
                elif kind == 4007:
                    grants_extra_turn = True

                # Extend debuffs (kind=5008)
                elif kind == 5008:
                    per_hit = (actual_hits > 1)
                    effects_list.append(_eff("extend_debuffs", turns=1, per_hit=per_hit))

                # Extend buffs (kind=4011)
                elif kind == 4011:
                    effects_list.append(_eff("extend_buffs", turns=1))

                # Activate poisons (kind=9002)
                elif kind == 9002:
                    effects_list.append(_eff("activate_poisons"))

                # Detonate poisons (kind=5018)
                elif kind == 5018:
                    effects_list.append(_eff("detonate_poisons"))

                # Ally attack (kind=4006)
                elif kind == 4006:
                    effects_list.append(_eff("ally_attack", count=count or 3))

                # Ignore DEF modifier (kind=7001)
                elif kind == 7001 and formula:
                    m = re.match(r'-([\d.]+)', formula)
                    if m:
                        ignore_def_pct = float(m.group(1))

                # TM reduce (kind=5001) — not modeled for CB (immune)
                # Cleanse (kind=4010) — relevant for passive only
                # Strip buff (kind=5003) — not relevant for CB
                # Reduce CD (kind=4009) — handle per hero if needed
                # Heal (kind=1000) — handled in passive detection

            sd_entry = {
                "mult": mult,
                "stat": stat,
                "hits": hits,
                "cd": booked_cd,
                "team_buffs": team_buffs,
                "team_tm_fill": team_tm_fill,
                "self_tm_fill": self_tm_fill,
                "grants_extra_turn": grants_extra_turn,
            }
            if ignore_def_pct > 0:
                sd_entry["ignore_def"] = ignore_def_pct

            hero_sd[label] = sd_entry
            hero_eff[label] = effects_list

        if hero_sd:
            skill_data[name] = hero_sd
        if hero_eff:
            skill_effects[name] = hero_eff

        # Process passives
        p_data = {}
        for sk in passive_skills:
            for eff in sk.get('effects', []):
                kind = eff.get('kind', 0)
                formula = eff.get('formula', '')
                ses = eff.get('status_effects', [])

                # Passive ally protect (kind=4018 or kind=4010 passive)
                if kind == 4018 or kind == 4010:
                    p_data['ally_protect'] = True

                # Passive damage reduction (kind=7004 with -X*DMG_MUL)
                if kind == 7004 and formula:
                    m = re.match(r'^-([\d.]+)\*DMG_MUL', formula)
                    if m:
                        val = float(m.group(1))
                        p_data['dmg_reduction'] = max(p_data.get('dmg_reduction', 0), val)
                    # Sicia burn scaling: DMG_MUL*(0.03*burn_count)
                    m2 = re.search(r'DMG_MUL\*\(([\d.]+)\*.*AoEContinuousDamage', formula)
                    if m2:
                        p_data['burn_dmg_reduction'] = float(m2.group(1))
                    # Corvis poison scaling
                    m3 = re.search(r'-([\d.]+)\*DMG_MUL\).*ContinuousDamage', formula)
                    if m3:
                        p_data['poison_dmg_reduction_per'] = float(m3.group(1))

                # Extra turns passive (kind=7017)
                if kind == 7017:
                    p_data['extra_turns'] = True

                # Passive buff extension (kind=4012)
                if kind == 4012:
                    p_data['buff_extension'] = True

                # Passive stat scaling (kind=4013)
                if kind == 4013 and formula:
                    # Ninja: B_ATK*0.2*producerComboCounterOnBosses
                    m_atk = re.search(r'B_ATK\*([\d.]+)\*producerComboCounterOnBosses', formula)
                    if m_atk:
                        p_data['combo_atk_pct'] = float(m_atk.group(1))
                    m_crd = re.search(r'B_CRD\*([\d.]+)\*producerComboCounterOnBosses', formula)
                    if m_crd:
                        p_data['combo_cd_pct'] = float(m_crd.group(1))
                    # Sicia: 3*(burn_count)
                    if 'AoEContinuousDamage' in formula and not formula.startswith('-') and not formula.startswith('DMG_MUL'):
                        m6 = re.match(r'([\d.]+)\*', formula)
                        if m6:
                            p_data['burn_stat_pct'] = float(m6.group(1)) / 100

                # Passive counterattack (kind=4012)
                if kind == 4012:
                    p_data['passive_counterattack'] = True

                # Cleanse passive (kind=4010 on passive)
                if kind == 4010:
                    p_data['cleanse'] = True

                # Passive trigger (kind=9006) — Ninja's TM passive
                if kind == 9006:
                    p_data['passive_trigger'] = True

                # Geomancer-style reflect damage (kind=4017)
                if kind == 4017:
                    p_data['reflect_damage'] = True
                    if formula:
                        m_reflect = re.search(r'([\d.]+)\*TRG_HP', formula)
                        if m_reflect:
                            p_data['reflect_pct'] = float(m_reflect.group(1))

                # Passive debuff placement (OB passive places poisons)
                if kind == 5000:
                    for se in ses:
                        se_type = se.get('type', 0)
                        se_name = SE_TO_SIM.get(se_type)
                        dur = se.get('duration', 0)
                        if se_name in DEBUFF_SES:
                            p_data.setdefault('passive_debuffs', []).append(
                                {'debuff': se_name, 'duration': dur})

            # A1 heal detection
            for eff in sk.get('effects', []):
                kind = eff.get('kind', 0)
                formula = eff.get('formula', '')
                # Passive heal on dealt damage
                if kind == 1000 and 'DEALT_DMG' in formula:
                    m = re.match(r'([\d.]+)\*DEALT_DMG', formula)
                    if m:
                        p_data['self_heal_pct'] = float(m.group(1))
                if kind == 1000 and 'TRG_HP' in formula:
                    m = re.match(r'([\d.]+)\*TRG_HP', formula)
                    if m:
                        p_data['target_heal_pct'] = float(m.group(1))

        # Also check A1 for self-heal
        if 'A1' in labeled:
            for eff in labeled['A1'].get('effects', []):
                kind = eff.get('kind', 0)
                formula = eff.get('formula', '')
                if kind == 1000 and 'DEALT_DMG' in formula:
                    m = re.match(r'([\d.]+)\*DEALT_DMG', formula)
                    if m:
                        p_data['a1_self_heal_pct'] = float(m.group(1))
                if kind == 1000 and 'TRG_HP' in formula:
                    m = re.match(r'([\d.]+)\*TRG_HP', formula)
                    if m:
                        p_data['a1_target_heal_pct'] = float(m.group(1))

        if p_data:
            passive_data[name] = p_data

    return skill_data, skill_effects, passive_data


if __name__ == "__main__":
    sd, se, pd = load_profiles()
    print(f"Loaded {len(sd)} heroes with skills")
    print(f"Loaded {len(se)} heroes with effects")
    print(f"Loaded {len(pd)} heroes with passives")

    # Print a few examples
    for name in ["Sicia Flametongue", "Maneater", "Ninja", "Occult Brawler", "Skullcrusher"]:
        if name in sd:
            print(f"\n=== {name} ===")
            for label, s in sd[name].items():
                print(f"  {label}: mult={s['mult']:.1f}x{s['stat']} hits={s['hits']} "
                      f"CD={s['cd']} buffs={s['team_buffs']} "
                      f"extra_turn={s.get('grants_extra_turn',False)}")
            if name in se:
                for label, effs in se[name].items():
                    for e in effs:
                        print(f"  {label} effect: {e['effect_type']} {e['params']}")
            if name in pd:
                print(f"  Passive: {pd[name]}")
