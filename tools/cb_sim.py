"""
UNM Clan Boss Turn-by-Turn Damage Simulator — Game-Accurate

Simulates every tick, every skill use, every debuff placement, every poison tick.
Replaces the averaging model with exact deterministic (or Monte Carlo) simulation.

Mechanics modeled:
- Tick-based turn meter (TM += speed, threshold 1000, overflow preserved)
- 10-slot debuff bar on CB with exact placement/expiry
- Buff tracking per champion with duration ticking
- CB 3-turn cycle: AoE → AoE → Stun (Void)
- Skill rotations with cooldowns and opening sequences
- WM/GS procs (60% once for WM, 30% per hit for GS)
- Counter-attack (extra A1 on CB AoE)
- Ally attack (triggers random allies' A1)
- Geomancer passive (reflects on CB AoE)
- Debuff extension (Vizier, Corvis, Master Hexer)
- Poison Sensitivity (+25% all poison ticks)
- ACC vs RES landing rate

Usage:
    python3 tools/cb_sim.py                          # simulate best team
    python3 tools/cb_sim.py --team "ME,ME,Venus,OB,Geo"
    python3 tools/cb_sim.py --verbose                # turn-by-turn log
    python3 tools/cb_sim.py --monte-carlo 100        # RNG mode, N runs
"""
import json
import re
import random
from pathlib import Path
from copy import deepcopy
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from raid_data import (SKILLS, POISON_5PCT_DMG, HP_BURN_DMG, WM_DMG, GS_DMG,
                       PROC_RATE, CA_UPTIME, UNM_HP, UNM_DEF, UNM_RES,
                       MASTERY_IDS, calc_acc_land_rate)

# =============================================================================
# Constants
# =============================================================================
TM_THRESHOLD = 1000
MAX_CB_TURNS = 50
MAX_DEBUFF_SLOTS = 10

WM_PROC_RATE = 0.60   # Warmaster: 60% once per skill
GS_PROC_RATE = 0.30   # Giant Slayer: 30% per hit
LEECH_HEAL_RATE = 0.10  # Leech debuff: attackers heal 10% of damage dealt

# Force Affinity damage caps — empirical observation from live UNM Force-Affinity runs
# (clan has already beaten CB; he's in "infinite HP / capped-damage" endless mode).
# Per-skill damage to CB is capped at:
#   - ~250K  for big AoE / A3 skills (Maneater A2, Venomage A3, etc.)
#   - ~175K  for single-target big hits
#   - ~75K   for A1 / basic skills
# Observed as suspiciously round numbers in per-turn damage deltas.
# These caps are applied AFTER damage calc, before WM/GS/passive add-ons.
# Override via CBSimulator(force_affinity=False) to disable.
FA_CAP_BIG     = 250_000   # big AoE / A3
FA_CAP_MEDIUM  = 175_000   # large single-target
FA_CAP_SMALL   =  75_000   # A1 baseline
FA_CAP_DOT     =  75_000   # per-tick DoT cap (HP Burn / Poison tick)

# Affinity system: Magic=1, Force=2, Spirit=3, Void=4
# Weak hit: 20-35% damage reduction AND 35% chance debuffs don't land
# Strong hit: 20-30% damage increase
WEAK_AFFINITY = {1: 2, 2: 3, 3: 1}  # Magic weak vs Force, Force weak vs Spirit, Spirit weak vs Magic
STRONG_AFFINITY = {1: 3, 2: 1, 3: 2}  # Magic strong vs Spirit, etc.
WEAK_HIT_DMG_MULT = 0.70      # 30% damage reduction on weak hit
WEAK_HIT_DEBUFF_FAIL = 0.35   # 35% chance debuff doesn't land on weak hit
STRONG_HIT_DMG_MULT = 1.30    # 30% damage increase on strong hit

HP, ATK, DEF, SPD, RES, ACC, CR, CD = 1, 2, 3, 4, 5, 6, 7, 8

CB_VOID_PATTERN = ["aoe1", "aoe2", "stun"]


# =============================================================================
# Debuff Bar (10 slots on the Clan Boss)
# =============================================================================
@dataclass
class DebuffSlot:
    debuff_type: str   # "poison_5pct", "hp_burn", "def_down", "weaken", "poison_sens", "leech", "dec_atk"
    remaining: int     # turns remaining (ticks at start of CB turn)
    source: str = ""   # hero who placed it (for damage attribution)


class DebuffBar:
    def __init__(self):
        self.slots: List[DebuffSlot] = []

    def add(self, debuff_type: str, duration: int, source: str = "") -> bool:
        """Add a debuff. Returns False if bar is full."""
        if len(self.slots) >= MAX_DEBUFF_SLOTS:
            return False
        self.slots.append(DebuffSlot(debuff_type, duration, source))
        return True

    def tick(self) -> List[DebuffSlot]:
        """Tick all durations at start of CB turn. Returns expired slots."""
        expired = []
        remaining = []
        for s in self.slots:
            s.remaining -= 1
            if s.remaining <= 0:
                expired.append(s)
            else:
                remaining.append(s)
        self.slots = remaining
        return expired

    def has(self, debuff_type: str) -> bool:
        return any(s.debuff_type == debuff_type for s in self.slots)

    def count(self, debuff_type: str) -> int:
        return sum(1 for s in self.slots if s.debuff_type == debuff_type)

    def extend_all(self, turns: int = 1):
        """Extend all debuffs by N turns (Vizier/Corvis mechanic)."""
        for s in self.slots:
            s.remaining += turns

    def is_full(self) -> bool:
        return len(self.slots) >= MAX_DEBUFF_SLOTS

    def summary(self) -> str:
        counts = {}
        for s in self.slots:
            counts[s.debuff_type] = counts.get(s.debuff_type, 0) + 1
        return ", ".join(f"{v}x{k}" for k, v in sorted(counts.items()))

    def __len__(self):
        return len(self.slots)


# =============================================================================
# Damage Tracker (per champion)
# =============================================================================
@dataclass
class DamageTracker:
    direct: float = 0.0
    poison: float = 0.0
    hp_burn: float = 0.0
    wm_gs: float = 0.0
    passive: float = 0.0

    @property
    def total(self):
        return self.direct + self.poison + self.hp_burn + self.wm_gs + self.passive


# =============================================================================
# Skill Effect System
# =============================================================================
@dataclass
class SkillEffect:
    """One discrete effect a skill performs."""
    effect_type: str    # "debuff", "buff", "extend_debuffs", "extend_buffs",
                        # "ally_attack", "cd_reduce", "conditional_debuff"
    params: dict = field(default_factory=dict)


@dataclass
class SimSkill:
    """A champion's skill with damage and effect data."""
    name: str                # "A1", "A2", "A3"
    base_cd: int = 0         # 0 = no cooldown (A1)
    current_cd: int = 0
    multiplier: float = 0.0  # total damage multiplier
    scaling_stat: str = "ATK"
    hit_count: int = 1
    effects: List[SkillEffect] = field(default_factory=list)
    # Buff effects on team (simple buffs handled directly)
    team_buffs: List[Tuple[str, int]] = field(default_factory=list)  # (buff_name, duration)
    team_tm_fill: float = 0.0  # fraction of TM bar to fill for all allies (e.g., 0.30 = 30%)
    self_tm_fill: float = 0.0  # fraction of TM bar to fill for self on use (e.g., Ninja A1: 0.15)
    grants_extra_turn: bool = False  # kind=4007: immediately get another turn after use
    ignore_def: float = 0.0   # fraction of DEF to ignore (Ninja A3: 0.5, OB A2: 0.3)


# =============================================================================
# Sim Champion
# =============================================================================
@dataclass
class SimChampion:
    name: str
    speed: float
    position: int
    stats: Dict[int, float]  # {ATK: val, DEF: val, ...}
    base_speed: float = 0.0   # Unmodified base speed (for speed buff/debuff: ±30% of base)
    element: int = 4          # 1=Magic, 2=Force, 3=Spirit, 4=Void
    skills: List[SimSkill] = field(default_factory=list)
    tm: float = 0.0
    buffs: Dict[str, int] = field(default_factory=dict)
    buffs_new: set = field(default_factory=set)  # DWJ isAddedThisTurn — skip first tick
    is_stunned: bool = False
    turns_taken: int = 0
    damage: DamageTracker = field(default_factory=DamageTracker)
    opening: List[str] = field(default_factory=list)

    # Mastery flags
    has_wm: bool = False
    has_gs: bool = False
    has_helmsmasher: bool = False
    has_flawless_exec: bool = False
    has_bring_it_down: bool = False
    has_sniper: bool = False
    has_master_hexer: bool = False
    has_retribution: bool = False

    # Special flags
    is_geomancer: bool = False
    is_counterattack_provider: bool = False
    is_dead: bool = False
    death_turn: int = 0

    # HP tracking for non-UK survival
    current_hp: float = 0.0
    max_hp: float = 0.0
    has_lifesteal: bool = False

    # Passive abilities (detected from game data)
    has_passive_ally_protect: bool = False   # Skullcrusher: permanent Ally Protect
    has_passive_dmg_reduction: float = 0.0  # Cardiel: -20%, Geomancer: -15%/-30%
    has_passive_extra_turns: bool = False    # Gnut: extra turns when allies hit
    has_passive_buff_extension: bool = False # Heiress: extends all ally buffs by 1T each turn
    a1_self_heal_pct: float = 0.0           # Ma'Shalled: 0.3 = 30% of dealt damage
    a1_target_heal_pct: float = 0.0         # Cardiel: 0.075 = 7.5% of target's max HP

    # PassiveChangeStats (kind=4013) — dynamic stat scaling
    combo_counter: int = 0                  # Ninja: tracks consecutive hits on boss
    combo_atk_pct: float = 0.0             # Ninja: +10% ATK per combo on bosses
    combo_cd_pct: float = 0.0              # Ninja: +10% CD per combo on bosses
    burn_stat_pct: float = 0.0             # Sicia: +3% ATK per HP Burn on field
    burn_dmg_reduction: float = 0.0        # Sicia: 3% dmg reduction per HP Burn

    def has_buff(self, name):
        return self.buffs.get(name, 0) > 0

    def add_buff(self, name, duration):
        self.buffs[name] = max(self.buffs.get(name, 0), duration)
        self.buffs_new.add(name)  # mark as new — won't tick until next turn

    def tick_buffs(self):
        # DWJ: isAddedThisTurn — buffs added since last tick don't decrement
        expired = []
        for b, d in self.buffs.items():
            if b in self.buffs_new:
                continue  # skip first tick (just applied)
            if d <= 1:
                expired.append(b)
            else:
                self.buffs[b] = d - 1
        for b in expired:
            del self.buffs[b]
        self.buffs_new.clear()  # next tick will decrement normally

    def tick_cooldowns(self):
        for sk in self.skills:
            if sk.current_cd > 0:
                sk.current_cd -= 1


# =============================================================================
# Skill Data — loaded from game-extracted hero_profiles_game.json
# =============================================================================
def _eff(effect_type, **params):
    return SkillEffect(effect_type, params)

try:
    from load_game_profiles import load_profiles as _load_game_profiles
    SKILL_DATA, SKILL_EFFECTS, PASSIVE_DATA = _load_game_profiles()
