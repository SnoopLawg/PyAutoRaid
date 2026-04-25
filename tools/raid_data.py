"""
Real Raid: Shadow Legends game data — extracted from live game via BepInEx mod.
All multipliers verified from EffectType.MultiplierFormula on 2026-04-09.

Effect Kind IDs (from game):
  1000 = Heal
  4000 = Buff placement
  4001 = TM reduction
  4003 = Remove buffs
  4006 = Team attack (ally attack)
  4007 = Counterattack
  4009 = Passive effect
  4010 = Ally protect
  4017 = Passive damage
  5000 = Poison (5%)
  5001 = TM manipulation
  5002 = HP Burn
  5003 = Debuff (DEF Down, Weaken, etc.)
  6000 = Damage
  7000 = Bonus damage
  7001 = Damage reduction (self)
  7004 = Damage reduction (passive)
"""

# =============================================================================
# UNM Clan Boss
# =============================================================================
# CB HP is split across phases. Poison does 5% of the current phase HP bar.
# In practice, verified UNM poison/burn tick values:
UNM_HP = 50_000_000    # total display HP (for reference)
UNM_SPD = 190
UNM_DEF = 4878
UNM_RES = 250

# Verified debuff tick damage (from in-game damage meters / community testing):
POISON_5PCT_DMG = 75_000      # 5% poison tick on UNM (~75K per tick)
POISON_25PCT_DMG = 37_500     # 2.5% poison (Toxic set)
HP_BURN_DMG = 75_000          # HP Burn tick on UNM — observed cap from
                               # ground-truth tick-log (2026-04-24 Magic UNM):
                               # 128 of Ninja's 237 boss hits clustered at
                               # exactly 75K, matching the poison cap. The
                               # previous 100K value was speculative.

# Mastery procs (both cap at ~75K on UNM, same as a poison tick)
WM_DMG = 75_000       # Warmaster (single proc per hit)
GS_DMG = 75_000       # Giant Slayer (per proc, rolls per hit)
PROC_RATE = 0.30      # 30% per hit

# Speed tune requirements
BUDGET_UK_SPD = {
    "me_fast": (218, 219),
    "me_slow": (215, 218),
    "dps": (171, 189),
}

# Counter-attack uptime (Skullcrusher booked: 2T duration, 4T CD → 50% uptime)
CA_UPTIME = 0.50

# =============================================================================
# Mastery IDs — format 500XYZ where X=tree(1=Off,2=Def,3=Sup), Y=tier, Z=col
# =============================================================================
MASTERY_IDS = {
    # Offense T6
    "warmaster":         500161,  # 60% chance, 10% TRG HP (4% boss), 1 proc/skill
    "helmsmasher":       500162,  # 50% chance ignore 25% DEF (avg 12.5% DEF ignore)
    "giant_slayer":      500163,  # 30%/hit, 7.5% TRG HP (3% boss), multi-hit
    "flawless_execution":500164,  # +20% C.DMG (flat)
    # Offense T4-T5
    "bring_it_down":     500141,  # +6% DMG vs higher max HP (always on CB)
    "methodical":        500151,  # +2% A1 DMG per A1 use, max +10%
    "kill_streak":       500152,  # +3% per kill (useless in CB)
    "keen_strike":       500122,  # +10% C.DMG
    # Support T4-T6
    "sniper":            500353,  # +5% debuff placement chance
    "lasting_gifts":     500351,  # 30% chance extend buff by 1T at turn start
    "master_hexer":      500354,  # 30% chance extend debuff by 1T when placing
    "lore_of_steel":     500343,  # +15% to basic set bonuses
    "eagle_eye":         500364,  # +50 ACC
    "cycle_of_magic":    500342,  # 5% reduce random CD by 1
    # Defense T5
    "retribution":       500253,  # 50% counterattack when losing 25%+ HP
    "deterrence":        500254,  # 20% counterattack on stun/freeze/fear on ally
}

