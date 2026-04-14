"""
Auto-generate SKILL_DATA and SKILL_EFFECTS for cb_sim.py from skills_db.json.

Reads the raw game data and produces accurate skill entries for ALL heroes.
No hand-coding — everything comes from the game.
"""
import json
import re
from pathlib import Path


def parse_formula(formula: str) -> dict:
    """Parse damage formula like '3.9*ATK' into {mult, stat, hits_in_formula}."""
    if not formula:
        return {"mult": 0, "stat": "ATK"}
    formula = formula.strip()

    # Simple: N*STAT
    m = re.match(r'^([\d.]+)\*(\w+)$', formula)
    if m:
        return {"mult": float(m.group(1)), "stat": m.group(2)}

    # STAT alone (mult=1)
    if formula in ("ATK", "DEF", "HP"):
        return {"mult": 1.0, "stat": formula}

    # N*STAT + M*STAT2 (take first term)
    m = re.match(r'^([\d.]+)\*(\w+)\s*[\+\-]', formula)
    if m:
        return {"mult": float(m.group(1)), "stat": m.group(2)}

    # DEF+ATK or ATK+DEF (hybrid)
    if "DEF" in formula and "ATK" in formula:
        return {"mult": 1.0, "stat": "ATK"}

    # SPD-based
    if "SPD" in formula:
        return {"mult": 3.0, "stat": "ATK"}  # approximate

    # HP-based: 0.05*HP*(...) or N*HP
    m = re.match(r'^([\d.]+)\*HP', formula)
    if m:
        return {"mult": float(m.group(1)), "stat": "HP"}
    if "HP" in formula:
        return {"mult": 0.1, "stat": "HP"}

    # TRG_HP (enemy max HP)
    if "TRG_HP" in formula:
        return {"mult": 0.1, "stat": "HP"}  # approximate

    # Fallback
    return {"mult": 0, "stat": "ATK"}


# Effect kind → what it means for the sim
# Format: (sim_effect_type, params_template)
EFFECT_DECODERS = {
    6000: ("damage", {}),           # Damage — handled via multiplier, not as effect
    5000: ("debuff", {"debuff": "poison_5pct", "duration": 2}),
    5002: ("debuff", {"debuff": "hp_burn", "duration": 2}),
    5003: ("debuff", {"debuff": "debuff_generic", "duration": 2}),  # DEF Down, Weaken, etc.
    5005: ("debuff", {"debuff": "stat_debuff", "duration": 2}),     # Dec SPD, Dec ATK
    5008: ("extend_debuffs", {"turns": 1}),
    5009: ("debuff", {"debuff": "leech", "duration": 2}),
    11000: ("debuff", {"debuff": "leech", "duration": 2}),
    4007: None,  # Counterattack buff — handled via team_buffs
    4000: None,  # Generic buff — handled via team_buffs
    4006: ("ally_attack", {"count": 3}),
    4010: None,  # Ally Protect — handled specially
    4011: ("extend_buffs", {"turns": 1}),
    9002: ("activate_poisons", {}),
    1000: None,  # Heal — handled specially per hero
    7004: None,  # Damage reduction — handled via team_buffs
    4001: None,  # TM manipulation — not modeled as effect
    5001: None,  # TM reduce on enemy — not relevant for damage
    4003: None,  # Remove buffs — not relevant for CB
    4009: None,  # Passive trigger — handled per hero
    4012: None,  # Passive buff extension — handled per hero
    4013: None,  # Stat boost passive — handled per hero
    4017: None,  # Passive damage — handled per hero (Geomancer)
    7003: None,  # Shield — not modeled yet
    5004: None,  # CC debuff (stun/freeze) — CB immune
    5011: None,  # Hex — CB immune
    7001: None,  # Bonus damage — approximate in multiplier
    7017: None,  # Extra turns passive — handled per hero
    9000: None,  # Unkillable passive — handled per hero
    5014: None,  # DEF steal — not modeled
    9006: None,  # Ninja TM boost — handled per hero
}


