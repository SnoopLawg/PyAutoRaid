# PyAutoRaid Roadmap

Phased execution plan against `MISSION.md`. Single source of truth for
what's done, in flight, and next. Updated as work moves between states.

> **Definition of done**: (a) CLI works, (b) sim/optimizer matches game
> behavior to its calibration target (±5% per-affinity-per-tune for any
> location feeding a recommender), (c) values are sourced from the game
> (live mod or static IL2CPP dump), not back-solved.

## Status legend

- ✅ **Done** — game-truth values, calibration verified, scalable
- 🟡 **Partial** — works for the common case; edge cases or other content not yet covered
- 🔴 **Open** — not started or stalled

---

## Milestones

The plan is to nail **CB end-to-end** as the reference implementation,
then port the same pattern (sim → log → recommend → run) to every other
location. Milestones are sequential — Milestone N's pattern informs N+1.

### M1: CB end-to-end (in flight)

**Goal**: sim ±5% across all 4 affinities × all tunes the user runs;
full per-tick + post-battle logging; prompt-on-destructive recommender
that proposes team/gear swaps; daily runner that survives mod restarts
and verifies leaderboard credit.

| Sub-goal | Status | Notes |
|---|---|---|
| Sim — Force-day MEN tune | ✅ | **2026-06-23**: -3.4% @ BT24 + -1.8% @ BT19 (2 fixtures within ±5%). DWJ-parity scheduler ported via TM-reset fix. |
| Sim — Magic-day MEN tune | ✅ | **2026-06-23**: -1.4% / +3.2% / +0.8% @ BT49 (3 BT49 fixtures within ±5%). Was -55% under pre-session. |
| Sim — Spirit-day MEN tune | ✅ | **2026-06-23 (afternoon)**: 4 fixtures all ±5% (BT28×2 +0.5%/+2.6%, BT48 -1.9%, BT49 full +0.4%). Stale "-55% under" memory was pre-element-fix data — disregarded. |
| Sim — Void-day MEN tune | 🟡 | Per user 2026-06-23: there is no "Void day" — boss is Void for first 50% HP, then today's affinity. Validating pure-Void calibration requires solo-attack at fresh boss reset. See `project_cb_void_first_half_mechanic`. |
| Battle log — per-tick state | ✅ | Mod's `/tick-log` captures TM, HP, buffs, debuffs, damage events with intermediates |
| Battle log — post-battle deltas | 🟡 | Damage attribution per-hero works; quest/leaderboard credit verification added to `cb_daily.py`; item drops not yet structured |
| Death watcher (key conservation) | ✅ | `tools/cb_watcher.py` validated end-to-end. Trigger fires on `hp_cur<=0`; per-poll JSONL trace lands at `cb_watcher_<tag>_<ts>.poll.jsonl`. Skill: `.claude/skills/cb-key-conservation/` |
| Fixture library + replay | ✅ | `tools/fixture_archive.py` catalogs (tick + battle + poll + **presets** as of 2026-06-23) triples into `data/fixtures/manifest.json`. **New 2026-06-23**: preset snapshot bundled at capture time so historical fixtures replay against the correct preset. |
| Per-hero turn cadence diagnostic | ✅ | `tools/turn_cadence_diff.py` (NEW 2026-06-23) compares per-hero turn counts between sim and real per BT. Cb_sim cadence now matches DWJ-parity exactly on the MEN tune. |
| DWJ-parity scheduler | ✅ | **NEW 2026-06-23**: TM-reset (not preserve-overflow) on cast brings cb_sim per-hero cadence within 0 turns of DWJ-parity. See memory `project_cb_sim_tm_reset_fix`. |
| Recommender — team picks | 🟡 | `cb_team_explorer.py` surfaces novel comps; **gate now passed for Magic+Force MEN** — still gated for Spirit+Void until verified. |
| Recommender — gear loadouts | ✅ | `global_gear_solver.py` + `cb_optimizer.py` solve per-team stat targets; per-hero stat targets via `hh_picker.py` (HH still in path — to deprecate) |
| Daily runner | ✅ | `cb_daily.py` runs all keys, session warm-up, leaderboard verification, silent-fail detection |
| Preset substrate integration | ✅ | `/save-preset`, `/update-preset`, `/apply-preset` all live; user's flagship preset is id=1 (signal-matched, not type-filtered) |

