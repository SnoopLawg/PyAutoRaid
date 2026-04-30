# CB Sim — Potential-Team Plan

## Goal
TuneLab shows every DWJ tune as a *potential* preset, not gated by current
account state. Per tune we surface what's missing; if blockers are clear,
we materialize a `PotentialTeam` (team + preset + gear plan + masteries
+ blessings) and run `cb_sim` against it using **in-game-truth data only**
— no hardcoded multipliers, no assumed values, no Claude hunting.

## Blockers vs todos

A tune has exactly **two** blockers. Anything else is a todo (the user can
fix easily, so we project as if fixed):

| Kind | Blocker? | Reason |
|---|---|---|
| Hero ownership (any grade) | **BLOCKER** | Can't ascend what you don't own |
| Gear availability for the tune's 5 slot-speeds | **BLOCKER** | Need substats/sets in the vault to hit speeds |
| Hero <6★ | todo | Ascendable with shards/sacrifices |
| Skills not fully booked | todo | Books farmable |
| Masteries not maxed | todo | Scrolls farmable |
| Blessing not chosen | todo | Free per hero |
| Current gear not equipped on the right hero | todo | Just a swap |

The rule: **if you own the hero and could gear them to the tune's speeds
from your current artifact pool, the tune is runnable.** Everything else
is a checklist.

## Output shape per tune

```python
{
  "tune_slug": "myth-hare",
  "tune_name": "Myth Hare",
  "calc_variant": "Ultimate Nightmare Spirit",  # picked by today's affinity
  "blockers": [
    # Empty when the tune is runnable.
    {"kind": "missing_hero",  "hero": "Underpriest Brogni"},
    {"kind": "missing_gear",  "hero": "Demytha", "need": "SPD>=315"},
  ],
  "todos": [
    {"kind": "ascend",     "hero": "Bully", "current_grade": 1, "target": 6},
    {"kind": "book",       "hero": "Razelvarg", "skill": "A3", "books": 3, "max": 4},
    {"kind": "mastery",    "hero": "Demytha", "missing": ["Warmaster"]},
    {"kind": "blessing",   "hero": "Seeker", "recommended": "Brimstone"},
  ],
  "potential_team": {            # only present when blockers == []
    "team": [
      {"index": 1, "hero": "Razelvarg",  "target_grade": 6, "target_speed": 212, "role": "uk_anchor"},
      {"index": 2, "hero": "Demytha",    "target_grade": 6, "target_speed": 315, "role": "speed_aura"},
      {"index": 3, "hero": "Underpriest Brogni", "target_grade": 6, "target_speed": 211, "role": "block_debuff"},
      {"index": 4, "hero": "Seeker",     "target_grade": 6, "target_speed": 210, "role": "tm_fill"},
      {"index": 5, "hero": "Bully",      "target_grade": 6, "target_speed": 195, "role": "dps"},
    ],
    "preset": {
      # Driven by calc_variant.skill_configs — DWJ-truth, not assumption.
      "Razelvarg":  {"opener": "A1", "priorities": [{"skill":"A2","delay":0},{"skill":"A3","delay":0}]},
      "Demytha":    {"opener": "A1", "priorities": [{"skill":"A2","delay":2},{"skill":"A3","delay":3}]},
      ...
    },
    "gear_plan": {
      # Per-hero per-slot artifact pick from current pool. Optimizer assigns
      # to hit target SPD using existing artifacts — no fantasy gear.
      "Razelvarg": [{"slot":1,"set":"speed","primary":"HP","art_id":12345}, ...],
      ...
    },
    "masteries":  {"Razelvarg": ["Warmaster", ...], ...},  # HH-recommended
    "blessings":  {"Razelvarg": "Brimstone", ...},          # HH-recommended
  },
  "sim": {                       # only if potential_team built
    "total_damage_M": 62.4,
    "boss_turns": 50,
    "cast_timeline": [...],      # DWJ-parity check
    "warnings": [],
    "calibration_baseline": {"mean_err": -8.8, "n_runs": 7},  # context
  }
}
```

