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

## Refactor Plan — Phases

Each phase is independently shippable. We do them in order; each one
ends with a working game on user's machine.

### Phase 0 — Foundation cleanup (KISS / YAGNI)

**Goal**: remove rough edges before adding new features.

- [x] DRY out duplicate name dicts (memory_reader, mod_heroes) — done in commit ad7d621
- [x] Replace silent `except: pass` in cb_optimizer with logged variants — done in ad7d621
- [x] Remove dead `ReadBattleHeroesIL2CPP_OLD` — done in ad7d621
- [ ] Convert `tune_library_dwj.py` from 5k-LOC Python → JSON + loader (5 min, big startup-time win)
- [ ] Audit `tune_library.py` vs `tune_library_dwj.py` — collapse if redundant
- [ ] Document `Modules/` vs `tools/` boundary in a one-liner per package init
- [ ] Convert HTTP `Handler.do_GET`/`do_POST` from giant if-chain to a route-table dispatcher (~30 min, easier to add routes)

**Deliverable**: cleaner baseline. Behavior unchanged.

### Phase 1 — Computed Stats parity (the trust foundation)

**Goal**: PyAutoRaid's per-hero stat numbers match the in-game *Total
Stats* screen exactly. Nothing else can be trusted until this is.

- [ ] Add `tools/hero_stats.py` columns: Arena (from `account_data.json`),
      Blessing (`/all-heroes[].blessing`), Faction Guardians (mod read,
      data exists), Relic (`/all-heroes[].relic`), Area Bonuses (per-
      location modifiers from `data/static/`)
- [ ] Cross-check tool: `python3 tools/hero_stats.py "<name>" --vs-mod`
      shows our calc vs `/hero-computed-stats` for the same hero, flags
      any column that disagrees
- [ ] Wire dashboard `compute_hero_actual_stats` to use the full
      breakdown (currently only feeds the partial calc)

**Deliverable**: dashboard hero rows show stats matching the game. Sim
inputs become trustworthy.

### Phase 2 — All-locations static data (scope expansion)

**Goal**: stage list, enemy stats, and reward profile for *every* battle
location, not just CB + dungeons.

- [ ] Mod endpoint `/stage-rewards?stage_id=N` → reward composition
      (artifact/shard/scroll/potion drop probabilities) for any stage.
- [ ] Mod endpoint `/all-skill-data` → per-skill effect dump for ALL
      heroes (not just owned). Powers sim of teams the user doesn't have yet.
- [ ] Mod endpoint `/cursed-city-stages`, `/doom-tower-floors`,
      `/hydra-config`, `/chimera-config`, `/siege-config` (one new
      partial-class file: `RaidAutomationPlugin.AltLocations.cs`)
- [ ] Add to `tools/refresh_static_data.py` SECTIONS dict; outputs land
      in `data/static/<location>.json`

**Deliverable**: PyAutoRaid knows the full game's reward + enemy data.
Sim and optimizer can target any location.

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

Add answers / counter-proposals inline; we iterate from there.
