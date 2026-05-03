# PyAutoRaid Roadmap

Single source of truth for what's done, what's in flight, and what's next.
Sourced from the **Goals & Scope** section of `CLAUDE.md` (which lists every
location, every system, every non-negotiable). This file tracks completion
status and prioritizes the next work.

> **Rule of thumb**: a feature is "done" only when (a) the CLI works, (b) the
> sim/optimizer matches game behavior to its calibration target, and (c) the
> values are sourced from the game (live mod or static IL2CPP dump), not
> back-solved.

## Status legend

- ✅ **Done** — game-truth values, calibration verified, scalable
- 🟡 **Partial** — works for the common case; edge cases or other content not yet covered
- 🔴 **Open** — not started or stalled

## Overall progress (2026-05-02)

| Area | Status | Notes |
|---|---|---|
| Mod API + Battle Logger | ✅ | Per-tick capture; HTTP API on :6790; covers all hooks needed for derivation |
| Hero/Skill Index | ✅ | 1120/1121 heroes have skill profiles (full game). Static export refresh-able via `tools/refresh_static_data.py` |
| Computed Stats | ✅ | `/hero-computed-stats` returns the GAME's Total-Stats column breakdown; `cb_optimizer.calc_stats` sums the columns directly |
| CB Sim — DEF formula | ✅ | Literal formula extracted (`0.85`, `1500`, `Fixed.One`, `Fixed.Zero`, `−0.02`); +0.61% calibration on Magic UNM |
| CB Sim — other mechanics | 🟡 | Many still hand-coded or empirical (see CB Sim breakdown below) |
| Artifact Optimizer (CB) | ✅ | `cb_optimizer.py` + `global_gear_solver.py` work for owned + synthetic heroes |
| Artifact Optimizer (other locations) | 🔴 | No targets defined for Dragon, Spider, FK, Doom Tower, etc. |
| Mastery System (read) | ✅ | Stat-bonus masteries auto-loaded from static; conditional masteries hand-coded |
| Mastery System (apply) | 🟡 | Per-hero apply works (`/open-mastery`); no `/apply-build` batch endpoint |
| Auto-Run — CB | ✅ | `cb_run.py`, `cb_daily.py` |
| Auto-Run — Dungeons | 🟡 | `tools/dungeon_run.py` exists; per-stage logic incomplete |
| Auto-Run — other locations | 🔴 | Faction Wars, Doom Tower, Hydra, Chimera, Cursed City, Siege, Grim Forest |
| Sell rules engine | 🟡 | `tools/sell_rules.py` + `tools/sell.py preview/execute/history`; per-hero per-area "needed-for-build" check missing |
| Smart farming recommendations | 🔴 | Drop tables in `data/static/drops.json`; recommender not built |
| Demon Lord (CB) sim — game-truth methodology | ✅ | DEF formula via Il2CppDumper + capstone; full pipeline documented in `CLAUDE.md` |
| Hydra / Chimera sim | 🔴 | Same shape as CB sim could apply; haven't been targeted yet |
| Doom Tower sim | 🔴 | Per-floor logic, secret rooms, special modifiers; nothing yet |

---

## CB Sim — current breakdown of "what's game-truth vs hand-coded"

This is the section the user wants to keep iterating on. Every line is a
candidate for the same extraction process used on `DamageReductionByDefence`.

### ✅ Fully extracted from `GameAssembly.dll`

- **DEF mitigation function** (`tools/cb_constants.py::def_mitigation_factor`)
  - Source: `SharedModel.Battle.Core.DamageCalculator.DamageReductionByDefence`
  - Formula: `factor = 1 − 0.85 × (1 − exp((Defence − acc_mod) × (1 + defence_modifier) × (−1/1500)))`
  - Verified against 247 captured `(t_def, factor)` tuples — <0.01% error
  - Mod hook chain: `BattleHook_DefReduction_Prefix` + `BattleHook_FixedSubtraction` + `BattleHook_DefReduction` postfix

### ✅ Game-truth values from static export (no decompile needed)

