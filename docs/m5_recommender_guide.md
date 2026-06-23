# Milestone 5 — Recommender suite (usage guide)

The M5 engine answers, for **every location** (not just CB): *what team should
I bring, how do I build each hero, are my heroes ready, and what should I pull
or farm next?* Everything is grounded in game-truth (skill descriptions, static
data, the live `/hero-computed-stats` endpoint); HellHades ratings are an
additive signal, never authoritative.

## The data layer (regenerate after a Raid patch)

| File | Tool | What it holds |
|---|---|---|
| `docs/m5_phase1_inventory.md` | `m5_inventory.py` | universe inventory (heroes/skills/masteries/blessings/sets/locations) |
| `data/m5_hero_catalog.jsonl` | `m5_hero_catalog.py` | per-hero CB sim coverage (modeled / no_op / gap) |
| `data/m5_synergy.jsonl` | `m5_synergy_graph.py` | per-hero provides/needs (team buffs, debuffs, DoTs, TM, cleanse, …) |
| `data/static/mastery_relevance.json` | `m5_mastery_tagger.py` | all 66 masteries × 12 locations |
| `data/static/blessing_relevance.json` | `m5_blessing_tagger.py` | all 34 blessings × 12 locations |
| `data/static/blessing_procs.json` | `extract_blessing_procs.py` | game-truth blessing proc formulas (grade-by-grade) |
| `data/static/stage_stat_targets.json` | `m5_stat_targets.py` | per-stage boss stat modifiers + ACC floors |
| `hero_computed_stats.json` | `/hero-computed-stats` (live) | the user's actual Total-Stats per geared hero |

Regenerate the derived files:
```bash
python3 tools/refresh_static_data.py            # static data from live mod
python3 tools/m5_inventory.py
python3 tools/m5_hero_catalog.py
python3 tools/m5_synergy_graph.py
python3 tools/m5_mastery_tagger.py
python3 tools/m5_blessing_tagger.py
python3 tools/extract_blessing_procs.py
python3 tools/m5_stat_targets.py
curl -s "http://localhost:6790/hero-computed-stats?min_grade=4" -o hero_computed_stats.json
```

## The recommender layer (what you run day-to-day)

### Team for a location
```bash
python3 tools/m5_recommender.py --location cb            # owned roster
python3 tools/m5_recommender.py --location dragon --builds   # + per-hero builds
python3 tools/m5_recommender.py --location arena --pool all  # "what if I pulled X"
python3 tools/m5_recommender.py --list-locations
```
Greedy axis-coverage builder over 8 location profiles (cb / dragon / spider /
fire_knight / ice_golem / hydra / chimera / arena). CC providers are
downweighted vs CC-immune bosses; the game-truth ACC floor is surfaced.

### How to build a specific hero
```bash
python3 tools/m5_build_recommender.py --hero Venomage --location cb
```
Maps the hero's game-truth kit → relevant masteries (filtered to the location),
blessing, and stat focus — and checks the user's **actual ACC** against the
floor (`[READY: you have 423]` / `[GAP: need +M]`).

### What to pull / build next
```bash
python3 tools/m5_roster_gaps.py                  # all locations summary
python3 tools/m5_roster_gaps.py --location cb    # gaps + best unowned upgrades
```

## Coverage / limitations (no silent caps)

- **Sim validation**: the recommender ranks by synergy coverage + HH signal; it
  does **not** yet run the CB sim on the suggested team (CB-only + calibration
  work in progress — see `project_spirit_fixture_attribution_20260623`).
- **Damage stat targets**: only game-imposed floors (ACC = boss RES) are
  modeled. Per-build CR/CD/ATK% targets are intentionally not invented.
- **Readiness**: covers heroes present in `hero_computed_stats.json` (grade≥4
  snapshot). Absent heroes get no annotation.
- **Blessing procs**: extracted game-truth (`blessing_procs.json`) but not yet
  wired into the CB damage sim.

## Naming gotcha (blessings)

`blessings.json` `id` is the internal **code enum** (MagicOrb, Meteor,
Exterminator); the **UI name** is the proc skill's display name (Phantom Touch,
Brimstone, Cruelty). `blessing_procs.json` carries both. Match by either; the
`skill_type_id` link is authoritative.
