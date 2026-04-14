#!/usr/bin/env python3
"""
Description-Driven Skill Profiler.

Parses the natural-language skill descriptions (from game localization) to extract
complete skill effects for every hero. Replaces manual per-hero fixes with systematic
pattern matching against the game's own text.

The game uses template-based descriptions with consistent patterns:
  "Has a X% chance of placing a Y% [Effect] debuff for Z turns"
  "Places a [Buff] buff on all allies for Z turns"
  "Attacks N times at random"
  "Grants an Extra Turn"
  "Will instantly activate any [HP Burn] debuffs"
  etc.

Usage:
    from desc_profiler import parse_all_descriptions
    parsed = parse_all_descriptions()  # {hero_name: {A1: {...}, A2: {...}, ...}}

    python3 tools/desc_profiler.py --hero "Sicia Flametongue"
    python3 tools/desc_profiler.py --compare  # compare parsed vs current sim
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# =============================================================================
# Debuff name → sim debuff type mapping
# =============================================================================
DEBUFF_MAP = {
    "Poison": "poison_5pct",
    "HP Burn": "hp_burn",
    "Decrease DEF": "def_down",
    "Decrease ATK": "dec_atk",
    "Decrease SPD": "dec_spd",
    "Decrease ACC": "dec_acc",
    "Decrease C. RATE": "dec_cr",
    "Weaken": "weaken",
    "Leech": "leech",
    "Heal Reduction": "heal_reduction",
    "Poison Sensitivity": "poison_sensitivity",
    "Block Buffs": "block_buffs",
    "Block Active Skills": "block_active",
    "Stun": "stun",
    "Freeze": "freeze",
    "Sleep": "sleep",
    "Provoke": "provoke",
    "Fear": "fear",
    "True Fear": "true_fear",
    "Hex": "hex",
    "Block Revive": "block_revive",
    "Bomb": "bomb",
}

BUFF_MAP = {
    "Increase ATK": "atk_up",
    "Increase DEF": "inc_def",
    "Increase SPD": "inc_spd",
    "Increase C. RATE": "inc_cr_30",
    "Increase C. DMG": "inc_cd_30",
    "Increase C.DMG": "inc_cd_30",
    "Increase C.RATE": "inc_cr_30",
    "Increase ACC": "inc_acc",
    "Increase RES": "inc_res",
    "Counterattack": "counterattack",
    "Unkillable": "unkillable",
    "Block Damage": "block_damage",
    "Block Debuffs": "block_debuffs",
    "Ally Protection": "ally_protect",
    "Shield": "shield",
    "Continuous Heal": "cont_heal_15",
    "Perfect Veil": "perfect_veil",
    "Veil": "veil",
    "Reflect Damage": "reflect_damage",
    "Revive On Death": "revive_on_death",
    "Revive on Death": "revive_on_death",
    "Strengthen": "strengthen",
}


def parse_skill_description(desc, skill_label="A1"):
    """Parse a single skill description into structured effects.

    Returns dict with:
        hits: int
        debuffs: [{type, duration, chance, count, condition}]
        buffs: [{type, duration, target}]
        extra_turn: bool
        ignore_def_pct: float
        tm_fill_self: float
        tm_fill_team: float
        activate_burns: bool
        activate_poisons: bool
        activate_dots: bool
        extend_debuffs: str or None  ("all", "hp_burn", "poison_burn")
        ally_attack: bool
        cd_reduction: int
        self_damage: bool (places debuff on self)
    """
    result = {
        "hits": 1,
        "debuffs": [],
        "buffs": [],
        "extra_turn": False,
        "ignore_def_pct": 0,
        "tm_fill_self": 0,
        "tm_fill_team": 0,
        "activate_burns": False,
        "activate_poisons": False,
        "activate_dots": False,
        "extend_debuffs": None,
        "extend_buffs": False,
        "ally_attack": False,
        "cd_reduction": 0,
        "self_damage": False,
    }

    if not desc:
        return result

    # --- HIT COUNT ---
    m = re.search(r'Attacks.*?(\d+) times', desc)
    if m:
        result["hits"] = int(m.group(1))

    # --- DEBUFF PLACEMENT ---
    # Pattern: "Has a X% chance of placing (a|an|two|three) Y% [Effect] debuff(s) for Z turns"
    for m in re.finditer(
        r'(?:Has a |has a )?(\d+)% chance of placing '
        r'(?:(two|three|four|2|3|4) )?'
        r'(?:a |an )?'
        r'(?:(\d+)% )?'
        r'\[([^\]]+)\] debuffs? '
        r'(?:on (?:all enemies|the target|a random enemy|each enemy|the attacker) )?'
        r'for (\d+) turns?',
        desc
    ):
        chance = int(m.group(1))
        count_str = m.group(2)
        # pct = m.group(3)  # e.g., "60" for 60% Decrease DEF
        effect_name = m.group(4)
        duration = int(m.group(5))
        count = {"two": 2, "three": 3, "four": 4, "2": 2, "3": 3, "4": 4}.get(count_str, 1)

        sim_type = DEBUFF_MAP.get(effect_name)
        if sim_type:
            result["debuffs"].append({
                "type": sim_type,
                "duration": duration,
                "chance": chance / 100,
                "count": count,
            })

    # Pattern: "Places a Y% [Effect] debuff on ... for Z turns" (100% chance)
    for m in re.finditer(
        r'[Pp]laces? '
        r'(?:(two|three|four|2|3|4) )?'
        r'(?:a |an )?'
        r'(?:(\d+)% )?'
        r'\[([^\]]+)\] debuffs? '
        r'(?:on (?:all enemies|the target|a random enemy|each enemy|this Champion|the attacker) )?'
        r'for (\d+) turns?',
        desc
    ):
        count_str = m.group(1)
        effect_name = m.group(3)
        duration = int(m.group(4))
        count = {"two": 2, "three": 3, "four": 4, "2": 2, "3": 3, "4": 4}.get(count_str, 1)

        sim_type = DEBUFF_MAP.get(effect_name)
        if sim_type:
            # Check if this is on self
            on_self = "this Champion" in m.group(0)
            result["debuffs"].append({
                "type": sim_type,
                "duration": duration,
                "chance": 1.0,
                "count": count,
                "on_self": on_self,
            })
            if on_self:
                result["self_damage"] = True

    # --- BUFF PLACEMENT ---
    for m in re.finditer(
        r'[Pp]laces? '
        r'(?:a |an )?'
        r'(?:(\d+)% )?'
        r'\[([^\]]+)\] buffs? '
        r'(?:on (?:all allies|this Champion|all allies except this Champion) )?'
        r'for (\d+) turns?',
        desc
    ):
        effect_name = m.group(2)
        duration = int(m.group(3))
        sim_type = BUFF_MAP.get(effect_name)
        if sim_type:
            target = "team"
            if "this Champion" in m.group(0) and "except" not in m.group(0):
                target = "self"
            result["buffs"].append({
                "type": sim_type,
                "duration": duration,
                "target": target,
            })

    # --- EXTRA TURN ---
    if re.search(r'Grants? an Extra Turn|grants? an extra turn', desc):
        result["extra_turn"] = True

    # --- IGNORE DEF ---
    m = re.search(r'ignore (\d+)% of (?:the )?(?:target\'?s? )?(?:enemy )?DEF', desc, re.IGNORECASE)
    if m:
        result["ignore_def_pct"] = int(m.group(1)) / 100

    # --- TM FILL ---
    m = re.search(r"fills? this Champion'?s? Turn Meter by (\d+)%", desc, re.IGNORECASE)
    if m:
        result["tm_fill_self"] = int(m.group(1)) / 100

    m = re.search(r"fills? (?:all allies'?|the Turn Meters? of all allies by) (\d+)%", desc, re.IGNORECASE)
    if m:
        result["tm_fill_team"] = int(m.group(1)) / 100

    # --- ACTIVATE DEBUFFS ---
    if re.search(r'instantly activate.*?\[HP Burn\]', desc, re.IGNORECASE):
        result["activate_burns"] = True
    if re.search(r'activating up to.*?\[Poison\]', desc, re.IGNORECASE):
        result["activate_poisons"] = True
    if re.search(r'instantly activates? one tick of all \[Poison\].*?\[HP Burn\]', desc, re.IGNORECASE):
        result["activate_dots"] = True

    # --- EXTEND DEBUFF DURATION ---
    if re.search(r'increas\w+ the duration of.*?\[HP Burn\] debuffs?.*?by (\d+) turn', desc, re.IGNORECASE):
        if '[Poison]' in desc:
            result["extend_debuffs"] = "poison_burn"
        else:
            result["extend_debuffs"] = "hp_burn"
    elif re.search(r'[Ii]ncreas\w+ the duration of all.*?debuffs?.*?by (\d+) turn', desc):
        result["extend_debuffs"] = "all"
    elif re.search(r'[Ii]ncreas\w+ the duration of all \[Poison\].*?\[HP Burn\].*?by (\d+) turn', desc):
        result["extend_debuffs"] = "poison_burn"

    # --- EXTEND BUFF DURATION ---
    if re.search(r'[Ii]ncreas\w+ the duration of all ally buffs? by', desc):
        result["extend_buffs"] = True

    # --- ALLY ATTACK ---
    if re.search(r'teams? up with all allies to attack|all allies except this Champion will attack', desc, re.IGNORECASE):
        result["ally_attack"] = True

    # --- CD REDUCTION ---
    m = re.search(r'decrease the cooldown.*?by (\d+) turn', desc, re.IGNORECASE)
    if m:
        result["cd_reduction"] = int(m.group(1))

    return result


def parse_all_descriptions(descs_path=None):
    """Parse all skill descriptions and return structured data per hero."""
    if descs_path is None:
        descs_path = PROJECT_ROOT / "skill_descriptions.json"

    descs = json.loads(Path(descs_path).read_text())
    parsed = {}

    for hero_name, skills in descs.items():
        hero_parsed = {}
        for label, info in skills.items():
            desc = info.get("desc", "")
            name = info.get("name", "")
            stid = info.get("skill_type_id", 0)

            p = parse_skill_description(desc, label)
            p["name"] = name
            p["skill_type_id"] = stid
            hero_parsed[label] = p

        parsed[hero_name] = hero_parsed

    return parsed


def compare_with_sim(hero_name, parsed, sd, se):
    """Compare parsed description effects with current sim data."""
    p_skills = parsed.get(hero_name, {})
    s_skills = sd.get(hero_name, {})
    s_effs = se.get(hero_name, {})

    diffs = []

    for label in ["A1", "A2", "A3"]:
        p = p_skills.get(label)
        s = s_skills.get(label, {})
        e = s_effs.get(label, [])
        if not p:
            continue

        # Compare debuffs
        for db in p.get("debuffs", []):
            if db.get("on_self"):
                continue  # Skip self-placed debuffs (not CB-relevant)
            sim_has = any(
                eff.get("params", {}).get("debuff", "").startswith(db["type"].split("_")[0])
                for eff in e
            )
            if not sim_has:
                diffs.append(f"{label}: DESC places [{db['type']}] ({db['chance']*100:.0f}%) but SIM missing")

        # Compare buffs
        for buf in p.get("buffs", []):
            if buf.get("target") == "self":
                continue  # Self-buffs less critical for sim
            sim_has = any(
                b[0].startswith(buf["type"].split("_")[0]) if isinstance(b, tuple) else False
                for b in s.get("team_buffs", [])
            )
            if not sim_has:
                diffs.append(f"{label}: DESC places [{buf['type']}] buff but SIM missing")

        # Compare extra turn
        if p.get("extra_turn") and not s.get("grants_extra_turn"):
            diffs.append(f"{label}: DESC has Extra Turn but SIM missing")
        if s.get("grants_extra_turn") and not p.get("extra_turn"):
            diffs.append(f"{label}: SIM has Extra Turn but DESC doesn't")

        # Compare ignore DEF
        if abs(p.get("ignore_def_pct", 0) - s.get("ignore_def", 0)) > 0.01:
            diffs.append(f"{label}: DEF ignore DESC={p['ignore_def_pct']*100:.0f}% SIM={s.get('ignore_def',0)*100:.0f}%")

        # Compare activate effects
        if p.get("activate_burns"):
            has = any("activate_hp_burns" in eff.get("effect_type", "") or "activate_dots" in eff.get("effect_type", "") for eff in e)
            if not has:
                diffs.append(f"{label}: DESC activates HP Burns but SIM missing")
        if p.get("activate_poisons"):
            has = any("activate_poisons" in eff.get("effect_type", "") or "activate_dots" in eff.get("effect_type", "") for eff in e)
            if not has:
                diffs.append(f"{label}: DESC activates Poisons but SIM missing")

        # Compare ally attack
        if p.get("ally_attack"):
            has = any("ally_attack" in eff.get("effect_type", "") for eff in e)
            if not has:
                diffs.append(f"{label}: DESC has Ally Attack but SIM missing")

    return diffs


# =============================================================================
# CLI
# =============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Description-Driven Skill Profiler")
    parser.add_argument("--hero", help="Parse and show skills for a specific hero")
    parser.add_argument("--compare", action="store_true", help="Compare parsed vs current sim for all profiled heroes")
    parser.add_argument("--cb-only", action="store_true", help="Only show CB-relevant effects")
    args = parser.parse_args()

    parsed = parse_all_descriptions()

    if args.hero:
        h = parsed.get(args.hero)
        if not h:
            print(f"Hero '{args.hero}' not found")
            return
        print(f"=== {args.hero} ===")
        for label in ["A1", "A2", "A3", "Passive", "Passive2"]:
            p = h.get(label)
            if not p:
                continue
            print(f"\n  {label}: {p['name']} [{p['skill_type_id']}]")
            print(f"    Hits: {p['hits']}")
            if p["debuffs"]:
                for db in p["debuffs"]:
                    self_str = " (SELF)" if db.get("on_self") else ""
                    print(f"    Debuff: {db['type']} dur={db['duration']} chance={db['chance']*100:.0f}% x{db['count']}{self_str}")
            if p["buffs"]:
                for buf in p["buffs"]:
                    print(f"    Buff: {buf['type']} dur={buf['duration']} target={buf['target']}")
            if p["extra_turn"]: print(f"    Extra Turn")
            if p["ignore_def_pct"]: print(f"    Ignore DEF: {p['ignore_def_pct']*100:.0f}%")
            if p["tm_fill_self"]: print(f"    TM fill self: {p['tm_fill_self']*100:.0f}%")
            if p["tm_fill_team"]: print(f"    TM fill team: {p['tm_fill_team']*100:.0f}%")
            if p["activate_burns"]: print(f"    Activate HP Burns")
            if p["activate_poisons"]: print(f"    Activate Poisons")
            if p["activate_dots"]: print(f"    Activate ALL DoTs")
            if p["extend_debuffs"]: print(f"    Extend debuffs: {p['extend_debuffs']}")
            if p["extend_buffs"]: print(f"    Extend buffs")
            if p["ally_attack"]: print(f"    Ally Attack")
            if p["cd_reduction"]: print(f"    CD Reduction: {p['cd_reduction']}")
        return

    if args.compare:
        sys.path.insert(0, str(PROJECT_ROOT / "tools"))
        from load_game_profiles import load_profiles
        sd, se, pd = load_profiles()

        profiled = set(sd.keys())
        total_diffs = 0
        heroes_with_diffs = 0

        for hero in sorted(profiled):
            diffs = compare_with_sim(hero, parsed, sd, se)
            if diffs:
                heroes_with_diffs += 1
                total_diffs += len(diffs)
                print(f"\n{hero}:")
                for d in diffs:
                    print(f"  - {d}")

        print(f"\n{'='*50}")
        print(f"Profiled heroes: {len(profiled)}")
        print(f"Heroes with discrepancies: {heroes_with_diffs}")
        print(f"Total discrepancies: {total_diffs}")
        return

    # Default: show summary stats
    print(f"Parsed {len(parsed)} heroes from descriptions")
    debuff_heroes = sum(1 for h in parsed.values() if any(s.get("debuffs") for s in h.values()))
    burn_heroes = sum(1 for h in parsed.values() if any(
        any(d["type"] == "hp_burn" for d in s.get("debuffs", []))
        for s in h.values()))
    poison_heroes = sum(1 for h in parsed.values() if any(
        any(d["type"] == "poison_5pct" for d in s.get("debuffs", []))
        for s in h.values()))
    dd_heroes = sum(1 for h in parsed.values() if any(
        any(d["type"] == "def_down" for d in s.get("debuffs", []))
        for s in h.values()))
    wk_heroes = sum(1 for h in parsed.values() if any(
        any(d["type"] == "weaken" for d in s.get("debuffs", []))
        for s in h.values()))
    et_heroes = sum(1 for h in parsed.values() if any(s.get("extra_turn") for s in h.values()))

    print(f"  Place debuffs: {debuff_heroes}")
    print(f"  Place Poison: {poison_heroes}")
    print(f"  Place HP Burn: {burn_heroes}")
    print(f"  Place DEF Down: {dd_heroes}")
    print(f"  Place Weaken: {wk_heroes}")
    print(f"  Extra Turn: {et_heroes}")


if __name__ == "__main__":
    main()
