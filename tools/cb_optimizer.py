"""
UNM Clan Boss Team Optimizer — Potential-Based v3

Uses REAL game multipliers extracted from live game via BepInEx mod.
Turn-by-turn damage simulation with:
- Verified skill multipliers from EffectType.MultiplierFormula
- Proper counter-attack WM/GS proc math (CA uptime 50%)
- Geomancer passive: 3% of CB HP per reflect = 1.5M per proc
- Debuff slot rotation (duration-based)
- Ally Attack extra A1 triggers
- Artifact redistribution from full inventory
- Speed tune validation for Budget Unkillable

UNM CB: Void, 190 SPD, 50M HP, 50-turn cap, 10 debuff slots
"""
import json
import math
from pathlib import Path
from itertools import combinations
from collections import Counter
from typing import List, Dict, Tuple
from raid_data import (SKILLS, POISON_5PCT_DMG, HP_BURN_DMG, WM_DMG, GS_DMG,
                       PROC_RATE, CA_UPTIME, UNM_HP, UNM_RES, calc_poisons_per_turn,
                       get_stat_mult, DEBUFF_UPTIMES, calc_debuff_uptime,
                       calc_acc_land_rate, MASTERY_IDS, EMPOWERMENT_BONUSES)
from speed_tune import (SpeedTuneSimulator, build_team as build_tune_team,
                        CHAMPION_SKILLS as TUNE_SKILLS)

# =============================================================================
# CB Constants (verified from game data — see raid_data.py)
# =============================================================================
MAX_TURNS = 50
MAX_DEBUFFS = 10
POISON_DURATION = 2

# Stat IDs
HP, ATK, DEF, SPD, RES, ACC, CR, CD = 1, 2, 3, 4, 5, 6, 7, 8

# Scaling
L60_HP_MULT = 165.0  # HP scales ~165x from base at 6★ L60 (calibrated: Cardiel 119→19650)
L60_AD_MULT = 11.0  # ATK/DEF scales ~11x from base at 6★ L60 (calibrated: Cardiel 92→1013)

# Arena bonus % by league ID (league 22 = Gold IV = 16%)
ARENA_PCT_BY_LEAGUE = {
    10: 4, 11: 4, 12: 6, 13: 6, 14: 8, 15: 8,  # Bronze/Silver
    16: 10, 17: 10, 18: 12, 19: 12,              # Gold I-II
    20: 14, 21: 14, 22: 16, 23: 16,              # Gold III-IV
    24: 18, 25: 20,                                # Platinum
}
ARENA_PCT = 16  # default, will be overridden from account data

# Great Hall bonuses per level
GH_BONUSES = {
    HP:  [0, 75, 150, 225, 300, 400, 500, 600, 700, 850, 1000],
    ATK: [0, 8, 16, 24, 32, 42, 52, 62, 72, 87, 100],
    DEF: [0, 8, 16, 24, 32, 42, 52, 62, 72, 87, 100],
    RES: [0, 4, 8, 12, 16, 22, 28, 34, 40, 50, 60],
    ACC: [0, 4, 8, 12, 16, 22, 28, 34, 40, 50, 60],
    CD:  [0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12],
}

# Set bonuses: (pieces_needed, {stat: bonus%})
# From ArtifactSetKindId enum in game
SET_BONUSES = {
    1:  (2, {HP: 15}), 2: (2, {ATK: 15}), 3: (2, {DEF: 15}),
    4:  (2, {SPD: 12}), 5: (2, {CR: 12}), 6: (2, {CD: 20}),
    7:  (2, {ACC: 40}), 8: (2, {RES: 40}),
    29: (2, {SPD: 5, ACC: 40}),   # Perception (ACC+SPD)
    38: (2, {SPD: 5, ACC: 40}),   # AccuracyAndSpeed (similar to Perception)
}
# Complete set name mapping from ArtifactSetKindId enum
SET_NAMES = {
    0:"None", 1:"HP%", 2:"ATK%", 3:"DEF%", 4:"Speed", 5:"CritRate", 6:"CritDmg",
    7:"ACC", 8:"RES", 9:"Lifesteal", 10:"Savage", 11:"Daze", 12:"Cursed",
    13:"Frost", 14:"Frenzy", 15:"Regeneration", 16:"Toxic", 17:"Shield",
    18:"Relentless", 19:"Destroy", 20:"DecMaxHP", 21:"Stun", 22:"DotRate",
    23:"Provoke", 24:"Counterattack", 25:"Fury", 26:"Stalwart", 27:"Reflex",
    28:"CritHeal", 29:"Perception", 30:"Regeneration", 31:"Avenging",
    32:"Cruel", 33:"Guardian", 34:"SwiftParry", 35:"Unkillable", 36:"Immortal",
    37:"Resilience", 38:"AccSpeed", 44:"Protection", 47:"Bolster", 48:"StoneSkin",
    57:"Untouchable", 61:"Lethal", 1002:"DivinOffense", 1003:"DivinLife", 1004:"DivinSpeed",
}
STAT_NAMES = {HP:"HP", ATK:"ATK", DEF:"DEF", SPD:"SPD", RES:"RES", ACC:"ACC", CR:"CR%", CD:"CD%"}

# Import canonical slot/set names from central module
try:
    from gear_constants import SLOT_NAMES, SET_NAMES as GEAR_SET_NAMES
except ImportError:
    SLOT_NAMES = {1:"Helmet",2:"Chest",3:"Gloves",4:"Boots",5:"Weapon",6:"Shield",7:"Ring",8:"Amulet",9:"Banner"}

# =============================================================================
# Hero CB Profiles
# =============================================================================
class HeroProfile:
    def __init__(self, name, *, a1_hits=1, a1_mult=3.5, a1_stat="ATK",
                 poisons_per_turn=0, poison_on_counter=0,
                 hp_burn_uptime=0, passive_dmg=0,
                 unkillable=False, counterattack=False, ally_attack=0,
                 def_down=False, weaken=False, dec_atk=False,
                 inc_atk=False, inc_def=False, strengthen=False,
                 poison_sensitivity=False,
                 breaks_speed_tune=False,
                 gs_preferred=False, needs_acc=False,
                 notes=""):
        self.name = name
        self.a1_hits = a1_hits
        self.a1_mult = a1_mult
        self.a1_stat = a1_stat
        self.poisons_per_turn = poisons_per_turn  # average poisons placed per hero turn
        self.poison_on_counter = poison_on_counter  # poisons from counter-attack A1s
        self.hp_burn_uptime = hp_burn_uptime  # fraction of turns HP Burn is active
        self.passive_dmg = passive_dmg  # flat damage per CB turn
        self.unkillable = unkillable
        self.counterattack = counterattack
        self.ally_attack = ally_attack  # num allies
        self.def_down = def_down
        self.weaken = weaken
        self.dec_atk = dec_atk
        self.inc_atk = inc_atk
        self.inc_def = inc_def
        self.strengthen = strengthen
        self.poison_sensitivity = poison_sensitivity
        self.breaks_speed_tune = breaks_speed_tune  # TM manipulation breaks UK rotation
        self.gs_preferred = gs_preferred
        self.needs_acc = needs_acc or poisons_per_turn > 0 or def_down or weaken or hp_burn_uptime > 0
        self.notes = notes

