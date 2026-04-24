# DeadwoodJedi calculator algorithm (reverse-engineered)

Sourced from minified JS chunk `/_next/static/chunks/824-25a04abfc26efff9.js` (April 2026). Complete extraction in `probe/extracted/`.

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
        actor = max(actors, key=turn_meter)  # ties broken by actor array index (earliest wins)

    # Decrement turn-start effects, remove expired
    for e in actor.effects:
        if e.reduceDurationAt == "turn-start": e.duration -= 1
    actor.effects = [e for e in actor.effects if e.duration > 0]

    actor.turn_meter = 0

    # Pick skill: HIGHEST priority NUMBER with cd=0 AND delay=0
    skills_by_pri_desc = sorted(actor.skillConfigs, key=lambda c: -c.priority)
    skill = first c in skills_by_pri_desc where c.current_cooldown == 0 and c.delay == 0

    record turn

    skill.current_cooldown = skill.cooldown
    for c in actor.skillConfigs: c.delay = max(0, c.delay - 1)
    for c in actor.skillConfigs: c.current_cooldown = max(0, c.current_cooldown - 1)

    # Apply effects via el() → see below
    el(actor, skill, all_actors, isRetaliation=false, turn_record)

    # Decrement turn-end effects, remove expired
```

## Priority convention (opposite of in-game UI)

**In DWJ calc, higher priority NUMBER = fires FIRST.** The skills are sorted descending by priority; the first with `cd=0 AND delay=0` is cast.

(Contrast Raid's in-game preset UI where priority 1 = highest rank.)

## Effect dispatcher chain `el` → `ei` → `er`/`ea`

```
el(actor, skill, all_actors, isRetaliation, turn_record):
    Run start_of_turn passive on actor (if not retaliation)
    Run current skill via es()
    Run end_of_turn passive on actor
    Run `always` passives on every actor
    If actor is hostile: trigger `when_attacked` passives on hostile side
    Hardcoded leader-aura tm_up: Foli (+50% to self on A4 cd 3),
                                  Supreme Galek (extra_turn on A4 cd 4)
```

`es(skill, context)` iterates `skill.effect[]` and routes each entry via `ei`:

```
ei = {
    add_debuff: effect => {
        # ONLY fires if actor.id === "champion-cb" (i.e. CB is the caster).
        # PLAYER CHAMPION DEBUFF EFFECTS ARE NO-OPS in DWJ's sim.
        # This is because DWJ's sim only models scheduling, not DoT damage.
        handler = ea[effect.debuff]
        targets = effect.enemy == "all" ? all_hostiles : [hostiles[0]]
        if handler AND no condition AND actor is clanboss: handler(...)
    },
    add_buff: effect => {
        handler = er[effect.buff]
        targets by effect.champions:
            "allies" = friendlies + self
            "self" = [actor]
            "notself" = friendlies only
            "single" = [friendlies[0]]
            "highest_tm" = [friendly with highest TM]
        if handler AND (no condition OR condition.check_target === "isBoss"):
            handler(...)
        else if condition is an array of sub-conditions:
            iterate each; handle check_enemy, check_target affinity, buff_added, check_buff
    }
}
```

### Key implication

**`condition: {check_target: "isBoss"}` always fires** in DWJ's sim because the boss is the only hostile. We don't need to check whether any specific target is the boss — the effect just fires.

**`condition: {check_target: "!isBoss"}` NEVER fires** in DWJ's sim — only-boss hostile means "!isBoss" is always false.

This is why my earlier condition check was too strict; self-buffs like Ninja A1's +15% TM (conditioned on attacking boss) weren't firing.

## Effective speed — `eh(actor, aura=0, buff_mod=0, stat_mod=0)`

```
l = ep[speed_bonus]   # lookup: 0->0; 5->perception; 12->speed_set; etc.
true_speed = r - i - round(i*l) - (LoS? round(i*l*0.15):0)
             + i + i*l + (LoS? i*l*0.15:0)
             + aura/100 * base_speed + stat_mod_speed
