# CB Mechanics — Game Ground Truth Catalogue

**Goal**: 1:1 game calculation. For every mechanic the sim models, this
doc captures *what the game actually does* (formula, source, exact
constants) so the sim can implement it faithfully instead of back-fitting
constants from observed runs.

Per `feedback_sim_ground_truth_not_back_fit` (2026-05-01): only RNG in
the sim should be **weak hits, debuff land rate, crit chance**.
Everything else is deterministic per game spec.

**Sources used in this doc**:
- `data/static/skills_all.json` — every skill's `Effects[]` array with
  `KindId` / `MultiplierFormula` / `Condition` / `TargetType` (5368
  skills, Phase 2 deliverable).
- `data/static/effects.json` — effect-type prototypes (StackCount,
  Category, StrengthInFamily).
- IL2CPP method dumps via the live mod's `/types`, `/list-static-methods`,
  `/props`, `/static-export` endpoints.
- External resources cited inline (Plarium docs, HellHades, AyumiLove,
  DWJ spec).

**Status legend**:
- ✅ Ground-truth source identified, formula extracted, sim matches.
- ⚠️ Ground-truth identified, sim mismatched — fix needed.
- 🟡 Ground-truth partially identified, more research needed.
- ❌ Sim has back-fit value with no game source yet.

---

## 1. Damage Formula

### 1.1 Pipeline (DamageCalculator + DamageProcessor)

The game's full pipeline is in
`SharedModel.Battle.Core.DamageCalculator` (16 real methods) and
`SharedModel.Battle.Core.Skill.EffectProcessing.Processors.DamageProcessor`
(44 methods, mostly `Phase_*` hooks).

**Order of operations** (from `DamageProcessor.Phase_*` method names):

1. `Phase_AfterDamageContextCreated` — context built from skill effect
2. `Phase_AfterHitTypeCalculated` — crit/crush/glance roll resolved
3. `Phase_BeforeDamageCalculated` — pre-calc hooks
4. `DamageCalculator.CalculateDamage(EffectContext, Fixed)` — base formula
5. `DamageCalculator.DamageReductionByDefence(EffectContext, BattleHero, Fixed)` — DEF mitigation
6. `Phase_IgnoreDefenceModifierProcessing` — Ninja-A3 / OB-A2 style ignore-DEF
7. `Phase_AfterDamageCalculated`
8. `DamageCalculator.DamageReductionByStatusEffects(...)` — DEF Down / Weaken / Stoneskin etc.
9. `DamageCalculator.StoneSkinDamageFactor(BattleHero, EffectKindId)` — set proc
10. `Phase_NewbieDefenceProcessing` — early-game protection
11. `Phase_AfterFinalDamageCalculated`
12. `Phase_BlockDamageProcessing` — Block Damage buff absorption
13. `Phase_CrabShellProcessing` — Demytha A2 shield-style absorption (?)
14. `Phase_SpecialAbsorptionProcessing` / `Phase_AbsorptionAfterShieldProcessing`
15. `LimitDamage` — caps (DoT caps, etc.)
16. `Phase_UnkillableProcessing` — UK clamp-to-1
17. `Phase_BeforeDamageDealt`
18. `Phase_AfterDamageDealt` — health reduced, post-hit triggers

### 1.2 Hit Type (Crit / Crush / Glance)

`DamageCalculator.CalculateHitType(EffectContext, ElementRelation, Nullable<Fixed>&)`
— resolves the hit type. Sub-helpers:
- `IsCritHit(ElementRelation, Nullable, Fixed)`
- `IsCrushHit(ElementRelation, Nullable, Fixed)`
- `IsGlanceHit(ElementRelation, Nullable, Fixed)`
- `HitTypeBonus(BattleHero, HitType)` — the damage multiplier per type

**Game-spec constants** (`StaticData.GameplayData`, ✅ verified):

| Constant | Value | Meaning |
|---|---:|---|
| `CriticalHitChance` | 0.15 | Base hero crit rate (15%) |
| `CrushingHitChance` | 0.5 | Base crushing rate (50%) |
| `GlancingHitChance` | 0.35 | Base glancing rate (35%) |
| `CriticalHitChanceAdvantage` | 0.15 | Extra crit on strong-affinity hit (+15%) |
| `CrushingHitCoef` | 0.3 | Crushing hit damage multiplier (+30%) |
| `GlancingHitCoef` | -0.3 | Glancing hit damage multiplier (-30%) |
| `CriticalHealCoef` | 0.5 | Crit heal bonus (+50%) |
| `ElementDisadvantageCoef` | -0.2 | **Weak-affinity damage modifier (-20%)** |

⚠️ **Sim mismatch**: `tools/cb_constants.py:WEAK_HIT_DMG_MULT = 0.70`
(implies -30% damage on weak hits). **Game spec is -20%** (multiplier
0.80). Off by a flat 10%. Replace with `1.0 + ElementDisadvantageCoef`.

⚠️ Sim mismatch: `STRONG_HIT_DMG_MULT = 1.30` is also wrong as a
direct damage multiplier — the game gives strong-affinity heroes
**+15% crit chance** (`CriticalHitChanceAdvantage`), which raises
expected damage but is NOT a flat 30% damage adder. The +30% feel
comes from "more crits land" + the crit bonus. Sim should roll crit
chance with the affinity bonus, not multiply final damage.

