#!/usr/bin/env python3
"""Fetch CB boss skill data directly from the game via /enemy-skills.

No more guessing: we read the exact effect kinds, chances, durations,
and status-effect type IDs straight from StaticData. This is how the
sim should learn what "stun" actually is.

Usage:
    python3 tools/cb_boss_skills.py              # all 4 CB elements
    python3 tools/cb_boss_skills.py 22270        # specific CB boss
"""
import json
import sys
import urllib.request
from pathlib import Path

MOD = "http://localhost:6790"

# CB boss type IDs per element (observed from battle logs)
CB_BOSSES = {
    "void":   22270,   # from current run
    # other elements — fill in as we encounter them
}

EFFECT_KIND = {
    1000: "heal",
    2000: "tm_change",
    4000: "buff",
    5000: "debuff",
    5001: "tm_drain",
    5008: "extend_debuffs",
    6000: "attack",
    7001: "ignore_def",
    9002: "activate_dots",
    11000: "extra_turn",
}

STATUS_EFFECT = {
    10: "stun", 20: "freeze", 30: "sleep",
    60: "block_damage",
    80: "poison", 91: "ally_protect",
    100: "cont_heal_7.5pct", 120: "inc_atk",
    130: "dec_atk", 131: "dec_atk_alt", 151: "def_down",
    161: "inc_cd", 261: "inc_spd", 280: "inc_def",
    320: "unkillable", 350: "weaken",
    360: "gathering_fury", 460: "leech", 470: "hp_burn",
    481: "invis", 491: "true_fear", 500: "poison_sens",
}


def fetch(type_id):
    url = f"{MOD}/enemy-skills?type_id={type_id}"
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def pretty_print(data):
    if "error" in data:
        print("ERROR:", data["error"])
        return
    print(f"=== Boss type {data['type_id']}: {data.get('name', '?')} ===")
    for s in data.get("skills", []):
        sid = s["skill_type_id"]
        nm = s.get("name", "?")
        desc = s.get("desc", "")
        cd = s.get("cooldown", 0)
        print(f"\n[{sid}] {nm}  CD={cd}")
        if desc:
            # Strip color tags for readability
            import re
            clean = re.sub(r"<[^>]+>", "", desc)
            print(f"  desc: {clean[:200]}")
        for i, eff in enumerate(s.get("effects", [])):
            kind = eff.get("kind", 0)
            kind_n = EFFECT_KIND.get(kind, f"kind{kind}")
            chance = eff.get("chance", 0)
            formula = eff.get("formula", "")
            count = eff.get("count", 1)
            ses = eff.get("status_effects", [])
            parts = [f"kind={kind_n}"]
            if count > 1:
                parts.append(f"count={count}")
            if chance:
                parts.append(f"chance={chance}%")
            if formula:
                parts.append(f"formula={formula}")
            if ses:
                se_names = ",".join(
                    f"{STATUS_EFFECT.get(se['type'], 'type'+str(se['type']))}({se['duration']}t)"
                    for se in ses
                )
                parts.append(f"applies=[{se_names}]")
            print(f"    eff[{i}]: {' '.join(parts)}")


def main():
    if len(sys.argv) > 1:
        ids = [int(a) for a in sys.argv[1:]]
    else:
        ids = list(CB_BOSSES.values())
    for tid in ids:
        data = fetch(tid)
        pretty_print(data)
        print()


if __name__ == "__main__":
    main()