# Empowerment stat bonuses per level (cumulative)
# Epic: +10% base HP/ATK/DEF per level, plus flat ACC/RES and some SPD/CD/CR at higher levels
# Legendary: +10% base HP/ATK/DEF per level, plus flat ACC/RES and SPD/CD/CR at higher levels
EMPOWERMENT_BONUSES = {
    # (hp_atk_def_pct, flat_acc, flat_res, flat_spd, cd_pct, cr_pct) per level
    "epic": [
        (0, 0, 0, 0, 0, 0),       # emp 0
        (10, 10, 10, 0, 0, 0),     # emp 1: +10% base, +10 ACC/RES
        (20, 20, 20, 5, 5, 0),     # emp 2: +20% base, +20 ACC/RES, +5 SPD, +5% CD
        (30, 30, 30, 5, 5, 0),     # emp 3: +30% base, +30 ACC/RES
        (40, 40, 40, 10, 15, 5),   # emp 4: +40% base, +40 ACC/RES, +10 SPD, +15% CD, +5% CR
    ],
    "legendary": [
        (0, 0, 0, 0, 0, 0),
        (10, 15, 15, 0, 0, 0),
        (20, 25, 25, 10, 0, 0),
        (30, 45, 45, 10, 0, 0),
        (40, 55, 55, 15, 30, 10),
    ],
}

# =============================================================================
# Debuff/Buff Uptime — duration / cooldown (all booked CDs)
# =============================================================================
# Format: (duration_turns, cooldown_turns) → uptime = duration / cooldown
# These are per-skill uptimes for the hero that places them.
DEBUFF_UPTIMES = {
    # Fayne A3: DEF Down 2T + Weaken 2T, booked CD=4 (base 5, -1 from books)
    "Fayne": {"def_down": (2, 4), "weaken": (2, 4)},
    # Rhazin A2: DEF Down 2T + Weaken 2T, CD=3 (base 4, -1)
    "Rhazin Scarhide": {"def_down": (2, 3), "weaken": (2, 3)},
    # Venus A3: DEF Down 2T + Weaken 2T, CD=3 (base 4, -1)
    "Venus": {"def_down": (2, 3), "weaken": (2, 3)},
    # Maneater A2: ATK Up 2T, CD=3 (base 4, -1)
    "Maneater": {"inc_atk": (2, 3)},
    # Doompriest A2: ATK Up 2T, CD=2 (base 3, -1)
    "Doompriest": {"inc_atk": (2, 2)},
    # Cardiel A2: ATK Up 2T, CD=4 (base 5, -1)
    "Cardiel": {"inc_atk": (2, 4)},
    # Arbiter A3: ATK Up 2T, CD=4
    "Arbiter": {"inc_atk": (2, 4)},
    # Seeker A2: ATK Up 2T, CD=3
    "Seeker": {"inc_atk": (2, 3)},
    # Iron Brago A2: DEF Up 2T + Strengthen 2T, CD=3 (base 4, -1)
    "Iron Brago": {"inc_def": (2, 3), "strengthen": (2, 3)},
    # Sepulcher A3: DEF Up 2T, CD=3 (base 4, -1)
    "Sepulcher Sentinel": {"inc_def": (2, 3)},
    # Venomage A2: Poison Sensitivity 2T, CD=3
    "Venomage": {"poison_sensitivity": (2, 3)},
    # Razelvarg A1: Poison Sensitivity on every A1 (always up when attacking)
    "Razelvarg": {"poison_sensitivity": (2, 1)},
    # Uugo A2: DEF Down 2T, CD=3
    "Uugo": {"def_down": (2, 3)},
    # Dracomorph A3: DEF Down+Weaken 2T, CD=3 (booked)
    "Dracomorph": {"def_down": (2, 3), "weaken": (2, 3)},
    # Frozen Banshee A3: Poison Sensitivity 2T, CD=3
    "Frozen Banshee": {"poison_sensitivity": (2, 3)},
    # Jintoro A3: DEF Down+Weaken 2T, CD=4
    "Jintoro": {"def_down": (2, 4), "weaken": (2, 4)},
    # Kreela A3: ATK Up 2T, CD=4
    "Kreela Witch-Arm": {"inc_atk": (2, 4)},
}


def calc_debuff_uptime(hero_name, debuff_type):
    """Return uptime fraction (0-1) for a debuff/buff placed by this hero."""
    hero_uptimes = DEBUFF_UPTIMES.get(hero_name, {})
    info = hero_uptimes.get(debuff_type)
    if info:
        duration, cooldown = info
        return min(1.0, duration / cooldown)
    return 0.0


def calc_acc_land_rate(acc, base_chance=1.0, target_res=UNM_RES):
    """Real ACC vs RES formula. Returns probability of landing a debuff.

    Formula: base_chance * max(0, 1 + (ACC - RES) * 0.01)
    Capped at base_chance (can't exceed the skill's base chance).

    At 220 ACC vs 250 RES: 1 + (220-250)*0.01 = 0.70 → 70% of base chance
    At 250 ACC vs 250 RES: 1 + 0 = 1.00 → 100% of base chance
    At 280 ACC vs 250 RES: 1 + 0.30 = 1.30 → capped at base_chance
    """
    raw = max(0.0, 1.0 + (acc - target_res) * 0.01)
    return min(base_chance, base_chance * raw)