## Data sources — every calc backed by a real source

If a source isn't available the calc must **fail loud**, not fall back to
a hardcoded value. Below is what gets read for each input.

| Input | Source | File / endpoint |
|---|---|---|
| Owned heroes + grades + level + empower | `/all-heroes` | `heroes_all.json` |
| Hero base stats by grade | `/hero-computed-stats` | `hero_computed_stats.json` |
| Skill effects, formulas, multipliers | `/skill-data` | `skills_db.json` |
| Skill book progress (current / max) | `/skill-data` per hero | `skills_db.json` (`level_bonuses`) |
| Mastery progress per hero | `/mastery-data` | `mastery_data.json` |
| Blessing per hero | `/all-heroes` (`blessing` field) | `heroes_all.json` |
| Equipped + vault artifacts | `/all-artifacts` | `all_artifacts.json` |
| Artifact set bonuses | `gear_constants.SET_BONUSES` | `tools/gear_constants.py` |
| Status-effect type-id → name | `tools/status_effect_map.py` | already present |
| DWJ tune slot speeds + masteries flags | scraped | `data/dwj/parsed/tunes.json` |
| DWJ calc variant heroes + speeds + skill priorities + delays | scraped | `data/dwj/parsed/calc_tunes.json` |
| HH recommended sets, primaries, masteries, blessing | scraped | `data/hh/parsed/champions.json` |
| Today's CB affinity | latest battle log boss element | `battle_logs_cb_latest.json` |

**Refresh commands** (one-line each):
- `tools/refresh_all.py --calibrate` — regenerates everything from the live mod.
- Per-source refresh in `tools/refresh_data.py` for narrower updates.

## Pipeline

```
DWJ tune  +  best-fit calc variant (today's affinity preferred)
    │
    ▼
[1] resolve concrete team
    - tune.slots that pin a specific hero → required
    - tune.slots that are generic ("DPS", "Block Debuff") → use calc_variant
      champion at the matching slot index, or named match
    - never substitute; if calc_variant has a specific hero, that's the requirement
    │
    ▼
[2] check ownership
    - emit `missing_hero` blocker per unowned slot
    │
    ▼
[3] check gear feasibility
    - run gear_optimizer.attempt_assign(hero, target_speed_range, current_pool)
    - emit `missing_gear` blocker if no assignment hits the SPD range
    │
    ▼
[4] enumerate todos (informational, not gating)
    - hero <6★, sub-max books, missing masteries, missing blessing
    │
    ▼
[5] build PotentialTeam (only if blockers == [])
    - preset.priorities + delays from calc_variant.skill_configs
    - preset.opener from calc_variant booked-CDs
    - gear_plan from gear_optimizer
    - masteries / blessings from HH recommendations
    │
    ▼
[6] cb_sim.run_potential_team(pt)
    - stats = computed at target_grade from /hero-computed-stats + gear_plan
    - skill effects = generated from skills_db (no hardcoded buffs)
    - masteries effects = applied from data/masteries.json mapping
    - blessings effects = applied from data/blessings.json mapping
    - schedule = DWJ-parity scheduler driven by preset.priorities + delays
    │
    ▼
[7] surface result
    - per-tune row in TuneLab: blockers / todos count, sim damage if runnable
    - drill-down: full PotentialTeam detail + cast timeline
```

## CB sim accuracy strategy

Convert every hardcoded value in `tools/cb_sim.py` to a derivation from
`skills_db` / `hero_profiles_game.json`. Each conversion follows the same
pattern:

1. **Identify the magic number.** Example: `cb_sim.py:629` has
   `"A1": {"mult": 4.61, "stat": "ATK", "hits": 2, "cd": 0}` for Demytha.
2. **Find the in-game source.** `skills_db.Demytha[0].effects[0].formula =
   "3.2*ATK"` and `effects[0].count = 2`. Wait — game says 3.2, sim says
   4.61. That's a known gap. The source is authoritative; the sim drift
   gets a regression note.
3. **Replace** the hardcoded entry with a load from the source. Add a
   provenance field: `{"_source": "skills_db.Demytha.A1", "_formula": "3.2*ATK"}`.