**Status 2026-06-23 (end of day)**: M1 ±5% gate MET on Magic + Force +
Spirit (3 of effective 3 affinities — Void doesn't have a "day" in the
normal rotation, see Void note above). Recommender now eligible to
ship prescriptive picks for the user's MEN tune on Magic/Force/Spirit.

**Headline fix this session**: cb_sim per-hero cadence was systematically
8-14% slower than DWJ-parity (which matches real game). Root cause was
`champ.tm -= TM_THRESHOLD` (preserve overflow) instead of DWJ's
`turn_meter = 0` (reset). One-line scheduler fix brought all 5 heroes
to within 0 turns of DWJ over 50 BTs. Plus: facade encoding bug fixed,
preset snapshot pipeline added, Ninja A3 reduce_cd Hailburn modeled.

**Spirit calibration (afternoon push)**: 4 captures (3 partial via
cb_watcher kill-at-turn-48, 1 full battle) all within ±5%. Stale
"Spirit -55% under, dies BT22" memory was pre-element-fix Magic/Force
data mislabeled — disregarded. Real Spirit MEN survives to T50 enrage
with 35-36M.

### M2: Replicate pattern for Hydra / Chimera

**Goal**: same bar as CB (±5% sim, full logging, recommender, runner)
applied to weekly Hydra and weekly Chimera battles.

| Sub-goal | Status |
|---|---|
| Static export — Hydra heads + skills | ✅ (`data/static/hydra.json`) |
| Static export — Chimera | ✅ (`data/static/chimera.json`) |
| Sim — Hydra heads (Head/Hand/Torso/Stomach) | 🔴 |
| Sim — Chimera | 🔴 |
| Battle log — Hydra-specific damage attribution | 🔴 |
| Recommender — head-targeting logic | 🔴 |
| Runner | 🔴 |

Pre-req: M1's death-watcher + fixture library generalize directly.

### M3: Daily/weekly/monthly/event orchestrator

**Goal**: resource-aware runner that walks every quest tier, every
tournament, every event progression task. Smart-skip when resources
won't support attempts. Records every action and its effect.

| Sub-goal | Status |
|---|---|
| Daily quests (`tools/daily_quests.py` + per-domain tools) | 🟡 — most quest types tick; some have known automation gotchas (see memory `project_daily_quest_protos.md`) |
| Weekly quests | 🟡 |
| Monthly quests | 🔴 |
| Tournaments | 🔴 (event detection in `tools/events_status.py`; per-tournament point-source mapping TBD) |
| Events (e.g. fusion ingredient progression) | 🟡 — `fusion_frag_tracker.py` handles fragment events |
| Magic shop daily | ✅ |
| Arena daily (`tools/daily_arena.py`) | 🟡 — opponent picker live; sim recommender absent |
| Tag Team Arena | 🔴 |
| Clan tournament | 🔴 |
| Gem mine, inbox, timed quests | 🟡 |

### M4: Arena (classic + Tag Team) full

**Goal**: opponent sim, team picker, daily runner. Classic Arena should
factor speed-rank into picks; TT should factor 3v3 round structure.

| Sub-goal | Status |
|---|---|
| Opponent state + refresh (`/arena-opponents`, `/arena-refresh`) | ✅ |
| Sim — arena 5v5 turn order | 🔴 |
| Sim — TT 3v3 round structure | 🔴 |
| Recommender — counter-pick | 🔴 |
| Runner | 🟡 (defensive — picks lowest-power available) |

