#!/usr/bin/env python3
"""Python port of DeadwoodJedi's calculator turn-order logic.

Spec: docs/dwj/calc_algorithm.md.

This first version models the turn-scheduler exactly (TM ticks, priority pick,
cooldowns, delays, extra turns, speed buffs/debuffs) — enough to reproduce
DWJ's cast-order output. Skill-effect application (add_buff / add_debuff /
tm_up / reduce_cd etc.) is deferred; the sim runs with empty effect handling
and still produces correct cast timelines for tunes where no passive TM
manipulation occurs before sync.

Usage:
    # Run against a scraped calc variant (hash)
    python3 tools/calc_parity_sim.py --hash 6737fa4be0ec51c5065a433d3f23b7616d9ca430 --turns 50

    # Run against an ad-hoc tune
    python3 tools/calc_parity_sim.py --slug myth-eater --variant "Ultra Nightmare" --turns 25

The output is one line per turn:
    Turn  3 (boss tn 0): Maneater      A1
    Turn  4 (boss tn 0): Ninja         A1
    ...
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dwj_tunes import load_all, DwjVariant, DwjSkillEffect, DwjChampion


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
    name: str
    amount: float = 0.0
    duration: int = 1
    reduceDurationAt: str = "turn-end"
    isAddedThisTurn: bool = False


@dataclass
class Actor:
    name: str
    is_boss: bool
    total_speed: int
    base_speed: int
    speed_bonus: int
    has_lore_of_steel: bool
    skill_configs: list[SkillConfig]
    # skill_effects[alias] = list of DwjSkillEffect dicts from calc_champions
    skill_effects: dict[str, list] = field(default_factory=dict)
    turn_meter: float = 0.0
    has_extra_turn: bool = False
    effects: list[Effect] = field(default_factory=list)
    stat_mod_speed: float = 0.0


@dataclass
class TurnRecord:
    turn_number: int
    boss_turn_number: int
    actor_name: str
    skill_alias: str
    skill_id: str


def speed_bonus_table(idx: int) -> float:
    """DWJ's `ep` lookup — speed-bonus index → multiplier. Best-effort guess:
    appears to be a % table keyed by a small int (rarity? or stat-bonus index).
    For now treat as pass-through with idx=0 → 0.0 multiplier. The eh rounding
    cancellation makes this table largely self-canceling for our port — the
    net effective_speed computation below uses total_speed directly.
    """
    return 0.0  # placeholder; see docs/dwj/calc_algorithm.md


def speed_buff_modifier(actor: Actor) -> float:
    """DWJ's em(actor): return (1 + buff_amount - debuff_amount) - 1 = net offset."""
    t = 1.0
    for e in actor.effects:
        if e.name == "speed-buff":
            t *= 1 + e.amount
        elif e.name == "speed-debuff":
            t -= e.amount
    return t - 1.0


def effective_speed(actor: Actor, aura: float) -> float:
    """DWJ's eh(actor, aura, buff_mod, stat_mod).

    The rounded/unrounded cancellation in DWJ's eh reconstructs pre-rounding
    'true' speed. Net: total_speed + aura_bonus + stat_mod, * (1 + buff_mod).
    """
    base = actor.base_speed
    aura_used = 0.0 if actor.is_boss else aura
    buff_mod = speed_buff_modifier(actor)
    # Net formula (see docs/dwj/calc_algorithm.md); speed_bonus table
    # cancels in rounded/unrounded pair so we just use total_speed as ground truth.
    true_speed = actor.total_speed + (aura_used / 100.0) * base + actor.stat_mod_speed
    return true_speed * (1.0 + buff_mod)


def make_clanboss(boss_speed: int, affinity: str) -> Actor:
    """DWJ's e_ factory. A1 STUN cd=0, A2 AOE2 cd=3, A3 AOE1 cd=3."""
    skills = [
        SkillConfig(alias="STUN", id="A1", priority=1, delay=0, cooldown=0),
        SkillConfig(alias="AOE2", id="A2", priority=2, delay=0, cooldown=3),
        SkillConfig(alias="AOE1", id="A3", priority=3, delay=0, cooldown=3),
    ]
    return Actor(
        name="Clanboss",
        is_boss=True,
        total_speed=boss_speed or 190,
        base_speed=0,
        speed_bonus=0,
        has_lore_of_steel=False,
        skill_configs=skills,
    )