except ImportError:
    SKILL_DATA, SKILL_EFFECTS, PASSIVE_DATA = {}, {}, {}

DEFAULT_SKILL_DATA = {
    "A1": {"mult": 3.5, "stat": "ATK", "hits": 1, "cd": 0},
    "A2": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 4},
    "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 5},
}

_OLD_SKILL_EFFECTS = {  # DEAD CODE — kept for reference only
    "Maneater": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],
        "A2": [],  # ATK Up handled via team_buffs
        "A3": [],  # Unkillable + BD handled via team_buffs
    },
    "Venus": {
        "A1": [],
        "A2": [_eff("debuff", debuff="hp_burn", duration=3, chance=0.75),
               _eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
        "A3": [_eff("debuff", debuff="def_down", duration=2, chance=1.0),
               _eff("debuff", debuff="weaken", duration=2, chance=1.0)],
    },
    "Fayne": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5, per_hit=True)],
        "A2": [_eff("debuff", debuff="leech", duration=2, chance=0.75),
               _eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
        "A3": [_eff("debuff", debuff="def_down", duration=2, chance=1.0),
               _eff("debuff", debuff="weaken", duration=2, chance=1.0)],
    },
    "Occult Brawler": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.75)],
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.75)],
        "passive": [_eff("debuff", debuff="poison_5pct", duration=2, chance=1.0)],  # per turn
    },
    "Geomancer": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],
        "A2": [],
        "A3": [_eff("debuff", debuff="hp_burn", duration=2, chance=0.75),
               _eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.5)],
    },
    "Frozen Banshee": {
        "A1": [_eff("conditional_debuff", debuff="poison_5pct", duration=2, chance=0.75,
                     requires="poison_sensitivity", per_hit=True)],
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],
        "A3": [_eff("debuff", debuff="poison_sensitivity", duration=2, chance=1.0)],
    },
    "Venomage": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5, per_hit=True)],
        "A2": [_eff("debuff", debuff="poison_sensitivity", duration=2, chance=1.0),
               _eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],
        "A3": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
    },
    "Razelvarg": {
        "A1": [_eff("debuff", debuff="poison_sensitivity", duration=2, chance=0.75),
               _eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],
        "A2": [],
        "A3": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.5)],
    },
    "Teodor the Savant": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],  # 3.1*DEF + Poison
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
        # A2 also places Inc SPD on allies — BREAKS speed tunes!
        # WARNING: Teodor does NOT have Poison Sensitivity (web research was wrong)
        "A3": [_eff("extend_debuffs_poison_burn", turns=1),  # kind 5008: extend poisons+burns
               _eff("activate_dots"),                         # kind 9002: trigger all DoT debuffs (poisons + HP burns)
               _eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],  # also places 1 poison
    },
    "Corvis the Corruptor": {
        "A1": [_eff("debuff", debuff="dec_atk", duration=2, chance=0.75)],
        "A2": [_eff("extend_debuffs", turns=1),   # hit 1: extend enemy debuffs
               _eff("extend_buffs", turns=1)],     # hit 2: extend ally buffs
        "A3": [_eff("debuff", debuff="poison_5pct", duration=2, count=4, chance=0.5)],
    },
    "Vizier Ovelis": {
        "A1": [_eff("extend_debuffs", turns=1, per_hit=True)],  # 3 hits = +3T
        "A2": [_eff("debuff", debuff="dec_atk", duration=2, chance=1.0),
               _eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.5)],
    },
    "Skullcrusher": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],
        "A2": [],  # CA via team_buffs. Ally Protect is PASSIVE (permanent, not from skill).
    },
    "Fahrakin the Fat": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, count=3, chance=0.5)],
        "A3": [_eff("ally_attack", count=3)],
    },
    "Nethril": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5, per_hit=True)],
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
        "A3": [],
    },
    "Urogrim": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.75)],
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
    },
    "Toragi the Frog": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5, per_hit=True)],
        "A2": [],  # ally protect, not relevant to damage sim
        "A3": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
    },
    "Rhazin Scarhide": {
        "A1": [],
        "A2": [_eff("debuff", debuff="def_down", duration=2, chance=1.0),
               _eff("debuff", debuff="weaken", duration=2, chance=1.0)],
        "A3": [],
    },
    "Iron Brago": {
        "A1": [],
        "A2": [],  # DEF Up + Strengthen handled via team_buffs
        "A3": [_eff("debuff", debuff="dec_atk", duration=2, chance=1.0)],
    },
    "Sepulcher Sentinel": {
        "A1": [_eff("debuff", debuff="dec_atk", duration=2, chance=1.0)],
        "A3": [],  # block debuffs + DEF Up via team_buffs
    },
    "Artak": {
        "A1": [_eff("debuff", debuff="hp_burn", duration=2, chance=1.0)],
        "A2": [],
        "A3": [],  # self buffs
    },
    "Steelskull": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],
        "A2": [],  # heal + DEF Up via team_buffs
    },
    "Dracomorph": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.75, per_hit=True)],
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
        "A3": [_eff("debuff", debuff="def_down", duration=2, chance=1.0),
               _eff("debuff", debuff="weaken", duration=2, chance=1.0)],
    },
    "Kreela Witch-Arm": {
        "A1": [],
        "A2": [_eff("ally_attack", count=3)],
        "A3": [],  # ATK Up + CR Up via team_buffs
    },
    # --- Survival champions ---
    "Ultimate Deathknight": {
        "A1": [],
        "A2": [],  # Ally Protect 2T via team_buffs
        "A3": [],  # Provoke (useless on CB) + self shield
        # Passive: Unkillable at 1HP when would die (4T CD) — handled in sim engine
    },
    "Cardiel": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],  # A1 places poison!
        "A2": [],  # Block Debuffs + Inc DEF via team_buffs
        "A3": [_eff("ally_attack", count=3)],  # A3 is ALLY ATTACK, not Strengthen!
        # Passive: 20% dmg reduction + Block Damage on dying ally — handled in sim engine
    },
    "Ma'Shalled": {
        "A1": [_eff("debuff", debuff="leech", duration=2, chance=1.0)],
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
        "A3": [_eff("debuff", debuff="hp_burn", duration=2, chance=0.75),
               _eff("debuff", debuff="poison_5pct", duration=2, chance=0.75)],
    },
    "Gnut": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.5)],
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=0.75)],
        "A3": [],
    },
    "Bad-El-Kazar": {
        "A1": [],
        "A2": [_eff("debuff", debuff="poison_5pct", duration=2, count=2, chance=1.0)],
        "A3": [],  # cleanse + heal
    },
    "Kalvalax": {
        "A1": [_eff("debuff", debuff="poison_5pct", duration=2, chance=0.75)],
        "A2": [_eff("detonate_poisons")],  # instant damage from all poisons
        "A3": [_eff("debuff", debuff="poison_5pct", duration=2, count=3, chance=0.75)],
        "passive": [_eff("debuff", debuff="poison_5pct", duration=2, chance=1.0)],  # per existing poison
    },
}  # END _OLD_SKILL_EFFECTS