### 1.3 Element / Affinity Relation

`DamageCalculator.CalculateElementRelation(EffectContext)` — reads the
attacker / target elements and returns the relation (Strong / Weak /
Neutral). `ElementAdvantageBonus(ElementRelation)` returns the damage
multiplier.

The Magic→Spirit→Force→Magic cycle (each strong vs the next, weak vs
the previous) is the visible game rotation. **Void = neutral against
all four elements** (no advantage either way). Need to verify the
exact match-up table — the game's `ElementRelation` enum should have
the values.

🟡 **TODO**: extract `ElementRelation` enum values via /types, verify
the cycle direction matches sim's `WEAK_AFFINITY` / `STRONG_AFFINITY`
maps.

### 1.4 DEF Mitigation Formula — ✅ EMPIRICAL CAPTURE

`DamageCalculator.DamageReductionByDefence(EffectContext, BattleHero, Fixed)`
is the actual mitigation function. Body lives inside the IL2CPP
method.

**Captured 2026-05-01** via the upgraded damage hook (1210 events from
a CB UNM Void run, ME/Demytha/Ninja/Geo/Venomage):

⚠️ **Boss UNM DEF = 1520** (not 4878 as `raid_data.UNM_DEF` had —
that was a CALIBRATED back-fit). With Decrease Defence 60% the
target DEF reads **608** (1520 × 0.4 ✓).

Empirical DEF mitigation factors (calc / mul on cap-procs WM at 75K
and GS at 93.75K, where pre-DEF damage is the cap, no ATK
dependency):

| target DEF | observed factor | observed damage reduction |
|---:|---:|---:|
| 1520 (no DEF Down) | **0.4649** | 53.5% |
| 608  (DEF Down 60%) | **0.7213** | 27.9% |

⚠️ **Community formula `DR = DEF / (DEF + 600)` is wrong** for the
boss:
- DEF=1520: `DR = 1520/2120 = 71.7%` (predicted), 53.5% (observed)
- DEF=608: `DR = 608/1208 = 50.3%` (predicted), 27.9% (observed)

Tested formulas that DO NOT fit both data points:
- `factor = ATK / (ATK + DEF × K)` — different K per DEF value
- `factor = level / (level + DEF × K)` — different K per DEF
- `factor = level² / (level² + DEF × K)` — different K per DEF
- `factor = C / (C + DEF)` — different C per DEF

The real game formula is more complex than any simple ratio. Likely
involves both attacker level AND target level non-linearly.

🟡 **Next**: capture a CB run with the rebuilt mod to get accurate
`p_cd` / `p_cr` (the fixed-point reader was truncating to integer
part, losing decimals). Also capture more DEF values (Stoneskin
modifier, Newbie Defence, Decrease DEF 30%) to over-determine the
formula. Plan: read `DamageReductionByDefence` body via a new mod
endpoint that synthesizes test args.

**Practical interim approach**: use a 2-point lookup
`{1520: 0.4649, 608: 0.7213}` for CB UNM since DEF Down is the only
real DEF modifier in CB. ✓ exact-match for the calc; need real
formula for other locations.

### 1.4b Damage caps in skill 200008 — ✅ confirmed

The boss's passive applies multiple `ChangeDamageMultiplier` rules.
What we observed in `mul` values (the post-cap multiplier):

| Cap source | mul value | DEF mitigated? | Notes |
|---|---:|:---:|---|
| Poison 5% per tick (UNM) | 50,000 | ❌ no | calc=mul=50000 always; flat damage path |
| Floor cap (skill 200008 line 5) | 250,000 | ❌ no | calc=mul=250000; absolute upper bound |
| HP Burn legendary cap | 75,000 | ✅ yes | observed 0.4649× and 0.7213× factors |
| Warmaster proc | (raw 0.04×TRG_HP, capped 75K) | ✅ yes | same DEF mitigation as HP Burn |
| Giant Slayer proc | (raw 0.03×TRG_HP, capped 75K) → mul=93750 | ✅ yes | same factors |

⚠️ Note: GS shows `mul=93750` in the data (= 75000 × 1.25), suggesting
the cap path includes a +25% modifier somewhere (Weaken? Crushing
hit?). On `mul=93750, DEF=1520`, calc=43581 → factor 0.4648 (same
as 75K WM). So the same DEF mitigation applies regardless of the
exact cap value — it's the `mul` field that differs.

### 1.5 Ignore-DEF (Ninja A3, OB A2)

`Phase_IgnoreDefenceModifierProcessing` — applies the
`AddIgnoredEffects` / `ChangeDefenceModifier` effects from the casting
skill. KindId in effects is `ChangeDefenceModifier`.

Game spec from skill descriptions:
- Ninja A3 (62003): `ignore_def: 0.5` (50%) when target is Boss
- OB A2 (33002): `ignore_def: 0.3` (30%) when target has debuffs
- Various others — extracted by `desc_profiler.py`

✅ Sim handles via `ignore_def` skill flag.

---

## 2. CB Boss Skills (the entire kit)

All skill IDs verified against `data/static/skills_all.json`. Boss has
6-7 active/passive skills total:

### 2.1 Skill 222601 — Stun (default A1)

```
Group: Active, CD: 0
Effects:
  Damage 0.2 × TRG_B_HP   (1 hit)
  ApplyDebuff (Stun)
```

✅ **`0.2 * TRG_B_HP`** = 20% of target's BASE max HP (B_HP, before gear).
Sim has `CB_STUN_HP_FRACTION = 0.2` ✓.

⚠️ Sim variable name says "MAX_HP" — game uses `TRG_B_HP` which is
the **base** (level-60 unequipped) HP, NOT current max with gear.
This matters for high-HP heroes — sim might be inflating stun damage.

### 2.2 Skill 222802 — AOE2 (Boss action #2)

```
Group: Active, CD: 3
Effects:
  Damage 2 × ATK   (Count=1)
  Damage 1 × ATK   (Count=1)
  ApplyDebuff
Total: 3 × ATK
```

✅ Sim has `CB_ATTACK_MULT["aoe2"] = 3.0` ✓.

### 2.3 Skill 222603 — AOE1 (Boss action #1)

```
Group: Active, CD: 3
Effects:
  Damage 1 × ATK   (Count=4)   ← 4 hits
  ApplyBuff
Total: 4 × ATK
```

✅ Sim has `CB_ATTACK_MULT["aoe1"] = 4.0` ✓.

### 2.4 Skill 222904 — Gathering Fury (passive)

```
Group: Passive
Effects (all KindId=ChangeDamageMultiplier):

  T10-T19: DMG_MUL × 0.75 × (OWNERS_TURN_NUMBER - 9)
    Cond: OWNERS_TURN_NUMBER >= 10 && < 20
    → T10: ×0.75 over base, T11: ×1.5, T12: ×2.25, ..., T19: ×7.5

  T20+: DMG_MUL × 7.5 + DMG_MUL × (OWNERS_TURN_NUMBER - 19)
    Cond: OWNERS_TURN_NUMBER >= 20
    → T20: ×8.5 (=7.5 +1), T21: ×9.5, T30: ×18.5

  T50+: AddIgnoredEffects (enrage — ignores all defensive effects)
  T50+: ApplyDebuff if heroKilledByProducer (final-blow debuff)
```

⚠️ **Sim mismatch**: `cb_constants.py` uses `GATHERING_FURY_RATE_PER_TURN
= 0.85` — **game spec is 0.75**. Was tagged CALIBRATED
("CALIBRATED 0.85 — game spec is 0.75") with a comment about
overcorrecting BT-14 damage. That's a back-fit. Replace with 0.75 and
investigate the BT-14 discrepancy elsewhere.

### 2.5 Skill 200008 — DoT cap on the boss (HP Burn / Poison)

The exact, game-spec DoT cap formulas. Caps depend on the **producer's
rarity** (REL_PRODUCER_RARITY).

```
Group: Passive
KindId: ChangeDamageMultiplier (4 separate caps + 1 PassiveBlockEffect + 1 floor)

For "reletionEffectScalesByTargetHp" effects (HP Burn et al.):

  Legendary producer (RARITY >= 4) OR specific effect ids 5001632, 5001612:
    cap = 75,000 (per tick, undetonated)
        = 75,000 × Burn_TurnsLeft (when detonated)

  Epic producer (RARITY == 3):
    cap = 50,000   (undetonated)
        = 50,000 × Burn_TurnsLeft (detonated)

  Rare or below (RARITY <= 2):
    cap = 15,000   (undetonated)
        = 15,000 × Burn_TurnsLeft (detonated)

  Floor for any other ScalesByTargetHp effect:
    cap = 250,000

PassiveBlockEffect — relevant when ownerIsRelatedEffectTarget
```

⚠️ Sim has a single `hp_burn` cap at 75K from `data/observed_dot_caps.json`.
Game splits by producer rarity. Heroes deal different burn ticks
depending on what rarity placed the burn:
- **Geomancer (Legendary)** → 75K cap ✓ (matches our hardcoded 75K)
- **Sicia (Legendary)** → 75K cap
- **Any Epic burn placer** → 50K cap (sim currently overestimates)
- **Rare/Common** → 15K cap (sim massively overestimates)

Special effect IDs **5001632** and **5001612** get the 75K cap regardless
of producer rarity — need to identify which skills produce these.

### 2.6 Skill 200004 — Poison cap on the boss

```
Group: Passive

For ContinuousDamage025p (2.5% poison):
  cap = 10,000 (undetonated)
      = 10K × turns_left_of_2.5p + 20K × turns_left_of_5p (detonated)

For ContinuousDamage5p (5% poison):
  cap = 20,000 (undetonated)
      = 10K × turns_left_of_2.5p + 20K × turns_left_of_5p (detonated)
```

⚠️ Sim has `POISON_5PCT_DMG = 50000` from `data/observed_dot_caps.json`.
**Game spec is 20K per tick**. Our 50K observation likely from
detonations (Ninja A2 / Sicia A2 / Venomage A1 detonation skills) —
those scale by remaining turns × 20K, so 2-3 turns left ≈ 40-60K.

### 2.7 Skill 200000 — Block Effect (passive)

