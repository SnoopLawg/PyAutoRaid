# Battle Logging Pipeline & IL2CPP Internals

Deep reference for the BepInEx mod's battle telemetry system. For high-level architecture, see CLAUDE.md.

## Battle State Machine

State lives in static fields on `RaidAutomationPlugin`:

- `_battleActive` — toggled by Harmony `BattleHook_ProcessStartBattle` / `BattleHook_ProcessEndBattle`. `PollBattleState` ALSO confirms activation via scene-name + BattleHUD GameObject presence (scene name alone is insufficient — e.g. `GoldArena` stays set on the opponent-select screen).
- `_battleCommandCount` — increments ONLY on `ProcessStartTurn` hook. True turn count.
- `_pollCount` — increments per Update() poll (every 0.5s) while `_battleActive`. Distinct from turns; do not confuse.
- `_battleLog` — `List<string>` of JSON entry strings, capped at 2000. Cleared on each `battle_start`. Entry shapes: `{"event":"battle_start|battle_end",...}`, `{"turn":N,"active_hero":id,"ptr":1}`, `{"poll":N,"turn":T,"scene":...,"heroes":[...]}`, `{"diag":"ctx_props",...}`.

## BattleProcessor Schema (captured from live diag 2026-04-13)

- `BattleProcessor` get_* = `[Settings, Context, Setup, State, Statistics]`
- `BattleSetup` = `[IsAutoBattle, IsBackgroundBattle, Stage, MaxTurnsInBattle]` — NO heroes here
- `BattleState` = `[PlayerTeam, EnemyTeam, SkipViewData]` — **heroes live under the teams**
- `BattleContext` = `[DecisionMaker, MaxRecursionDepth, CurrentRegionTypeId, CurrentAreaTypeId, ActiveHeroId, ActiveUserId, StageId]` — metadata only
- Prior code navigated `Processor.Context.Setup.Heroes` which never returned — Setup/State hang off the Processor directly, not Context.

## ReadBattleHeroesIL2CPP Path (verified 2026-04-13)

`BattleProcessor → State → {PlayerTeam, EnemyTeam} → HeroesWithGuardian[i]` yields each `BattleHero`. The accessor is `get_HeroesWithGuardian` (NOT `Heroes`/`Members`/`Units`).

### BattleHero Properties Extracted Per Turn
- Identity: `Id` (battle slot index), `BaseTypeId` (matches `HeroType.Id` in `skills_db.json`)
- HP: `MaxHealth`, `DestroyedHealth` (current HP = max - destroyed). Prefer computing from max/destroyed over `HealthPerc`.
- TM: `Stamina` (0–100 scale after conversion)
- Bool flags: `IsUnkillable`, `IsBoss`, `CanAttack`, `MustSkipTurn`
- Active status: 27 boolean flag getters mapped to short labels (`stun`, `freeze`, `sleep`, `provoke`, `invincible`, `block_debuff`, `taunt`, `invis`, `dying`, `dead`, `block_heal`, `nullifier`, `petrify`, `ss`, `ss_simple`, `ss_reflect`, `banish`, `grab`, `devour`, `entangle`, `absent`, `enfeeble`, `no_tm_tick`, `rages`, `xform`, `act_blk`, `pass_blk`). Only TRUE flags emitted.
- Skills: `HeroSkills` collection, each as `{t:<skill_type_id>, rdy:<bool>, start?:true, same:<count>, blk?:true}`. Skill `rdy:true→false` between turns = hero used it.

## Fixed-Point Encoding (critical)

Raid's `Fixed` type is **32.32** (raw value = display × 2³²), NOT 16.16. Correct decode: `value = raw >> 32`. Using 16.16 gives ~65000× inflated numbers. Affects ALL Fixed reads (HP, Stamina/TM, damage, etc.).

Example: Maneater HP raw=173,351,751,876,938 → `>> 32` = 40,363 HP.

## Per-Turn Snapshot Cadence

Emits full `{poll,turn,scene,heroes:[...]}` once per turn change (via `_lastStatsLogTurn`) and every ~5s during long turns. `BattleHook_ProcessEndTurn` nudges `_lastStatsLogTurn = -1` to force-emit next poll.

## Harmony Patching Reality

- `ProcessStartTurn` / `ProcessEndTurn` / `ProcessStartBattle` / `ProcessEndBattle` — fire reliably, authoritative turn counter.
- `ProcessStartRound` / `ProcessEndRound` / `ApplySkillCommand` — report patched but postfixes don't fire in IL2CPP builds (BepInEx 6.0.0-be limitation). Infer rounds from turn counts, skill-use from `rdy` cooldown deltas.