_OLD_SKILL_DATA = {  # DEAD CODE — replaced by load_game_profiles
    "Maneater": {
        "A1": {"mult": 5.5, "stat": "ATK", "hits": 1, "cd": 0},
        "A2": {"mult": 8.2, "stat": "ATK", "hits": 1, "cd": 3,
               "team_buffs": [("atk_up", 2)]},
        "A3": {"mult": 0.25, "stat": "HP", "hits": 1, "cd": 5,
               "team_buffs": [("unkillable", 3), ("block_damage", 1)]},
    },
    "Venus": {
        "A1": {"mult": 2.2, "stat": "ATK", "hits": 1, "cd": 0},
        "A2": {"mult": 3.7, "stat": "ATK", "hits": 1, "cd": 3},  # game: booked CD=3
        "A3": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 5},  # game: base CD=5, booked CD=4
    },
    "Fayne": {
        "A1": {"mult": 3.1, "stat": "ATK", "hits": 2, "cd": 0},
        "A2": {"mult": 4.8, "stat": "ATK", "hits": 1, "cd": 4},
        "A3": {"mult": 5.4, "stat": "ATK", "hits": 3, "cd": 5},
    },
    "Occult Brawler": {
        "A1": {"mult": 4.5, "stat": "ATK", "hits": 1, "cd": 0},
        "A2": {"mult": 6.2, "stat": "ATK", "hits": 1, "cd": 4},
    },
    "Geomancer": {
        "A1": {"mult": 2.4, "stat": "ATK", "hits": 1, "cd": 0},
        "A2": {"mult": 6.0, "stat": "ATK", "hits": 2, "cd": 4},
        "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 5},
    },
    "Frozen Banshee": {
        "A1": {"mult": 3.0, "stat": "ATK", "hits": 2, "cd": 0},
        "A2": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 4},
        "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 3},
    },
    "Venomage": {
        "A1": {"mult": 3.5, "stat": "ATK", "hits": 2, "cd": 0},
        "A2": {"mult": 3.0, "stat": "ATK", "hits": 1, "cd": 3},
        "A3": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 4},
    },
    "Razelvarg": {
        "A1": {"mult": 3.2, "stat": "ATK", "hits": 2, "cd": 0},
        "A2": {"mult": 5.0, "stat": "ATK", "hits": 3, "cd": 4},
        "A3": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 4},
    },
    "Teodor the Savant": {
        "A1": {"mult": 3.1, "stat": "DEF", "hits": 1, "cd": 0},  # from game: 3.1*DEF
        "A2": {"mult": 0, "stat": "DEF", "hits": 0, "cd": 4},    # 2 poisons + Inc SPD (no damage)
        "A3": {"mult": 0, "stat": "DEF", "hits": 0, "cd": 5},    # extend+activate+poison (no direct dmg)
    },
    "Corvis the Corruptor": {
        "A1": {"mult": 3.5, "stat": "DEF", "hits": 1, "cd": 0},
        "A2": {"mult": 4.0, "stat": "DEF", "hits": 2, "cd": 4},
        "A3": {"mult": 3.0, "stat": "DEF", "hits": 2, "cd": 4},
    },
    "Vizier Ovelis": {
        "A1": {"mult": 3.0, "stat": "ATK", "hits": 3, "cd": 0},
        "A2": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 4},
    },
    "Skullcrusher": {
        "A1": {"mult": 3.7, "stat": "DEF", "hits": 1, "cd": 0},
        "A2": {"mult": 0, "stat": "DEF", "hits": 0, "cd": 4,
               "team_buffs": [("counterattack", 2)]},
    },
    "Fahrakin the Fat": {
        "A1": {"mult": 4.3, "stat": "ATK", "hits": 1, "cd": 0},
        "A2": {"mult": 7.3, "stat": "ATK", "hits": 1, "cd": 4},
        "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 6},
    },
    "Nethril": {
        "A1": {"mult": 3.0, "stat": "ATK", "hits": 3, "cd": 0},
        "A2": {"mult": 4.8, "stat": "ATK", "hits": 1, "cd": 5},
        "A3": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 5},
    },
    "Urogrim": {
        "A1": {"mult": 3.2, "stat": "ATK", "hits": 1, "cd": 0},
        "A2": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 3},
    },
    "Toragi the Frog": {
        "A1": {"mult": 3.0, "stat": "DEF", "hits": 2, "cd": 0},
        "A2": {"mult": 0, "stat": "DEF", "hits": 0, "cd": 4},
        "A3": {"mult": 3.5, "stat": "DEF", "hits": 1, "cd": 4},
    },
    "Rhazin Scarhide": {
        "A1": {"mult": 4.0, "stat": "DEF", "hits": 1, "cd": 0},
        "A2": {"mult": 4.5, "stat": "DEF", "hits": 1, "cd": 4},
        "A3": {"mult": 5.5, "stat": "DEF", "hits": 1, "cd": 4},
    },
    "Iron Brago": {
        "A1": {"mult": 3.5, "stat": "DEF", "hits": 1, "cd": 0},
        "A2": {"mult": 0, "stat": "DEF", "hits": 0, "cd": 4,
               "team_buffs": [("inc_def", 2), ("strengthen", 2)]},
        "A3": {"mult": 6.0, "stat": "DEF", "hits": 1, "cd": 4},
    },
    "Sepulcher Sentinel": {
        "A1": {"mult": 3.8, "stat": "DEF", "hits": 1, "cd": 0},
        "A3": {"mult": 0, "stat": "DEF", "hits": 0, "cd": 4,
               "team_buffs": [("block_debuffs", 2), ("inc_def", 2), ("ally_protect", 2)]},
    },
    "Demytha": {
        "A1": {"mult": 4.61, "stat": "ATK", "hits": 2, "cd": 0,
               "team_buffs": [("shield", 2)]},
        "A2": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 3},  # extend buffs (handled in SKILL_EFFECTS)
        "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 3,
               "team_buffs": [("unkillable", 2), ("block_damage", 1), ("cont_heal_15", 2)]},
    },
    "Seeker": {
        "A1": {"mult": 3.72, "stat": "ATK", "hits": 2, "cd": 0},
        "A2": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 3,
               "team_buffs": [("atk_up", 2)], "team_tm_fill": 0.30},  # 30% TM fill all allies
        "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 5,
               "team_buffs": [("inc_def", 2)]},
    },
    "Artak": {
        "A1": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 0},
        "A2": {"mult": 6.0, "stat": "ATK", "hits": 1, "cd": 3},
        "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 5},
    },
    "Dracomorph": {
        "A1": {"mult": 4.0, "stat": "ATK", "hits": 2, "cd": 0},
        "A2": {"mult": 4.5, "stat": "ATK", "hits": 4, "cd": 4},
        "A3": {"mult": 5.0, "stat": "ATK", "hits": 1, "cd": 4},
    },
    "Kreela Witch-Arm": {
        "A1": {"mult": 3.5, "stat": "ATK", "hits": 2, "cd": 0},
        "A2": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 4},
        "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 5,
               "team_buffs": [("atk_up", 2)]},
    },
    "Steelskull": {
        "A1": {"mult": 3.5, "stat": "DEF", "hits": 1, "cd": 0},
        "A2": {"mult": 0, "stat": "DEF", "hits": 0, "cd": 3,
               "team_buffs": [("inc_def", 2)]},
    },
    # --- Survival champions ---
    "Ultimate Deathknight": {
        "A1": {"mult": 3.5, "stat": "DEF", "hits": 1, "cd": 0},
        "A2": {"mult": 0, "stat": "DEF", "hits": 0, "cd": 4,
               "team_buffs": [("ally_protect", 2)]},
        "A3": {"mult": 3.0, "stat": "DEF", "hits": 1, "cd": 5},
    },
    "Cardiel": {
        "A1": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 0},    # + heals ally 7.5% HP + poison
        "A2": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 3,       # remove buffs + block_debuffs + inc_def
               "team_buffs": [("block_debuffs", 2), ("inc_def", 2)]},
        "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 4},      # 2 buffs + ALLY ATTACK
    },
    # --- Non-UK DPS/Support ---
    "Ma'Shalled": {
        "A1": {"mult": 7.8, "stat": "ATK", "hits": 2, "cd": 0},    # 3.9*ATK × 2 + self-heal + Leech
        "A2": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 3,       # 2 buffs + 2 poisons + CA
               "team_buffs": [("counterattack", 2), ("atk_up", 2)]},
        "A3": {"mult": 6.6, "stat": "ATK", "hits": 1, "cd": 3,     # big hit + 50% dmg reduce + poison + burn
               "team_buffs": [("dmg_reduction", 2)]},
    },
    "Gnut": {
        "A1": {"mult": 3.3, "stat": "DEF", "hits": 3, "cd": 0},    # 1.1*DEF × 3 hits + TM reduce + poison
        "A2": {"mult": 3.5, "stat": "DEF", "hits": 1, "cd": 3,     # + 2 poisons + buff
               "team_buffs": [("inc_def", 2)]},
        "A3": {"mult": 4.5, "stat": "DEF", "hits": 3, "cd": 4},    # (1.5*DEF+0.1*TRG_HP) × 3 + DEF steal + self-heal
    },
}

# Old defaults (dead)
_OLD_DEFAULT_SKILL_DATA = {
    "A1": {"mult": 3.5, "stat": "ATK", "hits": 1, "cd": 0},
    "A2": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 4},
    "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 5},
}


# =============================================================================
# DEAD CODE — Auto-patch (replaced by load_game_profiles)
# =============================================================================
def _load_auto_generated_skills_DEAD():
    """Load auto-generated skill data from skills_db.json for ALL heroes.
    Auto-generated data fills in heroes that don't have hand-coded entries.
    For heroes WITH hand-coded entries, only update multipliers and CDs
    but PRESERVE team_buffs and skill_effects (which need manual mapping)."""
    try:
        from auto_skills import generate_all
        auto_sd, auto_se = generate_all()

        for name, sd in auto_sd.items():
            if name in SKILL_DATA:
                # Hero has hand-coded entry — update mults/CDs but keep team_buffs
                for label in ["A1", "A2", "A3"]:
                    if label in sd and label in SKILL_DATA[name]:
                        hand = SKILL_DATA[name][label]
                        auto = sd[label]
                        # Update multiplier and CD from auto (game data)
                        hand["mult"] = auto["mult"]
                        hand["cd"] = auto["cd"]
                        hand["hits"] = auto["hits"]
                        hand["stat"] = auto["stat"]
                        # Preserve team_buffs from hand-coded
                        if "team_buffs" in auto and "team_buffs" not in hand:
                            hand["team_buffs"] = auto["team_buffs"]
                    elif label in sd and label not in SKILL_DATA[name]:
                        SKILL_DATA[name][label] = sd[label]
            else:
                # New hero — use auto-generated entirely
                SKILL_DATA[name] = sd

        for name, se in auto_se.items():
            if name not in SKILL_EFFECTS:
                SKILL_EFFECTS[name] = se
            # For heroes WITH hand-coded effects, keep them (they have correct mappings)
    except Exception as e:
        pass  # Fall back to hand-coded if auto-gen fails

# _load_auto_generated_skills()  # replaced by load_game_profiles


def _patch_from_game_data_DEAD():
    """Override SKILL_DATA with fully-booked values from game data.
    Patches: cooldowns, damage multipliers (book bonuses), debuff chances."""
    db_path = Path(__file__).parent.parent / "skills_db.json"
    if not db_path.exists():
        return

    with open(db_path) as f:
        db = json.load(f)

    for name, sd in SKILL_DATA.items():
        game_skills = db.get(name, [])
        if not game_skills:
            continue

        # Deduplicate by type_id, keep highest level
        best = {}
        for sk in game_skills:
            tid = sk.get("skill_type_id", 0)
            lvl = sk.get("level", 0)
            if tid not in best or lvl > best[tid].get("level", 0):
                best[tid] = sk

        # Match: A1 first, then A2/A3 by cooldown order
        a1_skill = next((s for s in best.values() if s.get("is_a1")), None)
        cd_skills = sorted(
            [s for s in best.values() if s.get("cooldown", 0) > 0],
            key=lambda s: s.get("cooldown", 0)
        )

        skill_map = {}
        if a1_skill:
            skill_map["A1"] = a1_skill
        for i, sk in enumerate(cd_skills[:2]):
            skill_map[["A2", "A3"][i]] = sk

        for label, sk in skill_map.items():
            if label not in sd:
                continue

            bonuses = sk.get("level_bonuses", [])

            # Patch CD (type 3 = CD reduction)
            base_cd = sk.get("cooldown", 0)
            if base_cd > 0:
                cd_reds = sum(1 for b in bonuses if b.get("type") == 3)
                sd[label]["cd"] = base_cd - cd_reds

            # Patch damage multiplier with book bonuses (type 0 = +damage%)
            dmg_bonus_pct = sum(b["value"] for b in bonuses if b.get("type") == 0)
            if dmg_bonus_pct > 0 and sd[label].get("mult", 0) > 0:
                sd[label]["mult"] = round(sd[label]["mult"] * (1 + dmg_bonus_pct / 100), 2)
                sd[label]["_booked"] = True  # mark as already boosted

# _patch_from_game_data_DEAD()  # replaced by load_game_profiles


# =============================================================================
# Core Simulator
# =============================================================================
# UNM CB damage parameters
CB_ATK = 10000         # estimated CB attack stat
CB_AOE_MULT = 3.5      # AoE multiplier
CB_STUN_MULT = 5.0     # Stun (A1) multiplier
GATHERING_FURY_START_ROUND = 4  # starts ramping at round 4 (~turn 10)
GATHERING_FURY_RATE = 0.02  # +2% ATK per ROUND (1 round = 3 CB turns) after start
LIFESTEAL_RATE = 0.30  # Lifesteal set: 30% of damage dealt as healing
CONT_HEAL_RATE = 0.075  # Continuous Heal: 7.5% max HP per tick


