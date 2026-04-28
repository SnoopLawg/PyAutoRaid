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

**Phase 5 — TuneLab UI (~1 session)**
- The Heroes tab's "Gaps" sub-tab gets a sibling "TuneLab" sub-tab.
- Lists all 103 DWJ tunes with: blocker/todo counts, sim damage (if
  runnable), affinity tag.
- Click a tune → drill panel: blocker/todo list, team, preset, gear plan
  (with current vs recommended), cast timeline.

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

## Open questions to resolve before phase 2

1. **Mastery truth source.** The mod's `/mastery-data` returns mastery
   IDs per hero — does it also return the *effects* of each mastery, or
   only IDs? If only IDs, we need a separate data source for the effects
   (the in-game mastery descriptions, scrapeable via the mod or an
   existing source).
2. **Blessing truth source.** Same question for blessings — do we have a
   data file with blessing→effect mapping, or do we need to build one?
3. **Gear optimizer for tune speeds.** `tools/gear_optimizer.py` already
   does optimal assignment for a CB hero at a target SPD. Confirm it can
   accept multiple heroes simultaneously (currently per-hero).
4. **Calc variant selection.** When a tune has UNM/NM/Brutal/UNM-Spirit
   variants, which do we use for sim purposes? Default to the variant
   matching today's affinity; fall back to UNM.

Resolution of these blocks the start of phase 2.
