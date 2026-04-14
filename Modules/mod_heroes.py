"""
Fetch full hero + artifact data from the RaidAutomation mod API.

The /all-heroes endpoint returns JSON with hero stats, equipped artifacts,
substats, sets, masteries etc — everything needed for team optimization.

Usage:
    from mod_heroes import fetch_all_heroes
    heroes = fetch_all_heroes()
    for h in heroes:
        print(h["name"], h["base_stats"], h["artifacts"])
"""

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

MOD_API_URL = "http://localhost:6790"
TIMEOUT = 30

STAT_NAMES = {
    1: "HP", 2: "ATK", 3: "DEF", 4: "SPD",
    5: "RES", 6: "ACC", 7: "CR", 8: "CD",
    9: "C.HEAL", 10: "IGN.DEF",
}

ELEMENT_NAMES = {0: "Magic", 1: "Force", 2: "Spirit", 3: "Void"}
ROLE_NAMES = {0: "Attack", 1: "Defense", 2: "HP", 3: "Support"}

RARITY_NAMES = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary", 6: "Mythical"}

FACTION_NAMES = {
    0: "Unknown", 1: "BannerLords", 2: "HighElves", 3: "SacredOrder",
    4: "CovenOfMagi", 5: "OgrynTribes", 6: "LizardMen", 7: "Skinwalkers",
    8: "Orcs", 9: "Demonspawn", 10: "UndeadHordes", 11: "DarkElves",
    12: "KnightsRevenant", 13: "Barbarians", 14: "SylvanWatchers",
    15: "Samurai", 16: "Dwarves", 17: "Olympians",
}

SET_NAMES = {
    0: "None", 1: "HP", 2: "ATK", 3: "DEF", 4: "Speed", 5: "CritRate",
    6: "CritDmg", 7: "ACC", 8: "RES", 9: "Lifesteal",
    10: "Savage", 17: "Shield", 24: "Counterattack", 35: "Unkillable",
}

ARTIFACT_KINDS = {
    1: "Weapon", 2: "Helmet", 3: "Shield",
    4: "Gauntlets", 5: "Chestplate", 6: "Boots",
    7: "Ring", 8: "Amulet", 9: "Banner",
}


def fetch_all_heroes(base_url=MOD_API_URL):
    """Fetch all heroes with full data from the mod API."""
    url = f"{base_url}/all-heroes"
    try:
        resp = urllib.request.urlopen(url, timeout=TIMEOUT)
        data = json.loads(resp.read().decode())
    except Exception as e:
        logger.error(f"Failed to fetch heroes from mod API: {e}")
        return []

    if "error" in data:
        logger.error(f"Mod API error: {data['error']}")
        return []

    heroes = []
    for h in data.get("heroes", []):
        hero = {
            "id": h.get("id"),
            "type_id": h.get("type_id"),
            "name": h.get("name", "?"),
            "grade": h.get("grade"),
            "level": h.get("level"),
            "empower": h.get("empower", 0),
            "element": ELEMENT_NAMES.get(h.get("element"), "?"),
            "role": ROLE_NAMES.get(h.get("role"), "?"),
            "faction": FACTION_NAMES.get(h.get("fraction"), "?"),
            "rarity": RARITY_NAMES.get(h.get("rarity"), "?"),
            "base_stats": h.get("base_stats", {}),
            "artifacts": [],
        }

        # Process artifacts
        for art in h.get("artifacts", []):
            artifact = {
                "slot": ARTIFACT_KINDS.get(art.get("kind"), f"Slot{art.get('kind')}"),
                "id": art.get("id"),
                "level": art.get("level", 0),
                "rank": art.get("rank", 0),
                "rarity": RARITY_NAMES.get(art.get("rarity"), "?"),
                "set_id": art.get("set", 0),
                "set_name": SET_NAMES.get(art.get("set", 0), f"Set{art.get('set')}"),
            }

            # Primary stat
            prim = art.get("primary")
            if prim:
                artifact["primary"] = {
                    "stat": STAT_NAMES.get(prim.get("stat"), f"?{prim.get('stat')}"),
                    "stat_id": prim.get("stat"),
                    "value": prim.get("value", 0),
                    "is_flat": prim.get("flat", True),
                }

            # Substats
            artifact["substats"] = []
            for sub in art.get("substats", []):
                artifact["substats"].append({
                    "stat": STAT_NAMES.get(sub.get("stat"), f"?{sub.get('stat')}"),
                    "stat_id": sub.get("stat"),
                    "value": sub.get("value", 0),
                    "is_flat": sub.get("flat", True),
                    "rolls": sub.get("level", 0),
                })

            hero["artifacts"].append(artifact)

        heroes.append(hero)

    logger.info(f"Fetched {len(heroes)} heroes from mod API")
    return heroes


def print_hero_summary(hero, show_artifacts=True):
    """Print a formatted hero summary."""
    bs = hero.get("base_stats", {})
    print(f"\n{'='*50}")
    print(f"{hero['name']} — {hero['grade']}* L{hero['level']} "
          f"({hero['element']}/{hero['role']}) [{hero['faction']}] {hero['rarity']}")
    if bs:
        print(f"  Base: HP={bs.get('HP',0):.0f} ATK={bs.get('ATK',0):.0f} "
              f"DEF={bs.get('DEF',0):.0f} SPD={bs.get('SPD',0):.0f} "
              f"CR={bs.get('CR',0):.0f}% CD={bs.get('CD',0):.0f}%")

    if show_artifacts and hero.get("artifacts"):
        sets = {}
        for art in hero["artifacts"]:
            sets[art["set_name"]] = sets.get(art["set_name"], 0) + 1
            prim = art.get("primary", {})
            ptype = "flat" if prim.get("is_flat") else "%"
            print(f"  {art['slot']:12s} {art['rank']}* +{art['level']:2d} [{art['set_name']:10s}] "
                  f"| {prim.get('stat','?'):4s} {prim.get('value',0):6.0f} ({ptype})")
            for sub in art.get("substats", []):
                stype = "flat" if sub["is_flat"] else "%"
                print(f"{'':38s}  {sub['stat']:4s} {sub['value']:6.1f} ({stype}) x{sub['rolls']}")
        print(f"  Sets: {sets}")


if __name__ == "__main__":
    heroes = fetch_all_heroes()
    if not heroes:
        print("No heroes fetched. Is the mod API running?")
    else:
        # Show top 10 by grade/level
        heroes.sort(key=lambda h: (h["grade"], h["level"]), reverse=True)
        for h in heroes[:10]:
            print_hero_summary(h)
