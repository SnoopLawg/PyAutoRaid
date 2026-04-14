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
    241: "inc_cr_30",
    261: "inc_cd_30",
    280: "shield",
    300: "revive_on_death",
    160: "inc_spd_15",
    70: "heal_reduction",
    71: "heal_reduction_50",
    481: "perfect_veil",
}

# Which SE types are team buffs (applied to allies) vs debuffs (applied to enemies)
BUFF_SES = {
    "counterattack", "block_damage", "block_debuffs", "ally_protect",
    "ally_protect_25", "unkillable", "atk_up", "atk_up_25", "inc_def",
    "inc_def_30", "inc_spd", "inc_spd_15", "cont_heal_75", "cont_heal_15", "strengthen",
    "strengthen_15", "inc_cr_30", "inc_cd_30", "shield", "revive_on_death",
}

# SE types that go on the CB debuff bar
DEBUFF_SES = {
    "poison_5pct", "poison_2pct", "hp_burn", "def_down", "def_down_30",
    "dec_atk", "dec_atk_25", "weaken", "weaken_15", "poison_sensitivity",
    "poison_sensitivity_50", "leech", "dec_spd", "block_revive",
    "stun", "freeze", "heal_reduction", "heal_reduction_50",
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
        # If more than 2 actives, prefer ones with damage effects over utility-only
        if len(active_skills) > 2:
            def has_damage(sk):
                return any(e.get('kind') == 6000 or e.get('tag') == 'damage' for e in sk.get('effects', []))
            dmg_skills = [s for s in active_skills if has_damage(s)]
            nodmg_skills = [s for s in active_skills if not has_damage(s)]
            # Take up to 2 damage skills (sorted by CD), then fill with non-damage
            active_skills = (dmg_skills[:2] + nodmg_skills)[:3]
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
            mult = sk.get('mult', 0) or 0
            stat = sk.get('stat', 'ATK') or 'ATK'
            hits = sk.get('hits', 1) or 1

            # If mult is 0/None, try to parse from damage effect formulas
            if mult == 0:
                for eff in sk.get('effects', []):
                    if eff.get('kind') == 6000 or eff.get('tag') == 'damage':
                        f = eff.get('formula', '')
                        if not f:
                            continue
                        # Parse various formula patterns:
                        #   "3.9*ATK" -> mult=3.9, stat=ATK
                        #   "DEF*1.5" -> mult=1.5, stat=DEF
                        #   "ATK" -> mult=1.0, stat=ATK
                        #   "0.2*HP" -> mult=0.2, stat=HP
                        #   "DEF*6" -> mult=6, stat=DEF
                        m = re.match(r'^([\d.]+)\*(ATK|DEF|HP)', f)
                        if m:
                            mult = float(m.group(1))
                            stat = m.group(2)
                            break
                        m = re.match(r'^(ATK|DEF|HP)\*([\d.]+)', f)
                        if m:
                            stat = m.group(1)
                            mult = float(m.group(2))
                            break
                        m = re.match(r'^(ATK|DEF|HP)$', f)
                        if m:
                            mult = 1.0
                            stat = m.group(1)
                            break
                        # HP-scaling: "0.2*HP" or "HP*0.2"
                        m = re.match(r'^([\d.]+)\*HP', f)
                        if m:
                            mult = float(m.group(1))
                            stat = 'HP'
                            break

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

                # HP Burn spread/activation (kind=5002) — exact mechanic unclear.
                # Used by 44 heroes. NOT necessarily "place HP Burn" — may be
                # "spread existing burn" or "activate burn damage". Needs real
                # game testing per hero before enabling. Skipped for now.
                # elif kind == 5002:
                #     effects_list.append(_eff("debuff", debuff="hp_burn", duration=2, chance=1.0))

                # Extend debuffs (kind=5008)
                # Per skill descriptions:
                #   Sicia A1 (57701): extends [HP Burn] only, per hit
                #   Teodor A3 (36003): extends [Poison] and [HP Burn]
                #   Others: extends all debuffs
                elif kind == 5008:
                    per_hit = (actual_hits > 1)
                    # Determine which debuffs to extend based on skill context
                    skill_id = sk.get('id', 0)
                    if skill_id == 57701:  # Sicia A1: only HP Burn
                        effects_list.append(_eff("extend_debuffs_hp_burn", turns=1, per_hit=per_hit))
                    elif skill_id == 36003:  # Teodor A3: poison + HP burn
                        effects_list.append(_eff("extend_debuffs_poison_burn", turns=1, per_hit=per_hit))
                    else:
                        effects_list.append(_eff("extend_debuffs", turns=1, per_hit=per_hit))

                # Extend buffs (kind=4011)
                elif kind == 4011:
                    effects_list.append(_eff("extend_buffs", turns=1))

                # Activate DoTs (kind=9002) — mechanic varies by hero/skill.
                # Verified from in-game skill descriptions:
                #   Ninja A2 (62002): "instantly activate any [HP Burn] debuffs" vs Bosses
                #   Sicia A2 (57702): "instantly activates one tick of [HP Burn] debuffs"
                #   Teodor A3 (36003): "instantly activates one tick of all [Poison] and [HP Burn]"
                #   Venomage A1 (62801): "activating up to two [Poison] debuffs"
                #   Artak A2 (78602): activates HP Burns
                elif kind == 9002:
                    skill_id = sk.get('id', 0)
                    # Ninja A2 (62002): "will instantly activate any [HP Burn] debuffs"
                    #   Description says once per skill use, not per hit. The game data
                    #   has 3x kind=9002 (one per hit) but the effect triggers once.
                    #   Only add on first occurrence to avoid triple-counting.
                    already_has = any(e.get('effect_type') == 'activate_hp_burns' for e in effects_list)
                    if skill_id == 62002 and not already_has:  # Ninja A2
                        effects_list.append(_eff("activate_hp_burns"))
                    elif skill_id == 57702:  # Sicia A2: activate HP Burns (1 tick)
                        effects_list.append(_eff("activate_hp_burns"))
                    elif skill_id == 78602:  # Artak A2: activate HP Burns
                        effects_list.append(_eff("activate_hp_burns"))
                    elif skill_id == 36003:  # Teodor A3: activate all DoTs (poison + burn)
                        effects_list.append(_eff("activate_dots"))
                    elif skill_id == 62801:  # Venomage A1: activate up to 2 Poisons per hit
                        effects_list.append(_eff("activate_poisons", max_count=2))
                    # Other heroes with 9002: skip (unknown mechanic)

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

        # =====================================================================
        # Per-hero fixes from verified skill descriptions.
        # These correct effects that the generic parser can't extract from
        # the game's effect kind/formula encoding.
        # Source: skill_descriptions.json (game-localized text via mod API)
        # =====================================================================

        # Ninja A3 (62003): vs Boss, ignores 50% DEF + reduces A2 CD by 1
        if name == "Ninja" and "A3" in hero_sd:
            hero_sd["A3"]["ignore_def"] = 0.5

        # OB A2 (33002): ignores 30% DEF when under debuffs (kind=7001 already captured)
        # (already handled by generic kind=7001 parser — no fix needed)

        # Venus A3 (35003): places HP Burn (was incorrectly getting extra_turn from A3 data)
        # The game data for Venus has skill 35005 as A3 which is wrong; real A3 is 35003
        if name == "Venus" and "A3" in hero_sd:
            hero_sd["A3"]["grants_extra_turn"] = False
            if not any(e.get('params', {}).get('debuff') == 'hp_burn' for e in hero_eff.get("A3", [])):
                hero_eff.setdefault("A3", []).append(_eff("debuff", debuff="hp_burn", duration=2, chance=1.0))

        # Fahrakin A3 (56603): places Inc CR 30% + Inc CD 30% on allies BEFORE ally attack
        if name == "Fahrakin the Fat" and "A3" in hero_sd:
            buffs = hero_sd["A3"].get("team_buffs", [])
            if not any(b[0] == "inc_cr_30" for b in buffs if isinstance(b, tuple)):
                hero_sd["A3"]["team_buffs"] = [("inc_cr_30", 3), ("inc_cd_30", 3)] + buffs

        # Cardiel A3 (57603): places Inc CR 30% + Inc CD 30% on allies BEFORE ally attack
        if name == "Cardiel" and "A3" in hero_sd:
            buffs = hero_sd["A3"].get("team_buffs", [])
            if not any(b[0] == "inc_cr_30" for b in buffs if isinstance(b, tuple)):
                hero_sd["A3"]["team_buffs"] = [("inc_cr_30", 2), ("inc_cd_30", 2)] + buffs

        # Teodor A2 (36002): places Poison Sensitivity (already captured via kind=5000+type=500)
        # Verify it's there:
        if name == "Teodor the Savant" and "A2" in hero_eff:
            has_psens = any(e.get('params', {}).get('debuff') == 'poison_sensitivity' for e in hero_eff["A2"])
            if not has_psens:
                hero_eff["A2"].append(_eff("debuff", debuff="poison_sensitivity", duration=2, chance=1.0))

        # Ma'Shalled A2 (9304): Inc SPD + Inc CD buffs on team
        if name == "Ma'Shalled" and "A2" in hero_sd:
            buffs = hero_sd["A2"].get("team_buffs", [])
            if not any(b[0] == "inc_cd_30" for b in buffs if isinstance(b, tuple)):
                buffs.append(("inc_cd_30", 2))
                hero_sd["A2"]["team_buffs"] = buffs

        # Ma'Shalled A2: also places True Fear + Leech on enemies
        if name == "Ma'Shalled" and "A2" in hero_eff:
            has_leech = any(e.get('params', {}).get('debuff') == 'leech' for e in hero_eff["A2"])
            if not has_leech:
                hero_eff["A2"].append(_eff("debuff", debuff="leech", duration=2, chance=1.0))

        # Venomage A3 (62803): places Heal Reduction (type=70) — enables passive dmg reduction
        if name == "Venomage" and "A3" in hero_eff:
            has_hr = any(e.get('params', {}).get('debuff') == 'heal_reduction' for e in hero_eff["A3"])
            if not has_hr:
                hero_eff["A3"].append(_eff("debuff", debuff="heal_reduction", duration=3, chance=1.0))

        # Sepulcher Sentinel A2 (38802): Inc DEF 60% + Block Debuffs on team
        if name == "Sepulcher Sentinel" and "A2" in hero_sd:
            buffs = hero_sd["A2"].get("team_buffs", [])
            if not any(b[0].startswith("inc_def") for b in buffs if isinstance(b, tuple)):
                hero_sd["A2"]["team_buffs"] = [("inc_def", 2), ("block_debuffs", 2)] + buffs

        # Drexthar Passive: HP Burn when attacked (passive debuff on attacker)
        # Already detected by passive processor via kind=5000+type=470

        # Artak A1 (78601): extends HP Burn duration (like Sicia A1)
        if name == "Artak" and "A1" in hero_eff:
            has_extend = any('extend' in e.get('effect_type', '') for e in hero_eff["A1"])
            if not has_extend:
                hero_eff["A1"].append(_eff("extend_debuffs_hp_burn", turns=1, per_hit=True))

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

    # =====================================================================
    # Auto-correction pass: use parsed skill descriptions to fix chances,
    # missing debuffs/buffs, ignore_def, and other effects that the generic
    # effect-kind parser can't extract from game data alone.
    # =====================================================================
    try:
        from desc_profiler import parse_all_descriptions
        desc_parsed = parse_all_descriptions()

        for hero_name in skill_data:
            dp = desc_parsed.get(hero_name, {})
            if not dp:
                continue

            for label in ["A1", "A2", "A3"]:
                p = dp.get(label)
                sd_entry = skill_data[hero_name].get(label)
                eff_list = skill_effects.get(hero_name, {}).get(label, [])
                if not p or not sd_entry:
                    continue

                # Fix debuff chances from descriptions (game data often has 100% when real is lower)
                for desc_db in p.get("debuffs", []):
                    if desc_db.get("on_self"):
                        continue
                    for eff in eff_list:
                        if (eff.get("effect_type") == "debuff" and
                            eff["params"].get("debuff", "").startswith(desc_db["type"].split("_")[0])):
                            # Update chance from description if different
                            if abs(eff["params"].get("chance", 1.0) - desc_db["chance"]) > 0.01:
                                eff["params"]["chance"] = desc_db["chance"]

                # Fix ignore_def from descriptions
                if p.get("ignore_def_pct", 0) > 0 and sd_entry.get("ignore_def", 0) == 0:
                    sd_entry["ignore_def"] = p["ignore_def_pct"]

                # Add missing buffs from descriptions
                for desc_buf in p.get("buffs", []):
                    if desc_buf.get("target") == "self":
                        continue
                    existing_buffs = sd_entry.get("team_buffs", [])
                    has = any(b[0].startswith(desc_buf["type"].split("_")[0])
                              for b in existing_buffs if isinstance(b, tuple))
                    if not has:
                        existing_buffs.append((desc_buf["type"], desc_buf["duration"]))
                        sd_entry["team_buffs"] = existing_buffs

                # Fix extra_turn from descriptions
                if p.get("extra_turn") and not sd_entry.get("grants_extra_turn"):
                    sd_entry["grants_extra_turn"] = True
                if not p.get("extra_turn") and sd_entry.get("grants_extra_turn"):
                    sd_entry["grants_extra_turn"] = False

                # Add missing activate effects from descriptions
                if p.get("activate_burns"):
                    has = any("activate_hp_burns" in e.get("effect_type", "") for e in eff_list)
                    if not has:
                        eff_list.append(_eff("activate_hp_burns"))
                if p.get("activate_poisons"):
                    has = any("activate_poisons" in e.get("effect_type", "") for e in eff_list)
                    if not has:
                        eff_list.append(_eff("activate_poisons", max_count=2))
                if p.get("activate_dots"):
                    has = any("activate_dots" in e.get("effect_type", "") for e in eff_list)
                    if not has:
                        eff_list.append(_eff("activate_dots"))

                # Add ally attack from descriptions
                if p.get("ally_attack"):
                    has = any("ally_attack" in e.get("effect_type", "") for e in eff_list)
                    if not has:
                        eff_list.append(_eff("ally_attack", count=4))

                # Add extend debuffs from descriptions
                if p.get("extend_debuffs") and not any("extend" in e.get("effect_type", "") for e in eff_list):
                    ext_type = p["extend_debuffs"]
                    if ext_type == "hp_burn":
                        eff_list.append(_eff("extend_debuffs_hp_burn", turns=1, per_hit=(p["hits"] > 1)))
                    elif ext_type == "poison_burn":
                        eff_list.append(_eff("extend_debuffs_poison_burn", turns=1))
                    else:
                        eff_list.append(_eff("extend_debuffs", turns=1, per_hit=(p["hits"] > 1)))

                # Add missing debuffs from descriptions (that game data didn't capture)
                for desc_db in p.get("debuffs", []):
                    if desc_db.get("on_self"):
                        continue
                    has = any(e.get("params", {}).get("debuff", "").startswith(desc_db["type"].split("_")[0])
                              for e in eff_list if e.get("effect_type") == "debuff")
                    if not has and desc_db["type"] in (
                        "def_down", "weaken", "dec_atk", "hp_burn", "poison_5pct",
                        "leech", "poison_sensitivity", "heal_reduction"
                    ):
                        eff_list.append(_eff("debuff",
                            debuff=desc_db["type"],
                            duration=desc_db["duration"],
                            chance=desc_db["chance"]))

    except Exception as ex:
        pass  # desc_profiler not available or failed — use game-data-only profiles

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
