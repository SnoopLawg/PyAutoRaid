"""
Central artifact/gear constants for all PyAutoRaid tools.

All slot IDs, stat IDs, set IDs, and mapping tables in ONE place.
Import from here — do NOT hardcode these values in other files.

Source: IL2CPP dump (ArtifactKindId, ArtifactStatKindId, StatKindId, ArtifactSetKindId)
Verified: 2026-04-11 against Teodor the Savant's in-game artifacts.
"""

# =============================================================================
# Artifact Slot (ArtifactKindId enum from dump line 335xxx)
# =============================================================================
SLOT_HELMET = 1
SLOT_CHEST = 2
SLOT_GLOVES = 3
SLOT_BOOTS = 4
SLOT_WEAPON = 5
SLOT_SHIELD = 6
SLOT_RING = 7
SLOT_AMULET = 8  # "Cloak" in game code
SLOT_BANNER = 9

SLOT_NAMES = {
    1: "Helmet", 2: "Chest", 3: "Gloves", 4: "Boots",
    5: "Weapon", 6: "Shield", 7: "Ring", 8: "Amulet", 9: "Banner",
}

SLOT_NAMES_SHORT = {
    1: "Hlm", 2: "Cht", 3: "Glv", 4: "Bts",
    5: "Wpn", 6: "Shd", 7: "Rng", 8: "Aml", 9: "Bnr",
}

# Main gear slots (weapon through boots)
MAIN_SLOTS = {SLOT_HELMET, SLOT_CHEST, SLOT_GLOVES, SLOT_BOOTS, SLOT_WEAPON, SLOT_SHIELD}
# Accessory slots (faction-locked)
ACCESSORY_SLOTS = {SLOT_RING, SLOT_AMULET, SLOT_BANNER}

# Which primary stat types are valid per slot
# Source: Raid game rules
VALID_PRIMARIES = {
    SLOT_WEAPON: ["ATK_flat"],                                        # always ATK flat
    SLOT_HELMET: ["HP_flat"],                                         # always HP flat
    SLOT_SHIELD: ["DEF_flat", "HP%", "DEF%", "ATK%", "CR%", "CD%"],  # DEF flat base + ascension options
    SLOT_GLOVES: ["HP%", "ATK%", "DEF%", "CD%", "HP_flat", "ATK_flat", "DEF_flat"],
    SLOT_CHEST: ["HP%", "ATK%", "DEF%", "ACC", "RES", "HP_flat", "ATK_flat", "DEF_flat"],
    SLOT_BOOTS: ["SPD", "HP%", "ATK%", "DEF%", "HP_flat", "ATK_flat", "DEF_flat"],
    SLOT_RING: ["HP_flat", "ATK_flat", "DEF_flat"],
    SLOT_AMULET: ["HP_flat", "ATK_flat", "DEF_flat", "CD%"],
    SLOT_BANNER: ["ACC", "RES", "HP_flat", "ATK_flat", "DEF_flat"],
}

# =============================================================================
# Stat IDs (StatKindId — the mod outputs these)
# Combined with IsAbsolute (flat) to identify the full stat type
# =============================================================================
STAT_HP = 1
STAT_ATK = 2
STAT_DEF = 3
STAT_SPD = 4
STAT_RES = 5
STAT_ACC = 6
STAT_CR = 7
STAT_CD = 8

STAT_NAMES = {
    1: "HP", 2: "ATK", 3: "DEF", 4: "SPD",
    5: "RES", 6: "ACC", 7: "CR", 8: "CD",
}

# Full stat type from (stat_id, is_flat) → human-readable name
def stat_type_name(stat_id, is_flat):
    """Convert stat ID + flat flag to readable name like 'ATK%' or 'HP flat'."""
    base = STAT_NAMES.get(stat_id, f"s{stat_id}")
    if stat_id in (STAT_SPD, STAT_RES, STAT_ACC):
        return base  # always additive
    if stat_id in (STAT_CR, STAT_CD):
        return base + "%"  # always percentage (additive to stat)
    return base + ("_flat" if is_flat else "%")


# =============================================================================
# ArtifactStatKindId (game's internal artifact stat enum, 1-12)
# The mod stores StatKindId (1-8) + IsAbsolute. This table maps back.
# =============================================================================
def to_artifact_stat_kind_id(stat_id, is_flat):
    """Convert (StatKindId, IsAbsolute) to ArtifactStatKindId."""
    if stat_id == STAT_HP:
        return 1 if is_flat else 2
    if stat_id == STAT_ATK:
        return 3 if is_flat else 4
    if stat_id == STAT_DEF:
        return 5 if is_flat else 6
    if stat_id == STAT_SPD:
        return 7
    if stat_id == STAT_RES:
        return 8
    if stat_id == STAT_ACC:
        return 9
    if stat_id == STAT_CR:
        return 10
    if stat_id == STAT_CD:
        return 11
    return 0