effective_speed = true_speed * (1 + buff_mod)
```

The rounded/unrounded cancellation reconstructs the pre-rounding "true" speed, so net = `total_speed + aura/100*base + stat_mod` times buff multiplier.

## Speed buff/debuff modifier — `em(actor)`

```
t = 1
if actor has "speed-buff" effect: t *= 1 + effect.amount   # amount is decimal fraction
if actor has "speed-debuff" effect: t -= effect.amount
return t - 1
```

## Effect amount computation — `V(actor, effect, amount)`

```
V(e, t, n) = {
    a = e.skills.find(x => x.passive?.trigger === "add_buff")
    r = a?.effect.find(x => x.buff === t.buff)
    return a && r ? n * (1 + r.amount/100) : n
}
```

If the actor has a passive `add_buff` trigger that matches the current buff type, multiply amount by that passive's amount+100. Otherwise return amount unchanged.

Used by `tm_up` handler to scale the amount (e.g. a passive enhancing TM fills).

## Buff-adder — `G(all, target, caster, new_effect, turn)`

```
G(all, target, caster, new_effect, turn):
    existing_idx = target.effects.findIndex(e => e.name === new_effect.name)
    if existing_idx === -1 OR new_effect.isSingular === false:
        if target.effects.length < 10:
            target.effects.push(new_effect)
            q(all, target, new_effect, caster, turn)
    else:
        existing = target.effects[existing_idx]
        if new_effect.amount > existing.amount:
            target.effects.splice(existing_idx, 1)
            target.effects.push(new_effect)
            q(...)
        elif new_effect.amount === existing.amount AND existing.duration < new_effect.duration:
            existing.isAddedThisTurn = new_effect.isAddedThisTurn
            existing.duration = max(existing.duration, new_effect.duration)
            q(...)
```

**Max 10 effects per target.** Singular effects replace lower-amount / extend-duration.

## Post-buff hook — `q(all, target, new_effect, caster, turn)`

```
q(all, target, new_effect, caster, turn):
    # Valkyrie auto-TM on any buff placement
    v = hostile_of(all, target).find(x => x.name === "Valkyrie")
    if v: v.turn_meter += 10

    # Razelvarg self-speed-buff SPD stacking
    r = all.find(x => x.name === "Razelvarg")
    if r AND new_effect.name === "speed-buff" AND caster === r AND r.stat_modifiers.speed < 100:
        r.stat_modifiers.speed += 5

    # Track speed-buff count on turn record
    if new_effect.name === "speed-buff" AND !target is champion:
        turn.processed_effects.speedbuff += 1
