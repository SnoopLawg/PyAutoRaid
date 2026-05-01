"""Display-name maps for Raid game enums.

Used across the dashboard, CLI tools, and battle-log readers. The
canonical numeric IDs come from HeroType.Forms[0].Element / Faction /
Rarity / Role enums in the IL2CPP dump. This module owns the
human-readable mapping; everything else imports from here.
"""
from __future__ import annotations

# Hero rarity (HeroType.Rarity enum int).
RARITY_NAMES: dict[int, str] = {
    1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic",
    5: "Legendary", 6: "Mythical",
}

# Element (HeroType.Forms[0].Element enum int).
# 1=Magic, 2=Force, 3=Spirit, 4=Void. Matches the value the BepInEx mod
# emits in /all-heroes and the battle log.
ELEMENT_NAMES: dict[int, str] = {1: "Magic", 2: "Force", 3: "Spirit", 4: "Void"}

# Hero role (HeroType.DefaultRole enum int).
ROLE_NAMES: dict[int, str] = {
    0: "Unknown", 1: "Attack", 2: "Defense", 3: "HP", 4: "Support",
}

# Faction (HeroType.Fraction enum int).
FACTION_NAMES: dict[int, str] = {
    0: "Unknown", 1: "Banner Lords", 2: "High Elves", 3: "Sacred Order",
    4: "Coven of Magi", 5: "Ogryn Tribes", 6: "Lizardmen", 7: "Skinwalkers",
    8: "Orcs", 9: "Demonspawn", 10: "Undead Hordes", 11: "Dark Elves",
    12: "Knights Revenant", 13: "Barbarians", 14: "Sylvan Watchers",
    15: "Samurai", 16: "Dwarves", 17: "Olympians",
}

# Plarium-internal CamelCase faction names → display names. The mod's
# /all-heroes endpoint sometimes emits the raw enum string instead of an
# int, so this bridges to a clean label.
FACTION_PRETTY: dict[str, str] = {
    "BannerLords": "Banner Lords",
    "HighElves": "High Elves",
    "SacredOrder": "Sacred Order",
    "CovenOfMagi": "Coven of Magi",
    "OgrynTribes": "Ogryn Tribes",
    "LizardMen": "Lizardmen",
    "UndeadHordes": "Undead Hordes",
    "DarkElves": "Dark Elves",
    "KnightsRevenant": "Knights Revenant",
    "SylvanWatchers": "Sylvan Watchers",
}


def faction_display(value) -> str:
    """Resolve a faction value (int or string) to its display name.
    Returns empty string for unknown values rather than raising."""
    if isinstance(value, int):
        return FACTION_NAMES.get(value, "")
    if isinstance(value, str):
        return FACTION_PRETTY.get(value, value)
    return ""


def element_display(value: int | None) -> str:
    return ELEMENT_NAMES.get(value or 0, "")


def role_display(value: int | None) -> str:
    return ROLE_NAMES.get(value or 0, "")


def rarity_display(value: int | None) -> str:
    return RARITY_NAMES.get(value or 0, "")
