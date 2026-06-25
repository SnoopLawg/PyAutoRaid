# Blessing → Clan Boss effect classification (task #7)

`tools/blessing_cb_effects.py` evaluates each blessing's game-truth proc
`condition` (lifted from IL2CPP effect relations in
`data/static/blessing_procs.json`) against the fixed facts of a Clan Boss
fight and reports the **real per-grade CB effect** of every blessing.

This replaces the hand-maintained CB-relevance flags in
`blessing_relevance.json`, which are stale and wrong in several places.
Output: `data/static/blessing_cb_effects.json` (per-blessing role +
resolved per-grade formula).

## Why parse, not hand-wire

"Model the remaining blessings" looked like 25+ unknowns. Parsing the
conditions collapses it: most are no-op on CB, most of the rest are
survival/indirect, and only a handful are direct CB damage amps with a
clean per-grade formula. The load-bearing CB facts are:

- `isPvPBattle` is **False** → any blessing gated on it is a **no-op on CB**
  (Incinerate, Lethal Dose's damage half).
- one enemy, no minions → `aliveEnemiesCount == 1`.
- boss is **control-immune** (Polymorph no-op) and **TM-immune**
  (stamina-vs-boss no-op: Survival Instinct) and **DestroyHp-immune**
  (task #8: Life Harvest no-op).
- owner-role atoms (`isOwnerProduceRelatedEffect` /
  `ownerIsRelatedEffectTarget`) are evaluated in both an **offense** and a
  **defense** context; the activating context + the formula sign decide
  whether a blessing amplifies output (offense) or reduces damage taken
  (defense). A negative `ChangeDefenceModifier` on the boss is *offensive*
  (it strips boss DEF) — Crushing Rend.

## CB roles (30 blessings)

| role | count | meaning |
|---|---|---|
| `cb_offense` | 11 | increases damage dealt; `damage_amp_by_grade` is the wire-in formula |
| `cb_survival` | 6 | heal / shield / cleanse / reflect — survival, not output |
| `cb_other` | 8 | indirect/uncertain (Smite debuff, leader auras) — needs case-by-case |
| `cb_defense` | 1 | reduces damage **taken** (Iron Will) |
| `cb_noop_*` | 4 | PvP-only (Incinerate), control-immune (Polymorph), TM-immune (Survival Instinct), DestroyHp-immune (Life Harvest) |

### CB offensive amps (the real wire-in worklist)

Already modeled in `cb_sim`: Heavencast (EnhancedWeapon), Nature's Wrath
(NatureBalance), Phantom Touch (MagicOrb). Brimstone (Meteor) is modeled
via its Smite debuff (classified `cb_other` here because it's an
ApplyDebuff, not direct damage).

Not yet wired (formula in `blessing_cb_effects.json`): Hero's Soul
(`+0.5%→3% × aliveEnemiesCount`, =1 on CB), Cracking Roots (StoneSkin
break), Cruelty (`+4% × boss DEF`), Dark Resolve (`+5% × dead allies`),
Execute (`1 × TRG_CUR_HP`, expect a CB cap), Ward of the Fallen (`3×ATK`
proc), Crushing Rend (`−DEF modifier on boss`), Lightning Cage (`%TRG_HP ×
LightOrbs stacks`, boss branch halves the rate).

**None are worn by the active MEN tune** (its blessings — 4101/1301/2201/
5201 — are all already modeled), so this is universal-engine prep: it lets
future `cb_comp_finder` candidates that use these blessings be simmed
accurately. The actual hot-path wiring is mechanical (one runtime hook per
formula variable) and is best done when a candidate needs it (Gate B).

## Audit corrections (vs `blessing_relevance.json`)

Confident disagreements the parser found:

- **Incinerate, Survival Instinct** — audit "relevant", actually **no-op**
  on CB (PvP-gated / TM-immune).
- **Dark Resolve** — audit "no-op", actually **active** (`+5%/dead ally`),
  relevant to non-stall comps where allies die.

## Latent sim finding (not yet changed)

Heavencast's per-grade ramp from the catalog is
`0.005 / 0.005 / 0.01 / 0.01 / 0.015 / 0.02` (`×BUFF_COUNT`). `cb_sim`'s
hardcoded comment caps grade 5-6 at `0.015` — i.e. it **under-credits
grade-6 Heavencast by 0.005/buff**. No current impact (the user's Demytha
holds it at grade 1 = 0.005), but the catalog (game-truth) should drive the
per-grade value if/when a grade-6 holder is simmed.