```
KindId: PassiveBlockEffect
Cond: ownerIsRelatedEffectTarget && (producerId != relationProducerId
                                     || relatedEffectWasRedirected)
```

Boss blocks effects from sources that aren't the target's producer
(or whose effect was redirected). Used to prevent shenanigans like
TM-share buffs landing on boss.

### 2.8 Skill 220605 — TM/Debuff immunity (passive)

```
KindId: PassiveBlockDebuff
Cond: ownerIsRelatedEffectTarget
```

This is the boss's **Stun/Sleep/Freeze/Provoke/TM-drain immunity**.
Verified-by-memory (`project_cb_boss_tm_immunity`): drain skills
(Syphon, Quicksand) are full no-op vs CB; caster does NOT gain "what
would have been drained".

✅ Sim already respects this via the `BossProfile.immunities` list +
the kind=5001 drain handling that we re-added for the right reason
(TM drain on non-CB targets still drains; vs CB it's the no-op).

### 2.9 Other passive skills

Boss has additional skills (id 200000 / 220605 already covered).
Need to verify if there are any missed skills by checking
`alliance_bosses[].skill_ids` for each difficulty.

🟡 **TODO**: confirm the per-difficulty skill list matches across
Easy/Normal/Hard/Brutal/NM/UNM.

---

## 3. Turn Meter

### 3.1 Tick rate + threshold

✅ **Game-spec from GameplayData**:
- `StaminaToTurn = 100` — TM threshold to act
- `StaminaByTick = 0.07` — TM gained per tick is `0.07 × Speed`

Sim uses threshold=1000 with `0.7 × Speed` per tick (just rescaled by
10×). Mathematically identical.

### 3.2 TM Modification effects

Effect kinds (from `effects.json` + skill data):
- `IncreaseStamina` (kind=4001) — TM boost on cast (formula like
  `0.15*MAX_STAMINA` for Ninja A1's +15%)
- `ReduceStamina` (kind=5001) — TM drain target
- `Stamina` set bonus (id=14) — gives flat stamina

### 3.3 CB Boss TM Immunity

✅ Verified via skill 220605 + memory. The boss has
`PassiveBlockDebuff` blocking all incoming debuff-style effects
including:
- Stun (10), Sleep (20), Freeze (~20), Provoke
- ReduceStamina (TM drain)

The caster of a drain effect does NOT receive any "compensation fill"
when the drain is blocked.

### 3.4 ⚠️ Sim TM Drain Handling Re-Examination

Memory says the Syphon caster-fill model was reverted (was a hack).
The current `cb_sim` model: kind=5001 with `MAX_STAMINA` formula AND
kind=4001 with `CHANGED_STAMINA_AMOUNT` formula together = "caster
fills from drain" mechanic. Vs CB this is the no-op — verified.

🟡 **TODO**: confirm against fresh tick log that Maneater A2 + Geo A3
post-cast TM matches pure natural accumulation (no caster-fill bonus
vs CB).

---

## 4. Stat Buffs / Debuffs — Stack Limits

✅ **Per-target max active**:
- `MaxAppliedBuffEffects = 10` (GameplayData)
- `MaxAppliedDebuffEffects = 10` (GameplayData)

This is the "10-slot debuff bar" sim already models.

✅ **Per-effect StackCount** (`effects.json`):

| Effect | KindId | StackCount | Note |
|---|---|---:|---|
| HP Burn | 470 | AoEContinuousDamage | 1 | Single bar slot — but Ninja's 3-per-cast burns appeared to stack in observations. **Re-verify.** |
| Poison 5% | 80 | ContinuousDamage | 10 | Stacks up to 10 per source pool |
| Poison 2.5% | 81 | ContinuousDamage | 10 | Stacks up to 10 |
| Stun | 10 | Stun | 1 | (Boss is immune) |
| Unkillable | 320 | Unkillable | 1 | Single buff |
| BlockDamage | 60 | BlockDamage | 1 | Single buff |
| BlockDebuff | 100 | BlockDebuff | 1 | Single buff |
| Counterattack | 50 | StatusCounterattack | 1 | Single buff |
| Ally Protect | 310 | ShareDamage | 1-2 | StrengthInFamily=2 |

⚠️ **Sim's HP burn observation** vs static: memory says "Ninja's 80
burn ticks in 50 CB turns implies ~1.6 active simultaneously". Static
says StackCount=1. Likely explanations:
- Burns from different producers count as separate effects (e.g. one
  per Ninja hit due to RandomEffectProducer or similar)
- The 80 ticks include detonations (Ninja A2 forces tick of all burns)
  which inflates count

🟡 **TODO**: pull burn effect prototype + relationship-with-skill data
to confirm whether per-producer burns get separate slots.

---

## 5. Set Bonuses

From `data/static/artifact_sets.json`:

✅ **Lifesteal (id=9, "LifeDrain")**: 2-piece, formula `0.3*DEALT_DMG`
on Heal effect → **30% heal-on-damage**. Sim has `LIFESTEAL_RATE = 0.30` ✓.

✅ **Stoneskin (id=10, "DamageIncreaseOnHpDecrease")**: 4-piece, gives
damage reduction scaling with target's HP-percent damage. Game function:
`DamageCalculator.StoneSkinDamageFactor(BattleHero, EffectKindId)`.

🟡 **TODO**: extract Stoneskin formula via the IL2CPP method body
(or empirically from a tick log with Stoneskin equipped).

✅ **Speed (id=4, "AttackSpeed")**: 2-piece +12% SPD. Static formula:
`stat: Speed value: 0.12 absolute: false` ✓.

✅ Other stat sets (HP/ATK/DEF/CR/CD/Acc/Res): all 2-piece with a
single `stat_bonus` entry. Linear additive, multiplied by
`Lore of Steel` mastery if equipped (+15% set bonus value).

---

## 6. Masteries (conditional, no static formula)

Per memory `project_mastery_blessing_data`: stat-bonus masteries are
loadable from static; **conditional ones** (Warmaster, Crushing Rend,
etc.) have NO static form — game-side proc rules.

Game-spec values from in-game tooltips:
- **Warmaster**: 60% chance per skill cast to deal `1*ATK` extra
  damage to one target (boss = single target so always lands on boss).
- **Giant Slayer**: 30% chance per HIT to deal `0.04*TRG_MAX_HP` of
  the target's max HP (capped — see DoT-cap section, falls under the
  250K floor cap).
- **Crushing Rend**: damage bonus per debuff on target (formula?).
- **Lore of Steel**: +15% to set-bonus stats.

Sim has `WM_PROC_RATE = 0.60`, `GS_PROC_RATE = 0.30`. Damage values
stored as flat (`WM_DMG`, `GS_DMG`).

⚠️ **Sim damage values**: `WM_DMG = 75000`, `GS_DMG = ~67626` (from
observed_dot_caps). These are the per-proc cap values. The actual
formula is `1*ATK` for WM and `0.04*MAX_HP` for GS — capped by skill
200008's `floor=250,000` for general TargetHp-scales effects, but the
per-proc cap of 75K (WM/GS observed) suggests they fall under the
Legendary HP-burn cap path. **Re-verify which cap applies**.

🟡 **TODO**: find the Warmaster + Giant Slayer effect IDs in
`effects.json`, check if they're flagged as `ScalesByTargetHp`,
determine which cap rule applies.

---

## 7. Survival Mechanics

### 7.1 Unkillable buff (kind=Unkillable, effect id=320)

`Phase_UnkillableProcessing` in DamageProcessor — clamps incoming
damage to leave the target at exactly 1 HP.

**Game spec**: UK leaves the hero at 1 HP. **Sim mismatch**:
`cb_sim` treats UK as full damage skip (no damage taken). Per memory
`project_cb_sim_calibration_state` listed wrong #2.

### 7.2 Block Damage buff (kind=BlockDamage, effect id=60)

`Phase_BlockDamageProcessing` in DamageProcessor — fully absorbs the
incoming damage hit. StackCount=1 (one BD active per hero).

### 7.3 Shield (kind=Shield, ShieldCapValue=1,000,000)

✅ `GameplayData.ShieldCapValue = 1,000,000` — shields cap at 1M
absorption.

✅ **Demytha A1 shield formula** (verified skill 65101 effect):
`shield_value = 0.10 × HP_caster` placed on MostInjuredAlly for
2 turns. Sim's "3.9K" memory note matches Demytha's HP/10 (~3,900).

⚠️ Sim doesn't model shield absorption. Wrong #5 in compensating list.
Damage pipeline's `Phase_AbsorptionAfterShieldProcessing` is where
shield deduction happens — sim should subtract shield amount from
incoming damage before applying HP loss.

### 7.3b Demytha A2 heal (verified)

✅ Skill 65102 effect formula:
`heal = 0.025 × TRG_HP + 0.025 × TRG_HP × (totalIncreasedTurnsCountBySkill + totalDecreasedTurnsCountBySkill)`

Translation: 2.5% of each ally's MAX HP base, plus 2.5% per
buff-extended or debuff-shrunk turn changed by this cast. With one
buff extension on each ally + one debuff shrink, the multiplier is
`(1 + N)` where N is the count of changes (typically 5-7 → 17.5%-20%).

✅ Memory note matches: "Maneater HP recovers from 25673 → 34025 at
tick 12 (her A2 cast time) — 21% MAX_HP heal matches the 2.5% × (1
base + 7 changes) formula."

⚠️ Sim doesn't model this heal. Wrong #4 in compensating list.

### 7.4 Heal on round start

✅ `GameplayData.HealOnStartRound = 0.2` — every round start, heroes
heal 20% of MAX_HP.

⚠️ Sim doesn't model this. CB has only one round (it's a single
sustained fight), so this might not affect CB calibration. Verify
that CB rounds do/don't trigger this.