```

**Scheduler-affecting hardcoded champion reactions**:
- **Valkyrie** passive: +10 TM whenever ANY ally gets a buff placed
- **Razelvarg** passive: +5 SPD when he gives himself a speed buff (stacks to 100 max)

## Clanboss factory — `e_(config)`

- Name: "Clanboss", id: "champion-cb"
- Speed: `config.clanboss.speed || 190`
- Base speed: 0 (no lore of steel / aura applies)
- Skills:
  - A1 "Crushing Force" (STUN): cd 0, effect `{add_debuff turns:1 enemy:single debuff:stun}`
  - A2 (AOE2): cd 3. Affinity-dependent:
    - void: "Dark Nova" with empty effect list
    - spirit: another name with effect
  - A3 (AOE1): cd 3. Also affinity-dependent:
    - void: `{add_debuff turns:2 enemy:all amount:2.5 debuff:poison}`
    - spirit: `{add_buff turns:2 champions:self amount:25 buff:atkup}`
- skillConfigs: A1 p1 d0 cd0, A2 p2 d0 cd3, A3 p3 d0 cd3

## Champion preparation — `ey(champ)`

- turn_meter = 0, has_extra_turn = false, effects = []
- skillConfigs = original.filter(c => c.id === "A1" OR c.cooldown > 0)  # drops A4 passive w/ cd 0
- stat_modifiers zeroed; `speed: 10` for Genzin specifically

## Er handler table (30+ effect types)

Scheduler-affecting:
- **tm_up**: `target.turn_meter += V(actor, effect, amount)`
- **reduce_cd**: per skillConfig with `cd_not_resettable` flag check; if amount===-1 clear all, else subtract amount (or only on `reduce_cd: skill_name` match)
- **reset_cd**: set all skillConfigs.current_cooldown = 0
- **extra_turn**: set target.has_extra_turn = true
- **speedup**: G(all, target, actor, {name:"speed-buff", amount:n/100, duration:turns, reduceDurationAt:"turn-end", isSingular:true})

Non-scheduler (we skip for parity purposes):
- atkup, defup, accup, resup, crit_rate_up, crit_dmg_up, continuous_heal, shield, strengthen, stoneskin, fortify, unkillable, block_dmg, block_debuff, taunt, counter_atk, allyatk, allyprotect, reflect, magma_shield, poison_cloud, pveil, intercept, rod (ring of destruction), shatter, str, remove_debuff, reduce_debuff, extend_buff

## Ea handler table (debuffs, clanboss-only)

add_debuff handlers fire ONLY when actor.id === "champion-cb". Each filters targets with `x.id !== "champion-cb"` (exclude boss) and checks `!et(target)` (not immune). Handlers: acc_down, resdown, atkdown, defdown, hpburn, poison, poison_sensitivity, stun, freeze, sleep, block_buffs, block_cooldown_skills, provoke, true_fear, fear, weaken, decrease_attack, decrease_speed, etc.

## Speed-bonus table — `ep[speed_bonus]`

```
ep = {
    0: 0,
    5: ef.perception,
    10: 2*ef.perception,
    12: ef.speed_set,
    15: 3*ef.perception,
    17: ef.speed_set + ef.perception,
    18: ef.swift_parry,
    22: ef.speed_set + 2*ef.perception,
    24: 2*ef.speed_set,
    36: 3*ef.speed_set,
    48: ef.righteous,
    ...
}
```

Used when the user provides "speed_bonus" as an index. For calc_tunes slots with `speed_bonus: 0`, `ep[0] = 0` so no bonus. For other speed_bonus values it sums set-bonus multipliers. `ef` holds per-set multipliers (from CDN `/api/cb/speed_bonuses`).

## Condition parsing — nested cases

The `ei.add_buff` handler supports condition AS AN ARRAY:
```js
if (condition not undefined AND condition is array) {
    condition.forEach(c => {
        if (c.check_enemy && hostile.effects.has(c.check_enemy)) handler(...)
        if (c.check_target === affinity string) handler(...)
        if (c.type === "buff_added" && c.target === "enemy") handler(...)
        if (c.type === "check_buff" && c.target === "self" && actor.effects.has(c.buff)) handler(...)
    })
}
```

Unknown conditions default to "don't fire", not "fire". This is stricter than my first port.

## Port notes (what Python needs to do)

1. **Turn scheduler**: as described, tick TMs until one hits 100, pick max (first tie-break).
2. **Skill select**: DESC priority, first with cd=0 AND delay=0.
3. **Effect routing**:
   - `add_buff`: target via `champions` enum; apply if no condition OR condition.check_target === "isBoss" (never try the non-existent "!isBoss" path).
   - `add_debuff`: SKIP if actor isn't clanboss. Target via `enemy` enum; filter out boss from targets; filter immune actors.
4. **Scheduler-affecting effect handlers**: tm_up, reduce_cd, reset_cd, extra_turn, speedup, speeddown. Non-scheduler effects are no-ops in scheduling sim.
5. **Hardcoded reactions**: Valkyrie +10 TM on any buff place, Razelvarg +5 SPD on self speed-buff (cap 100). Passive triggers (start_of_turn, end_of_turn, always, when_attacked) for future expansion.
