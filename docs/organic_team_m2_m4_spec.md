# Implementation Spec — M2 (`synergy_resolver.py`) + M4 (`team_generator.py`)

> Companion to `docs/organic_team_milestones.md`. Design for Wave 2 (both depend
> on M1's enriched `data/m5_synergy.jsonl` + M3's `data/static/boss_constraints.json`).
> Authored 2026-06-29. Citations point at the real code each part generalizes/reuses.

## 0. Shared substrate

### 0.1 M1-enriched per-hero record (`data/m5_synergy.jsonl`)
Existing (`m5_synergy_graph.py:232-243`): `name, base_id, element, rarity, fraction,
game_role, synergy_role, provides[], needs[], debuffs_control_only`.
`provides[]` vocab (`:160-191`): `team_buff:<Name>`, `enemy_debuff:<Name>`, `dot:<Name>`,
`enables:poison`, `dot_detonate`, `tm_control`, `tm_drain`, `cleanse`, `revive`,
`cooldown_reduction`, `heal`, `buff_extension`. `needs[]` (`:194-214`): `def_break`,
`poison_synergy`, `burn_synergy`, `tm_control`, `survival_support`, `buff_extension`.

**M1 adds (authoritative):** `amplifier_channel ∈ {hit,poison,none}`,
`engine_channel ∈ {hit,wm_gs,poison,hp_burn,bring_it_down,none}`,
`survival_currency ∈ {unkillable,block_damage,shield,revive_on_death,ally_protect,heal_lifesteal,none}`,
`enabler ∈ {cooldown_reduction,buff_extension,none}`, `keystone_needs_enabler: bool`.
M2/M4 must tolerate records **with and without** M1 fields (safe-default accessor
`_get(rec,"amplifier_channel","none")`; warn once if absent).

### 0.2 Ordering data NOT in the synergy record
M2 needs **buff duration**, **skill cooldown**, **base SPD** → new `OrderingContext`
builder reads `skills_all.json` (`Cooldown`) + `"for N turns"` in
`skill_descriptions_all.json` (same sources `m5_synergy_graph`/`cb_team_explorer.discover_roles`
parse); CB path reuses gear-aware SPD via `cb_sim` build.

### 0.3 M3 constraints
`boss_constraints.for_location(loc) -> BossConstraint` with `cc_immunities[]`,
`tm_immunities[]`, `acc_floor`, `faction_lock`, `affinity`, `slot_caps`,
`dot_reactions`, `script_notes`.

---

## M2 — `tools/synergy_resolver.py`

**Purpose:** the reasoning layer that doesn't exist today (`m5_recommender` only
counts axis coverage `:246-266`; `cb_team_explorer` sims but has no explicit
provider→consumer graph). Builds the channel-aware graph + verifies ordering/duration.

**API:** `resolve(comp: list[str], context: ResolveContext) -> ResolveResult`
- `SynergyEdge{provider, consumer, tag, via, channel, ordering_ok, ordering_reason}`
- `ResolveResult{satisfied[], broken[], unmet[], order[], keystones[], notes[]}`

**Edge construction — need→provide routing table (channel-gated):**

| Consumer need | Satisfied by | Channel gate |
|---|---|---|
| `def_break` | `enemy_debuff:Decrease DEF`/`Weaken` | provider.amplifier_channel==`hit` AND consumer.engine_channel ∈ {hit,wm_gs,bring_it_down} |
| `poison_synergy` | `enables:poison`, `dot_detonate` | provider.amplifier_channel==`poison` (Poison-Sens half) |
| `burn_synergy` | `dot_detonate` | engine_channel==`hp_burn`; **no amplifier exists** |
| `tm_control` | `tm_control` | none |
| `survival_support` | any `survival_currency!=none` | none (see keystone logic) |
| `buff_extension` | provider.enabler==`buff_extension` | consumer must hold a survival buff |

**The channel rule (game-truth, milestones.md:32-36):** hit/wm_gs/bring_it_down
engines amplified ONLY by `amplifier_channel==hit`; poison engine ONLY by
`amplifier_channel==poison`; hp_burn engine by neither (`dot_detonate` only). When
matching `def_break`, gate by the **consumer's engine_channel** — a poison engine
carrying `needs:def_break` (because `m5_synergy_graph:199-202` adds it to all
attackers) must NOT be credited a Weaken edge → category mismatch → `notes`, not
`satisfied`/`broken`. This is the "won't credit Weaken→poison" acceptance.

