# Computed Stats Parity — In-game *Total Stats* vs PyAutoRaid

The in-game *Total Stats* screen breaks per-hero stats into 10 columns:

```
Basic | Artifacts | Affinity | Classic Arena | Masteries
      | Faction Guardians | Empowerment | Blessing | Relic | Area Bonuses
                                                                      | Total
```

Phase 1's goal: PyAutoRaid's per-hero numbers match every column exactly.
Without this parity, any sim or optimizer downstream is built on shaky
inputs.

## Ground truth — Cardiel (id=13250, L60 6★, account level 60)

From the `assets/`-screenshotted *Total Stats* screen:

| Column           | HP     | ATK   | DEF   | SPD | CR  | CD   | RES | ACC |
|------------------|-------:|------:|------:|----:|----:|-----:|----:|----:|
| Basic            | 19,650 | 1,013 | 1,255 | 106 | 15% |  50% |  50 |   0 |
| Artifacts        | 14,775 | 2,033 | 1,299 | 131 | 46% |  69% | 124 |  23 |
| Affinity         |  1,965 |    61 |   125 |  -- |  -- |  18% |  20 |  80 |
| Classic Arena    |    589 |    30 |    38 |  -- |  -- |   -- |  -- |  -- |
| Masteries        |     -- |    -- |    75 |  -- |  5% |  10% |  -- |  -- |
| Faction Guardians|     -- |    -- |    -- |  -- |  -- |   -- |  -- |  -- |
| Empowerment      |     -- |    -- |    -- |  -- |  -- |   -- |  -- |  -- |
| Blessing         |  7,500 |   750 |   600 |  -- |  -- |   -- |  -- |  -- |
| Relic            |    900 |    -- |    -- |  -- |  -- |   -- |  -- |  -- |
| Area Bonuses     |     -- |    -- |    -- |  -- |  -- |   -- |  -- |  -- |
| **Total**        | 45,379 | 3,887 | 3,392 | 237 | 66% | 147% | 194 | 103 |

## Mod payload — `/hero-computed-stats?min_grade=6` for the same hero

```json
{
  "id": 13250, "grade": 6, "level": 60,
  "base_computed":   {"HP": 19650, "ATK": 1013, "DEF": 1255, "SPD": 106, "RES": 50, "CR": 0.1, "CD": 0.5},
  "blessing_bonus":  {"HP":  7500, "ATK":  750, "DEF":  600},
  "empower_bonus":   {"HP":     0, "ATK":    0, "DEF":    0},
  "great_hall_bonus":{"HP":  1965, "ATK":   61, "DEF":  125, "ACC": 80, "RES": 20, "CD": 0.2},
  "arena_bonus":     {"HP":  3144, "ATK":  162, "DEF":  201, "SPD":  0},
  "_arena_league":   "GoldII"
}
```

## Field-by-field analysis

| Mod field          | Maps to column        | Match? |
|--------------------|-----------------------|:------:|
| `base_computed`    | Basic                 | ✅      |
| `blessing_bonus`   | Blessing              | ✅      |
| `empower_bonus`    | Empowerment           | ✅      |
| `great_hall_bonus` | Affinity (mislabel!)  | ✅ value, ❌ name |
| `arena_bonus`      | (none)                | ❌ — value 3144 doesn't match Classic Arena (589) |
| (missing)          | Classic Arena         | ❌      |
| (missing)          | Relic                 | ❌ — block exists in mod but emits nothing for Cardiel |
| (missing)          | Faction Guardians     | ❌      |
| (missing)          | Masteries             | ❌      |
| (missing)          | Area Bonuses          | ❌      |

Cross-check Cardiel HP totals:
- Basic + Affinity + ClassicArena + Blessing + Relic + (Artifacts) + (Masteries=0) + (Empower=0) = 19650 + 1965 + 589 + 7500 + 900 + 14775 + 0 + 0 = **45,379** ✅ matches the in-game total.

So **Affinity column = Village Building bonuses** (the towers in the
Village area; in IL2CPP they're computed by `CalcBuildingsBonus` from
the `BuildingSetup` returned by `Village.CapitalBuildingSetupForElement`).
The mod calls this `great_hall_bonus` which is misleading; the in-game
labels it "Affinity Bonuses".

## What the mod needs to add / fix

| Issue | Fix |
|---|---|
| Rename `great_hall_bonus` → `affinity_bonus` | Cosmetic; update the mod emit + Python consumers |
| `arena_bonus` value doesn't match anything | Investigate — what does `Hero.CalcArenaBonus(GoldII)` actually compute? Maybe Arena Defense / Faction Wars / Doom Tower? Empirically test. |
| Classic Arena column missing | Find the IL2CPP method that produces ClassicArena +589 HP. Likely `CalcGreatHallBonus` (the *real* Great Hall — bonuses based on Classic Arena rank/league). Re-investigate naming. |
| Relic column missing | Mod has a `CalcRelicsBonus` block but it silently fails — debug why no `relic_bonus` or `_relic_err` field appears. |
| Faction Guardians missing | New `CalcFactionGuardiansBonus` method (if it exists). |
| Masteries column missing | Mastery stat-bonus lookup — already in `data/static/masteries.json` for the 13 stat ones; just needs to read hero.masteries[] and sum them. Pure Python. |
| Area Bonuses missing | Per-location bonuses (CB/Dungeon/Hydra/etc.); the dropdown on the Total Stats screen. Mod's `CalcAreaBonus` if it exists. |

## Approach

1. **Don't rewrite the mod yet** — first, get the Python side reading what the mod already returns and producing a per-column breakdown that the dashboard renders.
2. **Add a verifier CLI**: `python3 tools/hero_stats.py "Cardiel" --vs-mod` — pulls the mod's `/hero-computed-stats` for that hero and diffs each column against our calc. Surfaces every gap.
3. **Iterate the mod**: each missing column is a small mod patch + redeploy + recheck. The verifier tells us when a column locks in.

This is the trust foundation for everything downstream. Without it, we
can't say sim damage is wrong vs game damage is wrong. The verifier is
the regression suite for Phase 5 calibration.