# =============================================================================
# Set IDs (ArtifactSetKindId)
# =============================================================================
SET_NAMES = {
    0: "None",
    1: "HP", 2: "ATK", 3: "DEF", 4: "Speed", 5: "CritRate", 6: "CritDmg",
    7: "Accuracy", 8: "Resistance",
    9: "Lifesteal", 10: "Fury", 11: "Daze", 12: "Cursed", 13: "Frost",
    14: "Frenzy", 15: "Regeneration", 16: "Toxic", 17: "Shield",
    18: "Relentless", 19: "Savage", 20: "Destroy", 21: "Stun",
    22: "Cruel", 23: "Immortal", 24: "DivineSpeed", 25: "DivineCritRate",
    26: "Stalwart", 27: "DivineLife", 28: "Swift Parry", 29: "Perception",
    30: "Regeneration", 33: "Reflex", 34: "Deflection",
    35: "Resilience", 36: "Deflection", 37: "Immunity", 38: "Perception",
    40: "Guardian", 41: "Untouchable", 43: "Cruel",
    44: "Guardian", 46: "Lethal", 47: "Bolster",
    48: "Bloodthirst", 50: "Curing", 51: "Reaction",
    53: "Stoneskin", 54: "Protection", 56: "Prowess",
    57: "Forsaken", 58: "Frostbite", 59: "Affinitybreaker",
    60: "Bloodshield", 61: "Divine Offense", 62: "Vigor",
    63: "Fortitude",
}

# Set bonuses: {set_id: (pieces_needed, {stat_id: bonus_value})}
# Only commonly used sets included. Bonus is percentage for HP/ATK/DEF/SPD/CR/CD,
# flat for ACC/RES.
SET_BONUSES = {
    1: (2, {STAT_HP: 15}),
    2: (2, {STAT_ATK: 15}),
    3: (2, {STAT_DEF: 15}),
    4: (2, {STAT_SPD: 12}),
    5: (2, {STAT_CR: 12}),
    6: (2, {STAT_CD: 20}),
    7: (2, {STAT_ACC: 40}),     # flat
    8: (2, {STAT_RES: 40}),     # flat
    22: (2, {STAT_ATK: 15}),    # Cruel = ATK + ignore DEF (DEF ignore in sim)
    29: (2, {STAT_ACC: 40, STAT_SPD: 5}),  # Perception
    38: (2, {STAT_ACC: 40, STAT_SPD: 5}),  # Perception variant
    35: (2, {STAT_RES: 40, STAT_HP: 10}),  # Resilience
}

# Special set flags (tracked but bonuses applied in sim, not stat calc)
SPECIAL_SETS = {
    9: "lifesteal",      # 30% heal on damage
    10: "fury",          # +5% damage per 10% HP lost
    16: "toxic",         # 2.5% chance to place Poison per hit
    17: "shield",        # 30% HP shield at start
    18: "relentless",    # 18% extra turn chance
    19: "savage",        # Ignore 25% DEF
    20: "destroy",       # Reduce max HP on hit
    21: "stun",          # 18% stun on A1
    23: "immortal",      # +15% HP + 3% heal per turn
    24: "counterattack", # 30% chance to counter
    26: "stalwart",      # 12% AoE damage reduction
    30: "regeneration",  # 15% HP heal per turn
    36: "deflection",    # Reflect damage
    40: "guardian",      # Passive ally protect
    44: "guardian",      # Guardian variant
}


# =============================================================================
# Rarity
# =============================================================================
RARITY_NAMES = {
    1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary",
}


# =============================================================================
# Helper functions
# =============================================================================
def get_primary_value(artifact):
    """Get primary stat value + glyph from artifact dict."""
    pri = artifact.get("primary", {})
    val = pri.get("value", 0)
    glyph = pri.get("glyph", 0)
    return val + glyph


def get_total_stat(artifact, stat_id, include_glyph=True):
    """Sum a specific stat across primary + all substats of an artifact."""
    total = 0
    pri = artifact.get("primary", {})
    if pri.get("stat") == stat_id:
        total += pri.get("value", 0)
        if include_glyph:
            total += pri.get("glyph", 0)
    for sub in artifact.get("substats", []):
        if sub.get("stat") == stat_id and sub.get("flat") == pri.get("flat"):
            total += sub.get("value", 0)
            if include_glyph:
                total += sub.get("glyph", 0)
    return total