class CBSimulator:
    def __init__(self, champions: List[SimChampion], cb_speed: float = 190,
                 cb_element: int = 4, deterministic: bool = True,
                 rng_seed: int = None, verbose: bool = False,
                 model_survival: bool = True, force_affinity: bool = True):
        self.champions = champions
        self.cb_speed = cb_speed
        self.cb_element = cb_element  # 1=Magic, 2=Force, 3=Spirit, 4=Void
        self.cb_tm = 0.0
        self.cb_turn = 0
        self.cb_pattern = CB_VOID_PATTERN
        self.debuff_bar = DebuffBar()
        self.deterministic = deterministic
        self.rng = random.Random(rng_seed)
        self.verbose = verbose
        self.model_survival = model_survival
        # Force Affinity mode: boss has infinite HP and caps per-skill damage.
        # Empirically verified vs live runs — caps bring 43M sim prediction down
        # to observed ~31M actual (Myth-Eater team vs UNM FA).
        self.force_affinity = force_affinity
        self.log = []
        self.errors = []
        self.turn_snapshots = []  # Per-CB-turn damage/debuff snapshots for calibration
        self._placement_debt = {}  # Fractional debuff placement accumulator per champion

        # Detect if this is an Unkillable tune (any champion places UK on team)
        self.is_uk_tune = any(
            any(b[0] == "unkillable" for b in skill.team_buffs)
            for c in self.champions
            for skill in (c.skills or [])
        )

        # Initialize HP for survival mode
        for c in self.champions:
            c.max_hp = c.stats.get(HP, 30000)
            c.current_hp = c.max_hp
            c.has_lifesteal = c.stats.get("has_lifesteal", False)

    def _cap_fa(self, raw_dmg: float, kind: str = "direct", skill_name: str = "", hits: int = 1) -> float:
        """Apply Force-Affinity per-skill damage cap if FA mode is on.

        Empirically observed from live UNM Force-Affinity runs (clan has already beaten CB;
        he's in endless "capped damage" mode). Caps bring sim predictions in line with
        actual in-game totals. Set force_affinity=False for pre-defeat CB where damage is uncapped.
        """
        if not self.force_affinity or raw_dmg <= 0:
            return raw_dmg
        if kind == "dot":
            return min(raw_dmg, FA_CAP_DOT)
        if kind in ("wm_gs", "passive"):
            return min(raw_dmg, FA_CAP_SMALL)
        if skill_name == "A3" or (hits and hits >= 3):
            per_hit_cap = FA_CAP_BIG
        elif skill_name in ("A2", "A4") or (hits and hits >= 2):
            per_hit_cap = FA_CAP_MEDIUM
        else:
            per_hit_cap = FA_CAP_SMALL
        return min(raw_dmg, per_hit_cap * max(1, hits or 1))

    def run(self, max_cb_turns: int = MAX_CB_TURNS) -> dict:
        """Run full simulation. Set max_cb_turns=0 for unlimited (run until all dead)."""
        tick = 0
        effective_max = max_cb_turns if max_cb_turns > 0 else 999
        while self.cb_turn < effective_max:
            tick += 1
            if tick > 100000:
                self.errors.append("Exceeded 100K ticks")
                break

            # Check if all heroes are dead
            if all(c.is_dead for c in self.champions):
                break

            # Fill turn meters (DWJ: speed buff/debuff = ±30% of BASE speed)
            for c in self.champions:
                if not c.is_dead:
                    effective_spd = c.speed
                    base = c.base_speed if c.base_speed > 0 else c.speed
                    if c.has_buff("inc_spd"):
                        effective_spd += base * 0.30
                    if c.has_buff("dec_spd"):
                        effective_spd -= base * 0.30
                    c.tm += effective_spd
            self.cb_tm += self.cb_speed

            # Process all above threshold
            while True:
                ready = []
                for c in self.champions:
                    if c.tm >= TM_THRESHOLD and not c.is_dead:
                        ready.append(("champ", c))
                if self.cb_tm >= TM_THRESHOLD:
                    ready.append(("cb", None))

                if not ready:
                    break

                # DWJ tie-breaking: highest TM first, then highest speed, then position
                ready.sort(key=lambda x: (
                    -(x[1].tm if x[0] == "champ" else self.cb_tm),
                    -(x[1].speed if x[0] == "champ" else self.cb_speed),
                    x[1].position if x[0] == "champ" else 99
                ))

                kind, actor = ready[0]
                if kind == "cb":
                    self._cb_turn(tick)
                else:
                    self._champion_turn(actor, tick)

        return self._compile_result()

    # ----- CB Turn -----
    def _get_affinity_mult(self, champ: SimChampion) -> Tuple[float, float]:
        """Return (damage_mult, debuff_land_mult) for this champion vs CB affinity.
        Weak hit: 70% damage, 65% debuff chance. Strong: 130% damage, 100% debuff. Neutral: 100%, 100%."""
        if champ.element == 4 or self.cb_element == 4:
            return (1.0, 1.0)  # Void = always neutral
        if WEAK_AFFINITY.get(champ.element) == self.cb_element:
            return (WEAK_HIT_DMG_MULT, 1.0 - WEAK_HIT_DEBUFF_FAIL)  # 0.70, 0.65
        if STRONG_AFFINITY.get(champ.element) == self.cb_element:
            return (STRONG_HIT_DMG_MULT, 1.0)  # 1.30, 1.0
        return (1.0, 1.0)

    def _cb_turn(self, tick: int):
        self.cb_tm -= TM_THRESHOLD
        self.cb_turn += 1
        attack = self.cb_pattern[(self.cb_turn - 1) % 3]

        # Tick debuffs
        self.debuff_bar.tick()

        # Poison ticks — each active poison deals damage
        poison_sens = self.debuff_bar.has("poison_sensitivity")
        psens_mult = 1.25 if poison_sens else 1.0
        for slot in list(self.debuff_bar.slots):
            if slot.debuff_type == "poison_5pct":
                dmg = POISON_5PCT_DMG * psens_mult
                dmg = self._cap_fa(dmg, kind="dot")  # FA per-tick cap
                # Attribute to source hero
                for c in self.champions:
                    if c.name == slot.source:
                        c.damage.poison += dmg
                        break

        # HP Burn tick (only 1 counts even if multiple on bar)
        if self.debuff_bar.has("hp_burn"):
            burn_slot = next(s for s in self.debuff_bar.slots if s.debuff_type == "hp_burn")
            burn_dmg = self._cap_fa(HP_BURN_DMG, kind="dot")
            for c in self.champions:
                if c.name == burn_slot.source:
                    c.damage.hp_burn += burn_dmg
                    break

        # AoE — deal damage to all heroes
        if attack in ("aoe1", "aoe2"):
            # Gathering Fury: +2% ATK per ROUND (game: BattleStatsModifier, round-based)
            # 1 round = 3 CB turns. Round N starts at CB turn (N-1)*3+1
            cb_round = (self.cb_turn - 1) // 3 + 1
            fury_mult = 1.0
            if cb_round > GATHERING_FURY_START_ROUND:
                fury_mult = 1.0 + GATHERING_FURY_RATE * (cb_round - GATHERING_FURY_START_ROUND)

            # Dec ATK on CB reduces damage by 50%
            dec_atk_mult = 0.5 if self.debuff_bar.has("dec_atk") else 1.0

            # Find Ally Protect providers (from buff OR permanent passive)
            ap_providers = [c for c in self.champions
                           if not c.is_dead and (c.has_buff("ally_protect") or c.has_passive_ally_protect)]

            # Calculate and apply damage to each hero
            redirected_damage = {}  # provider -> total redirected damage
            for ap in ap_providers:
                redirected_damage[ap.position] = 0

            for c in self.champions:
                if c.is_dead:
                    continue

                has_uk = c.has_buff("unkillable")
                has_bd = c.has_buff("block_damage")

                if has_uk or has_bd:
                    continue  # fully protected, no damage taken

                # GAP DETECTED: champion has NO protection (UK or BD) when CB attacks.
                # This is ALWAYS an error for Unkillable tunes — even if the hero survives.
                if self.is_uk_tune:
                    self.errors.append(
                        f"GAP: {c.name}(p{c.position}) has NO UK/BD on CB turn {self.cb_turn} ({attack})")

                if not self.model_survival:
                    c.is_dead = True
                    c.death_turn = self.cb_turn
                    continue

                # Calculate base damage taken
                target_def = c.stats.get(DEF, 1000)
                if c.has_buff("inc_def"):
                    target_def *= 1.6  # DEF Up = +60%
                def_reduction = 1 - target_def / (target_def + 2220)

                aoe_dmg = CB_ATK * CB_AOE_MULT * def_reduction * dec_atk_mult * fury_mult

                # Damage reduction buff (e.g., Ma'Shalled A3: 50% reduction)
                if c.has_buff("dmg_reduction"):
                    aoe_dmg *= 0.50

                # Passive damage reduction (e.g., Cardiel -20%, Geomancer -15%)
                if c.has_passive_dmg_reduction > 0:
                    aoe_dmg *= (1 - c.has_passive_dmg_reduction)

                # Sicia passive: -3% damage taken per HP Burn on field
                if c.burn_dmg_reduction > 0:
                    burn_count = sum(1 for s in self.debuff_bar.slots if s.debuff_type == "hp_burn")
                    aoe_dmg *= max(0, 1 - c.burn_dmg_reduction * burn_count)

                # Stalwart set: 30% AoE damage reduction
                if c.stats.get("has_stalwart"):
                    aoe_dmg *= 0.70

                # Strengthen is NOT damage reduction — it increases outgoing damage

                # Ally Protect: redirect 50% to each provider (split among providers)
                if ap_providers and c not in ap_providers:
                    redirect_pct = 0.50
                    redirect_total = aoe_dmg * redirect_pct
                    per_provider = redirect_total / len(ap_providers)
                    for ap in ap_providers:
                        redirected_damage[ap.position] += per_provider
                    aoe_dmg -= redirect_total  # hero takes reduced damage

                c.current_hp -= aoe_dmg

                # Cardiel passive: Block Damage when about to die (4T CD per ally)
                if c.current_hp <= 0:
                    saved = False
                    # Check for Cardiel passive
                    cardiel_cd_key = f"_cardiel_cd_{c.position}"
                    cardiel = next((x for x in self.champions
                                   if x.name == "Cardiel" and not x.is_dead), None)
                    if cardiel and not hasattr(cardiel, cardiel_cd_key):
                        setattr(cardiel, cardiel_cd_key, 0)
                    if cardiel and getattr(cardiel, cardiel_cd_key, 0) <= 0:
                        c.current_hp = 1  # saved by Cardiel
                        setattr(cardiel, cardiel_cd_key, 4)
                        saved = True

                    # UDK passive: Unkillable at 1HP (4T CD)
                    if not saved and c.name == "Ultimate Deathknight":
                        udk_cd_key = "_udk_passive_cd"
                        if not hasattr(c, udk_cd_key):
                            setattr(c, udk_cd_key, 0)
                        if getattr(c, udk_cd_key, 0) <= 0:
                            c.current_hp = 1
                            c.add_buff("unkillable", 1)
                            setattr(c, udk_cd_key, 4)
                            saved = True

                    if not saved:
                        c.is_dead = True
                        c.death_turn = self.cb_turn
                        self.errors.append(
                            f"DEATH: {c.name}(p{c.position}) CB turn {self.cb_turn} ({attack})")

            # Apply redirected damage to Ally Protect providers
            for ap in ap_providers:
                rd = redirected_damage.get(ap.position, 0)
                if rd > 0:
                    # Guardian set on provider: absorb 10% extra from allies (already in redirect)
                    # Stalwart on provider: 30% reduction on redirected damage too
                    if ap.stats.get("has_stalwart"):
                        rd *= 0.70
                    ap.current_hp -= rd
                    if ap.current_hp <= 0:
                        # UDK passive check
                        saved = False
                        if ap.name == "Ultimate Deathknight":
                            udk_cd_key = "_udk_passive_cd"
                            if not hasattr(ap, udk_cd_key):
                                setattr(ap, udk_cd_key, 0)
                            if getattr(ap, udk_cd_key, 0) <= 0:
                                ap.current_hp = 1
                                ap.add_buff("unkillable", 1)
                                setattr(ap, udk_cd_key, 4)
                                saved = True
                        if not saved:
                            ap.is_dead = True
                            ap.death_turn = self.cb_turn
                            self.errors.append(
                                f"DEATH: {ap.name}(p{ap.position}) CB turn {self.cb_turn} ({attack}) [from ally protect]")

            # Tick Cardiel/UDK passive cooldowns
            for c in self.champions:
                if not c.is_dead:
                    for attr in dir(c):
                        if attr.startswith("_cardiel_cd_") or attr == "_udk_passive_cd":
                            val = getattr(c, attr, 0)
                            if val > 0:
                                setattr(c, attr, val - 1)

            # Regeneration set: heal at start of each round (approximate as per CB turn)
            for c in self.champions:
                if not c.is_dead and c.stats.get("has_regen"):
                    heal = c.max_hp * 0.15
                    c.current_hp = min(c.max_hp, c.current_hp + heal)

            # Counter-attacks (only living heroes)
            for c in self.champions:
                if not c.is_dead and c.has_buff("counterattack"):
                    self._execute_a1(c, is_counter=True)

            # Extra turn passives (e.g., Gnut: gets an extra turn when allies are hit)
            # DWJ: extra turn = TM += threshold, processed by the main loop naturally
            for c in self.champions:
                if not c.is_dead and c.has_passive_extra_turns:
                    c.tm += TM_THRESHOLD

            # Geomancer passive (only if alive)
            for c in self.champions:
                if c.is_geomancer and not c.is_dead:
                    geo_data = SKILLS.get("Geomancer", {}).get("passive", {})
                    flat = geo_data.get("flat_dmg_per_cb_turn", 200_000)
                    gs_procs = geo_data.get("gs_procs_per_cb_turn", 1.0)
                    wk = 1.25 if self.debuff_bar.has("weaken") else 1.0
                    c.damage.passive += self._cap_fa(flat * wk, kind="passive")
                    c.damage.wm_gs += self._cap_fa(gs_procs * GS_DMG * wk, kind="wm_gs")

        elif attack == "stun":
            # Game data: fromTargetsWithSkillOnCDSelectWithMaxStamina
            # Stun targets the champion with HIGHEST Turn Meter (Stamina)
            # who has at least one skill on cooldown AND doesn't have Block Debuffs.
            # CB avoids champions with Block Damage, Counter-Attack, Inc DEF.
            def _stun_eligible(c):
                if c.is_dead: return False
                if c.has_buff("block_debuffs"): return False
                if c.has_buff("block_damage") or c.has_buff("counterattack") or c.has_buff("inc_def"):
                    return False
                return True

            def _has_skill_on_cd(c):
                return any(s.current_cd > 0 for s in c.skills if s.base_cd > 0)

            # Primary: eligible + has skill on CD, pick highest TM
            candidates = [c for c in self.champions if _stun_eligible(c) and _has_skill_on_cd(c)]
            if not candidates:
                # Fallback: eligible without CD filter
                candidates = [c for c in self.champions if _stun_eligible(c)]
            if not candidates:
                # Last resort: anyone alive without block_debuffs
                candidates = [c for c in self.champions if not c.is_dead and not c.has_buff("block_debuffs")]
            if not candidates:
                candidates = [c for c in self.champions if not c.is_dead]
            target = max(candidates, key=lambda c: (c.tm, c.speed, -c.position)) if candidates else None
            if target:
                if target.has_buff("block_debuffs"):
                    pass  # stun is blocked!
                else:
                    target.is_stunned = True
                # Stun deals damage too
                if self.model_survival and not target.has_buff("unkillable") and not target.has_buff("block_damage"):
                    fury_mult = 1.0
                    cb_round_s = (self.cb_turn - 1) // 3 + 1
                    if cb_round_s > GATHERING_FURY_START_ROUND:
                        fury_mult = 1.0 + GATHERING_FURY_RATE * (cb_round_s - GATHERING_FURY_START_ROUND)
                    dec_atk_mult = 0.5 if self.debuff_bar.has("dec_atk") else 1.0
                    target_def = target.stats.get(DEF, 1000)
                    if target.has_buff("inc_def"):
                        target_def *= 1.6
                    def_red = 1 - target_def / (target_def + 2220)
                    stun_dmg = CB_ATK * CB_STUN_MULT * def_red * dec_atk_mult * fury_mult
                    target.current_hp -= stun_dmg
                    if target.current_hp <= 0:
                        target.is_dead = True
                        target.death_turn = self.cb_turn

        # Record per-CB-turn snapshot for calibration
        cumul_dmg = sum(c.damage.total for c in self.champions)
        poi_count = self.debuff_bar.count("poison_5pct")
        self.turn_snapshots.append({
            "cb_turn": self.cb_turn,
            "cumulative_damage": cumul_dmg,
            "poison_count": poi_count,
            "hp_burn_active": self.debuff_bar.has("hp_burn"),
            "def_down_active": self.debuff_bar.has("def_down"),
            "weaken_active": self.debuff_bar.has("weaken"),
            "dec_atk_active": self.debuff_bar.has("dec_atk"),
            "debuff_bar_size": len(self.debuff_bar),
            "attack": attack,
        })

        if self.verbose:
            self.log.append(
                f"  T{self.cb_turn:>3} CB {attack:5s} "
                f"[{len(self.debuff_bar)}/10: {self.debuff_bar.summary()}]"
                f" Poi×{poi_count}={'✓' if poison_sens else ''}")

    # ----- Champion Turn -----
    def _champion_turn(self, champ: SimChampion, tick: int):
        champ.tm -= TM_THRESHOLD
        champ.turns_taken += 1

        # Passive buff extension (Heiress): extend ALL ally buffs by 1T
        # In-game: extends OTHER allies' buffs (not self). The extension effectively
        # counters the tick, keeping buffs alive. For allies who already ticked this
        # cycle, the extension adds a turn they'll use next cycle. For allies who
        # haven't ticked yet, they'll tick the extension turn and still have the buff.
        # Net effect: buffs on ALL allies persist as long as Heiress takes turns.
        if champ.has_passive_buff_extension:
            for ally in self.champions:
                if not ally.is_dead:
                    for buff_name in list(ally.buffs.keys()):
                        ally.buffs[buff_name] += 1
            # Also cleanse 1 debuff from a random ally (Heiress passive includes cleanse)
            for ally in self.champions:
                if not ally.is_dead and ally.is_stunned:
                    ally.is_stunned = False
                    break

        champ.tick_buffs()
        champ.tick_cooldowns()

        if champ.is_stunned:
            champ.is_stunned = False
            if self.verbose:
                self.log.append(f"       {champ.name:>20} — STUNNED")
            return

        # Select skill
        chosen = champ.skills[0]  # A1
        if champ.opening:
            forced = champ.opening.pop(0)
            for sk in champ.skills:
                if sk.name == forced:
                    chosen = sk
                    break
        else:
            for sk in reversed(champ.skills):
                if sk.base_cd > 0 and sk.current_cd == 0:
                    chosen = sk
                    break

        # Apply team buffs
        for buff_name, duration in chosen.team_buffs:
            for c in self.champions:
                c.add_buff(buff_name, duration)

        # Apply TM fill to all allies (e.g., Seeker A2: 30% TM fill)
        if chosen.team_tm_fill > 0:
            tm_amount = chosen.team_tm_fill * TM_THRESHOLD
            for c in self.champions:
                if not c.is_dead and c is not champ:
                    c.tm += tm_amount

        # Apply self TM fill (e.g., Ninja A1: +15% TM)
        if chosen.self_tm_fill > 0:
            champ.tm += chosen.self_tm_fill * TM_THRESHOLD

        # Ninja combo counter: increment on each skill use against boss
        if champ.combo_atk_pct > 0 or champ.combo_cd_pct > 0:
            champ.combo_counter += 1

        # Calculate hit damage
        if chosen.multiplier > 0 and chosen.hit_count > 0:
            dmg = self._calc_skill_damage(champ, chosen)
            # Force-Affinity damage cap on the direct-hit total (per-hit-capped, summed).
            dmg = self._cap_fa(dmg, kind="direct", skill_name=chosen.name, hits=chosen.hit_count)
            champ.damage.direct += dmg

            # WM/GS procs
            wm_gs = self._roll_wm_gs(champ, chosen.hit_count)
            wm_gs = self._cap_fa(wm_gs, kind="wm_gs", hits=chosen.hit_count)
            champ.damage.wm_gs += wm_gs

            # Healing from damage dealt
            if self.model_survival:
                total_dealt = dmg + wm_gs
                heal = 0
                # Lifesteal set: 30% of damage dealt
                if champ.has_lifesteal:
                    heal += total_dealt * LIFESTEAL_RATE
                # Leech debuff on CB: all attackers heal 10% of damage dealt
                if self.debuff_bar.has("leech"):
                    heal += total_dealt * LEECH_HEAL_RATE
                # A1 self-heal (e.g., Ma'Shalled: 30% of dealt damage)
                if champ.a1_self_heal_pct > 0 and chosen.name == "A1":
                    heal += total_dealt * champ.a1_self_heal_pct
                if heal > 0:
                    champ.current_hp = min(champ.max_hp, champ.current_hp + heal)
                # A1 target heal (e.g., Cardiel: heals ally 7.5% of their max HP)
                if champ.a1_target_heal_pct > 0 and chosen.name == "A1":
                    # Heal lowest HP ally
                    alive = [c for c in self.champions if not c.is_dead and c is not champ]
                    if alive:
                        target = min(alive, key=lambda c: c.current_hp / c.max_hp)
                        target.current_hp = min(target.max_hp,
                            target.current_hp + target.max_hp * champ.a1_target_heal_pct)

        # Continuous Heal tick (7.5% or 15% variant)
        if self.model_survival:
            if champ.has_buff("cont_heal_15"):
                heal = champ.max_hp * 0.15
                champ.current_hp = min(champ.max_hp, champ.current_hp + heal)
            elif champ.has_buff("cont_heal"):
                heal = champ.max_hp * CONT_HEAL_RATE
                champ.current_hp = min(champ.max_hp, champ.current_hp + heal)

        # Immortal set: 3% HP per turn
        if self.model_survival and champ.stats.get("has_immortal"):
            champ.current_hp = min(champ.max_hp, champ.current_hp + champ.max_hp * 0.03)

        # Apply skill effects
        self._apply_effects(champ, chosen)

        # OB passive: place extra poison per turn
        if champ.name == "Occult Brawler":
            self._try_place_debuff(champ, "poison_5pct", 2, 1.0)

        # Put skill on CD
        if chosen.base_cd > 0:
            chosen.current_cd = chosen.base_cd

        # Extra turn: immediately take another turn (DWJ: TM += threshold)
        if chosen.grants_extra_turn:
            champ.tm += TM_THRESHOLD

        if self.verbose:
            buffs = ",".join(f"{k}{v}" for k, v in champ.buffs.items()) or "-"
            self.log.append(
                f"       {champ.name:>20} {chosen.name:>3} [{buffs}]")

    # ----- Execute A1 (for counter-attacks and ally attacks) -----
    def _execute_a1(self, champ: SimChampion, is_counter=False):
        a1 = champ.skills[0]
        if a1.multiplier > 0 and a1.hit_count > 0:
            dmg = self._calc_skill_damage(champ, a1)
            dmg = self._cap_fa(dmg, kind="direct", skill_name="A1", hits=a1.hit_count)
            champ.damage.direct += dmg
            wm_gs = self._roll_wm_gs(champ, a1.hit_count)
            wm_gs = self._cap_fa(wm_gs, kind="wm_gs", hits=a1.hit_count)
            champ.damage.wm_gs += wm_gs
            # Healing from counter/ally attacks
            if self.model_survival:
                total_dealt = dmg + wm_gs
                heal = 0
                if champ.has_lifesteal:
                    heal += total_dealt * LIFESTEAL_RATE
                if self.debuff_bar.has("leech"):
                    heal += total_dealt * LEECH_HEAL_RATE
                if champ.a1_self_heal_pct > 0:
                    heal += total_dealt * champ.a1_self_heal_pct
                if heal > 0:
                    champ.current_hp = min(champ.max_hp, champ.current_hp + heal)
        self._apply_effects(champ, a1)

    # ----- Damage Calculation -----
    def _calc_skill_damage(self, champ: SimChampion, skill: SimSkill) -> float:
        stat_id = ATK if skill.scaling_stat == "ATK" else (DEF if skill.scaling_stat == "DEF" else HP)
        scaling = champ.stats.get(stat_id, 0)

        if skill.scaling_stat == "ATK" and champ.has_buff("atk_up"):
            scaling *= 1.5

        # Ninja passive (kind=4013): +combo_atk_pct per combo counter on bosses
        if champ.combo_atk_pct > 0 and skill.scaling_stat == "ATK":
            scaling *= (1.0 + champ.combo_atk_pct * champ.combo_counter)

        # Sicia passive (kind=4013): +burn_stat_pct per HP Burn on field
        if champ.burn_stat_pct > 0 and skill.scaling_stat == "ATK":
            burn_count = sum(1 for s in self.debuff_bar.slots if s.debuff_type == "hp_burn")
            scaling *= (1.0 + champ.burn_stat_pct * burn_count)

        raw = scaling * skill.multiplier

        # Crit
        effective_cd = champ.stats.get(CD, 50)
        if champ.has_flawless_exec:
            effective_cd += 20

        # Inc C.DMG buff (Fahrakin A3, Cardiel A3, Ma'Shalled A2: +30% CD)
        if champ.has_buff("inc_cd_30"):
            effective_cd += 30

        # Ninja passive: +combo_cd_pct per combo counter
        if champ.combo_cd_pct > 0:
            effective_cd += champ.combo_cd_pct * 100 * champ.combo_counter

        effective_cr = champ.stats.get(CR, 15)
        # Inc C.RATE buff (Fahrakin A3, Cardiel A3: +30% CR)
        if champ.has_buff("inc_cr_30"):
            effective_cr = min(100, effective_cr + 30)

        crit_mult = 1 + (effective_cr / 100) * (effective_cd / 100)

        # DEF reduction (game: DamageReductionByDefence)
        # Phase 4: IgnoreDefenceModifierProcessing — Savage, Helmsmasher modify DEF
        cb_def = UNM_DEF
        if self.debuff_bar.has("def_down"):
            cb_def *= 0.4  # DEF Down 60% = 40% remaining

        # Savage set: ignore 25% of DEF (game: IgnoreDefense set, multiplicative with DEF)
        effective_def = cb_def
        if champ.stats.get("has_savage"):
            effective_def *= 0.75  # Ignore 25% DEF

        # Per-skill ignore DEF (Ninja A3: 50%, OB A2: 30%)
        if skill.ignore_def > 0:
            effective_def *= (1.0 - skill.ignore_def)

        # Helmsmasher: ignore additional DEF (50% chance × 50% ignore = avg 25% → ~12.5% avg)
        # Simplified as average: ignore 12.5% of remaining DEF
        if champ.has_helmsmasher:
            effective_def *= 0.875

        def_mult = max(0.05, 1 - effective_def / (effective_def + 2220))

        wk = 1.25 if self.debuff_bar.has("weaken") else 1.0
        str_mult = 1.25 if champ.has_buff("strengthen") else 1.0
        bid = 1.06 if champ.has_bring_it_down else 1.0

        # Affinity modifier
        aff_dmg, _ = self._get_affinity_mult(champ)

        return raw * crit_mult * def_mult * wk * str_mult * bid * aff_dmg

    # ----- WM/GS -----
    def _roll_wm_gs(self, champ: SimChampion, hit_count: int) -> float:
        # WM/GS procs deal flat damage (% of boss max HP), capped at 75K on UNM.
        # They are NOT multiplied by DEF Down or Weaken — the cap is absolute.
        # Previous code incorrectly applied DEF Down + Weaken multipliers here,
        # causing ~2x overestimation of WM/GS damage.
        if self.deterministic:
            if champ.has_gs:
                return hit_count * GS_PROC_RATE * GS_DMG
            elif champ.has_wm:
                return WM_PROC_RATE * WM_DMG
            return 0
        else:
            dmg = 0
            if champ.has_gs:
                for _ in range(hit_count):
                    if self.rng.random() < GS_PROC_RATE:
                        dmg += GS_DMG
            elif champ.has_wm:
                if self.rng.random() < WM_PROC_RATE:
                    dmg += WM_DMG
            return dmg

    # ----- Effect Application -----
    def _apply_effects(self, champ: SimChampion, skill: SimSkill):
        effects = SKILL_EFFECTS.get(champ.name, {}).get(skill.name, [])
        acc_rate = calc_acc_land_rate(champ.stats.get(ACC, 0))
        sniper_bonus = 0.05 if champ.has_sniper else 0
        _, aff_debuff_mult = self._get_affinity_mult(champ)  # weak hits reduce debuff landing

        for eff_raw in effects:
            # Handle both SkillEffect objects and dicts (from auto_skills)
            if isinstance(eff_raw, dict):
                eff_type = eff_raw.get("effect_type", "")
                eff_params = eff_raw.get("params", {})
            else:
                eff_type = eff_raw.effect_type
                eff_params = eff_raw.params
            eff = type('E', (), {'effect_type': eff_type, 'params': eff_params})()

            if eff.effect_type == "debuff":
                base_chance = eff.params.get("chance", 1.0) + sniper_bonus
                count = eff.params.get("count", 1)
                per_hit = eff.params.get("per_hit", False)
                hits = skill.hit_count if per_hit else 1
                for _ in range(hits):
                    for _ in range(count):
                        self._try_place_debuff(
                            champ, eff.params["debuff"],
                            eff.params.get("duration", 2),
                            base_chance * acc_rate * aff_debuff_mult)

            elif eff.effect_type == "conditional_debuff":
                if eff.params.get("requires") == "poison_sensitivity":
                    if not self.debuff_bar.has("poison_sensitivity"):
                        continue
                base_chance = eff.params.get("chance", 1.0) + sniper_bonus
                per_hit = eff.params.get("per_hit", False)
                hits = skill.hit_count if per_hit else 1
                for _ in range(hits):
                    self._try_place_debuff(
                        champ, eff.params["debuff"],
                        eff.params.get("duration", 2),
                        base_chance * acc_rate)

            elif eff.effect_type == "extend_debuffs":
                turns = eff.params.get("turns", 1)
                per_hit = eff.params.get("per_hit", False)
                reps = skill.hit_count if per_hit else 1
                for _ in range(reps):
                    self.debuff_bar.extend_all(turns)

            elif eff.effect_type == "extend_buffs":
                turns = eff.params.get("turns", 1)
                for c in self.champions:
                    for b in c.buffs:
                        c.buffs[b] += turns

            elif eff.effect_type == "ally_attack":
                count = eff.params.get("count", 3)
                candidates = [c for c in self.champions if c is not champ]
                if self.deterministic:
                    targets = candidates[:count]
                else:
                    targets = self.rng.sample(candidates, min(count, len(candidates)))
                for ally in targets:
                    self._execute_a1(ally, is_counter=False)

            elif eff.effect_type == "detonate_poisons":
                # Kalvalax: instant damage from all active poisons, then remove them
                psens = 1.25 if self.debuff_bar.has("poison_sensitivity") else 1.0
                poi_count = self.debuff_bar.count("poison_5pct")
                dmg = poi_count * POISON_5PCT_DMG * 2.0 * psens  # detonation = 2x tick
                champ.damage.direct += dmg
                self.debuff_bar.slots = [s for s in self.debuff_bar.slots
                                          if s.debuff_type != "poison_5pct"]

            elif eff.effect_type == "activate_hp_burns":
                # Ninja A2 / Sicia A2: instantly trigger all HP Burn debuffs (1 tick each)
                for slot in list(self.debuff_bar.slots):
                    if slot.debuff_type == "hp_burn":
                        dmg = self._cap_fa(HP_BURN_DMG, kind="dot")
                        for c in self.champions:
                            if c.name == slot.source:
                                c.damage.hp_burn += dmg
                                break

            elif eff.effect_type == "activate_poisons":
                # Venomage A1: activate up to N poisons (trigger 1 tick each)
                psens = 1.25 if self.debuff_bar.has("poison_sensitivity") else 1.0
                max_count = eff.params.get("max_count", 99)
                activated = 0
                for slot in list(self.debuff_bar.slots):
                    if slot.debuff_type == "poison_5pct" and activated < max_count:
                        dmg = self._cap_fa(POISON_5PCT_DMG * psens, kind="dot")
                        for c in self.champions:
                            if c.name == slot.source:
                                c.damage.poison += dmg
                                break
                        activated += 1

            elif eff.effect_type == "activate_dots":
                # Teodor A3: instantly trigger ALL DoT debuffs (poisons + HP burns, 1 tick each)
                psens = 1.25 if self.debuff_bar.has("poison_sensitivity") else 1.0
                for slot in list(self.debuff_bar.slots):
                    if slot.debuff_type == "poison_5pct":
                        dmg = self._cap_fa(POISON_5PCT_DMG * psens, kind="dot")
                        for c in self.champions:
                            if c.name == slot.source:
                                c.damage.poison += dmg
                                break
                    elif slot.debuff_type == "hp_burn":
                        dmg = self._cap_fa(HP_BURN_DMG, kind="dot")
                        for c in self.champions:
                            if c.name == slot.source:
                                c.damage.hp_burn += dmg
                                break

            elif eff.effect_type == "extend_debuffs_hp_burn":
                # Sicia A1: extend only HP Burn debuffs by N turns, per hit
                turns = eff.params.get("turns", 1)
                per_hit = eff.params.get("per_hit", False)
                reps = skill.hit_count if per_hit else 1
                for _ in range(reps):
                    for slot in self.debuff_bar.slots:
                        if slot.debuff_type == "hp_burn":
                            slot.remaining += turns

            elif eff.effect_type == "extend_debuffs_poison_burn":
                # Teodor A3: extend only poison and HP burn debuffs by N turns
                turns = eff.params.get("turns", 1)
                for slot in self.debuff_bar.slots:
                    if slot.debuff_type in ("poison_5pct", "hp_burn"):
                        slot.remaining += turns

        # Master Hexer: 30% chance to extend placed debuffs
        if champ.has_master_hexer and not self.deterministic:
            # In RNG mode, roll per debuff
            pass  # TODO for Monte Carlo mode

    def _try_place_debuff(self, champ: SimChampion, debuff_type: str,
                          duration: int, effective_chance: float) -> bool:
        """Try to place a debuff on CB. Returns True if placed."""
        if self.debuff_bar.is_full():
            return False
        if self.deterministic:
            # Fractional accumulator: track debt per (champion, debuff_type).
            # >= 50% chance: place on first attempt (more likely than not).
            # < 50% chance: accumulate until debt >= 1.0 (models weak-hit scenarios).
            if effective_chance >= 0.5:
                return self.debuff_bar.add(debuff_type, duration, champ.name)
            key = (champ.name, debuff_type)
            self._placement_debt[key] = self._placement_debt.get(key, 0.0) + effective_chance
            if self._placement_debt[key] >= 1.0:
                self._placement_debt[key] -= 1.0
                return self.debuff_bar.add(debuff_type, duration, champ.name)
            return False
        else:
            if self.rng.random() < effective_chance:
                return self.debuff_bar.add(debuff_type, duration, champ.name)
        return False

    # ----- Results -----
    def _compile_result(self) -> dict:
        heroes = []
        for c in self.champions:
            heroes.append({
                "name": c.name,
                "direct": c.damage.direct,
                "poison": c.damage.poison,
                "hp_burn": c.damage.hp_burn,
                "wm_gs": c.damage.wm_gs,
                "passive": c.damage.passive,
                "total": c.damage.total,
                "turns": c.turns_taken,
            })

        total = sum(h["total"] for h in heroes)

        # Unkillable gap detection is already handled by DEATH errors during
        # AoE processing — if any champion lacks Unkillable when CB hits, it's
        # flagged as an error. No heuristic needed.
        return {
            "total": total,
            "cb_turns": self.cb_turn,
            "cb_element": self.cb_element,
            "heroes": heroes,
            "errors": self.errors,
            "valid": len(self.errors) == 0,
            "log": self.log,
            "turn_snapshots": self.turn_snapshots,
        }


