# CLAUDE.md

> **Mission**: see `MISSION.md` (the "why" — pillars, non-negotiables, anti-patterns).
> **Roadmap**: see `docs/roadmap.md` (the "what's next" — phased milestones).
> This file is the "how" — operational reference and tool catalog.

## Project Overview

PyAutoRaid automates Raid: Shadow Legends via a BepInEx mod HTTP API (port 6790) running on the local Windows PC (no VM). Primary focus: CB optimization with a turn-by-turn damage simulator calibrated to -7% of real battle data.

**NEVER use UI/screen automation.** All game actions go through the mod API context-calls.

**CLI is the source of truth.** Every dashboard feature has a CLI counterpart so the system runs headless. When adding a feature, write it as `tools/<feature>.py` with an `if __name__ == "__main__"` entrypoint first; the dashboard becomes a thin HTTP wrapper that calls the same domain functions. Examples: `tools/sell.py preview|execute|history`, `tools/hero_stats.py "<name>"`, `tools/cb_day.py`.

**The game is ground truth.** Plarium's IL2CPP runtime is the only authoritative source for stats, skills, and effects. DeadwoodJedi's calculator and HellHades's optimizer are *additive* references — useful for cross-checking and learning their profiling approaches, but they are NOT primary sources. Concretely:
- `tools/calc_parity_sim.py` matches DWJ's scheduler 100% — that's a sanity check that our turn order is right, not a coupling. If DWJ disagrees with the live game, the game wins.
- `data/hh/parsed/` holds HH's public hero ratings + tier list — we use them as scoring signals in `comp_finder.py`, never as authoritative data. If HH says hero X is S-tier but the in-game skill description says it does 1×ATK, the game's number wins.
- RSL Helper has feature parity with much of what we do (auto-farm, sell rules, mastery setup). We borrow ideas, not code or data.
- Avoid tight coupling to either source: if DWJ's site goes down or HH changes their schema, PyAutoRaid keeps working because the game is on the local machine.

## Goals & Scope

PyAutoRaid is a comprehensive offline assistant for Raid: Shadow Legends. It
must be able to run any battle the game offers, log it perfectly, simulate it
without spending energy/keys, optimize gear and masteries for the hero+location
combo, and either drive runs interactively or on a schedule.

The non-negotiables:
- Mod API only (never screen automation).
- Stats and skills must match what the game shows (the in-game *Total Stats*
  and skill-effect descriptions are the ground truth).
- Sim numbers must match observed battle logs within calibrated bounds.

> **Roadmap & status by area** — `docs/roadmap.md` tracks completion per
> location/system, what's still hand-coded vs game-truth-extracted, and the
> priority queue of next mechanics to extract. Update it whenever a feature
> moves from 🟡/🔴 to ✅ or when a new gap is identified.

### Battle Locations (the universe of activity)

Every location below uses the same **Battle Setup** screen (5+ slot grid +
hero list at the bottom; Battle/Multi-Battle on the right). Hero slot
contents persist across runs — Raid auto-fills the previous team. The
`Team Setup` button on the left opens **15 saved presets**; checking a
preset's box auto-populates the slots. Each preset has a per-round skill
order editor (essential for CB delays, e.g. delay-2 A3).

| Location           | Stages          | Notes / Reward profile                                  |
|--------------------|-----------------|---------------------------------------------------------|
| Campaign           | 12 chapters × Brutal/Nightmare | XP, silver, shards (drop-rate by stage)  |
| Dungeons           | Dragon, Spider, Fire Knight, Ice Golem, Minotaur, 4 Keeps | Stage-specific gear/accessories. Some have Hard tier. |
| Faction Wars       | 16 factions × 21 stages | Crypt items, soulstones, Glyph rewards.        |
| Demon Lord         | Easy/Normal/Hard/Brutal/NM/UNM | Chest tiers by damage; affinity rotates daily |
| Hydra              | Easy/Normal/Hard/Brutal/NM/UNM | Mythical/Divine/Celestial/Transcendent chests |
| Chimera            | Easy/Normal/Hard/Brutal/NM/UNM | Same chest model as Hydra                     |
| Doom Tower         | 120 floors × Normal/Hard       | Doom keys, frags, secret-room rewards         |
| Cursed City        | Districts × Quests             | Cursed City currency, items                   |
| Siege              | Castle/War assault             | Siege resources                               |
| Grim Forest        | Easy/Hard worlds × stages      | Foggy Forest currency, gold, treasure         |

