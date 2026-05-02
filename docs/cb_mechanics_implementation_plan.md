# CB Mechanics — Implementation Plan

The catalogue (`cb_mechanics_research.md`) identifies game-spec ground
truth. This doc converts each finding into a concrete sim change with
a regression checkpoint.

**Rule** (from `feedback_no_hacky_fixes` + memory): un-stack
compensating wrongs **together**. Don't fix one in isolation — they
mask each other. The plan below batches related changes so the
regression suite (`tools/sim_calibrate.py`) can verify team-total
stays sane while per-hero attributions converge.

## Phase A — Pure constant fixes (no behavioural change beyond numbers)

These swap a back-fit constant for the verified game-spec value.
Should land in one batch + one regression run.

| File | Variable | Old | New | Source |
|---|---|---:|---:|---|
| `cb_constants.py` | `WEAK_HIT_DMG_MULT` | 0.70 | **0.80** | `GameplayData.ElementDisadvantageCoef = -0.2` |
| `cb_constants.py` | `STRONG_HIT_DMG_MULT` | 1.30 | **1.0 (no flat damage mult)** | Strong affinity adds crit chance, not damage |
| `cb_constants.py` | `GATHERING_FURY_RATE_PER_TURN` | 0.85 | **0.75** | Skill 222904: `DMG_MUL*0.75*(turn-9)` |
| `cb_constants.py` | `GS_DMG` (proc cap) | ~67626 | **75000** | Same path as WM via skill 200008 |

Also remove the strong-affinity damage adder path in cb_sim and
replace with a +15% crit chance bonus on the hit-type roll.

**Checkpoint A**: run `python3 tools/sim_calibrate.py` over all
battle logs. Expected: UNM mean delta moves toward zero (was -16.6%);
Brutal stays within ±5%.

## Phase B — Unblock the survival-model un-stack

Six compensating wrongs from memory, swapped together:

1. **Off-by-one CD hack** in `build_sim_champion`:
   `base_cd = max(0, sd["cd"] - 1)` → revert to `sd["cd"]`.
2. **UK = full skip** → **UK clamps to 1 HP** per `Phase_UnkillableProcessing`.
   Implement: incoming damage that would kill UK target is set to
   `current_hp - 1` instead of zero.
3. **`extend_buffs` extends UK/BD** → respect `NonIncreaseableEffects`.
   `cb_sim.SimChampion.extend_buffs` should skip buffs whose type is
   in [`unkillable`, `block_damage`, `revive_on_death`, `stoneskin`,
   `taunt`, `poison_cloud`, `thunder`, `entangle`, `syphon`, `on_guard`].
4. **Demytha A2 heal not modeled** → add the `0.025 × MAX_HP × (1 + changes)`
   heal as an effect_type the sim handles.
5. **Shield absorption not modeled** → add a `shield_amount` field on
   SimChampion; subtract incoming damage from shield first.
6. **SPD discrepancy** → use mod's `s_spd` per-tick capture (deployed
   2026-04-29, validated next CB run) as ground truth for in-battle SPD.

**Checkpoint B**: capture a fresh CB UNM run with the new mod build
(includes ATK/DEF stat capture + s_spd). Run sim_calibrate. Expected:
team-total delta improves; per-hero attributions converge.
**Critical guard**: don't ship Phase B if team-total moves further
from real (it means a wrong is uncovered without a corresponding fix).

## Phase C — Damage formula precision

After Phase B settles, work on the damage math itself:

1. **DEF mitigation formula**: back-solve `DEF_COEF` from captured
   `(p_atk, t_def, calc_raw, calc)` tuples in tick logs. Cross-check
   with community 600 estimate.
2. **DEF Down / Weaken multiplicative stacking**: per HellHades guide,
   damage debuffs combine multiplicatively. Verify sim does this.
3. **Hit-type roll order**: implement the 0-100 single-roll algorithm
   per Plarium forum (crit range first, then crush, then normal).

**Checkpoint C**: per-event damage match within ±2% on 90%+ of
captured events.

## Phase D — DoT cap precision

1. **Per-difficulty Poison cap**: read CB difficulty, look up
   `POISON_CAPS[difficulty]` (from skill 200004/5/6/7 extraction).
   Today sim hardcodes UNM values; correct would be per-difficulty.
2. **Per-rarity HP Burn cap**: read each burn's producer rarity (from
   `heroes_all.json[hero_id].rarity`), apply the 75K/50K/15K cap from
   skill 200008.
3. **Detonation cap formula**: `cap × turns_left_of_remaining_burn`.
   Sim already detonates Burns/Poisons but applies the wrong cap.

**Checkpoint D**: per-event Burn/Poison damage match within ±1%.

## Phase E — Boss skill conditions

1. **Stun damage scaling**: skill 222601 uses `0.2 × TRG_B_HP`. The
   `TRG_B_HP` token is the **base** (level-60 ungeared) HP, not
   current MAX. Sim uses MAX. Switch to base HP.
2. **Boss A2 Flesh Wither**: places **2.5% Poison** (not 5%). If the
   sim simulates the boss's debuff placement on heroes, this matters
   for hero damage taken. Verify routing.

**Checkpoint E**: stun damage on heroes matches real per-hit values.

