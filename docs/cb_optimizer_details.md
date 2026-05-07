# CB Optimizer & Simulator — Detailed Reference

For high-level architecture, see CLAUDE.md. This doc covers calibration data, verified results, and deep implementation details.

## Gear-Optimizer SPD-Calc Calibration (learned the hard way)

- **Lore of Steel mastery ID = `500343`** (Support T4 col 3). Amplifies all basic set bonuses by +15% (Speed set 12% → 13.8%). Earlier code checked wrong IDs (500333/500334).
- **Raid rarity codes: 1=Common, 2=Uncommon, 3=Rare, 4=Epic, 5=Legendary.** Empowerment selection: `rarity >= 5` for legendary, not `>= 4`. Epic caps at +10 SPD (emp4), Legendary at +15.
- **`CalcEmpowerBonus` only returns HP/ATK/DEF** — NOT SPD/ACC/RES/CR/CD. Add those separately from `EMPOWERMENT_BONUSES` table. Epic emp3 → +5 SPD.
- **`flat_bonus` only aggregates HP/ATK/DEF/SPD** — NOT ACC/RES/CR/CD. Use `flat_bonus` for the 4 scaling stats (includes Divine-rank enhancement bonuses), iterate `primary` + `substats` for ACC/RES/CR/CD.
- **Divine enhancement:** e.g. Demytha's weapon (id 29809) has substat SPD=11+glyph 5=16, but `flat_bonus.SPD=22`. Extra 6 is Divine enhancement with no substat row.
- **Calibration vs live (post-fix):** Maneater 288.6/288-289 ✓, Demytha 172.1/173 ✓, Geomancer 179.0/179 ✓, Ninja 205.8/206 ✓, Venomage 162.0/162 ✓. Residual ±1 is game rounding.

## DWJ Myth-Eater Tune Presets

Target in-game speeds (embedded in `gear_optimizer.py` MYTH_EATER_SPEEDS):
```
Maneater   287-290   (tight)
Demytha    171-174
Ninja      204-207   (1:1 DPS variant, NOT 4:3)
DPS_1to1   177-180   (Geomancer slot)
DPS_slow   159-162   (Venomage slot)
```
UNM tune syncs on boss turn 6. Missing even one slot breaks sync.

## Verified Tune Performance (2026-04-13, UNM Force Affinity)

Speeds: Maneater 288-289, Demytha 173, Ninja 206, Geomancer 179, Venomage 162.
Result: **50/50 CB turns, 30.78M total damage, zero deaths.** Previous misaligned run (Demytha 229, Maneater 227) did 13M with team wipe at boss turn 26 — 2.4× improvement just from correct speeds.

## Force-Affinity Mode Observations

- Boss has infinite HP; `DamageTaken` accumulates normally (headline damage number).
- Boss flags: `dying:100%` permanently, `block_heal:~90%+` when Block Heal debuff landing.
- Per-skill damage caps: `+75K` (A1/WM/GS/passive), `+175K` (A2/A4), `+250K` (A3/AoE). Hard game caps in FA mode.
- Player HP tracking still works normally. `DestroyedHealth` unreliable in FA; use `dmg_taken` + `hp_cur`.
- `block_heal` is NOT HP Burn. Block Heal = prevents healing. HP Burn = DoT, no HeroState boolean.

## CB Sim Refinements (calibrated vs live run)

- **Force-Affinity caps:** `FA_CAP_BIG=250K`, `FA_CAP_MEDIUM=175K`, `FA_CAP_SMALL=75K`, `FA_CAP_DOT=75K`. Applied at all damage sites. Default `force_affinity=True`, disable with `--no-force-affinity`.
- **Removed Budget-UK speed overrides** that broke non-Budget tunes. Now uses actual calculated speeds.
- **Calibration:** sim predicted 36.5M (caps ON) vs 30.78M actual (18% over). Caps-OFF = 46.9M (52% over). Gap is rotation-timing / debuff-uptime modeling.

## Game Stat Calculator Integration