### 7.5 Counterattack damage

✅ `GameplayData.CounterattackModifier = -0.25` — counterattacks deal
**75% damage** (modifier -0.25 is the multiplier delta).

🟡 Sim's counterattack model — verify this constant is applied.

### 7.6 HP Destruction

✅ Constants:
- `HpDestructionFromDamagePercent = 0.4` — 40% of damage becomes
  destruction (when an HpDestruct effect is involved)
- `MaxPossibleHpDestructionPercent = 0.6` — total destruction capped
  at 60% of max HP
- `MaxPossibleHpDestructionPerSkillPercent = 0.08` — single skill
  can destruct max 8%

Not used in CB sim (HP destruction is mostly Doom Tower / specific
skills). Add when needed.

---

## 8. RNG (legitimate randomness)

Per the user's directive, the only RNG should be:

1. **Crit roll** — `CriticalHitChance` (base 15% + hero stats + advantage bonus).
2. **Glance roll** — `GlancingHitChance` 35% baseline (vs `accuracy` reduces it?).
3. **Crushing roll** — `CrushingHitChance` 50% baseline.
4. **Debuff land rate** — `chance_to_land = max(0.15, base_chance + (ACC - RES) / 1000)` (community-verified formula; need to find game source).

⚠️ Sim's `WEAK_HIT_DEBUFF_FAIL = 0.35` — extra penalty for debuff
land on weak hits. Need to verify this is multiplicative on top of the
ACC-vs-RES roll.

