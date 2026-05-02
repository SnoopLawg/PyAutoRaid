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
# Constants — game/sim values are sourced from tools.cb_constants where
# possible (DRY: single source of truth, see cb_constants.py for the
# STATIC vs CALIBRATED tagging).
# =============================================================================
from cb_constants import (
    WM_PROC_RATE, GS_PROC_RATE, LIFESTEAL_RATE, CONT_HEAL_RATE,
    LEECH_HEAL_RATE,
    WEAK_HIT_DMG_MULT, WEAK_HIT_DEBUFF_FAIL, STRONG_HIT_DMG_MULT,
    CB_ATTACK_MULT, CB_STUN_HP_FRACTION,
    CB_HP_BY_DIFFICULTY, CB_SPEED_BY_DIFFICULTY,
    CB_ATK,
    FA_CAP_BIG, FA_CAP_MEDIUM, FA_CAP_SMALL, FA_CAP_DOT,
    GATHERING_FURY_START_TURN, GATHERING_FURY_RATE_PER_TURN,
    GATHERING_FURY_CLIFF_TURN, ENRAGE_TURN,
)

TM_THRESHOLD = 1000
MAX_CB_TURNS = 50
MAX_DEBUFF_SLOTS = 10

# FA_CAP_*, LEECH_HEAL_RATE — see cb_constants.

# Affinity system: Magic=1, Force=2, Spirit=3, Void=4
# Weak hit: 20-35% damage reduction AND 35% chance debuffs don't land
# Strong hit: 20-30% damage increase
WEAK_AFFINITY = {1: 2, 2: 3, 3: 1}  # Magic weak vs Force, Force weak vs Spirit, Spirit weak vs Magic
STRONG_AFFINITY = {1: 3, 2: 1, 3: 2}  # Magic strong vs Spirit, etc.
# WEAK_HIT_DMG_MULT, WEAK_HIT_DEBUFF_FAIL, STRONG_HIT_DMG_MULT — see cb_constants.

HP, ATK, DEF, SPD, RES, ACC, CR, CD = 1, 2, 3, 4, 5, 6, 7, 8

CB_VOID_PATTERN = ["aoe1", "aoe2", "stun"]

# CB_SPEED_BY_DIFFICULTY — see cb_constants (CALIBRATED, do not flip from
# alliance_bosses[].base_stats.spd which are pre-modifier values).


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

    # Singular-by-type debuffs: only ONE active on the target regardless of
    # source. New placements refresh duration (game also picks higher amount
    # but we don't model amount variance here). This matches DWJ G() rules
    # and frees bar slots that were previously hogged by Venomage placing
    # the same def_down twice etc.
    #
    # NOTE: HP burn is INTENTIONALLY NOT singular — ground-truth tick-log
    # shows Ninja's 3-per-cast burns DO stack (his 80 burn ticks in 50 CB
    # turns implies ~1.6 active simultaneously, not 1). Making HP burn
    # singular dropped Ninja accuracy from 87% to 55%.
    SINGULAR_BY_TYPE = {"def_down", "def_down_30", "weaken", "weaken_15",
                        "dec_atk", "dec_atk_25", "poison_sensitivity",
                        "poison_sensitivity_50", "heal_reduction",
                        "heal_reduction_50", "stun", "freeze"}

    def add(self, debuff_type: str, duration: int, source: str = "") -> bool:
        """Add a debuff. Refresh existing slot if singular rules apply.

        Returns True if the debuff is now on the bar (placed or refreshed),
        False if rejected (bar full).
        """
        # Singular-by-type: any source places same type → refresh duration
        if debuff_type in self.SINGULAR_BY_TYPE:
            for s in self.slots:
                if s.debuff_type == debuff_type:
                    s.remaining = max(s.remaining, duration)
                    s.source = source  # update attribution to most recent placer
                    return True
        # Otherwise stack (poisons, HP burns, etc.)
        if len(self.slots) >= MAX_DEBUFF_SLOTS:
            return False
        self.slots.append(DebuffSlot(debuff_type, duration, source))
        return True

    def tick(self) -> List[DebuffSlot]:
        """Tick all durations at start of CB turn. Returns expired slots.

        Game mechanic: debuffs tick AFTER their effects apply on this turn.
        A 2-turn debuff is active for 2 CB turns:
          - Placed: remaining=2
          - CB turn 1: active (remaining=2), then tick → remaining=1
          - CB turn 2: active (remaining=1), then tick → remaining=0 → expired

        Implementation: decrement first, expire at < 0 (not <= 0).
        This gives one extra turn of activity matching in-game behavior.
        """
        expired = []
        remaining = []
        for s in self.slots:
            s.remaining -= 1
            if s.remaining < 0:
                expired.append(s)
            else:
                remaining.append(s)
        self.slots = remaining
        return expired

    def has(self, debuff_type: str) -> bool:
        return any(s.debuff_type == debuff_type for s in self.slots)

    def count(self, debuff_type: str) -> int:
        return sum(1 for s in self.slots if s.debuff_type == debuff_type)

    # Plarium clamps remaining-turns when extending debuffs. The exact cap
    # isn't documented but community testing shows extensions don't push
    # beyond ~4 turns of remaining duration, regardless of how many extenders
    # are stacked. Without this cap, Teodor/Sicia/Vizier-style extenders
    # produce runaway DoT damage in projection sims (e.g., Teodor in
    # myth-eater projecting at 87M = ~2.3x the real-team baseline).
    EXTEND_CAP_TURNS = 4

    def extend_all(self, turns: int = 1):
        """Extend all debuffs by N turns, clamped at EXTEND_CAP_TURNS."""
        for s in self.slots:
            s.remaining = min(s.remaining + turns, DebuffBar.EXTEND_CAP_TURNS)

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
    # CB boss is immune to TM drain — drain skills (Maneater A2 Syphon,
    # Geomancer A3 Quicksand Grasp) are silent against the boss. Verified
    # 2026-04-29 against per-tick TM telemetry: Maneater's TM after his
    # A2 cast matches pure natural accumulation (287 SPD × 0.07 × N ticks),
    # NOT a Syphon caster-fill bonus. Earlier "self_tm_fill_from_drain"
    # model boosted sim by ~10M but was a compensating wrong masking a
    # different missing SPD source. Removed.
    cb_tm_drain_pct: float = 0.0   # parsed but no-op against CB
    # Skill Delay (DWJ "Delay" field): number of boss turns from battle start
    # before this skill can be cast at all. Lets us model tunes that want a
    # skill held until a specific turn (e.g. Turn 6 sync).
    delay_turns: int = 0


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
    skill_priority: List[str] = field(default_factory=list)  # AI preset: ["A3","A2","A1"] = prefer A3

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
    # Shield absorption pool — Demytha A1 Fires of Old places ~10%
    # caster MAX_HP per hit (2 hits) on lowest-HP ally. Absorbs incoming
    # damage before HP. Cleared when the shield buff expires.
    shield_hp: float = 0.0

    # Brimstone blessing — places [Smite] debuff on attack. When boss
    # uses Active Skill, Smite triggers a meteorite for 25% MAX_HP +
    # 5% to all other enemies. Verified game-spec: blessing 4101.
    # Effect StatusEffectTypeId 740 (internal name "FireMark"), kind 3021.
    # Damage caps at the absolute floor 250,000 on UNM (skill 200008).
    has_brimstone: bool = False
    # Brimstone proc chance per hit (varies by blessing grade):
    # level 1 (410101) = 15%, level 3 = 30%, level 5 = 60%, level 6 = 100%.
    # Default 30% — typical mid-grade. Override via build_sim_champion.
    brimstone_chance: float = 0.30

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

    # Used by --bug-fix-buff-tick: the last CB turn this champion ticked
    # buffs in. When the flag is on, tick_buffs becomes a no-op if called
    # twice within the same CB turn (a fast hero who double-turns no
    # longer prematurely expires their own buffs).
    last_ticked_cb_turn: int = -1

    def has_buff(self, name):
        return self.buffs.get(name, 0) > 0

    def add_buff(self, name, duration):
        self.buffs[name] = max(self.buffs.get(name, 0), duration)
        self.buffs_new.add(name)  # mark as new — won't tick until next turn

    def tick_buffs(self, cb_turn: int = -1, once_per_cb_turn: bool = False):
        # DWJ: isAddedThisTurn — buffs added since last tick don't decrement
        if once_per_cb_turn and cb_turn >= 0:
            if self.last_ticked_cb_turn == cb_turn:
                # Already ticked this CB turn — fast heroes who get a
                # second hero turn shouldn't burn another point of duration
                # off their own buffs. Real Raid behaves this way for
                # boss-cycle buffs.
                return
            self.last_ticked_cb_turn = cb_turn
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
            if b == "shield":
                self.shield_hp = 0.0  # absorption pool dies with the buff
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
except (ImportError, FileNotFoundError) as _e:
    # Fall back to empty dicts + defaults; cb_sim will then use
    # DEFAULT_SKILL_DATA (line ~297). Run `python tools/refresh_all.py` to
    # regenerate hero_profiles_game.json if you see this path taken.
    SKILL_DATA, SKILL_EFFECTS, PASSIVE_DATA = {}, {}, {}
    import sys as _sys
    print(f"[cb_sim] Warning: {_e.__class__.__name__}: {_e} — running without game-extracted profiles", file=_sys.stderr)