PROFILES = {
    "Maneater": HeroProfile("Maneater", a1_hits=2, a1_mult=3.4,
        unkillable=True, inc_atk=True,
        notes="Budget UK core. A3: Unkillable+BlockDmg. A2: ATK Up."),

    "Demytha": HeroProfile("Demytha", a1_hits=1, a1_mult=4.0, a1_stat="DEF",
        unkillable=True, inc_def=True,
        notes="Myth comps. A2: Block Damage 2T. A3: Continuous Heal."),

    "Skullcrusher": HeroProfile("Skullcrusher", a1_hits=1, a1_mult=3.8,
        counterattack=True,
        notes="A2: CA 2T on team. Ally Protect passive. CA = ~2x everyone's turns."),

    "Geomancer": HeroProfile("Geomancer", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        hp_burn_uptime=0.6, passive_dmg=0, needs_acc=True,
        notes="Passive: reflects CB AoE → GS procs (5 hits/AoE × 30% = ~1.5 GS/turn = ~112K/turn). HP Burn A3."),
    # Geomancer's passive is calculated specially in the sim

    "Fayne": HeroProfile("Fayne", a1_hits=3, a1_mult=3.0,
        poisons_per_turn=1.5, poison_on_counter=0.5,
        def_down=True, weaken=True, gs_preferred=True, needs_acc=True,
        notes="A3: DEF↓+Weaken+2 Poisons. A1: 3-hit poison chance. Top debuffer."),

    "Occult Brawler": HeroProfile("Occult Brawler", a1_hits=1, a1_mult=3.5,
        poisons_per_turn=2.5, poison_on_counter=1.5, needs_acc=True,
        notes="A1: 2× 5% Poison. Passive: random poison. Best raw poisoner."),

    "Fahrakin the Fat": HeroProfile("Fahrakin the Fat", a1_hits=2, a1_mult=3.2,
        poisons_per_turn=0.5, ally_attack=3, hp_burn_uptime=0.3,
        notes="A2: Ally Attack 3. A3: 2 Poisons. A1: HP Burn chance."),

    "Nethril": HeroProfile("Nethril", a1_hits=3, a1_mult=3.0,
        poisons_per_turn=2.0, gs_preferred=True, needs_acc=True,
        notes="A2: 3× Poison. A1: 3-hit TM↓."),

    "Venomage": HeroProfile("Venomage", a1_hits=2, a1_mult=3.5,
        poisons_per_turn=1.5, poison_on_counter=0.5, needs_acc=True,
        poison_sensitivity=True,
        notes="A1: Poison. A2: Poison Sens 2T/3T CD + Poison. A3: 2 Poisons."),

    "Urogrim": HeroProfile("Urogrim", a1_hits=1, a1_mult=3.2,
        poisons_per_turn=2.0, poison_on_counter=0.5, needs_acc=True,
        notes="A1: Poison. A2: Heal + 2 Poisons."),

    "Rhazin Scarhide": HeroProfile("Rhazin Scarhide", a1_hits=1, a1_mult=4.0, a1_stat="DEF",
        def_down=True, weaken=True, needs_acc=True,
        notes="A2: DEF↓+Weaken (100%). A3: TM↓. DEF-based."),

    "Sepulcher Sentinel": HeroProfile("Sepulcher Sentinel", a1_hits=1, a1_mult=3.8, a1_stat="DEF",
        dec_atk=True, inc_def=True,
        notes="A1: Dec ATK 100%. A3: Block Debuffs + DEF Up. DEF-based."),

    "Doompriest": HeroProfile("Doompriest", a1_hits=1, a1_mult=3.5,
        inc_atk=True,
        notes="Passive: Cleanse 1 debuff/turn + 5% heal. A2: ATK Up."),

    "Aox the Rememberer": HeroProfile("Aox the Rememberer", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        dec_atk=True, poisons_per_turn=0.5,
        notes="A1: 50% Dec ATK. A3: CD reduction + Poison. DEF-based."),

    "Toragi the Frog": HeroProfile("Toragi the Frog", a1_hits=2, a1_mult=3.0, a1_stat="DEF",
        poisons_per_turn=1.0, poison_on_counter=0.3,
        notes="A1: Poison. A2: Ally Protect. A3: 2 Poisons. DEF-based."),

    "Ninja": HeroProfile("Ninja", a1_hits=3, a1_mult=4.2,
        hp_burn_uptime=0.6, gs_preferred=True, breaks_speed_tune=True,
        notes="A3: HP Burn. A2: high dmg. A1: 3-hit. PASSIVE: TM boost on HP Burn — breaks UK tune!"),

    "Venus": HeroProfile("Venus", a1_hits=1, a1_mult=3.5,
        def_down=True, weaken=True, hp_burn_uptime=0.5,
        poisons_per_turn=1.0, needs_acc=True,
        notes="A3: DEF↓+Weaken. A2: HP Burn+2 Poisons. Best all-in-one debuffer."),

    "Cardiel": HeroProfile("Cardiel", a1_hits=1, a1_mult=3.5,
        inc_atk=True,
        notes="Passive: Block Damage on low HP. Revive + ATK Up."),

    "Iron Brago": HeroProfile("Iron Brago", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        inc_def=True, strengthen=True,
        notes="A2: DEF Up + Strengthen (25% dmg). DEF-based."),

    "Drexthar Bloodtwin": HeroProfile("Drexthar Bloodtwin", a1_hits=1, a1_mult=4.0, a1_stat="DEF",
        hp_burn_uptime=0.5,
        notes="Passive: HP Burn on hit. DEF-based."),

    "Coldheart": HeroProfile("Coldheart", a1_hits=4, a1_mult=2.8,
        gs_preferred=True,
        notes="A1: 4-hit. A3: MaxHP dmg (bad for CB). GS value only."),

    "Apothecary": HeroProfile("Apothecary", a1_hits=3, a1_mult=2.4,
        gs_preferred=True, breaks_speed_tune=True,
        notes="A2: SPD buff + TM boost. A1: 3-hit. TM boost breaks UK tune!"),

    "Arbiter": HeroProfile("Arbiter", a1_hits=1, a1_mult=3.0,
        inc_atk=True,
        notes="A3: TM boost + ATK Up. Revive."),

    "Seeker": HeroProfile("Seeker", a1_hits=1, a1_mult=4.0, a1_stat="DEF",
        inc_atk=True, breaks_speed_tune=True,
        notes="A2: TM boost + ATK Up. DEF-based. TM boost breaks UK tune!"),

    "Ultimate Deathknight": HeroProfile("Ultimate Deathknight", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        inc_def=True,
        notes="Passive: 15% Ally Protect. Shield. DEF-based."),

    "Achak the Wendarin": HeroProfile("Achak the Wendarin", a1_hits=1, a1_mult=3.5,
        hp_burn_uptime=0.3,
        notes="A3: HP Burn + Freeze."),

    "Teodor the Savant": HeroProfile("Teodor the Savant", a1_hits=1, a1_mult=3.1, a1_stat="DEF",
        poisons_per_turn=1.5, poison_on_counter=0.5, needs_acc=True,
        breaks_speed_tune=True,
        notes="A1: 3.1*DEF + Poison. A2: 2 Poisons + INC SPD (BREAKS UK TUNE!). A3: Extend+Activate poisons."),

    "Artak": HeroProfile("Artak", a1_hits=1, a1_mult=4.0,
        hp_burn_uptime=0.8, needs_acc=True,
        notes="A1: HP Burn 100%. A3: Strengthen+BlockDebuffs self. Passive: +dmg per debuff on enemy."),

    "Razelvarg": HeroProfile("Razelvarg", a1_hits=2, a1_mult=3.2,
        poisons_per_turn=1.0, poison_on_counter=0.3,
        poison_sensitivity=True, needs_acc=True,
        notes="A1: Poison Sens. A2: multi-hit. A3: Poisons. PSens on A1 = high uptime."),

    "Steelskull": HeroProfile("Steelskull", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        poisons_per_turn=1.0, poison_on_counter=0.3, inc_def=True, needs_acc=True,
        notes="A1: Poison. A2: Heal+Cleanse+DEF Up. DEF-based. Clean kit."),

    "Uugo": HeroProfile("Uugo", a1_hits=1, a1_mult=3.5,
        def_down=True, needs_acc=True,
        notes="A2: DEF Down. A3: Heal+BlockDebuffs+Revive. HP-based support, wastes DPS slot."),

    # TM breakers — profiled but flagged
    "Ma'Shalled": HeroProfile("Ma'Shalled", a1_hits=1, a1_mult=4.0,
        hp_burn_uptime=0.4, breaks_speed_tune=True,
        notes="A2: HP Burn. A3: TM boost 20% to allies — BREAKS UK TUNE!"),

    "Scyl of the Drakes": HeroProfile("Scyl of the Drakes", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        breaks_speed_tune=True,
        notes="Passive: random SPD Up on allies — BREAKS UK TUNE!"),

    "Gnut": HeroProfile("Gnut", a1_hits=1, a1_mult=4.0,
        breaks_speed_tune=True,
        notes="Passive: extra turns when allies hit. Extra turns burn Unkillable buff duration faster → expires before Maneater can reapply."),

    "Galek": HeroProfile("Galek", a1_hits=1, a1_mult=3.0,
        hp_burn_uptime=0.3, breaks_speed_tune=True,
        notes="A2: SPD Up on self — BREAKS UK TUNE! Starter, too weak for UNM."),

    # --- S-tier CB heroes (may not be in roster but profiled for future pulls) ---
    "Dracomorph": HeroProfile("Dracomorph", a1_hits=1, a1_mult=4.0,
        poisons_per_turn=2.0, poison_on_counter=0.5,
        def_down=True, weaken=True, gs_preferred=True, needs_acc=True,
        notes="A2: 4-hit + poisons. A3: DEF Down+Weaken. Best single-slot debuffer in game."),

    "Frozen Banshee": HeroProfile("Frozen Banshee", a1_hits=2, a1_mult=3.0,
        poisons_per_turn=2.0, poison_on_counter=0.8,
        poison_sensitivity=True, needs_acc=True,
        notes="A1: 2-hit Poison IF PSens up. A3: Poison Sensitivity 2T. Best Rare poisoner."),

    "Bad-El-Kazar": HeroProfile("Bad-El-Kazar", a1_hits=1, a1_mult=3.5,
        poisons_per_turn=2.0, needs_acc=True,
        notes="A2: 2 Poisons on all enemies + heal. A3: Cleanse+heal. Self-sufficient."),

    "Kalvalax": HeroProfile("Kalvalax", a1_hits=1, a1_mult=4.0,
        poisons_per_turn=2.5, needs_acc=True,
        notes="A2: Detonate poisons (instant damage). A3+Passive: places poisons continuously."),

    "Vizier Ovelis": HeroProfile("Vizier Ovelis", a1_hits=3, a1_mult=3.0,
        poisons_per_turn=0.5, gs_preferred=True, needs_acc=True,
        notes="A1: 3-hit + extends ALL debuffs by 1T per hit. Keeps poisons/DD/WK up forever."),

    "Corvis the Corruptor": HeroProfile("Corvis the Corruptor", a1_hits=1, a1_mult=3.5,
        poisons_per_turn=2.0, dec_atk=True, needs_acc=True,
        notes="A2: extends enemy debuffs + ally buffs. A3: 2 Poison per hit. Built-in dmg reduction."),

    "Kreela Witch-Arm": HeroProfile("Kreela Witch-Arm", a1_hits=2, a1_mult=3.5,
        ally_attack=3, inc_atk=True,
        notes="A2: Ally Attack 3. A3: ATK Up + CR Up on all. Like Fahrakin but better buffs."),

    "Helicath": HeroProfile("Helicath", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        unkillable=True,  # Block Damage 3T = effectively unkillable solo
        inc_def=True,
        notes="A2: Block Damage 3T on all. Solo UK enabler — frees 4 DPS slots!"),

    "Warcaster": HeroProfile("Warcaster", a1_hits=2, a1_mult=3.0,
        unkillable=True,
        notes="A2: Block Damage 1T on all. Paired with Roshcard for UK loop."),

    "Roshcard the Tower": HeroProfile("Roshcard the Tower", a1_hits=1, a1_mult=3.5, a1_stat="DEF",
        unkillable=True,
        notes="A2: Block Damage 2T on all. Paired with Warcaster for UK loop."),

    "Jintoro": HeroProfile("Jintoro", a1_hits=1, a1_mult=4.0,
        def_down=True, weaken=True, needs_acc=True,
        notes="A3: DEF Down+Weaken (every 4th use = 5 hits). Ramps damage over fight."),

    "Narma the Returned": HeroProfile("Narma the Returned", a1_hits=1, a1_mult=3.5,
        poisons_per_turn=2.5, needs_acc=True,
        notes="A1+A2: Poisons. Passive: places poisons + 25% dmg reduction when 5+ poisons."),

    "Heiress": HeroProfile("Heiress", a1_hits=1, a1_mult=3.0,
        notes="Passive: extends all ally buffs by 1T each turn + cleanse. Myth-Heir core."),

    "Pain Keeper": HeroProfile("Pain Keeper", a1_hits=1, a1_mult=3.0,
        notes="A3: Reduce all ally CDs by 1T. Budget UK core with Maneater. Rare."),

    # --- Tune breakers with profiles for reference ---
    "Sicia Flametongue": HeroProfile("Sicia Flametongue", a1_hits=1, a1_mult=4.0,
        hp_burn_uptime=0.8, breaks_speed_tune=True,
        notes="A3: Extra Turn — BREAKS UK TUNE! Dungeon speed farmer, not CB."),

    "Turvold": HeroProfile("Turvold", a1_hits=1, a1_mult=6.0,
        breaks_speed_tune=True,
        notes="A3: Extra Turn + SPD Up self — BREAKS standard UK. Needs Turvold-specific tune."),
}