---

## 9. Constants Already Stored Correctly

Quick reference of game-spec-verified values in sim:

| Sim Variable | Value | Game source | Match? |
|---|---:|---|:---:|
| `CB_STUN_HP_FRACTION` | 0.2 | Skill 222601 `0.2*TRG_B_HP` | ✅ |
| `CB_ATTACK_MULT["aoe1"]` | 4.0 | Skill 222603 4×(1×ATK) | ✅ |
| `CB_ATTACK_MULT["aoe2"]` | 3.0 | Skill 222802 (2+1)×ATK | ✅ |
| `LIFESTEAL_RATE` | 0.30 | Set 9 `0.3*DEALT_DMG` | ✅ |
| `CONT_HEAL_RATE` | 0.075 | (need source) | 🟡 |
| `WM_PROC_RATE` | 0.60 | Tooltip | ✅ |
| `GS_PROC_RATE` | 0.30 | Tooltip | ✅ |
| `MAX_DEBUFF_SLOTS` | 10 | `MaxAppliedDebuffEffects` | ✅ |
| `ENRAGE_TURN` | 50 | Skill 222904 `>=50` cond | ✅ |
| `GATHERING_FURY_START_TURN` | 10 | Skill 222904 `>=10` cond | ✅ |
| `GATHERING_FURY_CLIFF_TURN` | 20 | Skill 222904 `>=20` cond | ✅ |

---

## 10. ⚠️ Constants That Need Replacement

The following sim constants are back-fits that disagree with game spec:

| Sim Variable | Sim Value | Game Spec | Source |
|---|---:|---:|---|
| `WEAK_HIT_DMG_MULT` | 0.70 (-30%) | **0.80 (-20%)** | `ElementDisadvantageCoef = -0.2` |
| `STRONG_HIT_DMG_MULT` | 1.30 (+30%) | **+15% crit chance**, no flat damage mult | `CriticalHitChanceAdvantage = 0.15` |
| `GATHERING_FURY_RATE_PER_TURN` | 0.85 | **0.75** | Skill 222904 `DMG_MUL*0.75*(turn-9)` |
| `HP_BURN_DMG` (single value) | 75,000 | **15K / 50K / 75K by producer rarity** | Skill 200008 cap rules |
| `POISON_5PCT_DMG` | 50,000 | **20,000 base; scales on detonation** | Skill 200004 cap rules |
| `POISON_2PCT_DMG` (if used) | ? | **10,000 base** | Skill 200004 |

These don't get fixed in isolation — they're the "compensating wrongs"
list. Tracking together so the next un-stack pass can swap them as a
batch with the regression suite watching team-total stability.

---

## 11. Items still to investigate

Open follow-ups (work to do in this catalogue):

- [x] ~~Specific Burn effect IDs 5001632 / 5001612~~: identified —
  these are **Warmaster (500161 effect 5001612) and Giant Slayer
  (500163 effect 5001632)** mastery effects. They get the 75K cap on
  the boss regardless of producer rarity.
- [x] ~~Warmaster + Giant Slayer~~: **WM = 0.04×TRG_HP, GS = 0.03×TRG_HP**
  (vs boss); both capped at 75K via skill 200008 special-case path.
  Verified in skills_all.json.
- [x] ~~NON_EXTENDABLE list~~: read live via new `/static-field`
  endpoint. `NonIncreaseableEffects = [BlockDamage, Unkillable,
  ReviveOnDeath, StoneSkin, Taunt, PoisonCloud, Thunder, Entangle,
  Syphon, OnGuard]`. UK + BD CANNOT be extended.
- [x] ~~Per-difficulty CB boss skill_ids~~: verified.
  Easy/Normal/Hard each have unique cap-passive (200004/5/6).
  Brutal/NM/UNM all share **skill 200007** (the 25K/50K caps).
- [x] ~~ElementRelation enum~~: 3 values — `Neutral=0`, `Advantage=1`,
  `Disadvantage=-1`. Damage modifier comes from `ElementDisadvantageCoef
  = -0.2` (advantage gives crit/crush bonuses, not damage adder).

Still open:

- [ ] **DEF_COEF in `DamageReductionByDefence`**: not exposed as a
  static field. **Plan landed**: damage hook now captures attacker
  ATK, target DEF, target HP, raw + post-mitigation damage. After a
  fresh CB run, back-solve DEF_COEF empirically from many events,
  cross-check with community estimate (~600 per kianl.com,
  level-scaled).