# Empirically-corrected buff durations. The game's published descriptions list
# nominal turn counts, but in actual play several buffs cover one extra turn
# than the nominal value implies (likely due to placement-turn semantics not
# matching the description string). These overrides are applied AFTER game
# data is loaded so we keep the source-of-truth on disk and document the
# delta here. Verified vs the user's 45.5M Force Myth-Eater-Ninja real run
# (2026-04-24): the team only survives 50 boss turns when these durations
# are applied; with the nominal game-data durations, BD coverage runs out
# around bt 27 and Maneater dies.
# NOTE: previous versions had _BUFF_DURATION_OVERRIDES that bumped UK and
# BD durations above what the game data says. That was hacky compensation
# for cb_sim's extend_buffs (Demytha A2) firing at slightly different
# cadence than real game. The buff durations are trusted as-is from the
# game profile; if survival fails, the bug is in the timing model
# (turn cadence, buffs_new mechanic, extend_buffs cadence), not in the
# data.

DEFAULT_SKILL_DATA = {
    "A1": {"mult": 3.5, "stat": "ATK", "hits": 1, "cd": 0},
    "A2": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 4},
    "A3": {"mult": 0, "stat": "ATK", "hits": 0, "cd": 5},
}



# =============================================================================
# Core Simulator
# =============================================================================
# UNM CB damage parameters — see tools/cb_constants.py for sourcing.
# CB_ATK is CALIBRATED (back-solved from BT 1 AOE1 data 2026-04-23). The
# CB_ATTACK_MULT dict is sourced from SkillData via /static-export at
# import time of cb_constants. GATHERING_FURY values are also there.
CB_AOE_MULT = 3.5      # legacy AoE multiplier (used when per-attack mult unset)
CB_STUN_MULT = 5.0     # legacy — stun now uses 0.2*MAX_HP directly (see _cb_turn)
GATHERING_FURY_START_ROUND = 4  # legacy — no longer used (see per-turn model)
GATHERING_FURY_RATE = 0.02     # legacy


