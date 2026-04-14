"""
Auto-generate CB simulator skill profiles from skills_db.json.

Reads the raw game skill data and generates:
1. SKILL_DATA entries (damage formulas, cooldowns, hit counts)
2. SKILL_EFFECTS entries (debuff placements, buff applications, special mechanics)

Usage:
    python3 tools/generate_profiles.py              # print all CB-relevant profiles
    python3 tools/generate_profiles.py --all        # print all 343 heroes
    python3 tools/generate_profiles.py --hero Venus # print one hero
"""
import json
import re
import sys
from pathlib import Path


def parse_formula(formula: str) -> dict:
    """Parse a damage formula like '3.1*DEF' or '1.55*ATK' into {mult, stat}."""
    if not formula:
        return {"mult": 0, "stat": "ATK"}

    formula = formula.strip()

    # Simple: N*STAT
    m = re.match(r'^([\d.]+)\*(\w+)$', formula)
    if m:
        return {"mult": float(m.group(1)), "stat": m.group(2)}

    # With addition: N*STAT + M*STAT2
    m = re.match(r'^([\d.]+)\*(\w+)\s*\+', formula)
    if m:
        return {"mult": float(m.group(1)), "stat": m.group(2)}

    # Just STAT (mult=1)
    if formula in ("ATK", "DEF", "HP"):
        return {"mult": 1.0, "stat": formula}

    # SPD-based: ATK*(N+SPD/100) or ATK*(N*SPD/100)
    if "SPD" in formula and "ATK" in formula:
        return {"mult": 3.0, "stat": "ATK"}  # approximate
    if "SPD" in formula and "DEF" in formula:
        return {"mult": 3.0, "stat": "DEF"}

    # HP-based: 0.05*HP*(...)
    if "HP" in formula:
        m2 = re.match(r'^([\d.]+)\*HP', formula)
        if m2:
            return {"mult": float(m2.group(1)), "stat": "HP"}
        return {"mult": 0.1, "stat": "HP"}

    # DEF-based
    if "DEF" in formula:
        m2 = re.match(r'^([\d.]+)\*DEF', formula)
        if m2:
            return {"mult": float(m2.group(1)), "stat": "DEF"}

    # Fallback
    return {"mult": 0, "stat": "ATK"}


def generate_profile(name: str, skills: list) -> dict:
    """Generate a profile from raw skill data."""
    # Deduplicate by skill_type_id, keep highest level
    best = {}
    for sk in skills:
        tid = sk.get("skill_type_id", 0)
        lvl = sk.get("level", 0)
        if tid not in best or lvl > best[tid].get("level", 0):
            best[tid] = sk

    # Sort: A1 first, then by CD ascending
    sorted_skills = sorted(best.values(), key=lambda s: (
        0 if s.get("is_a1") else (1 if s.get("cooldown", 0) > 0 else 2),
        s.get("cooldown", 0)
    ))

    profile = {
        "name": name,
        "skill_data": {},   # for SKILL_DATA dict
        "skill_effects": {},  # for SKILL_EFFECTS dict
        "flags": {
            "has_poison": False,
            "has_hp_burn": False,
            "has_def_down": False,
            "has_weaken": False,
            "has_ally_attack": False,
            "has_counterattack": False,
            "has_extend_debuffs": False,
            "has_extend_buffs": False,
            "has_activate_poisons": False,
            "has_tm_manip": False,
            "scaling_stat": "ATK",
        },
    }

    skill_labels = []
    a1_done = False
    a2_done = False

    for sk in sorted_skills:
        is_a1 = sk.get("is_a1", False)
        cd = sk.get("cooldown", 0)
        effects = sk.get("effects", [])

        # Assign label
        if is_a1 and not a1_done:
            label = "A1"
            a1_done = True
        elif cd > 0:
            if not a2_done:
                label = "A2"
                a2_done = True
            else:
                label = "A3"
        else:
            if not a1_done:
                label = "A1"
                a1_done = True
            else:
                continue  # skip extra passives for now

        # Parse damage
        damage_effects = [e for e in effects if e.get("kind") == 6000]
        hit_count = len(damage_effects) if damage_effects else 0
        formula_str = damage_effects[0].get("formula", "") if damage_effects else ""
        parsed = parse_formula(formula_str)

        # For multi-hit, the total mult is per-hit × hits
        total_mult = parsed["mult"] * max(hit_count, 1) if parsed["mult"] > 0 else 0

        # Calculate booked CD from level bonuses (type 3 = CD reduction)
        bonuses = sk.get("level_bonuses", [])
        cd_reductions = sum(1 for b in bonuses if b.get("type") == 3)
        booked_cd = max(0, cd - cd_reductions)

        profile["skill_data"][label] = {
            "mult": round(total_mult, 2),
            "stat": parsed["stat"],
            "hits": max(hit_count, 1),
            "cd": cd,
            "booked_cd": booked_cd,
        }
        if parsed["stat"] in ("DEF", "HP"):
            profile["flags"]["scaling_stat"] = parsed["stat"]

        # Parse effects
        skill_effects = []
        for eff in effects:
            kind = eff.get("kind", 0)
            chance = eff.get("chance", 0)
            turns = eff.get("turns", 0)
            count = eff.get("count", 0)
            formula = eff.get("formula", "")

            if kind == 5000:
                profile["flags"]["has_poison"] = True
                # kind 5000 covers both Poison and Poison Sensitivity
                # We can't distinguish without StatusParams subtype
                skill_effects.append(f"poison({count or 1}x,{chance}%,{turns}T)")
            elif kind == 5002:
                profile["flags"]["has_hp_burn"] = True
                skill_effects.append(f"hp_burn({chance}%,{turns}T)")
            elif kind == 5003:
                # Generic debuff — could be DEF Down, Weaken, etc.
                profile["flags"]["has_def_down"] = True  # assume for now
                skill_effects.append(f"debuff({chance}%,{turns}T)")
            elif kind == 5005:
                skill_effects.append(f"stat_debuff({chance}%,{turns}T)")
            elif kind == 5008:
                profile["flags"]["has_extend_debuffs"] = True
                skill_effects.append("extend_debuffs")
            elif kind == 4000:
                skill_effects.append(f"buff({count or 1}x)")
            elif kind == 4006:
                profile["flags"]["has_ally_attack"] = True
                skill_effects.append("ally_attack")
            elif kind == 4007:
                profile["flags"]["has_counterattack"] = True
                skill_effects.append("counterattack_buff")
            elif kind == 4011:
                profile["flags"]["has_extend_buffs"] = True
                skill_effects.append("extend_buffs")
            elif kind == 9002:
                profile["flags"]["has_activate_poisons"] = True
                skill_effects.append("activate_poisons")
            elif kind == 4001:
                profile["flags"]["has_tm_manip"] = True
                skill_effects.append(f"tm_manip({formula[:30]})")
            elif kind == 5009:
                skill_effects.append("leech")

        profile["skill_effects"][label] = skill_effects

    return profile