### M5: Universal hero / gear / synergy engine

**Goal**: the Understand-pillar foundation generalized across every
location. Per-location stat targets, per-hero kit synergy graph, per-set
contribution model. Drives the recommender for every other location
(Dragon, Spider, FK, Ice Golem, Minotaur, 4 Keeps, Faction Wars, Doom
Tower, Cursed City, Siege, Grim Forest).

Pre-req: M1-M4 patterns proven. M5 is the unification step.

| Sub-goal | Status |
|---|---|
| Phase 1 — Game-truth inventory (`docs/m5_phase1_inventory.md`) | ✅ 2026-06-23 — 1113 playable + 968 boss entries indexed; 100% hero-referenced skill coverage; mastery + blessing gaps tagged |
| Phase 2 — Per-hero CB sim coverage catalog (`docs/m5_phase2_hero_catalog.md`) | ✅ 2026-06-23 — every champion classified: 607 fully_modeled / 505 has_gaps / 0 unknown / 1 missing data (after recovering 525 skills omitted from `hero_types.json` skill_ids — earlier 672/440 undercounted gaps) |
| Phase 3 — Per-location mastery relevance (`docs/m5_mastery_relevance.md`) | ✅ 2026-06-23 — all 66 masteries tagged per location (cb/arena/tt/dungeon/fw/dt/cc/siege/hydra/chimera/forest/campaign); 24 hand-coded sim handlers (M5 batch: Oppressor / Heart of Glory / Grim Resolve / Single Out / Ruthless Ambush / Blastproof / Improved Parry / Bulwark / Spirit Haste / Wrath of the Slain), 11 stat-bonus auto-loaded |
| Phase 3 — Per-location blessing relevance (`docs/m5_blessing_relevance.md`) | ✅ 2026-06-23 — all 34 blessings tagged per location; 6 modeled with verified game-truth procs, 28 with tooltip-public mechanics pending IL2CPP verification |
| Hero kit model (1113 heroes) | ✅ — universe-wide skill modeling foundation shipped |
| Mastery effect map — game-wide hand-code | 🟡 — 10 new procs shipped 2026-06-23 (Oppressor, Heart of Glory, Grim Resolve, Single Out, Ruthless Ambush, Blastproof, Improved Parry, Bulwark, Spirit Haste, Wrath of the Slain). Still queued (need hero-side debuff/crit-incoming-event tracking the sim lacks): Cycle of Revenge (TM on ally crit), Stoked To Fury (dmg per self-debuff), Arcane Celerity (TM on debuff received), Wisdom of Battle (BD on ally crit), Stubbornness (RES per self-debuff). |
| Blessing effect map — game-wide hand-code | 🟡 — all 30 blessing proc formulas now game-truth (`data/static/blessing_procs.json`, `docs/m5_blessing_procs.md`) after fixing the `GetBlessingsTruth` Nullable<int> read to expose the authoritative blessing→skill link. Revealed community-sourced manifest names (Brimstone/Cruelty/PerfectHeal) aren't in the current 30-blessing set. SoulDrinker corrected to NO-OP vs CB (DestroyHp). Sim-wiring of the proc damage still pending (calibration-sensitive). |
| Per-location stat targets | 🟡 2026-06-23 — `tools/m5_stat_targets.py` → `data/static/stage_stat_targets.json` + `docs/m5_stat_targets.md`. Game-truth ACC floors (effective boss RES) + boss SPD/ATK/DEF modifiers for 627 boss stages from `stages.json` Modifiers[]. CB UNM ACC floor=225 (30 base+195 mod), matches community canon. Wired into recommender. Still needs per-build damage targets (CR/CD/ATK% — not game-imposed floors). |
| Per-set bonus model | ✅ — `data/static/artifact_sets.json` |
| Synergy graph (cross-hero kit interactions) | ✅ 2026-06-23 — `tools/m5_synergy_graph.py` → `docs/m5_synergy_graph.md` + `data/m5_synergy.jsonl`. Per-hero provides/needs tags from game-truth skill descriptions; provider index per synergy axis (Block Damage, Unkillable, Decrease DEF, poison-enable, dot-detonate, TM control, cleanse, revive). Recovered 525 skills omitted from `hero_types.json` skill_ids. |
| Recommender per location | ✅ (functional) 2026-06-23 — complete decision loop: `m5_recommender.py` (team, 8 locations, `--builds`) → `m5_build_recommender.py` (per-hero masteries + sets + blessing + stat focus + ACC readiness vs live `/hero-computed-stats` + where-to-farm sets via `drops.json`) → `m5_roster_gaps.py` (pull/build priorities). Guide: `docs/m5_recommender_guide.md`. Still gated: sim-validation of teams (CB-only, blocked on calibration) + per-build CR/CD/ATK% damage targets (deliberately not invented). |

