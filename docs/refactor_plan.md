# Refactor Plan — Aligning Code to Goals

This is a working document. Decisions get added inline as we agree.
Nothing on this list executes without your sign-off — the principle is
"surface, don't silently delete."

The goals this plan serves are in CLAUDE.md ("Goals & Scope" section).
Architectural principles are also there — every line below cites which
principle it serves and which goal it advances.

## Current Architecture (what we have)

```
PyAutoRaid/
├── mod/bepinex/                       # BepInEx plugin (C#)
│   ├── RaidAutomationPlugin.cs            HTTP router, hooks, status
│   ├── RaidAutomationPlugin.StaticData.cs StaticData extraction
│   ├── RaidAutomationPlugin.LiveData.cs   live heroes/artifacts/skills
│   ├── RaidAutomationPlugin.Battle.cs     battle-state IL2CPP read path
│   ├── RaidAutomationPlugin.Mutations.cs  equip/unequip/sell
│   ├── RaidAutomationPlugin.Presets.cs    team preset CRUD
│   └── RaidAutomationPlugin.Navigate.cs   /navigate + /context-call
│
├── tools/                             # Python — CLI is source of truth
│   ├── (CLI-first modules — added this session)
│   │   sell.py, hero_stats.py, cb_day.py, cb_history.py,
│   │   cb_autorun.py, task_runner.py, potential_teams.py,
│   │   raid_names.py, cli_util.py, windows_tasks.py,
│   │   cb_constants.py, cb_profiles.py, static_data.py
│   │
│   ├── (sim + optimizer — pre-existing, working)
│   │   cb_sim.py (~2.5k LOC), cb_optimizer.py (~1.1k LOC),
│   │   calc_parity_sim.py, comp_finder.py, cb_run.py,
│   │   cb_daily.py, dungeon_run.py
│   │
│   ├── (data refresh + scrape)
│   │   refresh_static_data.py, refresh_data.py, refresh_all.py,
│   │   scrape_dwj.py, scrape_dwj_calc.py, scrape_hellhades.py
│   │
│   └── (dashboard server, port 6791)
│       dashboard_server.py (~2.3k LOC)
│
├── Modules/                            # Lower-level adapters
│   ├── mod_client.py                       HTTP client to mod
│   ├── memory_reader.py                    pymem fallback path
│   └── mod_heroes.py                       hero shape adapter
│
├── data/static/                        # game reference data
│   hero_types.json (8100), artifact_sets.json (71),
│   alliance_bosses.json (6 difficulties), masteries.json (66),
│   blessings.json (30), effects.json (136), drops.json (46 regions),
│   stage_bosses.json (228), forge_sets.json (49)
│
├── data/dwj/parsed/                    # DeadwoodJedi tunes + variants
│   tunes.json (103), calc_tunes.json (246 variants),
│   calc_champions.json (859 configs)
│
└── data/hh/parsed/                     # HellHades ratings (1013)
```

## Gap Analysis vs Goals (what's missing)

For each goal in CLAUDE.md, what exists, what doesn't:

