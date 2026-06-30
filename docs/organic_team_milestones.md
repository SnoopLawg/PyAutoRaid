# Organic Team Identification — Milestone Plan

> **Goal:** move PyAutoRaid from *replaying scraped templates* (score DWJ tunes
> vs roster) to *deriving teams from first principles* — generate and validate
> novel, viable comps for any location from game-truth champion kits, using
> external data only as a sanity cross-check, never as the source.

This plan operationalizes the design in the 2026-06-29 research synthesis
(CB archetype taxonomy + team-building principles + internal capability audit;
see session notes / memory `project_cb_per_skill_fitting_20260629` neighbors).

## The thesis

Templates are **emergent, not fundamental**. DWJ's 103 CB tunes are solved
instances of one structure:

> **survival currency** (covers the boss AoE/stun) **+ enabler** (sustains the
> survival keystone) **+ amplifier(s)** (multiply the damage *channel*) **+
> damage engine** (fires every turn) — gated by the **ACC floor** and bounded
> by the **turn-50 cliff**.

Encode the *structure* (roles-from-effects → provider→consumer dependency +
ordering → hard constraints → fitness) and a generator re-derives the meta AND
finds novel comps. The proof it isn't cheating: hide the scraped templates and
show it rediscovers the known-good comps from game-truth alone.

## Foundational facts the system must encode (game-truth)

- **Role = function of emitted/consumed effects**, not a label. We already have
  roster-wide `provides`/`needs` tags (`tools/m5_synergy_graph.py`,
  `data/m5_synergy.jsonl`).
- **Two separate amplifier channels** (critical): **Dec-DEF / Weaken** amplify
  *hits + WM/GS + Bring-It-Down* — **NOT DoTs**; **Poison Sensitivity** amplifies
  *poison only*; **HP Burn** is amplified by neither.
- **Provider→consumer ordering:** a provider only helps if it acts *before* its
  consumer with *duration covering* the consumer's turn (speed-tuning solves this).
- **Hard constraints are filters:** ACC-vs-RES floor; 10-debuff/10-poison/1-HP-burn
  slot caps; boss CC/TM-immunity lists; affinity glance; faction lock (FW);
  DoT-vs-boss reactions (Ice Golem DEF-down trigger, poison-resist Hydra heads).
- **CB no-ops (zero value vs boss):** all TM manipulation, Stun/Sleep/Freeze/
  Provoke/Fear, Dec SPD, MAX-HP reduction.

## Current state (audit verdict)

Predominantly **template-replicating**. Substrate (`provides`/`needs` tags) is
complete; two organic generators exist (`m5_recommender` greedy axis-coverage,
`cb_team_explorer` role-discovery + sim) but the first is *unvalidated* for 7/8
locations and the only real fitness function (`cb_sim`) is **CB-only**.

---

## Milestones

Each: **Goal · Deliverables · Files · Acceptance · Depends-on · Parallel-safe**.

### M1 — Enriched synergy substrate (channel-split + role classification)
- **Goal:** add the semantics the scorer is missing on top of existing tags.
- **Deliverables:**
  - `amplifier_channel` per provider ∈ {`hit`, `poison`, `none`} (Dec-DEF/Weaken→hit;
    Poison-Sens→poison; HP-Burn amp→none).
  - `engine_channel` per damage engine ∈ {`hit`, `wm_gs`, `poison`, `hp_burn`,
    `bring_it_down`} so an amplifier can be matched to the engine it actually helps.
  - `survival_currency` ∈ {`unkillable`,`block_damage`,`shield`,`revive_on_death`,
    `ally_protect`,`heal_lifesteal`,none}; `enabler` ∈ {`cooldown_reduction`,
    `buff_extension`,none}; `keystone_needs_enabler` bool (buff CD > duration).
- **Files:** `tools/m5_synergy_graph.py`, regenerate `data/m5_synergy.jsonl`.
- **Acceptance (game-truth spot-checks):** Maneater = survival:unkillable +
  keystone_needs_enabler:true; Pain Keeper = enabler:cooldown_reduction; Demytha =
  survival:block_damage + enabler:buff_extension; Heiress = enabler:buff_extension;
  Geomancer = engine:hp_burn, amplifier:none; Frozen Banshee = engine:poison +
  amplifier:poison; Fayne = amplifier:hit (def_down+weaken); Cardiel =
  survival:revive_on_death. Channel of an amplifier never mismatched to a DoT.
- **Depends-on:** none. **Parallel-safe:** yes (own files).