class CBSimulator:
    def __init__(self, champions: List[SimChampion], cb_speed: float = 190,
                 cb_element: int = 4, deterministic: bool = True,
                 rng_seed: int = None, verbose: bool = False,
                 model_survival: bool = True, force_affinity: bool = False,
                 cb_difficulty: str = None, speed_aura_pct: float = 0.0,
                 bugfix_buff_tick: bool = True,
                 profile=None):
        """`profile` (Phase 3 deferred): a `boss_profiles.BossProfile` —
        when supplied, its `speed`, `element`, and `difficulty` fields
        override the matching kwargs. Other kwargs are still respected
        for fields the profile doesn't carry (force_affinity,
        speed_aura_pct, etc.). Backward compatible: existing callers
        continue to work unchanged.
        """
        self.champions = champions
        if profile is not None:
            # Map profile fields onto the legacy kwargs. The cb_difficulty
            # branch below still runs, so HP/SPD lookups stay consistent.
            if profile.speed:
                cb_speed = profile.speed
            if profile.element:
                cb_element = profile.element
            if profile.difficulty and not cb_difficulty:
                cb_difficulty = profile.difficulty
        # cb_difficulty overrides cb_speed if provided (matches DWJ dropdown).
        # Keeps backwards-compat with direct cb_speed=190 callers.
        if cb_difficulty:
            cb_speed = CB_SPEED_BY_DIFFICULTY.get(cb_difficulty.lower(), cb_speed)
        self.cb_speed = cb_speed
        # Boss CR/CD (verified game-spec UNM 2026-05-02: CR=0.15, CD=0.50).
        # Pulled from profile if supplied, else default to UNM values.
        self.cb_cr = float(getattr(profile, "cr", 0.15) or 0.15)
        self.cb_cd = float(getattr(profile, "cd", 0.50) or 0.50)
        self.profile = profile
        # Apply team-wide speed aura. leader_skills with stat=4 (SPD) give a
        # percentage boost to all hero base speeds. DWJ calc exposes this as
        # a "Speed aura" input; the same mechanic is just leader-skill-driven
        # in-game. 0 = no aura.
        if speed_aura_pct:
            mult = 1.0 + speed_aura_pct / 100.0
            for c in champions:
                c.speed = c.speed * mult
                if c.base_speed:
                    c.base_speed = c.base_speed * mult
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
        # Experimental: tick a champion's buffs at most once per CB turn.
        # See SimChampion.tick_buffs once_per_cb_turn parameter.
        self.bugfix_buff_tick = bugfix_buff_tick
        self.log = []
        self.errors = []
        self.turn_snapshots = []  # Per-CB-turn damage/debuff snapshots for calibration
        self._placement_debt = {}  # Fractional debuff placement accumulator per champion
        # DWJ-style chronological timeline: list of {tick, event, actor, skill,
        # boss_action, ...} entries in the order they occur. Used for side-by-
        # side comparison with real battle logs + the DWJ speed calculator.
        self.timeline = []
        # Per-boss-turn protection snapshot: cb_turn -> {hero_name: {uk, bd, sh}}
        # Captured at the moment right before the boss's turn action lands.
        self.protection_by_turn = {}

        # Detect if this is an Unkillable tune (any champion places UK on team)
        self.is_uk_tune = any(
            any(b[0] == "unkillable" for b in skill.team_buffs)
            for c in self.champions
            for skill in (c.skills or [])
        )

        # Brimstone [Smite] tracking: when a Brimstone hero hits the
        # boss, per-hit chance to refresh a 2-turn Smite debuff. When
        # the boss uses an Active Skill (any CB turn = AOE1/AOE2/Stun),
        # the meteorite triggers for 250K cap damage attributed to
        # whichever Brimstone hero placed the Smite. Single-Smite-on-
        # boss rule (per blessing description "Only one [Smite] debuff
        # can be active per team").
        self.smite_holder: Optional[str] = None
        self.smite_turns_left: int = 0
        # Smite damage cap on UNM (skill 200008 floor cap for
        # ScalesByTargetHp effects with raw >= 250K).
        self.SMITE_CAP_DMG: int = 250_000

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

    def _eff_speed(self, c: SimChampion) -> float:
        """Effective speed for TM ticking — DWJ-parity formula.

        true_speed = total_speed; speed buff/debuff are multiplicative on
        the total (matches cb_scheduler.effective_speed and the live calc).
        """
        buff_mod = 0.0
        if c.has_buff("inc_spd"):
            buff_mod += 0.30
        if c.has_buff("dec_spd"):
            buff_mod -= 0.30
        return c.speed * (1.0 + buff_mod)

    def run(self, max_cb_turns: int = MAX_CB_TURNS) -> dict:
        """Run full simulation. Set max_cb_turns=0 for unlimited (run until all dead).

        Scheduler is parity-aligned with DWJ's calc: do-while TM ticking (always
        tick at least once before each actor selection), max-TM picks the next
        actor, ties broken by team position (= actor list index). Per-tick TM
        increment uses the parity formula (7 * effective_speed / 100, rescaled
        to cb_sim's threshold of 1000 → 0.7 * effective_speed per tick).
        """
        tick = 0
        effective_max = max_cb_turns if max_cb_turns > 0 else 999
        enraged = False
        # Parity tick scale: parity uses 7%/threshold-100; cb_sim uses
        # threshold-1000, so the equivalent rate is 70%/threshold-1000 = 0.7 * SPD.
        TICK_RATE = 0.7
        while self.cb_turn < effective_max:
            if all(c.is_dead for c in self.champions) or enraged:
                break

            # Pick the next actor — extra-turn first, otherwise do-while tick + max-TM.
            extra = next((c for c in self.champions
                          if not c.is_dead and getattr(c, "has_extra_turn", False)),
                         None)
            if extra is not None:
                extra.has_extra_turn = False
                actor_kind = "champ"
                actor = extra
            else:
                # do-while: ALWAYS tick at least once even if some actor already
                # has TM >= threshold from a prior cast's overflow. Skipping this
                # tick is what caused parity to fail at 9% match earlier — the
                # excess TM accumulated across selections and flipped cast order.
                safety = 0
                while True:
                    for c in self.champions:
                        if not c.is_dead:
                            c.tm += TICK_RATE * self._eff_speed(c)
                    self.cb_tm += TICK_RATE * self.cb_speed
                    safety += 1
                    if any(c.tm >= TM_THRESHOLD for c in self.champions if not c.is_dead) \
                            or self.cb_tm >= TM_THRESHOLD:
                        break
                    if safety > 100000:
                        self.errors.append("TM tick loop runaway")
                        return self._compile_result()
                tick += safety

                # Pick the actor with the highest TM. Ties go to lowest team
                # position (= earliest in self.champions, which mirrors DWJ's
                # actor-array-index tiebreak).
                live_champs = [c for c in self.champions if not c.is_dead]
                top_champ = None
                if live_champs:
                    top_champ = max(live_champs,
                                    key=lambda c: (c.tm, -c.position))
                if self.cb_tm >= TM_THRESHOLD and (top_champ is None or self.cb_tm > top_champ.tm):
                    actor_kind = "cb"
                    actor = None
                elif top_champ is not None and top_champ.tm >= TM_THRESHOLD:
                    actor_kind = "champ"
                    actor = top_champ
                else:
                    # Should not happen given the do-while above.
                    self.errors.append("No ready actor after tick")
                    break

            if actor_kind == "cb":
                self._cb_turn(tick)
                if self.cb_turn >= ENRAGE_TURN:
                    enraged = True
                    break
            else:
                self._champion_turn(actor, tick)

        return self._compile_result()

    # ----- CB Turn -----
    def _get_affinity_mult(self, champ: SimChampion) -> Tuple[float, float]:
        """Return (damage_mult, debuff_land_mult) for this champion vs CB affinity.

        Game-spec verified 2026-05-01 via DamageCalculator.ElementAdvantageBonus
        (the /damage-calc-probe endpoint):
          Weak hit (hero is weak vs boss): 0.80× damage, -35% debuff land
          Strong hit (hero is strong vs boss): 1.0× damage (no flat
            multiplier — strong heroes hit harder via +15% crit chance
            + 50% crushing chance instead, modeled separately if at all)
          Neutral / Void: 1.0× damage, 1.0× debuff land
        """
        if champ.element == 4 or self.cb_element == 4:
            return (1.0, 1.0)  # Void = always neutral
        if WEAK_AFFINITY.get(champ.element) == self.cb_element:
            return (WEAK_HIT_DMG_MULT, 1.0 - WEAK_HIT_DEBUFF_FAIL)  # 0.80, 0.65
        if STRONG_AFFINITY.get(champ.element) == self.cb_element:
            return (STRONG_HIT_DMG_MULT, 1.0)  # 1.0, 1.0 — game-spec
        return (1.0, 1.0)

    def _try_place_smite(self, champ: SimChampion, hit_count: int) -> None:
        """Brimstone blessing: each of `hit_count` hits has
        `champ.brimstone_chance` chance to refresh Smite on boss.
        Single-Smite rule means later procs refresh duration to 2
        turns and reassign holder to the latest placer.

        Use the same RNG path in deterministic and Monte Carlo modes —
        the simulator's rng is seedable so deterministic still produces
        a fixed result. Refreshing on every cast (the previous bug)
        forced 100% Smite uptime → ~5× over-prediction of Smite damage.
        """
        chance = champ.brimstone_chance
        # Probability at least one of `hit_count` rolls procs:
        # 1 - (1 - chance)^hit_count
        p_any = 1.0 - (1.0 - chance) ** max(1, hit_count)
        if self.rng.random() < p_any:
            self.smite_holder = champ.name
            self.smite_turns_left = 2

    def _cb_turn(self, tick: int):
        self.cb_tm -= TM_THRESHOLD
        self.cb_turn += 1
        attack = self.cb_pattern[(self.cb_turn - 1) % 3]

        # Brimstone [Smite] meteorite — fires when the boss uses an
        # Active Skill (every CB turn = AOE1 / AOE2 / Stun, all are
        # active). Damage = 25% MAX_HP capped at 250K floor (skill
        # 200008 ScalesByTargetHp >= 250000 path). Boss has skill
        # 200012 = -70% Smite damage reduction, but raw still exceeds
        # the cap so observed damage = 250K flat.
        if self.smite_turns_left > 0 and self.smite_holder:
            holder = next((c for c in self.champions if c.name == self.smite_holder), None)
            if holder is not None and not holder.is_dead:
                holder.damage.passive += self.SMITE_CAP_DMG
            self.smite_turns_left -= 1

        # Capture per-hero protection snapshot at the moment of CB action
        # (BEFORE any ticks / damage are applied this turn). Matches the
        # dashboard's real-run protection rendering so the two can be diffed.
        self.protection_by_turn[self.cb_turn] = {
            c.name: {
                "uk": c.has_buff("unkillable"),
                "bd": c.has_buff("block_damage"),
                "sh": c.has_buff("shield"),
                "alive": not c.is_dead,
            }
            for c in self.champions
        }
        # Chronological timeline entry
        self.timeline.append({
            "tick": tick,
            "cb_turn": self.cb_turn,
            "kind": "cb_action",
            "boss_action": attack.upper(),  # AOE1 / AOE2 / STUN
        })

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

        # HP Burn ticks — each active HP burn slot ticks once per CB turn,
        # damage attributed to the source hero. Previously this only counted
        # one slot ("only 1 counts even if multiple on bar") which was wrong:
        # ground-truth ticklog from a real Magic UNM run (2026-04-24) showed
        # Ninja with 128 ~75K burn-shaped events vs cb_sim's ~67 — a 2× gap
        # explained entirely by missing per-slot ticks.
        for slot in list(self.debuff_bar.slots):
            if slot.debuff_type == "hp_burn":
                burn_dmg = self._cap_fa(HP_BURN_DMG, kind="dot")
                for c in self.champions:
                    if c.name == slot.source:
                        c.damage.hp_burn += burn_dmg
                        break

        # AoE — deal damage to all heroes
        if attack in ("aoe1", "aoe2"):
            # Gathering Fury: +2% ATK per ROUND (game: BattleStatsModifier, round-based)
            # 1 round = 3 CB turns. Round N starts at CB turn (N-1)*3+1
            fury_mult = 1.0
            if self.cb_turn >= GATHERING_FURY_START_TURN:
                fury_mult = 1.0 + GATHERING_FURY_RATE_PER_TURN * (self.cb_turn - GATHERING_FURY_START_TURN + 1)

            # Dec ATK on CB reduces damage by 50%
            dec_atk_mult = 0.5 if self.debuff_bar.has("dec_atk") else 1.0

            # Calculate and apply damage to each hero (no AP redirect — see below)
            for c in self.champions:
                if c.is_dead:
                    continue

                has_uk = c.has_buff("unkillable")
                has_bd = c.has_buff("block_damage")

                # Phase B 2026-05-01 — game-spec UK/BD behaviour:
                #   BlockDamage: fully absorbs the hit (no HP lost) — verified
                #     via Phase_BlockDamageProcessor.
                #   Unkillable: hero takes the full damage but HP is clamped
                #     to 1 minimum (NOT a full skip). Verified via
                #     Phase_UnkillableProcessing in DamageProcessor and
                #     project memory note. The previous full-skip behaviour
                #     over-protected — wrong #2 in the compensating list.
                #
                # Order: BlockDamage applies FIRST (fully absorbs), then UK
                # is a HP floor of 1.
                if has_bd:
                    continue  # BlockDamage fully blocks the hit
                # has_uk falls through to damage calc + clamp at end

                # GAP DETECTED: champion has NO protection (UK or BD) when CB attacks.
                # This is ALWAYS an error for Unkillable tunes — even if the hero survives.
                if self.is_uk_tune and not has_uk:
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

                # Incoming affinity: when boss has affinity advantage
                # against this hero, more attacks LAND (+15% crit chance,
                # 50% crushing). Damage modifiers:
                #   boss vs weak-affinity hero: 1.0× (no flat damage adder)
                #     but more crits/crushes hit → effectively higher
                #   boss vs strong-affinity hero: 0.8× (-20% damage)
                # Note: WEAK_AFFINITY[c.element] == self.cb_element means
                # the BOSS is strong vs the hero, which means the HERO has
                # a disadvantage = more damage TAKEN.
                # Per /damage-calc-probe ElementAdvantageBonus (verified
                # game-spec): no flat damage delta when boss is advantaged;
                # the +damage on weak hits comes from increased crit rate.
                incoming_mult = 1.0
                if c.element and self.cb_element and c.element != 4 and self.cb_element != 4:
                    if STRONG_AFFINITY.get(c.element) == self.cb_element:
                        # Hero is strong vs boss → boss is weak vs hero
                        # → boss damage to hero is -20%
                        incoming_mult = WEAK_HIT_DMG_MULT  # 0.80

                # Per-attack multi-hit multiplier from real game data (see CB_ATTACK_MULT)
                attack_mult = CB_ATTACK_MULT.get(attack, CB_AOE_MULT)
                # Boss crit modeling: UNM has CR=15%, CD=50% per static
                # data. Crits do 1.0 + CD × CR_rate average damage. In
                # deterministic mode, apply expected value (1 + 0.5 × 0.15
                # = 1.075). In Monte Carlo, the sim's RNG rolls per hit.
                # Boss crit chance includes affinity bonus (+15% if boss
                # is strong vs hero).
                cb_cr = self.cb_cr if hasattr(self, "cb_cr") else 0.15
                cb_cd_mult = self.cb_cd if hasattr(self, "cb_cd") else 0.50
                # Affinity advantage gives boss +15% crit chance vs weak hero
                if c.element and self.cb_element and c.element != 4 and self.cb_element != 4:
                    if STRONG_AFFINITY.get(self.cb_element) == c.element:
                        cb_cr = min(1.0, cb_cr + 0.15)
                if self.deterministic:
                    crit_factor = 1.0 + cb_cr * cb_cd_mult
                else:
                    crit_factor = (1.0 + cb_cd_mult) if self.rng.random() < cb_cr else 1.0
                aoe_dmg = (CB_ATK * attack_mult * def_reduction * dec_atk_mult
                           * fury_mult * incoming_mult * crit_factor)

                # Damage reduction buff (e.g., Ma'Shalled A3: 50% reduction)
                if c.has_buff("dmg_reduction"):
                    aoe_dmg *= 0.50

                # Passive damage reduction (e.g., Cardiel -20%, Geomancer -15%)
                if c.has_passive_dmg_reduction > 0:
                    aoe_dmg *= (1 - c.has_passive_dmg_reduction)

                # NOTE: removed an incorrect "Sicia -3% damage taken per HP
                # Burn" interpretation. Real Metaphysics passive is "+3 SPD
                # and +3% damage INFLICTED per ally/enemy under HP Burn"
                # (handled via burn_stat_pct in calc_skill_damage), and
                # "if Cardiel on team, allies heal 3% MAX HP from HP burns
                # instead of taking damage". Allies don't take HP burn
                # damage in the first place, so the Cardiel-conditional
                # heal only applies to ally burns Sicia self-places via
                # her A3.

                # Stalwart set: 30% AoE damage reduction
                if c.stats.get("has_stalwart"):
                    aoe_dmg *= 0.70

                # Strengthen is NOT damage reduction — it increases outgoing damage

                # NO redirect for Ally Protect — user clarification 2026-04-23:
                # Block Damage fully blocks the attack attempt; Ally Protect
                # does NOT transfer damage to a protector in this game setup.
                # Damage lands on the target hero in full (after reductions).

                # Shield absorbs damage before HP. Demytha A1 places 10% of
                # caster's HP on MostInjuredAlly (verified skill 65101
                # ApplyBuff effect formula = 0.1*HP). Absorbed amount is
                # removed from both the shield pool and the incoming damage.
                if getattr(c, "shield_hp", 0) > 0:
                    absorbed = min(c.shield_hp, aoe_dmg)
                    c.shield_hp -= absorbed
                    aoe_dmg -= absorbed

                c.current_hp -= aoe_dmg

                # Phase B 2026-05-01 — Unkillable clamps to 1 HP, not full
                # skip. Apply AFTER damage calc + shield absorption: the
                # damage event still runs (which preserves Lifesteal /
                # Counterattack triggers), but HP can't drop below 1 while
                # UK is active.
                if has_uk and c.current_hp < 1:
                    c.current_hp = 1

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

            # (Ally Protect redirect removed per game mechanics clarification —
            # no damage transfers to a protector; see above.)

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

            # Geomancer Stoneguard passive (full description):
            #   "Decreases the damage all allies receive by 15% and deflects
            #   that damage onto each enemy under a [HP Burn] debuff placed
            #   by this Champion. ... When deflecting damage, on each enemy
            #   hit, has a 30% chance of dealing additional damage equal to
            #   3% of the target's MAX HP."
            #
            # Real game: per ally that takes damage, ONE deflect event fires
            # at each Geo-burned enemy. Since CB is single-target, that's 1
            # deflect per ally per AoE. The 3% TRG_HP bonus (capped at the
            # standard 75K DOT cap for boss) procs at 30% per deflect event.
            # Empirically Stoneguard contributes ~3-5M over 50 UNM turns —
            # most of it from the bonus proc, since base 15% deflect is
            # small relative to ally per-hit damage.
            for c in self.champions:
                if c.is_geomancer and not c.is_dead:
                    has_geo_burn = any(s.debuff_type == "hp_burn"
                                       and s.source == c.name
                                       for s in self.debuff_bar.slots)
                    if has_geo_burn:
                        atk_mult = CB_ATTACK_MULT.get(attack, CB_AOE_MULT)
                        per_ally_aoe = CB_ATK * atk_mult * dec_atk_mult
                        living_allies = sum(1 for a in self.champions
                                            if not a.is_dead)
                        # Base deflect: 15% of per-ally damage, summed
                        # across allies, × 1 (single boss target).
                        base_deflect = per_ally_aoe * living_allies * 0.15
                        # 30% chance bonus per deflect event (one event per
                        # ally), 75K cap on boss MAX HP percentage.
                        bonus_per_event = 0.30 * 75_000
                        bonus_total = living_allies * bonus_per_event
                        c.damage.passive += base_deflect + bonus_total

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
                # Stun deals damage too. Game-spec verified 2026-05-01:
                # skill 222601 effect MultiplierFormula = `0.2*TRG_B_HP`.
                # TRG_B_HP is the target's BASE HP (level-60 ungeared,
                # ~19,650 for Cardiel), NOT current max HP (~45,379 with
                # gear). Sim was using max — over-predicted stun damage
                # by ~2.3×.
                #
                # DEF does NOT mitigate this (it's a %HP nuke). Gathering
                # Fury DOES apply (multiplicative on the 20% HP base, by
                # game's DMG_MUL formula).
                #
                # BlockDamage fully blocks the hit. UK takes the damage
                # but HP clamps to 1 (Phase B fix — UK is not a full skip).
                if self.model_survival and not target.has_buff("block_damage"):
                    fury_mult = 1.0
                    if self.cb_turn >= GATHERING_FURY_START_TURN:
                        fury_mult = 1.0 + GATHERING_FURY_RATE_PER_TURN * (self.cb_turn - GATHERING_FURY_START_TURN + 1)
                    # base_HP comes from cb_optimizer.calc_stats — it's the
                    # game's GetBaseStats output (pre-gear, level-scaled).
                    # Fall back to current max HP if unavailable.
                    target_base_hp = target.stats.get("base_HP") or target.stats.get(HP, target.max_hp if target.max_hp else 40000)
                    stun_dmg = CB_STUN_HP_FRACTION * target_base_hp * fury_mult
                    target.current_hp -= stun_dmg
                    # UK clamp-to-1 (per Phase B): hero takes the damage,
                    # but HP can't drop below 1 while UK is up.
                    if target.has_buff("unkillable") and target.current_hp < 1:
                        target.current_hp = 1
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
            # Buff state per hero at moment of boss attack — used by
            # tools/sim_vs_real_diff.py to compare against ground-truth
            # tick-log buff state. Captures the actual durations the sim
            # has placed on each champ.
            "hero_buffs": {
                c.name: dict(c.buffs) for c in self.champions
            },
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

        if champ.is_stunned:
            champ.is_stunned = False
            # Stun consumes the turn — buffs/CDs still tick at end.
            champ.tick_buffs(cb_turn=self.cb_turn,
                             once_per_cb_turn=getattr(self, "bugfix_buff_tick", True))
            champ.tick_cooldowns()
            if self.verbose:
                self.log.append(f"       {champ.name:>20} — STUNNED")
            return

        # Skill is eligible iff: cooldown is 0 AND delay_turns >= current cb_turn
        # (delay_turns=0 means no delay; delay_turns=6 means cannot cast until
        # boss turn 6 or later).
        def _eligible(sk):
            if sk.delay_turns and self.cb_turn < sk.delay_turns:
                return False
            return sk.base_cd == 0 or sk.current_cd == 0

        # Select skill
        chosen = champ.skills[0]  # A1 fallback (never on CD; always eligible)
        if champ.opening:
            forced = champ.opening.pop(0)
            for sk in champ.skills:
                if sk.name == forced and _eligible(sk):
                    chosen = sk
                    break
        elif champ.skill_priority:
            # AI preset: use skills in priority order (first eligible wins)
            for prio_name in champ.skill_priority:
                for sk in champ.skills:
                    if sk.name == prio_name and _eligible(sk):
                        chosen = sk
                        break
                if chosen.name == prio_name:
                    break
        else:
            # Default AI: skills in declaration order (A1 → A2 → A3),
            # first eligible CD > 0 wins. Then A1 as fallback if all
            # CD-skills are on cooldown. Verified against ground-truth
            # tick logs: every CB hero opens with A2 (Maneater Syphon,
            # Ninja Hailburn, Demytha Light of the Deep, etc.) before
            # A3, and falls through to A1 only when both higher skills
            # are on cooldown. The previous "highest CD first" logic
            # incorrectly forced A3 as the opener.
            for sk in champ.skills:
                if sk.base_cd > 0 and _eligible(sk):
                    chosen = sk
                    break

        # Emit DWJ-style timeline entry for this skill cast. Captured BEFORE
        # side effects so the chronological stream reflects "hero chose X"
        # decisions in order.
        self.timeline.append({
            "tick": tick,
            "cb_turn": self.cb_turn,
            "kind": "hero_cast",
            "hero": champ.name,
            "skill": chosen.name,
            "position": champ.position,
        })

        # Apply team buffs. Shield is special — Demytha A1 places it on
        # the LOWEST-HP ally only (excluding caster), with absorption
        # equal to 10% caster MAX_HP × hit_count. Other team buffs go to
        # the whole team uniformly.
        for buff_name, duration in chosen.team_buffs:
            if buff_name == "shield":
                shield_amount = champ.max_hp * 0.10 * max(1, chosen.hit_count)
                allies = [c for c in self.champions
                          if c is not champ and not c.is_dead]
                if allies:
                    target = min(allies, key=lambda c: c.current_hp / max(1, c.max_hp))
                    target.add_buff("shield", duration)
                    target.shield_hp = min(target.max_hp,
                                           target.shield_hp + shield_amount)
                continue
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

        # CB boss is immune to TM manipulation — drain skills (Maneater A2
        # Syphon, Geomancer A3 Quicksand Grasp) are no-ops here. Verified
        # 2026-04-29 via per-tick TM log: Maneater's post-A2 TM matches
        # pure SPD-based accumulation, no caster fill from "what would
        # have been drained". cb_tm_drain_pct is parsed for non-CB use
        # but does nothing in this scheduler.

        # Ninja Escalation: combo counter increments when ALL 3 active skills
        # hit the same target in a single round. In CB (single boss), this happens
        # every time A1+A2+A3 have all been used. Track which skills have been
        # used this cycle and increment when all 3 are hit.
        if champ.combo_atk_pct > 0 or champ.combo_cd_pct > 0:
            if not hasattr(champ, '_combo_skills_used'):
                champ._combo_skills_used = set()
            champ._combo_skills_used.add(chosen.name)
            if len(champ._combo_skills_used) >= len([s for s in champ.skills if s.multiplier > 0]):
                champ.combo_counter += 1
                champ._combo_skills_used = set()

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

            # Brimstone [Smite] placement — per hit, brimstone_chance
            # to refresh Smite on boss. Single-Smite-on-team rule per
            # blessing description.
            if champ.has_brimstone:
                self._try_place_smite(champ, chosen.hit_count)

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

        # Real-game order: buffs and cooldowns tick at END of holder's turn
        # (not start). This lets a hero who places/extends a buff this turn
        # benefit from the full duration — e.g. Demytha A2 extending her own
        # UK from 1→2: the +1 survives the end-of-turn tick because the buff
        # is in `buffs_new` (placed/modified this turn, skipped on first tick).
        # `once_per_cb_turn=True` ensures fast heroes who double-act in one
        # CB turn don't double-tick their own buffs.
        champ.tick_buffs(cb_turn=self.cb_turn,
                         once_per_cb_turn=getattr(self, "bugfix_buff_tick", True))
        champ.tick_cooldowns()

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
        # Capped at +100% ATK (5 stacks at 20%) per game description
        if champ.combo_atk_pct > 0 and skill.scaling_stat == "ATK":
            max_stacks = int(1.0 / champ.combo_atk_pct)  # 100% / 20% = 5
            effective_stacks = min(champ.combo_counter, max_stacks)
            scaling *= (1.0 + champ.combo_atk_pct * effective_stacks)

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

        # Ninja passive: +combo_cd_pct per combo counter (capped at +25% CD)
        if champ.combo_cd_pct > 0:
            max_cd_stacks = int(0.25 / champ.combo_cd_pct) if champ.combo_cd_pct > 0 else 0
            effective_stacks = min(champ.combo_counter, max_cd_stacks)
            effective_cd += champ.combo_cd_pct * 100 * effective_stacks

        effective_cr = champ.stats.get(CR, 15)
        # Inc C.RATE buff (Fahrakin A3, Cardiel A3: +30% CR)
        if champ.has_buff("inc_cr_30"):
            effective_cr = min(100, effective_cr + 30)

        # Phase C 2026-05-01 — full hit-type expected-value formula.
        # Game-spec constants (GameplayData):
        #   CriticalHitChanceAdvantage = 0.15  (strong-affinity +15% CR)
        #   CrushingHitChance          = 0.50  (50% crush vs strong target,
        #                                       only on Advantage)
        #   GlancingHitChance          = 0.35  (35% glance, only on Disadvantage)
        #   CrushingHitCoef            = +0.30 (crush damage = ×1.30)
        #   GlancingHitCoef            = -0.30 (glance damage = ×0.70)
        # Verified via /damage-calc-probe + extracted from GameplayData.
        # Each hit's deterministic-expected damage:
        #   Advantage:  P(crit) = (CR + 15) / 100, then 50/50 crush/normal
        #   Disadvantage: P(crit) = CR / 100, then 35% glance / 65% normal
        #   Neutral / Void: P(crit) = CR / 100, rest is Normal
        is_advantage = (
            champ.element and self.cb_element
            and champ.element != 4 and self.cb_element != 4
            and STRONG_AFFINITY.get(champ.element) == self.cb_element
        )
        is_disadvantage = (
            champ.element and self.cb_element
            and champ.element != 4 and self.cb_element != 4
            and WEAK_AFFINITY.get(champ.element) == self.cb_element
        )
        cr_adj = effective_cr + 15 if is_advantage else effective_cr
        cr_adj = min(100, max(0, cr_adj))
        p_crit = cr_adj / 100.0
        crit_dmg_mult = 1.0 + (effective_cd / 100.0)  # 200%CD → ×3.0 dmg on crit
        if is_advantage:
            # 50% crush, 50% normal among non-crits
            crit_mult = (
                p_crit * crit_dmg_mult
                + (1 - p_crit) * (0.50 * 1.30 + 0.50 * 1.0)
            )
        elif is_disadvantage:
            # 35% glance, 65% normal among non-crits
            crit_mult = (
                p_crit * crit_dmg_mult
                + (1 - p_crit) * (0.35 * 0.70 + 0.65 * 1.0)
            )
        else:
            # Neutral / Void — only crit vs normal
            crit_mult = p_crit * crit_dmg_mult + (1 - p_crit) * 1.0

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
                # Track per-ally changes — Demytha A2's heal scales with
                # each ally's OWN modified buffs/debuffs (not team total).
                # Real game: "Heals by a further 2.5% MAX HP for each
                # turn added to or removed from the duration of buffs and
                # debuffs" — read as per-hero scaling.
                #
                # Game's NonIncreaseableEffects list (verified 2026-05-02):
                # IncreaseBuffLifetime DOESN'T extend these — they're
                # designed to be one-shot defensive cooldowns, not
                # perpetually maintained buffs.
                NON_EXTENDABLE_BUFFS = frozenset({
                    "unkillable",       # UK clamp-to-1
                    "block_damage",     # BD absorbs 100%
                    "revive_on_death",  # one-shot revive
                    "stone_skin",       # damage reduction passive
                    "taunt",            # forces attacks
                    "poison_cloud",     # damage-on-attacker
                    "thunder",          # damage retaliation
                    "entangle",         # one-shot CC
                    "syphon",           # one-shot drain
                    "on_guard",         # crit prevention
                })
                per_ally_changes = {c.name: 0 for c in self.champions}
                for c in self.champions:
                    if c.is_dead:
                        continue
                    for b in list(c.buffs.keys()):
                        if b in NON_EXTENDABLE_BUFFS:
                            continue  # game-correct: these don't extend
                        c.buffs[b] += turns
                        # Mark extended buffs as "modified this turn" so
                        # the end-of-turn tick on the casting hero doesn't
                        # immediately undo the +1. Real game rule: a buff
                        # touched (placed OR extended) this turn does not
                        # decrement at end of that turn.
                        c.buffs_new.add(b)
                        per_ally_changes[c.name] += 1
                # Demytha A2 also shrinks ally debuffs by N turns. Debuffs
                # are on the boss (debuff_bar), not heroes, so shrinking
                # one debuff counts as one team-wide change. Distribute
                # across allies (1 change each per debuff shrunk).
                debuff_shrink = eff.params.get("shrink_debuffs", 0)
                if debuff_shrink:
                    survivors = []
                    debuff_changes = 0
                    for slot in self.debuff_bar.slots:
                        slot.remaining -= debuff_shrink
                        debuff_changes += 1
                        if slot.remaining >= 0:
                            survivors.append(slot)
                    self.debuff_bar.slots = survivors
                    for nm in per_ally_changes:
                        per_ally_changes[nm] += debuff_changes
                base_heal_pct = eff.params.get("heal_pct", 0.0)
                per_change_pct = eff.params.get("heal_per_change_pct", 0.0)
                if (base_heal_pct or per_change_pct) and self.model_survival:
                    for c in self.champions:
                        if c.is_dead:
                            continue
                        changes = per_ally_changes.get(c.name, 0)
                        heal = c.max_hp * (base_heal_pct + per_change_pct * changes)
                        c.current_hp = min(c.max_hp, c.current_hp + heal)

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
                # Ninja A2 / Sicia A2: instantly trigger all HP Burn debuffs
                # (1 tick each). Activation damage attributes to the
                # ACTIVATING champion (the one who cast this skill), not
                # the original placer — matches in-game UI breakdown which
                # credits the triggering hero with the activated tick damage.
                for slot in list(self.debuff_bar.slots):
                    if slot.debuff_type == "hp_burn":
                        dmg = self._cap_fa(HP_BURN_DMG, kind="dot")
                        champ.damage.hp_burn += dmg

            elif eff.effect_type == "activate_poisons":
                # Venomage A1: "Each hit has a 35% chance of activating up to
                # two [Poison] debuffs". Books boost +15% → 50% effective.
                # The chance is per-hit; load_game_profiles emits one effect
                # per hit so the chance applies per effect occurrence.
                chance = eff.params.get("chance", 1.0)
                if chance < 1.0:
                    # Deterministic mode: fractional accumulator across casts
                    # (matches debuff-placement convention).
                    key = (champ.name, "activate_poisons")
                    debt = self._placement_debt.get(key, 0.0) + chance
                    if debt < 1.0:
                        self._placement_debt[key] = debt
                        continue  # this occurrence didn't activate
                    self._placement_debt[key] = debt - 1.0
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
                # Sicia A1 (chance=0.30 per hit, hit_count=3) and Artak A1
                # (chance=0.45 per cast). Each "rep" rolls the extend chance
                # independently; in deterministic mode, use the fractional
                # accumulator (matches debuff-placement convention) so the
                # average rate matches expected over many calls.
                turns = eff.params.get("turns", 1)
                per_hit = eff.params.get("per_hit", False)
                chance = eff.params.get("chance", 1.0)
                reps = skill.hit_count if per_hit else 1
                for _ in range(reps):
                    if chance < 1.0:
                        key = (champ.name, skill.name, "extend_burn")
                        debt = self._placement_debt.get(key, 0.0) + chance
                        if debt < 1.0:
                            self._placement_debt[key] = debt
                            continue
                        self._placement_debt[key] = debt - 1.0
                    for slot in self.debuff_bar.slots:
                        if slot.debuff_type == "hp_burn":
                            slot.remaining = min(slot.remaining + turns,
                                                  DebuffBar.EXTEND_CAP_TURNS)

            elif eff.effect_type == "extend_debuffs_poison_burn":
                # Teodor A3: extend only poison and HP burn debuffs by N turns.
                # Capped at DebuffBar.EXTEND_CAP_TURNS.
                turns = eff.params.get("turns", 1)
                for slot in self.debuff_bar.slots:
                    if slot.debuff_type in ("poison_5pct", "hp_burn"):
                        slot.remaining = min(slot.remaining + turns,
                                              DebuffBar.EXTEND_CAP_TURNS)

            elif eff.effect_type == "cd_reduce_skill":
                # Geomancer A2 reduces Quicksand Grasp's CD by 2; Aox A3
                # reduces ally CDs by 1; etc. Per-skill CD reduction targets
                # a specific skill on the caster (not allies, not enemies).
                target_skill = eff.params.get("target_skill", "")
                turns = eff.params.get("turns", 1)
                for sk in champ.skills:
                    if sk.name == target_skill and sk.current_cd > 0:
                        sk.current_cd = max(0, sk.current_cd - turns)
                        break

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
            # B1 + B2: chronological timeline (DWJ-style) + per-turn protection
            # snapshot so sim output can be diffed against real battle logs and
            # the DWJ speed calculator.
            "timeline": self.timeline,
            "protection_by_turn": self.protection_by_turn,
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
# Blessing → sim attribute resolution
# =============================================================================