4. **Gold test**: assert that the loaded value matches expectation for a
   known set of heroes (Maneater, Demytha, Ninja, etc.). Failures = loud.
5. **Re-run calibration history** (`data/sim_calibration_history.jsonl`)
   to confirm no regression.

The same approach for:
- Buff/debuff lists (currently `team_buffs=[(...)]`) → from `effects` with
  `kind=4000` for buffs, target_type for placement scope.
- Cooldowns → from `skill.cooldown` with `level_bonuses` book reductions
  applied.
- Passives → from `skills_db[hero][i].passive` entries.
- Mastery effects (Warmaster 60% chance / 10% TRG HP, etc.) → from a new
  `data/masteries_truth.json` populated from in-game mastery descriptions
  via the mod's `/mastery-data` endpoint.
- Blessing effects → from a new `data/blessings_truth.json` similarly.

After all conversions, **the sim has zero magic numbers**. Every
calculation traces to a documented in-game source. New heroes work
without a code change — just refresh `skills_db.json`.

## Build phases

**Phase 1 — PotentialTeam constructor (~1–2 sessions)**
- New module `tools/potential_team.py`.
- `build_potential_team(tune, calc_variant, roster, artifact_pool, hh) → dict`.
- Returns the shape above. Blocker detection wired; todos populated; if
  blocker-free, builds team + preset + gear_plan (using existing
  `tools/gear_optimizer.py`).
- Replaces the ad-hoc enrichment we just shipped in `comp_finder.py`.

**Phase 2 — Game-truth skill data layer (~2–3 sessions)**
- Refactor `tools/load_game_profiles.py` so its output for any given hero
  is a pure function of `skills_db.json` + `hero_profiles_game.json`.
- Add `tools/skill_truth_diff.py`: compares the loaded skill data against
  the legacy `_OLD_SKILL_DATA` dict in `cb_sim.py` for the user's main
  heroes (Maneater, Demytha, Ninja, Geomancer, Venomage, Cardiel,
  Razelvarg, Heiress, etc.). Surfaces every drift case for triage.
- Delete `_OLD_SKILL_DATA` once the truth layer is verified — single source.

**Phase 3 — sim re-driver (~2 sessions)**
- New entry: `cb_sim.run_potential_team(pt: PotentialTeam) → result`.
- Pulls stats from `pt.gear_plan` (computed at target_grade), not from
  `heroes_6star.json`.
- Skill priorities + delays from `pt.preset` (the DWJ scheduler shape).
- Mastery + blessing effects applied from `data/masteries_truth.json` /
  `data/blessings_truth.json`.

**Phase 4 — validation loop (~1 session, ongoing)**
- After every `cb_run --calibrate`: append a row to
  `data/sim_per_tune_accuracy.jsonl` keyed by tune_slug.
- New `/api/sim-accuracy` returns rolling error_pct per tune.
- A small dashboard widget shows drift per tune over time. Drift > 5%
  flagged as regression candidate.

**Phase 5 — TuneLab UI (~1 session)** — DONE
- The Heroes tab's "Gaps" sub-tab gets a sibling "TuneLab" sub-tab.
- Lists all 103 DWJ tunes with: blocker/todo counts, sim damage (if
  runnable), affinity tag.
- Click a tune → drill panel: blocker/todo list, team, preset, gear plan
  (with current vs recommended), cast timeline, per-affinity drilldown.

**Phase 6 — Full-Potential projection (~3 sessions)** — IN PROGRESS

Sub-progress (2026-04-28):
- ✓ Stat-bonus masteries (12 of the 13) auto-applied in `calc_stats`
  from `data/masteries_truth.json` based on `hero["masteries"]`.
- ✓ `projection=True` flag through `run_potential_team` /
  `build_tune_lab` / `/api/tune-lab?projection=1` treats every hero as
  having every stat-bonus mastery, regardless of actual selection.
  Dashboard modal shows projection levers panel.