**Ordering verification** `verify_ordering(edge, context) -> (ok, reason)`:
- **CB mode:** reuse `cb_scheduler`/`turn_meter` (locked PICK-MAX-ONE + ZERO-RESET,
  `cb_sim.py:1107-1131` — DO NOT re-derive). Lightweight: build `cb_scheduler.Actor`
  (`:54-72`) + boss proxy SPD 190, run one boss cycle (3 turns, `cb_pattern`
  `cb_sim.py:1372`), record act order; edge ok iff provider acted earlier in the
  same cycle AND `duration >= turns_until_consumer`. Full (when `cb_sim_hook`
  given): consume a `cb_sim` trace. reason=`cb_schedule`|`cb_sim_trace`.
- **Generic mode:** SPD-rank model — ok iff `rank(provider)<rank(consumer)` AND
  `duration >= max(1, cooldown)`; `ordering_mode ∈ {burst,sustained}` picks which
  dominates; cd-0 re-appliers → `untimed_refresh`. reason=`spd_rank+duration`.

**Edge cases:**
1. **Self-amplifier** (Frozen Banshee self Poison-Sens): allow `provider==consumer`
   for amplifier/engine edges; ok with reason `self`.
2. **keystone_needs_enabler:** for each survival provider with the flag, find a
   compatible enabler via `KEYSTONE_ENABLER_COMPAT`:
   - `unkillable/block_damage/shield/heal_lifesteal`: {cooldown_reduction, buff_extension}
   - `revive_on_death/ally_protect`: {cooldown_reduction}  (nothing to extend)
   Then ordering-check the enabler vs the keystone's expiry. Record in `keystones[]`.
3. **Redundant providers (slot caps 10/10/1):** keep best edge per (consumer,tag);
   surplus → `notes` `redundant`; 2nd HP-burner redundant (cap 1). Not `broken`.
4. **CB no-ops:** effects in `boss.cc_immunities`/`tm_immunities` (TM/Stun/Freeze/
   Provoke/Dec-SPD/MaxHP-down) → `notes` `no-op vs boss`, never `satisfied`.
   (`debuffs_control_only` flag `m5_synergy_graph:242` for fast exclusion.)

**Tests:** known DWJ tune → Maneater keystone enabler_ok via Demytha; Ninja(hit)
def_break satisfied; Venomage(poison) def_break NOT credited (channel negative);
mis-ordered comp → `broken`; self-amplifier; keystone-enabler compat; 2 burners
→ redundant.

---

## M4 — `tools/team_generator.py`

**Purpose:** generalize `cb_team_explorer` (CB-only, fixed feasibility
`:106-124`) into a location-agnostic CSP generator driven by **archetype
skeletons** (abstract role-slot constraints, NOT champion lineups) × roster × M3
filters × M1 tags, validated by M2, ranked by M5/cb_sim.

**API:** `generate(location, roster, opts: GenOpts) -> list[CandidateComp]`
- `GenOpts{size=5, pool=owned|all, top=30, beam_width=200, max_candidates=5000,
  skeletons, cb_element, use_current_gear, rank_with=auto|cb_sim|heuristic}`
- `CandidateComp{team, skeleton, resolve, fitness, fitness_kind, constraint_report, novelty}`

**Skeletons (tag predicates only — no champion names):**
`SlotConstraint{name, require_any:[predicate_keys], optional}`,
`Skeleton{name, slots, team_rules}`. Predicate keys: `survival:<currency>|any`,
`enabler:<kind>|any`, `engine:<channel>`, `amplifier:<channel>`, `cleanse`, `heal`,
`tm_control`, `dot_detonate`, `acc_capable`.

Canonical **`unified`** skeleton (subsumes most DWJ CB tunes):
```
slots: survival(survival:any); enabler(enabler:any, optional - required iff keystone_needs_enabler);
       amplifier(amplifier:<engine_channel>); engine(engine:<channel>);
       flex(engine:<channel>|amplifier:<ch>|cleanse|heal, optional)
team_rules: acc_floor_met, channel_consistent, survival_present,
            enabler_if_keystone, boss_hard_filters
```
Instantiated **once per engine channel present in the roster** (hit/wm_gs/poison/
hp_burn/bring_it_down), binding `<channel>`. Named presets
(`double_survival_stall`, `poison_dot`, `hit_nuke`) are thin wrappers.