**Top sim-coverage gap-kinds across the 440 has_gaps heroes** (drives priority for next round):
`RemoveBuff` (106 heroes), `RemoveDebuff` (101), `StealBuff` (88), `ReduceBuffLifetime` (44),
`IncreaseCooldown` (39), `TransferDebuff` (36), `ActivateSkill` (30), `MultiplyDebuff` (24).

---

## Overall progress snapshot (last updated 2026-06-21)

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
- **HitTypeBonus function** (`tools/cb_constants.py::hit_type_bonus`)
  - Source: `DamageCalculator.HitTypeBonus(BattleHero, HitType)` at VA 0x182CE7880
  - Branches by hitType: Normal=0, Crushing=`GameplayData.CrushingHitCoef` (=+0.30), Critical=`dealer.Stats.CriticalDamage`, Glancing=`GameplayData.GlancingHitCoef` (=-0.30)
  - Constants confirmed game-truth (already matched values in `gameplay.json`)
- **DamageReductionByStatusEffects scope** (`tools/cb_constants.py::stone_skin_damage_factor` and friends)
  - Source: `DamageCalculator.DamageReductionByStatusEffects` at VA 0x182CE6E50
  - The function processes ONLY: Invisible (480/481), StoneSkin (620/621), Petrification (630), NewbieDefence (670). None of these are active in CB scenarios.
  - Loaded literals 0.25, 0.075, 0.15 are reduction amounts for those specific buffs.
  - **Implication for CB sim**: Weaken/Strengthen/Decrease ATK are NOT in this function; they're applied by other code paths (`CalculateDamage` itself or via boss skill multipliers). Sim's hand-coded `wk = 1.25 if has_weaken` is correct.
- **StoneSkin / Petrification / NewbieDefence factor functions** (stubs returning 1.0)
  - Source: `StoneSkinDamageFactor` (0x182CE8520), `PetrificationDamageFactor` (0x182CE8200), `NewbieDefenceDamageFactor` (0x182CE80C0)
  - All three return 1.0 (no reduction) for any CB-realistic state. Functions added to `cb_constants.py` for future use; CB sim doesn't call them.

### ✅ Game-truth values from static export (no decompile needed)