| Goal | Status | Gap |
|---|---|---|
| All battle locations (10) | Partial | We have CB + Dungeons + (some) Faction Wars. Missing: Hydra, Chimera, Doom Tower, Cursed City, Siege, Grim Forest, Campaign |
| Per-stage rewards & drops | Partial | `data/static/drops.json` covers 46 regions for artifact drops. Shard/scroll/potion/relic drop rates not captured. Doom Tower secret rooms unknown. |
| Per-stage enemy stats | Done for CB, partial elsewhere | `alliance_bosses.json` has all 6 CB rows. `stage_bosses.json` covers 228 dungeon+FF stages. Missing: per-stage skill rotations (boss skill cycles). |
| Battle Setup screen automation | Done | `/equip` + `/preset-...` + `/context-call` cover everything. |
| Battle Logger | Done | `/battle-log` + `/battle-state` + `tools/cb_history.py` produce the per-turn JSON. |
| Hero/Skill/Mastery exhaustive index | Mostly | 8100 hero types ✓. Skills: per-account `skills_db.json` (1370 owned-hero skills). **Missing**: ALL skill descriptions (not just owned); needs a /all-skill-data endpoint. |
| Computed Stats matching the game | Partial | `hero_stats.py` covers Basic + Artifacts + Sets + LoS + Empower. **Missing columns**: Arena, Blessing, Faction Guardians, Relic, Area Bonuses. The mod's `/hero-computed-stats` returns the live-game values for cross-check. |
| Artifact Optimizer per location | Partial | `cb_optimizer.py` and `global_gear_solver.py` exist for CB. **Missing**: per-location stat-target presets; per-hero-per-location optimizer call. |
| Mastery system with per-area recs | Partial | Read works (`/all-heroes` has masteries[]). Apply works (`/open-mastery`). **Missing**: per-area recommendation table; "apply build" batch wrapper. |
| Auto-run / N runs / cron | Done | `cb_daily.py`, `dungeon_run.py --runs N`, `windows_tasks.py`, dashboard's LoopController. |
| Smart-farm recommender | Missing | Need: given stat goals, recommend dungeons + run counts using drop rates. |
| Sell rules (user-approved) | Done | `tools/sell.py preview\|execute --confirm\|history` + dashboard panel. |
| Upgrade recommender | Missing | Need: rank artifacts in vault by "should upgrade" score using team needs, set, primary, substats. |
| Demon Lord sim — turn order parity | Done | `calc_parity_sim.py` matches DWJ 100% for 4/4 verified variants. |
| Demon Lord sim — damage numbers | Partial | `cb_sim.py` calibrated to ~94%; per memory has 6 compensating wrongs that mask each other. |
| Demon Lord sim — hero kit modeling | Partial | `cb_profiles.py` has 51 heroes with hand-coded flags. **Missing**: any hero not in this list reverts to a generic profile, which is wrong for new heroes. |

## Suspected unnecessary code (FOR REVIEW — do not delete without sign-off)

These are flagged for *you* to confirm. Each one is real code that runs;
the question is whether it still serves a goal.

| Path | Why flagged | Recommended action |
|---|---|---|
| `tools/tune_library_dwj.py` (5,159 LOC) | Auto-generated data file disguised as Python source. Loaded once at import, never edited by hand. | Convert to `data/dwj/parsed/legacy_tunes.json` + ~50 LOC loader. **Confirm before doing.** |
| `tools/tune_library.py` | A separate tune library from `tune_library_dwj.py`. Unclear which is canonical. | Audit: which CLIs use which? Probably collapse to one. |
| `mod/bepinex/RaidAutomationPlugin.cs : ReadBattleHeroesIL2CPP_OLD` | Dead method, wrapped in `#if false`, ~140 LOC. **Already deleted in commit ad7d621.** | Done. |
| `tools/_*.py` (debug scripts) | Per .gitignore `_*.py` rule — these are throwaway. | Already excluded from VCS; just don't accidentally promote them. |
| Multiple `_today_cb_element_str` / `_last_cb_team_names` shims in dashboard_server.py | Back-compat wrappers around the new tools/ modules, used by 6 leftover dashboard build_X functions. | Keep until the `build_X` callers are also extracted; delete shims when their last caller leaves. |
| `tools/cb_optimizer.py : simulate_damage` | Older damage estimator. `tools/cb_sim.py` is the canonical sim now. | Audit callers. If only used by the optimizer's own scoring, leave it (cohesion); if external code calls it, that's a refactor target. |
| `tools/auto_profile.py` | "Auto-generate CB profiles for all 343 heroes." Did this run produce `cb_profiles.PROFILES`? Or was that hand-curated? | Determine if it's still useful or if `cb_profiles.py` superseded it. |
| `Modules/{hybrid_controller, PyAutoRaid, DailyQuests, PullMysteryShards, CreateTask, base, screen_state, game_state, win32_input}.py` | Legacy pyautogui-based screen automation. Violates CLAUDE.md "NEVER use UI/screen automation". **BUT** `hybrid_controller.py` is still wired as a VM scheduled-task entry point per `docs/vm_deployment.md`. | Real migration job — port each daily run to a mod-API `tools/<x>_daily.py`. Don't delete until the VM scheduled task is repointed. Tracked as Phase ?? (after Phase 2 enables enough locations). |