**What we need stored** (per stage, per location):
- Reward composition (gear, silver, shards, scrolls, potions, awakening, relics, soulstones)
- Drop rates for each artifact slot/rank/rarity
- Enemy lineup per round + stat block (HP/ATK/DEF/SPD/RES/ACC/CR/CD)
- Skill rotation pattern (boss skill cycle, mob compositions)
- Stage-level modifiers (Acc/Res floor, SPD bonus, e.g. CB UNM modifiers)

`tools/refresh_static_data.py` pulls most of this from the live mod via
`/static-export` and `/alliance-bosses`/`/cb-bosses` (P1/P4 done; see
`docs/static_data_roadmap.md`).

> **Dungeon farming reference** — `docs/dungeon_farming.md` documents the
> Normal/Hard stage layouts (Hard caps at 10, NOT 20), per-dungeon set
> drops, Mythical-rarity rules (Hard-only), and farm-priority ordering.
> Read this before recommending a "best stage to farm" — older Raid
> guides reference "Hard 20" which doesn't exist and predate Hard mode.

### Battle Logger (the foundation)

Every battle the user (or PyAutoRaid) runs MUST capture:
- Per-turn turn-meter / stamina state for every champion + boss
- Active hero and skill chosen on each turn
- Buff list per champion (type, source, duration), debuff list per enemy
- HP / current_hp / max_hp / dmg_taken / dmg_dealt
- Counter-attack triggers, Unkillable saves, ally-protect events
- Boss action (AOE1 / AOE2 / Stun / Affinity-skill) + the resulting damage delta

Captured by the BepInEx mod via `/battle-state` polling + Harmony hooks.
Output: `battle_logs_cb_*.json` and similar. The dashboard's **Last Run**
panel and `tools/cb_history.py last-run` parse this format.

### Hero / Skill / Mastery Index (must be exhaustive)

