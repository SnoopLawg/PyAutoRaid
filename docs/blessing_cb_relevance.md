# Blessing CB-relevance (task #7)

Game-truth classification of the 30 blessings (proc skills 600XXX) for the **Clan
Boss** sim. Source: `data/static/blessing_procs.json` (effect formulas + conditions,
extracted via `tools/extract_blessing_procs.py`) and the `BlessingTypeId` enum
(int ids) from the IL2CPP dump. Code→int id: read the live hero's
`stats["blessing"]["id"]` (int); `cb_sim` keys on it.

**Key finding:** most "unmodeled" blessings are **NO-OP vs Clan Boss** — they are
PvP-gated, boss-excluded, require dead allies, need a specific buff (StoneSkin),
are purely defensive (reduce damage *taken*), or are non-damage utility (heal /
stamina / buff). The sim is *correct* not to model them as CB damage. Only a
handful actually affect CB damage.

## Modeled in cb_sim (CB damage-relevant)
| Blessing (UI) | code | int id | skill | model |
|---|---|---|---|---|
| Brimstone | Meteor | 4101 | 600190 | FireMark place + detonate (250K cap) |
| Phantom Touch | MagicOrb | 1301 | 600050 | 3.5×ATK bonus / attack (g6 ×1.35) |
| Heavencast | EnhancedWeapon | 2201 | 600090 | +0.5–1.5%/buff dmg amp |
| Nature's Wrath | NatureBalance | 5201 | 600270 | +2–5%/debuff (capped) amp |
| **Hero's Soul** | **Amplification** | **3302** | **600180** | **flat +0.5/1/1.5/3% vs boss (×1 enemy) — added 2026-06-29** |

## CB-applicable but NOT yet wired (real damage effect on CB; needs a hero w/ it to validate)
| Blessing (UI) | code | int id | skill | game-truth effect on CB |
|---|---|---|---|---|
| Crushing Rend | Penetrator | 4202 | 600220 | boss DEF −0.01×(bossLvl/[50/40/25/10]) on FIRST hit/round → ≈ −5% to −25% DEF by grade. Needs DEF-mod + per-round gate + boss level. |
| Faultless Defense | Adaptation | 3301 | 600170 | reflect 3/6/9/15% of damage an ALLY took (when ally hit by enemy & owner-placed effect on them) — Geo-Stoneguard-like deflect. |
| Soul Reap | Execute | 3101 | 600130 | damage = 1×TRG_CUR_HP when target not dying — HP-based, **CB-capped** (cap TBD). |

## NO-OP vs Clan Boss (correctly absent)
- **PvP-only** (`isPvPBattle`): Lethal Dose (ToxicBlade 1201), Incinerate (MagicFlame 4201).
- **Boss-excluded** (`!targetIsBoss` factor = 0): Lightning Cage (LightOrbs 2101).
- **Requires dead allies** (`deadAlliesCount>0`, 0 on a surviving run): Ward of the Fallen (Necromancy 1101), Dark Resolve (Fearless 1302).
- **Defensive / incoming** (`ownerIsRelatedEffectTarget` — reduces damage TAKEN, not outgoing): Iron Will (Vanguard 2202).
- **Buff-gated** (target needs StoneSkin; CB boss has none): Cracking Roots (CreepingRoots 5302).
- **Non-damage utility** (heal / stamina / buff / debuff-block / stat — no CB damage): Intimidating Presence, Miracle Heal, Indomitable Spirit, Temporal Chains, Cruelty, Life Harvest, Chainbreaker, Commanding Presence, Polymorph, Survival Instinct, Emergency Heal, Harmonic Impulse, Neutralize, Nature's Bounty, Nourish. (Some affect *survival*, modeled separately, not damage.)

## How to add a CB-applicable blessing
1. Get its int id from `BlessingTypeId` (dump) and the per-grade formula from
   `blessing_procs.json`.
2. For a flat/scaling damage **amp**: add an `elif bid == <id>:` branch in
   `build_sim_champion` (cb_sim ~3335) setting a `*_pct` field, and apply it in
   `_calc_skill_damage`'s `bless_mult` block (~2578). (Hero's Soul is the template.)
3. For a **proc** (direct damage / reflect / DEF-mod): wire a trigger like
   Brimstone (`_try_place_smite`) or the Geo deflect, with the CB cap.
4. Validate against a fixture where a hero actually carries the blessing — the
   MEN calibration team carries none of the unwired ones, so they can't be
   fixture-validated yet (formula is game-truth, wiring is untested live).