## Refactor Plan — Phases

Each phase is independently shippable. We do them in order; each one
ends with a working game on user's machine.

### Phase 0 — Foundation cleanup (KISS / YAGNI)

**Goal**: remove rough edges before adding new features.

- [x] DRY out duplicate name dicts (memory_reader, mod_heroes) — done in commit ad7d621
- [x] Replace silent `except: pass` in cb_optimizer with logged variants — done in ad7d621
- [x] Remove dead `ReadBattleHeroesIL2CPP_OLD` — done in ad7d621
- [x] Audit `tune_library.py` vs `tune_library_dwj.py` — done a57989c
      Result: `tune_library_dwj.py` (5159 LOC, 0 callers) was dead.
      Deleted; generator `gen_tune_library_dwj.py` kept + marked
      "CURRENT STATUS: UNUSED" in its docstring.
- [x] Document `Modules/` vs `tools/` boundary — done. Both packages
      now have docstring `__init__.py`. Audit revealed
      `Modules/hybrid_controller.py` is the legacy pyautogui-based
      VM-scheduled entry point. Documented but NOT deleted (active
      production scheduled task per `docs/vm_deployment.md`).
- [x] Convert HTTP `Handler.do_GET`/`do_POST` from giant if-chain to a
      route-table dispatcher — done. GET_ROUTES (22) +
      GET_ROUTES_RAW_QUERY (2) + POST_ROUTES (8) + POST_PATTERNS (1) +
      DELETE_ROUTES (2) + DELETE_PATTERNS (1) = 36 endpoints, same as
      before. Live-tested 6 routes; static-file fallthrough verified.

**Deliverable**: cleaner baseline. Behavior unchanged. ✅ Phase 0 complete.

### Phase 1 — Computed Stats parity (the trust foundation) ✅

**Goal**: PyAutoRaid's per-hero stat numbers match the in-game *Total
Stats* screen exactly. Nothing else can be trusted until this is.

- [x] Mod-side `/hero-computed-stats` returns every column (Basic,
      Artifacts, Affinity, Classic Arena, Masteries, Faction Guardians,
      Empowerment, Blessing, Relic) via the game's own `Calc*Bonus`
      methods.
- [x] Cross-check tool: `python3 tools/hero_stats.py "<name>" --vs-mod`
      diffs our calc against the mod's payload.
- [x] **EXACT match 16/16** verified vs in-game screenshots for Cardiel
      L60 6★ + Gnut L60 6★ (different elements/factions/roles).
- [x] Area Bonuses column — `tools/hero_stats.py "Cardiel" --area dt-hard-f120`
      surfaces the per-round Modifiers from `data/static/stages.json`
      (e.g. R1 +200 RES, R1 +230 ACC, R3 +75 boss SPD). The in-game
      "Area Bonuses" toggle is exactly this data; sim consumers can
      adopt by calling `get_area_modifiers(area_slug)` directly.

**Deliverable**: dashboard hero rows show stats matching the game.
Sim inputs become trustworthy. ✅ Phase 1 complete (commit `b7fdf69`).

### Phase 2 — All-locations static data (scope expansion) ✅

**Goal**: stage list, enemy stats, and reward profile for *every* battle
location, not just CB + dungeons.

Realized via the existing generic `/static-export` endpoint instead of
new dedicated mod endpoints — DRY/KISS. The mod already exposes every
top-level `StaticData.*Data` tree at any depth, so Phase 2 became new
sections in `refresh_static_data.py` rather than C# code.

