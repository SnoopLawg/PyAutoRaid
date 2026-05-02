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
- [ ] Area Bonuses column — per-location buffs (CB / Dungeon / Hydra
      modifiers). Not in the default Total Stats view; deferred until a
      caller needs per-area accuracy.

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
- Stage `FirstTimeReward.Resources` and `Formations.HeroesByRound`
  contain IL2CPP-wrapped `Dictionary<,>` placeholders (`<Dictionary\`2>`)
  that the generic `/static-export` reflection can't enumerate. Same
  fix pattern as the Cardiel `ArtifactIdByKind` block (use
  `GetEnumerator + MoveNext + Current` instead of indexer). Add when
  the sim or optimizer needs per-stage reward lookups beyond the
  scalar fields (XP, IsBoss, Modifiers).

### Phase 3 — Universal sim (not just CB)

**Goal**: simulate any battle, not just Demon Lord.

- [ ] Generalize `tools/cb_sim.py` to take a *boss profile* (HP, ATK,
      DEF, SPD, skill rotation) from `data/static/` rather than
      hardcoded UNM Demon Lord values
- [ ] Hydra mechanics module — multiple heads, head-specific skills,
      decapitation rules
- [ ] Doom Tower bosses module — per-floor boss profiles
- [ ] CLI: `python3 tools/sim.py --location hydra-unm --team "..."`
      (single dispatcher, current `cb_sim.py` becomes one backend)

**Deliverable**: any battle the user might run can be simmed before
spending energy/keys.

### Phase 4 — Hero kit completeness (sim correctness)

**Goal**: any hero the user *could own* sims correctly. Don't fall back
to a generic A1×3 profile for unknown heroes.

- [ ] Auto-derive hero profiles from `skill_descriptions.json` +
      `effects.json` — buff/debuff types, damage multipliers, special
      passives. (Already partly done by `desc_profiler.py`; finish it.)
- [ ] Hand-corrected overrides for kits where text-parsing is ambiguous
      (the current `cb_profiles.py` becomes the override layer, not
      the primary source)
- [ ] CLI: `python3 tools/sim.py --hero "Cardiel" --print-profile`
      shows the derived profile + overrides

**Deliverable**: sim accuracy not bottlenecked on "we don't have a
profile for this hero". New game release → re-run desc_profiler → done.

### Phase 5 — Sim damage calibration (the hardest one)

**Goal**: sim damage numbers match real battle logs within ±5% per
hero, not just team total. Per memory `project_cb_sim_calibration_state`,
this is paused at 94% with 6 compensating wrongs.

- [ ] Build a regression suite: every battle log in `battle_logs_cb_*.json`
      becomes a test case (sim that team → assert per-hero damage within
      5%)
- [ ] Un-stack the 6 compensating wrongs *together*, tracking the
      regression suite at every step (per memory: don't fix in isolation)
- [ ] CLI: `python3 tools/sim_calibrate.py --logs battle_logs_*.json`

**Deliverable**: sim is trustworthy enough to test gear/team changes
without spending CB keys.

### Phase 6 — Optimizer per location

**Goal**: artifact optimizer takes a location target and produces a
swap-list.

- [ ] Per-location stat target presets (`data/targets/cb_unm.json`,
      `data/targets/dragon_20.json`, etc.)
- [ ] Generalize `tools/global_gear_solver.py` to read these
- [ ] Diff output: which artifact swaps actually move stats; produce
      one-click "apply this loadout" via the existing equip endpoints

**Deliverable**: user picks a hero + location, gets the swap plan.

### Phase 7 — Smart farm recommender

**Goal**: given stat goals (CB ACC for Hero X, Dragon CD for Y), tell
the user which dungeons to farm and how many runs.

- [ ] Drop-rate model from `data/static/drops.json` × per-stage rolls
- [ ] Greedy / linear-prog allocator: minimize energy spent to hit all
      goals
- [ ] CLI: `python3 tools/farm_plan.py --goals goals.json --max-energy 5000`

**Deliverable**: farming becomes a measured process, not vibes.

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