We need every hero in the game (not just the user's roster), every skill,
and every mastery — exact effect IDs, multipliers, durations, books-applied
state, max-stack rules.

- `data/static/hero_types.json` — 8100 HeroType rows (ALL heroes × forms × ascend grades, base stats + leader skills + skill IDs).
- `data/static/effects.json` — 136 effect catalog (buff/debuff types, max stack, dispellable).
- `data/static/masteries.json` — 66 masteries with stat-bonus rows (the 13 stat ones); conditional masteries (Warmaster/GS/Crushing Rend/etc.) need hand-coded effect logic.
- `skills_db.json` + `skill_descriptions.json` — per-account snapshot of owned heroes' skills + book status.

**Update cadence**: re-run `tools/refresh_static_data.py` after any Raid
version bump. New heroes get auto-indexed; new skill effects need a sim
mapping (see "Skill Effect Mapping" table below).

### Computed Stats — must match the game exactly

Per-hero *Total Stats* screen breaks down into columns:

```
Basic | Artifacts | Affinity | Classic Arena | Masteries | Faction Guardians | Empowerment | Blessing | Relic | Area Bonuses | Total
```

`tools/hero_stats.py` covers Basic + Artifacts + Set Bonuses + Lore-of-Steel
+ Empowerment. **Missing**: Arena, Faction Guardians, Blessing, Relic, Area
Bonuses. The mod's `/hero-computed-stats` endpoint reads the live game's
computed values directly — that's the cross-check ground truth. Any divergence
between our calc and the mod read should be treated as a bug in our column
breakdown.

### Artifact Optimizer

Goal: assign artifacts to heroes to hit location-specific stat targets.

Examples:
- Demon Lord UNM debuffer needs **≥250 ACC**.
- Speed-tune slots need exact SPD values (e.g. Myth Eater Ninja: 246 SPD).
- Dragon 20 attacker needs **CR≥80, CD≥150, ATK%>+200%**.

Inputs:
- Vault: `all_artifacts.json` (or `data/static/...` snapshot)
- Hero base stats: `hero_types.json`
- Already-equipped (lock vs swap): `/all-heroes`
- Location targets: per-location preset (e.g. `data/targets/cb_unm.json`)

Outputs:
- Per-hero artifact assignment that maximises a scoring function under
  constraints (set bonuses, slot requirements, accessory faction lock).
- Diff vs current loadout (so the user only swaps what improves the team).

Exists today: `tools/cb_optimizer.py`, `tools/global_gear_solver.py`. Needs
extension to all locations.

### Mastery System

Each hero has 3 trees (Offense/Defense/Support) with up to 15 slots. Costs
are scrolls (Basic/Advanced/Divine — 100/600/950 per maxed hero). Per-area
recommendations differ (CB benefits Warmaster/GS, dungeons benefit different
trees). Unmastered heroes show empty + slots [Image #7].

What we need:
- Per-hero scroll inventory: `/all-resources` (already have)
- Per-hero current masteries: `/all-heroes` (already have)
- Per-area recommendation: data table + lookup (TODO)
- Programmatic apply: mod's `/open-mastery?hero_id=X&mastery_id=Y` per click
  (already implemented for individual masteries; needs a `/apply-build`
  batch endpoint)

### Auto-Run Modes

1. **Active / interactive** — user clicks Battle in the dashboard or runs `tools/cb_run.py`.
2. **N-runs of a location** — `tools/dungeon_run.py --runs 50`, the dungeon
   LoopController for the dashboard, `tools/cb_daily.py` for CB. Reads
   energy/keys before each iteration and stops on cap.
3. **Scheduled / cron** — Windows Task Scheduler entries created via
   `tools/windows_tasks.py`. The dashboard's Schedule tab is one consumer.
4. **Smart farming** (planned) — given a list of stat goals (CB ACC for
   Hero X, Dragon CD for Hero Y) and the drop-rate tables in
   `data/static/drops.json`, recommend which dungeons to farm and how
   many runs.

### Selling & Upgrading Gear

Substat upgrades happen at levels 4/8/12/16 (max 16). Main stat upgrades
every level. **Flat main stat is undesirable on Gloves/Chest/Boots** (those
slots can roll a percent main, which scales with base). Other slots
(Helmet/Shield/Weapon) are flat by definition.

Approach:
- Rules engine in `tools/sell_rules.py` — user-defined predicates per slot/
  rank/rarity/primary/substats. Rules are user-approved.
- Recommendations from `tools/sell.py preview` show what rules would catch.
- 6★ rank weighted higher; good main+substat combos weighted more for upgrades.
- Per-team / per-area need: an artifact useful to one of the user's planned
  builds is upgrade-worthy even if generic rules would mark it sellable.

### Demon Lord — Sim & Speed Tuning

Demon Lord is the headline use-case. Mechanics that make it tricky:
- HP-tier rewards: Mythical (17.57M-23.43M), Divine (23.43M-46.85M),
  Celestial (46.85M-70.28M), Transcendent (70.28M+) [Image #11/12].
- Affinity rotates daily (Magic / Force / Spirit / Void). Off-affinity
  damage is reduced (-30% on weak hits).
- HP-phase transition: below ~50% HP the Demon Lord switches to a faction
  affinity skill set. Sim must model this.
- **CB is immune to**: Stun, Sleep, Freeze, Provoke, all turn-meter
  manipulation (drain skills are full no-op vs CB; the caster does NOT
  retain "what would have been drained").
- DoT caps: Poison and HP Burn are capped per-tick on CB (prevents 5%-of-
  1.17B nukes).

Speed tuning: champions are geared so their SPD ratios cycle perfectly
against the boss. SPD buffs / TM manipulation / extra-turn skills break
these tunes — the sim has to model each champion's actual kit, not just
"hits N times". Hero-level signals to the sim:
- A1 hits + multiplier
- Active-skill cooldowns + delays + priority order
- Turn-meter modification (boost on hit, share on cast)
- Buff/debuff placements (DoTs need separate damage tick handling)
- "Breaks tune" flag for kits that are incompatible with shared-cycle tunes
  (e.g. Ninja's TM-on-burn passive)

DeadwoodJedi has done this work for ~103 tunes / 246 calc variants / 859
champion configs (`data/dwj/parsed/`). `tools/calc_parity_sim.py` is a
100%-matching port of his scheduler. The sim already gets turn order
right; **damage numbers are still off**. The remaining work is per-hero
damage modeling (multipliers, stat-scaling, set procs) which lives in
`tools/cb_sim.py` — currently calibrated to ~94% accuracy with several
compensating wrongs (see memory `project_cb_sim_calibration_state.md`).

### Architectural Principles

These guide every refactor:
- **Modularity**: each domain (sell, hero stats, CB sim, dungeon runner,
  cb history) lives in its own `tools/<feature>.py` with a CLI entrypoint.
- **Abstraction**: hide IL2CPP plumbing inside the mod; consumers see plain
  JSON. Hide live-mod fetch/cache details behind `tools/cli_util.py`.
- **Encapsulation**: module-level mutable state (caches) is owned by the
  module that defines it; cross-module access goes through a function.
- **Separation of Concerns**: HTTP routing, business logic, and game-state
  reading are different layers — don't mix in the same class.
- **DRY**: one source of truth per concept (set bonuses, faction names,
  CB constants, etc.). New duplicates are a code smell.
- **KISS**: don't catch what you can't recover from. Avoid silent `except:`.
  Don't add abstractions that don't have at least 2 consumers.
- **YAGNI**: don't write a generic framework when one concrete tool will do.
  Delete dead code rather than commenting it out.
- **Low Coupling / High Cohesion**: a module's functions belong together
  (cohesion); modules don't reach into each other's privates (coupling).

## Quick Commands

```bash
# CB battle (navigate → start → poll → log → calibrate)
python3 tools/cb_run.py --calibrate --cb-element void

# Daily CB automation (cron-ready, runs all keys)
python3 tools/cb_daily.py --wait --cb-element force

# Rebuild + redeploy mod (local)
"/c/Program Files/dotnet/dotnet" build -c Release mod/bepinex
taskkill //F //IM Raid.exe   # PlariumPlay stays up
cp mod/bepinex/bin/Release/net6.0/RaidAutomationPlugin.dll \
   "C:/Users/logan/AppData/Local/PlariumPlay/StandAloneApps/raid/build/BepInEx/plugins/RaidAutomationPlugin.dll"

# Mod fails to attach (localhost:6790 dead despite Raid running) — full PP reset
./tools/reset_pp.sh

# Full data refresh + rebuild
python3 tools/refresh_all.py --calibrate        # from live mod
python3 tools/refresh_all.py --offline           # rebuild from cached JSON

# Sim & optimization
python3 tools/cb_sim.py --team "ME,Demytha,Ninja,Geo,Venomage" --cb-element void
python3 tools/cb_sim.py --tune myth_eater --team "ME,Demytha,Ninja,Geo,Venomage"
python3 tools/cb_sim.py --list-tunes
python3 tools/cb_team_search.py --top 20
python3 tools/cb_gap_analysis.py
python3 tools/gear_gap_analysis.py                    # gear-farm priorities by set/primary/substat × area
python3 tools/gear_gap_analysis.py --area dragon --top 20
curl -s http://localhost:6790/dungeon-drops > data/dungeon_drops.json   # refresh drop tables from live game
python3 tools/global_gear_solver.py --team "ME,Demytha,Ninja,Geo,Venomage"
python3 tools/auto_profile.py --hero Venus
python3 tools/desc_profiler.py --compare

# DWJ-parity work (unified entry: tools/cb.py)
python3 tools/cb.py potential --runnable                  # DWJ tunes you can run today
python3 tools/cb.py potential --missing 1                 # 1 hero away
python3 tools/cb.py sim --slug myth-eater --turns 25      # DWJ-parity scheduler
python3 tools/cb.py sim --hash <variant_hash> --trace     # per-action TM dump
python3 tools/cb.py inspect list                          # 103 scraped tune slugs
python3 tools/cb.py inspect tune myth-eater               # variants + slot configs
python3 tools/cb.py inspect champion Ninja                # skills + effects
python3 tools/cb.py parity --hash <h> --text-file dwj.txt # diff sim vs live DWJ
python3 tools/cb.py gaps --roster-only                    # HH cross-reference
python3 tools/cb.py dungeon --dungeon dragon --stage 20 --start  # Village->battle
```

`tools/cb.py` thin-dispatches into `comp_finder`, `calc_parity_sim`,
`calc_parity_check`, `dwj_inspect`, `hh_vs_dwj`, `dungeon_run`. The
dashboard's `potential teams` + `cast timeline` panels (port 6791)
read the same data.

## CB Sim Accuracy

Calibrated to **+0.61%** vs real battle data on Magic UNM (36.36M sim avg / 36.14M real, σ=0.88M, 10 runs). The DEF mitigation formula is now extracted *literally* from `GameAssembly.dll` (see Reverse-Engineering section below).

Key mechanics:
- All fights uncapped (no FA damage caps)
- CB element defaults Void; pass `--cb-element` for day's affinity (Magic heroes do -30% vs Force)
- WM/GS: flat 75K per proc, NOT multiplied by DEF Down/Weaken
- Debuff placement: >=50% chance places immediately, <50% uses fractional accumulator
- Debuff duration: `remaining < 0` expiry (2-turn debuff lasts 2 CB turns)
- Book bonuses on debuff chances auto-applied from skills_db level_bonuses
- Desc-profiler auto-corrects all skill effects from game descriptions
- Ninja Escalation: capped at +100% ATK (5 stacks), increments per full A1+A2+A3 cycle
- Turn 50 enrage: no hero actions after final CB turn
- Geomancer passive: deflect scales with Gathering Fury + HP Burn presence
- HP Burn `StackCount: 1` (game-truth from `data/static/effects.json` Id 470) — singular, not stacking
- Sim covers 1120/1121 heroes for skills (full game roster)
- Unowned heroes: synthetic record from `hero_types.json` + best-vault-gear from optimizer

## Reverse-Engineering Methodology — game is ground truth

When sim output diverges from observed game data, the rule is:

> **Back-solving / fitting is a SIGNAL to find the literal formula in the game, not a license to embed a constant.**

### When to extract a formula

Trigger conditions:
1. Empirical fit produces a constant that "looks meaningful" (e.g., implied C drifts with input — not a true single-C formula).
2. Sim residual exceeds the calibration target (±7%) on a specific event class.
3. A new game mechanic (set, hero passive, boss skill) produces unexplained variance.

### Extraction pipeline (CB DEF formula, 2026-05-02 — gold-standard reference)

| Step | Tool | Output |
|---|---|---|
| 1. Static dump | `tools/il2cpp_dumper/Il2CppDumper.exe GameAssembly.dll global-metadata.dat dump_output/` | `dump.cs` (signatures + RVAs), `script.json` (~178MB symbol table), `il2cpp.h` (struct layouts), `DummyDll/` |
| 2. Locate method | `grep "DamageReductionByDefence" dump.cs` | RVA + file offset of the IL2CPP-compiled method |
| 3. Disassemble | Python `capstone` (`pip install capstone pefile`) | x86_64 instructions for the method body |
| 4. Resolve calls | Cross-reference `[rip + N]` targets against `dump.cs` VA listings | Helper-function names (`Fixed.op_Multiply`, `Fixed.Exp`, `EnumerateAppliedEffects`) |
| 5. Read .rdata literals | `pefile` to map RVA → file offset, `struct.unpack('<d', ...)` | Embedded double constants (e.g. `0.85`) |
| 6. Resolve struct fields | `il2cpp.h` for field offsets (e.g. `BattleHero._Stats @ 0x98`, `BattleStats.Defence @ 0x20`) | What's being read at each `[reg + N]` access |
| 7. Mod-side live capture | `mod/bepinex/RaidAutomationPlugin.cs` Harmony postfix (and prefix-postfix chains for intermediate values) | Per-call (input, output) tuples → `tick_log_*.json` |
| 8. Verify in Python | `tools/extract_def_factor.py`, `tools/derive_damage_formula.py` | Formula matches captured outputs to <0.01% |
| 9. Wire into sim | `tools/cb_constants.py` exposes `def_mitigation_factor(...)`; `cb_sim.py` imports it | Sim uses the literal function, not a back-fit |

### Scalability across game updates

| Concern | Survives game update? |
|---|---|
| **Method names** (e.g. `DamageReductionByDefence`) | ✓ Yes — Harmony patches lookup by FQN. Re-attach automatically. |
| **Method RVAs / file offsets** (e.g. `0x2CE5350`) | ✗ Will move. Re-run Il2CppDumper to get new offsets. |
| **`.rdata` literal positions** (e.g. `0x3EB9B68`) | ✗ Will move. Re-read from new dump. |
| **Static-field offsets in `Fixed`/`BattleStats`/etc.** | ✓ Stable across patches (new fields appended). |
| **Game-internal constants the formula uses** (e.g. `0.85`, `1500`) | Likely stable; if Plarium tunes them, our captures auto-detect drift |
| **Mod hook tick logs** (`def_reduction` events) | ✓ Continue to work; if a value changes, the next capture shows it |
| **Sim's hardcoded constants in `cb_constants.py`** | ⚠️ Need re-confirmation after each major patch — but the procedure is "run a battle, run `extract_def_factor.py`, compare" |

### Methodology rule of thumb — static first, decompile second

When chasing a "what's the literal value of X" question, the order is:

1. **Check `data/static/effects.json`** for any `MultiplierFormula` /
   `Amount` / `StackCount` field on the effect ID. Many "magic numbers"
   that look like they need decompile actually live in plain text:
   - Weaken = 1.25 (Id 350 `MultiplierFormula`)
   - HP Burn DoT = 0.03 × TRG_HP (Id 470)
   - Damage Reduction 15 = 0.85 (Id 510)
2. **Check `data/static/skills_all.json`** for the relevant skill's
   Effects[] block. Per-skill behavior (Geomancer Stoneguard's -15%
   team / -30% self, CB boss's DoT caps in skill 200008/200007,
   Gathering Fury formula in skill 222904) is spelled out as
   `MultiplierFormula` strings.
3. **Check `data/static/gameplay.json`** for global tuning constants
   (CrushingHitCoef, GlancingHitCoef, ElementDisadvantageCoef, etc.).
4. **Only after all three** — disassemble. Decompile is for the
   pure-arithmetic *functions* (DEF mitigation formula, hit-type
   selector); `static` is the source for *parameters*.

The IL2CPP processors (`ChangeCalculatedDamageProcessor`,
`ChangeDamageMultiplierProcessor`, `ChangeDefenceModifierProcessor`)
contain NO hardcoded multipliers — they read each value from the
status effect's `MultiplierFormula` field at runtime. So whenever
you see a hand-coded "1.25" / "75000" / "0.30" in `cb_sim.py` or
`raid_data.py`, the first move is `grep MultiplierFormula
data/static/skills_all.json` for it.

### Refresh procedure for a new game version

```bash
# 1. Re-dump
tools/il2cpp_dumper/Il2CppDumper.exe \
  "$LOCALAPPDATA/PlariumPlay/StandAloneApps/raid/build/GameAssembly.dll" \
  "$LOCALAPPDATA/PlariumPlay/StandAloneApps/raid/build/Raid_Data/il2cpp_data/Metadata/global-metadata.dat" \
  tools/il2cpp_dumper/dump_output

# 2. Run a battle to capture fresh tick log (mod auto-reattaches)
python3 tools/cb_run.py --calibrate

# 3. Extract & compare against current cb_constants.py
python3 tools/extract_def_factor.py tick_log_cb_<latest>.json
python3 tools/derive_damage_formula.py tick_log_cb_<latest>.json

# 4. If values drift, update tools/cb_constants.py + commit
```

### Skill Effect Mapping (kind → sim)

| Kind | Sim Effect | Per-Hero |
|------|-----------|----------|
| 5000 | debuff placement | All (chance from desc + books) |
| 4000 | buff placement | All |
| 4007 | extra turn | Sicia A3, Ma'Shalled A2, OB A2 |
| 5008 | extend debuffs | Sicia A1 (HP Burn only), Teodor A3 (poison+burn), others (all) |
| 9002 | activate DoTs | Ninja A2 (burns, once/skill), Sicia A2 (burns), Venomage A1 (poisons, max 2), Teodor A3 (all DoTs) |
| 7001 | ignore DEF | Ninja A3 (50%), OB A2 (30%), per desc |
| 4006 | ally attack | Fahrakin A3, Cardiel A3 (with Inc CR/CD buffs) |

## DWJ Calculator Parity

`tools/calc_parity_sim.py` is a separate, **100%-matching** Python port of
DeadwoodJedi's calc scheduler (turn-meter ticks, priority/CD/delay picking,
buff/debuff effect dispatcher). Verified action-for-action on 4 diverse
variants (Myth Eater Ninja, Myth Eater std UNM, Batman Forever, Endless
Speed). Spec lives in `docs/dwj/calc_algorithm.md`; data lives in
`data/dwj/parsed/` (103 tunes + 246 calc variants + 859 champion configs)
and `data/hh/parsed/` (1013 HellHades champion ratings).

Use `tools/cb.py` for everything DWJ-parity: `potential` (roster vs tunes),
`sim` (turn-by-turn cast timeline), `parity` (diff sim vs live DWJ text),
`inspect` (browse scraped data), `gaps` (HH cross-reference). The dashboard
(port 6791) renders the same data in `potential teams` + `cast timeline`
panels.

### How to Start CB Battle (mod API only)
```
curl /navigate?target=cb
curl /context-call?path=...AllianceEnemiesDialog/.../RightPanel&method=OnStartClick
curl /context-call?path=...AllianceBossHeroesSelectionDialog&method=StartBattle
```

## Tools

| Tool | Purpose |
|------|---------|
| `tools/cb_run.py` | One-command CB battle runner (start → poll → log → calibrate) |
| `tools/cb_daily.py` | Cron-ready daily CB (runs all keys, stores to DB) |
| `tools/refresh_all.py` | Full pipeline: fetch → rebuild DB → verify profiles → calibrate |
| `tools/cb_sim.py` | Turn-by-turn damage simulator with DWJ tune support |
| `tools/tune_library.py` | DWJ speed tune definitions (Myth Eater, Budget UK, Batman Forever, etc.) |
| `tools/desc_profiler.py` | Parse skill descriptions → auto-correct sim effects |
| `tools/auto_profile.py` | Auto-generate CB profiles for all 343 heroes |
| `tools/cb_calibrate.py` | Per-turn sim vs real battle log comparison |
| `tools/global_gear_solver.py` | Constraint + SA gear optimizer across 5 heroes |
| `tools/cb_team_search.py` | Exhaustive team evaluation (4000+ combos) |
| `tools/cb_gap_analysis.py` | Hero gap analysis (roster + pull priority) |
| `tools/db_init.py` | SQLite database builder (pyautoraid.db) |
| `tools/refresh_data.py` | Fetch heroes/artifacts/skills from mod API |
| `tools/cb.py` | Unified CLI for DWJ-parity work (potential / sim / parity / inspect / gaps) |
| `tools/calc_parity_sim.py` | DWJ-parity turn scheduler (100% match, 4/4 variants tested) |
| `tools/comp_finder.py` | Score 103 DWJ tunes against owned roster (runnable / N-away) |
| `tools/dwj_inspect.py` | Browse scraped DWJ tunes, variants, champions |
| `tools/calc_parity_check.py` | Diff sim cast order vs live DWJ rendered text |
| `tools/hh_vs_dwj.py` | HellHades cross-reference (gap finder, roster snapshot) |
| `tools/scrape_dwj.py` / `scrape_dwj_calc.py` | DWJ WordPress + calculator scrapers |
| `tools/scrape_hellhades.py` | HH WordPress scraper (champions + tierlist + posts) |
| `tools/dashboard_server.py` | HTTP dashboard server (port 6791) |
| `tools/loadouts.py` | SQLite-backed artifact loadout snapshot / apply / restore |
| `tools/hh_picker.py` | HH-driven team picker + per-hero stat targets + greedy gear picker (emits farm_cycle plans) |
| `tools/farm_cycle.py` | Orchestrator: plan/prepare (snapshot → equip → preset), restore, status, run |
| `tools/m5_recommender.py` | **M5** per-location team recommender (`--location`, `--builds`, `--pool all`); see `docs/m5_recommender_guide.md` |
| `tools/m5_build_recommender.py` | M5 per-hero build (masteries/blessing/stats) + ACC-floor readiness vs `/hero-computed-stats` |
| `tools/m5_roster_gaps.py` | M5 "what to pull/build next" per location (hard gaps, thin axes, best unowned upgrades) |
| `tools/m5_synergy_graph.py` | M5 cross-hero provides/needs tags from game-truth skill descriptions |
| `tools/m5_stat_targets.py` | M5 game-truth ACC floors (boss RES) + boss stat modifiers per stage |
| `tools/m5_inventory.py` / `m5_hero_catalog.py` | M5 universe inventory + per-hero CB sim coverage |
| `tools/m5_mastery_tagger.py` / `m5_blessing_tagger.py` | M5 mastery/blessing relevance × 12 locations |
| `tools/extract_blessing_procs.py` | M5 game-truth blessing proc formulas (grade-by-grade) via authoritative skill link |
| `tools/cb_attribution_diff.py` | per-hero/per-source damage diff (real tick log vs sim) for calibration |
| `tools/gear_target_optimizer.py` | **M6** generalized per-champion gear optimizer — per-stat min/max/importance + modes, any location, set-aware (HellHades-parity flagship) |

## Data Files

| File | Content |
|------|---------|
| `heroes_all.json` | 482 heroes with stats, artifacts, masteries |
| `all_artifacts.json` | 2684 artifacts (equipped + vault) |
| `skills_db.json` | 1370 skills with effects + descriptions |
| `skill_descriptions.json` | Game-localized skill text for 321 heroes |
| `hero_profiles_game.json` | 137 game-extracted skill profiles |
| `hero_computed_stats.json` | Game-computed stats for 511 heroes |
| `account_data.json` | Great Hall, Arena, Clan level |
| `pyautoraid.db` | SQLite with all data unified |
| `battle_logs_cb_*.json` | Per-turn battle telemetry |
| `data/dwj/parsed/tunes.json` | 103 DWJ tunes with slot configs |
| `data/dwj/parsed/calc_tunes.json` | 246 calculator variants (hash-keyed) |
| `data/dwj/parsed/calc_champions.json` | 859 champion configs (skills + effects) |
| `data/hh/parsed/champions.json` | 1013 HellHades champion metadata + sets |
| `data/hh/parsed/tierlist.json` | 1013 HH tier ratings (CB / overall / etc.) |
| `docs/dwj/calc_algorithm.md` | Reverse-engineered DWJ scheduler spec |

## Reference IDs

**Slots**: 1=Helmet, 2=Chest, 3=Gloves, 4=Boots, 5=Weapon, 6=Shield, 7=Ring, 8=Amulet, 9=Banner
**Stats**: 1=HP, 2=ATK, 3=DEF, 4=SPD, 5=RES, 6=ACC, 7=CR, 8=CD
**Effects**: Poison=80, HPBurn=470, DEFDown=151, Weaken=350, Unkillable=320, DecATK=131, Leech=460, PoisonSens=500
**Masteries**: Format `500XYZ` (X=tree, Y=tier, Z=col). Warmaster=500161, Lore of Steel=500343
**Full mappings**: `tools/gear_constants.py`, `tools/status_effect_map.py`

## BepInEx Mod

HTTP API on port 6790. Key endpoints: `/status`, `/all-heroes`, `/all-artifacts`, `/skill-data`, `/skill-texts`, `/navigate`, `/context-call`, `/battle-state`, `/battle-log`, `/equip`, `/presets`, `/buttons`, `/click`.

Build & deploy: see Quick Commands above (dotnet build → kill Raid.exe → copy DLL).

### Launching Raid (mod-attached)

Standard invocation (used by `Modules/base.py:open_raid`):
```bash
"$LOCALAPPDATA/PlariumPlay/PlariumPlay.exe" --args -gameid=101 -tray-start
```
PP launches Raid; doorstop's local `winhttp.dll` hooks; BepInEx loads `RaidAutomationPlugin.dll`; mod binds `localhost:6790`. Verify: `curl localhost:6790/status` → `{"logged_in":true,"scene":"Village",...}`.

**Mod URL**: listener prefix is `http://localhost:6790/` — `127.0.0.1:6790` returns HTTP.sys "Invalid Hostname".

**Normal redeploy** (mod-only changes): `taskkill /F /IM Raid.exe` → copy DLL → relaunch via PP command above. PP stays up; you keep the session.

### Recovery: mod fails to attach

Symptom: Raid runs but `localhost:6790` is dead, or BepInEx log mtime doesn't update on launch, or `Get-Process -Module` shows local `winhttp.dll` loaded but no `BepInEx\*` modules.

Cause: PlariumPlay session can wedge (often visible as 6+ stale `PlariumPlay.exe` processes). Wedged PP launches Raid in a state where doorstop hooks but BepInEx core never initializes.

Fix — full PP reset:
```bash
taskkill //F //IM Raid.exe
taskkill //F //IM PlariumPlay.exe         # kills all PP.exe instances
taskkill //F //IM PlariumPlay.NetHost.exe # broker
# Leave PlariumPlayClientService.exe alone (Windows service)
"$LOCALAPPDATA/PlariumPlay/PlariumPlay.exe" &
sleep 8
"$LOCALAPPDATA/PlariumPlay/PlariumPlay.exe" --args -gameid=101 -tray-start
```
Re-login may be required in the PP window. After Raid is in-game, expect ~218 DLLs from `raid/build` and ~157 BepInEx assemblies in the Raid process — that's the "healthy" mod-attached state.

**`NEVER kill PlariumPlay`** for normal mod redeploy (breaks session, costs a re-login). Only do the full PP reset when the mod fails to attach despite Raid launching.

## Key Rules

- **NEVER use screen automation** for game actions — mod API only
- Rings/Amulets cannot roll SPD substats
- Accessories are faction-locked
- `ArtifactKindId` 1 = Helmet (NOT Weapon)
- Fixed-point encoding: **32.32** (raw >> 32)
- Equip from vault unreliable — swap between heroes instead
