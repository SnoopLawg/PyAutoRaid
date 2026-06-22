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

# Workstream 1 Stage E — data-driven effect dispatcher. Replaces the
# legacy `if buff_name == "shield"` style branches with manifest-keyed
# decisions. See docs/cb_workstream_1_effect_manifest.md.
# Optional import: if the manifest isn't built yet, legacy paths still work.
try:
    from effect_dispatcher import EffectDispatcher as _EffectDispatcher
    _EFFECT_DISPATCHER: "_EffectDispatcher | None" = _EffectDispatcher()
except Exception as _disp_err:  # noqa: BLE001
    _EFFECT_DISPATCHER = None
    print(f"# cb_sim: effect_dispatcher unavailable ({_disp_err}); "
          f"falling back to legacy effect handling.")


def _dispatcher() -> "_EffectDispatcher | None":
    """Lazy accessor — keeps cb_sim importable even without the manifest."""
    return _EFFECT_DISPATCHER


# Workstream 1.E / 2 / 3 — single facade accessor for damage / mastery /
# boss / blessing manifest reads. Cached at module load so hot-path code
# doesn't pay per-call import cost. Survives missing manifests via None.
try:
    from sim_data_facade import try_facade as _try_facade
    _SIM_FACADE = _try_facade()
except Exception:
    _SIM_FACADE = None


def _facade():
    """Cached facade accessor — returns None if manifests are missing."""
    return _SIM_FACADE


# Workstream 4 — lethal-save passive registry. Replaces the previous
# per-name branches (Cardiel ally-save, UDK self-save) with a
# data-driven dispatch. New heroes with revive-at-1-HP passives are
# added here (data, not code).
#
# Schema:
#   save_scope: "ally" — savior can revive any dying ally
#                "self" — savior can only save themselves
#   cooldown_turns: turns the passive is unavailable after use
#   grant_uk_turns: if >0, the saved hero gets that many turns of
#                    Unkillable (else just 1-HP clamp)
#   skill_id: reference to static skill (for future literal extraction)
LETHAL_SAVE_PASSIVES: dict[str, dict] = {
    "Cardiel": {
        "save_scope": "ally",
        "cooldown_turns": 4,
        "grant_uk_turns": 0,
        "skill_id": 57604,
    },
    "Ultimate Deathknight": {
        "save_scope": "self",
        "cooldown_turns": 4,
        "grant_uk_turns": 1,
        "skill_id": 70904,
    },
}


# Heroes the user owns more than one of (and therefore may field
# both copies on the same team — e.g. dual-Maneater "RabBatEater" tunes).
# The team builder uses these to stash the second copy under a synthetic
# `<name>_2` key. Generalizing the pattern: when the user pulls dups of
# any other hero they want on a CB team, add them here (data, not code).
DUPLICATE_INSTANCE_HEROES: tuple[str, ...] = (
    "Maneater",
)

# Per-occurrence opener convention for duplicate-eligible heroes. The
# Nth entry (1-based) is the opening skill sequence for the Nth copy
# of that hero on the team. For Maneater this matches the RabBatEater
# tune: 1st Maneater opens A3 (anchor), 2nd opens A1+A3 (delayed).
DUPLICATE_INSTANCE_OPENERS: dict[str, list[list[str]]] = {
    "Maneater": [["A3"], ["A1", "A3"]],
}


# Self-buff placements that hero_profiles_game.json extraction misses.
# Each entry is `{ hero_name: { skill_label: [(buff_name, duration), ...] } }`.
# The data is verified against `data/static/skills_all.json` (skill Effects[]
# with TargetType=Producer and KindId=ApplyBuff). When the upstream extractor
# in tools/load_game_profiles.py gains TargetType awareness, entries here
# should move to the data file and be removed from this registry.
#
# Each entry must include a comment with the static skill Id + effect
# index that justifies it, so cross-checks against future game updates
# are quick.
KNOWN_SELF_BUFF_OVERRIDES: dict[str, dict[str, list]] = {
    "Ninja": {
        # Skill 62002 (A2 "Storm of Kicks") effect [9]: ApplyBuff
        # target=Producer, status_effect type=481 (perfect_veil) dur=2.
        # Static-verified 2026-06-15 — without this, sim's Ninja never
        # has Veil and the diff against real CB battles flags it
        # every turn 1.
        "A2": [("veil", 2)],
    },
}


def _dup_key_for(name: str, occurrence: int) -> str:
    """Return the lookup key for the Nth occurrence of a duplicate hero
    (1-based). First occurrence is the plain name; subsequent are
    `name_2`, `name_3`, etc."""
    if occurrence <= 1 or name not in DUPLICATE_INSTANCE_HEROES:
        return name
    return f"{name}_{occurrence}"


def _dup_opener_for(name: str, occurrence: int) -> list[str]:
    """Return the opener skill sequence for the Nth occurrence of a
    duplicate-eligible hero. Falls back to [] (no opener override) if
    not registered."""
    seqs = DUPLICATE_INSTANCE_OPENERS.get(name, [])
    idx = occurrence - 1
    if 0 <= idx < len(seqs):
        return list(seqs[idx])
    return []
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
    WEAK_HIT_GLANCE_CHANCE,
    CB_ATTACK_MULT, CB_STUN_HP_FRACTION, NORMAL_HIT_BASE_FACTOR,
    CB_HP_BY_DIFFICULTY, CB_SPEED_BY_DIFFICULTY,
    CB_CR_DEFAULT, CB_CD_DEFAULT,
    CB_ATK,
    FA_CAP_BIG, FA_CAP_MEDIUM, FA_CAP_SMALL, FA_CAP_DOT,
    GATHERING_FURY_START_TURN, GATHERING_FURY_RATE_PER_TURN,
    GATHERING_FURY_CLIFF_TURN, ENRAGE_TURN,
    def_mitigation_factor, HERO_BASE_ARMOR_PIERCE, WEAKEN_MULT,
    buff_mult,
    MAX_APPLIED_DEBUFF_EFFECTS,
)

TM_THRESHOLD = 1430  # Game-truth (per RSL Speedology 201 / MaxMeng77 reddit
# post). Sim was using 1000 prior to 2026-06-21 which produced the same
# RATIOS but broke Speed-Division semantics + the dragging effect.
MAX_CB_TURNS = 50
# Game-truth from data/static/gameplay.json (`MaxAppliedDebuffEffects`).
MAX_DEBUFF_SLOTS = MAX_APPLIED_DEBUFF_EFFECTS

# FA_CAP_*, LEECH_HEAL_RATE — see cb_constants.

# Affinity system: Magic=1, Force=2, Spirit=3, Void=4 (IL2Cpp Element enum
# from dump.cs line 311202). Raid trinity: Spirit > Force > Magic > Spirit
# (each strong against next). Equivalent: Magic > Spirit, Force > Magic, Spirit > Force.
# Weak hit (hero weak vs boss): -20% damage + 35% glance chance + -35% debuff land
# Strong hit (hero strong vs boss): 0% damage but +15% crit + 50% crushing chance
#
# Verified 2026-06-16 (user correction): I briefly flipped these tables to
# {1:2, 2:3, 3:1} thinking "Magic > Force" but real Raid is "Magic > Spirit".
# REVERTED to the original tables, which are correct.
WEAK_AFFINITY = {1: 2, 2: 3, 3: 1}    # Magic weak vs Force, Force weak vs Spirit, Spirit weak vs Magic
STRONG_AFFINITY = {1: 3, 2: 1, 3: 2}  # Magic strong vs Spirit, Force strong vs Magic, Spirit strong vs Force
# WEAK_HIT_DMG_MULT, WEAK_HIT_DEBUFF_FAIL, STRONG_HIT_DMG_MULT — see cb_constants.

HP, ATK, DEF, SPD, RES, ACC, CR, CD = 1, 2, 3, 4, 5, 6, 7, 8