- [x] All-skills dump (was: `/all-skill-data`). New section
      `skills_all` → `data/static/skills_all.json` (5368 skills with
      Effects[] / KindId / MultiplierFormula / TargetType / Condition /
      Category). Replaces the per-account `skills_db.json` for unowned
      heroes — Phase 4 dependency.
- [x] Master stage list (was: `/stage-rewards?stage_id=N`). New section
      `stages` → `data/static/stages.json` (2873 stages × Area /
      Region / Difficulty / Number / Modifiers / FirstTimeReward).
      Covers every battle location: DoomTower(792) + Fractions(630) +
      FoggyForest(422) + Dungeon(400) + Story(336) + CursedCity(202) +
      Chimera(24) + AllianceBoss(24) + Hydra(24) + Coop(5) + Arena(4) +
      LiveArena(4) + Siege(3) + Arena3X3(3).
- [x] Per-location config blocks (was: `/cursed-city-stages` etc.):
      - `hydra` → `HydraCompetitionData` (Settings, RewardRanges, MilestoneRewardByPoints)
      - `chimera` → `ChimeraCompetitionData` (same shape as hydra)
      - `siege` → `SiegeData` (Layers, Modifiers, Bonuses, Tiers, Traps)
      - `cursed_city` → `StageData.CursedCityData` (DifficultyData)
      - `foggy_forest` → `StageData.FoggyForestData` (Map, Progression, DifficultyIds)
      - `stage_areas` → `StageData.Areas` (the 14 location types)
      - `stage_regions` → `StageData.Regions` (campaign chapters / dungeon tiers)
- [x] Doom Tower coverage: 792 stages live in `stages.json` filtered by
      `Area=DoomTower`. No separate `DoomTowerData` tree exists.

**Deliverable**: ✅ Phase 2 complete. PyAutoRaid has the full game's
stage/skill universe in `data/static/`. Total: 16 sections, ~71MB
canonical reference (skills_all 35MB + stages 35MB + the rest <2MB).

**Known follow-up** (deferred — not blocking Phase 3):
- Stage `FirstTimeReward.Resources` *scalar* fields (Silver, Energy,
  Tokens) ARE captured in the depth=3 `stages.json` we already have.
  The inner `RawValues` IL2CPP-wrapped dict still placeholders out at
  depth=3 — investigated, the `_entries` walk pattern works, but
  bulk pulling all 2873 stages at depth=4 hits the mod's main-thread
  timeout. Real fix: an on-demand `/stage-detail?id=N` endpoint that
  fetches one stage at depth=5+. Add when a caller needs per-stage
  reward composition beyond the scalar fields.
- `Formations.HeroesByRound` (per-stage enemy lineups) has the same
  depth-vs-timeout constraint. Same on-demand fix pattern.

### Phase 3 — Universal sim (not just CB) 🟢 (foundations + plumbing complete; engines remain)

**Goal**: simulate any battle, not just Demon Lord.

- [x] BossProfile abstraction — `tools/boss_profiles.py` with a
      dataclass holding HP/ATK/DEF/SPD/element/skill_pattern/immunities/
      dot_caps/enrage_turn. Profiles auto-generate for CB Easy→UNM ×
      Magic/Force/Spirit/Void (24), plus stub profiles for Hydra (6),
      Chimera (6), and Doom Tower (on-demand via `dt-{normal|hard}-fNNN`).
- [x] CLI: `python3 tools/sim.py --list-locations` enumerates every
      battle slug; `--location <slug> --team "..."` routes to the
      right engine. Stub engines print "not yet implemented" without
      crashing — keeps the surface honest.
- [x] CB engine wired via `cb_potential.simulate_team`; verified
      identical numbers vs direct `cb_potential.py` call (31.36M for
      ME/Demytha/Ninja/Geo/Venomage on UNM Void).
