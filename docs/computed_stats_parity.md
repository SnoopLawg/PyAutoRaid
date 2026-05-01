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

## Verification status (2026-05-01) — 🎯 **EXACT MATCH 16/16**

### Cardiel L60 6★ (no Faction Guardians, +900 HP Relic)

| Stat | Ours | Screenshot | Δ |
|------|-----:|-----------:|---:|
| HP   | 45,379 | 45,379 | ✅ EXACT |
| ATK  | 3,887 | 3,887 | ✅ EXACT |
| DEF  | 3,392 | 3,392 | ✅ EXACT |
| SPD  | 237 | 237 | ✅ EXACT |
| RES  | 194 | 194 | ✅ EXACT |
| ACC  | 103 | 103 | ✅ EXACT |
| CR   | 66 | 66 | ✅ EXACT |
| CD   | 147 | 147 | ✅ EXACT |

### Gnut L60 6★ (Faction Guardians +1965 HP, +11% CD Relic)

| Stat | Ours | Screenshot | Δ |
|------|-----:|-----------:|---:|
| HP   | 41,445 | 41,445 | ✅ EXACT |
| ATK  | 2,008 | 2,008 | ✅ EXACT |
| DEF  | 4,951 | 4,951 | ✅ EXACT |
| SPD  | 180 | 180 | ✅ EXACT |
| RES  | 152 | 152 | ✅ EXACT |
| ACC  | 218 | 218 | ✅ EXACT |
| CR   | 87 | 87 | ✅ EXACT |
| CD   | 194 | 194 | ✅ EXACT |

**16/16 EXACT match across both test heroes.**

## Fixes that closed the residuals (2026-05-01)

1. **`CalcArtifactsBonus` was passing the wrong type.** `HeroExtensions.CalcArtifactsBonus` takes `List<ArtifactSetup>`, not `List<Artifact>`. Wrapping each `Artifact` via `ArtifactSetup.FromArtifact` before adding fixed the silent `Artifact cannot be converted to ArtifactSetup` error and closed the Cardiel DEF -64 / Gnut ACC -11 residuals.

2. **`Dictionary<ArtifactKindId, int>` doesn't accept `int` for `ContainsKey`.** Replaced the slot-1..9 indexer pattern with the `GetEnumerator + MoveNext + Current` pattern that `AppendEquippedArtifacts` already uses successfully for the same dictionary.

3. **Float precision: `FixedToJson` used F1 (1 decimal).** Bumped to F10. `0.4596` was being formatted as `"0.5"`, so CR/CD percentages came through as 50% instead of 46%. F10 reveals the true Fixed64 fractional bits (e.g. affinity DEF is `125.4999998247`, not exactly `125.5`).

4. **`ReadFixed` preferred `ToString()` over raw long.** Fixed64's `ToString` truncates precision; reordered to read the underlying long first and divide by 2^32 for an exact double conversion.

5. **In-game display rounding rule.** Each per-column displayed integer is `int(value + 0.5 - 1e-9)` — i.e. round-half-down. The total = sum of per-column rounded integers (NOT round/floor of the unrounded sum). This matters for Cardiel DEF (3392.6 → 3392 not 3393) and ATK (3886.97 → 3887 not 3886).

## Architecture: how the calc works now

`tools/hero_stats.py:compute_hero_actual_stats(hero, base_computed=, mod_bonuses=)` accepts the mod's `/hero-computed-stats` payload and uses each per-column field as the authoritative value:

| Column           | Mod field                  | Source method               |
|------------------|----------------------------|-----------------------------|
| Basic            | `base_computed`            | `HeroExtensions.GetBaseStats`     |
| Artifacts        | `artifact_bonus`           | `CalcArtifactsBonus`        |
| Affinity         | `affinity_bonus`           | `CalcBuildingsBonus`        |
| Classic Arena    | `classic_arena_bonus`      | `CalcArenaBonus`            |
| Masteries        | `mastery_bonus`            | `CalcMasteriesBonus`        |
| Faction Guardians| `faction_guardians_bonus`  | `CalcAcademyBonus`          |
| Empowerment      | `empower_bonus`            | `CalcEmpowerBonus`          |
| Blessing         | `blessing_bonus`           | `CalcBlessingBonus`         |
| Relic            | `relic_bonus`              | `CalcRelicsBonus`           |

Each value is rounded with the in-game display rule (`int(v + 0.5 - 1e-9)`) and summed.

## Outstanding gap: Area Bonuses

The Total Stats screen has an "Area Bonuses" dropdown (CB / Dungeon / Hydra / Faction Wars / Doom Tower / etc.) — these are per-location buffs. The mod doesn't expose a `CalcAreaBonus` yet. They aren't shown in the default Total Stats view, so the 16/16 EXACT matches above don't include them. Add when the sim/optimizer needs per-area accuracy.

## Approach

1. **Don't rewrite the mod yet** — first, get the Python side reading what the mod already returns and producing a per-column breakdown that the dashboard renders.
2. **Add a verifier CLI**: `python3 tools/hero_stats.py "Cardiel" --vs-mod` — pulls the mod's `/hero-computed-stats` for that hero and diffs each column against our calc. Surfaces every gap.
3. **Iterate the mod**: each missing column is a small mod patch + redeploy + recheck. The verifier tells us when a column locks in.

This is the trust foundation for everything downstream. Without it, we
can't say sim damage is wrong vs game damage is wrong. The verifier is
the regression suite for Phase 5 calibration.