- **HP Burn `StackCount: 1`** (singular per target) — `data/static/effects.json` Id 470
- **Boss UNM HP, base ATK/DEF/SPD** — `data/static/cb_bosses.json` + `data/static/alliance_bosses.json` + tick log capture (`p_atk=6993`, `t_def=1520` at base)
- **CB skill multipliers** (AoE1=4×ATK, AoE2=2+1×ATK, Stun=0.2×TRG_B_HP) — `data/static/skills_all.json` for skill IDs 222603/222802/222601
- **Affinity coefficients** (`ElementDisadvantageCoef=−0.2`, `CrushingHitCoef=0.3`, `GlancingHitCoef=−0.3`, `CriticalHitChanceAdvantage=0.15`, etc.) — `data/static/gameplay.json`
- **NonIncreaseable buffs** (UK / BD / etc. don't extend) — `data/static/non_increaseable_effects.json`
- **Gathering Fury formula** (T10–T19: `0.75 × (turn − 9)`; T20+: cliff; T50: enrage) — extracted from `data/static/skills_all.json` skill 222904

### 🟡 Hand-coded / empirical — candidates for the same extraction treatment
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

### Newly extracted 2026-05-02 (later in session)

- **`CalculateDamage` / `Calculate` orchestrator body** — investigated. Weaken/Strengthen/dec_atk are NOT in either; they're applied by per-effect processors (`ChangeCalculatedDamageProcessor` at VA 0x182CF9AE0, `ChangeDamageMultiplierProcessor` at VA 0x182CFA2C0). The processor reads the literal multiplier from the status effect's `MultiplierFormula` field — already in `data/static/effects.json`.
- **Status-effect multipliers from static** (`tools/cb_constants.py::status_effect_multiplier`):
  - Weaken (Id 350): 1.25 — confirmed game-truth via `effects.json`
  - IDT15 (Id 351): 1.15
  - Minotaur IDT (Id 430): 3.0
  - HydraNeck IDT (Id 431): 3.0
- **DoT caps from boss passive skills** (`tools/cb_constants.py::cb_dot_cap`):
  - HP Burn cap = 75000 (skill 200008)
  - Poison 5% cap = 50000 (skill 200007)
  - Poison 2.5% cap = 25000 (skill 200007)
  - Big-AoE cap = 250000 (skill 200008 last effect)
  - All parsed from each skill's `MultiplierFormula` regex
  - `tools/raid_data.py` now consumes these via `cb_constants.cb_dot_cap()` first, falls back to `data/observed_dot_caps.json`, then to hand-coded defaults

### Next-up extraction targets in priority order

1. **Boss skill cycle priority** — INVESTIGATED 2026-05-02: real captured boss casts show exactly the same `aoe1 → aoe2 → stun` rotation sim already implements. The game doesn't use a complex utility-AI for CB; the cycle is determined by skill priority + cooldown rules (A3 cd=3, A2 cd=3, A1 cd=0). No extraction needed — sim's `CB_VOID_PATTERN` is game-truth. The full `UtilityAI` / `EnemyTurnActionGenerator.PickSkills` pipeline exists in dump.cs at VAs 0x182DC2820+ / 0x182DC58B0 and matters for non-CB battles (other dungeons / Hydra / DT bosses) where the boss's per-turn decision is non-trivial.
2. **CB damage caps in infinite-HP mode** — `FA_CAP_*` constants. From skill 200008's MultiplierFormula effects we now have all four cap values: 15000 / 50000 / 75000 / 250000. Sim uses 75000 for SMALL/DoT and 250000 for BIG; the 175K MEDIUM cap doesn't exist in skill 200008 — it might be a different skill or an empirical observation that's actually one of the other values. Re-derive sim's MEDIUM usage from real captured Force-Affinity battles when one's available.
3. **Per-hero passive scheduler** — DEFERRED. Audit shows only 4 hand-coded mechanics remain: Cardiel revive, Ultimate Deathknight revive, Occult Brawler ignore-DEF, Geomancer Stoneguard team-wide. Each is a unique mechanic; merging them into a generic dispatcher would add abstraction without removing per-hero logic. Per KISS/YAGNI, leave as-is but ensure each value/multiplier is sourced from static data (verified for Stoneguard — its `data/static/effects.json` MultiplierFormula provides the -15% reduction).

Each remaining item is bounded; the sim is now within ±2% calibration on Magic UNM with all major formulas sourced from game data.

---

## Team explorer (`tools/cb_team_explorer.py`)

State at end of 2026-05-02: explorer is functional and surfacing
genuinely novel team comps from the user's owned roster.

### What works

- **Dynamic role discovery** from `data/static/skill_descriptions_all.json` — keyword matching for UK/BD/heal/shield/def_down/weaken/poisoner/burner/inc_atk/inc_def/inc_spd/inc_cr/inc_cd/cd_reset/extra_turn/revive/etc. Across all 1121 hero names.
- **Stratified random sampling** from feasible team enumeration (eliminates alphabetical bias).
- **Score-based prune** via `predict_score()` (role coverage + HellHades CB ratings) before paying full sim cost.
- **DWJ tune fill** — populates each DWJ tune's slot list with owned heroes, substituting role placeholders (`"DPS"`, `"Cleanser"`, `"Pain Keeper"`, `"Tower/Santa"`) with same-role owned heroes. 35/103 DWJ tunes fillable from a typical 6-star roster.
- **Tighter `novel?` flag** — distinguishes `DWJ` (exact tune match), `+N%` (beats closest DWJ by N%), `no` (worse than closest DWJ), with `--novel-margin` threshold (default 10%).
- **Two sim paths**:
  - Default `simulate_team` — potential gear, ~12M scale
  - `--use-current-gear` → `evaluate_team_calibrated` — real gear + Maneater A3-opener convention, ~16M scale
  - `--explore-speed` — drops UK SPD cap during gear opt (often produces lower damage but useful for genuine new-tune exploration when paired with cross-hero SPD coordination)

### Known gaps (not blocking — flagged for future)

1. **Preset-driven skill priorities** — the 16M-vs-36M gap. Calibrated sim hits ~36M because it applies the user's saved presets (Demytha A2 priority, Ninja delay-2 A3, etc.). `evaluate_team_calibrated` doesn't yet read `/presets`. Closing this gap requires loading the user's saved presets and applying matching ones to test teams during sim. User flagged as "preset handling isn't ready yet".
2. **`--explore-speed` is naive** — just drops the SPD cap; doesn't coordinate cross-hero ratios. Real new-tune discovery needs an SPD-search algorithm that finds hero-speed combinations where the UK chain holds at non-traditional values.
3. **`vs_dwj` baseline** uses the closest DWJ tune by hero overlap — fine for swap-style novel comps but uninformative for fully-novel comps with no DWJ overlap (shows `n/a`).

### Current strong novel candidates (run on owned 6-star roster, Magic UNM, --use-current-gear)

| Damage | vs DWJ | Team |
|---|---|---|
| 65.5M | +87% | Geomancer, Maneater, Seeker, Teodor the Savant, Uugo |
| 44.7M | +27% | Demytha, Maneater, Razelvarg, Seeker, Teodor the Savant |
| 29.1M | +149% | Alsgor, Maneater, Ninja, Teodor the Savant, Urogrim |
| 28.9M | +65% | Demytha, Fayne, Geomancer, Maneater, Uugo |
| 22.1M | +59% | Demytha, Maneater, Miscreated Monster, Sicia, Teodor |

Pattern observation: `Teodor the Savant` (DoT-extender) and `Seeker` (multi-debuff) appear in 4 of top 5; `Uugo` (def_down + cleanse) is the standout sustain+debuff hybrid. Worth in-game testing.

### When picking back up

1. **Validate top picks in-game**: spend a CB key on `Geomancer + Maneater + Seeker + Teodor + Uugo` and compare to ~36M baseline.
2. **Wire `/presets` reading** when ready: read user's saved presets at sim time, apply matching priorities to each test team. Closes the 16M→36M gap.
3. **Per-hero damage breakdown in explorer output** — show DoT vs direct vs WM/GS contribution for each top team so the user sees WHERE the damage is coming from.
4. **Cross-hero SPD coordinator** for real `--explore-speed` discovery.
5. **Use the team explorer to validate new heroes** before deciding to ascend / book / gear them.

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
| Per-location stat targets | 🟡 | ACC floors now game-truth via `tools/m5_stat_targets.py` (CB UNM=225, derived from stage RES modifiers). DPS CR/CD/ATK% targets still per-build TODO. |
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