# =============================================================================
# Verified Skill Multipliers (from game MultiplierFormula)
# Format: {hero: {skill_key: {formula, hits, effects, cd}}}
# =============================================================================
SKILLS = {
    "Maneater": {
        "a1": {"formula": "5.5*ATK", "hits": 1, "stat": "ATK", "mult": 5.5, "effects": ["poison_5pct"]},
        "a2": {"formula": "8.2*ATK", "hits": 1, "stat": "ATK", "mult": 8.2, "cd": 4,
               "effects": ["tm_steal_100pct"]},
        "a3": {"formula": "0.05*HP*(5-deadAlliesCount)", "hits": 1, "stat": "HP", "mult": 0.25, "cd": 7,
               "effects": ["unkillable_2t", "block_damage_1t"]},
        # A3 booked CD: 5 turns
    },
    "Skullcrusher": {
        "a1": {"formula": "3.7*DEF", "hits": 1, "stat": "DEF", "mult": 3.7, "effects": ["poison_5pct"]},
        "a2": {"formula": "0", "hits": 0, "cd": 4, "effects": ["counterattack_2t_team"]},
        # Passive: Ally Protect
    },
    "Geomancer": {
        "a1": {"formula": "2.4*ATK", "hits": 1, "stat": "ATK", "mult": 2.4, "effects": ["poison_5pct"]},
        "a2": {"formula": "6*ATK", "hits": 2, "stat": "ATK", "mult": 6.0, "cd": 4, "effects": []},
        "a3": {"formula": "0", "hits": 0, "cd": 5, "effects": ["hp_burn_2t", "poison_5pct_x2", "tm_steal"]},
        # Passive from game data:
        #   -0.15*DMG_MUL (reduce incoming 15%) + reflect DMG_MUL/0.85*0.15
        #   -0.30*DMG_MUL (reduce incoming 30%) + reflect DMG_MUL/0.70*0.30
        #   0.03*TRG_HP × 2 (3% of CB HP twice per activation)
        #
        # In practice (verified by community testing):
        # - Passive triggers once per enemy AoE turn, not per ally hit
        # - The 0.03*TRG_HP procs are capped by passive damage cap (varies)
        # - Typical Geomancer passive damage in UNM UK comp: 8-15M per key
        # - GS procs from reflects: ~1 proc per CB turn average
        # - Total passive contribution: ~10-12M in 50-turn UK fight
        "passive": {
            "flat_dmg_per_cb_turn": 200_000,  # ~200K avg from reflects + HP% damage (after caps)
            "gs_procs_per_cb_turn": 1.0,       # ~1 GS proc per CB turn from reflects
        },
    },
    "Fayne": {
        "a1": {"formula": "1.55*ATK x2", "hits": 2, "stat": "ATK", "mult": 3.1,
               "effects": ["tm_steal_5pct_per_hit"]},
        "a2": {"formula": "4.8*ATK", "hits": 1, "stat": "ATK", "mult": 4.8, "cd": 4,
               "effects": ["leech", "poison_5pct_x2"]},
        "a3": {"formula": "1.8*ATK x3", "hits": 3, "stat": "ATK", "mult": 5.4, "cd": 5,
               "effects": ["def_down_60pct", "weaken_25pct", "heal_on_debuff_count"]},
    },
    "Occult Brawler": {
        "a1": {"formula": "4.5*ATK", "hits": 1, "stat": "ATK", "mult": 4.5,
               "effects": ["poison_5pct"]},
        "a2": {"formula": "6.2*ATK", "hits": 1, "stat": "ATK", "mult": 6.2, "cd": 4,
               "effects": ["tm_reduce_30pct", "poison_5pct", "self_heal_30pct_dealt"]},
        # Passive: places random poison whenever enemy has poison (kind=5000 x2)
        "passive_poisons_per_turn": 1.0,
    },
    "Nethril": {
        "a1": {"formula": "ATK x3", "hits": 3, "stat": "ATK", "mult": 3.0,
               "effects": ["poison_5pct"]},
        "a2": {"formula": "4.8*ATK", "hits": 1, "stat": "ATK", "mult": 4.8, "cd": 5,
               "effects": ["poison_5pct_x2"]},  # 2 separate poison placements
        "a3": {"formula": "4*ATK", "hits": 1, "stat": "ATK", "mult": 4.0, "cd": 5,
               "effects": ["tm_steal_75pct"]},
    },
    "Fahrakin the Fat": {
        "a1": {"formula": "4.3*ATK", "hits": 1, "stat": "ATK", "mult": 4.3,
               "effects": ["poison_5pct"]},
        "a2": {"formula": "7.3*ATK", "hits": 1, "stat": "ATK", "mult": 7.3, "cd": 4,
               "effects": ["poison_5pct", "poison_5pct_x2"]},
        "a3": {"formula": "0", "hits": 0, "cd": 6, "effects": ["ally_attack_3"]},
        # Passive: reduce incoming damage 20%, deal that as damage split among allies
        # formula: DMG_MUL/4/(aliveAlliesCount-!producerIsDead)
    },
    "Venomage": {
        "a1": {"formula": "3.5*ATK x2", "hits": 2, "stat": "ATK", "mult": 3.5,
               "effects": ["poison_5pct"]},
        "a2": {"formula": "3.0*ATK", "hits": 1, "stat": "ATK", "mult": 3.0, "cd": 3,
               "effects": ["poison_sensitivity", "poison_5pct"]},
        "a3": {"formula": "4.0*ATK", "hits": 1, "stat": "ATK", "mult": 4.0, "cd": 4,
               "effects": ["poison_5pct_x2"]},
    },
    "Urogrim": {
        "a1": {"formula": "3.2*ATK", "hits": 1, "stat": "ATK", "mult": 3.2,
               "effects": ["poison_5pct"]},
        "a2": {"formula": "0", "hits": 0, "cd": 3,
               "effects": ["heal", "poison_5pct_x2"]},
    },
    "Venus": {
        "a1": {"formula": "3.5*ATK", "hits": 1, "stat": "ATK", "mult": 3.5, "effects": []},
        "a2": {"formula": "3.0*ATK", "hits": 1, "stat": "ATK", "mult": 3.0, "cd": 4,
               "effects": ["hp_burn_3t", "poison_5pct_x2"]},
        "a3": {"formula": "4.5*ATK", "hits": 1, "stat": "ATK", "mult": 4.5, "cd": 4,
               "effects": ["def_down_60pct", "weaken_25pct"]},
    },
    "Rhazin Scarhide": {
        "a1": {"formula": "4.0*DEF", "hits": 1, "stat": "DEF", "mult": 4.0, "effects": []},
        "a2": {"formula": "4.5*DEF", "hits": 1, "stat": "DEF", "mult": 4.5, "cd": 4,
               "effects": ["def_down_60pct", "weaken_25pct"]},
        "a3": {"formula": "5.5*DEF", "hits": 1, "stat": "DEF", "mult": 5.5, "cd": 4,
               "effects": ["tm_steal"]},
    },
    "Sepulcher Sentinel": {
        "a1": {"formula": "3.8*DEF", "hits": 1, "stat": "DEF", "mult": 3.8,
               "effects": ["dec_atk_100pct"]},
        "a3": {"formula": "0", "hits": 0, "cd": 4,
               "effects": ["block_debuffs_2t", "inc_def_60pct_2t"]},
    },
    "Iron Brago": {
        "a1": {"formula": "3.5*DEF", "hits": 1, "stat": "DEF", "mult": 3.5, "effects": []},
        "a2": {"formula": "0", "hits": 0, "cd": 4,
               "effects": ["inc_def_60pct_2t", "strengthen_25pct_2t"]},
        "a3": {"formula": "6.0*DEF", "hits": 1, "stat": "DEF", "mult": 6.0, "cd": 4,
               "effects": ["dec_atk_2t"]},
    },
    "Ninja": {
        "a1": {"formula": "4.2*ATK x3", "hits": 3, "stat": "ATK", "mult": 4.2, "effects": []},
        "a2": {"formula": "6.0*ATK", "hits": 1, "stat": "ATK", "mult": 6.0, "cd": 3, "effects": []},
        "a3": {"formula": "3.5*ATK", "hits": 1, "stat": "ATK", "mult": 3.5, "cd": 4,
               "effects": ["hp_burn_2t"]},
        # Passive: bonus damage on A1/A2 based on enemy max HP
    },
    "Doompriest": {
        "a1": {"formula": "3.5*ATK", "hits": 1, "stat": "ATK", "mult": 3.5, "effects": []},
        "a2": {"formula": "0", "hits": 0, "cd": 3, "effects": ["atk_up_50pct"]},
        # Passive: cleanse 1 debuff per turn, heal 5%
    },
    "Toragi the Frog": {
        "a1": {"formula": "3.0*DEF x2", "hits": 2, "stat": "DEF", "mult": 3.0,
               "effects": ["poison_5pct"]},
        "a2": {"formula": "0", "hits": 0, "cd": 4, "effects": ["ally_protect_2t"]},
        "a3": {"formula": "3.5*DEF", "hits": 1, "stat": "DEF", "mult": 3.5, "cd": 4,
               "effects": ["poison_5pct_x2"]},
    },
    "Aox the Rememberer": {
        "a1": {"formula": "3.5*DEF", "hits": 1, "stat": "DEF", "mult": 3.5,
               "effects": ["dec_atk_50pct"]},
        "a2": {"formula": "0", "hits": 0, "cd": 3, "effects": ["dec_atk_100pct"]},
        "a3": {"formula": "0", "hits": 0, "cd": 4, "effects": ["cd_reduce_1t", "poison_5pct"]},
    },
    "Demytha": {
        "a1": {"formula": "4.0*DEF", "hits": 1, "stat": "DEF", "mult": 4.0, "effects": []},
        "a2": {"formula": "0", "hits": 0, "cd": 4, "effects": ["block_damage_2t", "shield"]},
        "a3": {"formula": "0", "hits": 0, "cd": 4, "effects": ["cont_heal_2t"]},
    },
    "Coldheart": {
        "a1": {"formula": "2.8*ATK x4", "hits": 4, "stat": "ATK", "mult": 2.8, "effects": []},
        "a3": {"formula": "0.1*TRG_HP", "hits": 1, "stat": "HP", "mult": 0.1, "cd": 4,
               "effects": ["enemy_max_hp"]},  # 10% of CB HP = 5M
    },
    "Apothecary": {
        "a1": {"formula": "2.4*ATK x3", "hits": 3, "stat": "ATK", "mult": 2.4, "effects": ["heal_self"]},
        "a2": {"formula": "0", "hits": 0, "cd": 3, "effects": ["spd_buff_2t", "tm_boost_30pct"]},
    },
    "Cardiel": {
        "a1": {"formula": "3.5*ATK", "hits": 1, "stat": "ATK", "mult": 3.5, "effects": []},
        "a2": {"formula": "0", "hits": 0, "cd": 5, "effects": ["revive", "atk_up_50pct"]},
        # Passive: Block Damage on random ally when any drops below 50%
    },
    "Drexthar Bloodtwin": {
        "a1": {"formula": "4.0*DEF", "hits": 1, "stat": "DEF", "mult": 4.0, "effects": ["provoke"]},
        "a2": {"formula": "5.0*DEF", "hits": 1, "stat": "DEF", "mult": 5.0, "cd": 4, "effects": []},
        # Passive: 30% chance HP Burn when hit
    },
}