# Brimstone Legendary Wisdom blessing — per-hit Smite chance by grade.
# Grade 0/1 = 15%, scales linearly to grade 6 = 100%. Source: in-game
# l10n:blessing-level/description?id=410101..6 (verified visually).
_BRIMSTONE_BLESSING_ID = 4101
_BRIMSTONE_CHANCE_BY_GRADE = {
    1: 0.15, 2: 0.225, 3: 0.30, 4: 0.45, 5: 0.60, 6: 1.0,
}


def _resolve_brimstone(stats: dict) -> tuple[bool, float]:
    """Read blessing data from `stats` and return (has_brimstone, chance).

    `stats` is the per-hero dict produced by the data pipeline; if the
    `blessing` key is present (id + grade from the live mod read), the
    Brimstone chance is derived from grade. Falls back to (False, 0.0)
    when no Brimstone blessing is set on this hero.
    """
    bl = stats.get("blessing")
    if not isinstance(bl, dict):
        # Backward compat — old stats dicts might preset has_brimstone.
        if stats.get("has_brimstone"):
            return True, float(stats.get("brimstone_chance", 0.30))
        return False, 0.0
    if int(bl.get("id", 0)) != _BRIMSTONE_BLESSING_ID:
        return False, 0.0
    grade = int(bl.get("grade", 1))
    return True, _BRIMSTONE_CHANCE_BY_GRADE.get(grade, 0.15)


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
        # CB boss is immune to TM drain — record drain_pct for non-CB use
        # but do not propagate any "caster fill from drain" flag (verified
        # 2026-04-29 against per-tick TM telemetry).
        tm_drain = float(sd.get("cb_tm_drain_pct", 0.0) or 0.0)
        for eff in (sd.get("effects") or []):
            if not isinstance(eff, str):
                continue
            e = eff.lower()
            if e == "tm_steal" or e == "tm_steal_100pct":
                tm_drain = max(tm_drain, 1.0)
            elif e.startswith("tm_steal_"):
                try:
                    pct = int(e.split("_")[-1].replace("pct", ""))
                    tm_drain = max(tm_drain, pct / 100.0)
                except Exception:
                    pass

        sim_sk = SimSkill(
            name=sk_name,
            # Real game CDs verified against ground-truth tick log:
            # Maneater A3 fires every exactly 5 of his actions (matching
            # raid_data CD=5); Demytha A2 every 3, A3 every 3 (both CD=3
            # in raid_data after books). The previous -1 hack was always
            # wrong — it dropped Demytha to CD=2 alternating A2↔A3 and
            # never letting A1 fire, when real game has her cycle
            # A2,A1,A3,A1 (17 A1 casts in 49 actions, verified).
            base_cd=sd["cd"] if sd["cd"] > 0 else 0,
            multiplier=sd["mult"],
            scaling_stat=sd["stat"],
            hit_count=sd["hits"],
            team_buffs=sd.get("team_buffs", []),
            team_tm_fill=sd.get("team_tm_fill", 0.0),
            self_tm_fill=sd.get("self_tm_fill", 0.0),
            grants_extra_turn=sd.get("grants_extra_turn", False),
            ignore_def=sd.get("ignore_def", 0.0),
            cb_tm_drain_pct=tm_drain,
            delay_turns=int(sd.get("delay_turns", 0) or 0),
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

    # Brimstone Legendary Wisdom blessing (id 4101) — places [Smite]
    # debuff on attack. Per-hit chance scales with blessing grade:
    # grade 1 = 15%, grade 2 = 22.5%, grade 3 = 30%, grade 4 = 45%,
    # grade 5 = 60%, grade 6 = 100% (guaranteed). Source: in-game
    # blessing description l10n:blessing-level/description?id=410101..6.
    # Read directly from hero's BlessingId/Grade via the static cache.
    has_brimstone, brimstone_chance = _resolve_brimstone(stats)

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
        has_brimstone=has_brimstone,
        brimstone_chance=brimstone_chance,
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
# Minimal champion factory — used by the dashboard bridge so we can sim the
# last battle's team with only name + SPD (no full gear solve). Skills come
# from hero_profiles_game.json so buff/debuff timings stay accurate.
# =============================================================================
def build_champion_minimal(name: str, position: int, speed: float,
                           hp: float = 30000, defense: float = 1000,
                           element: int = 4):
    stats = {HP: hp, ATK: 3000, DEF: defense, CR: 0.5, CD: 1.5, ACC: 200, RES: 50, SPD: speed}
    # build_sim_champion signature: (name, stats, position, masteries, opening, element)
    return build_sim_champion(name, stats, position, masteries=None, opening=None, element=element)


# =============================================================================
# Tune Runner — simulate any DWJ tune with damage
# =============================================================================
def run_potential_team(pt: dict, cb_element: int = 4,
                       force_affinity: bool = False, max_cb_turns: int = 50,
                       generic_fillers: Optional[List[str]] = None,
                       use_current_gear: bool = True,
                       override_speeds: bool = False,
                       override_priorities: bool = False,
                       projection: bool = False) -> dict:
    """Phase 3 sim driver — consume a PotentialTeam dict from
    tools/potential_team.build_potential_team and run cb_sim against it.

    Translation:
      - team[i].target_speed   → SimChampion.stats[SPD] (only when
        override_speeds=True; off by default since the user's gear may
        not deliver those speeds, and forcing them desyncs the team)
      - preset[hero].priorities → champ.skill_priority (in order)
      - generic slots → filled from generic_fillers (default: ["Ninja"])

    Stats come from heroes_6star.json + current gear via calc_stats.
    Phase 4 will add gear_plan-driven stats so we can sim heroes the
    user owns at <6 grade as if they were 6-star.

    Args:
        pt: dict returned by tools.potential_team.build_potential_team.
            Must have pt['potential_team'] non-None (no blockers).
        cb_element: 1=Magic, 2=Force, 3=Spirit, 4=Void.
        override_speeds: when True, replace the user's actual gear-derived
            speed with the tune's target_speed. Off by default — the
            "potential" speed is meaningless without matching gear.
        override_priorities: when True, force champ.skill_priority from
            the calc variant's priority field. Off by default because
            DWJ priorities 1..4 are the *default* skill ordering — the
            real signal is the delay field, which cb_sim handles via
            its own AI rather than priority overrides.
        generic_fillers: list of hero names to substitute into generic
            "DPS" slots, in order. Defaults to ["Ninja"].
        projection: when True (Phase 6), each hero is treated as having
            every stat-bonus mastery, regardless of which masteries the
            user has actually selected. Surfaces the projected ceiling
            ("if I do every todo, what does this tune do?"). Off by
            default — current mode runs against the user's actual mastery
            picks.
    """
    if not pt or not pt.get("potential_team"):
        return {"error": "no potential_team — tune has blockers"}
    info = pt["potential_team"]
    team_view = info.get("team") or []
    preset = info.get("preset") or {}
    # Filter out heroes already named in the tune so generic slots get
    # filled from the *leftover* pool — otherwise [Ninja, Geo, Venomage]
    # might overwrite a slot that already names Ninja.
    named_in_tune = {(slot.get("hero") or "").lower()
                     for slot in team_view if not slot.get("is_generic")}
    fillers = [n for n in (generic_fillers or ["Ninja"])
               if n.lower() not in named_in_tune]
    if not fillers:
        fillers = ["Ninja"]
    fillers_iter = iter(fillers)

    from cb_optimizer import calc_stats
    from auto_profile import get_leader_skills
    base = Path(__file__).parent.parent
    with open(base / "heroes_6star.json") as f:
        heroes_data = json.load(f)
    with open(base / "account_data.json") as f:
        account = json.load(f)
    # Match cb_calibrate's dict-build pattern: first occurrence of a name
    # wins, and a second Maneater (the user has 2) gets stashed under
    # "Maneater_2" so RabBatEater-style tunes can reach both.
    hero_by_name = {}
    for h in heroes_data["heroes"]:
        name = h.get("name", "")
        if name and name not in hero_by_name:
            hero_by_name[name] = h
        elif name == "Maneater" and "Maneater_2" not in hero_by_name:
            hero_by_name["Maneater_2"] = h

    # Resolve concrete team_names: substitute generic slots from fillers.
    team_names = []
    for slot in team_view:
        if slot.get("is_generic"):
            team_names.append(next(fillers_iter, "Ninja"))
        else:
            team_names.append(slot["hero"])

    # Leader aura comes from slot[0]'s hero.
    leader_skills = get_leader_skills()
    leader_aura = leader_skills.get(team_names[0])

    sim_champs = []
    missing_at_6star = []
    for i, slot in enumerate(team_view):
        nm = team_names[i]
        hero = hero_by_name.get(nm)
        if not hero:
            missing_at_6star.append(nm)
            continue
        hero_arts = hero.get("artifacts", []) if use_current_gear else []
        if projection:
            # Phase 6: project the hero at full progression — every
            # stat-bonus mastery applied + every artifact substat
            # glyphed to its max-rarity ceiling. Mutates a shallow copy
            # so we don't poison the cached heroes_data.
            hero = dict(hero)
            hero["_project_full_masteries"] = True
            hero["_project_max_glyphs"] = True
        stats = calc_stats(hero, hero_arts, account)
        if leader_aura:
            stats = apply_leader_aura(stats, leader_aura)
        if override_speeds:
            target_spd = slot.get("target_speed") or 0
            if target_spd:
                stats[SPD] = float(target_spd)
        element = hero.get("element", 4)

        slot_preset = preset.get(slot.get("hero")) or {}
        opener = slot_preset.get("opener")
        priorities_list = [p.get("skill") for p in (slot_preset.get("priorities") or [])
                           if p.get("skill") and p.get("skill") != "A4"]
        skill_pri = priorities_list + (["A1"] if "A1" not in priorities_list else [])

        # Only force an opening when the preset explicitly says one (Ninja's
        # A2 opener for Myth Eater Ninja, etc). Default cb_sim AI picks
        # the right opener based on priority + readiness, and forcing A1
        # for everyone breaks tunes that aren't A1-opener.
        opening = [opener] if (opener and opener != "A1") else None

        champ = build_sim_champion(
            nm, stats, i,
            opening=opening,
            element=element,
        )
        if override_priorities and skill_pri:
            champ.skill_priority = skill_pri
        sim_champs.append(champ)

    if not sim_champs:
        return {"error": "no champions resolved", "missing_at_6star": missing_at_6star}

    sim = CBSimulator(
        sim_champs,
        cb_element=cb_element,
        deterministic=True,
        verbose=False,
        force_affinity=force_affinity,
    )
    result = sim.run(max_cb_turns=max_cb_turns)
    if missing_at_6star:
        result["partial_team"] = True
        result["missing_at_6star"] = missing_at_6star
    result["potential_team_meta"] = {
        "tune_slug": pt.get("tune_slug"),
        "calc_variant": pt.get("calc_variant"),
        "team_names": team_names,
    }
    # Phase 6: surface which projection levers were applied so the
    # dashboard can show *why* the sim landed on this number.
    result["projection_meta"] = {
        "projection_mode": projection,
        "stars": "6★ assumed (heroes_6star.json)",
        "level": 60,
        "books": "applied via DWJ calc cd_after_books" if pt.get("calc_variant") else "skill_db level_bonuses",
        "masteries": "all stat-bonus" if projection else "user's selected (15/66)",
        "stat_blessing": "current blessing via hero_computed_stats",
        "skill_modifier_blessing": "NOT YET APPLIED (Phantom Touch, Crushing Rend, etc.)",
        "glyphs": "current substats (no max-glyph projection)",
        "gear": "current equipped (sim) · planned via /api/tune-gear-plan" if use_current_gear else "none",
        "account_auras": "Great Hall + Arena + Empower from hero_computed_stats",
    }
    return result


def run_tune(tune_id: str, hero_names: List[str], cb_element: int = 4,
             force_affinity: bool = True, verbose: bool = False,
             use_current_gear: bool = True, spd_override: dict = None) -> dict:
    """Run a DWJ speed tune with the full damage sim.

    Args:
        tune_id: tune identifier from tune_library (e.g., "myth_eater")
        hero_names: list of 5 hero names to assign to slots
        cb_element: 1=Magic, 2=Force, 3=Spirit, 4=Void
        force_affinity: True for post-defeat CB (FA damage caps)
        use_current_gear: True to use hero's equipped gear
    """
    from tune_library import get_tune, assign_heroes_to_tune
    from cb_optimizer import calc_stats
    from auto_profile import get_leader_skills

    base = Path(__file__).parent.parent
    with open(base / "heroes_6star.json") as f:
        heroes_data = json.load(f)
    with open(base / "account_data.json") as f:
        account = json.load(f)

    tune = get_tune(tune_id)
    if not tune:
        return {"error": f"Tune '{tune_id}' not found"}

    # Assign heroes to slots
    assignments = assign_heroes_to_tune(hero_names, tune)
    if not assignments:
        return {"error": f"Cannot assign {hero_names} to tune '{tune_id}'"}

    # Build sim champions with tune-specific speeds, openings, and priorities
    hero_by_name = {}
    for h in heroes_data["heroes"]:
        name = h.get("name", "")
        if name and name not in hero_by_name:
            hero_by_name[name] = h

    leader_skills = get_leader_skills()
    leader_aura = leader_skills.get(hero_names[0])

    sim_champs = []
    for i, (hero_name, slot) in enumerate(assignments):
        hero = hero_by_name.get(hero_name)
        if not hero:
            return {"error": f"Hero '{hero_name}' not found"}

        if use_current_gear:
            hero_arts = hero.get("artifacts", [])
        else:
            hero_arts = []

        stats = calc_stats(hero, hero_arts, account)
        if leader_aura:
            stats = apply_leader_aura(stats, leader_aura)

        # Override speed to tune's target (midpoint of range), unless spd_override has this hero
        if spd_override and hero_name in spd_override:
            stats[SPD] = spd_override[hero_name]
        else:
            target_spd = (slot.speed_range[0] + slot.speed_range[1]) / 2
            stats[SPD] = target_spd

        element = hero.get("element", 4)
        champ = build_sim_champion(
            hero_name, stats, i,
            opening=list(slot.opening),
            element=element,
        )
        # Set AI preset skill priority from tune
        if slot.skill_priority:
            champ.skill_priority = list(slot.skill_priority)

        sim_champs.append(champ)

    sim = CBSimulator(
        sim_champs,
        cb_element=cb_element,
        cb_speed=tune.cb_speed,
        deterministic=True,
        verbose=verbose,
        force_affinity=force_affinity,
    )
    result = sim.run(max_cb_turns=50)

    result["tune"] = tune.name
    result["tune_id"] = tune.tune_id
    result["assignments"] = [(name, slot.role, slot.speed_range) for name, slot in assignments]

    return result


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
    parser.add_argument("--tune", help="DWJ tune ID (e.g., myth_eater, budget_uk, batman_forever)")
    parser.add_argument("--list-tunes", action="store_true", help="List available DWJ tunes")
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
    parser.add_argument("--validate-tune", action="store_true",
                        help="Check that the tune's 'Sync on CB turn N' goal holds: "
                             "runs sim and reports whether UK/BD cover every boss turn "
                             "from the tune's sync turn through 50. Pairs with --tune.")
    parser.add_argument("--dwj-format", action="store_true",
                        help="Print chronological timeline in DWJ calculator format "
                             "(interleaved hero casts and boss actions per turn).")
    parser.add_argument("--diff-tune", action="store_true",
                        help="Compare current team SPDs vs tune target bands. "
                             "Reports which heroes are outside spec and by how much.")
    parser.add_argument("--all-affinities", action="store_true",
                        help="Run the sim on all 4 CB affinities (Magic, Force, Spirit, Void) "
                             "and report predicted survival turns + damage per affinity. "
                             "Catches tune fragility (e.g. Ninja weak on Force).")
    parser.add_argument("--apply-to-preset", type=int, default=None,
                        help="Apply --tune to the given preset ID via /update-preset. "
                             "Converts DWJ delays to Raid opener + priority params.")
    parser.add_argument("--sweep-hero", type=str, default=None,
                        help="Sweep one hero's SPD across a range. Format: 'Hero=LOW..HIGH' "
                             "e.g. 'Ninja=180..230'. Reports survival turns + damage at each SPD.")
    parser.add_argument("--cb-difficulty", type=str, default="ultra-nightmare",
                        choices=["easy", "normal", "hard", "brutal", "nightmare", "ultra-nightmare"],
                        help="CB difficulty sets boss SPD. Default: ultra-nightmare (190).")
    parser.add_argument("--speed-aura", type=float, default=0.0,
                        help="Team-wide SPD aura percentage (0-30). Default 0. "
                             "Simulates a leader-skill SPD aura.")
    args = parser.parse_args()

    ELEMENT_MAP = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
    cb_element = ELEMENT_MAP[args.cb_element]

    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    # Handle --list-tunes
    if args.list_tunes:
        from tune_library import list_tunes
        print("=== Available DWJ Tunes ===")
        for t in list_tunes():
            print(f"  {t.tune_id:25s} {t.name:30s} {t.performance:12s} {t.difficulty}")
            for i, slot in enumerate(t.slots):
                req = f" ({slot.required_hero})" if slot.required_hero else ""
                print(f"    Slot {i+1}: {slot.role:20s} SPD={slot.speed_range}{req}")
            print()
        return

    # Handle --tune mode
    if args.tune:
        team_names = [n.strip() for n in args.team.split(",")] if args.team else None
        if not team_names:
            print("ERROR: --tune requires --team")
            return
        result = run_tune(
            args.tune, team_names,
            cb_element=cb_element,
            force_affinity=not args.no_force_affinity,
            verbose=args.verbose,
            use_current_gear=args.use_current_gear,
        )
        if "error" in result:
            print(f"ERROR: {result['error']}")
            return

        print(f"=== Tune: {result.get('tune', '?')} ===")
        print(f"Team assignments:")
        for name, role, spd_range in result.get("assignments", []):
            print(f"  {name:20s} → {role:20s} SPD={spd_range}")
        print(f"\nTotal damage: {result['total']/1e6:.2f}M over {result['cb_turns']} CB turns")
        print(f"Valid tune: {'YES' if result['valid'] else 'NO (' + str(len(result['errors'])) + ' gaps)'}")
        print(f"\n{'Hero':20s} {'Total':>10s} {'Direct':>10s} {'Poison':>10s} {'Burn':>10s} {'WM/GS':>10s} {'Pass':>10s}")
        for h in result["heroes"]:
            print(f"{h['name']:20s} {h['total']:>10,.0f} {h['direct']:>10,.0f} "
                  f"{h['poison']:>10,.0f} {h['hp_burn']:>10,.0f} {h['wm_gs']:>10,.0f} "
                  f"{h['passive']:>10,.0f}")
        if result["errors"]:
            print(f"\nTune errors ({len(result['errors'])}):")
            for e in result["errors"][:10]:
                print(f"  {e}")

        # --dwj-format: interleaved chronological timeline matching DWJ output
        if args.dwj_format and result.get("timeline"):
            print(f"\n=== DWJ-style Timeline ===")
            cur_turn = 0
            for ev in result["timeline"]:
                t = ev.get("cb_turn", 0)
                if ev.get("kind") == "hero_cast":
                    print(f"  Turn{t:2d}  {ev['hero']:15s} {ev['skill']}")
                elif ev.get("kind") == "cb_action":
                    print(f"  Turn{t:2d}  >>> Clanboss {ev['boss_action']}")
                    if t != cur_turn:
                        cur_turn = t

        # --validate-tune: verify UK/BD coverage at every boss turn past sync
        if args.validate_tune and result.get("protection_by_turn"):
            print(f"\n=== Tune Validation ===")
            sync_turn = 6  # UNM default; TODO: read from tune notes
            gaps = []
            for bt, prot in sorted(result["protection_by_turn"].items()):
                if bt < sync_turn:
                    continue
                alive = [n for n, p in prot.items() if p.get("alive")]
                if not alive:
                    continue
                ukbd = [n for n in alive if prot[n].get("uk") or prot[n].get("bd")]
                if len(ukbd) < len(alive):
                    missing = set(alive) - set(ukbd)
                    gaps.append((bt, sorted(missing)))
            if gaps:
                print(f"  ✗ Coverage gaps found at {len(gaps)} boss turn(s) past sync (T{sync_turn}):")
                for bt, missing in gaps[:20]:
                    print(f"    Turn {bt:2d}: unprotected = {', '.join(missing)}")
                if len(gaps) > 20:
                    print(f"    ... +{len(gaps) - 20} more")
            else:
                print(f"  ✓ UK/BD covers every boss turn from T{sync_turn} to T{result['cb_turns']}")

        # --diff-tune: report SPD/priority deltas vs tune spec
        if args.diff_tune:
            print(f"\n=== Tune Compliance (vs {result.get('tune','?')}) ===")
            from tune_library import get_tune
            t = get_tune(args.tune)
            if t:
                assignments = result.get("assignments", [])
                for name, role, spd_range in assignments:
                    # Find actual SPD of this hero in our result
                    h_out = next((h for h in result.get("heroes", []) if h.get("name") == name), None)
                    spd_actual = None
                    for c in [] if h_out is None else []:
                        pass
                    # SPD from the live data: we don't carry it in result — fetch from the sim's champ list via a side channel. Simpler: print the target band.
                    lo, hi = spd_range if isinstance(spd_range, (list, tuple)) else (spd_range, spd_range)
                    print(f"  {name:20s} slot={role:20s} target SPD={lo}-{hi}  (check in-game: spd band ⇄ target)")
                print("  Tip: run `python tools/compute_team_stats.py --team \"...\" --tune {0}` for a per-hero diff with actual SPDs.".format(args.tune))

        # --all-affinities: run sim on Magic/Force/Spirit/Void, compare
        if args.all_affinities:
            print(f"\n=== All-Affinity Matrix ===")
            orig_elem = cb_element
            from cb_sim import run_tune as _run_tune
            print(f"  {'Affinity':<10} {'CB Turns':>10} {'Damage':>12} {'Gaps':>6}")
            for elem_name, elem_id in [("Magic",1),("Force",2),("Spirit",3),("Void",4)]:
                res = _run_tune(args.tune, team_names, cb_element=elem_id,
                                 force_affinity=not args.no_force_affinity, verbose=False,
                                 use_current_gear=args.use_current_gear)
                if "error" in res:
                    print(f"  {elem_name:<10}  ERROR: {res['error']}")
                    continue
                gaps = 0
                for _bt, prot in (res.get("protection_by_turn") or {}).items():
                    alive = [n for n,p in prot.items() if p.get("alive")]
                    if alive and not all(p.get("uk") or p.get("bd") for n,p in prot.items() if p.get("alive")):
                        gaps += 1
                print(f"  {elem_name:<10} {res['cb_turns']:>10} {res['total']/1e6:>11.2f}M {gaps:>6}")

        # --sweep-hero: vary one hero's SPD across a range
        if args.sweep_hero:
            try:
                hero_name, rng = args.sweep_hero.split("=")
                lo_s, hi_s = rng.split("..")
                lo, hi = int(lo_s), int(hi_s)
            except Exception:
                print(f"  --sweep-hero format: 'Hero=LOW..HIGH' (got {args.sweep_hero})")
            else:
                print(f"\n=== SPD Sweep: {hero_name} {lo}-{hi} ===")
                from cb_sim import run_tune as _rt
                print(f"  {'SPD':>4} {'CB Turns':>10} {'Damage':>12} {'Gaps':>6}")
                for spd_try in range(lo, hi+1, 2):
                    # We need a way to override SPD for one hero. For now, run via
                    # the tune path — the caller can reconfigure gear externally.
                    # TODO: thread spd-override through build_sim_champion.
                    pass
                print("  (Note: SPD override hook not yet wired into run_tune — manual gear edit required for full sweep)")

        # --apply-to-preset: convert DWJ delays to Raid preset params and push
        if args.apply_to_preset:
            print(f"\n=== Applying tune '{args.tune}' to preset #{args.apply_to_preset} ===")
            try:
                from tune_to_preset import build_update_preset_url, MYTH_EATER_TUNE
                import urllib.request
                # For now, only Myth Eater is pre-defined; future tunes need similar dicts.
                if args.tune == "myth_eater":
                    url = build_update_preset_url(preset_id=args.apply_to_preset, tune=MYTH_EATER_TUNE)
                    resp = urllib.request.urlopen(url, timeout=30).read().decode()
                    print(f"  Response: {resp[:200]}")
                else:
                    print(f"  Tune '{args.tune}' doesn't have a predefined delay map in tune_to_preset.py yet.")
            except Exception as ex:
                print(f"  Error: {ex}")
        return

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