# =============================================================================
# Leader Skill Aura
# =============================================================================
def apply_leader_aura(stats: dict, leader_skill: dict) -> dict:
    """Apply a leader skill aura bonus to a hero's stats dict.

    leader_skill: {stat: int (1-8), amount: float, absolute: bool, area: int}
    area: 0=all battles, 4=clan boss (both apply in CB)

    Returns a new stats dict with the aura applied.
    """
    if not leader_skill:
        return stats
    area = leader_skill.get("area", 0)
    if area not in (0, 4):  # only "all battles" and "clan boss" apply
        return stats

    stat_id = leader_skill.get("stat", 0)
    amount = leader_skill.get("amount", 0)
    absolute = leader_skill.get("absolute", False)

    stats = dict(stats)  # shallow copy
    if absolute:
        # Flat bonus (e.g., +45 ACC)
        stats[stat_id] = stats.get(stat_id, 0) + amount
    else:
        # Percentage bonus (e.g., +33% HP) — applied to base stat
        # For HP/ATK/DEF: multiply current total (approximate since we don't have base separately)
        stats[stat_id] = stats.get(stat_id, 0) * (1 + amount / 100)
    return stats


# =============================================================================
# Champion Builder
# =============================================================================
def build_sim_champion(name: str, stats: dict, position: int,
                       masteries: list = None, opening: list = None,
                       element: int = 4) -> SimChampion:
    """Build a SimChampion from name, computed stats, and masteries."""
    masteries = masteries or []

    # Build skills
    hero_sd = SKILL_DATA.get(name, DEFAULT_SKILL_DATA)
    skills = []
    for sk_name in ["A1", "A2", "A3"]:
        sd = hero_sd.get(sk_name)
        if not sd:
            continue
        sim_sk = SimSkill(
            name=sk_name,
            base_cd=max(0, sd["cd"] - 1) if sd["cd"] > 0 else 0,  # displayed CD → internal
            multiplier=sd["mult"],
            scaling_stat=sd["stat"],
            hit_count=sd["hits"],
            team_buffs=sd.get("team_buffs", []),
            team_tm_fill=sd.get("team_tm_fill", 0.0),
            self_tm_fill=sd.get("self_tm_fill", 0.0),
            grants_extra_turn=sd.get("grants_extra_turn", False),
            ignore_def=sd.get("ignore_def", 0.0),
        )
        skills.append(sim_sk)

    # Load passive data from game-accurate profiles
    pd = PASSIVE_DATA.get(name, {})

    # All passive values from PASSIVE_DATA (pre-computed by load_game_profiles)
    passive_ally_protect = pd.get('ally_protect', False)
    passive_dmg_reduction = pd.get('dmg_reduction', 0.0)
    passive_extra_turns = pd.get('extra_turns', False)
    passive_buff_extension = pd.get('buff_extension', False)
    a1_self_heal = pd.get('a1_self_heal_pct', 0.0)
    a1_target_heal = pd.get('a1_target_heal_pct', 0.0)
    combo_atk_pct = pd.get('combo_atk_pct', 0.0)
    combo_cd_pct = pd.get('combo_cd_pct', 0.0)
    burn_stat_pct = pd.get('burn_stat_pct', 0.0)
    burn_dmg_red = pd.get('burn_dmg_reduction', 0.0)

    # Base speed from hero data (before gear), for speed buff/debuff calculations
    raw_base_speed = stats.get("base_speed", 0)
    if raw_base_speed <= 0:
        raw_base_speed = stats.get(SPD, 100)  # fallback: use total speed

    champ = SimChampion(
        name=name,
        speed=stats.get(SPD, 100),
        base_speed=raw_base_speed,
        position=position,
        stats=stats,
        element=element,
        skills=skills,
        opening=list(opening) if opening else [],
        has_lifesteal=stats.get("has_lifesteal", False),
        has_passive_ally_protect=passive_ally_protect,
        has_passive_dmg_reduction=passive_dmg_reduction,
        has_passive_extra_turns=passive_extra_turns,
        has_passive_buff_extension=passive_buff_extension,
        a1_self_heal_pct=a1_self_heal,
        a1_target_heal_pct=a1_target_heal,
        has_wm=MASTERY_IDS["warmaster"] in masteries,
        has_gs=MASTERY_IDS["giant_slayer"] in masteries,
        has_helmsmasher=MASTERY_IDS["helmsmasher"] in masteries,
        has_flawless_exec=MASTERY_IDS["flawless_execution"] in masteries,
        has_bring_it_down=MASTERY_IDS["bring_it_down"] in masteries,
        has_sniper=MASTERY_IDS["sniper"] in masteries,
        has_master_hexer=MASTERY_IDS["master_hexer"] in masteries,
        has_retribution=MASTERY_IDS["retribution"] in masteries,
        is_geomancer=(name == "Geomancer"),
        is_counterattack_provider=(name == "Skullcrusher"),
        combo_atk_pct=combo_atk_pct,
        combo_cd_pct=combo_cd_pct,
        burn_stat_pct=burn_stat_pct,
        burn_dmg_reduction=burn_dmg_red,
    )

    # Auto-assign WM/GS if no T6 offense mastery
    if not (champ.has_wm or champ.has_gs or champ.has_helmsmasher or champ.has_flawless_exec):
        a1_hits = skills[0].hit_count if skills else 1
        if a1_hits >= 3:
            champ.has_gs = True
        else:
            champ.has_wm = True

    return champ