def main():
    base = Path(__file__).parent.parent
    with open(base / "skills_db.json") as f:
        db = json.load(f)

    hero_filter = None
    show_all = False
    if "--hero" in sys.argv:
        idx = sys.argv.index("--hero")
        hero_filter = sys.argv[idx + 1]
    if "--all" in sys.argv:
        show_all = True

    # CB-relevant heroes
    cb_names = [
        "Maneater", "Venus", "Occult Brawler", "Geomancer", "Fayne",
        "Frozen Banshee", "Pain Keeper", "Corvis the Corruptor",
        "Teodor the Savant", "Venomage", "Razelvarg", "Skullcrusher",
        "Fahrakin the Fat", "Nethril", "Urogrim", "Toragi the Frog",
        "Iron Brago", "Sepulcher Sentinel", "Artak", "Doompriest",
        "Rhazin Scarhide", "Heiress", "Warcaster", "Steelskull",
        "Demytha", "Drexthar Bloodtwin", "Ninja",
    ]

    profiles = {}
    for name, skills in db.items():
        if hero_filter and hero_filter.lower() not in name.lower():
            continue
        if not show_all and not hero_filter and name not in cb_names:
            continue
        profiles[name] = generate_profile(name, skills)

    # Print as Python code for cb_sim.py
    print(f"# Auto-generated from skills_db.json ({len(profiles)} heroes)")
    print(f"# Game data extracted via BepInEx mod API")
    print()

    print("SKILL_DATA_AUTO = {")
    for name, p in sorted(profiles.items()):
        sd = p["skill_data"]
        print(f'    "{name}": {{')
        for label in ["A1", "A2", "A3"]:
            if label in sd:
                d = sd[label]
                print(f'        "{label}": {{"mult": {d["mult"]}, "stat": "{d["stat"]}", "hits": {d["hits"]}, "cd": {d["cd"]}}},')
        print(f'    }},')
    print("}")

    print()
    print("# Hero flags (for optimizer profiles)")
    print(f'{"Hero":30s} {"Stat":4s} {"Poi":3s} {"Brn":3s} {"DD":3s} {"Ext":3s} {"Atk":3s} {"CA":3s} {"TM":3s} {"Act":3s}')
    print("-" * 75)
    for name, p in sorted(profiles.items()):
        f = p["flags"]
        print(f'{name:30s} {f["scaling_stat"]:4s} '
              f'{"Y" if f["has_poison"] else ".":3s} '
              f'{"Y" if f["has_hp_burn"] else ".":3s} '
              f'{"Y" if f["has_def_down"] else ".":3s} '
              f'{"Y" if f["has_extend_debuffs"] else ".":3s} '
              f'{"Y" if f["has_ally_attack"] else ".":3s} '
              f'{"Y" if f["has_counterattack"] else ".":3s} '
              f'{"Y" if f["has_tm_manip"] else ".":3s} '
              f'{"Y" if f["has_activate_poisons"] else ".":3s}')


if __name__ == "__main__":
    main()