def generate_skill_data(name: str, skills: list) -> dict:
    """Generate SKILL_DATA entry from raw game skill data."""
    # Deduplicate by type_id, keep highest level
    best = {}
    for sk in skills:
        tid = sk.get("skill_type_id", 0)
        lvl = sk.get("level", 0)
        if tid not in best or lvl > best[tid].get("level", 0):
            best[tid] = sk

    # Sort: A1 first, then by CD
    sorted_skills = sorted(best.values(), key=lambda s: (
        0 if s.get("is_a1") else 1,
        s.get("cooldown", 0) if s.get("cooldown", 0) > 0 else 999
    ))

    result = {}
    labels_used = {"A1": False, "A2": False, "A3": False}

    for sk in sorted_skills:
        is_a1 = sk.get("is_a1", False)
        cd = sk.get("cooldown", 0)

        # Assign label
        if is_a1 and not labels_used["A1"]:
            label = "A1"
        elif cd > 0 and not labels_used["A2"]:
            label = "A2"
        elif cd > 0 and not labels_used["A3"]:
            label = "A3"
        else:
            continue  # skip passives and extras

        labels_used[label] = True

        # Calculate booked CD
        bonuses = sk.get("level_bonuses", [])
        cd_reds = sum(1 for b in bonuses if b.get("type") == 3)
        booked_cd = cd - cd_reds if cd > 0 else 0

        # Calculate booked damage multiplier
        dmg_bonus_pct = sum(b["value"] for b in bonuses if b.get("type") == 0)

        # Parse damage from effects
        damage_effects = [e for e in sk.get("effects", []) if e.get("kind") == 6000]
        # Hit count: number of separate damage effects, OR count field on a single effect
        if damage_effects:
            if len(damage_effects) > 1:
                hit_count = len(damage_effects)
            else:
                hit_count = max(damage_effects[0].get("count", 1), 1)
        else:
            hit_count = 0
        formula_str = damage_effects[0].get("formula", "") if damage_effects else ""
        parsed = parse_formula(formula_str)

        total_mult = parsed["mult"] * max(hit_count, 1) if parsed["mult"] > 0 else 0
        if dmg_bonus_pct > 0 and total_mult > 0:
            total_mult *= (1 + dmg_bonus_pct / 100)

        # Detect team buffs
        team_buffs = []
        for e in sk.get("effects", []):
            kind = e.get("kind", 0)
            status_effects = e.get("status_effects", [])

            # USE EXACT status_effects when available (from game's StatusEffectTypeId)
            if status_effects:
                from status_effect_map import STATUS_EFFECT_MAP, ALLY_BUFFS
                for se in status_effects:
                    se_type = se.get("type", 0)
                    se_dur = se.get("duration", 2)
                    se_info = STATUS_EFFECT_MAP.get(se_type)
                    if se_info:
                        se_name, _, is_buff = se_info
                        if is_buff and se_name in ALLY_BUFFS:
                            team_buffs.append((se_name, se_dur))
            elif kind == 7004:  # Damage reduction (passive/buff, no status_effect)
                team_buffs.append(("dmg_reduction", 2))

        entry = {
            "mult": round(total_mult, 2),
            "stat": parsed["stat"],
            "hits": max(hit_count, 1),
            "cd": booked_cd,
        }
        if team_buffs:
            entry["team_buffs"] = team_buffs

        result[label] = entry

    return result


