# Auto-Leveling + Food-Farm Pipeline Plan

Goal: replicate RSL Helper's Multi-Level XP / food-champ rotation, then go
beyond it by leveraging the data we already have (preset rosters, vault,
HH team knowledge, drop tables).

## Mod endpoints (Phase 1)

The food loop needs primitives the mod doesn't expose yet. Each is a
focused IL2Cpp endpoint following the same pattern as
`/apply-blessing` / `/open-mastery`: find the cmd type, ctor with right
args, `InvokeExecute`.

| Endpoint                                    | Cmd / target                              | Notes |
|---------------------------------------------|-------------------------------------------|-------|
| `/swap-squad-hero?slot=N&hero_id=X`         | `HeroesSquadContext.SetHero`              | replace a campaign squad slot |
| `/clear-squad-slot?slot=N`                  | `HeroesSquadContext.RemoveHero`           | drop a slot to empty           |
| `/rank-up?hero_id=X&food=A,B,C`             | `RankUpHeroCmd`                           | sacrifice food to rank up      |
| `/sell-hero?hero_id=X`                      | `SellHeroCmd`                             | post-rank-up cleanup           |
| `/skill-up?hero_id=X&skill_idx=I&books=N`   | `LearnSkillBookCmd`                       | feed skill books               |
| `/open-campaign?chapter=X&stage=Y&difficulty=Z` | `WebViewInGameTransition.OpenBattleMode` | navigate to e.g. 12-3 Brutal   |
| `/sacred-ascend?hero_id=X`                  | `SacredAscendCmd` (verify name in dump)   | gates blessings + Lord-Stars   |

## Core tool (Phase 2): `tools/level_food.py`

CLI mirroring `dungeon_run.py`'s shape:

```
python3 tools/level_food.py \
  --stage 12-3 --difficulty brutal \
  --lead 13076 \
  --food-rarity-max common \
  --food-level-target 7 \
  --skip-locked --skip-vault \
  --auto-rank-up \
  --auto-sell-after-rank-2 \
  --runs 200
```

### Behaviors

1. **Pick lead**: highest-power 6/60 we own NOT slotted in any preset
2. **Pick food slots**: filter `/all-heroes` by:
   - rarity ≤ user threshold (common / uncommon / rare)
   - not locked, not in vault, not in reserved set
   - level < target
3. **Open campaign stage** via `/open-campaign`
4. **Slot via `/swap-squad-hero`**, start battle
5. **Loop**: after each battle, refresh `/all-heroes`, rank-up + sell food at
   target level, refill slots
6. **Stop conditions**: `--runs N`, `--until-energy 0`, `--until-no-food`,
   `--until-time HH:MM`, `--max-fails N`

## Reserved-hero awareness (Phase 3 — beats RSL Helper)

RSL Helper only knows lock/vault. We know all our presets and team plans:

- `data/reserved_heroes.json` — auto-generated:
  - CB roster from preset 1
  - Dragon team from preset 5
  - Spider team from preset 7
  - ITF team from preset 8
  - Heroes named in any HH-verified comp we want to build
  - User-pinned wishlist from dashboard

Tool: `tools/build_reserved_set.py` — scans presets + HH ownable comps +
dashboard pins, writes the JSON. Food picker reads it; never sacrifices
a champ we have a real plan for.

## Smart farming (Phase 4 — beyond RSL Helper)

### 4a. Optimal stage selector

```
expected_xp_per_energy(stage, hero_rank) =
  xp_per_clear(stage) / energy_cost(stage) * hero_xp_multiplier(rank)
```

`--auto-stage` picks the optimal stage for the food's rank distribution
(12-6 brutal if mostly rank-3+, 12-3 brutal if rank 1-2).

### 4b. Bulk rank-up (RSL Helper requested but unbuilt — issue #231)

After leveling N champs to rarity max, batch rank-up using the recursive
food chain (4 unranked epics → 1 epic-to-legendary, etc.). Tool plans the
chain and pipelines food.

### 4c. Skill book feeder

After max-rank, optionally feed reserve skill books from skill priorities
in HH team specs.

### 4d. Sacred ascend pipeline

Sacred Stars 1-6 gates Blessings. Pipeline:
- Need: Sacred Shards / fragments
- Steps: ascend → equip sacred-tier gear → unlock blessing tier
- Surfaces "next sacred-ascend candidate" by which preset hero is gating
  which blessing build

### 4e. Daily-task orchestrator

`tools/daily_run.py` chains:
1. `cb_daily.py` (have)
2. Daily quests
3. Faction Wars pushes
4. Doom Tower secret rooms
5. Free events (Get Artifacts / Champion Chase via dungeon farms)
6. Multi-Level XP backfill on leftover energy

## Dashboard (Phase 5)

New "Champ Manager" tab: roster table with role-tags (CB / Dragon / Spider /
Food / Reserved), food queue with drag-drop pipeline, sacred-plan gating chart.

## Sequencing

| Order | Item                                                                   | Effort   | Unlocks            |
|-------|------------------------------------------------------------------------|----------|--------------------|
| 1     | Mod endpoints: `/swap-squad-hero`, `/rank-up`, `/sell-hero`, `/open-campaign` | half day | Phase 2            |
| 2     | `tools/build_reserved_set.py`                                          | 1 hr     | reserved filter    |
| 3     | `tools/level_food.py` MVP (no auto rank-up)                            | half day | first auto-leveler |
| 4     | `--auto-rank-up` + `--auto-sell` flags                                 | 2 hr     | RSL Helper parity  |
| 5     | `--auto-stage` optimal-stage picker                                    | 2 hr     | beats RSL Helper   |
| 6     | Skill book feeder                                                      | half day |                    |
| 7     | Sacred ascend tool                                                     | half day | unblocks blessings |
| 8     | Dashboard Champ Manager tab                                            | 1 day    | UX                 |
| 9     | `daily_run.py` orchestrator                                            | 1 day    | hands-off daily    |

Total: ~5 working days. Phases 1-4 (RSL Helper parity + basic "more") = ~2 days.

## Out of scope

- Screen-clicking automation (mod API only)
- Anti-bot bypass (we work with IL2Cpp, not against)
- Macro recording — we use viewmodel calls
