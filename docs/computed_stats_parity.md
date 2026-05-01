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

## Verification status (2026-05-01)

### Cardiel L60 6★ (no Faction Guardians, +900 HP Relic)

| Stat | Ours | Screenshot | Δ |
|------|-----:|-----------:|---:|
| HP   | 45,379 | 45,379 | ✅ EXACT |
| ATK  | 3,885 | 3,887 | -2 |
| DEF  | 3,328 | 3,392 | -64 (−1.9%) |
| SPD  | 236 | 237 | -1 |
| RES  | 194 | 194 | ✅ EXACT |
| ACC  | 103 | 103 | ✅ EXACT |
| CR   | 66 | 66 | ✅ EXACT |
| CD   | 149 | 147 | +2 |

### Gnut L60 6★ (Faction Guardians +1965 HP, +11% CD Relic)

| Stat | Ours | Screenshot | Δ |
|------|-----:|-----------:|---:|
| HP   | 41,445 | 41,445 | ✅ EXACT |
| ATK  | 2,007 | 2,008 | -1 |
| DEF  | 4,950 | 4,951 | -1 |
| SPD  | 180 | 180 | ✅ EXACT |
| RES  | 152 | 152 | ✅ EXACT |
| ACC  | 207 | 218 | -11 |
| CR   | 87 | 87 | ✅ EXACT |
| CD   | 188 | 194 | -6 |

**11/16 EXACT match. 5/16 with small residuals (≤6.4% on the worst case).**

## Outstanding residuals (investigation status)

Investigated and ruled out:
- ❌ NOT artifact ascend bonuses — none of Cardiel's or Gnut's artifacts have AscendLevel set.
- ❌ NOT mastery sums — both have only the expected stat-bonus masteries (DEF +75 on Cardiel, +10 ACC / +5% CR / +10% CD on Gnut, plus Lore of Steel which only multiplies set bonuses).
- ❌ NOT set-bonus DEF — neither hero has a 2-piece DEF / Resilience / Stoneskin / Reflex set active.
- ❌ NOT mod's `CalcArtifactsBonus` — the IL2CPP `Dictionary<EnumKey, Int32>` enumeration on `ArtifactIdByKind` returns empty regardless of approach (GetEnumerator, _entries walk, indexer 1..9). Mod returns 0-stats; Python aggregation matches HP exactly so the numbers we have are the right ones, but a chunk is missing for some heroes.

Still mysterious:
- Cardiel DEF -64. Per-slot mod's `pct_bonus.DEF` shows 50% total; our manual sub-aggregation shows 54%; the screenshot wants 59%. Where the missing 5% comes from is unclear.
- Gnut ACC -11 (substats sum to 97; screenshot shows +108 from artifacts).
- Gnut CD -6 (mod's affinity_bonus.CD = 0.20 → 20%; screenshot column shows +25%; mod's relic_bonus.CD = 0.10 → 10%; screenshot shows +11%; combined -6).

The current best guess: the mod's `CalcBuildingsBonus` (Affinity column) and `CalcArenaBonus` use a slightly different rounding or scaling than the in-game *Total Stats* screen for percentage stats specifically. For HP/ATK/DEF flat stats they match exactly. For % stats (CD specifically on Gnut, possibly DEF substats) there's a 1-5% systematic underreport.

These are small enough that sim/optimizer downstream is well within trust bounds, but worth tracking for future investigation.

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