**Team rules (hard):** survival_present; enabler_if_keystone (M2 compat table);
channel_consistent (≥1 amplifier matching the engine channel + ≥1 channel engine);
acc_floor_met (enough acc-capable debuffers vs `boss.acc_floor`); boss_hard_filters
(faction_lock, affinity, exclude CC/TM-immune from value, slot_caps not a value
basis, dot_reactions e.g. Ice Golem Dec-DEF reaction).

**Search — slot-by-slot greedy-with-backtrack + beam (generalizes
`cb_team_explorer.generate_candidate_teams:127-204`):**
1. `boss=boss_constraints.for_location`; load enriched recs (pool); apply hard
   filters (faction/affinity/CC-only-vs-boss exclusion).
2. Per skeleton × engine channel: bucket roster by which slot each hero fills;
   skip if a non-optional bucket is empty (record roster gap).
3. **MRV ordering** (most-constrained slot first); **beam search** (width 200)
   with incremental team-rule pruning (`can_add` branch-and-bound); cheap
   pre-score = `cb_team_explorer.predict_score:240`.
4. Fill free slots from channel-consistent engines/flex (capped by max_candidates).
5. De-dup by `frozenset(team)`.
6. M2 `resolve` each; drop comps with unmet HARD edges (no survival / broken
   keystone-enabler / no channel-consistent amplifier→engine).
7. Rank by fitness (M5/cb_sim); top survive to real sim, rest heuristic.
8. Novelty flag vs scraped templates (`cb_team_explorer:541-585`).

**Tractability:** MRV + incremental pruning + beam cap + two-stage prune (cheap
score → top to cb_sim, mirrors `cb_team_explorer:482-502`). Fitness (cb_sim
~sec/comp) is the bottleneck → only `sim_top≈200` get a real sim.

**Fitness adapter (`rank_with`):** `cb_sim` → `cb_sim.evaluate_team_calibrated`
(`:3897`) / `cb_potential.simulate_team` (`:192`), MC via `evaluate_team_mc`
(`:3942`) for Force; `heuristic` (M5.5a, fallback to `predict_score` until M5
lands); `auto` = cb_sim for CB else heuristic.

**Edge cases:** roster-gap → skip + report; duplicate hero `Maneater_2`
convention end-to-end (`cb_team_explorer:192-204`, `cb_sim:238-240`,
`has_double_maneater:451`); pool=all → cap buckets top-N per slot (HH signal
additive) before beam; no engine channel → emit nothing + report.

**Tests:** reproduce the user's known CB comp (Maneater/Demytha/Ninja/Geomancer/
Venomage) in top-K as `rediscovered` from the `unified` skeleton — asserting the
skeleton/search contain ONLY tag predicates, no champion names (the organic
proof); every emitted comp passes its skeleton rules; FW → single-faction; CB →
no value from CC/TM; poison comp never credits Weaken; pool=all under wall-clock
budget; fixed seed deterministic.

---

## Build order & graceful degradation
1. **M2 first** (M4 depends on it). Ships with CB scheduler reuse; generic
   ordering can follow (CB is the validation target).
2. **M4** consumes M2+M3+M5. Degrades gracefully during the concurrent wave: M3
   absent → fall back to `m5_stat_targets` acc_floor + minimal CC/TM-immune sets;
   M5 absent → `predict_score`. Both files stay importable/testable throughout.

**Reuse anchors:** `cb_scheduler.py:54-203` + `turn_meter.py:50-105` (ordering,
do-not-re-derive), `cb_sim.py:1064-1132` (locked scheduler / boss SPD 190),
`cb_sim.py:3897` & `cb_potential.py:192` (fitness), `cb_team_explorer.py:127-204,
240,482-585` (search/prune/novelty), `m5_synergy_graph.py:58-214` (tag vocab),
`m5_recommender.py:164,246-266` (acc_floor + greedy coverage M4 replaces).