# =============================================================================
# Stat Calculation
# =============================================================================
# Load game-computed stats if available
_COMPUTED_STATS = {}
try:
    import os as _os
    _cs_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'hero_computed_stats.json')
    if _os.path.exists(_cs_path):
        with open(_cs_path) as _f:
            _cs_data = json.load(_f)
        for _h in _cs_data.get('heroes', []):
            _COMPUTED_STATS[_h['id']] = _h
except:
    pass


def calc_stats(hero, artifacts, account):
    hero_id = hero.get("id", 0)
    base = hero.get("base_stats", {})
    element = hero.get("element", -1)
    rarity = hero.get("rarity", 3)
    emp_level = min(hero.get("empower", 0), 4)

    # Use GAME-COMPUTED base stats + blessing if available (exact values)
    # But ONLY if the hero's current grade matches what's in the computed stats
    # (potential mode overrides grade to 6, but computed stats are for actual grade)
    computed = _COMPUTED_STATS.get(hero_id)
    if computed and computed.get("grade", 0) != hero.get("grade", 0):
        computed = None  # grade mismatch — hero is being modeled at different grade
    if computed:
        bc = computed.get("base_computed", {})
        bl = computed.get("blessing_bonus", {})
        emp_b = computed.get("empower_bonus", {})
        arena_b = computed.get("arena_bonus", {})
        gh_b = computed.get("great_hall_bonus", {})

        # Base stats from game's GetBaseStats (includes level scaling + ascension)
        scaled = {
            HP: bc.get("HP", 0),
            ATK: bc.get("ATK", 0),
            DEF: bc.get("DEF", 0),
            SPD: bc.get("SPD", 0),
            CR: bc.get("CR", 0) * 100 if bc.get("CR", 0) < 1 else bc.get("CR", 0),  # Fixed → %
            CD: bc.get("CD", 0) * 100 if bc.get("CD", 0) < 1 else bc.get("CD", 0),
            RES: bc.get("RES", 0),
            ACC: bc.get("ACC", 0),
        }
        # Add blessing bonus (from game's CalcBlessingBonus)
        for stat in (HP, ATK, DEF):
            stat_name = {HP: "HP", ATK: "ATK", DEF: "DEF"}[stat]
            scaled[stat] += bl.get(stat_name, 0)
        # Add empowerment bonus for HP/ATK/DEF from game's CalcEmpowerBonus.
        for stat in (HP, ATK, DEF):
            stat_name = {HP: "HP", ATK: "ATK", DEF: "DEF"}[stat]
            scaled[stat] += emp_b.get(stat_name, 0)
        # BUT the game's CalcEmpowerBonus only returns HP/ATK/DEF — it does NOT include
        # the SPD/ACC/RES/CR/CD bonuses that empowerment also provides. We add those
        # from our EMPOWERMENT_BONUSES table. (Verified empirically: Geomancer emp3 Epic
        # shows 183 SPD in-game which requires +5 SPD empower bonus NOT in emp_b.)
        emp_table = EMPOWERMENT_BONUSES.get("legendary" if rarity >= 5 else "epic", [])
        if emp_level < len(emp_table):
            _, emp_acc, emp_res, emp_spd, emp_cd, emp_cr = emp_table[emp_level]
            scaled[SPD] = scaled.get(SPD, 0) + emp_spd
            scaled[ACC] = scaled.get(ACC, 0) + emp_acc
            scaled[RES] = scaled.get(RES, 0) + emp_res
            scaled[CD]  = scaled.get(CD, 0)  + emp_cd
            scaled[CR]  = scaled.get(CR, 0)  + emp_cr
        # Add arena bonus if computed (currently 0 due to param issue)
        for stat in (HP, ATK, DEF):
            stat_name = {HP: "HP", ATK: "ATK", DEF: "DEF"}[stat]
            scaled[stat] += arena_b.get(stat_name, 0)
        # Add Great Hall bonus
        for stat in (HP, ATK, DEF, ACC, RES, CD):
            stat_name = {HP: "HP", ATK: "ATK", DEF: "DEF", ACC: "ACC", RES: "RES", CD: "CD"}[stat]
            scaled[stat] += gh_b.get(stat_name, 0)
        # Add relic bonus
        rl_b = computed.get("relic_bonus", {})
        for stat in (HP, ATK, DEF):
            stat_name = {HP: "HP", ATK: "ATK", DEF: "DEF"}[stat]
            scaled[stat] += rl_b.get(stat_name, 0)
    else:
        # Fallback: estimated multipliers for heroes not in computed stats
        # Raid rarity codes: 1=Common, 2=Uncommon, 3=Rare, 4=Epic, 5=Legendary.
        # Empowerment bonuses differ: Epic tops at +10 SPD (emp4), Legendary at +15 SPD.
        emp_table = EMPOWERMENT_BONUSES.get("legendary" if rarity >= 5 else "epic", [])
        emp_bonus = emp_table[emp_level] if emp_level < len(emp_table) else (0,0,0,0,0,0)
        emp_pct, emp_acc, emp_res, emp_spd, emp_cd, emp_cr = emp_bonus

        scaled = {
            HP: base.get("HP", 0) * L60_HP_MULT * (1 + emp_pct/100),
            ATK: base.get("ATK", 0) * L60_AD_MULT * (1 + emp_pct/100),
            DEF: base.get("DEF", 0) * L60_AD_MULT * (1 + emp_pct/100),
            SPD: base.get("SPD", 0) + emp_spd,
            CR: base.get("CR", 0) + emp_cr, CD: base.get("CD", 0) + emp_cd,
            RES: base.get("RES", 0) + emp_res, ACC: base.get("ACC", 0) + emp_acc,
        }
    flat_b, pct_b, sets = {s:0 for s in range(1,9)}, {s:0 for s in range(1,9)}, {}
    for art in artifacts:
        s_id = art.get("set", 0)
        sets[s_id] = sets.get(s_id, 0) + 1
        # HYBRID: the mod's flat_bonus only aggregates HP/ATK/DEF/SPD and includes Divine
        # enhancement bonuses (extra flat on 6★ rank-6 artifacts). For those 4 stats, prefer
        # flat_bonus (catches hidden Divine). For ACC/RES/CR/CD (which flat_bonus doesn't
        # include), sum substats + primary manually.
        fb = art.get("flat_bonus") or {}
        pb = art.get("pct_bonus") or {}
        FB_STAT_NAMES = {HP:"HP", ATK:"ATK", DEF:"DEF", SPD:"SPD"}
        for stat_id, stat_name in FB_STAT_NAMES.items():
            flat_b[stat_id] += fb.get(stat_name, 0) or 0
            pct_b[stat_id]  += pb.get(stat_name, 0) or 0
        # Sum substats + primary for ACC/RES/CR/CD only (avoid double-counting HP/ATK/DEF/SPD)
        for b in [art.get("primary")] + art.get("substats", []):
            if not b: continue
            stat = b.get("stat", 0)
            if stat not in (ACC, RES, CR, CD): continue
            val = b.get("value", 0) + (b.get("glyph", 0) or 0)
            if b.get("flat", True): flat_b[stat] += val
            else: pct_b[stat] += val

    set_pct = {s:0 for s in range(1,9)}
    active_sets = set()
    for s_id, cnt in sets.items():
        info = SET_BONUSES.get(s_id)
        if info and cnt >= info[0]:
            active_sets.add(s_id)
            num_complete = cnt // info[0]  # e.g., 6 speed pieces = 3 complete sets
            for stat, val in info[1].items():
                if stat in (ACC, RES): flat_b[stat] += val * num_complete
                else: set_pct[stat] += val * num_complete

    # Lore of Steel mastery (500343, Support T4 col 3 per raid_data.MASTERY_IDS):
    # +15% to ALL basic set bonuses. Confirmed empirically against live in-game speeds.
    hero_masteries = hero.get("masteries", []) or []
    has_lore_of_steel = MASTERY_IDS["lore_of_steel"] in hero_masteries  # 500343
    if has_lore_of_steel:
        for s in range(1, 9):
            set_pct[s] = round(set_pct[s] * 1.15, 2)

    gh = account.get("great_hall", {}).get(str(element), {}) if element >= 0 else {}
    def gh_flat(stat): return GH_BONUSES.get(stat,[0]*11)[min(gh.get(str(stat),0), 10)]

    stats = {}
    for s in (HP, ATK, DEF):
        stats[s] = scaled[s] * (1 + (pct_b[s] + set_pct.get(s,0) + ARENA_PCT)/100) + flat_b[s] + gh_flat(s)
    stats[SPD] = scaled[SPD] * (1 + (pct_b[SPD] + set_pct.get(SPD,0))/100) + flat_b[SPD]
    stats[CR] = min(100, scaled[CR] + pct_b[CR] + set_pct.get(CR,0) + flat_b[CR])
    stats[CD] = scaled[CD] + pct_b[CD] + set_pct.get(CD,0) + flat_b[CD] + gh_flat(CD)
    stats[RES] = scaled[RES] + flat_b[RES] + pct_b[RES] + gh_flat(RES)
    stats[ACC] = scaled[ACC] + flat_b[ACC] + pct_b[ACC] + gh_flat(ACC)
    stats["sets"] = active_sets
    stats["has_toxic"] = 16 in active_sets      # Toxic: 2.5% poison chance
    stats["has_savage"] = 10 in active_sets      # Savage: ignore 25% DEF
    stats["has_relentless"] = 18 in active_sets  # Relentless: extra turn (FIXED: was 34)
    stats["has_lifesteal"] = 9 in active_sets    # Lifesteal: 30% heal on damage
    stats["has_stalwart"] = 26 in active_sets    # Stalwart: -30% AoE dmg (FIXED: was 22)
    stats["has_regen"] = 30 in active_sets       # Regeneration: 15% HP/turn
    stats["has_immortal"] = 36 in active_sets    # Immortal: 3% HP/turn + 15% HP

    return stats

