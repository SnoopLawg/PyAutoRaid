# Sim Calibration Baseline (Phase 5)

This is the regression-suite snapshot, not a fix list. The point is to
surface the picture so the un-stacking of the "6 compensating wrongs"
can be planned with full data — per `project_cb_sim_calibration_state`
memory, individually tweaking calibration items is forbidden because
they cancel each other out.

Run the suite anytime: `python3 tools/sim_calibrate.py`.

## Baseline 2026-05-01 (sim @ Void)

Run: `python3 tools/sim_calibrate.py` over 22 battle logs (1 load failure).

Filtered to **complete battles** (real_turns ≥ 48 of 50) — partial
runs (early aborts) compare meaninglessly against a 50-turn sim.

| Difficulty | n | mean Δ | abs_mean | range |
|---|---:|---:|---:|---|
| Brutal | 3 | -4.4% | 4.4% | [-7.3%, -2.3%] ✅ within ±5% |
| NM | 1 | +7.1% | 7.1% | n=1, single sample |
| **UNM** | **8** | **-16.6%** | **16.6%** | [-31.1%, -11.0%] ❌ |

**Headline**: sim under-predicts UNM by ~16.6% on average. Brutal lands
within target. NM has only one complete-battle sample so isn't
informative on its own.

## Per-log UNM detail

Real damage (in M) of the standard ME/Demytha/Ninja/Geo/Venomage team:

| Log | Real | Sim | Δ |
|---|---:|---:|---:|
| 20260424_104433 | 45.54M | 31.36M | -31.1% (best UNM run on record) |
| 20260429_post_revert | 42.85M | 31.36M | -26.8% |
| 20260424_211255 | 36.81M | 31.36M | -14.8% |
| 20260427_000358 | 36.33M | 31.36M | -13.7% |
| 20260424_204109 | 35.63M | 31.36M | -12.0% |
| latest / run1_20260501 | 35.45M | 31.36M | -11.5% |
| 20260424_210812 | 35.21M | 31.36M | -11.0% |

Note the spread: real damage ranges from 35M to 46M for the same team
across UNM runs — the 11M variance is **affinity day** (Magic/Force/
Spirit/Void cycles change which heroes are weak/strong against the
boss). The sim runs at a single affinity (Void by default), so the
delta also includes the affinity miss.

The cleanest metric to track: **the run we have a good per-hero
ground-truth tick log for** is `2026-04-29 post_revert` at 42.85M.
Per memory, sim was at 31.2M after the survival fix → 73% of real.
Today's regression: 31.36M against the same log → 73.2%. Calibration
hasn't drifted since the pause.

## What the memory says about the 6 compensating wrongs

From `project_cb_sim_calibration_state` (do NOT individually revert
without coordinated changes — they mask each other):

1. `base_cd = max(0, sd["cd"] - 1)` off-by-one CD hack — speeds skill
   cycles, increases UK uptime, masks a survival-model gap. Cost:
   Demytha A1 cast count is 1 vs real 21.
2. UK = full skip (no damage taken). Real game UK clamps to 1 HP.
3. `extend_buffs` extends ALL buffs incl. UK. Per DWJ G() spec, UK
   is non-extendable.
4. Demytha A2's heal (2.5% × MAX_HP × (1+mods)) not modeled.
5. Shield absorption not modeled (Demytha A1 places ~3.9K shields).
6. SPD discrepancy — sim's `calc_stats` vs real's per-tick `s_spd`
   field disagrees by ~14 SPD on Demytha (capture deployed 2026-04-29
   but unvalidated; needs a fresh CB run).

## Per-hero accuracy (on the 2026-04-29 captured run)

| Hero | Real | Sim | Acc | Diagnostic |
|---|---:|---:|---:|---|
| Maneater | 4.53M | 3.87M | 85% | OK |
| Demytha | 1.40M | 0.04M | 3% | CD bug — only fires A1 once (opener) |
| Ninja | 17.36M | 14.26M | 82% | OK |
| Geomancer | 4.72M | 9.09M | 193% | Burn over-attribution (bar fairness) |
| Venomage | 6.06M | 4.82M | 79% | Bar congestion limits poison ticks |

Note that Geomancer over-predicts and Demytha under-predicts roughly
proportionally — that's literally the "compensating wrongs" pattern.
The team total can look closer to right than any individual hero's
attribution.

## Next chunk (planned with the user, not autonomous)

The bottom-up rewrite the memory describes:
- Capture a fresh CB run (any difficulty) to populate the `s_spd`
  per-tick field on Demytha + verify her real in-battle SPD.
- Per-CB-turn buff-state diff per hero — snapshot all `c.buffs` at
  the start of each CB turn, compare across heroes, determine the
  right buff-tick rule (per-holder vs placer-clock vs game-tick).
- Then refactor the survival model bottom-up *together*: shield
  absorption + Demytha A2 heal + UK-clamp-to-1 + parity-correct CDs
  + extend_buffs respecting NON_EXTENDABLE. Run `sim_calibrate.py`
  before/after each step to verify the team-total stays stable
  while per-hero attributions converge.

This is multi-day work and explicitly out-of-scope for autonomous
execution per the memory's "don't tweak in isolation" rule. The
regression suite + this baseline doc are the safe Phase 5 deliverables.

## Re-running the suite

```
python3 tools/sim_calibrate.py                 # default Void
python3 tools/sim_calibrate.py --cb-element force
python3 tools/sim_calibrate.py --json          # for downstream tooling
python3 tools/sim_calibrate.py --logs 'battle_logs_cb_run1*.json'
```

Suite outputs are **not** committed — they're regenerated from logs
on demand. Logs themselves are gitignored as `battle_logs_*.json`.