# Boss skill rotation. Game-truth per tick log 2026-06-16:
# T1=stun (222601), T2=aoe1 (222603 = 4×1*ATK), T3=aoe2 (222702/222802/222602/222902 = 3*ATK)
# Pattern repeats every 3 boss turns. All element bosses use the same
# pattern; only the aoe2 skill ID + applied debuff differs per element
# (same total damage formula).
#
# Sim's pattern [aoe1, aoe2, stun] is OFFSET by 1 turn from game-truth.
# Switching to game-truth [stun, aoe1, aoe2] HURTS Spirit-day prediction
# (which currently matches +1%) without fully fixing Force-day (T42/30M
# vs real T21/12.88M). The pattern offset is a documented compensating
# wrong that aligns with some other unmodeled mechanic. Keep as-is until
# the root cause of Force-day deaths is identified.
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
    # HP Burn (effect Id 470) is `StackCount: 1` in data/static/effects.json
    # — game-truth singular. Ninja A2 hitting 3 times still places one burn
    # per target (refresh on re-place). Poison (Id 80, StackCount=10) does
    # stack. Earlier ticklog (2026-04-24) suggested ~1.6 active stacks, but
    # that was end-of-turn ticks PLUS A2 activation ticks combined; with
    # singular burns and proper activation, today's 84 ticks/50 turns matches.
    SINGULAR_BY_TYPE = {"def_down", "def_down_30", "weaken", "weaken_15",
                        "dec_atk", "dec_atk_25", "poison_sensitivity",
                        "poison_sensitivity_50", "heal_reduction",
                        "heal_reduction_50", "stun", "freeze",
                        "hp_burn"}

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
    # ShieldCreation book bonus (SkillBonusType=4 from IL2Cpp enum).
    # Sourced from skills_db.json level_bonuses where type=4. Applied
    # multiplicatively to shield amounts placed by this skill. Demytha
    # A1 fully booked = 0.20 (+20% shield). Without books = 0.0.
    shield_creation_bonus: float = 0.0
    # Health book bonus (SkillBonusType=1 from IL2Cpp enum). Applied
    # multiplicatively to heal_pct on heal-effects (e.g. Demytha A2's
    # `Heals 2.5% MAX_HP per buff change`). Demytha A2 fully booked = 0.20.
    health_book_bonus: float = 0.0
    # Attack book bonus (SkillBonusType=0). Applied multiplicatively to
    # the skill's damage multiplier. Maneater A1 fully booked = 0.20
    # (+20% damage). Was the largest unmodeled damage gap in MEN tune.
    attack_book_bonus: float = 0.0
    # IgnoreResistance book bonus (SkillBonusType=5). Applied to debuff
    # land chance vs target RES. Sourced for future teams; no MEN hero
    # has any.
    ignore_res_book_bonus: float = 0.0
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
    # Tracks survival buffs that have already had their post-placement
    # tick. Per real-game tick log: UK/BD decrement once after the
    # placement turn's first owner-turn-end, then "stick" at the
    # resulting value until consumed by the failsafe. Cleared when
    # buff is re-applied (refresh resets the cycle).
    buffs_ticked_once: set = field(default_factory=set)
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
    # Lasting Gifts (mastery 500351): 30% chance at start of owner's turn
    # to extend a random ally buff by 1 turn. NonIncreaseable buffs (UK,
    # BD, ControlEffects, etc.) are EXCLUDED per game-truth IL2Cpp dump.
    has_lasting_gifts: bool = False
    # Cycle of Magic (mastery 500342): "At the start of hero turn 5% chance
    # to reduce random skill cooldown for 1 turn" (per game-truth static
    # skill 500342 + /mastery-info, verified 2026-06-22).
    # KindId=ReduceCooldown, TargetType=Owner, Condition=isOwnersTurn.
    # Fires on the mastery-holder's OWN skills (not random ally).
    has_cycle_of_magic: bool = False
    # Accumulator for deterministic COM procs: each own turn adds 0.05,
    # whole-integer crossings reduce a random non-A1 skill's CD by 1.
    _com_accum: float = 0.0

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

    # Blessing damage amplifiers (in addition to Brimstone Smite which
    # is handled separately as a debuff-on-target). Resolved from
    # blessing id+grade in _resolve_blessing_damage_amps. Per-hit
    # damage multiplied by (1 + heavencast_pct_per_buff * buff_count)
    # when active. Empirical default 0.06 (epic/grade 1 = +6% per buff,
    # max ~5 buffs = +30% dmg). Plarium doesn't expose the exact
    # coefficient in static export — value sourced from community
    # documentation, calibrated against per-event captures 2026-06-22.
    heavencast_pct_per_buff: float = 0.0   # Demy (blessing 2201 EnhancedWeapon)
    natures_wrath_pct_per_debuff: float = 0.0  # Geo (blessing 5201 NatureBalance)
    # Phantom Touch (MagicOrb blessing 1301, internal skill 600050):
    # AfterDamageDealt → bonus Damage = phantom_touch_mult × ATK to the
    # same target. Game-truth verified 2026-06-22 via /static-export on
    # SkillData.SkillTypeById.Item[600050]: KindId=Damage, Target=
    # RelationTarget, MultiplierFormula=3.5*ATK, Relation.Phases=
    # [AfterDamageDealt], ActivateOnGlancingHit=false. Grade-gated:
    # grades 1-2 use Effect[0] (6000501), grades 3-4 use Effect[1]
    # (6000502), grade 5 uses Effect[2] (6000503), grade 6 uses Effect[3]
    # (6000504) + Effect[4] ChangeEffectRepeatCount. All grades share
    # the 3.5*ATK multiplier in static; grade scaling is purely the
    # repeat-count effect at grade 6 (modeled as +1 hit there).
    phantom_touch_mult: float = 0.0          # 3.5 when blessed grade 1+, else 0
    phantom_touch_repeat: int = 1            # +1 extra fire at grade 6

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

    # Per-turn passive debuff placement — list of {debuff, duration} dicts
    # parsed from the hero's passive skill effects (kind=5000 effects on
    # Group=Passive skills). Sourced from load_game_profiles passive_data.
    # Example: Occult Brawler passive places poison_2_5pct + poison_5pct
    # every turn for 4 turns each.
    passive_debuffs: list = field(default_factory=list)

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
        # Refresh ALWAYS resets consume-on-use tick tracking. The new
        # placement gets its own post-placement first-tick allowance,
        # regardless of whether duration went up. Real-game refresh
        # observation: each Maneater A3 re-placement starts a fresh
        # cycle (tick log boss 'id' field changes per placement).
        self.buffs_ticked_once.discard(name)

    def tick_buffs(self, cb_turn: int = -1, once_per_cb_turn: bool = False,
                    phase: str = "end_owner_turn"):
        """Tick all buffs on this champion.

        Workstream 1 Stage E: routes through `EffectDispatcher` when
        available, so each buff's lifetime decrement respects the
        literal IL2Cpp `LifetimeUpdateType` (OnStartTurn / OnEndTurn /
        Custom). When the manifest is unavailable, falls back to the
        legacy "always decrement at end of owner turn" model.

        `phase`: "start_owner_turn" or "end_owner_turn". Default is
        end-of-turn since most legacy call sites assume that.
        """
        # DWJ: isAddedThisTurn — buffs added since last tick don't decrement
        if once_per_cb_turn and cb_turn >= 0:
            if self.last_ticked_cb_turn == cb_turn:
                # Already ticked this CB turn — fast heroes who get a
                # second hero turn shouldn't burn another point of duration
                # off their own buffs. Real Raid behaves this way for
                # boss-cycle buffs.
                #
                # KNOWN ISSUE (2026-06-16): buffs_new is NOT cleared here.
                # Buffs placed AFTER our first tick this CB turn (e.g.,
                # Demytha A3 placing BD on Maneater after Mane's first
                # action) carry "new" mark into the NEXT cb_turn's tick,
                # which skips again, extending BD lifetime by 1 cb_turn.
                # Sim BD coverage on Maneater = 71% vs real ~31%.
                # Clearing buffs_new here makes Spirit go from +1% to -9%
                # (the BD over-coverage was a compensating wrong matching
                # other untracked mechanics). Pair-fix required: clear
                # buffs_new HERE + restore pattern offset to game-truth
                # [stun, aoe1, aoe2] simultaneously. See task #11.
                return
            self.last_ticked_cb_turn = cb_turn

        disp = _dispatcher()
        expired = []
        for b, d in list(self.buffs.items()):
            if b in self.buffs_new:
                # SkipProcessingWhenJustApplied — equivalent to the legacy
                # "buffs_new" guard. Manifest captures this per-effect.
                if disp and not disp.skip_on_apply_tick_by_name(b):
                    # Effect doesn't have skip-on-apply set; allow tick
                    pass
                else:
                    continue
            if disp:
                # Consume-on-use survival buffs (UK, BD) tick once after
                # placement, then stick — see EffectDispatcher comments.
                # already_ticked=True suppresses further decrement.
                already = b in self.buffs_ticked_once
                new_d = disp.decrement_on_turn_by_name(
                    name=b, current_turn_left=d, phase=phase,
                    already_ticked=already,
                )
                # If the buff actually decremented (vs being skipped),
                # mark its first-tick-done for consume-on-use semantics.
                if (new_d < d
                        and phase == "end_owner_turn"
                        and disp.is_consume_on_use_by_name(b)):
                    self.buffs_ticked_once.add(b)
            else:
                # Legacy fallback: unconditional decrement
                new_d = max(0, d - 1)
            if new_d <= 0:
                expired.append(b)
            else:
                self.buffs[b] = new_d
        for b in expired:
            del self.buffs[b]
            self.buffs_ticked_once.discard(b)
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
    SKILL_DATA, SKILL_EFFECTS, PASSIVE_DATA, SKILL_IDS_BY_HERO = (
        _load_game_profiles()
    )
except (ImportError, FileNotFoundError) as _e:
    # Fall back to empty dicts + defaults; cb_sim will then use
    # DEFAULT_SKILL_DATA (line ~297). Run `python tools/refresh_all.py` to
    # regenerate hero_profiles_game.json if you see this path taken.
    SKILL_DATA, SKILL_EFFECTS, PASSIVE_DATA, SKILL_IDS_BY_HERO = (
        {}, {}, {}, {}
    )
    import sys as _sys
    print(f"[cb_sim] Warning: {_e.__class__.__name__}: {_e} — running without game-extracted profiles", file=_sys.stderr)

# Glance-gate lookup: skill_id (int) → set of effect indices with
# Relation.ActivateOnGlancingHit=false. Built by tools/build_glance_gates.py
# from live-mod /static-export at depth=8. We don't use the per-index info;
# the model is "if the skill has ANY gated effect AND attacker is weak, roll
# one glance per cast and skip the cast's secondary effects on a hit."
# This matches game behavior (glance is a property of the attack roll).
try:
    import json as _json
    from pathlib import Path as _Path
    _gg_path = (_Path(__file__).resolve().parent.parent
                / "data" / "static" / "glance_gates.json")
    _gg_raw = _json.loads(_gg_path.read_text(encoding="utf-8"))
    GLANCE_GATED_SKILL_IDS = {int(k) for k in (_gg_raw.get("gates") or {}).keys()}