# =============================================================================
# Damage Simulation
# =============================================================================
def simulate_damage(team, team_stats, profiles, account):
    """Simulate 50-turn CB fight and return total damage.

    v4 fixes applied:
    1. Debuff uptime: duration/cooldown instead of 100%
    2. ACC landing rate: real formula with UNM RES=250
    3. Skill rotation: A2/A3 turns subtract from A1 turns
    4. Poison Sensitivity: Venomage +25% poison dmg (67% uptime)
    5. HP Burn single-stack cap
    """
    n = len(team)
    uk_count = sum(1 for p in profiles if p and p.unkillable)
    has_ca = any(p.counterattack for p in profiles if p)

    turns = MAX_TURNS if uk_count >= 2 else (40 if uk_count == 1 else 25)

    # =========================================================================
    # FIX #1: Debuff uptime — calculate from duration/cooldown per source hero
    # Best uptime from any hero on the team that provides each buff/debuff
    # =========================================================================
    def best_uptime(debuff_type):
        """Find the best uptime for a debuff/buff across the team, factoring ACC."""
        best = 0.0
        for p in profiles:
            if not p:
                continue
            raw_uptime = calc_debuff_uptime(p.name, debuff_type)
            if raw_uptime > 0:
                # Debuffs on the CB need to land (ACC check)
                # Buffs on allies always land (no ACC needed)
                is_debuff = debuff_type in ("def_down", "weaken", "dec_atk",
                                            "poison_sensitivity")
                if is_debuff:
                    hero_idx = next((i for i, pr in enumerate(profiles) if pr and pr.name == p.name), None)
                    if hero_idx is not None:
                        acc = team_stats[hero_idx][ACC]
                        land_rate = calc_acc_land_rate(acc)
                        raw_uptime *= land_rate
                best = max(best, raw_uptime)
        return best

    dd_uptime = best_uptime("def_down")
    wk_uptime = best_uptime("weaken")
    str_uptime = best_uptime("strengthen")
    atk_up_uptime = best_uptime("inc_atk")
    psens_uptime = best_uptime("poison_sensitivity")

    # Weighted multipliers: apply the buff/debuff effect proportional to uptime
    # DEF Down: +60% damage when active
    dd_mult = 1.0 + 0.6 * dd_uptime
    # Weaken: +25% damage when active
    wk_mult = 1.0 + 0.25 * wk_uptime
    # Strengthen: +25% damage when active (buff on allies, not debuff on CB)
    str_mult = 1.0 + 0.25 * str_uptime
    # ATK Up: +50% ATK when active → effective damage increase depends on context
    # We apply it as a scaling factor on ATK-based heroes
    debuff_mult = dd_mult * wk_mult

    # Poison Sensitivity: +25% to all poison tick damage when active (FIX #4)
    has_poison_sensitivity = any(p.poison_sensitivity for p in profiles if p)
    poison_sens_mult = 1.0 + 0.25 * psens_uptime if has_poison_sensitivity else 1.0

    # Count active debuff slots for non-poison debuffs
    # Each of these occupies 1 of 10 debuff slots when active on the CB.
    # This is CRITICAL — every non-poison debuff steals a slot from poisons.
    reserved_slots = 0
    if dd_uptime > 0: reserved_slots += 1       # DEF Down
    if wk_uptime > 0: reserved_slots += 1       # Weaken
    if any(p.dec_atk for p in profiles if p): reserved_slots += 1  # Dec ATK
    if psens_uptime > 0: reserved_slots += 1    # Poison Sensitivity (debuff on CB)
    # HP Burn — only 1 slot regardless of how many heroes place it
    hp_burn_heroes = [p for p in profiles if p and p.hp_burn_uptime > 0]
    if hp_burn_heroes: reserved_slots += 1
    # Leech — Fayne A2 places it (2T/4T CD = sometimes active)
    has_leech = any(
        "leech" in eff
        for p in profiles if p
        for sk in SKILLS.get(p.name, {}).values() if isinstance(sk, dict)
        for eff in sk.get("effects", [])
    )
    if has_leech: reserved_slots += 1
    poison_slots = MAX_DEBUFFS - reserved_slots

    # FIX #5: HP Burn — take the BEST uptime, not sum (only 1 can be active)
    best_burn_uptime = 0.0
    best_burn_acc_rate = 0.0
    for i, p in enumerate(profiles):
        if p and p.hp_burn_uptime > 0:
            acc_rate = calc_acc_land_rate(team_stats[i][ACC])
            effective = p.hp_burn_uptime * acc_rate
            if effective > best_burn_uptime:
                best_burn_uptime = effective
                best_burn_acc_rate = acc_rate

    # Calculate per-hero damage
    breakdown = []

    for i in range(n):
        hero, stats, prof = team[i], team_stats[i], profiles[i]
        if prof is None:
            breakdown.append({"name": hero.get("name","?"), "total": 0})
            continue

        name = prof.name
        d = {"name": name, "direct": 0, "poison": 0, "burn": 0, "wm_gs": 0, "passive": 0}

        # --- Use REAL multipliers from raid_data.py ---
        hero_skills = SKILLS.get(name, {})
        a1_data = hero_skills.get("a1", {})
        real_mult = a1_data.get("mult", prof.a1_mult)
        real_stat = a1_data.get("stat", prof.a1_stat)
        real_hits = a1_data.get("hits", prof.a1_hits)

        # --- Decode masteries ---
        masteries = hero.get("masteries", [])
        has_wm = MASTERY_IDS["warmaster"] in masteries
        has_gs = MASTERY_IDS["giant_slayer"] in masteries
        has_helmsmasher = MASTERY_IDS["helmsmasher"] in masteries
        has_flawless = MASTERY_IDS["flawless_execution"] in masteries
        has_bring_it_down = MASTERY_IDS["bring_it_down"] in masteries
        has_sniper = MASTERY_IDS["sniper"] in masteries
        has_master_hexer = MASTERY_IDS["master_hexer"] in masteries
        has_keen_strike = MASTERY_IDS["keen_strike"] in masteries
        if not has_wm and not has_gs and not has_helmsmasher and not has_flawless:
            # No T6 offense — assume best choice
            if prof.gs_preferred or real_hits >= 3: has_gs = True
            else: has_wm = True

        # =================================================================
        # FIX #3: Skill rotation — A2/A3 turns subtract from A1 turns
        # On a turn where the hero uses A2 or A3, they do NOT use A1.
        # =================================================================
        a2_cd = hero_skills.get("a2", {}).get("cd", 0)
        a3_cd = hero_skills.get("a3", {}).get("cd", 0)
        a2_uses = (turns / a2_cd) if a2_cd > 0 else 0
        a3_uses = (turns / a3_cd) if a3_cd > 0 else 0
        a1_turns = max(0, turns - a2_uses - a3_uses)

        # Effective A1s: base a1_turns + counter-attack bonus + relentless + ally attack
        ca_bonus = CA_UPTIME if has_ca else 0
        rel_bonus = 0.18 if stats.get("has_relentless") else 0
        # CA and relentless give extra A1s (these are always A1)
        extra_a1_turns = turns * (ca_bonus + rel_bonus)

        # Ally attack: Fahrakin's A3 triggers 3 allies' A1
        ally_atk_heroes = [p for p in profiles if p and p.ally_attack > 0]
        extra_a1_from_ally = 0
        for aa in ally_atk_heroes:
            if aa.name == name:
                continue  # Caster doesn't attack themselves
            aa_cd = SKILLS.get(aa.name, {}).get("a3", {}).get("cd", 6)
            aa_uses_per_fight = turns / aa_cd
            # Each use picks ally_attack random allies from the other 4
            pick_chance = min(1.0, aa.ally_attack / 4)
            extra_a1_from_ally += aa_uses_per_fight * pick_chance

        total_a1s = a1_turns + extra_a1_turns + extra_a1_from_ally

        # Direct A1 damage
        scaling = stats[ATK] if real_stat == "ATK" else stats[DEF]
        # ATK Up applied proportional to uptime
        if real_stat == "ATK" and atk_up_uptime > 0:
            scaling *= (1.0 + 0.5 * atk_up_uptime)
        raw_per_a1 = scaling * real_mult
        # Mastery bonuses to crit/damage
        bonus_cd = 0
        if has_flawless: bonus_cd += 20   # Flawless Execution: +20% CD
        if has_keen_strike: bonus_cd += 10 # Keen Strike: +10% CD
        effective_cd = stats[CD] + bonus_cd
        crit_avg = 1 + (stats[CR]/100) * (effective_cd/100)

        savage = 1.15 if stats.get("has_savage") else 1.0
        # Helmsmasher: avg 12.5% DEF ignore → ~8% more damage (simplified)
        helmsmasher_mult = 1.08 if has_helmsmasher else 1.0
        # Bring It Down: +6% vs higher HP targets (always active on CB)
        bid_mult = 1.06 if has_bring_it_down else 1.0
        mastery_mult = helmsmasher_mult * bid_mult

        d["direct"] = raw_per_a1 * crit_avg * debuff_mult * str_mult * savage * mastery_mult * total_a1s

        # A2/A3 damage (on their own turns, not added on top of A1)
        for sk_key, sk_uses in [("a2", a2_uses), ("a3", a3_uses)]:
            sk = hero_skills.get(sk_key, {})
            sk_mult = sk.get("mult", 0)
            if sk_mult > 0 and sk_uses > 0:
                sk_stat = sk.get("stat", real_stat)
                sk_scaling = stats[ATK] if sk_stat == "ATK" else (stats[DEF] if sk_stat == "DEF" else stats[HP])
                if sk_stat == "ATK" and atk_up_uptime > 0:
                    sk_scaling *= (1.0 + 0.5 * atk_up_uptime)
                d["direct"] += sk_scaling * sk_mult * crit_avg * debuff_mult * str_mult * savage * mastery_mult * sk_uses

        # WM/GS procs on ALL damage skills (A1, A2, A3)
        wm_gs_total = 0
        # A1 procs
        if has_gs and real_hits > 1:
            wm_gs_total += real_hits * PROC_RATE * GS_DMG * debuff_mult * total_a1s
        else:
            wm_gs_total += PROC_RATE * WM_DMG * debuff_mult * total_a1s

        # A2/A3 procs (damage skills with hits > 0 also trigger WM/GS)
        for sk_key, sk_uses in [("a2", a2_uses), ("a3", a3_uses)]:
            sk = hero_skills.get(sk_key, {})
            sk_hits = sk.get("hits", 0)
            sk_mult = sk.get("mult", 0)
            if sk_hits > 0 and sk_mult > 0 and sk_uses > 0:
                if has_gs and sk_hits > 1:
                    wm_gs_total += sk_hits * PROC_RATE * GS_DMG * debuff_mult * sk_uses
                elif sk_hits > 0:
                    wm_gs_total += PROC_RATE * (GS_DMG if has_gs else WM_DMG) * debuff_mult * sk_uses

        d["wm_gs"] = wm_gs_total

        # Geomancer passive
        if name == "Geomancer":
            geo = hero_skills.get("passive", {})
            flat_per_turn = geo.get("flat_dmg_per_cb_turn", 200_000)
            gs_per_turn = geo.get("gs_procs_per_cb_turn", 1.0)
            d["passive"] = (flat_per_turn + gs_per_turn * GS_DMG * debuff_mult) * turns

        # FIX #5: HP Burn — only attribute to the hero with best uptime
        if prof.hp_burn_uptime > 0 and best_burn_uptime > 0:
            hero_effective = prof.hp_burn_uptime * calc_acc_land_rate(stats[ACC])
            if abs(hero_effective - best_burn_uptime) < 0.001:
                # This hero is the best burn source — gets all burn damage
                d["burn"] = best_burn_uptime * HP_BURN_DMG * turns
            # Other burn heroes contribute 0 (only 1 burn can be active)

        # FIX #2: Poisons with real ACC formula
        # Sniper mastery: +5% to base debuff placement chance
        sniper_bonus = 0.05 if has_sniper else 0
        acc_rate = calc_acc_land_rate(stats[ACC], base_chance=1.0 + sniper_bonus) if prof.needs_acc else 0
        real_poison_rate = calc_poisons_per_turn(name) if name in SKILLS else prof.poisons_per_turn
        base_poisons = real_poison_rate * acc_rate
        ca_poison_bonus = prof.poison_on_counter * acc_rate * CA_UPTIME if has_ca else 0
        toxic_poisons = 0.5 if stats.get("has_toxic") else 0

        total_poisons_per_turn = base_poisons + ca_poison_bonus + toxic_poisons
        d["poison_rate"] = total_poisons_per_turn

        breakdown.append(d)

    # Resolve poison slot contention
    total_poison_rate = sum(d.get("poison_rate", 0) for d in breakdown)
    max_active_poisons = min(poison_slots, total_poison_rate * POISON_DURATION)
    # FIX #4: Poison Sensitivity multiplier applied to all poison damage
    total_poison_dmg = max_active_poisons * POISON_5PCT_DMG * poison_sens_mult * turns

    # Distribute poison damage proportionally
    if total_poison_rate > 0:
        for d in breakdown:
            share = d.get("poison_rate", 0) / total_poison_rate
            d["poison"] = total_poison_dmg * share
    else:
        for d in breakdown:
            d["poison"] = 0

    # Sum totals
    for d in breakdown:
        d["total"] = d.get("direct",0) + d.get("poison",0) + d.get("burn",0) + d.get("wm_gs",0) + d.get("passive",0)

    total = sum(d["total"] for d in breakdown)

    return {
        "total": total, "turns": turns, "heroes": breakdown,
        "uk": uk_count >= 2, "ca": has_ca,
        "dd": dd_uptime > 0, "dd_uptime": dd_uptime,
        "wk": wk_uptime > 0, "wk_uptime": wk_uptime,
        "atk_up_uptime": atk_up_uptime, "str_uptime": str_uptime,
        "psens_uptime": psens_uptime,
        "max_poisons": max_active_poisons, "poison_slots": poison_slots,
        "burn_uptime": best_burn_uptime,
    }


