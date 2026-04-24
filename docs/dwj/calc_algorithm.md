# DeadwoodJedi calculator algorithm (reverse-engineered)

Sourced from minified JS chunk `/_next/static/chunks/824-25a04abfc26efff9.js` (April 2026).

This doc is the spec we match against in `tools/calc_parity_sim.py`.

## Main simulation loop — `ek(config, champions)`

```
actors = [prepare(champ) for champ in champions] + [make_clanboss(config)]
turns = []

until count_boss_turns(turns) >= 50 or len(turns) >= 1000:
    # Find next actor
    actor = first actor with has_extra_turn=True
    if actor:
        actor.has_extra_turn = False
    else:
        # Tick all TMs together until someone hits 100
        while all(a.turn_meter < 100 for a in actors):
            for a in actors:
                a.turn_meter = round(
                    a.turn_meter + 7 * effective_speed(a) / 100,
                    12 decimal places
                )
        actor = max(actors, key=turn_meter)

    # Decrement turn-start effects, remove expired
    for e in actor.effects:
        if e.reduceDurationAt == "turn-start": e.duration -= 1
    actor.effects = [e for e in actor.effects if e.duration > 0]

    actor.turn_meter = 0

    # Pick skill: HIGHEST priority NUMBER with cd=0 AND delay=0
    # (sort DESC by priority, find first castable)
    skills_by_pri_desc = sorted(actor.skillConfigs, key=lambda c: -c.priority)
    skill = first c in skills_by_pri_desc where c.current_cooldown == 0 and c.delay == 0
    if skill is None: raise "no castable skill"

    record turn {turn_number, actor, skill, ...}

    skill.current_cooldown = skill.cooldown
    for c in actor.skillConfigs: c.delay = max(0, c.delay - 1)
    for c in actor.skillConfigs: c.current_cooldown = max(0, c.current_cooldown - 1)

    # Apply effects (el function)
    apply_skill_effects(actor, skill, all_actors, turn)

    # Decrement turn-end effects, remove expired
    for e in actor.effects:
        if e.reduceDurationAt == "turn-end": e.duration -= 1
    actor.effects = [e for e in actor.effects if e.duration > 0]
```

## Priority convention (important — opposite of Raid's in-game UI)

**In DWJ calc, higher priority NUMBER = fires FIRST.** The skills are sorted descending by priority and the first with `cd=0 AND delay=0` is cast.

- Maneater skillConfigs: A1 p1 d0 cd0, A2 p2 d0 cd3, A3 p3 d1 cd5
- Turn 1: A3 has priority 3 (highest) but delay=1 → skip. A2 priority 2, cd=0, delay=0 → cast. A2 now on cd=3.
- Turn 2: A3 priority 3, cd=0, delay=0 (decremented) → cast. A3 now on cd=5.
- Turn 3: A3 cd=4, A2 cd=2, A1 priority 1 cd=0 delay=0 → cast A1.
- ...

(Contrast Raid's in-game preset UI where priority 1 is the HIGHEST rank — DWJ's calc is inverted.)

## Effective speed — `eh(actor, aura=0, buff_mod=0, stat_mod=0)`

```
true_speed = (total_speed - base_speed - round(base*bonus) - (LoS? round(base*bonus*0.15):0)
              + base_speed + base*bonus + (LoS? base*bonus*0.15:0)
              + aura/100 * base_speed
              + stat_mod)
effective_speed = true_speed * (1 + buff_mod)
```

The rounded/unrounded cancellation reconstructs the pre-rounding (true) speed. Net result equals `total_speed + aura_bonus + stat_mod`, buff-multiplied.

## Speed buff/debuff modifier — `em(actor)`

```
t = 1
if actor has "speed-buff" effect: t *= 1 + effect.amount   # amount is decimal fraction
if actor has "speed-debuff" effect: t -= effect.amount
return t - 1  # offset from 1.0
```

So net buff: +30% SPD = `em` returns 0.30 → effective_speed *= 1.30.

## TM tick granularity

7 * speed / 100 per tick. All actors tick simultaneously; first to ≥100 acts. Round TMs to 12 decimal places to avoid float drift.

## Extra turn

`actor.has_extra_turn = True` → that actor acts next without needing to tick TM. After the turn, `has_extra_turn` is cleared. Used for skills like "Grants an Extra Turn".

## Clanboss skills (all variants)

- A1 "Crushing Force" (STUN): CD 0, effect `{id: "add_debuff", turns:1, enemy:"single", debuff:"stun"}`
- A2 (AOE2): CD 3, effect varies by affinity (void/spirit/force/magic/arcane)
- A3 (AOE1): CD 3, effect varies by affinity

Priority: A1=1, A2=2, A3=3 (same sort DESC convention → A3 fires first when ready).

## Champion skill preparation — `ey(champ)`

- `turn_meter = 0`
- `has_extra_turn = false`
- `effects = []`
- `skillConfigs.filter(c => c.id === "A1" || c.cooldown > 0)` — drops A4 passive (CD 0) but keeps A1
- `stat_modifiers`: zeroed struct (speed=10 for "Genzin" special case)

## What's still unknown

- `el(actor, skill, actors, isRetaliation, turn)` — full effects dispatcher. Handles `add_buff`, `add_debuff`, `tm_up`, `reduce_cd`, `extend_buff`, `destroy_buff`, passive triggers (`start_of_turn`, `end_of_turn`, `always`), condition evaluation (`check_target`, `isBoss`, counter comparisons). Large block in the same JS chunk starting at `el=(e,t,n,a,r)=>`. Port separately.
- `ep[speed_bonus]` — lookup table for `speed_bonus` index → multiplier. Used in `eh`. Not yet extracted.

## Port notes

- `tools/calc_parity_sim.py` will implement the main loop and skill-pick logic. Effects dispatcher is deferred; sim records cast-order ground truth without applying effects (still captures priorities, CDs, delays correctly).
- To validate: load a DWJ calc variant's `pageProps.champions` + `clanboss` + `speed_aura`, run sim, compare to Chrome-rendered turn list. 95%+ match expected before effects are modeled.