- [ ] **Stoneskin formula**: `StoneSkinDamageFactor` in DamageCalculator.
  Community guides say "scales with missing HP %" but the exact curve
  is unknown. Same back-solve approach via the new stat-capture hook
  (need a hero with Stoneskin equipped to capture events).
- [ ] **HP Burn StackCount=1 vs observed-stacks**: capture a multi-burn
  tick log (Ninja A2 / Sicia A2 active) and inspect whether the boss
  has multiple AoEContinuousDamage applied effects via the
  AppliedEffectsByHeroes dict.
- [ ] **`HealOnStartRound`** behaviour in CB: CB has 1 round per fight.
  Does the 20% heal trigger on round start (i.e. battle start) only?
  Or every CB turn (no — that would be absurd)? Verify via tick log.
- [ ] **Counterattack modifier application**: verify `-0.25` is being
  applied to counterattack damage in sim's CA handler.
- [ ] **NewbieDefence**: `NewbieDefenceDamageFactor` — early-game
  protection. Possibly relevant only at low account levels; verify
  scope.
- [ ] **CrabShell**: `Phase_CrabShellProcessing` exists in damage
  pipeline. Investigate what it does (maybe Demytha A2 heal-style
  shield?).

---

## 12. External research notes

### Affinity / Hit Type — ✅ Plarium-confirmed mechanics

From Plarium official + community sources (HellHades, AyumiLove,
forum.plarium.com):

> "If the attacker has an Affinity Advantage, there is a 50% chance of
> a Skill landing as a Crushing hit and an extra 15% chance of a Skill
> landing as a Critical Hit. If the attacker has an Affinity
> disadvantage, damage is reduced by 20% and there is a 35% chance of
> getting a Weak Hit."

Hit-roll algorithm (from Plarium forum):

> "The game calculates one random value between 0 and 100. If the rolled
> value falls within the Critical Hit range, a Critical Hit triggers.
> If the rolled value does not fall within the Critical Hit range but
> falls within the Crushing Hit range, a Crushing Hit triggers. If the
> rolled value falls into neither Critical nor Crushing ranges, a
> Normal Hit triggers."

Cross-references with `GameplayData` constants confirmed:
- `CriticalHitChance = 0.15` (base)
- `CriticalHitChanceAdvantage = 0.15` (extra on affinity advantage → 30% baseline crit)
- `CrushingHitChance = 0.5` (only relevant on advantage)
- `GlancingHitChance = 0.35` (only relevant on disadvantage)
- `ElementDisadvantageCoef = -0.2` (-20% damage on weak hit, NOT -30%)
- `CrushingHitCoef = +0.3` (+30% damage on crush)
- `GlancingHitCoef = -0.3` (-30% damage on glance)

Crit damage multiplier (community-verified):
- `CritMultiplier = 1.0 + (CritDamage% / 100)` — applied multiplicatively
- e.g. 180% CD → ×2.8 damage on crit

### Damage Formula (HellHades guide)

> "Total ATK (or HP or DEF for HP or DEF champions) × Skill Multiplier
> × Increase Damage from Books × Crit Multiplier × Mastery Bonuses
> × Chance of Affinity Bonus × Buffs × Passives × Defense Mitigation"

Applied in this order, multiplicatively. Buffs/debuffs that change
damage taken (DEF Down, Weaken, Stoneskin, Crushing Rend) all combine
multiplicatively, NOT additively.

### DEF Mitigation (raid.guru / community)

> `Damage Reduction = ZSHT / (600 + ZSHT)` — where ZSHT is "effective
> DEF" (post-buffs/debuffs/ignore-DEF).

Different sources cite different constants (600, 350, 1100). The
factor depends on hero level: `coef = level × C` for some C. The
exact value lives in the IL2CPP `DamageReductionByDefence` body.

**Plan**: extend the mod's damage hook to also capture attacker ATK
and target DEF per event, then back-solve the formula from many
real damage events. The hook already captures `calc_raw`
(MultiplierValuePositive — pre-mitigation) and `calc` (post-mitigation
ActualValue). Adding ATK + DEF closes the loop.

### Demon Lord skills + immunities (cross-verified)

AyumiLove + HellHades + game data agree on:

- A1 "Crushing Force" (skill 222601): hits 1, places Stun (cannot resist)
- A2 "Flesh Wither" (skill 222802): hits all 2× + places **2.5% Poison** for 2T
  (NOT 5% poison — different cap path on the boss)
- A3 "Dark Nova" (skill 222603): hits all 4× (4×ATK) + places ApplyBuff
- Passive "Gathering Fury" (skill 222904): T10-T19 ramping ×0.75/turn,
  T20+ ×7.5+(turn-19), T50+ enrage (ignore Block Damage / UK)
- Affinity start: **Void**. Below 50% HP → next battle uses random
  affinity (Magic / Force / Spirit). The 50%-HP transition is per-fight
  flag for the *next* fight, not mid-fight transformation.