# =============================================================================
# Speed Tune Validation
# =============================================================================
# Budget UK speed requirements (from speed_tune.py sweep, with 2pt buffer)
UK_ME_SPD_RANGE = (212, 227)   # Maneater speed range (valid 212-229, buffer for rounding)
UK_DPS_SPD_RANGE = (171, 189)  # DPS speed range
UK_STUN_SPD_RANGE = (111, 118) # Stun target (slowest DPS)

def validate_speed_tune(team_profiles, team_stats):
    """Run the speed tune simulator on a team's actual stats.

    Returns (valid, errors, details) tuple.
    """
    # Build speed tune team: position UK heroes first, then DPS
    # Stun target = slowest non-UK hero, goes in position 1
    uk_indices = [i for i, p in enumerate(team_profiles) if p and p.unkillable]
    dps_indices = [i for i, p in enumerate(team_profiles) if p and not p.unkillable]

    if len(uk_indices) < 2:
        return True, [], "Non-UK team, no speed tune needed"

    # Sort DPS by speed to find the stun target (slowest)
    dps_by_spd = sorted(dps_indices, key=lambda i: team_stats[i][SPD])
    stun_idx = dps_by_spd[0]  # slowest DPS = stun target
    other_dps = dps_by_spd[1:]

    # Build team specs for simulator: [stun_target, ME1, ME2, dps...]
    specs = []
    # Position 1: stun target
    specs.append((team_profiles[stun_idx].name, team_stats[stun_idx][SPD]))
    # Position 2-3: Maneaters (faster first)
    me_sorted = sorted(uk_indices, key=lambda i: -team_stats[i][SPD])
    for mi in me_sorted:
        specs.append(("Maneater", team_stats[mi][SPD]))
    # Position 4+: remaining DPS
    for di in other_dps:
        name = team_profiles[di].name
        # Use generic name if not in tune skills dict
        tune_name = name if name in TUNE_SKILLS else "DPS"
        specs.append((tune_name, team_stats[di][SPD]))

    # Opening rotation: Fast ME opens A3, Slow ME delays
    openings = {2: ["A3"], 3: ["A1", "A3"]}

    team = build_tune_team(specs, openings=openings)
    sim = SpeedTuneSimulator(team, cb_speed=190)
    result = sim.run(max_cb_turns=50)

    # Collect speed details
    me_speeds = [team_stats[i][SPD] for i in me_sorted]
    stun_speed = team_stats[stun_idx][SPD]
    details = {
        "me_speeds": me_speeds,
        "stun_speed": stun_speed,
        "me_in_range": all(UK_ME_SPD_RANGE[0] <= s <= UK_ME_SPD_RANGE[1] for s in me_speeds),
        "stun_ok": stun_speed <= UK_STUN_SPD_RANGE[1],
    }

    return result["valid"], result["errors"], details