The mod calls the game's own `HeroExtensions` static methods:
- `GetBaseStats(hero)` → level-scaled base (HP×165, ATK/DEF×11.0 at 6★ L60) ✓
- `CalcBlessingBonus(hero)` ✓
- `CalcArenaBonus(hero, ArenaLeagueId)` ✓
- `CalcBuildingsBonus(hero, BuildingSetup)` → Great Hall ✓
- `CalcEmpowerBonus(hero)` → HP/ATK/DEF only ✓
- `CalcRelicsBonus(hero, relicSetups)` → returns 0 (pending, ~900 HP gap)
- Saved to `hero_computed_stats.json` (511 heroes)

## StatusEffectTypeId Breakthrough

Mod reads `EffectType.ApplyStatusEffectParams.StatusEffectInfos[i].TypeId` for exact buff/debuff types. Key corrections:
- Maneater A1: **Dec ATK 50%** (not Poison)
- Maneater A3: **Unkillable + Block Debuffs** (not Block Damage)
- Geomancer A3: **HP Burn + Weaken 25%** (not Poison)
- Corvis A1: Dec ATK, A3: Poison + Poison Sensitivity
- Skullcrusher A2: Ally Protect + Counterattack + Unkillable
- Venus A2 (CD3): DEF Down 60% + Weaken 25%, A3 (CD5): HP Burn

## Sim-Verified Best Teams

- **#1 UK:** 2×Maneater + Geomancer + Venus + Corvis = **50.1M/key** (VALID tune, 0 gaps)
- **#2 UK:** 2×ME + Skullcrusher + Geomancer + Fayne = **49.1M**
- **#3 UK:** 2×ME + Geomancer + Fayne + Fahrakin = **49.1M**
- **Non-UK:** Cardiel + Ma'Shalled + Skullcrusher + Geomancer + Gnut = **23.1M** over 27 turns
- **Current Best:** ME + Demytha + SC + Venomage + Sicia = ~63M (full auto, VALID tune)

## Non-UK Survival Model

Fully modeled: HP tracking, CB AoE damage (DEF formula), Gathering Fury (+2%/turn after T10), Lifesteal (30%), Leech (10%), Ally Protect, Cardiel passive (20% dmg reduction + BD on dying ally), UDK passive (UK at 1HP), Ma'Shalled A3 (50% dmg reduction), Gnut extra turns, Counter-attack healing chain, Block Debuffs prevents stun, Stalwart/Regen/Immortal sets. All passives auto-detected from skills_db.json.

## DWJ Speed Tune Mechanics

- **TM fill**: speed per tick, threshold 1000 (equivalent to DWJ's speed×0.07, threshold 100)
- **Tie-breaking**: highest TM → highest speed → position
- **Buff timing**: `isAddedThisTurn` — buffs don't tick on application turn. Critical for Unkillable.
- **Stun target**: Highest TM with skill on cooldown
- **Gathering Fury**: Round-based (+2% per round after round 4), NOT per-turn

## Skills from Game Data

`tools/load_game_profiles.py` reads `hero_profiles_game.json` (137 heroes). Key corrections:
- Maneater A3: Unkillable 2T + Block Debuffs 2T (NOT 3T UK + 1T Block Damage)
- Sicia A3: Extra Turn (NOT Counterattack)
- Ninja A1: DEF Down 60% + 15% self TM
- Ninja passive: +20% ATK + 10% CD per combo on bosses
- OB A2: 12.4×ATK + Extra Turn + 30% ignore DEF

## Remaining Gaps

- Relic bonus (CalcRelicsBonus returns 0, ~900 HP missing)
- Leader skill auras not applied
- Affinity weak/strong hit modifier
- Some passives need deeper modeling (Gnut extra turns)
- `calc_stats()` doesn't add empowerment SPD/ACC/RES/CR/CD — in-game speed is truth
- Evil Eye mastery: once per target per battle, NOT every A1
- Lore of Steel (+15% to set bonuses) — not applied in calc_stats
- 4-piece set bonuses not recognized