def prepare_champion(slot, champion: DwjChampion | None = None) -> Actor:
    """DWJ's ey(champ). Filter skillConfigs to only A1 or cooldown>0 skills
    (drops A4 passive). Everything else initialized fresh.

    `champion` (optional) supplies the hero's skill definitions from
    calc_champions.json so effects can be applied.
    """
    filtered = []
    for c in slot.skill_configs:
        if c.alias == "A1" or c.cooldown > 0:
            filtered.append(SkillConfig(
                alias=c.alias, id=c.alias,
                priority=c.priority, delay=c.delay, cooldown=c.cooldown,
                current_cooldown=0,
            ))
    # Build skill_effects map {alias: [effect_dicts]} from calc_champions
    skill_effects: dict[str, list] = {}
    if champion is not None:
        for sk in champion.skills:
            effects = []
            for e in sk.effects:
                effects.append({
                    "id": e.id,
                    "amount": e.amount,
                    "turns": e.turns,
                    "champions": e.champions,
                    "enemy": e.enemy,
                    "buff": e.buff,
                    "debuff": e.debuff,
                    "condition": e.condition,
                })
            skill_effects[sk.alias] = effects
    # Special case: Genzin gets stat_mod speed=10 per DWJ source
    stat_mod = 10.0 if slot.name == "Genzin" else 0.0
    return Actor(
        name=slot.name,
        is_boss=False,
        total_speed=slot.total_speed or 0,
        base_speed=slot.base_speed or 0,
        speed_bonus=slot.speed_bonus or 0,
        has_lore_of_steel=bool(slot.has_lore_of_steel),
        skill_configs=filtered,
        skill_effects=skill_effects,
        stat_mod_speed=stat_mod,
    )


def count_boss_turns(turns: list[TurnRecord]) -> int:
    return sum(1 for t in turns if t.actor_name == "Clanboss")


# ------------------------ effect dispatcher ------------------------
# Ports DWJ's `er` handler table from chunk 824-*.js. Focus on effects that
# affect turn scheduling: tm_up, tm_down, reduce_cd, reset_cd, extra_turn,
# speedup, speeddown. Other effects are no-ops for scheduling parity.


def _resolve_targets(effect: dict, actor: Actor, actors: list[Actor]) -> list[Actor]:
    """Map effect's 'champions' / 'enemy' to the list of targets."""
    champ = effect.get("champions")
    enemy = effect.get("enemy")
    if champ == "self":
        return [actor]
    if champ == "allies":
        return [a for a in actors if not a.is_boss and not actor.is_boss and a is not actor] + ([actor] if not actor.is_boss else [])
    if champ == "all":
        return list(actors)
    if champ == "single":
        # single friendly (or self). Without a real target picker, just self.
        return [actor]
    if enemy == "all":
        return [a for a in actors if a.is_boss != actor.is_boss]
    if enemy == "single":
        # pick first hostile
        return next(
            ([a] for a in actors if a.is_boss != actor.is_boss), []
        )
    return []


def _check_condition(condition: dict | None, targets: list[Actor]) -> bool:
    """Evaluate the effect's `condition`. Supported checks:
    - {"check_target": "isBoss"} — at least one target is the boss
    - {"check_target": "!isBoss"} — no target is the boss
    """
    if not condition:
        return True
    ct = condition.get("check_target")
    if ct == "isBoss":
        return any(t.is_boss for t in targets)
    if ct == "!isBoss":
        return not any(t.is_boss for t in targets)
    # Unknown condition → default to passing; effect still fires for unsupported conditions
    return True


def _apply_tm_up(targets: list[Actor], amount: float) -> None:
    for t in targets:
        t.turn_meter = min(100.0, t.turn_meter + amount)