- [x] `cb_potential.simulate_team` accepts `cb_difficulty` /
      `cb_element` / `cb_speed` kwargs; `sim.py` threads
      `profile.difficulty` + `profile.element` through. Verified:
      `cb-nm-force` produces different numbers (33.35M) from `cb-unm-void`
      (31.36M) — boss SPD/HP correctly differ per profile.
- [x] `CBSimulator` accepts a `profile=BossProfile` kwarg; its
      `speed` / `element` / `difficulty` fields override the matching
      legacy kwargs when supplied. Backward-compatible: existing
      callers continue to work unchanged.
- [x] Doom Tower per-floor profiles — `boss_profiles.doom_tower_profile()`
      pulls per-floor metadata from `data/static/stages.json` (792 DT
      stages). Stub output now surfaces stage_id / scene / has_boss /
      per-round Modifiers (R1 +200 RES, R3 boss +75 SPD, etc.) so the
      profile is informative even before the engine ships.
- [ ] Hydra mechanics module — multiple heads, head-specific skills,
      decapitation rules. Stub profiles ready; static config data
      (Settings/RewardRanges) is clan-match metadata, not per-fight
      stats. Real boss stats per fight need an on-demand
      `/stage-detail?id=N` endpoint to walk `Formations.HeroesByRound`
      at depth=5+.
- [ ] Chimera mechanics module — 3 heads with rotating affinity.
      Same as Hydra: stub profiles + clan-match config available;
      per-fight stats need on-demand stage fetch.

**Deliverable**: ✅ dispatcher + profile registry + CB profile
threading + DT per-floor metadata shipped. ⏳ Hydra / Chimera engine
algorithms remain (real engineering — multi-head + decapitation +
on-demand stage detail). The sim surface and CB engine are
production-ready for any of 24 CB difficulty/element combinations.

### Phase 4 — Hero kit completeness (sim correctness) ✅

**Goal**: any hero the user *could own* sims correctly. Don't fall back
to a generic A1×3 profile for unknown heroes.

- [x] All-hero skill descriptions via Phase 2 static data —
      `data/static/skill_descriptions_all.json` filtered out of
      StaticDataLocalization (2560 entries, all 1121 heroes).
- [x] `desc_profiler.parse_all_descriptions()` augmented to fall
      through to static descriptions for unowned heroes. Hero count
      went from 317 owned → 764 with parseable kits (447 newly
      derivable). Owned descriptions still take priority because they
      reflect the user's book upgrades.
- [x] CLI: `python3 tools/sim.py --hero <name> --print-profile`
      shows the parsed kit. Owned-hero output is "book-aware"; unowned
      output is flagged "static (unowned)" so consumers know it lacks
      book/multiplier corrections.
- [x] Sim runtime fallback: `tools/profile_resolver.py:augment_with_unowned`
      converts desc-parsed kits into the same SKILL_DATA / SKILL_EFFECTS
      shape that owned heroes use, then merges them into the
      `load_game_profiles.load_profiles()` output for any name not
      already covered. cb_sim's `SKILL_DATA.get(name, DEFAULT_SKILL_DATA)`
      lookup now hits a real entry for 764 heroes (was 317). Owned
      heroes are NOT touched — book-aware structured profiles always
      win. Verified: identical 31.4M total damage on the owned
      ME/Demytha/Ninja/Geo/Venomage team before and after wiring.