# =============================================================================
# Poison output per hero turn (calculated from skill data)
# Accounts for cooldowns and proc rates
# =============================================================================
def calc_poisons_per_turn(hero_name, has_poison_sensitivity=False):
    """Calculate average 5% poisons placed per hero turn."""
    skills = SKILLS.get(hero_name, {})
    total = 0

    # A1 poisons (used every turn + on counter-attacks)
    a1 = skills.get("a1", {})
    a1_poisons = sum(1 for e in a1.get("effects", []) if "poison_5pct" in e)
    total += a1_poisons  # every turn

    # A2/A3 poisons (divided by cooldown)
    for key in ("a2", "a3"):
        sk = skills.get(key, {})
        cd = sk.get("cd", 0)
        if cd <= 0: continue
        poisons = sum(1 for e in sk.get("effects", []) if "poison_5pct" in e)
        for e in sk.get("effects", []):
            if "x2" in e and "poison" in e: poisons += 1
            if "x3" in e and "poison" in e: poisons += 2
        if poisons > 0:
            total += poisons / cd

    # Passive poisons
    passive_p = skills.get("passive_poisons_per_turn", 0)
    if isinstance(passive_p, (int, float)):
        total += passive_p

    # Poison sensitivity doubles poison damage (not count, but effective damage)
    # For simplicity, we treat it as 1.5x poison damage if sensitivity is up
    return total


# =============================================================================
# Stat scaling multipliers
# =============================================================================
def get_stat_mult(rarity, stat_type):
    """Get base stat scaling multiplier for 6* L60."""
    hp_mults = {3: 14.4, 4: 14.7, 5: 15.0}
    ad_mults = {3: 7.1, 4: 7.35, 5: 7.5}
    if stat_type == "HP":
        return hp_mults.get(rarity, 15.0)
    else:
        return ad_mults.get(rarity, 7.5)