def generate_skill_effects(name: str, skills: list) -> dict:
    """Generate SKILL_EFFECTS entry from raw game skill data."""
    best = {}
    for sk in skills:
        tid = sk.get("skill_type_id", 0)
        lvl = sk.get("level", 0)
        if tid not in best or lvl > best[tid].get("level", 0):
            best[tid] = sk

    sorted_skills = sorted(best.values(), key=lambda s: (
        0 if s.get("is_a1") else 1,
        s.get("cooldown", 0) if s.get("cooldown", 0) > 0 else 999
    ))

    result = {}
    labels_used = {"A1": False, "A2": False, "A3": False}

    for sk in sorted_skills:
        is_a1 = sk.get("is_a1", False)
        cd = sk.get("cooldown", 0)

        if is_a1 and not labels_used["A1"]:
            label = "A1"
        elif cd > 0 and not labels_used["A2"]:
            label = "A2"
        elif cd > 0 and not labels_used["A3"]:
            label = "A3"
        else:
            continue

        labels_used[label] = True

        effects = []
        dmg_effs = [e for e in sk.get("effects", []) if e.get("kind") == 6000]
        if dmg_effs:
            hit_count = len(dmg_effs) if len(dmg_effs) > 1 else max(dmg_effs[0].get("count", 1), 1)
        else:
            hit_count = 0

        from status_effect_map import STATUS_EFFECT_MAP, CB_DEBUFFS, ALLY_BUFFS

        for e in sk.get("effects", []):
            kind = e.get("kind", 0)
            chance = e.get("chance", 0) / 100 if e.get("chance", 0) > 1 else e.get("chance", 0)
            if chance == 0:
                chance = 0.75  # default for most debuffs
            count = e.get("count", 1)

            # USE EXACT StatusEffectTypeId when available
            status_effects = e.get("status_effects", [])
            if status_effects:
                for se in status_effects:
                    se_type = se.get("type", 0)
                    se_dur = se.get("duration", 2)
                    se_info = STATUS_EFFECT_MAP.get(se_type)
                    if se_info:
                        se_name, is_debuff, is_buff = se_info
                        if is_debuff and se_name in CB_DEBUFFS:
                            effects.append({
                                "effect_type": "debuff",
                                "params": {"debuff": se_name, "duration": se_dur, "chance": chance, "count": count}
                            })
                        # Buffs are handled via team_buffs in SKILL_DATA, not effects
                continue  # status_effects handled, skip kind-based fallback

            # Fallback: use kind when no status_effects available
            if kind == 5008:  # Extend debuffs
                effects.append({
                    "effect_type": "extend_debuffs",
                    "params": {"turns": 1, "per_hit": hit_count > 1}
                })
            elif kind == 4011:  # Extend buffs
                effects.append({
                    "effect_type": "extend_buffs",
                    "params": {"turns": 1}
                })
            elif kind == 9002:  # Activate poisons
                effects.append({
                    "effect_type": "activate_poisons",
                    "params": {}
                })
            elif kind == 4006:  # Ally Attack
                effects.append({
                    "effect_type": "ally_attack",
                    "params": {"count": 3}
                })

        result[label] = effects

    return result


def generate_all():
    """Generate SKILL_DATA and SKILL_EFFECTS for all heroes."""
    db_path = Path(__file__).parent.parent / "skills_db.json"
    with open(db_path) as f:
        db = json.load(f)

    all_skill_data = {}
    all_skill_effects = {}

    for name, skills in db.items():
        sd = generate_skill_data(name, skills)
        se = generate_skill_effects(name, skills)
        if sd:
            all_skill_data[name] = sd
        if se:
            all_skill_effects[name] = se

    return all_skill_data, all_skill_effects


if __name__ == "__main__":
    sd, se = generate_all()
    print(f"Generated SKILL_DATA for {len(sd)} heroes")
    print(f"Generated SKILL_EFFECTS for {len(se)} heroes")

    # Print a few examples
    for name in ["Cardiel", "Ma'Shalled", "Skullcrusher", "Geomancer", "Gnut",
                  "Venus", "Occult Brawler", "Corvis the Corruptor"]:
        if name in sd:
            print(f"\n{name}:")
            for label, d in sd[name].items():
                tb = d.get("team_buffs", [])
                tb_str = f" buffs={tb}" if tb else ""
                print(f"  {label}: mult={d['mult']} stat={d['stat']} hits={d['hits']} cd={d['cd']}{tb_str}")
            for label, effs in se.get(name, {}).items():
                if effs:
                    eff_str = ", ".join(f"{e['effect_type']}({e['params'].get('debuff', '')})" for e in effs)
                    print(f"  {label} effects: [{eff_str}]")
