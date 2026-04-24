#!/usr/bin/env python3
"""
DWJ Speed Tune Library.

Defines all 65+ DWJ speed tunes with:
- Speed slots and ranges per position
- Opening skill sequences
- AI preset skill priorities (not just highest-CD)
- Tune type (unkillable, traditional, block damage)
- Required hero roles per slot

Used by cb_sim.py to accurately simulate any tune composition.

Usage:
    from tune_library import get_tune, list_tunes, match_tune
    tune = get_tune("myth_eater")
    tunes = match_tune(["Maneater", "Demytha"])  # find tunes these heroes can run
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class TuneSlot:
    """A slot in a speed tune with requirements."""
    role: str                    # "fast_uk", "slow_uk", "block_damage", "dps", "stun", "seeker", etc.
    speed_range: Tuple[int, int] # (min, max) SPD
    opening: List[str] = field(default_factory=list)  # ["A1", "A3"] = open A1 then A3
    skill_priority: List[str] = field(default_factory=list)  # ["A3", "A2", "A1"] = use A3 first when ready
    required_hero: Optional[str] = None  # specific hero name, or None for any
    needs_acc: bool = False
    is_stun_target: bool = False
    notes: str = ""


@dataclass
class TuneDefinition:
    """A complete DWJ speed tune."""
    name: str
    tune_id: str               # short ID like "myth_eater", "budget_uk"
    tune_type: str             # "unkillable", "block_damage", "traditional"
    difficulty: str            # "easy", "moderate", "hard", "expert", "extreme"
    performance: str           # "1_key_unm", "2_key_unm", "3_key_unm"
    affinities: str            # "all", "void_only", "not_force"
    cb_speed: int = 190        # UNM default
    slots: List[TuneSlot] = field(default_factory=list)
    notes: str = ""


# =============================================================================
# Tune definitions — from docs/deadwoodjedi_speed_tunes.md
# =============================================================================

TUNES = {}

def _register(tune):
    TUNES[tune.tune_id] = tune
    return tune


# --- Myth Eater (#30) ---
# Source of truth: https://deadwoodjedi.com/speed-tunes/myth-eater/
# Corrected 2026-04-23 after comparing to live DWJ tune page + calculator:
#   - Maneater opens A1 then A3 (NOT A3 only — previous value broke the sync)
#   - Ninja slot (4:3) band is 224-230 TRUE SPD (NOT 204-207)
#   - 1:1 DPS slot is 179 exactly (NOT 177-180 band)
#   - Slow DPS slot 160-169 (widened from 159-162)
#   - Maneater A3 at Level 3 (fully booked) = CD 5 (base 7, -1 at lvl 2, -1
#     at lvl 3). In-game screenshot confirms: "Lvl.2 Cooldown -1, Lvl.3 -1".
#     The tune's 3-BT Maneater A3 cycle IS achievable with this hero.
#   - Ninja is weak on Force CB — sub out for a 178-SPD DPS on Force days.
_register(TuneDefinition(
    name="Myth Eater",
    tune_id="myth_eater",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all_except_force",
    slots=[
        TuneSlot(role="fast_uk", speed_range=(286, 286), required_hero="Maneater",
                 opening=["A1", "A3"],
                 skill_priority=["A3", "A2", "A1"],
                 notes="Open A1 then A3 on Round 1. Priorities afterwards: A3 > A2 > A1."),
        TuneSlot(role="block_damage", speed_range=(171, 171), required_hero="Demytha",
                 opening=["A1", "A2", "A3"],
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="dps_4to3", speed_range=(224, 230), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"],
                 notes="4:3 DPS slot. Ninja ideal (TM fill + HP Burn). "
                       "Ninja: set A3 as 1st priority, A2 as 2nd. "
                       "Sub out on FORCE affinity — replace with 178-SPD DPS."),
        TuneSlot(role="dps_1to1", speed_range=(179, 179), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"],
                 notes="1:1 DPS slot at exactly 179 SPD"),
        TuneSlot(role="dps_slow", speed_range=(160, 169), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"],
                 notes="Slow DPS slot, 160-169 range"),
    ],
    notes="Unkillable via Maneater A3 + Block Damage via Demytha A3. "
          "UNM tune syncs on CB turn 6; NM on CB turn 9. "
          "Speeds are TRUE SPD (exclude Speed Auras, include Area Bonuses). "
          "Recommended blessings: 1 Brimstone, 1 Cruelty, rest Phantom Touch. "
          "Masteries: stick to Warmaster + Offense (NOT Relentless, Cycle of Magic, "
          "or Lasting Gifts — they break timing). "
          "On FORCE CB: sub Ninja out for a 178-SPD DPS of non-weak affinity."
))

# --- Myth Eater Ninja variant ---
# Verified from DWJ calculator 2026-04-23 via the "Ninja UNM" link on
# deadwoodjedi.com/speed-tunes/myth-eater/ (calculator URL hash
# 6737fa4be0ec51c5065a433d3f23b7616d9ca430). This is the alternative
# Myth Eater tune for use WITH Ninja — Ninja's A2 passive TM boost lets
# him run at SPD 205 (not the standard 224-230 range). All other slot
# speeds differ slightly too: Venomage 160 (was 160-169), priorities
# on Ninja are A3(1)/A2(2)/A1(default). Works on all affinities
# INCLUDING Force (unlike the non-Ninja standard variant). This is the
# tune actually used by the user's current team.
_register(TuneDefinition(
    name="Myth Eater (Ninja variant)",
    tune_id="myth_eater_ninja",
    tune_type="unkillable",
    difficulty="hard",
    performance="2_key_unm",
    affinities="all",
    slots=[
        # All slots use DWJ-delay convention (see memory feedback_raid_preset_delays.md):
        # opener = [A1] (single-skill opener always). Priorities below map
        # DWJ delays: skill with delay=0 = priority 1st, delay=1 = priority 2nd,
        # delay=2 = priority 3rd. A2 lands wherever A3's delay leaves room.
        TuneSlot(role="fast_uk", speed_range=(288, 288), required_hero="Maneater",
                 opening=["A1"],
                 skill_priority=["A2", "A3", "A1"],
                 notes="A2 delay=0 (1st), A3 delay=1 (2nd), A1 default. "
                       "A2 CD=3/4, A3 CD=5 after books."),
        TuneSlot(role="block_damage", speed_range=(172, 172), required_hero="Demytha",
                 opening=["A1"],
                 skill_priority=["A2", "A3", "A1"],
                 notes="A2 delay=0 (1st — Unkillable), A3 delay=2 (2nd — BlockDmg), "
                       "A1 default. A2 CD=3, A3 CD=3."),
        TuneSlot(role="ninja_tm_boost", speed_range=(205, 205), required_hero="Ninja",
                 opening=["A1"],
                 skill_priority=["A2", "A3", "A1"],
                 notes="Ninja's A2 passive TM fill lets him run at 205 not 224. "
                       "A2 delay=0 (1st), A3 delay=1 (2nd), A1 default. "
                       "A2 CD=3, A3 CD=4 after books."),
        TuneSlot(role="dps_1to1", speed_range=(178, 178), needs_acc=True,
                 opening=["A1"],
                 skill_priority=["A2", "A3", "A1"],
                 notes="1:1 slot at 178 SPD (Geomancer typical). "
                       "No delays — A2 1st, A3 2nd, A1 default."),
        TuneSlot(role="dps_slow", speed_range=(160, 160), needs_acc=True,
                 opening=["A1"],
                 skill_priority=["A2", "A3", "A1"],
                 notes="Slow DPS at 160 SPD (Venomage typical). "
                       "No delays — A2 1st, A3 2nd, A1 default."),
    ],
    notes="Myth Eater with Ninja. Ninja's self-TM-fill (A2 passive) "
          "substitutes for higher raw SPD, letting him run at 205. "
          "Works on all affinities including Force. 2 key UNM. "
          "Sync: UNM on CB turn 6, NM on turn 9."
))


# --- Budget Unkillable (#10) ---
_register(TuneDefinition(
    name="Budget Maneater Unkillable",
    tune_id="budget_uk",
    tune_type="unkillable",
    difficulty="easy",
    performance="2_key_unm",
    affinities="all",
    slots=[
        TuneSlot(role="fast_uk", speed_range=(218, 220), required_hero="Maneater",
                 opening=["A3"],
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="slow_uk", speed_range=(215, 218), required_hero="Maneater",
                 opening=["A1", "A3"],
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="dps", speed_range=(171, 189), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="dps", speed_range=(171, 189), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="stun", speed_range=(111, 118), is_stun_target=True,
                 skill_priority=["A2", "A3", "A1"],
                 notes="Slowest hero, absorbs stun"),
    ],
    notes="Requires 2 Maneaters. Stun target slot takes all stuns."
))

# --- Batman Forever (#4) ---
_register(TuneDefinition(
    name="Batman Forever",
    tune_id="batman_forever",
    tune_type="unkillable",
    difficulty="hard",
    performance="1_key_unm",
    affinities="all",
    slots=[
        TuneSlot(role="fast_uk", speed_range=(265, 285),
                 opening=["A3"],  # Open with UK skill
                 skill_priority=["A3", "A2", "A1"],
                 notes="4-Turn UK champion (Maneater, Tower, Roshcard)"),
        TuneSlot(role="seeker", speed_range=(248, 254), required_hero="Seeker",
                 opening=["A1", "A2"],
                 skill_priority=["A2", "A1"],
                 notes="TM boost creates 2:1 ratio"),
        TuneSlot(role="dps_block_debuff", speed_range=(245, 247), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"],
                 notes="Must have Block Debuffs or be immune to stun"),
        TuneSlot(role="slow_uk", speed_range=(245, 247),
                 opening=["A1", "A3"],
                 skill_priority=["A3", "A2", "A1"],
                 notes="Second 4-Turn UK champion"),
        TuneSlot(role="dps_cleanse", speed_range=(218, 227), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"],
                 notes="DPS with cleanse or stun immunity"),
    ],
    notes="2:1 speed ratio via Seeker TM boost. Requires two 4-turn UK champions."
))

# --- Budget Myth Heir (#8) ---
_register(TuneDefinition(
    name="Budget Myth Heir",
    tune_id="budget_myth_heir",
    tune_type="unkillable",
    difficulty="easy",
    performance="3_key_unm",
    affinities="all",
    slots=[
        TuneSlot(role="block_damage", speed_range=(255, 263), required_hero="Demytha",
                 opening=["A3"],
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="buff_extend", speed_range=(243, 254), required_hero="Heiress",
                 opening=["A2"],
                 skill_priority=["A2", "A1"]),
        TuneSlot(role="dps", speed_range=(234, 242), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="dps", speed_range=(171, 233), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="dps", speed_range=(171, 233), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"]),
    ],
    notes="Demytha Block Damage extended by Heiress passive. 3 DPS slots."
))

# --- Myth Salad (#38) ---
_register(TuneDefinition(
    name="Myth Salad",
    tune_id="myth_salad",
    tune_type="unkillable",
    difficulty="moderate",
    performance="2_key_unm",
    affinities="all",
    slots=[
        TuneSlot(role="block_damage", speed_range=(290, 295), required_hero="Demytha",
                 opening=["A3"],
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="block_debuff", speed_range=(218, 222),
                 skill_priority=["A2", "A1"],
                 notes="Sepulcher Sentinel ideal — Block Debuffs for stun"),
        TuneSlot(role="seeker", speed_range=(200, 205), required_hero="Seeker",
                 opening=["A1", "A2"],
                 skill_priority=["A2", "A1"]),
        TuneSlot(role="dps", speed_range=(188, 193), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"]),
        TuneSlot(role="dps", speed_range=(168, 172), needs_acc=True,
                 skill_priority=["A3", "A2", "A1"]),
    ],
    notes="Demytha BD + Sepulcher Block Debuffs. Seeker TM boost. TRUE full auto."
))


# =============================================================================
# API
# =============================================================================

def get_tune(tune_id: str) -> Optional[TuneDefinition]:
    return TUNES.get(tune_id)


def list_tunes() -> List[TuneDefinition]:
    return list(TUNES.values())


def match_tune(hero_names: List[str]) -> List[TuneDefinition]:
    """Find tunes that the given heroes can run."""
    name_set = set(hero_names)
    matches = []
    for tune in TUNES.values():
        # Check if required heroes are present
        required = set(s.required_hero for s in tune.slots if s.required_hero)
        if not required.issubset(name_set):
            continue
        matches.append(tune)
    return matches


def assign_heroes_to_tune(hero_names: List[str], tune: TuneDefinition) -> Optional[List[Tuple[str, TuneSlot]]]:
    """Assign heroes to tune slots. Returns [(hero_name, slot), ...] or None if impossible."""
    assignments = [None] * len(tune.slots)
    used = set()

    # First pass: assign required heroes
    for i, slot in enumerate(tune.slots):
        if slot.required_hero:
            if slot.required_hero in hero_names and slot.required_hero not in used:
                assignments[i] = (slot.required_hero, slot)
                used.add(slot.required_hero)
            elif slot.required_hero == "Maneater":
                # Handle 2x Maneater
                me_count = hero_names.count("Maneater")
                me_used = sum(1 for a in assignments if a and a[0] == "Maneater")
                if me_used < me_count:
                    assignments[i] = ("Maneater", slot)
                    used.add(f"Maneater_{me_used}")
                else:
                    return None
            else:
                return None

    # Second pass: assign remaining heroes to DPS slots
    remaining = [n for n in hero_names if n not in used or n == "Maneater"]
    # Remove used Maneaters
    for i, a in enumerate(assignments):
        if a and a[0] in remaining:
            remaining.remove(a[0])

    for i, slot in enumerate(tune.slots):
        if assignments[i] is not None:
            continue
        if not remaining:
            return None
        # Pick first available hero for this slot
        assignments[i] = (remaining.pop(0), slot)

    return assignments


# =============================================================================
# CLI
# =============================================================================
if __name__ == "__main__":
    print(f"=== DWJ Speed Tune Library ===")
    print(f"Tunes: {len(TUNES)}")
    print()
    for tune in TUNES.values():
        print(f"  {tune.tune_id:25s} {tune.name:30s} {tune.performance:12s} {tune.difficulty}")
        for i, slot in enumerate(tune.slots):
            req = f" ({slot.required_hero})" if slot.required_hero else ""
            opening = f" open={slot.opening}" if slot.opening else ""
            print(f"    Slot {i+1}: {slot.role:20s} SPD={slot.speed_range}{req}{opening}")
        print()