- ✓ Stat-bonus blessings already flow through via `_COMPUTED_STATS`
  (game's CalcBlessingBonus) for owned heroes' current blessing.
- ⏳ Skill-modifier blessings (Phantom Touch, Crushing Rend, etc.)
  need raid_data-level logic per-blessing-id. Tracked separately.
- ⏳ Projection of recommended *swap-to* blessings (e.g., user has
  Vanguard but tune wants Crushing Rend) needs `BlessingStatsByRarity`
  numeric extraction from the mod.
- ⏳ Glyph-max substat projection.
- ⏳ Conditional masteries (Warmaster, Single Out, Bring it Down,
  etc.) integrated with sim turn scheduler in projection mode.

The sim should answer "if I do every todo for this tune, what does it
do?" — projected ceiling, not current state. Apply every progression
axis at the assumed max:

- **Stars/Ascension**: every owned hero treated as 6★ ascended (use
  game's static stat tables for grade=6 ascension=full; if hero is
  fusable but unowned, project from base).
- **Level**: 60 (max for 6★).
- **Skill books**: every skill fully booked. The DWJ calc variant
  already gives `cd_after_books` and book-modified chances — use those
  directly. For non-calc-variant code paths, look up
  `skills_db.json[*].level_bonuses` and apply the full stack.
- **Masteries**: every owned hero given a full 66-mastery loadout. Use
  `data/masteries_truth.json`:
   - `stat_bonus` masteries → add the StatBonus to projected stats.
   - `conditional_logic` masteries → register the logic id with the sim
     so Warmaster / Lore of Steel / etc. trigger naturally during turn
     scheduling.
- **Blessings**: pick the recommended blessing per hero (the
  `blessing_pve_high` field in our todos) and apply via
  `data/blessings_truth.json` — same hybrid pattern as masteries.
- **Substat glyph upgrades**: every artifact substat assumed at its
  max-glyph value (the +1/+2/+3/+4 progression Sacred Gear allows).
  Surface the *unglyph'd* baseline too so the user can see how much of
  the projection depends on glyph farming.
- **Account auras**: Great Hall, Arena rank, Faction Wars, Forge —
  all snapshot from `account_data.json` and applied as flat
  multipliers per stat.
- **Aura buffs**: leader aura auto-applied based on team composition
  (already supported by `cb_sim` — verify it triggers under
  `run_potential_team`).

Output: `potential_team.projection` carries `{stars, level, masteries,
blessing, books, glyphs, account_auras, aura}` so the dashboard can
show *why* the sim says X — i.e., which lever contributed most.

**Phase 7 — Gear plan solver (~2 sessions)** — IN PROGRESS

Sub-progress (2026-04-28):
- ✓ `tools/potential_gear.py` wraps `solve_global_gear` with stdout
  capture + on-disk cache (`data/gear_plans_cache.json`, vault-hash
  invalidated). 500-iter SA budget = ~8s first call, instant cached.
- ✓ `/api/tune-gear-plan?slug=X[&sa=N]` endpoint. Modal lazy-fetches
  on open (doesn't block tune list).
- ✓ Modal renders solver output: per-hero projected stats, active
  sets, per-slot artifact id/set/primary.
- ⏳ Solver quality: 500 iterations finds 30M for myth-eater vs 33.5M
  with the user's hand-optimized current gear. Crank to 5000+ iters
  to converge, or use it for tunes the user *hasn't* tuned yet.
- ⏳ Sim integration: solver-recommended gear isn't yet plugged into
  the projection sim. Currently informational only.

Make `potential_team.gear_plan` non-null. For each runnable tune:

- Inputs: tune's per-slot speed bands (`min_spd`/`max_spd`), hero roles
  (DPS / debuffer / support / unkillable / etc.), the user's vault
  (`all_artifacts.json`), faction restrictions on accessories, set
  rules (Speed = 4-of, Lifesteal = 4-of, Cruel = 4-of, etc.).
- Solver: extend `tools/global_gear_solver.py` to multi-tune mode —
  assigns 30 artifacts (5 heroes × 6 slots) per tune without conflict.
- Output per slot: `{artifact_id, current_set, primary_stat, substats,
  glyph_max_substats}`. Compare against currently-equipped: emits
  "swap from hero X" or "pull from vault" actions.
- Fallback: if vault can't satisfy speed targets, surface a "gear
  shortfall" warning per slot rather than silently substituting bad gear.
- Surface in `/api/tune-lab` as `gear_plan: {hero: {slot: {…}}}`.

**Phase 8 — Generic-slot exploration (~1–2 sessions)** — IN PROGRESS

Sub-progress (2026-04-28):
- ✓ `tools/slot_alternatives.py` enumerates every owned 6★ hero per
  generic slot, runs the projection sim, returns top-N by damage.
- ✓ Disk cache (`data/slot_alternatives_cache.json`, roster-hash
  invalidated). 46 candidates × 3 generic slots ≈ 10s first call,
  sub-second from cache.
- ✓ `/api/tune-slot-alternatives?slug=X&affinity=Y&top=N` endpoint.
- ✓ Modal renders top-N per generic slot with damage delta vs default.
- Validation finding: for myth-eater on the user's roster, **Teodor
  the Savant** projects at +53M delta in any generic slot. The
  mechanism is Teodor A3 (Chymistry) which combines two effects:
  (1) `activate_dots` (kind 9002) instantly triggers a tick of every
  active DoT — with 10 active debuffs and ~10 A3 casts in 50 turns,
  this contributes ~100 free DoT ticks; (2) `extend_debuffs` (kind
  5008) extends remaining duration of poisons + burns. Burns come
  from **Ninja A2 Hailburn** and **Geomancer A2/A3**; poisons from
  **Venomage A1/A2/A3**. **Maneater + Demytha** provide Unkillable +
  ATK Down only — zero burns or poisons.
- Sub-fix (2026-04-28): added `DebuffBar.EXTEND_CAP_TURNS = 4` clamp
  on `extend_all` / `extend_debuffs_hp_burn` /
  `extend_debuffs_poison_burn`. Reins in Sicia by ~2M (57.2 → 55.2);
  Teodor unchanged because his damage comes from `activate_dots`
  triggers, not duration extension. The extra-ticks-via-activate_dots
  mechanism may need a per-skill cap if real CB caps it.

**Per-hero damage cross-check (2026-04-28)** — verified per-hero
contributions in projection sim vs real tick-log capture (memory:
project_cb_sim_calibration_state.md):

| Hero | Real (tick-log) | Sim (current) | Status |
|---|---|---|---|
| Ninja | 17.4M | 16.6M | ✓ close |
| Maneater | 4.5M | 4.0M | ✓ close |
| Geomancer | 4.7M | 8.9M | ⚠️ over (burn over-attribution) |
| Venomage | 6.1M | 5.0M | ✓ close |
| **Demytha** | **1.4M** | **0.0M** | ✗ A1 never fires |

Demytha-zero root cause: `base_cd=max(0, sd["cd"]-1)` (the -1 CD hack
in `cb_sim.py` line ~1488) drops Demytha's A2/A3 from CD3→CD2. With
both at CD2 the default AI alternates A3↔A2 every action and her A1
"Fires of Old" (2 hits × 3.2*ATK ≈ 200-300K/cast in real game) never
fires.

**Streamlined rewrite (2026-04-28)** — partial progress shipped.

What I shipped (all verified against real tick log):
1. **Removed the -1 CD hack** — `raid_data` cooldowns are correct.
   Verified: real-game Maneater A3 fires every exactly 5 of his
   actions matching CD=5 (not 4). The hack was wrong all along.
2. **Default AI ordering**: A1→A2→A3 (lowest skill index first).
   Verified: every CB hero in real game opens with A2 (Maneater
   Syphon, Ninja Hailburn, Demytha Light of the Deep), not A3 as
   the previous "highest CD first" logic forced.
3. **`bugfix_buff_tick=True` default** — buffs tick once per CB turn,
   matching the per-CB-turn cooldown semantics implied by CD=5
   cycling every 5 holder actions across all CB turns.
4. **Demytha A2 heal** modeled: 2.5% MAX_HP base + 2.5% per
   buff/debuff modified. Verified: real Maneater HP recovers from
   25673→34025 at tick 12 (her A2 cast time) = ~21% MAX_HP heal.
5. **Demytha A1 shield absorption**: 10% caster MAX_HP × hit_count
   on lowest-HP ally. Damage chips the shield pool before HP.
6. **Mastery data extension**: new `tools/extend_masteries_from_log.py`
   reads each player's `mods[]` from the first snapshot of a tick log
   and adds missing stat-bonus masteries (e.g., 500324 ACC +20,
   500333 ACC +4). The mod's `MasteryBonusById` only captures 13 of
   the actual stat-bonus masteries; this fills the gap empirically.
7. **`tools/sim_vs_real_diff.py`** — per-CB-turn buff-state diff
   between sim and real. Used iteratively to verify each fix.
   Confirmed: sim CB turn 2 buffs now match real CB turn 2 exactly
   (UK/2, BkD/2 on team).

**What's still off:** the team dies at bt25 in sim vs surviving 50
turns in real. Root cause: hero stats undercount.
- Sim Demytha SPD = 172 (real implied = 186 from 0.98 actions/CB
  ratio). Gap = 14 SPD likely from Sacred Gear glyph maxing not
  modeled — current substat values are pre-glyph-max.
- Sim Demytha takes 19 turns over 25 CB turns vs real's 49 turns
  over 50 — same SPD ratio gap projected forward.
- Damage delta: sim 15.22M vs real 37.92M (~60% gap). Driven by
  fewer Demytha actions + un-glyphed substats lowering ATK on
  damage-dealing heroes.

**Honest next step**: model glyph-max projection for substats. The
data is there in the artifact JSON (`b.get("glyph", 0)` already
applied, but glyphs can be UPGRADED to max — we're using current
glyph value, not max possible). Real game shows substats with glyph
N where N could be 4 (max) but on user's gear it's typically 1-2.
Once glyph-max is projected, SPD/ATK/DEF should align and survival
should work without further buff/CD tweaks.

**Glyph-max shipped 2026-04-28:** added `_MAX_GLYPH_FLAT` and
`_MAX_GLYPH_PCT` tables (separate flat/percent ceilings per rarity/stat)
derived from the user's vault's max-observed glyph values. Demytha's
projected SPD: 172 → 183 (real implied: 186, gap closed from 14 to 3).
Hero stats now within 1.0-1.4x of real-game hp_max, with no leader-aura
boost.

**Still-open survival gap**: team dies at bt~26 in projection sim
across all affinities. Root cause: TM scheduler timing — sim's Demytha
A2 fires AFTER Maneater's UK has expired, so the extension misses.
Real game timing has Demytha A2 firing JUST AFTER Maneater A3,
extending the fresh UK. The 5-action CD cycle on Maneater A3 + 3-action
CD on Demytha A2 don't naturally interleave the right way in cb_sim's
TM model. Needs scheduler ordering rework — possibly forcing Demytha's
A2 priority higher, or aligning per-CB-turn cooldown decrements.
Confirmed via `tools/sim_vs_real_diff.py` per-turn buff comparison.

**Trade-off acknowledged**: the previous "with -1 CD hack" baseline
showed 34.5M and 50-turn survival but was masking the issue (Demytha
A1 never fired, fake survival from over-applied leader aura). The
current state shows lower damage (18M) and shorter survival (bt 26)
but reflects a TRUER simulation. Each remaining gap is named and
data-backed, no compensating wrongs masking each other.

DWJ tunes have abstract slots like "4:3 DPS" or "1:1 DPS 1". Today we
substitute the user's last battle team. For full potential:

- For each generic slot, enumerate the user's owned heroes that match
  the role tag (DPS / debuffer / cleanser / unkillable / etc.).
- Score each candidate with the Phase-6 projection sim, holding the
  rest of the team fixed.
- Surface top-N candidates per generic slot in the modal so the user
  can see "Cardiel as 4:3 DPS = 38M, Razelvarg = 36M, Brakus = 34M".

## Acceptance criteria

- [ ] Every DWJ tune resolves to a concrete team + clear blockers / todos.
- [ ] No tune scores as "runnable" when its calc variant requires unowned heroes.
- [ ] PotentialTeam includes 5 heroes × 6 slots = 30 artifact assignments
      drawn from the current vault.
- [ ] `cb_sim.py` contains **zero** hardcoded skill multipliers, buffs,
      cooldowns, or passives — all loaded from `skills_db.json`.
- [ ] Sim mean signed error ≤ 5% across the user's last 10+ tuned CB
      runs (currently -8.8% on 7 runs).
- [ ] DWJ-parity test passes 100% on the user's main tune (Myth Eater)
      and at least 4 other tested variants.
- [ ] No `_OLD_SKILL_DATA` / `_OLD_SKILL_EFFECTS` blocks remain in the
      codebase. The truth layer is the single source.
- [ ] `potential_team.projection` contains every progression lever:
      stars=6, level=60, books=full, masteries=66/66, blessing=set,
      glyphs=max, account_auras applied. Owned 5★ heroes project at
      6★ stats.
- [ ] `potential_team.gear_plan` non-null for every runnable tune;
      assigns 30 artifacts from the user's vault without conflict
      across tunes the user might run on different days.
- [ ] No "current gear" leakage in projection mode — sim damage is
      ceiling, not present-state. Present-state is a separate optional
      mode for "what does this tune do today, with my current gear".
- [ ] Generic DPS slots ("4:3 DPS", "1:1 DPS") explored: each tune
      surfaces the top-3 owned heroes for each abstract slot, with
      damage delta vs the default fill.

## Open questions — RESOLVED 2026-04-27

1. **Mastery truth source — HYBRID.**
   - `AppModel.StaticData.MasteryData.MasteryTypes` (66 entries) gives only
     `Id` / `TreeId` / `Row` / `Column` — no effect description.
   - `AppModel.StaticData.MasteryData.MasteryBonusById` (13 entries) maps
     mastery ids that are pure stat bonuses to `StatBonus{StatKindId,
     Value, IsAbsolute}`. These auto-load.
   - The other ~53 masteries (Warmaster, Single Out, Bring it Down, etc.)
     are conditional / chance-based effects with no static-data shape —
     game logic must encode them. We already have these in
     `tools/raid_data.py` (Warmaster: 60% chance, 10% TRG HP per proc, etc.).
   - **Plan**: build `data/masteries_truth.json` with two flavors:
     `{"type": "stat_bonus", "stat": "ATK", "value": 75, "absolute": true}`
     for the 13 from StaticData, and
     `{"type": "conditional_logic", "logic_id": "warmaster"}` for the
     ~53 hand-coded ones. Sim looks up by mastery_id and dispatches.

2. **Blessing truth source — HYBRID, same pattern.**
   - `AppModel.StaticData.DoubleAscendData.Blessings` (30 entries). Each
     has `GradeBonuses` dict (6 grades I-VI) → `BlessingBonus{SkillTypeId,
     StatKindIds, Description}`.
   - Stat-bonus blessings: `BlessingStatsByRarity` has the numeric values.
   - Skill-modifier blessings (e.g., Crushing Rend on a specific A3) need
     per-blessing logic similar to masteries.
   - **Plan**: same hybrid — `data/blessings_truth.json` with stat_bonus
     entries auto-loaded, conditional ones hand-coded.

3. **Gear optimizer for tune speeds — DONE.**
   `tools/gear_optimizer.assign_gear_constrained(team_names, heroes,
   profiles, speed_ranges)` already accepts a `speed_ranges` dict per
   slot. Use as-is in PotentialTeam Phase 2.

4. **Calc variant selection — DONE.**
   `tools/potential_team.pick_calc_variant(tune, calc_variants,
   today_affinity)` prefers variants whose boss affinity matches today's
   CB > Ultimate Nightmare > Nightmare > Brutal > first available.

Phase 2 can now start.