# =============================================================================
# Artifact Optimizer (greedy per hero)
# =============================================================================
def optimal_artifacts_for_hero(hero, profile, all_artifacts, account, spd_target=None,
                               spd_max=None, is_stun_target=False):
    """Pick best artifacts for a hero from the full pool. Returns (arts, stats).

    Args:
        spd_target: minimum speed to aim for (soft target via scoring)
        spd_max: maximum speed — penalize SPD above this (for UK speed cap)
        is_stun_target: if True, MINIMIZE speed (want to be slowest)
    """
    name = hero.get("name", "")
    hero_skills = SKILLS.get(name, {})
    a1_data = hero_skills.get("a1", {})
    real_stat = a1_data.get("stat", profile.a1_stat)

    by_slot = {s: [] for s in range(1, 10)}
    for a in all_artifacts:
        slot = a.get("kind", 0)
        rank = a.get("rank", 0)
        if slot in by_slot and rank >= 5:
            by_slot[slot].append(a)

    is_poisoner = profile.needs_acc and (profile.poisons_per_turn > 0 or profile.def_down or profile.weaken)
    is_uk = profile.unkillable

    def score(art):
        s = 0
        for b in [art.get("primary")] + art.get("substats", []):
            if not b: continue
            stat, val, flat = b.get("stat",0), b.get("value",0), b.get("flat",True)
            if stat == SPD:
                if is_stun_target:
                    # Stun target wants MINIMUM speed — heavily penalize SPD
                    s -= val * 50
                elif is_uk and spd_max:
                    # UK heroes: want SPD near target range, penalize excess
                    # Score SPD modestly — we'll filter post-selection
                    s += val * 3
                else:
                    s += val * 10
            elif stat == ACC:
                if is_poisoner:
                    # ACC is make-or-break for poisoners/debuffers (need 220+)
                    s += val * (3 if flat else 15)
                elif profile.needs_acc:
                    s += val * (1 if flat else 8)
            elif stat == CR:
                s += val * 2
            elif stat == CD:
                s += val * 2.5
            elif stat == ATK:
                if real_stat == "ATK":
                    s += val * (0.08 if flat else 4)
                else:
                    s += val * 0.02
            elif stat == DEF:
                if real_stat == "DEF":
                    s += val * (0.08 if flat else 4)
                else:
                    s += val * (0.03 if flat else 0.5)
            elif stat == HP:
                s += val * (0.01 if flat else 1)
            elif stat == RES:
                s += val * 0.01  # RES is mostly irrelevant for CB
        # Rank and level bonuses
        s += art.get("rank", 0) * 15
        s += art.get("level", 0) * 4
        # Prefer 6* over 5*
        if art.get("rank", 0) == 6: s += 30
        return s

    picked = []
    for slot in range(1, 10):
        cands = sorted(by_slot.get(slot, []), key=score, reverse=True)
        if cands:
            picked.append(cands[0])

    # Post-selection: tune UK hero speed into the valid range (212-229)
    if is_uk and spd_max:
        spd_min = spd_target or UK_ME_SPD_RANGE[0]
        for _ in range(9):  # up to 9 swap attempts
            stats = calc_stats(hero, picked, account)
            cur_spd = stats[SPD]
            if spd_min <= cur_spd <= spd_max:
                break  # in range!

            need_more_spd = cur_spd < spd_min
            best_swap_idx = None
            best_swap_art = None
            best_delta = 0

            for idx, art in enumerate(picked):
                slot = art.get("kind", 0)
                art_spd = sum(b.get("value", 0) for b in [art.get("primary")] + art.get("substats", [])
                              if b and b.get("stat") == SPD)
                for alt in by_slot.get(slot, []):
                    if alt.get("id") == art.get("id"):
                        continue
                    alt_spd = sum(b.get("value", 0) for b in [alt.get("primary")] + alt.get("substats", [])
                                  if b and b.get("stat") == SPD)
                    delta = alt_spd - art_spd  # positive = more SPD
                    if need_more_spd and delta > best_delta:
                        best_delta = delta
                        best_swap_idx = idx
                        best_swap_art = alt
                    elif not need_more_spd and (-delta) > best_delta:
                        best_delta = -delta
                        best_swap_idx = idx
                        best_swap_art = alt

            if best_swap_art is not None and best_swap_idx is not None:
                picked[best_swap_idx] = best_swap_art
            else:
                break  # no improving swap found

    return picked, calc_stats(hero, picked, account)