- [x] Effect-level structured data — `profile_resolver` now reads
      `data/static/skills_all.json` (Phase 2) Effects[] for unowned
      heroes: exact damage multipliers (e.g. Erinyes A1=3.1×ATK,
      A2=5.0×ATK, A3=3.2×ATK from the live game data, replacing
      DEFAULT_SKILL_DATA's generic 3.5/4.0/0). Multi-hit Damage
      effects sum their per-effect multipliers, matching the
      load_game_profiles parser shape.

**Deliverable**: ✅ Phase 4 complete — sim has structured data for
764 of 1121 heroes vs. 317 previously, with real damage multipliers
sourced from skills_all.json for unowned heroes. Owned-hero CB sim
unchanged (verified 31.4M total on the calibration team). New game
release → re-run refresh_static_data + refresh_data → done.

### Phase 5 — Sim damage calibration (the hardest one) 🟡 (suite shipped; un-stacking pending user collab)

**Goal**: sim damage numbers match real battle logs within ±5% per
hero, not just team total. Per memory `project_cb_sim_calibration_state`,
the survival model has compensating wrongs that mask each other —
"don't tweak in isolation" is explicit user feedback.

- [x] Regression suite: `tools/sim_calibrate.py` reads every
      `battle_logs_cb_*.json`, extracts team + final boss damage,
      runs the sim with same team/difficulty, reports per-log error %
      and difficulty-grouped summary. Filters to complete battles
      (real_turns ≥ 48) for the headline metric.
- [x] Calibration baseline doc: `docs/sim_calibration_baseline.md`
      captures the 2026-05-01 snapshot:
      - **Brutal**: 3 logs, mean -4.4%, ✅ within ±5% target
      - **UNM**: 8 logs, mean -16.6%, range [-31.1%, -11.0%] ❌
      - Cleanest reference: 2026-04-29 post-revert run is 31.36M sim
        vs 42.85M real = 73.2% accuracy. Calibration hasn't drifted
        since the survival fix paused the work.
- [ ] **Bottom-up survival-model rewrite** (planned with user, not
      autonomous): capture fresh CB run for `s_spd` ground truth +
      buff-state-diff per CB turn → refactor shield absorption +
      Demytha A2 heal + UK-clamp-to-1 + parity-correct CDs +
      extend_buffs(NON_EXTENDABLE) *together*, with sim_calibrate.py
      verifying team-total stays stable. Multi-day coordinated work
      explicitly out-of-scope for autonomous execution.

**Deliverable**: ✅ measurement framework + baseline shipped;
⏳ the calibration un-stacking is now a measured, planable task
instead of a "paused at 94%" black box. User runs the suite, picks
the next chunk to tackle, regression-checks each step.

### Phase 6 — Optimizer per location ✅ (target schema + evaluator shipped; full SA solver remains CB-specific)

**Goal**: artifact optimizer takes a location target and produces a
swap-list.

- [x] Per-location stat target presets in `data/targets/`:
      `cb-unm.json` (3 roles: debuffer / stunner / unkillable),
      `dragon-25.json` (nuker / support), `fire-knight-25.json`
      (shield_piercer), `ice-golem-20.json` (tank). Schema has
      stat_floors / stat_caps / preferred_sets / primary_by_slot /
      substats_priority / notes — documented in `tools/gear_targets.py`.
- [x] `tools/gear_targets.py` — load_target / list_targets / get_role /
      evaluate_gear. Synthetic `<STAT>_pct_of_base` floors evaluate
      against per-hero base stats from the mod's hero-computed-stats.
- [x] CLI: `python3 tools/gear_solve.py --hero <name> --location <slug>
      --role <role>`. Reports PASS / FAIL with deltas; for missed
      stats, scans the user's vault for unequipped artifacts that roll
      the needed substat (top 5 candidates per gap).
- [ ] Wire target preset's preferred_sets into `tools/global_gear_solver.py`
      so the SA optimizer can target any location, not just CB UK.
      Today the SA solver hardcodes Myth Eater speed bands; reading
      from a target preset would generalize it. (Real refactor; not
      blocking.)
- [ ] One-click "apply this loadout" via the existing equip endpoints —
      `gear_solve.py` only suggests swaps today. Application would
      thread through `/equip` + `/swap`. (Real refactor; not blocking.)

**Deliverable**: ✅ user picks a hero + location, gets the floor /
violation report + vault candidates per missed stat. Full SA-driven
swap optimizer for non-CB locations is a logged follow-up.

### Phase 7 — Smart farm recommender ✅ (set-coverage allocator shipped; per-substat odds remain rough)

**Goal**: given stat goals (CB ACC for Hero X, Dragon CD for Y), tell
the user which dungeons to farm and how many runs.

- [x] Set-coverage greedy allocator: `tools/farm_plan.py`. Reads
      `data/static/drops.json` (46 regions × difficulties × set IDs),
      cross-references with the target preset's `preferred_sets`,
      ranks dungeons by sets-covered / energy-cost (efficiency), and
      produces a greedy coverage plan.
- [x] Friendly-name aliasing — UI names ("Lifesteal") map to internal
      codenames ("LifeDrain") so target presets can use whichever.
- [x] CLI: `python3 tools/farm_plan.py --target cb-unm` (uses target's
      preferred_sets) or `--sets "Lifesteal,Speed,Accuracy"` for
      ad-hoc queries. `--list-sources` enumerates every (region, diff,
      set) row.
- [ ] Per-substat odds — drops.json exposes which sets *can* drop
      (set_drops.max_prob), not the per-roll probability of getting
      a specific substat (e.g. "ACC roll on a Lifesteal Banner").
      Substat odds are uniform within an artifact's primary set, so
      the recommender's rough "10 runs per dungeon" budget is the
      right granularity until per-stage rolls are exposed.
- [ ] Goal file: today the recommender takes `--target <slug>` or
      `--sets <list>`. A `goals.json` shape (per-hero per-stat needs
      with weights) would let multiple heroes' demands aggregate. Add
      when a caller needs the multi-goal LP.

**Deliverable**: ✅ farming becomes measured. `python3 tools/farm_plan.py
--target cb-unm` says "farm DragonsLair Normal for Accuracy + LifeDrain
+ DotRate (3-of-4 needed sets at 0.50 efficiency); FireGolemCave Normal
for StunChance" — concrete instead of vibes.

## External Data Sources — How We Use Them

The game on the user's PC is the ground truth. Everything else is
additive — useful for ideas, cross-checks, and pre-computed signals,
but never authoritative.

### DeadwoodJedi (DWJ)

**What we have**: 103 tunes + 246 calc variants + 859 champion configs
in `data/dwj/parsed/`. `tools/calc_parity_sim.py` is a 100%-matching
port of DWJ's turn-meter / priority / delay scheduler.

**What we use it for**:
- Turn-order sanity check — if our cb_sim picks a different action
  than DWJ's calc, one of us is wrong (and DWJ has had years to bake)
- Tune library — pre-computed slot configs / SPD bands / opener orders
  that we score against the user's roster (`tools/comp_finder.py`)
- Profiling approach — DWJ has a clean way of representing per-skill
  priorities, delays, and cooldowns; we mirror that shape

**What we do NOT use it for**:
- Damage numbers (DWJ doesn't even calculate damage, only sync)
- Authoritative skill effects — if DWJ's calc says A2 places Poison
  but the in-game description says HP Burn, the game wins
- Live data — DWJ is a static scrape; only refreshed when we re-run
  `tools/scrape_dwj_calc.py`

**Coupling boundary**: tight enough to inherit their data shapes (slug,
hash, slot), loose enough that DWJ going dark wouldn't break us — the
parsed JSON is our local copy.

### HellHades

**What we have**: 1013 champion ratings + tier list in `data/hh/parsed/`.
Public WordPress data via `tools/scrape_hellhades.py`.

**What we use it for**:
- Tier list as a tiebreaker in `comp_finder.rank_tunes` (when two tunes
  score equally vs roster, prefer the one with higher HH-rated heroes)
- "Should I pull this hero?" gap analysis (`tools/cb.py gaps`)

**What we do NOT use it for**:
- Authoritative team recommendations
- Live damage numbers
- Their crawled user-battle database (see below)

### Open question — HellHades's "Find Team" community data

[Image of raidoptimiser.hellhades.com/team-optimizer]

HH's site has a *Find Team* feature: enter your owned heroes, get
suggested teams that real users have logged on their server. This is
their crawled user-battle dataset — not public scraping fodder.

**Three options**:

1. **Scrape it (light)** — paginate through public team-finder results
   and cache successful team compositions. Pros: instant team recs
   without our sim. Cons: HH's TOS may forbid; their API changes
   would break us; depends on HH staying up.

2. **Build our own community submission system** — let users
   opt-in to upload their battle logs to a shared db; over time
   build the same kind of dataset. Pros: not dependent on HH; we
   own the data. Cons: huge engineering lift; needs hosting; needs
   privacy policy; useless until many users adopt it.

3. **Don't crawl, sim instead** — keep our own sim approach
   (`tools/cb_sim.py` + `calc_parity_sim.py` + `comp_finder.py`)
   and rely on it for team recs. Pros: self-contained; matches our
   "game is ground truth" principle; already 80% built. Cons:
   accuracy still depends on Phase 5 calibration finishing.

**Recommendation: option 3.** HH's user-battle data is their moat;
duplicating or scraping it is a long-tail burden we don't need. Our
sim, once Phase 5 calibrates damage to ±5%, should be a strict
upgrade — it tells you *why* a team works, not just that it did once.
We'd consider option 2 only if a community grows around PyAutoRaid.

### RSL Helper

Reference tool — similar feature surface to ours: auto-farm, sell rules,
artifact optimizer, mastery setup, scheduling. We borrow *ideas* (e.g.
their sell-rules UX informed `tools/sell_rules.py`'s rule shape), not
code or data. Worth periodically checking what features they ship that
we don't, and asking whether the gap matters.

## Process Rules

1. **Don't silently delete code.** Anything in the "Suspected
   unnecessary" table above gets a confirmation step before removal.
2. **Don't break working pipelines.** The mod, sim, dashboard, sell,
   dungeon-loop, and CB-daily all need to keep working at every commit.
3. **CLI first.** Every feature added in any phase ships as a CLI
   command before (or alongside) the dashboard wiring. CLAUDE.md's
   "CLI is the source of truth" principle.
4. **Smoke test at each commit.** Per the session pattern: smoke-test
   the CLI + the dashboard wrapper for any function that changes.
5. **One concept, one home.** Per the DRY principle in CLAUDE.md: when
   adding a new constant, dict, or shared function, search before
   defining. Add to the existing canonical module.

## Open Questions (for the user before we execute)

**Resolved 2026-05-01**:
- HellHades user-battle data: NOT crawling. Stick with our own sim
  (option 3 above). Game is ground truth; HH is additive.
- DWJ + HH stay loose-coupled — `tools/calc_parity_sim.py` is sanity
  checking, never authoritative.

**Still open**:
- Phase 0 — `tune_library_dwj.py` → JSON: do it now, or wait until we
  next touch the DWJ pipeline?
- Phase 0 — `tune_library.py` vs `tune_library_dwj.py`: are both used,
  or is one a leftover?
- Phase 1 — do we want the per-column breakdown to match the game's
  "Affinity" column, which is account-wide vs the hero, or hero-
  specific? (Affinity Bonuses screen has confused us before.)
- Phase 2 — Hydra and Chimera mechanics: should sim model them, or just
  log them for now? (Modeling = real engineering; logging = ~1 day.)
- Phase 4 — when `desc_profiler` derives a hero profile that conflicts
  with hand-curated `cb_profiles.PROFILES`: which wins? Memory says
  "verify skills before attributing damage" — so probably the hand
  override wins, but it should warn-on-divergence.
- Phase 5 — what's the regression bar? "Same per-hero damage to ±5%"
  or "same total damage to ±10%"? (Per-hero is harder; team-total
  hides errors.)
- RSL Helper feature gap audit — should we make a one-time list of
  what RSL Helper does that we don't, and decide which gaps matter?

Add answers / counter-proposals inline; we iterate from there.