- **HP Burn `StackCount: 1`** (singular per target) — `data/static/effects.json` Id 470
- **Boss UNM HP, base ATK/DEF/SPD** — `data/static/cb_bosses.json` + `data/static/alliance_bosses.json` + tick log capture (`p_atk=6993`, `t_def=1520` at base)
- **CB skill multipliers** (AoE1=4×ATK, AoE2=2+1×ATK, Stun=0.2×TRG_B_HP) — `data/static/skills_all.json` for skill IDs 222603/222802/222601
- **Affinity coefficients** (`ElementDisadvantageCoef=−0.2`, `CrushingHitCoef=0.3`, `GlancingHitCoef=−0.3`, `CriticalHitChanceAdvantage=0.15`, etc.) — `data/static/gameplay.json`
- **NonIncreaseable buffs** (UK / BD / etc. don't extend) — `data/static/non_increaseable_effects.json`
- **Gathering Fury formula** (T10–T19: `0.75 × (turn − 9)`; T20+: cliff; T50: enrage) — extracted from `data/static/skills_all.json` skill 222904

### 🟡 Hand-coded / empirical — candidates for the same extraction treatment

| Mechanic | Where it lives now | Extraction target |
|---|---|---|
| **Hit-type damage factors** (Normal/Crushing/Critical/Glancing damage modifiers) | `cb_constants.py` constants + `cb_sim.py::_calc_skill_damage` crit_mult logic | `DamageCalculator.HitTypeBonus(BattleHero, HitType)` and `DamageCalculator.CalculateHitType` — same dump+disassemble pipeline |
| **DamageReductionByStatusEffects** (Weaken / Strengthen / Inc Damage Taken) | Hand-coded multipliers (`wk = 1.25 if has_weaken`) | `DamageCalculator.DamageReductionByStatusEffects` — already located in dump.cs |
| **Stoneskin / Petrification damage factors** | Geomancer Stoneguard hand-coded; petrification not modeled | `StoneSkinDamageFactor`, `PetrificationDamageFactor` — visible in dump.cs |
| **Newbie defence damage factor** (low-level account protection) | Not modeled (we're past it) | `NewbieDefenceDamageFactor` — likely returns 1.0 for level-60+ |
| **DoT cap formula** (75K HP Burn, 50K Poison) | Hardcoded constants in `cb_constants.py::FA_CAP_*` | Find the cap-applying function (likely `ApplyDamageCap` or in `EffectKindGroup` rules) |
| **Hero per-skill `IgnoreDefence`** values | Inferred from skill descriptions (Ninja A3 = 50%, OB A2 = 30%, etc.) | Captured live as additional `defence_modifier` variants (–0.32, –0.52, –1.0 observed); resolve which skill produces which value |
| **Damage cap chain** (Force-Affinity caps, infinite-HP-mode caps) | Empirical observation, FA_CAP_BIG/MEDIUM/SMALL | Find the runtime cap-resolver — likely in `CalculateDamage` or `DamageContext` post-processing |
| **CB stun damage formula** | `0.2 × TRG_B_HP` hand-mapped from skill 222601's `MultiplierFormula` | Already from static; verify formula evaluator handles `TRG_B_HP` token correctly |
| **Per-hero passive damage models** (Sicia burn-density, Ninja Escalation, Geomancer reflect, etc.) | Hand-coded in `cb_sim.py` | If each maps to a SkillEffect with `Group=Passive`, the loop scheduler in `BattleHero.Process` could be hooked to capture per-passive damage events |

### 🔴 Open — known but uninvestigated

- **Heal cap calculation** (capped at some fraction of MAX_HP per cast)
- **Counterattack damage** (CounterattackModifier=−0.25 from gameplay.json; not yet wired in)
- **Shield refresh-vs-stack rules** (Demytha A1 multi-hit shield) — handled per-hero in cb_sim, not from a shared rule
- **Buff/debuff overflow** at `MAX_DEBUFF_SLOTS` — sim has 10, game's true cap unknown
- **Boss skill cycle priority** (which boss skill on which CB turn) — sim cycles aoe1/aoe2/stun by turn-mod, but live game might use AI

### Next-up extraction targets in priority order

1. **`HitTypeBonus(BattleHero, HitType)`** — biggest open variance source. Determines per-hit damage when sim rolls a hit type. Same pipeline as DEF formula.
2. **`DamageReductionByStatusEffects`** — Weaken / Strengthen / dec_atk should land in here. Will let us drop the hand-coded `wk = 1.25` and friends.
3. **DoT cap formula** — resolves `FA_CAP_*` constants which are currently empirical.
4. **`StoneSkinDamageFactor` / `PetrificationDamageFactor`** — replaces Geomancer Stoneguard's hand-rolled implementation.
5. **Per-hero passive scheduler** — possibly a single hook on the passive-process site captures all of them generically.

Each one removes one more "hand-coded multiplier" line from `cb_sim.py` and replaces it with a call into a `cb_constants.py` function backed by the actual game arithmetic.

---

## Beyond CB — the larger goals from CLAUDE.md

### Battle Locations universe

| Location | Sim? | Optimizer targets? | Auto-run? | Logged battles? |
|---|---|---|---|---|
| Demon Lord (CB) | ✅ | ✅ | ✅ | ✅ |
| Campaign | 🔴 | 🔴 | 🔴 | 🟡 (logger works generically) |
| Dragon | 🔴 | 🔴 | 🟡 (`dungeon_run.py`) | 🟡 |
| Spider | 🔴 | 🔴 | 🟡 | 🟡 |
| Fire Knight | 🔴 | 🔴 | 🟡 | 🟡 |
| Ice Golem | 🔴 | 🔴 | 🟡 | 🟡 |
| Minotaur | 🔴 | 🔴 | 🟡 | 🟡 |
| 4 Keeps (Forest/Magma/Iron/Sand) | 🔴 | 🔴 | 🟡 | 🟡 |
| Faction Wars (16 factions × 21 stages) | 🔴 | 🔴 | 🔴 | 🟡 |
| Hydra | 🔴 | 🔴 | 🔴 | 🟡 |
| Chimera | 🔴 | 🔴 | 🔴 | 🟡 |
| Doom Tower (120 floors × Hard) | 🔴 | 🔴 | 🔴 | 🟡 |
| Cursed City | 🔴 | 🔴 | 🔴 | 🟡 |
| Siege | 🔴 | 🔴 | 🔴 | 🟡 |
| Grim Forest | 🔴 | 🔴 | 🔴 | 🟡 |

### Gear / build systems

| System | Status | Next |
|---|---|---|
| Sell rules engine | 🟡 | Per-hero "needed-for-build" lookback (don't sell what one of the user's planned builds wants) |
| Substat upgrade recommender | 🔴 | Score gear for upgrade-worthiness; flag flat main on Gloves/Chest/Boots as priority sells |
| Per-location stat targets (`data/targets/*.json`) | 🔴 | DL UNM debuffer ≥ 250 ACC; Dragon-20 DPS CR≥80/CD≥150; etc. |
| Mastery batch apply (`/apply-build`) | 🔴 | Today: 60 individual `/open-mastery` calls per hero |

### Auto-run modes

| Mode | Status | Notes |
|---|---|---|
| Active / interactive | ✅ | `tools/cb_run.py`, dashboard Battle button |
| N-runs of a location | 🟡 | CB done; `dungeon_run.py --runs N` works for some dungeons; not all locations |
| Scheduled / cron | ✅ | `tools/windows_tasks.py` + Schedule tab |
| **Smart farming** (planned) | 🔴 | Stat-goal-driven dungeon recommender + run-count estimator. Drop tables exist (`data/static/drops.json`); decision logic doesn't. |

---

## How to keep extending the methodology

For every new "hand-coded sim hack" we want to replace:

1. Find the IL2CPP method in `tools/il2cpp_dumper/dump_output/dump.cs` (grep for the mechanic's likely name).
2. Disassemble its body via `capstone` at the file offset listed in `dump.cs`.
3. Resolve every `call` target via the same VA → method-name lookup.
4. Read any `.rdata` double literals via `pefile` + `struct.unpack`.
5. Resolve struct-field accesses via `il2cpp.h`.
6. Add a Harmony hook to capture live inputs/outputs into the tick log.
7. Verify the formula in Python; commit the constants to `cb_constants.py`.
8. Wire it into the sim, removing the hand-coded value.

Reference implementation: see commit `8501dc7` (DEF formula, 2026-05-02) for the full chain end-to-end.