except Exception as _e:
    GLANCE_GATED_SKILL_IDS = set()
    import sys as _sys
    print(f"[cb_sim] Warning: glance_gates.json load failed ({_e}); "
          f"generic glance gating disabled", file=_sys.stderr)


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
        self.cb_cr = float(getattr(profile, "cr", CB_CR_DEFAULT) or CB_CR_DEFAULT)
        self.cb_cd = float(getattr(profile, "cd", CB_CD_DEFAULT) or CB_CD_DEFAULT)
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
        # Team-wide passive damage reduction propagation. Some heroes
        # (Geomancer Stoneguard -15%, Sepulcher Sentinel -X%, etc.)
        # provide damage reduction to ALL allies, not just themselves.
        # Compute the team-wide pool here and stamp on each champion.
        team_red = 0.0
        for c in champions:
            v = float(c.stats.get("team_dmg_reduction", 0) or 0)
            team_red = max(team_red, v)
        for c in champions:
            c.team_dmg_reduction = team_red
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
        Multipliers come from data/static/effects.json via cb_constants
        BUFF_REGISTRY (Ids 161/171 = +30%/-30% Speed; Ids 160/170 are
        the smaller +15%/-15% variants tracked separately if needed).
        """
        buff_mod = 0.0
        if c.has_buff("inc_spd"):
            buff_mod += buff_mult("inc_spd_30")
        if c.has_buff("dec_spd"):
            buff_mod -= buff_mult("dec_spd_30")
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
        # Facade-backed: TICK_RATE = StaminaByTick × (TM_THRESHOLD / StaminaToTurn).
        # gameplay.json defines StaminaByTick=0.07, StaminaToTurn=100; if either
        # changes Plarium-side, re-running extract_tm_pipeline.py flows it in.
        _f = _facade()
        TICK_RATE = (
            _f.tm.tick_rate_for_threshold(TM_THRESHOLD)
            if _f is not None else 0.7
        )
        # 2026-06-19 calibration applied TICK_RATE *= 1.12 to fit
        # observed boss/Mane game-ticks/turn under TM_THRESHOLD=1000.
        # That calibration is now removed:
        #   (a) TM_THRESHOLD raised to 1430 (game-truth) — see constant decl
        #   (b) The "+12% TM" observation was relative to wrong-threshold
        #       sim, not a real game mechanic
        #   (c) The "Mane +6% from COM" attribution was based on the wrong
        #       mastery ID (500344 = Evil Eye, not COM) — see
        #       project_cycle_of_magic_id_fix memory
        # With threshold=1430 + no bump, the SD-ceiling effect emerges
        # naturally. Per-hero residual gap (~0-12%) is the dragging
        # effect, which would need explicit modeling to close fully.
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
                # 2026-06-21: tested removing this to fix Geo/Venom same-SD bug
                # (pure-SD gives them 8/7 turns, sim gives 7/6). Removing did
                # NOT change calibration outputs — the bug is elsewhere. See
                # project_sim_sd_dragging_underprediction memory.
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
                # Turn-50 enrage trigger: facade-backed for game-truth.
                # Demon Lord skill 222904 fires at this turn; bypasses
                # BlockDamage + Unkillable (see project_cb_boss_turn_50_bypass).
                _f = _facade()
                _enrage_turn = (
                    _f.boss.turn_50_trigger if _f is not None else ENRAGE_TURN
                )
                if self.cb_turn >= _enrage_turn:
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
        # Pull multipliers from the manifest facade when available so any
        # future Plarium rebalance (gameplay.json ElementDisadvantageCoef)
        # flows in without code edits. WEAK_HIT_DEBUFF_FAIL is sim-only
        # (no manifest equivalent) — keep as constant.
        _f = _facade()
        weak_mult = (
            _f.damage.element_multiplier("Disadvantage")
            if _f is not None else WEAK_HIT_DMG_MULT
        )
        strong_mult = (
            _f.damage.element_multiplier("Advantage")
            if _f is not None else STRONG_HIT_DMG_MULT
        )
        if WEAK_AFFINITY.get(champ.element) == self.cb_element:
            return (weak_mult, 1.0 - WEAK_HIT_DEBUFF_FAIL)
        if STRONG_AFFINITY.get(champ.element) == self.cb_element:
            return (strong_mult, 1.0)
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
        # Deterministic mode uses per-champ fractional accumulator so
        # score_team / cb_calibrate produce identical results across runs.
        # Without this branch, each sim used self.rng (random.Random
        # initialized with system time when rng_seed=None) which caused
        # ~1.3M damage variance per run on the MEN team. Bug discovered
        # round 25 via score_team determinism check.
        if self.deterministic:
            key = ("brimstone_smite", champ.name)
            self._placement_debt[key] = self._placement_debt.get(key, 0.0) + p_any
            if self._placement_debt[key] >= 1.0:
                self._placement_debt[key] -= 1.0
                self.smite_holder = champ.name
                self.smite_turns_left = 2
            return
        if self.rng.random() < p_any:
            self.smite_holder = champ.name
            self.smite_turns_left = 2

    def _try_lethal_save(self, victim: "SimChampion") -> bool:
        """Attempt to save a dying champion via any registered
        lethal-save passive. Returns True if saved, False if death proceeds.

        Resolution order:
          1. Ally-scope passives — any living savior on the team whose
             registry entry is `save_scope == "ally"` may revive the
             victim if their CD attr is <= 0.
          2. Self-scope passives — if the victim's own name maps to a
             `save_scope == "self"` entry, they self-revive.

        CD bookkeeping uses `_save_cd_<savior_name>_<victim_pos>` for
        ally-scope (one CD per (savior, target) pair) and
        `_save_cd_self_<name>` for self-scope.
        """
        # Ally-scope passives first
        for savior_name, defn in LETHAL_SAVE_PASSIVES.items():
            if defn.get("save_scope") != "ally":
                continue
            savior = next(
                (x for x in self.champions
                 if x.name == savior_name and not x.is_dead),
                None,
            )
            if savior is None:
                continue
            cd_key = f"_save_cd_{savior_name}_{victim.position}"
            if not hasattr(savior, cd_key):
                setattr(savior, cd_key, 0)
            if getattr(savior, cd_key, 0) <= 0:
                victim.current_hp = 1
                uk_turns = int(defn.get("grant_uk_turns", 0) or 0)
                if uk_turns > 0:
                    victim.add_buff("unkillable", uk_turns)
                setattr(savior, cd_key, int(defn.get("cooldown_turns", 4)))
                return True

        # Self-scope passive
        defn = LETHAL_SAVE_PASSIVES.get(victim.name)
        if defn and defn.get("save_scope") == "self":
            cd_key = f"_save_cd_self_{victim.name}"
            if not hasattr(victim, cd_key):
                setattr(victim, cd_key, 0)
            if getattr(victim, cd_key, 0) <= 0:
                victim.current_hp = 1
                uk_turns = int(defn.get("grant_uk_turns", 0) or 0)
                if uk_turns > 0:
                    victim.add_buff("unkillable", uk_turns)
                setattr(victim, cd_key, int(defn.get("cooldown_turns", 4)))
                return True
        return False

    def _apply_cycle_of_magic(self, owner: "SimChampion") -> None:
        """Cycle of Magic mastery (500342): at the start of the mastery
        holder's own turn, 5% chance to reduce one of their own skill
        cooldowns by 1 turn.

        Game-truth (verified 2026-06-22 via static skill 500342 +
        /mastery-info):
          - Description: "At the start of hero turn 5% chance to reduce
            random skill cooldown for 1 turn"
          - Effect: KindId=ReduceCooldown, TargetType=Owner,
            Condition=isOwnersTurn, Chance=0.05
          - Affects the mastery holder's own skills (Owner), not allies.

        The prior implementations were both wrong:
          - "5% per hit reduce ALLY CD" — wrong target (Owner not ally).
          - "+5% TM per CD-skill use" — wrong trigger (start-of-turn not
            after-cast) AND wrong effect (CD reduce, not TM gain).
        """
        _f = _facade()
        pct = 0.05
        if _f is not None:
            try:
                proc = _f.mastery.get(500342) or {}
                cp = proc.get("conditional_proc") or {}
                if cp.get("chance") is not None:
                    pct = float(cp["chance"])
            except Exception:
                pass
        # Eligible CD skills: ones with base_cd > 0 currently on cooldown.
        # A1 skills (base_cd==0) cannot be reduced — already always ready.
        eligible = [sk for sk in owner.skills
                    if sk.base_cd > 0 and sk.current_cd > 0]
        if not eligible:
            return
        if self.deterministic:
            owner._com_accum += pct
            while owner._com_accum >= 1.0:
                owner._com_accum -= 1.0
                # Deterministic pick: rotate through eligible by turn count
                idx = owner.turns_taken % len(eligible)
                eligible[idx].current_cd = max(0, eligible[idx].current_cd - 1)
        else:
            if self.rng.random() < pct:
                pick = self.rng.choice(eligible)
                pick.current_cd = max(0, pick.current_cd - 1)

    def _apply_special_buff(self, caster: "SimChampion", chosen,
                              buff_name: str, duration: int) -> bool:
        """Handle buffs with non-team-wide placement / non-default amounts.
        Returns True if handled here (caller skips the team-wide path),
        False if the caller should apply normally to all allies.

        Currently registered:
          shield — lowest-HP ally (excl. caster), absorption = 10% caster
                    max_hp, refresh (not stack), one shield per hit.
        Future hero kits with bespoke placement (e.g. Aura Shield, Bromiel
        ramping shield) plug in here as additional branches.
        """
        if buff_name == "shield":
            allies_alive = [c for c in self.champions
                            if c is not caster and not c.is_dead]
            if not allies_alive:
                return True
            # Apply ShieldCreation book bonus (IL2Cpp SkillBonusType=4).
            # Demytha A1 fully booked = +20% shield amount. Without books,
            # `shield_creation_bonus` is 0.0 and the shield matches the
            # raw 10% caster max_hp baseline.
            sc_bonus = float(getattr(chosen, "shield_creation_bonus", 0.0))
            shield_amount = caster.max_hp * 0.10 * (1.0 + sc_bonus)
            hits = max(1, getattr(chosen, "hit_count", 1))
            for _ in range(hits):
                target = min(
                    allies_alive,
                    key=lambda c: c.current_hp / max(1, c.max_hp),
                )
                target.add_buff("shield", duration)
                target.shield_hp = max(
                    target.shield_hp,
                    min(target.max_hp, shield_amount),
                )
            return True
        return False

    def _cb_turn(self, tick: int):
        self.cb_tm -= TM_THRESHOLD
        # Determine attack BEFORE Smite check below — Brimstone Smite
        # only fires on AoE active skills (aoe1, aoe2), NOT single-
        # target ones (stun).
        #
        # Empirical: 5 Magic BT15 captures showed 18 Smite damage
        # events all aligned with aoe1/aoe2 boss casts, ZERO aligned
        # with stun. Probability of stun-skip being chance: (2/3)^18
        # = 0.07%.
        #
        # Structural cause (verified 2026-06-22 via static export of
        # skills 222601/222602/222603):
        #   stun (222601): Damage TargetType=Target (single hero)
        #   aoe1 (222603): Damage TargetType=AllEnemies
        #   aoe2 (222602): Damage TargetType=AllEnemies
        # Brimstone's "uses an Active Skill" trigger has an implicit
        # multi-target requirement — single-target damage skills are
        # skipped despite being Group=Active.
        _attack_for_smite = self.cb_pattern[(self.cb_turn) % 3]

        # No static dragging constant. The sim's actor-pick logic in the
        # main schedule loop already implements the game-truth PvE
        # tie-break ("team wins TM-tie vs boss" via the strict-greater
        # `cb_tm > top_champ.tm` check). Any team-wide dragging effect
        # should emerge naturally from that and per-hero TM mechanics
        # (Cycle of Magic CD-reduce, A1 self-TM, set/mastery procs).
        #
        # History: a `cb_tm -= TM_THRESHOLD * X` static drag was added
        # 2026-06-22 at X=0.11 ("Speedology 201"), then re-tuned to 0.03
        # after the SimChampion.element default-to-Void bug
        # (project_sim_element_bug_fix) was fixed. Both are magic
        # constants that mask team-specific TM mismodeling — they don't
        # generalize to comps the team explorer surfaces.
        #
        # Removing the drag exposes ~3-5% Force AVG under-prediction
        # rooted in a separately-tracked unmodeled mechanism: Mane
        # shows +18% effective TM vs displayed SPD in real game (per
        # project_real_game_21_tick_cycle). That's the real bug to
        # solve — investigate the missing TM source rather than
        # continuing to patch via boss slowdown.

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
            # Smite only fires on aoe1/aoe2 — NOT stun (empirical from
            # Magic BT15 captures 2026-06-22).
            if holder is not None and not holder.is_dead and _attack_for_smite != "stun":
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
            # Gathering Fury per static boss skill 222904 formulas:
            #   Formula 1 (turn 10-19): DMG_MUL * 0.75 * (turn - 9) added
            #   Formula 2 (turn 20+):   DMG_MUL * 7.5 + DMG_MUL * (turn - 19)
            # Game-truth verified via data/static/boss_skill_manifest.json.
            # At turn 19 both formulas give 7.5x added → 8.5x total.
            # Pre-round 24, sim used formula 1 unbounded which over-predicted
            # by ~9% at turn 20+ (sim 9.25x vs game-truth 8.5x).
            fury_mult = 1.0
            if self.cb_turn >= GATHERING_FURY_CLIFF_TURN:
                # Formula 2: 7.5 + (turn - 19) added to base 1.0
                fury_mult = 1.0 + 7.5 + (self.cb_turn - 19)
            elif self.cb_turn >= GATHERING_FURY_START_TURN:
                # Formula 1: 0.75 * (turn - 9) added to base 1.0
                fury_mult = 1.0 + GATHERING_FURY_RATE_PER_TURN * (self.cb_turn - GATHERING_FURY_START_TURN + 1)

            # Dec ATK on CB: effect Id 131 (StatusReduceAttack 50%) — formula
            # `0.5*TRG_B_ATK`. Damage scales linearly with ATK, so the damage
            # factor is `1.0 - 0.5 = 0.5`. Pulled from static via buff_mult().
            dec_atk_mult = (
                (1.0 - buff_mult("dec_atk_50", 0.5))
                if self.debuff_bar.has("dec_atk") else 1.0
            )

            # T50 enrage bypass: boss skill 222904 effect [2] adds
            # BlockDamage + Unkillable to IgnoredEffects at OWNERS_TURN>=50.
            # Verified live via /static-export of skill 222904
            # AddIgnoredEffectsParams.IgnoredEffects = ["BlockDamage", "Unkillable"].
            # See project_cb_boss_turn_50_bypass.md.
            _t50_bypass = self.cb_turn >= 50

            # Calculate and apply damage to each hero (no AP redirect — see below)
            for c in self.champions:
                if c.is_dead:
                    continue

                # At T50+, UK/BD are bypassed (ignored) per skill 222904 effect [2]
                has_uk = c.has_buff("unkillable") and not _t50_bypass
                has_bd = c.has_buff("block_damage") and not _t50_bypass

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
                # is a HP floor of 1. BD stays time-decay (with skip-on-apply
                # override) — consume-on-use was tried in round 23 but BD's
                # effective coverage drops sharply (dur=1 = 1 boss action).
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

                # Boss → hero damage uses the game-truth DEF mitigation
                # function from cb_constants (extracted from
                # DamageCalculator.DamageReductionByDefence in
                # GameAssembly.dll, 2026-05-02).
                target_def = c.stats.get(DEF, 1000)
                if c.has_buff("inc_def"):
                    # Inc DEF buff: +60% relative to base DEF.
                    # effects.json Id 141, MultiplierFormula = 0.6*TRG_B_DEF.
                    target_def *= (1.0 + buff_mult("inc_def_60"))
                def_reduction = def_mitigation_factor(target_def)

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
                        # Hero is strong vs boss → boss is weak vs hero.
                        # Multiplier sourced from sim_data_facade
                        # (gameplay.json ElementDisadvantageCoef = -0.2);
                        # falls back to WEAK_HIT_DMG_MULT if facade missing.
                        _f = _facade()
                        incoming_mult = (
                            _f.damage.element_multiplier("Disadvantage")
                            if _f is not None else WEAK_HIT_DMG_MULT
                        )

                # Per-attack multi-hit multiplier from real game data (see CB_ATTACK_MULT)
                attack_mult = CB_ATTACK_MULT.get(attack, CB_AOE_MULT)
                # Boss crit modeling: UNM has CR=15%, CD=50% per static
                # data. Crits do 1.0 + CD × CR_rate average damage. In
                # deterministic mode, apply expected value (1 + 0.5 × 0.15
                # = 1.075). In Monte Carlo, the sim's RNG rolls per hit.
                # Boss crit chance includes affinity bonus (+15% if boss
                # is strong vs hero).
                cb_cr = self.cb_cr if hasattr(self, "cb_cr") else CB_CR_DEFAULT
                cb_cd_mult = self.cb_cd if hasattr(self, "cb_cd") else CB_CD_DEFAULT
                # Affinity advantage gives boss +X% crit chance vs weak hero.
                # X = gameplay.json CriticalHitChanceAdvantage (0.15), now
                # routed through sim_data_facade so any future Plarium
                # rebalance flows from the manifest automatically.
                _f = _facade()
                _affinity_crit_bonus = (
                    _f.damage.hit_type_chance("crit_adv")
                    if _f is not None else 0.15
                )
                # Boss has element advantage over hero when STRONG_AFFINITY[cb_element]==hero.element
                boss_has_advantage = False
                if c.element and self.cb_element and c.element != 4 and self.cb_element != 4:
                    if STRONG_AFFINITY.get(self.cb_element) == c.element:
                        cb_cr = min(1.0, cb_cr + _affinity_crit_bonus)
                        boss_has_advantage = True
                # Compute crit/crush damage modifier.
                # gameplay.json: CrushingHitChance=0.5, CrushingHitCoef=0.3 (= +30% damage)
                # When boss has element advantage over target:
                #   p_crit fires for full crit damage (1 + CD)
                #   non-crit hits: 50% crush (×1.30), 50% normal (×1.0)
                # Verified 2026-06-16 via real CB battle (capture 144150 T17):
                # Ninja (Magic, weak vs Force) took 43.9K vs Demytha (Void, neutral)
                # 33.2K = +32% — matches crushing-hit modeling. Sim previously
                # missed this for boss-to-hero damage; only modeled crit-chance
                # bonus, leaving heroes alive in sim that died in real on
                # Force/Magic/Spirit days (depending on team affinity mix).
                if self.deterministic:
                    if boss_has_advantage:
                        # Crit fires p_crit, then non-crit splits crush/normal
                        crit_factor = (
                            cb_cr * (1.0 + cb_cd_mult)
                            + (1 - cb_cr) * (0.5 * 1.30 + 0.5 * 1.0)
                        )
                    else:
                        crit_factor = 1.0 + cb_cr * cb_cd_mult
                else:
                    if self.rng.random() < cb_cr:
                        crit_factor = 1.0 + cb_cd_mult
                    elif boss_has_advantage and self.rng.random() < 0.5:
                        crit_factor = 1.30  # crushing
                    else:
                        crit_factor = 1.0
                # Apply Normal-hit base factor (0.85) — derived from
                # captured calc_raw/p_atk = 0.85 across all boss events.
                # Already includes any "scrub" factor the game applies
                # to all incoming damage; do NOT also apply a separate
                # 1.0 multiplier.
                aoe_dmg = (CB_ATK * attack_mult * NORMAL_HIT_BASE_FACTOR
                           * def_reduction * dec_atk_mult
                           * fury_mult * incoming_mult * crit_factor)

                # Damage reduction buff (e.g., Ma'Shalled A3: 50% reduction)
                if c.has_buff("dmg_reduction"):
                    aoe_dmg *= 0.50

                # Passive damage reduction. Per-hero field (Cardiel -20%,
                # Geomancer -30% self) takes precedence over team-wide
                # (e.g. Geomancer Stoneguard -15% on all allies). Don't
                # STACK — the bigger effect REPLACES the smaller, since
                # the game's "Decreases damage" passives don't compose
                # multiplicatively across the same source type.
                team_dmg_red = getattr(c, "team_dmg_reduction", 0.0)
                effective_red = max(c.has_passive_dmg_reduction, team_dmg_red)
                if effective_red > 0:
                    aoe_dmg *= (1 - effective_red)

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

                # Lethal-save passives — data-driven dispatch via
                # LETHAL_SAVE_PASSIVES registry. Approximated here as
                # cooldown gates because the literal static-skill logic
                # involves faction-gated triggers + canUniqueApplyForTurn
                # rate-limits we don't fully model. See registry comments
                # at top of file for the original skill IDs.
                if c.current_hp <= 0:
                    saved = self._try_lethal_save(c)
                    if not saved:
                        c.is_dead = True
                        c.death_turn = self.cb_turn
                        self.errors.append(
                            f"DEATH: {c.name}(p{c.position}) CB turn {self.cb_turn} ({attack})")

            # (Ally Protect redirect removed per game mechanics clarification —
            # no damage transfers to a protector; see above.)

            # Tick lethal-save passive cooldowns (registry-driven).
            # All save-passive CD attrs use the `_save_cd_` prefix per
            # _try_lethal_save's bookkeeping convention.
            for c in self.champions:
                if not c.is_dead:
                    for attr in dir(c):
                        if attr.startswith("_save_cd_"):
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
                        # Only count allies who actually TAKE the AOE damage
                        # (BD absorbs 100% = no damage to deflect from). Per
                        # game logic: "deflects damage" — if damage was
                        # absorbed by BD, there's no damage to deflect.
                        # Verified 2026-06-22: real Geo deflect ≈ 182K/cap,
                        # sim was 619K/cap (3.4x over) because sim counted
                        # all 5 living allies regardless of BD protection.
                        # MEN team has BD coverage ~50%+ on Magic so this
                        # halves real deflect.
                        unprotected_allies = sum(
                            1 for a in self.champions
                            if not a.is_dead and not a.has_buff("block_damage")
                        )
                        # Base deflect: 15% of per-ally damage, summed
                        # across UNPROTECTED allies only.
                        base_deflect = per_ally_aoe * unprotected_allies * buff_mult("strengthen_15", 0.15)
                        # Reflect bonus: skill 48805's `'0.03*TRG_HP'`
                        # PassiveReflectDamage path, capped at 75K (CB
                        # DoT cap from skill 200008). 2026-06-22:
                        # corrected — bonus is ONE event per boss AOE
                        # (boss is the only enemy/target), not per ally.
                        # Was: bonus_total = living_allies * 22.5K → 5x
                        # over-attribution. See dragging-fix downstream
                        # damage investigation.
                        bonus_total = 0.30 * 75_000
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
    # Buffs that the game's NonIncreaseableEffects list excludes from
    # Lasting Gifts / Demytha A2 extends / similar effects. Sourced
    # from `data/static/non_increaseable_effects.json` (IL2Cpp dump).
    # ControlEffects (the entire group) also excluded — encoded as a
    # name set below since sim doesn't currently expose group membership
    # at the buff_name level.
    _NON_EXTENDABLE_BUFFS_FOR_MASTERY = frozenset({
        "unkillable",       # UK clamp-to-1
        "block_damage",     # BD absorbs 100%
        "revive_on_death",  # one-shot revive
        "stone_skin",
        "taunt",
        "poison_cloud",
        "thunder",
        "entangle",
        "syphon",
        "on_guard",
    })

    def _apply_lasting_gifts(self, champ: "SimChampion") -> None:
        """Lasting Gifts mastery (500351): 30% chance at start of owner's
        turn to extend a random ally buff by 1 turn. NonIncreaseable
        buffs are excluded. Deterministic mode uses an accumulator.
        Chance sourced from facade.mastery.
        """
        if not getattr(champ, "has_lasting_gifts", False):
            return
        _f = _facade()
        chance = 0.30
        if _f is not None:
            try:
                rec = _f.mastery.get(500351) or {}
                cp = rec.get("conditional_proc") or {}
                if cp.get("chance") is not None:
                    chance = float(cp["chance"])
            except Exception:
                pass
        if self.deterministic:
            key = ("lasting_gifts", champ.name)
            self._placement_debt[key] = self._placement_debt.get(key, 0.0) + chance
            if self._placement_debt[key] < 1.0:
                return
            self._placement_debt[key] -= 1.0
        else:
            if self.rng.random() >= chance:
                return

        # Pick a random living ally and a random eligible buff.
        living = [c for c in self.champions if not c.is_dead]
        if not living:
            return
        target = (
            living[champ.turns_taken % len(living)]
            if self.deterministic else self.rng.choice(living)
        )
        eligible = [
            b for b in target.buffs
            if b not in self._NON_EXTENDABLE_BUFFS_FOR_MASTERY
        ]
        if not eligible:
            return
        pick = (
            eligible[champ.turns_taken % len(eligible)]
            if self.deterministic else self.rng.choice(eligible)
        )
        target.buffs[pick] += 1
        target.buffs_new.add(pick)

    def _champion_turn(self, champ: SimChampion, tick: int):
        champ.tm -= TM_THRESHOLD
        champ.turns_taken += 1

        # Lasting Gifts mastery proc at start of owner turn.
        self._apply_lasting_gifts(champ)

        # Cycle of Magic (mastery 500342): at the start of the owner's
        # turn, 5% chance to reduce one of their own skill CDs by 1.
        # Game-truth verified 2026-06-22.
        if champ.has_cycle_of_magic:
            self._apply_cycle_of_magic(champ)

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

        # Apply team buffs. Buffs with custom targeting / amount rules
        # (e.g. shield with lowest-HP target + 10% caster max_hp) route
        # through _apply_special_buff; the rest go team-wide.
        for buff_name, duration in chosen.team_buffs:
            if self._apply_special_buff(champ, chosen, buff_name, duration):
                continue
            for c in self.champions:
                c.add_buff(buff_name, duration)

        # Apply TM fill to all allies (e.g., Seeker A2: 30% TM fill)
        if chosen.team_tm_fill > 0:
            tm_amount = chosen.team_tm_fill * TM_THRESHOLD
            for c in self.champions:
                if not c.is_dead and c is not champ:
                    c.tm += tm_amount

        # Apply self TM fill (e.g., Ninja A1: +15% TM).
        # GLANCE GATING (2026-06-18): static skill data sets
        # Relation.ActivateOnGlancingHit=false on these effects, so weak-affinity
        # hits skip the fill ~27% of the time (the glance rate).
        #   - Monte Carlo / RNG mode: binary per-cast — full fill OR zero.
        #     Captures the cascading cycle-desync effect that breaks MEN
        #     on real Force days (glance streaks → Mane A3 / Demytha A2
        #     cycle drifts → BD gap opens → die T20-24).
        #   - Deterministic mode: scale by non-glance probability (averages
        #     the effect, used for steady-state damage prediction).
        # Strong/Neutral/Void hits never glance → full fill applies.
        if chosen.self_tm_fill > 0:
            fill = chosen.self_tm_fill
            is_weak = (champ.element in (1, 2, 3) and self.cb_element in (1, 2, 3)
                       and WEAK_AFFINITY.get(champ.element) == self.cb_element)
            if is_weak:
                if self.deterministic:
                    fill *= (1.0 - WEAK_HIT_GLANCE_CHANCE)
                else:
                    if self.rng.random() < WEAK_HIT_GLANCE_CHANCE:
                        fill = 0.0
            champ.tm += fill * TM_THRESHOLD

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

            # Phantom Touch (MagicOrb blessing): AfterDamageDealt fires
            # an additional Damage hit at 3.5*ATK. Once per damage effect
            # (so once per source hit; multi-hit skills proc it per hit).
            # ActivateOnGlancingHit=false → weak-affinity casters skip on
            # glance (35% rate, dampened by 0.65 in deterministic mode).
            # Attributed to .passive for clarity in per-source breakdowns.
            if champ.phantom_touch_mult > 0:
                pt_skill = SimSkill(
                    name=f"{chosen.name}_phantom",
                    base_cd=0,
                    multiplier=champ.phantom_touch_mult,
                    scaling_stat="ATK",
                    hit_count=1,  # PT fires per source-damage; loop external
                )
                pt_per_hit = self._calc_skill_damage(champ, pt_skill)
                is_weak = (champ.element in (1, 2, 3) and self.cb_element in (1, 2, 3)
                           and WEAK_AFFINITY.get(champ.element) == self.cb_element)
                if is_weak:
                    if self.deterministic:
                        pt_per_hit *= (1.0 - WEAK_HIT_GLANCE_CHANCE)
                    else:
                        # Per-hit glance roll handled inside the loop below.
                        pass
                total_pt = 0.0
                fires_per_skill_hit = champ.phantom_touch_repeat
                for _ in range(chosen.hit_count * fires_per_skill_hit):
                    if not self.deterministic and is_weak:
                        if self.rng.random() < WEAK_HIT_GLANCE_CHANCE:
                            continue  # glance: PT skips
                    total_pt += pt_per_hit
                champ.damage.passive += total_pt

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

        # Continuous Heal tick — multipliers from data/static/effects.json:
        #   Id 91 (ContinuousHeal15 family): 0.15*TRG_HP per tick
        #   Id 90 (ContinuousHeal075p):      0.075*TRG_HP per tick
        if self.model_survival:
            if champ.has_buff("cont_heal_15"):
                heal = champ.max_hp * buff_mult("cont_heal_15")
                champ.current_hp = min(champ.max_hp, champ.current_hp + heal)
            elif champ.has_buff("cont_heal"):
                heal = champ.max_hp * buff_mult("cont_heal_75")
                champ.current_hp = min(champ.max_hp, champ.current_hp + heal)

        # Immortal set: 3% HP per turn
        if self.model_survival and champ.stats.get("has_immortal"):
            champ.current_hp = min(champ.max_hp, champ.current_hp + champ.max_hp * 0.03)

        # Apply skill effects
        self._apply_effects(champ, chosen)

        # Per-turn passive debuff placement. Any hero whose passive
        # skill carries a kind=5000 effect (e.g. Occult Brawler:
        # passive places poison_2_5pct + poison_5pct, both 4 turns)
        # gets each placement triggered once per turn here. List
        # populated by load_game_profiles from the static skill data.
        for db_def in champ.passive_debuffs:
            db_type = db_def.get("debuff")
            db_dur  = int(db_def.get("duration", 2))
            if db_type:
                self._try_place_debuff(champ, db_type, db_dur, 1.0)

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

        # Skill multiplier scaled by Attack book bonus (IL2Cpp
        # SkillBonusType=0). Maneater A1 fully booked = +20% damage,
        # Ninja A2 (5 books mix incl. type=0) = +15%. Default 0.0.
        effective_mult = skill.multiplier * (1.0 + skill.attack_book_bonus)
        raw = scaling * effective_mult

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

        # MC mode: per-hit roll for crit/glance/crush. This is the
        # dominant source of cycle-level variance (a crit streak boosts
        # damage by 3x on those hits; a glance streak on weak-affinity
        # caster gimps an entire cycle). Without per-hit rolls, MC mode
        # has ~12% damage spread vs real-game ~58% — sim was too
        # narrow to validate against real fixture variance.
        # Deterministic mode keeps expected-value formula for stable
        # point comparison.
        if self.deterministic:
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
        else:
            # Per-hit Monte Carlo roll. Aggregate over hit_count.
            crit_mult = 0.0
            hits = max(1, skill.hit_count)
            for _ in range(hits):
                if self.rng.random() < p_crit:
                    crit_mult += crit_dmg_mult
                elif is_advantage and self.rng.random() < 0.50:
                    crit_mult += 1.30  # crush
                elif is_disadvantage and self.rng.random() < 0.35:
                    crit_mult += 0.70  # glance
                else:
                    crit_mult += 1.0
            # crit_mult is now a SUM across hits; divide by hit_count
            # so downstream multiplication by hits stays equivalent.
            # (Sim doesn't multiply by hit_count in _calc_skill_damage;
            # crit_mult already represents the per-skill total.)
            crit_mult /= hits

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

        # Helmsmasher (mastery 500162): 50% chance × ignore 25% DEF.
        # Deterministic average is `1 - (chance × ignore) = 1 - 0.125 = 0.875`.
        # Pulled from mastery_manifest.json so a future game patch (e.g.
        # chance or ignore-fraction change) flows in via re-extract.
        if champ.has_helmsmasher:
            _f = _facade()
            if _f is not None:
                hm = _f.mastery.helmsmasher_proc() or {}
                _avg_ignore = float(
                    hm.get("average_def_ignore",
                           (hm.get("chance", 0.5) * 0.25))
                )
            else:
                _avg_ignore = 0.125
            effective_def *= (1.0 - _avg_ignore)

        # Hero -> boss DEF mitigation: same game-truth function.
        # The caller (CalculateDamage) passes a base defence_modifier of
        # -0.02 for hero attackers (HERO_BASE_ARMOR_PIERCE, captured
        # 2026-05-02). Skill-level ignore_def is already applied above
        # by reducing effective_def, so we pass the base only here.
        def_mult = max(0.05, def_mitigation_factor(
            effective_def, defence_modifier=HERO_BASE_ARMOR_PIERCE))

        # Weaken multiplier from data/static/effects.json Id 350
        # (IncreaseDamageTaken25): MultiplierFormula = 1.25. Applied
        # via ChangeCalculatedDamageProcessor when the boss is Weakened.
        wk = WEAKEN_MULT if self.debuff_bar.has("weaken") else 1.0
        # Strengthen (+25% ATK buff, effect Id 120, formula `0.25*TRG_B_ATK`)
        # scales damage by 1 + 0.25 = 1.25. Pulled from static via buff_mult.
        str_mult = (
            (1.0 + buff_mult("inc_atk_25", 0.25))
            if champ.has_buff("strengthen") else 1.0
        )
        bid = 1.06 if champ.has_bring_it_down else 1.0

        # Affinity modifier
        aff_dmg, _ = self._get_affinity_mult(champ)

        # Blessing damage amplifiers — game-truth rates (verified 2026-06-22
        # via /static-export on skills 600090 + 600270):
        #
        # Heavencast (600090, EnhancedWeapon blessing 2201):
        #   - Grade 1-2: 0.005 per buff on self
        #   - Grade 3-4: 0.01 per buff
        #   - Grade 5-6: 0.015 per buff
        #   Formula: bless_mult *= (1 + 0.005 * BUFF_COUNT)
        #   Glance-gated (Relation.ActivateOnGlancingHit=false)
        #
        # Nature's Wrath (600270, NatureBalance blessing 5201):
        #   - Counter NaturesBalance_Counter increments per debuff PLACED
        #     by owner (Relation.EffectKindGroups: EffectThatApplyStatusDebuffs,
        #     Phases: AfterEffectAppliedOnTarget). Cap = 3 (ValueRange.MaxFormula='3').
        #   - Grade 1-2: 0.02 per counter stack
        #   - Grade 3-4: 0.02 per stack
        #   - Grade 5-6: 0.03 per stack
        #   Max bonus = 0.02 * 3 = +6% (grade 1-2) or +9% (grade 5-6)
        #   Glance-gated on damage application AND counter increment.
        #
        # Pre-fix (until 2026-06-22) the sim used 0.06 per stack uncapped for
        # both, which over-stated Heavencast by ~12x and Nature's Wrath by
        # ~5x (uncapped on a 5+ debuff boss).
        bless_mult = 1.0
        if champ.heavencast_pct_per_buff > 0:
            buff_count = len(getattr(champ, 'buffs', {}))
            bless_mult *= (1.0 + champ.heavencast_pct_per_buff * buff_count)
        if champ.natures_wrath_pct_per_debuff > 0:
            # Approximate the counter via "debuffs placed by this hero
            # currently on boss" capped at 3 (game-truth ValueRange.Max).
            # For most boss fights the counter saturates within 2-3
            # debuff placements, so the cap dominates and exact count
            # tracking would only matter for the first ~5-10 turns.
            debuff_count = sum(
                1 for s in self.debuff_bar.slots if s.source == champ.name
            )
            counter = min(3, debuff_count)
            bless_mult *= (1.0 + champ.natures_wrath_pct_per_debuff * counter)

        return raw * crit_mult * def_mult * wk * str_mult * bid * aff_dmg * bless_mult

    # ----- WM/GS -----
    def _roll_wm_gs(self, champ: SimChampion, hit_count: int) -> float:
        # WM/GS procs deal flat damage (% of boss max HP), capped at 75K on UNM.
        # They are NOT multiplied by DEF Down or Weaken — the cap is absolute.
        # Previous code incorrectly applied DEF Down + Weaken multipliers here,
        # causing ~2x overestimation of WM/GS damage.
        #
        # Proc rates + damage caps come from the mastery manifest (facade)
        # so a future game patch flows in via re-running
        # extract_mastery_manifest.py rather than editing constants.
        #
        # Glance gating (game-truth verified 2026-06-22 via static skill
        # 500161): WM's Relation.ActivateOnGlancingHit=false, so weak-
        # affinity casters' procs are gated by the 35% glance rate.
        # Same condition on GS (500163). Heroes attacking neutral/strong/
        # void targets glance 0% — full proc rate applies.
        _f = _facade()
        if _f is not None:
            wm_proc = _f.mastery.warmaster_proc() or {}
            gs_proc = _f.mastery.giant_slayer_proc() or {}
            gs_rate = gs_proc.get("chance", GS_PROC_RATE)
            wm_rate = wm_proc.get("chance", WM_PROC_RATE)
            gs_dmg = gs_proc.get("damage_cap", GS_DMG)
            wm_dmg = wm_proc.get("damage_cap", WM_DMG)
        else:
            gs_rate, wm_rate, gs_dmg, wm_dmg = (
                GS_PROC_RATE, WM_PROC_RATE, GS_DMG, WM_DMG)

        is_weak = (champ.element in (1, 2, 3) and self.cb_element in (1, 2, 3)
                   and WEAK_AFFINITY.get(champ.element) == self.cb_element)

        if self.deterministic:
            glance_attenuation = (1.0 - WEAK_HIT_GLANCE_CHANCE) if is_weak else 1.0
            if champ.has_gs:
                return hit_count * gs_rate * gs_dmg * glance_attenuation
            elif champ.has_wm:
                return wm_rate * wm_dmg * glance_attenuation
            return 0
        else:
            dmg = 0
            if champ.has_gs:
                for _ in range(hit_count):
                    if is_weak and self.rng.random() < WEAK_HIT_GLANCE_CHANCE:
                        continue  # glance: no proc
                    if self.rng.random() < gs_rate:
                        dmg += gs_dmg
            elif champ.has_wm:
                if is_weak and self.rng.random() < WEAK_HIT_GLANCE_CHANCE:
                    return 0
                if self.rng.random() < wm_rate:
                    dmg += wm_dmg
            return dmg

    # ----- Effect Application -----
    def _apply_effects(self, champ: SimChampion, skill: SimSkill):
        effects = SKILL_EFFECTS.get(champ.name, {}).get(skill.name, [])
        acc_rate = calc_acc_land_rate(champ.stats.get(ACC, 0))
        # IgnoreResistance book bonus (IL2Cpp SkillBonusType=5) — boosts
        # the caster's effective ACC vs target RES on this skill. Default 0.0.
        if skill.ignore_res_book_bonus > 0:
            acc_rate = min(1.0, acc_rate + skill.ignore_res_book_bonus)
        sniper_bonus = 0.05 if champ.has_sniper else 0
        _, aff_debuff_mult = self._get_affinity_mult(champ)  # weak hits reduce debuff landing

        # Apply self-buff overrides for skills where the upstream
        # extractor missed an ApplyBuff Producer-target effect.
        # Registry-driven (KNOWN_SELF_BUFF_OVERRIDES at module top); data,
        # not branching code. Self-buffs only land on the caster.
        # (Self-buffs don't glance — no attack roll on the placement.)
        for sb_name, sb_dur in (
            KNOWN_SELF_BUFF_OVERRIDES.get(champ.name, {}).get(skill.name, [])
        ):
            champ.add_buff(sb_name, sb_dur)

        # GLANCE GATING (generic, 2026-06-18): weak-affinity attacks have a
        # ~35% chance to glance (gameplay.json GlancingHitChance). When they
        # glance, every secondary effect with Relation.ActivateOnGlancingHit=
        # false on the cast skill is SUPPRESSED. This is the missing piece
        # that explains MEN's Force-UNM failure: Ninja+Venom (Magic) glance
        # ~35% on Force boss, losing DEC DEF / poisons / TM boost / HP burns
        # → boss tankier, team takes more damage, BD/UK cycle drifts.
        # Damage rolls (the kind=6000 damage effect) still apply (at the
        # GlancingHitCoef penalty modeled elsewhere); we only gate the
        # secondaries lumped into SKILL_EFFECTS[].
        is_weak = (
            champ.element in (1, 2, 3) and self.cb_element in (1, 2, 3)
            and WEAK_AFFINITY.get(champ.element) == self.cb_element
        )
        skill_id = SKILL_IDS_BY_HERO.get(champ.name, {}).get(skill.name, 0)
        skill_has_gate = skill_id in GLANCE_GATED_SKILL_IDS
        glance_blocks_secondaries = False
        glance_avg_dampen = 1.0   # for deterministic mode
        if is_weak and skill_has_gate:
            if self.deterministic:
                # In deterministic mode, scale debuff land + per-cast effect
                # firing by (1 - glance_chance) — averages the binary roll.
                glance_avg_dampen = 1.0 - WEAK_HIT_GLANCE_CHANCE
            else:
                # Monte Carlo: binary roll per cast. If it glances, gate
                # blocks ALL of this cast's secondary effects.
                if self.rng.random() < WEAK_HIT_GLANCE_CHANCE:
                    glance_blocks_secondaries = True

        if glance_blocks_secondaries:
            # MC glance: skip the entire effects list. Damage already
            # applied at the calc-damage call site.
            return

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
                            base_chance * acc_rate * aff_debuff_mult
                            * glance_avg_dampen)

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
                        base_chance * acc_rate * glance_avg_dampen)

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
                # Track GLOBAL change totals separately. Game-truth Demytha
                # A2 heal formula (skill 65102 E[2], verified 2026-06-18):
                # `(0.025*TRG_HP) + ((0.025*TRG_HP) *
                #  (totalIncreasedTurnsCountBySkill +
                #   totalDecreasedTurnsCountBySkill))`
                # → both `total*` are global across the cast.
                buff_extend_total = 0
                debuff_shrink_total = 0
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
                        buff_extend_total += turns  # +1 turn per buff per cast
                # Demytha A2 also shrinks debuffs on the boss by N turns.
                debuff_shrink = eff.params.get("shrink_debuffs", 0)
                if debuff_shrink:
                    survivors = []
                    for slot in self.debuff_bar.slots:
                        slot.remaining -= debuff_shrink
                        debuff_shrink_total += debuff_shrink
                        if slot.remaining >= 0:
                            survivors.append(slot)
                    self.debuff_bar.slots = survivors
                base_heal_pct = eff.params.get("heal_pct", 0.0)
                per_change_pct = eff.params.get("heal_per_change_pct", 0.0)
                # Apply Health book bonus (IL2Cpp SkillBonusType=1).
                # Demytha A2 fully booked = +20% heal output.
                hb = float(getattr(skill, "health_book_bonus", 0.0) or 0.0)
                heal_scale = 1.0 + hb
                # Pre-fix (2026-06-18): sim counted changes per-ally, so a
                # hero with 1 extended buff and 5 shrunken boss debuffs got
                # changes=6 -> heal = 0.025 + 0.15 = 17.5% MaxHP. Real:
                # GLOBAL total = (1 buff × 5 heroes) + 5 debuffs = 10 ->
                # heal = 0.025 + 0.25 = 27.5% MaxHP. Sim was undershooting
                # heals by ~40-50%, which caused Mane to bleed out under
                # her A3 self-damage on Spirit days. Verified per-skill via
                # data/static/snapshots/men_skills_depth8.json.
                total_changes = buff_extend_total + debuff_shrink_total
                if (base_heal_pct or per_change_pct) and self.model_survival:
                    for c in self.champions:
                        if c.is_dead:
                            continue
                        heal = (c.max_hp
                                * (base_heal_pct + per_change_pct * total_changes)
                                * heal_scale)
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

            elif eff.effect_type == "team_heal":
                # Generic ally-team heal from static `KindId=Heal,
                # TargetType=AllAllies, MultiplierFormula=X*TRG_HP`.
                # Translator in load_game_profiles.py reads X into heal_pct.
                if self.model_survival:
                    pct = float(eff.params.get("heal_pct", 0.0))
                    hb = float(getattr(skill, "health_book_bonus", 0.0) or 0.0)
                    heal_scale = 1.0 + hb
                    for c in self.champions:
                        if c.is_dead:
                            continue
                        heal = c.max_hp * pct * heal_scale
                        c.current_hp = min(c.max_hp, c.current_hp + heal)

            elif eff.effect_type == "self_heal":
                # Generic self heal (Producer/Owner target). Same shape as
                # team_heal but only the caster.
                if self.model_survival:
                    pct = float(eff.params.get("heal_pct", 0.0))
                    hb = float(getattr(skill, "health_book_bonus", 0.0) or 0.0)
                    heal = champ.max_hp * pct * (1.0 + hb)
                    champ.current_hp = min(champ.max_hp, champ.current_hp + heal)

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

            elif eff.effect_type == "self_damage_alive_allies":
                # Maneater A3 "Ancient Blood": damage received = 5% MaxHP
                # for each ALIVE ally. Game-truth formula from skill 10703
                # effect 107033: `0.05*HP*(5-deadAlliesCount)`. The Damage
                # effect (KindId=Damage) has TargetType=Producer so the
                # caster takes the damage themselves. Verified 2026-06-15
                # from skill screenshots: "Damage received is equal to 5%
                # MAX HP for each alive ally."
                pct = float(eff.params.get("pct_max_hp_per_alive", 0.05))
                alive = sum(1 for c in self.champions if not c.is_dead)
                dmg = champ.max_hp * pct * alive
                if dmg > 0 and self.model_survival:
                    # Damage is absorbed by shield first, then HP.
                    if champ.shield_hp > 0:
                        absorbed = min(champ.shield_hp, dmg)
                        champ.shield_hp -= absorbed
                        dmg -= absorbed
                    champ.current_hp = max(0, champ.current_hp - dmg)
                    if champ.current_hp <= 0:
                        champ.is_dead = True

        # Master Hexer extension is now applied inline at the moment of
        # placement in _try_place_debuff — see _master_hexer_extends().
        # This block is intentionally left blank (was a TODO stub).

    def _try_place_debuff(self, champ: SimChampion, debuff_type: str,
                          duration: int, effective_chance: float) -> bool:
        """Try to place a debuff on CB. Returns True if placed.

        Master Hexer mastery (500354): 30% chance to extend placed debuff
        by 1 turn. Applied just before the bar receives the placement so
        the slot starts with the extended duration. Deterministic mode
        uses a per-(caster,debuff) fractional accumulator; MC mode rolls.
        """
        if self.debuff_bar.is_full():
            return False
        # Master Hexer extension — fires only when placement succeeds.
        # Resolved up-front so the same `duration` value is passed to
        # debuff_bar.add for both deterministic and MC branches.
        mh_extend = self._master_hexer_extends(champ, debuff_type)
        eff_duration = duration + mh_extend
        if self.deterministic:
            if effective_chance >= 0.5:
                return self.debuff_bar.add(debuff_type, eff_duration, champ.name)
            key = (champ.name, debuff_type)
            self._placement_debt[key] = self._placement_debt.get(key, 0.0) + effective_chance
            if self._placement_debt[key] >= 1.0:
                self._placement_debt[key] -= 1.0
                return self.debuff_bar.add(debuff_type, eff_duration, champ.name)
            return False
        else:
            if self.rng.random() < effective_chance:
                return self.debuff_bar.add(debuff_type, eff_duration, champ.name)
        return False

    def _master_hexer_extends(self, champ: "SimChampion",
                                 debuff_type: str) -> int:
        """Returns 1 if Master Hexer extends this debuff placement, else 0.

        Chance sourced from facade.mastery (mastery 500354). Deterministic
        mode uses a fractional accumulator keyed by (champion, debuff_type)
        so extensions converge to the expected value without RNG noise.
        """
        if not getattr(champ, "has_master_hexer", False):
            return 0
        # Pull chance from manifest — falls back to 0.30 if unavailable
        _f = _facade()
        chance = 0.30
        if _f is not None:
            try:
                rec = _f.mastery.get(500354) or {}
                cp = rec.get("conditional_proc") or {}
                if cp.get("chance") is not None:
                    chance = float(cp["chance"])
            except Exception:
                pass

        if self.deterministic:
            key = ("master_hexer", champ.name, debuff_type)
            self._placement_debt[key] = self._placement_debt.get(key, 0.0) + chance
            if self._placement_debt[key] >= 1.0:
                self._placement_debt[key] -= 1.0
                return 1
            return 0
        else:
            return 1 if self.rng.random() < chance else 0

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
    Brimstone chance is derived from grade via the blessing manifest
    facade. Falls back to local _BRIMSTONE_CHANCE_BY_GRADE if facade
    is unavailable.
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
    # Prefer manifest-backed lookup — falls back to constant table if
    # facade missing or grade not in manifest.
    _f = _facade()
    if _f is not None:
        chance = _f.blessing.brimstone_chance_by_grade(grade)
        if chance > 0:
            return True, chance
    return True, _BRIMSTONE_CHANCE_BY_GRADE.get(grade, 0.15)


# =============================================================================
# Empirical CD overrides — per (hero, skill) calibration
# =============================================================================
# REVERTED 2026-06-15 (Round 23): User uploaded screenshots proving Maneater
# A3 is fully booked at level 3/3 with both cd-reduction bonuses applied
# (effective cd=5). The "cd=4" override was a hack masking a different gap.
# The real missing mechanic lives elsewhere — TM cycle, buff modeling, or
# an unmodeled passive. Investigation continues; don't re-add cd overrides
# without ground-truth proof from the live skill data.
#
# Format: { hero_name: { skill_name: cd_override } } — kept as empty
# scaffold for future use, NOT as a calibration backdoor.
EMPIRICAL_CD_OVERRIDES: dict[str, dict[str, int]] = {}


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

        # Empirical override applied AFTER base_cd computation. See
        # EMPIRICAL_CD_OVERRIDES dict + project_cb_speed_compensating_wrong
        # memory for the calibration rationale.
        _emp_override = EMPIRICAL_CD_OVERRIDES.get(name, {}).get(sk_name)
        _base_cd = _emp_override if _emp_override is not None else (sd["cd"] if sd["cd"] > 0 else 0)

        sim_sk = SimSkill(
            name=sk_name,
            base_cd=_base_cd,
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
            shield_creation_bonus=float(sd.get("shield_creation_bonus", 0.0) or 0.0),
            health_book_bonus=float(sd.get("health_book_bonus", 0.0) or 0.0),
            attack_book_bonus=float(sd.get("attack_book_bonus", 0.0) or 0.0),
            ignore_res_book_bonus=float(sd.get("ignore_res_book_bonus", 0.0) or 0.0),
        )
        skills.append(sim_sk)

    # Load passive data from game-accurate profiles
    pd = PASSIVE_DATA.get(name, {})

    # All passive values from PASSIVE_DATA (pre-computed by load_game_profiles)
    passive_ally_protect = pd.get('ally_protect', False)
    passive_dmg_reduction = pd.get('dmg_reduction', 0.0)
    # Team-wide reduction (e.g. Geomancer Stoneguard -15% to ALL allies).
    # Stamped on stats so sim init can propagate to every champion.
    if pd.get('team_dmg_reduction', 0):
        stats = dict(stats)
        stats['team_dmg_reduction'] = pd['team_dmg_reduction']
    passive_extra_turns = pd.get('extra_turns', False)
    passive_buff_extension = pd.get('buff_extension', False)
    a1_self_heal = pd.get('a1_self_heal_pct', 0.0)
    a1_target_heal = pd.get('a1_target_heal_pct', 0.0)
    combo_atk_pct = pd.get('combo_atk_pct', 0.0)
    combo_cd_pct = pd.get('combo_cd_pct', 0.0)
    burn_stat_pct = pd.get('burn_stat_pct', 0.0)
    burn_dmg_red = pd.get('burn_dmg_reduction', 0.0)
    passive_debuffs_data = pd.get('passive_debuffs', []) or []

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

    # Blessing damage amplifiers — Heavencast (2201 EnhancedWeapon) and
    # Nature's Wrath (5201 NatureBalance). Plarium doesn't expose the
    # per-grade coefficient in static export; using community-documented
    # default 0.06 (+6% per buff/debuff) for epic/grade 1. Refine per-
    # grade later when better source available.
    heavencast_pct = 0.0
    natures_wrath_pct = 0.0
    phantom_touch_mult = 0.0
    phantom_touch_repeat = 1
    bl = stats.get("blessing") if isinstance(stats.get("blessing"), dict) else None
    if bl is not None:
        bid = int(bl.get("id", 0))
        grade = int(bl.get("grade", 0))
        if bid == 2201:  # EnhancedWeapon / Heavencast (skill 600090)
            # Grade 0-1: 0.005, grade 2-3: 0.01, grade 4-5: 0.015 per buff
            # (grade field is 0-indexed; UI grade 1 = data grade 0).
            if grade >= 4:
                heavencast_pct = 0.015
            elif grade >= 2:
                heavencast_pct = 0.01
            else:
                heavencast_pct = 0.005
        elif bid == 5201:  # NatureBalance / Nature's Wrath (skill 600270)
            # Grade 0-3: 0.02 per counter, grade 4-5: 0.03 per counter
            # Counter capped at 3 (applied in _calc_skill_damage).
            if grade >= 4:
                natures_wrath_pct = 0.03
            else:
                natures_wrath_pct = 0.02
        elif bid == 1301:  # MagicOrb / Phantom Touch — 3.5*ATK bonus dmg per attack
            # Per static skill 600050 (verified 2026-06-22):
            #   Grades 0-1: Effect[0] gated by ownersDoubleAscendLevel==1||==2
            #   Grades 2-3: Effect[1] gated by ==3||==4
            #   Grade 4:    Effect[2] gated by ==5
            #   Grade 5:    Effect[3] gated by ==6 + Effect[4] ChangeEffectRepeatCount (+1 hit)
            # `grade` in /all-heroes is 0-indexed (grade 1 in UI = 0 in field, etc.).
            # All grades share MultiplierFormula=3.5*ATK.
            phantom_touch_mult = 3.5
            # Grade 5 (UI grade 6) gets +1 repeat per attack.
            if grade >= 5:
                phantom_touch_repeat = 2

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
        heavencast_pct_per_buff=heavencast_pct,
        natures_wrath_pct_per_debuff=natures_wrath_pct,
        phantom_touch_mult=phantom_touch_mult,
        phantom_touch_repeat=phantom_touch_repeat,
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
        has_cycle_of_magic=MASTERY_IDS.get("cycle_of_magic", 500342) in masteries,
        has_lasting_gifts=MASTERY_IDS.get("lasting_gifts", 500351) in masteries,
        is_geomancer=(name == "Geomancer"),
        is_counterattack_provider=(name == "Skullcrusher"),
        combo_atk_pct=combo_atk_pct,
        combo_cd_pct=combo_cd_pct,
        burn_stat_pct=burn_stat_pct,
        burn_dmg_reduction=burn_dmg_red,
        passive_debuffs=list(passive_debuffs_data),
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
    # wins, and subsequent copies of a duplicate-eligible hero (per
    # DUPLICATE_INSTANCE_HEROES) get stashed under `<name>_N` so multi-
    # copy tunes (e.g. RabBatEater dual-Maneater) can reach both.
    hero_by_name = {}
    _dup_seen: dict[str, int] = {}
    for h in heroes_data["heroes"]:
        name = h.get("name", "")
        if not name:
            continue
        if name not in hero_by_name:
            hero_by_name[name] = h
            _dup_seen[name] = 1
        elif name in DUPLICATE_INSTANCE_HEROES:
            _dup_seen[name] = _dup_seen.get(name, 1) + 1
            key = _dup_key_for(name, _dup_seen[name])
            if key not in hero_by_name:
                hero_by_name[key] = h

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


def _build_team_setup(hero_names: List[str], use_current_gear: bool = True):
    """Heavy one-shot work for evaluate_team_calibrated / evaluate_team_mc.

    Returns a dict carrying everything needed to rebuild fresh sim
    champions across trials: team hero records, optimized artifacts,
    account data, preset opener/priority plan, and the cached element
    per slot. Used by the MC wrapper to avoid re-doing data loads,
    calc_stats, and gear optimization for every trial.
    """
    from cb_optimizer import calc_stats, optimal_artifacts_for_hero
    from cb_optimizer import UK_ME_SPD_RANGE
    base = Path(__file__).parent.parent
    with open(base / "heroes_6star.json") as f:
        heroes_data = json.load(f)
    with open(base / "all_artifacts.json") as f:
        artifacts_data = json.load(f)
    with open(base / "account_data.json") as f:
        account = json.load(f)

    hero_by_name = {}
    for h in heroes_data["heroes"]:
        name = h.get("name", "")
        if name and name not in hero_by_name:
            hero_by_name[name] = h

    from profile_resolver import make_synthetic_hero_record
    from cb_profiles import resolve as _resolve_profile
    from load_game_profiles import load_profiles as _lgp
    SD, _, _, _ = _lgp()

    team_h, team_p = [], []
    _dup_count: dict[str, int] = {}
    for tname in hero_names:
        key = tname
        if tname in DUPLICATE_INSTANCE_HEROES:
            _dup_count[tname] = _dup_count.get(tname, 0) + 1
            key = _dup_key_for(tname, _dup_count[tname])
        h = hero_by_name.get(key) or hero_by_name.get(tname)
        if not h:
            h = make_synthetic_hero_record(tname)
            if not h:
                return {"error": f"Hero not found: {tname}"}
        team_h.append(h)
        team_p.append(_resolve_profile(tname, SD.get(tname)))

    if use_current_gear:
        assigned_arts = []
        for h in team_h:
            current = h.get("artifacts", []) or []
            assigned_arts.append([a for a in current
                                  if isinstance(a, dict) and a.get("id")])
    else:
        all_arts = [a for a in artifacts_data.get("artifacts", []) if not a.get("error")]
        used = set()
        from cb_optimizer import stun_priority
        has_uk = sum(1 for p in team_p if p and p.unkillable) >= 2
        dps_idx = [i for i, p in enumerate(team_p) if p and not p.unkillable]
        stun_idx = (min(dps_idx, key=lambda i: stun_priority(team_p[i]))
                    if dps_idx else -1)
        priority_order = sorted(range(5), key=lambda i: (
            0 if (team_p[i] and team_p[i].unkillable) else
            (3 if i == stun_idx else
             (1 if (team_p[i] and team_p[i].needs_acc) else 2))
        ))
        assigned_arts = [[] for _ in range(5)]
        for pi in priority_order:
            if team_h[pi].get("_synthetic"):
                continue
            avail = [a for a in all_arts if a.get("id") not in used and a.get("rank", 0) >= 5]
            spd_max = (UK_ME_SPD_RANGE[1]
                       if (has_uk and team_p[pi] and team_p[pi].unkillable)
                       else None)
            is_stun = has_uk and pi == stun_idx
            arts, _ = optimal_artifacts_for_hero(
                team_h[pi], team_p[pi], avail, account,
                spd_max=spd_max, is_stun_target=is_stun)
            assigned_arts[pi] = arts
            for a in arts:
                used.add(a.get("id"))

    # Pre-compute stats per hero (expensive — calls calc_stats)
    stats_per_hero = [calc_stats(team_h[i], assigned_arts[i], account)
                      for i in range(len(hero_names))]

    # Resolve preset opener+priority plan
    try:
        from preset_loader import load_preset_for_team
        preset_plan = load_preset_for_team(hero_names) or {}
    except Exception:
        preset_plan = {}

    return {
        "hero_names": hero_names,
        "team_h": team_h,
        "stats_per_hero": stats_per_hero,
        "preset_plan": preset_plan,
        "elements": [int(team_h[i].get("element", 4) or 4)
                     for i in range(len(hero_names))],
        "masteries": [team_h[i].get("masteries", [])
                      for i in range(len(hero_names))],
    }


def _build_sim_champs_from_setup(setup: dict):
    """Build fresh SimChampions from a setup dict (cheap; no calc_stats).

    Called once per Monte Carlo trial to give each run independent
    mutable hero state (cooldowns, buffs, accumulators).
    """
    hero_names = setup["hero_names"]
    sim_champs = []
    _opener_dup_count: dict[str, int] = {}
    for i, tname in enumerate(hero_names):
        plan = setup["preset_plan"].get(tname) or {}
        opening = plan.get("opening") or []
        if not opening and tname in DUPLICATE_INSTANCE_HEROES:
            _opener_dup_count[tname] = _opener_dup_count.get(tname, 0) + 1
            opening = _dup_opener_for(tname, _opener_dup_count[tname])
        champ = build_sim_champion(tname, setup["stats_per_hero"][i], i + 1,
                                    masteries=setup["masteries"][i],
                                    opening=opening,
                                    element=setup["elements"][i])
        priority = plan.get("priority") or []
        if priority:
            champ.skill_priority = list(priority)
        sim_champs.append(champ)
    return sim_champs


def evaluate_team_calibrated(hero_names: List[str], cb_element: int = 4,
                              use_current_gear: bool = True,
                              force_affinity: bool = True,
                              max_cb_turns: int = 50,
                              verbose: bool = False,
                              deterministic: bool = True,
                              rng_seed: int = None) -> dict:
    """Run the calibrated CB sim on an arbitrary 5-hero team.

    Mirrors what `cb_sim.py --team "X,Y,Z" --use-current-gear` does
    programmatically — no tune required, no DWJ assignment. Uses the
    hero's currently equipped artifacts (or re-optimizes via the
    artifact optimizer when use_current_gear=False), applies the
    Maneater A3-opener convention from cb_sim main, and runs the
    full CBSimulator with the same defaults as the calibration tests
    (deterministic=True, force_affinity=True, max_cb_turns=50).

    Args:
      deterministic: True for expected-value calc (single number,
        used in regression's point comparison). False for Monte
        Carlo — actual RNG rolls per cast. Pair with `rng_seed`
        when running multiple trials.
      rng_seed: seed for the per-run RNG when deterministic=False.

    On the calibration team (Maneater/Demytha/Ninja/Geomancer/
    Venomage) with current gear and Magic UNM, this matches the
    +0.61% calibration value (~36M).

    Returns a dict with keys: total, cb_turns, errors, valid (or
    `error` on failure).
    """
    setup = _build_team_setup(hero_names, use_current_gear=use_current_gear)
    if "error" in setup:
        return {"error": setup["error"], "total": 0}
    sim_champs = _build_sim_champs_from_setup(setup)
    sim = CBSimulator(sim_champs, deterministic=deterministic,
                       rng_seed=rng_seed,
                       verbose=verbose,
                       cb_element=cb_element,
                       force_affinity=force_affinity)
    return sim.run(max_cb_turns=max_cb_turns)


def evaluate_team_mc(hero_names: List[str], cb_element: int = 4,
                      n_trials: int = 30,
                      use_current_gear: bool = True,
                      force_affinity: bool = True,
                      max_cb_turns: int = 50,
                      seed_base: int = 1000) -> dict:
    """Monte Carlo wrapper around evaluate_team_calibrated.

    Runs the sim `n_trials` times with deterministic=False and varying
    rng_seeds, then returns the distribution. Use this for fixture
    validation when real-game RNG variance is significant (e.g. Force
    UNM fixtures where one bad glance can cascade into a team wipe).

    Returns:
      {trials, mean, median, stdev, min, max, p5, p25, p75, p95,
       turn_distributions: {bt: [trial values]}, samples: [totals]}
    """
    import statistics as _stats

    # One-shot setup: hero data, gear, stats, preset plan. Reused
    # across all trials so we only pay the calc_stats / file-load
    # cost once instead of n_trials times (was ~3s per trial before
    # refactor, now ~3s setup + ~0.5s/trial after).
    setup = _build_team_setup(hero_names, use_current_gear=use_current_gear)
    if "error" in setup:
        return {"error": setup["error"], "trials": 0}

    samples = []
    per_bt = {}  # bt -> list of cumulative damages
    for i in range(n_trials):
        sim_champs = _build_sim_champs_from_setup(setup)
        sim = CBSimulator(sim_champs, deterministic=False,
                           rng_seed=seed_base + i * 7919,
                           cb_element=cb_element,
                           force_affinity=force_affinity)
        r = sim.run(max_cb_turns=max_cb_turns)
        if "error" in r:
            continue
        samples.append(r.get("total", 0))
        for snap in r.get("turn_snapshots") or []:
            bt = snap.get("cb_turn")
            if bt is None:
                continue
            per_bt.setdefault(bt, []).append(snap.get("cumulative_damage", 0))
    if not samples:
        return {"error": "all trials failed", "trials": 0}

    sorted_s = sorted(samples)
    n = len(sorted_s)
    def _pct(p):
        idx = max(0, min(n - 1, int(round(p / 100.0 * (n - 1)))))
        return sorted_s[idx]

    return {
        "trials": n,
        "mean": _stats.mean(sorted_s),
        "median": _stats.median(sorted_s),
        "stdev": _stats.stdev(sorted_s) if n > 1 else 0.0,
        "min": sorted_s[0],
        "max": sorted_s[-1],
        "p5": _pct(5),
        "p25": _pct(25),
        "p75": _pct(75),
        "p95": _pct(95),
        "turn_distributions": per_bt,
        "samples": samples,
    }


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

    # Resolve heroes — duplicate-eligible names (DUPLICATE_INSTANCE_HEROES)
    # get stashed under `<name>_N` for the Nth copy.
    hero_by_name = {}
    _dup_seen: dict[str, int] = {}
    for h in heroes_data["heroes"]:
        name = h.get("name", "")
        if not name:
            continue
        if name not in hero_by_name:
            hero_by_name[name] = h
            _dup_seen[name] = 1
        elif name in DUPLICATE_INSTANCE_HEROES:
            _dup_seen[name] = _dup_seen.get(name, 1) + 1
            key = _dup_key_for(name, _dup_seen[name])
            if key not in hero_by_name:
                hero_by_name[key] = h

    # Resolve team heroes. Owned heroes win; unowned names fall back to
    # a synthetic record built from hero_types.json (max-ascended,
    # level 60, no equipped gear). The artifact optimizer below assigns
    # them best-available gear from the user's vault — so simming a
    # potential hero reflects "what would happen if I pulled them today
    # with my current account".
    from cb_profiles import resolve as _resolve_profile
    from profile_resolver import make_synthetic_hero_record
    from load_game_profiles import load_profiles as _lgp
    _SKILL_DATA, _, _, _ = _lgp()
    team_h, team_p = [], []
    _dup_count: dict[str, int] = {}
    synthetic_used = []
    for tname in team_names:
        if tname in DUPLICATE_INSTANCE_HEROES:
            _dup_count[tname] = _dup_count.get(tname, 0) + 1
            key = _dup_key_for(tname, _dup_count[tname])
        else:
            key = tname
        h = hero_by_name.get(key)
        if not h:
            h = make_synthetic_hero_record(tname)
            if not h:
                print(f"Hero not found: {tname}")
                return
            synthetic_used.append(tname)
        p = _resolve_profile(tname, _SKILL_DATA.get(tname))
        team_h.append(h)
        team_p.append(p)
    if synthetic_used:
        print(f"  (potential heroes — gearing from vault: {', '.join(synthetic_used)})")

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
        _opener_dup_count: dict[str, int] = {}
        for i, tname in enumerate(team_names):
            stats = calc_stats(team_h[i], assigned_arts[i], account)
            opening = []
            if tname in DUPLICATE_INSTANCE_HEROES:
                _opener_dup_count[tname] = _opener_dup_count.get(tname, 0) + 1
                opening = _dup_opener_for(tname, _opener_dup_count[tname])
            # 2026-06-18 fix: pass element from hero record so affinity
            # matchups apply (was defaulting to 4=Void → glance gating + damage
            # modifiers never fired in the --use-current-gear path).
            hero_elem = team_h[i].get("element", 4)
            champ = build_sim_champion(tname, stats, i + 1,
                                        masteries=team_h[i].get("masteries", []),
                                        opening=opening,
                                        element=hero_elem)
            sim_champs.append(champ)
            print(f"  {tname:20s} SPD:{stats[SPD]:.0f} ACC:{stats[ACC]:.0f} "
                  f"ATK:{stats[ATK]:.0f} DEF:{stats[DEF]:.0f} HP:{stats[HP]:.0f}")

        # 2026-06-18: apply user's saved in-game preset (starters + skill
        # priorities) to make the sim match their actual flagship tune.
        # Without this the sim runs Default-AI everywhere, which yields the
        # known 16M-vs-36M gap on MEN. Mirrors cb_calibrate.py path.
        try:
            from preset_loader import load_preset_for_team
            plan = load_preset_for_team(team_names)
        except Exception as e:
            plan = {}
            print(f"  [preset] load failed: {e}")
        if plan:
            applied = []
            for champ in sim_champs:
                entry = plan.get(champ.name) or {}
                p_open = entry.get("opening") or []
                p_prio = entry.get("priority") or []
                if p_open:
                    champ.opening = list(p_open)
                if p_prio:
                    champ.skill_priority = list(p_prio)
                if p_open or p_prio:
                    applied.append(
                        f"{champ.name}(open={p_open or '-'} prio={p_prio or '-'})")
            if applied:
                print(f"  [preset] applied: {', '.join(applied)}")
        else:
            print(f"  [preset] no matching preset for team — running Default AI")

        # Run simulation
        if args.monte_carlo > 0:
            totals = []
            for seed in range(args.monte_carlo):
                sim = CBSimulator(deepcopy(sim_champs), deterministic=False,
                                  rng_seed=seed, verbose=False,
                                  cb_element=cb_element,
                                  bugfix_buff_tick=False,
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
                              bugfix_buff_tick=False,
                              force_affinity=not args.no_force_affinity)
            result = sim.run(max_cb_turns=args.max_cb_turns)

            print(f"\n{'='*70}")
            print(f"TOTAL DAMAGE: {result['total']/1e6:.1f}M over {result['cb_turns']} CB turns")
            gaps = len(result["errors"])
            tune_str = "VALID" if result["valid"] else f"INVALID ({gaps} gaps)"
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
                    print(f"  x {e}")
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
            team_h[pi], team_p[pi], avail, account,
            spd_max=spd_max, is_stun_target=is_stun)
        assigned_arts[pi] = arts
        for a in arts:
            used.add(a.get("id"))

    # Build SimChampions with optimized stats — use the ACTUAL calculated stats from the
    # assigned gear. No hard-coded speed overrides; the tune is whatever the gear produces.
    # (Previous Budget-UK overrides that forced Maneater=228/215 and DPS=171-189 removed
    # because they conflicted with Myth-Eater or any other tune.)
    sim_champs = []
    _opener_dup_count: dict[str, int] = {}
    for i, tname in enumerate(team_names):
        stats = calc_stats(team_h[i], assigned_arts[i], account)
        opening = []
        if tname in DUPLICATE_INSTANCE_HEROES:
            _opener_dup_count[tname] = _opener_dup_count.get(tname, 0) + 1
            opening = _dup_opener_for(tname, _opener_dup_count[tname])
        champ = build_sim_champion(tname, stats, i + 1,
                                    masteries=team_h[i].get("masteries", []),
                                    opening=opening,
                                    element=int(team_h[i].get("element", 4) or 4))
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