## Phase F — Future research

Items requiring more game introspection or empirical capture:

- Stoneskin damage curve (`StoneSkinDamageFactor`)
- HP Burn stacking (per-producer separate slots?)
- HealOnStartRound timing in CB
- CrabShell mechanic
- NewbieDefence applicability

---

## Tracking

Each phase ends with a regression-suite run. Don't proceed to the next
phase if the current one moved team-total in the wrong direction.

**Status legend**:
- 🔴 not started
- 🟡 in progress
- 🟢 shipped + regression-checked

| Phase | Status | Expected delta |
|---|---|---|
| A — constants | 🟢 | UNM -15.3% → -10.9% (commit 2bfc223) |
| B — survival | 🟡 partial | UNM -10.9% → -11.3% (commit 833a5f6) |
| C — hit types + per-log affinity | 🟢 | -9.1% → -8.7% (commit ee698be) |
| D — DoT caps | 🟢 | -11.3% → -9.1% (commit 8528858) |
| E — boss skills (stun base HP) | 🟢 | -8.7% → -8.7% (commit 5247882; correct but no leverage on this team) |
| F — research | 🟡 | per-hero gap analyzed; FireMark + Geo reflect minor gaps |

## Phase E — Done 2026-05-01 (commit 5247882)

Stun damage now uses base HP (level-60 ungeared, ~19,650 for Cardiel)
via skill 222601's `0.2 * TRG_B_HP` formula. Previously sim used
gear-included max_hp (~45K) — over-predicted stun damage by ~2.3×.

UK no longer skips stun damage entirely (Phase B clamp-to-1 rule).

No regression suite movement because the calibration team's stun
target (Ninja) is usually under UK protection — stun damage was
being skipped before, gets clamped now. Same outcome.

Will matter for non-UK tunes.

## Per-hero gap analysis (post Phase A-E, 2026-05-01)

On the most recent capture (Magic UNM, real 36.8M / sim 33.8M = -8.2%):

| Hero | Real | Sim | Δ |
|---|---:|---:|---:|
| Maneater | 4.27M | 4.3M | ✓ match |
| Demytha | 1.12M | 0.9M | -0.2M |
| Ninja | 15.43M | 14.0M | -1.4M (sim under) |
| Geomancer | 9.06M | 6.8M | -2.3M (sim under) |
| Venomage | 5.82M | 7.8M | +2.0M (sim over) |

**Identified contributors**:
- Ninja FireMark damage 2.75M (11 events × 250K cap) — **sim doesn't
  model FireMark**. Source unclear: not in Ninja's skill descriptions,
  not in his equipped sets. Likely a relic effect or set bonus we
  haven't identified.
- Geomancer reflect 4.64M vs sim's ~3.8M passive aggregation — sim's
  formula uses approximations; real per-event values are 250-400K each.
- Venomage poison over-prediction — sim's `activate_poisons` likely
  fires too often per A1 cast.

Remaining gap is sub-9% and requires per-skill investigation.
Recommend: run more CB battles on different affinity days to pin
formulas before more constants tweaking.

## Phase B partial — Done 2026-05-01 (commit 833a5f6)

**Audit revealed 3 of the 6 compensating wrongs already fixed**:
- Off-by-one CD hack: already removed
- Demytha A1 shield: already placed via team_buffs
- Demytha A2 heal: already modeled in extend_buffs

**This commit fixed**:
- UK = full skip → UK clamps to 1 HP (game-spec
  Phase_UnkillableProcessing). BlockDamage still fully blocks.
- Incoming affinity multiplier: 1.30/0.70 → 1.0/0.80 to match
  ElementDisadvantageCoef ground truth.

**Still wrong (not fixed)**:
- extend_buffs extending UK/BD: trying to fix it drops sim UNM
  survival from 50/50 to 19/50 because the sim's rotation can't
  keep UK alive without the extension hack. True fix needs the
  rotation model rewritten so Demytha A3 + Maneater A3 re-place UK
  at the right cadence. Multi-day work.
- SPD discrepancy: needs s_spd capture validation (deployed
  2026-04-29, captured in 2026-05-01 tick logs but not yet diffed
  against sim's calc_stats output).

Slight regression (-10.9% → -11.3%) because UK full-skip was masking
a damage-modifier gap that Phase C will close.

## Phase A — Done 2026-05-01 (commit 2bfc223)

Landed 4 constants:
- `WEAK_HIT_DMG_MULT: 0.70 → 0.80`
- `STRONG_HIT_DMG_MULT: 1.30 → 1.0`
- `GATHERING_FURY_RATE_PER_TURN: 0.85 → 0.75`
- `UNM_DEF: 4878 → 1520`

Regression delta: UNM mean -15.3% → -10.9%, abs_mean 15.3% → 11.5%.

GS_DMG and HP_BURN_DMG were already at the correct 75K cap value
(matched skill 200008's Legendary-rarity cap rule), so no change
needed. Per-difficulty Poison cap mapping also wasn't changed since
sim only runs UNM and the UNM cap (50K) was already correct.

The goal is **1:1 game calculation** per the user's directive. Only
RNG remains is weak hits, debuff land, crit chance.
