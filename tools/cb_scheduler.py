"""DWJ-parity turn scheduler — extracted from calc_parity_sim.py.

This module provides the shared turn-scheduling engine that both
`calc_parity_sim` (cast-order parity check) and `cb_sim` (damage sim)
build on top of. It implements DWJ's ek() loop:

- TM ticks at 7 * effective_speed / 100 per tick (do-while: always tick once)
- Pick max-TM actor; tie-break by actor list index
- Pick highest-priority castable skill (cd=0, delay=0)
- Reset cast skill's cooldown; decrement all delays/cds by 1
- Decrement turn-end effect durations BEFORE applying new effects
- Filter expired effects after

100% match against DWJ calc on Myth Eater Ninja UNM, Myth Eater std UNM,
Batman Forever, Endless Speed (4/4 variants tested).

Usage:
    from cb_scheduler import (Actor, SkillConfig, Effect,
                              effective_speed, tick_until_ready, pick_skill,
                              advance_after_cast)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SkillConfig:
    alias: str
    id: str
    priority: int
    delay: int
    cooldown: int
    current_cooldown: int = 0


@dataclass
class Effect:
    """Buff or debuff entry on an actor.

    `reduceDurationAt` is "turn-end" by default — DWJ's ek loop decrements at
    the start of the OWNER's next turn, before that owner casts.
    "turn-start" is rare and used for stuns / freezes.
    """
    name: str
    amount: float = 0.0
    duration: int = 1
    reduceDurationAt: str = "turn-end"
    isAddedThisTurn: bool = False


@dataclass
class Actor:
    """Generic actor — works for both DWJ tune slots and live cb_sim champions.

    Callers populate skill_effects with whatever shape they need; the scheduler
    itself only reads turn_meter, effects, skill_configs, and the speed fields.
    """
    name: str
    is_boss: bool
    total_speed: int
    base_speed: int
    speed_bonus: int
    has_lore_of_steel: bool
    skill_configs: list[SkillConfig]
    skill_effects: dict[str, list] = field(default_factory=dict)
    turn_meter: float = 0.0
    has_extra_turn: bool = False
    effects: list[Effect] = field(default_factory=list)
    stat_mod_speed: float = 0.0


# ---------------- speed math ----------------

def speed_buff_modifier(actor: Actor) -> float:
    """DWJ's em(actor): net speed multiplier offset.

    Iterates effects: speed-buff multiplies (1+amount), speed-debuff subtracts.
    Returns the additive modifier so effective_speed = total * (1 + mod).
    """
    t = 1.0
    for e in actor.effects:
        if e.name == "speed-buff":
            t *= 1 + e.amount
        elif e.name == "speed-debuff":
            t -= e.amount
    return t - 1.0


def effective_speed(actor: Actor, aura: float) -> float:
    """DWJ's eh(actor, aura, buff_mod, stat_mod).

    Net formula: (total_speed + aura_bonus + stat_mod) * (1 + buff_mod).
    The boss is unaffected by the team's speed aura.
    """
    base = actor.base_speed
    aura_used = 0.0 if actor.is_boss else aura
    buff_mod = speed_buff_modifier(actor)
    true_speed = actor.total_speed + (aura_used / 100.0) * base + actor.stat_mod_speed
    return true_speed * (1.0 + buff_mod)


# ---------------- scheduler primitives ----------------

def tick_until_ready(actors: list[Actor], aura: float, *, threshold: float = 100.0,
                     max_safety_ticks: int = 10000) -> None:
    """DWJ's `do...while` TM tick loop. Always ticks AT LEAST once, then keeps
    ticking until at least one actor crosses `threshold`.

    Crucially this is do-while, not while: when an actor enters with TM already
    above threshold (carry-over from a previous cast's effects), DWJ still
    burns one tick. Skipping that tick caused a 9%-vs-91% parity miss earlier.
    """
    safety = 0
    while True:
        for a in actors:
            inc = 7.0 * effective_speed(a, aura) / 100.0
            a.turn_meter = round(a.turn_meter + inc, 12)
        safety += 1
        if any(a.turn_meter >= threshold for a in actors):
            break
        if safety > max_safety_ticks:
            raise RuntimeError("TM tick loop failed to terminate")


def pick_next_actor(actors: list[Actor], aura: float) -> Actor:
    """Find the actor that takes the next turn.

    Priority order:
      1. Anyone with `has_extra_turn` (consumes the flag).
      2. Otherwise: tick TMs (do-while), then pick max-TM. Ties resolved by
         actor list index — first one wins, matching DWJ's reduce(max).
    """
    actor = next((a for a in actors if a.has_extra_turn), None)
    if actor is not None:
        actor.has_extra_turn = False
        return actor
    tick_until_ready(actors, aura)
    max_tm = max(a.turn_meter for a in actors)
    return next(a for a in actors if a.turn_meter == max_tm)


def pick_skill(actor: Actor) -> Optional[SkillConfig]:
    """Pick the highest-priority castable skill (cd=0 AND delay=0).

    DWJ sorts skill_configs DESC by priority and returns the first castable
    one. This is OPPOSITE to Raid's in-game UI where priority 1 = highest.
    """
    sorted_cfg = sorted(actor.skill_configs, key=lambda c: -c.priority)
    return next(
        (c for c in sorted_cfg if c.current_cooldown == 0 and c.delay == 0),
        None,
    )


def consume_turn_start(actor: Actor) -> None:
    """Run before the actor picks/casts its skill: decrement turn-start
    effects and drop expired ones, then zero the turn meter.

    "turn-start" effects are rare — mostly stuns/freezes/sleep that block
    the actor at the moment they would act.
    """
    for e in actor.effects:
        if e.reduceDurationAt == "turn-start":
            e.duration -= 1
    actor.effects = [e for e in actor.effects if e.duration > 0]
    actor.turn_meter = 0.0


def advance_after_cast(actor: Actor, skill: SkillConfig) -> None:
    """Run after the cast: put the cast skill on its cooldown, decrement
    every other delay/cd by 1, then decrement turn-end effect durations.

    IMPORTANT: turn-end durations decrement BEFORE the skill's effects are
    applied. That means buffs added by THIS skill keep their full duration
    on the casting turn (they only start ticking down on the next actor's
    turn). This was a parity bug in earlier ports.
    """
    skill.current_cooldown = skill.cooldown
    for c in actor.skill_configs:
        c.delay = max(0, c.delay - 1)
        c.current_cooldown = max(0, c.current_cooldown - 1)
    for e in actor.effects:
        if e.reduceDurationAt == "turn-end":
            e.duration -= 1


def drop_expired_effects(actor: Actor) -> None:
    """Filter out effects whose duration has reached 0 or below. Call this
    after the per-cast effect dispatcher has run, so freshly-added buffs
    (which were not part of the turn-end decrement) remain in place.
    """
    actor.effects = [e for e in actor.effects if e.duration > 0]