def _apply_tm_down(targets: list[Actor], amount: float) -> None:
    for t in targets:
        t.turn_meter = max(0.0, t.turn_meter - amount)


def _apply_reduce_cd(targets: list[Actor], amount: float, named: str | None = None) -> None:
    for t in targets:
        for c in t.skill_configs:
            if named and c.alias != named:
                continue
            if amount == -1:
                c.current_cooldown = 0
            else:
                c.current_cooldown = max(0, c.current_cooldown - int(amount))


def _apply_reset_cd(targets: list[Actor]) -> None:
    for t in targets:
        for c in t.skill_configs:
            c.current_cooldown = 0


def _apply_extra_turn(targets: list[Actor]) -> None:
    for t in targets:
        t.has_extra_turn = True


def _apply_speed_buff(targets: list[Actor], amount_pct: float, duration: int, is_debuff: bool = False) -> None:
    name = "speed-debuff" if is_debuff else "speed-buff"
    for t in targets:
        # isSingular: replace existing same-name effect
        t.effects = [e for e in t.effects if e.name != name]
        t.effects.append(Effect(
            name=name,
            amount=amount_pct / 100.0,
            duration=duration,
            reduceDurationAt="turn-end",
        ))


def apply_skill_effects(actor: Actor, skill_alias: str, actors: list[Actor]) -> None:
    """Apply the skill's effect list. Only handles effects that affect scheduling.

    This is a subset of DWJ's el()/er table — just enough to reproduce turn
    order. Damage and stat-buff effects (atkup, defup, unkillable, shield,
    block_dmg, continuous_heal, poison, hpburn, etc.) are skipped because
    they don't alter cast order in DWJ's sim.
    """
    effects = actor.skill_effects.get(skill_alias, [])
    for e in effects:
        targets = _resolve_targets(e, actor, actors)
        if not targets:
            continue
        if not _check_condition(e.get("condition"), targets):
            continue
        eff_id = e.get("id")
        amount = e.get("amount") or 0
        turns = e.get("turns") or 0
        buff = e.get("buff")
        debuff = e.get("debuff")

        # Direct id effects
        if eff_id == "reduce_cd":
            _apply_reduce_cd(targets, amount, named=e.get("reduce_cd") if isinstance(e.get("reduce_cd"), str) else None)
            continue
        if eff_id == "reset_cd":
            _apply_reset_cd(targets)
            continue
        if eff_id == "extra_turn":
            _apply_extra_turn(targets)
            continue
        if eff_id == "tm_up":
            _apply_tm_up(targets, amount)
            continue
        if eff_id == "tm_down":
            _apply_tm_down(targets, amount)
            continue

        # add_buff with sub-type
        if eff_id == "add_buff":
            if buff == "tm_up":
                _apply_tm_up(targets, amount)
            elif buff == "speedup" or buff == "speed":
                _apply_speed_buff(targets, amount, turns, is_debuff=False)
            elif buff == "reduce_cd":
                _apply_reduce_cd(targets, amount)
            # Other buffs (unkillable, block_dmg, shield, etc.) don't affect scheduling
            continue

        if eff_id == "add_debuff":
            if debuff == "tm_down":
                _apply_tm_down(targets, amount)
            elif debuff == "speeddown" or debuff == "speed":
                _apply_speed_buff(targets, amount, turns, is_debuff=True)
            # Other debuffs don't affect scheduling
            continue