# =============================================================================
# CLI
# =============================================================================
def _validate_against_real(sim_result: dict, real_log_path: str):
    """Compare sim output against a real battle log from /battle-log.
    Uses the new buff/debuff fields (t=320 UK, t=60 BD, t=100 BlockDebuff, etc.)."""
    try:
        with open(real_log_path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"\n[validate] Could not load {real_log_path}: {e}")
        return

    log = data.get("log", [])
    # Find last snapshot = final state
    last_snap_by_turn = {}
    boss_actions = []
    for entry in log:
        e = json.loads(entry) if isinstance(entry, str) else entry
        if "heroes" in e:
            last_snap_by_turn[e.get("turn", 0)] = e
        elif e.get("active_hero") == 5:
            boss_actions.append(e.get("turn", 0))

    if not last_snap_by_turn:
        print("\n[validate] No hero snapshots found")
        return

    # Extract real stats
    real_boss_turns = len(boss_actions)
    final = last_snap_by_turn[max(last_snap_by_turn.keys())]
    boss = next((h for h in final["heroes"] if h.get("boss")), None)
    real_dmg = boss.get("dmg_taken", 0) if boss else 0

    print(f"\n{'='*70}")
    print(f"VALIDATION — sim vs real (from {real_log_path})")
    print(f"{'='*70}")
    print(f"  Total damage:    sim={sim_result['total']/1e6:.2f}M   real={real_dmg/1e6:.2f}M   "
          f"delta={(sim_result['total']-real_dmg)/1e6:+.2f}M "
          f"({100*(sim_result['total']-real_dmg)/max(1,real_dmg):+.1f}%)")
    print(f"  Boss turns:      sim={sim_result.get('cb_turns',0)}   real={real_boss_turns}")

    # Per-boss-turn UK/BD coverage in real data
    print(f"\n  Real UK/BD coverage per boss action:")
    for bt in boss_actions[:12]:
        snap = last_snap_by_turn.get(bt) or last_snap_by_turn.get(bt - 1)
        if not snap:
            continue
        covered = 0
        total = 0
        for h in snap["heroes"]:
            if h.get("boss"):
                continue
            total += 1
            buffs = h.get("buffs", [])
            if any(b.get("t") in (320, 60) for b in buffs):  # 320=UK, 60=BD
                covered += 1
        mark = "✓" if covered == total else ("⚠" if covered >= total-1 else "✗")
        print(f"    {mark} mod-turn {bt:3d}:  {covered}/{total} heroes protected")

    # Buff summary observed in real data
    from collections import Counter
    buff_counts = Counter()
    debuff_counts = Counter()
    for snap in last_snap_by_turn.values():
        for h in snap.get("heroes", []):
            for b in h.get("buffs", []):
                buff_counts[b.get("t")] += 1
            for d in h.get("debuffs", []):
                debuff_counts[d.get("t")] += 1
    EFFECT_NAMES = {
        60:"BlockDamage", 70:"BlockHeal100p", 80:"Poison5p", 91:"ContHeal15p",
        100:"BlockDebuff", 120:"IncATK25", 131:"DecATK50", 151:"DecDEF60",
        280:"Shield", 320:"Unkillable", 350:"IncDmgTaken25",
        470:"Burn", 481:"Invisible2", 740:"FireMark",
    }
    print(f"\n  Real effects seen (sorted by frequency):")
    for t, c in sorted(buff_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    BUFF   t={t:4d}  {EFFECT_NAMES.get(t,'?'):18s}  {c}x")
    for t, c in sorted(debuff_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    DEBUFF t={t:4d}  {EFFECT_NAMES.get(t,'?'):18s}  {c}x")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CB Turn-by-Turn Simulator")
    parser.add_argument("--team", help="Comma-separated hero names")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--monte-carlo", type=int, default=0,
                        help="Run N Monte Carlo simulations")
    parser.add_argument("--no-force-affinity", action="store_true",
                        help="Disable Force-Affinity per-skill damage caps (pre-defeat CB).")
    parser.add_argument("--use-current-gear", action="store_true",
                        help="Use hero's currently-equipped artifacts instead of re-optimizing. "
                             "Matches real in-game state for exact verification.")
    parser.add_argument("--validate-against", type=str, default=None,
                        help="Path to real battle log JSON; after sim, compare against actual run.")
    parser.add_argument("--max-cb-turns", type=int, default=50,
                        help="Cap simulation at N CB turns (boss actions). Default 50.")
    parser.add_argument("--cb-element", type=str, default="void",
                        choices=["magic", "force", "spirit", "void"],
                        help="CB affinity element (default: void). Set to today's affinity for accuracy.")
    args = parser.parse_args()

    ELEMENT_MAP = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
    cb_element = ELEMENT_MAP[args.cb_element]

    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from cb_optimizer import calc_stats, PROFILES, optimal_artifacts_for_hero

    base = Path(__file__).parent.parent
    with open(base / "heroes_6star.json") as f:
        heroes_data = json.load(f)
    with open(base / "all_artifacts.json") as f:
        artifacts_data = json.load(f)
    with open(base / "account_data.json") as f:
        account = json.load(f)

    all_arts = [a for a in artifacts_data.get("artifacts", []) if not a.get("error")]

    # Default team
    if args.team:
        team_names = [n.strip() for n in args.team.split(",")]
    else:
        team_names = ["Maneater", "Maneater", "Venus", "Occult Brawler", "Geomancer"]

    print(f"=== CB Turn-by-Turn Simulator ===")
    print(f"Team: {', '.join(team_names)}")
    print(f"CB Element: {args.cb_element} (id={cb_element})")

    # Resolve heroes
    hero_by_name = {}
    for h in heroes_data["heroes"]:
        name = h.get("name", "")
        if name and name not in hero_by_name:
            hero_by_name[name] = h
        elif name == "Maneater" and "Maneater_2" not in hero_by_name:
            hero_by_name["Maneater_2"] = h

    # Resolve team heroes
    team_h, team_p = [], []
    me_count = 0
    for tname in team_names:
        if tname == "Maneater":
            me_count += 1
            key = "Maneater" if me_count == 1 else "Maneater_2"
        else:
            key = tname
        h = hero_by_name.get(key)
        p = PROFILES.get(tname)
        if not h:
            print(f"Hero not found: {tname}")
            return
        team_h.append(h)
        team_p.append(p)

    # If validating against real run, auto-detect the real boss turn count for fair comparison
    if args.validate_against and args.max_cb_turns == 50:
        try:
            vdata = json.load(open(args.validate_against))
            # Boss turn_n in the last snapshot = # of CB turns completed
            for entry in vdata.get("log", []):
                e = json.loads(entry) if isinstance(entry, str) else entry
                if "heroes" in e:
                    last_snap = e
            if last_snap:
                bt = next((h.get("turn_n",0) for h in last_snap["heroes"] if h.get("boss")), 0)
                if bt > 0 and bt < 50:
                    print(f"  [auto] Real run has only {bt} boss turns; capping sim to match")
                    args.max_cb_turns = bt
        except Exception:
            pass

    # Gear assignment: either use current equipped gear OR re-optimize
    from cb_optimizer import UK_ME_SPD_RANGE
    has_uk = sum(1 for p in team_p if p and p.unkillable) >= 2

    if args.use_current_gear:
        # Use the hero's CURRENTLY equipped artifacts - matches real in-game state
        print(f"  [use-current-gear] Skipping gear optimization, using equipped artifacts")
        assigned_arts = [[] for _ in range(5)]
        for i in range(5):
            current = team_h[i].get("artifacts", [])
            # Filter out any non-artifact data, keep rank>=1 equipped items
            assigned_arts[i] = [a for a in current if isinstance(a, dict) and a.get("id")]
        # Skip to build phase
        stun_idx = -1
        sim_champs = []
        me_idx = 0
        for i, tname in enumerate(team_names):
            stats = calc_stats(team_h[i], assigned_arts[i], account)
            opening = []
            if tname == "Maneater":
                me_idx += 1
                opening = ["A3"] if me_idx == 1 else ["A1", "A3"]
            champ = build_sim_champion(tname, stats, i + 1,
                                        masteries=team_h[i].get("masteries", []),
                                        opening=opening)
            sim_champs.append(champ)
            print(f"  {tname:20s} SPD:{stats[SPD]:.0f} ACC:{stats[ACC]:.0f} "
                  f"ATK:{stats[ATK]:.0f} DEF:{stats[DEF]:.0f} HP:{stats[HP]:.0f}")

        # Run simulation
        if args.monte_carlo > 0:
            totals = []
            for seed in range(args.monte_carlo):
                sim = CBSimulator(deepcopy(sim_champs), deterministic=False,
                                  rng_seed=seed, verbose=False,
                                  cb_element=cb_element,
                                  force_affinity=not args.no_force_affinity)
                result = sim.run(max_cb_turns=args.max_cb_turns)
                totals.append(result["total"])
            avg = sum(totals) / len(totals)
            lo, hi = min(totals), max(totals)
            print(f"\nMonte Carlo ({args.monte_carlo} runs):")
            print(f"  Average: {avg/1e6:.1f}M  Range: {lo/1e6:.1f}M - {hi/1e6:.1f}M")
        else:
            sim = CBSimulator(sim_champs, deterministic=True, verbose=args.verbose,
                              cb_element=cb_element,
                              force_affinity=not args.no_force_affinity)
            result = sim.run(max_cb_turns=args.max_cb_turns)

            print(f"\n{'='*70}")
            print(f"TOTAL DAMAGE: {result['total']/1e6:.1f}M over {result['cb_turns']} CB turns")
            gaps = len(result["errors"])
            tune_str = "VALID ✓" if result["valid"] else f"INVALID ✗ ({gaps} gaps)"
            print(f"Speed tune: {tune_str}")
            print(f"{'='*70}")
            for hd in result["heroes"]:
                parts = []
                for key, label in [("direct","Dir"),("poison","Poi"),("hp_burn","Burn"),
                                    ("wm_gs","WM/GS"),("passive","Pass")]:
                    v = hd.get(key, 0)
                    if v > 0:
                        parts.append(f"{label}:{v/1e6:.1f}M")
                print(f"  {hd['name']:25s} {hd['total']/1e6:6.1f}M  [{', '.join(parts)}]  ({hd['turns']}T)")
            if result["errors"]:
                print(f"\nProtection gaps: {len(result['errors'])}")
                for e in result["errors"][:5]:
                    print(f"  ✗ {e}")
            if args.validate_against:
                _validate_against_real(result, args.validate_against)
        return

    dps_idx = [i for i, p in enumerate(team_p) if p and not p.unkillable]
    # Stun target: pick the DPS who contributes LEAST from taking turns
    # Poisoners and debuffers need turns; passive damage heroes (none) or pure supports are best
    # Rank by: has poison/debuffs = needs turns = bad stun target
    def stun_priority(i):
        p = team_p[i]
        if not p: return 0
        score = 0
        if p.def_down or p.weaken: score += 10  # WORST stun target
        if p.poisons_per_turn > 1: score += 5
        if p.hp_burn_uptime > 0: score += 3
        if p.needs_acc: score += 2
        return score
    stun_idx = min(dps_idx, key=stun_priority) if dps_idx else -1
    stun_name = team_names[stun_idx] if stun_idx >= 0 else "?"
    print(f"  Stun target: {stun_name} (position {stun_idx+1})")
    used = set()
    assigned_arts = [[] for _ in range(5)]
    priority = sorted(range(5), key=lambda i: (
        0 if team_p[i] and team_p[i].unkillable else
        (3 if i == stun_idx else (1 if team_p[i] and team_p[i].needs_acc else 2))
    ))
    for pi in priority:
        avail = [a for a in all_arts if a.get("id") not in used and a.get("rank", 0) >= 5]
        spd_max = UK_ME_SPD_RANGE[1] if (has_uk and team_p[pi] and team_p[pi].unkillable) else None
        is_stun = has_uk and pi == stun_idx
        arts, _ = optimal_artifacts_for_hero(
            team_h[pi], team_p[pi] or PROFILES.get("DPS1"), avail, account,
            spd_max=spd_max, is_stun_target=is_stun)
        assigned_arts[pi] = arts
        for a in arts:
            used.add(a.get("id"))

    # Build SimChampions with optimized stats — use the ACTUAL calculated stats from the
    # assigned gear. No hard-coded speed overrides; the tune is whatever the gear produces.
    # (Previous Budget-UK overrides that forced Maneater=228/215 and DPS=171-189 removed
    # because they conflicted with Myth-Eater or any other tune.)
    sim_champs = []
    me_idx = 0
    for i, tname in enumerate(team_names):
        stats = calc_stats(team_h[i], assigned_arts[i], account)
        opening = []
        if tname == "Maneater":
            me_idx += 1
            opening = ["A3"] if me_idx == 1 else ["A1", "A3"]
        champ = build_sim_champion(tname, stats, i + 1,
                                    masteries=team_h[i].get("masteries", []),
                                    opening=opening)
        sim_champs.append(champ)
        print(f"  {tname:20s} SPD:{stats[SPD]:.0f} ACC:{stats[ACC]:.0f} ATK:{stats[ATK]:.0f} DEF:{stats[DEF]:.0f}")

    # Run simulation
    if args.monte_carlo > 0:
        totals = []
        for seed in range(args.monte_carlo):
            sim = CBSimulator(deepcopy(sim_champs), deterministic=False,
                              rng_seed=seed, verbose=False,
                              cb_element=cb_element,
                              force_affinity=not args.no_force_affinity)
            result = sim.run()
            totals.append(result["total"])
        avg = sum(totals) / len(totals)
        lo, hi = min(totals), max(totals)
        print(f"\nMonte Carlo ({args.monte_carlo} runs):")
        print(f"  Average: {avg/1e6:.1f}M  Range: {lo/1e6:.1f}M - {hi/1e6:.1f}M")
    else:
        sim = CBSimulator(sim_champs, deterministic=True, verbose=args.verbose,
                          cb_element=cb_element,
                          force_affinity=not args.no_force_affinity)
        result = sim.run()

        print(f"\n{'='*70}")
        print(f"TOTAL DAMAGE: {result['total']/1e6:.1f}M over {result['cb_turns']} CB turns")
        gaps = len(result["errors"])
        tune_str = "VALID ✓" if result["valid"] else f"INVALID ✗ ({gaps} gaps)"
        print(f"Speed tune: {tune_str}")
        print(f"{'='*70}")

        for hd in result["heroes"]:
            parts = []
            for key, label in [("direct","Dir"),("poison","Poi"),("hp_burn","Burn"),
                                ("wm_gs","WM/GS"),("passive","Pass")]:
                v = hd.get(key, 0)
                if v > 0:
                    parts.append(f"{label}:{v/1e6:.1f}M")
            print(f"  {hd['name']:25s} {hd['total']/1e6:6.1f}M  [{', '.join(parts)}]  ({hd['turns']}T)")

        if result["errors"]:
            print(f"\nProtection gaps: {len(result['errors'])}")
            for e in result["errors"][:5]:
                print(f"  ✗ {e}")

        if args.verbose and result["log"]:
            print(f"\nTurn log ({len(result['log'])} entries):")
            for line in result["log"][:150]:
                print(line)

        if args.validate_against:
            _validate_against_real(result, args.validate_against)


if __name__ == "__main__":
    main()