## MessageBox Dismissal

Buttons live at `UIManager/Canvas (Ui Root)/MessageBoxes/MessageBox/BoxContainer/Box/Content/Buttons_h/{0|1}`. Dismiss via `/context-call?path=<button_path>&method=OnClick` (NOT `/click` or `/dismiss`).

## Where Buffs/Debuffs Live on BattleHero (verified 2026-04-13)

| Field | Offset | Status |
|-------|--------|--------|
| `AppliedEffectsByHeroes` | @0x108 | ALWAYS null — tracks effects BY hero, not ON |
| `_appliedStatModifications` | @0xB0 | Also null |
| `PhaseEffects._effectsByPhaseIndex` | @0xF0→0x10 | Real storage for active effects (UK, BD, Poison, etc.) — array of lists by skill phase |
| `StatImpactByEffects._statsImpactByEffect` | @0xA0→0x18 | Stat-modifying effects (DEF Down, ATK Down, Weaken) |
| `Bonuses:BattleBonuses` | @0xC8 | Pre-aggregated stat bonuses (Leader, Arena, Arts) — NOT dynamic buffs |
| `_heroState:HeroState` | @0xC0 | 30 boolean flags (same as `Is*` getters) |

.NET `Dictionary<K,V>` layout in IL2CPP: `_entries:Entry[]@0x18`, `_count:int@0x20`.

## Turn-Counter Semantics

- `_battleCommandCount` (mod-side): fires on every `ProcessStartTurn` (player + boss + passive ticks). Not the in-game UI number.
- In-game "Turn X" = `sum(player_hero.TurnCount)`. Each `BattleHero.TurnCount` @0xE8 increments per actual hero turn. Boss.TurnCount counts boss rounds separately.
- Speed-tune / turn-order: use `active_hero` field on each turn hook.

## Direct Active-Effect Tracking (landed 2026-04-13)

Two per-snapshot fields in every `heroes[i]` entry:

### `mods: [{id, k, v}, ...]`
From `StatImpactByEffects._statsImpactByEffect` dict. `id` = source effect_id, `k` = StatKindId (1=HP, 2=ATK, 3=DEF, 4=SPD, 5=RES, 6=ACC, 7=CR, 8=CD), `v` = signed value (Fixed >> 32; negative = debuff).

Dict-entry stride: **0x28** (hash:4, next:4, key:4, pad:4, value tuple:24). Tuple layout: `Fixed:8 @0x10`, `StatKindId:4 @0x18`, `EffectContext:8 @0x20`.

Examples: `id:151 k:3 v:-912` = DEF Down. `id:131 k:2 v:-3497` = Dec ATK. `id:620042 k:2 v:+2530` = Ninja self-ATK buff.

### `abs: {"<effect_kind>": <damage>, ...}`
From `AbsorbedDamageByEffectKindId:Dictionary<int, Fixed> @0x68`. Cumulative damage absorbed per effect-kind. Dict-entry stride: **0x18**.

Example: `Maneater abs={"2004": 21645}` = 21,645 damage absorbed by continuous-heal/shield family.

### What Doesn't Work
- `AppliedEffectsByHeroes @0x108` — always null
- `Challenges:Dictionary @0xE0` — count > 0 but no populated entries found
- `Counters:Dict<int, Fixed> @0x138` — probably mastery stack counter, NOT UK state
- Pure non-stat buffs (UK, BD when applied but not triggered) don't appear in `StatImpactByEffects`

## UK/BD Tracking — Direct Observation Only

Don't infer UK/BD windows from skill timing. Use verified sources only:
- `skills_db.json` entries that actually exist
- `AbsorbedDamageByEffectKindId` for retrospective absorption
- `uk_saved` / `block_damage` HeroState flags for triggered state
- Survival signatures (`hp_cur` reaching exactly 1) for UK-clamp detection

Key correction: Demytha A2 places **Block Damage**, NOT Unkillable.

## Unkillable Flag Behavior

`IsUnkillable` only returns true when hero is *at 0 HP being prevented from dying* — NOT when UK buff is applied but untriggered. Same for `IsInvincible` (Block Damage). The coverage-gap detector in the analyzer will over-report WIPE RISK. Trust outcomes (`dead` flag transitions + `hp_cur` trace) over moment-of-hit flag state.

## Schema Diags (auto-fire once per battle)

- `hero_schema` — BattleHero class dump
- `effect_schema` — EffectType schema (from PhaseEffects)
- `stat_impact_schema` — StatImpactByEffects tuple layout (confirmed stride 0x28)
- `challenge_schema` — Challenges dict (no populated entries in practice)