def simulate(variant: DwjVariant, max_turns: int = 1000, max_boss_turns: int = 50, apply_effects: bool = True) -> list[TurnRecord]:
    dwj = load_all()
    actors = [prepare_champion(s, dwj.champion(s.name)) for s in variant.slots]
    actors.append(make_clanboss(variant.boss_speed, variant.boss_affinity))
    turns: list[TurnRecord] = []

    while count_boss_turns(turns) < max_boss_turns and len(turns) < max_turns:
        # Find next actor
        actor = next((a for a in actors if a.has_extra_turn), None)
        if actor is not None:
            actor.has_extra_turn = False
        else:
            # Tick TM until someone hits 100
            safety = 0
            while all(a.turn_meter < 100 for a in actors):
                for a in actors:
                    inc = 7.0 * effective_speed(a, variant.speed_aura) / 100.0
                    a.turn_meter = round(a.turn_meter + inc, 12)
                safety += 1
                if safety > 10000:
                    raise RuntimeError("TM tick loop failed to terminate")
            # Pick fastest (first with max TM)
            max_tm = max(a.turn_meter for a in actors)
            actor = next(a for a in actors if a.turn_meter == max_tm)

        # Decrement turn-start effects, remove expired
        for e in actor.effects:
            if e.reduceDurationAt == "turn-start":
                e.duration -= 1
        actor.effects = [e for e in actor.effects if e.duration > 0]

        actor.turn_meter = 0.0

        # Pick skill: highest priority number with cd=0 AND delay=0
        sorted_cfg = sorted(actor.skill_configs, key=lambda c: -c.priority)
        skill = next(
            (c for c in sorted_cfg if c.current_cooldown == 0 and c.delay == 0),
            None,
        )
        if skill is None:
            raise RuntimeError(
                f"No castable skill for {actor.name} — configs={actor.skill_configs}"
            )

        # Record turn
        boss_tn = count_boss_turns(turns) + (0 if not actor.is_boss and len(turns) > 0 else (1 if actor.is_boss else 0))
        turn_number = len(turns) + 1
        turns.append(TurnRecord(
            turn_number=turn_number,
            boss_turn_number=boss_tn,
            actor_name=actor.name,
            skill_alias=skill.alias,
            skill_id=skill.id,
        ))

        # Apply cast cooldown + decrement all delays/cds
        skill.current_cooldown = skill.cooldown
        for c in actor.skill_configs:
            c.delay = max(0, c.delay - 1)
            c.current_cooldown = max(0, c.current_cooldown - 1)

        # Apply skill effects that affect scheduling
        if apply_effects and not actor.is_boss:
            apply_skill_effects(actor, skill.alias, actors)

        # Decrement turn-end effects, remove expired
        for e in actor.effects:
            if e.reduceDurationAt == "turn-end":
                e.duration -= 1
        actor.effects = [e for e in actor.effects if e.duration > 0]

    return turns


def format_turns(turns: list[TurnRecord]) -> str:
    lines = []
    for t in turns:
        lines.append(f"  Turn {t.turn_number:>3} (boss tn {t.boss_turn_number:>2}): {t.actor_name:<18} {t.skill_alias}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", help="calc variant hash")
    ap.add_argument("--slug", help="DWJ tune slug (e.g. 'myth-eater')")
    ap.add_argument("--variant", help="variant name (e.g. 'Ninja UNM')")
    ap.add_argument("--turns", type=int, default=25, help="max CB turns to simulate")
    args = ap.parse_args()

    dwj = load_all()
    variant: Optional[DwjVariant] = None
    if args.hash:
        variant = dwj.variants_by_hash.get(args.hash)
    elif args.slug:
        if args.variant:
            variant = dwj.find_variant(slug=args.slug, variant_name=args.variant)
        else:
            tune = dwj.tunes.get(args.slug)
            if tune and tune.variants:
                variant = tune.variants[0]
    if variant is None:
        sys.exit("need --hash or --slug (+ --variant)")

    print(f"=== sim: {variant.slug} [{variant.name}]  boss SPD={variant.boss_speed}  aura={variant.speed_aura} ===")
    for s in variant.slots:
        cfg = ", ".join(f"{c.alias}(p{c.priority} d{c.delay} cd{c.cooldown})" for c in s.skill_configs if c.alias != "A4")
        print(f"  slot{s.index} {s.name:<18} SPD={s.total_speed}  base={s.base_speed}  LoS={s.has_lore_of_steel}  {cfg}")
    print()

    turns = simulate(variant, max_boss_turns=args.turns)
    print(format_turns(turns))
    print()
    print(f"total turns: {len(turns)}  boss turns: {count_boss_turns(turns)}")


if __name__ == "__main__":
    main()