### M2 — Provider→consumer dependency + ordering resolver
- **Goal:** the missing *reasoning* layer — given a comp, build the
  provider→consumer graph and verify each consumer's provider acts earlier with
  duration coverage (speed/cooldown aware).
- **Deliverables:** `resolve(comp, context) -> {satisfied[], broken[], order}`;
  CB uses the existing scheduler; a lightweight ordering model for other modes.
- **Files:** `tools/synergy_resolver.py`.
- **Acceptance:** for a known DWJ CB tune it confirms providers→consumers are
  satisfied; for a deliberately mis-ordered comp it flags the broken edge;
  channel-aware (won't credit Weaken→poison).
- **Depends-on:** M1. **Parallel-safe:** yes once M1 lands.

### M3 — Boss / location constraint tables
- **Goal:** machine-readable per-location filters.
- **Deliverables:** per location/boss: CC/TM-immunity set, DoT-vs-boss reactions,
  ACC floor (from boss RES), affinity rule, faction-lock flag, slot caps,
  T50/cliff + script notes (Magma=Provoke-counter, Scarab=shield-first,
  Eternal=A1-only, etc.). Extract from `data/static/{effects,skills_all,
  alliance_bosses}.json` + `m5_stat_targets`; verify community claims vs game-truth.
- **Files:** `data/static/boss_constraints.json`, `tools/boss_constraints.py`.
- **Acceptance:** CB excludes Stun/TM-control as value; FW enforces single faction;
  Ice Golem flags large-DEF-down reaction; ACC floors match `m5_stat_targets`.
- **Depends-on:** none. **Parallel-safe:** yes (new files).

### M4 — Generative assembly engine
- **Goal:** constraint-satisfaction team generator: archetype skeletons (abstract
  role-slot requirements, NOT champion lineups) × roster × M3 filters × M1 tags ×
  M2 resolver → candidate comps for any location. Generalizes `cb_team_explorer`.
- **Deliverables:** `generate(location, roster, opts) -> ranked candidate comps`;
  archetype skeletons defined from the unifying model (≥1 survival currency; if
  keystone_needs_enabler, ≥1 matching enabler; ≥1 amplifier whose channel matches
  the engine; ≥1 channel-consistent engine; ACC floor met).
- **Files:** `tools/team_generator.py`.
- **Acceptance:** emits role-valid novel comps respecting all hard filters; no
  champion-name templates in the logic.
- **Depends-on:** M1, M2, M3. **Parallel-safe:** no (integrates the above).

### M5 — Universal fitness function
- **Goal:** score/validate a generated comp per location (the biggest gap).
- **Deliverables:** **5a** heuristic: channel-aware multiplier stacking +
  survival/control floor + boss-script penalties (works everywhere now). **5b**
  per-mode outcome sims or a model learned on (comp → cleared?) data we generate.
- **Files:** `tools/fitness/` (per-mode scorers + a CB adapter to `cb_sim`).
- **Acceptance:** CB heuristic correlates with `cb_sim` ranking; non-CB heuristic
  ranks sanely vs HH tier signal; clearly labels heuristic vs simulated.
- **Depends-on:** M1, M3 (5b later, may depend on M4 for data generation).

### M6 — Rediscovery harness + novelty (the "no-cheating" proof)
- **Goal:** prove the system reasons rather than replays.
- **Deliverables:** harness that *hides* scraped DWJ/HH templates and checks the
  generator re-derives the known-good comps from game-truth alone; a novelty
  flag for sim-validated comps matching no known template.
- **Files:** `tools/rediscovery_harness.py`, `tests/test_rediscovery.py`.
- **Acceptance:** rediscovers ≥ a target fraction of DWJ CB tunes (role-equivalent)
  from game-truth alone; surfaces ≥1 novel comp the CB sim validates.
- **Depends-on:** M4 (a **CB-only proof-of-concept** can run NOW against the
  existing `cb_team_explorer`).

---

## Execution waves (parallelization)

- **Wave 1 (parallel now):** M1, M3, and a **CB-only M6 proof-of-concept**
  against the existing `cb_team_explorer` (independent files). M2+M4 get a
  detailed implementation spec authored in parallel.
- **Wave 2:** M2, then M4 (need M1; M4 needs M2+M3).
- **Wave 3:** M5 (5a heuristic, then 5b), full multi-location M6.

## Definition of done (system level)

The daily recommender proposes teams from generative assembly + universal fitness,
labels each as rediscovered-meta or novel-candidate, and the rediscovery harness
(templates hidden) independently reproduces the known meta — at which point the
scraped DWJ/HH data is demoted to a cross-check, not a dependency.