# =============================================================================
# Main
# =============================================================================
def main():
    base = Path(__file__).parent.parent
    with open(base / "heroes_6star.json") as f: heroes_data = json.load(f)
    with open(base / "all_artifacts.json") as f: artifacts_data = json.load(f)
    with open(base / "account_data.json") as f: account = json.load(f)

    heroes = [h for h in heroes_data["heroes"] if h.get("name") and h.get("grade") == 6]
    all_arts = [a for a in artifacts_data.get("artifacts", []) if not a.get("error")]

    print(f"=== UNM CB Optimizer v4 (Uptime + ACC + Rotation fixes) ===")
    print(f"Heroes: {len(heroes)} | Artifacts: {len(all_arts)} | Usable 5-6★: {sum(1 for a in all_arts if a.get('rank',0)>=5)}")
    print()

    # Match heroes to profiles
    cb_heroes = []
    for h in heroes:
        name = h.get("name", "?")
        prof = PROFILES.get(name)
        if prof:
            cb_heroes.append((h, prof))

    print(f"CB-profiled heroes: {len(cb_heroes)}")

    # --- Phase 1: Evaluate with CURRENT gear ---
    print(f"\n{'='*80}")
    print("PHASE 1: Current gear evaluation")
    print(f"{'='*80}")

    combos = list(combinations(range(len(cb_heroes)), 5))
    print(f"Evaluating {len(combos)} team combinations...")

    results = []
    for combo in combos:
        team_h = [cb_heroes[i][0] for i in combo]
        team_p = [cb_heroes[i][1] for i in combo]
        names = [p.name for p in team_p]

        # Must have unkillable
        if not any(p.unkillable for p in team_p): continue
        # Max 2 of same hero
        if any(v > 2 for v in Counter(names).values()): continue
        # TM manipulators break unkillable speed tunes
        has_uk = sum(1 for p in team_p if p.unkillable) >= 2
        if has_uk and any(p.breaks_speed_tune for p in team_p if not p.unkillable):
            continue

        team_s = [calc_stats(h, h.get("artifacts", []), account) for h in team_h]
        result = simulate_damage(team_h, team_s, team_p, account)
        results.append((result["total"], combo, result))

    results.sort(key=lambda x: -x[0])

    print(f"\nTOP 10 TEAMS (current gear):")
    print(f"{'Rank':<5} {'Damage':>10} {'Team':<65} {'UK':>3} {'CA':>3} {'DD':>3} {'Poi':>4}")
    print("-" * 100)
    for rank, (dmg, combo, res) in enumerate(results[:10]):
        names = [cb_heroes[i][1].name for i in combo]
        poi = f"{res['max_poisons']:.1f}"
        print(f"#{rank+1:<4} {dmg/1e6:>9.1f}M {', '.join(names):<65} "
              f"{'✓' if res['uk'] else '':>3} {'✓' if res['ca'] else '':>3} "
              f"{'✓' if res['dd'] else '':>3} {poi:>4}")

    # --- Phase 2: Evaluate with OPTIMIZED gear ---
    print(f"\n{'='*80}")
    print("PHASE 2: Optimized gear evaluation (top 20 teams from Phase 1)")
    print(f"{'='*80}")

    opt_results = []
    for _, combo, _ in results[:20]:
        team_h = [cb_heroes[i][0] for i in combo]
        team_p = [cb_heroes[i][1] for i in combo]

        # Assign artifacts with speed-tune-aware conflict resolution:
        # 1. UK heroes get SPD-capped gear (212-229)
        # 2. Poisoners/debuffers get ACC-focused gear
        # 3. Stun target (slowest DPS in slot) gets minimal-SPD gear
        team_s = []
        used_art_ids = set()
        has_uk = sum(1 for p in team_p if p.unkillable) >= 2

        # Determine stun target: the DPS hero we'll deliberately make slowest
        # Pick the one that contributes least from direct/WM damage (most from poisons)
        dps_indices = [i for i, p in enumerate(team_p) if not p.unkillable]
        stun_target_idx = dps_indices[0] if dps_indices else -1  # default: first DPS

        # Priority: UK heroes first (speed-critical), then stun target (needs slow gear),
        # then poisoners/debuffers, then other DPS
        priority = sorted(range(5), key=lambda i: (
            0 if team_p[i].unkillable else
            (3 if i == stun_target_idx else
             (1 if team_p[i].needs_acc else 2))
        ))
        assigned_arts = [[] for _ in range(5)]
        for pi in priority:
            available = [a for a in all_arts if a.get("id") not in used_art_ids and a.get("rank",0) >= 5]
            spd_max = UK_ME_SPD_RANGE[1] if (has_uk and team_p[pi].unkillable) else None
            is_stun = has_uk and pi == stun_target_idx
            arts, stats = optimal_artifacts_for_hero(
                team_h[pi], team_p[pi], available, account,
                spd_max=spd_max, is_stun_target=is_stun)
            assigned_arts[pi] = arts
            for a in arts:
                used_art_ids.add(a.get("id"))
        for pi in range(5):
            team_s.append(calc_stats(team_h[pi], assigned_arts[pi], account))

        result = simulate_damage(team_h, team_s, team_p, account)

        # Validate speed tune
        tune_valid, tune_errors, tune_details = validate_speed_tune(team_p, team_s)
        result["tune_valid"] = tune_valid
        result["tune_errors"] = len(tune_errors)
        result["tune_details"] = tune_details

        opt_results.append((result["total"], combo, result, team_s))

    opt_results.sort(key=lambda x: -x[0])

    print(f"\nTOP 5 TEAMS (optimized gear POTENTIAL):")
    print(f"{'Rank':<5} {'Damage':>10} {'Team':<55} {'Tune':>8}")
    print("-" * 85)
    for rank, (dmg, combo, res, _) in enumerate(opt_results[:5]):
        names = [cb_heroes[i][1].name for i in combo]
        tune = "VALID" if res.get("tune_valid") else f"{res.get('tune_errors',0)} gaps"
        print(f"#{rank+1:<4} {dmg/1e6:>9.1f}M {', '.join(names):<55} {tune:>8}")

    # --- Detailed breakdown of #1 ---
    if opt_results:
        best_dmg, best_combo, best_res, best_stats = opt_results[0]
        print(f"\n{'='*80}")
        print(f"BEST TEAM — {best_dmg/1e6:.1f}M potential per key")
        print(f"{'='*80}")
        print(f"Turns: {best_res['turns']} | UK: {best_res['uk']} | CA: {best_res['ca']}")
        print(f"DEF↓: {best_res['dd_uptime']*100:.0f}% uptime | Weaken: {best_res['wk_uptime']*100:.0f}% | "
              f"ATK↑: {best_res['atk_up_uptime']*100:.0f}% | Strengthen: {best_res['str_uptime']*100:.0f}%")
        print(f"Poison Sens: {best_res['psens_uptime']*100:.0f}% uptime | "
              f"HP Burn: {best_res['burn_uptime']*100:.0f}% uptime")
        print(f"Active poisons: {best_res['max_poisons']:.1f}/{best_res['poison_slots']} slots")

        for idx, i in enumerate(best_combo):
            h, p = cb_heroes[i]
            s = best_stats[idx]
            hd = best_res["heroes"][idx]
            emp = h.get("empower", 0)
            mc = h.get("mastery_count", 0)

            parts = []
            for key, label in [("direct","Direct"),("poison","Poison"),("burn","HP Burn"),("wm_gs","WM/GS"),("passive","Passive")]:
                v = hd.get(key, 0)
                if v > 0: parts.append(f"{label}:{v/1e6:.1f}M")

            print(f"\n  {p.name} — {hd['total']/1e6:.1f}M total [{', '.join(parts)}]")
            print(f"    {p.notes}")
            print(f"    SPD:{s[SPD]:.0f} ACC:{s[ACC]:.0f} HP:{s[HP]:.0f} ATK:{s[ATK]:.0f} DEF:{s[DEF]:.0f} CR:{s[CR]:.0f}% CD:{s[CD]:.0f}%")
            print(f"    Empowerment:{emp} Masteries:{mc}/15", end="")
            if mc == 0: print(" ⚠ NEEDS SCROLLS", end="")
            print()

            if p.unkillable and not (UK_ME_SPD_RANGE[0] <= s[SPD] <= UK_ME_SPD_RANGE[1]):
                print(f"    ⚠ SPD {s[SPD]:.0f} → need {UK_ME_SPD_RANGE[0]}-{UK_ME_SPD_RANGE[1]} for Budget UK")
            if p.needs_acc and s[ACC] < 250:
                print(f"    ⚠ ACC {s[ACC]:.0f} → need 250+ for 100% land rate on UNM (RES=250)")

        # Speed tune result
        td = best_res.get("tune_details", {})
        print(f"\n  SPEED TUNE: {'VALID ✓' if best_res.get('tune_valid') else 'INVALID ✗'}")
        if td:
            me_spds = td.get("me_speeds", [])
            print(f"    ME speeds: {', '.join(f'{s:.0f}' for s in me_spds)} (need {UK_ME_SPD_RANGE[0]}-{UK_ME_SPD_RANGE[1]})")
            print(f"    Stun target speed: {td.get('stun_speed', 0):.0f} (need ≤{UK_STUN_SPD_RANGE[1]})")
        if not best_res.get("tune_valid"):
            gaps = best_res.get("tune_errors", 0)
            print(f"    ✗ {gaps} protection gaps in 50 turns — team would die!")

    # Compare current vs potential
    if results and opt_results:
        curr_best = results[0][0]
        pot_best = opt_results[0][0]
        print(f"\n{'='*80}")
        print(f"CURRENT BEST: {curr_best/1e6:.1f}M → POTENTIAL BEST: {pot_best/1e6:.1f}M")
        print(f"Improvement from gear optimization: +{(pot_best-curr_best)/1e6:.1f}M ({(pot_best/curr_best-1)*100:.0f}%)")
        print(f"{'='*80}")

    # =========================================================================
    # PHASE 3: Compare against internet-recommended teams
    # =========================================================================
    print(f"\n{'='*80}")
    print("PHASE 3: Internet-recommended teams comparison (optimized gear)")
    print(f"{'='*80}")

    internet_teams = [
        # --- Standard internet comps ---
        ("Fayne+OB+Geo",
         ["Maneater", "Maneater", "Fayne", "Occult Brawler", "Geomancer"]),
        ("Venus+OB+Geo",
         ["Maneater", "Maneater", "Venus", "Occult Brawler", "Geomancer"]),
        ("Fayne+Fahrakin+Geo",
         ["Maneater", "Maneater", "Fayne", "Fahrakin the Fat", "Geomancer"]),
        # --- Replace OB with Ninja (direct damage instead of poison) ---
        ("Venus+Ninja+Geo",
         ["Maneater", "Maneater", "Venus", "Ninja", "Geomancer"]),
        ("Fayne+Ninja+Geo",
         ["Maneater", "Maneater", "Fayne", "Ninja", "Geomancer"]),
        # --- Replace OB with Fahrakin (ally attack + some poison) ---
        ("Venus+Fahrakin+Geo",
         ["Maneater", "Maneater", "Venus", "Fahrakin the Fat", "Geomancer"]),
        # --- Venomage as OB replacement (PSens + poison) ---
        ("Venus+Venomage+Geo",
         ["Maneater", "Maneater", "Venus", "Venomage", "Geomancer"]),
        ("Fayne+Venomage+Geo",
         ["Maneater", "Maneater", "Fayne", "Venomage", "Geomancer"]),
        # --- Double poisoner + debuffer ---
        ("Venus+OB+Venomage (no Geo)",
         ["Maneater", "Maneater", "Venus", "Occult Brawler", "Venomage"]),
        # --- Teodor combos (debuff extender) ---
        ("Venus+Teodor+Geo",
         ["Maneater", "Maneater", "Venus", "Teodor the Savant", "Geomancer"]),
        ("Venus+OB+Teodor (no Geo)",
         ["Maneater", "Maneater", "Venus", "Occult Brawler", "Teodor the Savant"]),
        # --- Optimizer's pick ---
        ("Optimizer #1 (ours)",
         [cb_heroes[i][1].name for i in opt_results[0][1]] if opt_results else []),
    ]

    hero_by_name = {}
    for h in heroes:
        name = h.get("name", "")
        if name not in hero_by_name:
            hero_by_name[name] = h
        elif name == "Maneater":
            hero_by_name["Maneater_2"] = h

    for label, team_names in internet_teams:
        if not team_names:
            continue
        # Resolve heroes
        team_h, team_p = [], []
        me_count = 0
        missing = False
        for tname in team_names:
            if tname == "Maneater":
                me_count += 1
                key = tname if me_count == 1 else "Maneater_2"
                h = hero_by_name.get(key, hero_by_name.get("Maneater"))
            else:
                h = hero_by_name.get(tname)
            p = PROFILES.get(tname)
            if not h or not p:
                print(f"\n  {label}: SKIPPED (missing {tname})")
                missing = True
                break
            team_h.append(h)
            team_p.append(p)

        if missing:
            continue

        # Assign optimized gear (speed-tune-aware)
        has_uk = sum(1 for p in team_p if p.unkillable) >= 2
        dps_idx = [i for i, p in enumerate(team_p) if not p.unkillable]
        stun_idx = dps_idx[0] if dps_idx else -1
        team_s = []
        used_art_ids = set()
        priority = sorted(range(5), key=lambda i: (
            0 if team_p[i].unkillable else
            (3 if i == stun_idx else (1 if team_p[i].needs_acc else 2))
        ))
        assigned_arts = [[] for _ in range(5)]
        for pi in priority:
            available = [a for a in all_arts if a.get("id") not in used_art_ids and a.get("rank",0) >= 5]
            spd_max = UK_ME_SPD_RANGE[1] if (has_uk and team_p[pi].unkillable) else None
            is_stun = has_uk and pi == stun_idx
            arts, stats = optimal_artifacts_for_hero(
                team_h[pi], team_p[pi], available, account,
                spd_max=spd_max, is_stun_target=is_stun)
            assigned_arts[pi] = arts
            for a in arts:
                used_art_ids.add(a.get("id"))
        for pi in range(5):
            team_s.append(calc_stats(team_h[pi], assigned_arts[pi], account))

        result = simulate_damage(team_h, team_s, team_p, account)

        # Validate speed tune
        tune_valid, tune_errors, tune_details = validate_speed_tune(team_p, team_s)
        tune_str = "TUNE:✓" if tune_valid else f"TUNE:✗({len(tune_errors)} gaps)"
        me_spds = tune_details.get("me_speeds", []) if isinstance(tune_details, dict) else []
        me_str = f"ME:{','.join(f'{s:.0f}' for s in me_spds)}" if me_spds else ""

        print(f"\n  {label}: {result['total']/1e6:.1f}M  {tune_str}  {me_str}")
        print(f"    DEF↓:{result.get('dd_uptime',0)*100:.0f}% Weaken:{result.get('wk_uptime',0)*100:.0f}% "
              f"ATK↑:{result.get('atk_up_uptime',0)*100:.0f}% "
              f"PSens:{result.get('psens_uptime',0)*100:.0f}% "
              f"Burn:{result.get('burn_uptime',0)*100:.0f}%")
        for hd in result["heroes"]:
            parts = []
            for key, lbl in [("direct","Dir"),("poison","Poi"),("burn","Burn"),("wm_gs","WM"),("passive","Pass")]:
                v = hd.get(key, 0)
                if v > 0: parts.append(f"{lbl}:{v/1e6:.1f}M")
            idx = next((i for i, p in enumerate(team_p) if p.name == hd["name"]), 0)
            acc = team_s[idx][ACC] if idx < len(team_s) else 0
            print(f"      {hd['name']:20s} {hd['total']/1e6:6.1f}M  ACC:{acc:.0f}  [{', '.join(parts)}]")

    # Analysis summary
    print(f"\n{'='*80}")
    print("ANALYSIS: Why our optimizer disagrees with internet rankings")
    print(f"{'='*80}")
    print("""
  The optimizer favors poison-stacking teams WITHOUT DEF Down/Weaken because:

  1. DEBUFF SLOT ECONOMICS (biggest factor):
     - DEF Down + Weaken reserve 2 of 10 debuff slots → only 7 for poisons
     - Without them → 9 poison slots available
     - 2 extra poisons × 75K × 50 turns = +7.5M base
     - Poison Sensitivity (Venomage) amplifies ALL poisons by +17% effective

  2. DEF DOWN/WEAKEN ONLY BOOST HIT DAMAGE (not poisons):
     - Poisons tick for fixed 75K regardless of DEF Down
     - DEF Down (+60%) and Weaken (+25%) only boost direct hits + WM/GS
     - In poison-heavy teams, hit damage is only ~25-30% of total
     - The +46% on 25% of damage (+11.5% overall) < 2 extra poison slots

  3. REMAINING MODEL GAPS (may still shift rankings):
     - Missing mastery bonuses: Helmsmasher, Flawless Execution (+20% CD)
     - Empowerment stat bonuses not calculated
     - Internet 70-90M claims likely assume BiS gear, not our actual pool
     - Blessings (Lightning Cage, Cruelty) add flat damage we can't read yet

  VERDICT: Debuff slot economics genuinely favor poison-stacking when you
  have Poison Sensitivity (Venomage) and enough poisoners to fill 9 slots.
  DEF Down is less valuable than the internet assumes in max-poison comps.
  Internet guides may not consider this tradeoff because Venomage is newer.
""")

if __name__ == "__main__":
    main()