Boss immunities (full list from BossImmunitiesEffects group):
Freeze, Provoke, Sleep, Stun, BlockHeal, BlockActiveSkills,
**ContinuousDamage** (5% poison applied via apply-debuff is blocked),
**AoEContinuousDamage** (HP Burn applied via apply-debuff is blocked),
Fear, BlockPassiveSkills, Petrification, Enfeeble, Rage, HuntersMark,
Ensnare, Fatigue, Nullifier, **StatusReduceSpeed**, LifeShare,
**ReduceStamina** (TM drain), IncreaseCooldown, SwapHealth, DestroyHp,
EvenStamina.

⚠️ The boss being immune to ContinuousDamage / AoEContinuousDamage as
a **kind group** is a key insight. Damage from these effects on the
boss must therefore route through the **per-difficulty cap rules**
(skill 200004/5/6/7 + 200008) which clamp the multiplier — i.e. the
boss treats poisons and burns as damage-only events, capped, with no
"actual debuff" in its bar. Sim should NOT model the 10-slot debuff
bar tracking poisons/burns on the boss; it should just apply
`min(formula_damage, cap)` per tick.

### NonIncreaseable (UK extension blocked)

✅ Live IL2CPP read via new `/static-field` endpoint:

```
NonIncreaseableEffects = [
  BlockDamage, Unkillable, ReviveOnDeath, StoneSkin, Taunt,
  PoisonCloud, Thunder, Entangle, Syphon, OnGuard
]
NonIncreaseableEffectGroups = [ ControlEffects ]
UnmodifiableEffects = [ TimeBomb, FireMark, Infest ]
```

So `IncreaseBuffLifetime` (kind 4011) cannot extend UK or BlockDamage.
Demytha A2 extends *other* buffs but UK/BD must stay at their natural
duration.

⚠️ Sim's `extend_buffs` extending UK/BD is **wrong** per game spec.
This is one of the documented compensating wrongs. Per-spec fix is
straightforward; impact on team-total damage needs the regression
suite to verify.

### Per-difficulty Poison + HP Burn caps — ✅ EXTRACTED

CB skill 200004/5/6/7 sets the per-tick caps for poisons:

| Difficulty | Skill ID | 2.5% Poison cap | 5% Poison cap |
|---|---:|---:|---:|
| Easy | 200004 | 10K | 20K |
| Normal | 200005 | 15K | 30K |
| Hard | 200006 | 20K | 40K |
| Brutal | 200007 | 25K | 50K |
| Nightmare | 200007 | 25K | 50K |
| **UltraNightmare** | 200007 | **25K** | **50K** |

All difficulties share **skill 200008** for HP burn caps:

| Producer rarity | Cap (undetonated) | Note |
|---|---:|---|
| Legendary (>=4) | **75K** | Most CB-relevant heroes |
| Epic (3) | **50K** | Mid-tier burners |
| Rare (<=2) | **15K** | Low-tier |
| Effect 5001632 / 5001612 (WM/GS) | **75K** | Always Legendary cap |

When detonated (Sicia A2, Ninja A2, Teodor A3, Venomage A1):
`cap × turns_left_of_remaining_burn`.

✅ Sim's `POISON_5PCT_DMG = 50000` matches **UNM** exactly.
✅ Sim's `HP_BURN_DMG = 75000` matches Legendary producers exactly.
🟡 Sim doesn't differentiate by producer rarity — needs to read the
hero's rarity from heroes_all.json and apply the right cap.

### Warmaster + Giant Slayer — ✅ EXACT FORMULAS

Skill 500161 (Warmaster) effect 5001612 (vs boss): `0.04 × TRG_HP`
Skill 500163 (Giant Slayer) effect 5001632 (vs boss): `0.03 × TRG_HP`

Both capped at **75K** per proc (skill 200008, special-cased).

For UNM (1.17B HP):
- WM raw: `0.04 × 1.17B = 46.8M` >> 75K → always capped at 75K
- GS raw: `0.03 × 1.17B = 35.2M` >> 75K → always capped at 75K

✅ Sim's `WM_DMG = 75000`, `GS_DMG ≈ 67626`. **GS should also be 75K**
(observed cluster median was 67626, but the cap is 75K — observation
under-counted because some procs landed pre-cap).

### Sources

- [HellHades — Damage calculation breakdown](https://hellhades.com/how-your-damage-is-actually-calculated-in-raid-shadow-legends/)
- [HellHades — Ultimate Clan Boss Guide](https://hellhades.com/ultimate-clan-boss-guide-everything-you-need-to-know/)
- [HellHades — Shield buffs](https://hellhades.com/shield-buff-raid-shadow-legends/)
- [Raid.guru — Damage formula](https://raid.guru/en/guide/damage-formula)
- [AyumiLove — Demon Lord guide](https://ayumilove.net/raid-shadow-legends-champion-ranking-in-clan-boss/)
- [Plarium forum — Affinity & crit math](https://forum.plarium.com/en/raid-shadow-legends/674_game-discussion/620516_crit-damage-math/)
- [Plarium forum — Damage based on ATK and DEF](https://forum.plarium.com/en/raid-shadow-legends/674_game-discussion/129633_damage-based-on-atk-and-def/)
- [DeadwoodJedi calc algorithm spec — local](docs/dwj/calc_algorithm.md) (scheduling only; no damage)

✅ External research complete.

