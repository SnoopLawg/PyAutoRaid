# Clan Boss meta research — April 2026

Scope: high-damage CB compositions beyond DeadwoodJedi's 103 tunes. Sourced from HellHades, Ayumilove, Metammo, and community record-holder posts. Use this alongside `data/dwj/parsed/tunes.json` to identify gaps in our scraped tune set.

## Essential meta damage dealers

| Champion | Affinity | Rarity | Role | Notes |
|----------|----------|--------|------|-------|
| Ninja | Void | Legendary | Ramping DPS + HP Burn | Featured in HellHades' 132.89M Unkillable record; needs A1-heavy preset to trigger +15% self TM vs boss |
| Geomancer | Spirit | Legendary | Overall DPS + HP Burn deflect | Default shield-set wearer in Brogni Infinity |
| Venomage | Magic | Epic | Poison stacker + Heal Reduction | Still best Epic poisoner in 2026 |
| Maneater | Spirit | Epic | Unkillable anchor | Core of every Unkillable tune |
| Acrizia | Void | Legendary | Enemy-MAX-HP damage | CBs now have explicit MAX-HP caps; still top single-target nuker within cap |
| Corpulent Cadaver | Void | Legendary | Shield-scaling DPS | Primary damage in Brogni Infinity |
| Frozen Banshee | Magic | Rare | Poisoner | Still the best Rare CB poisoner |
| Underpriest Brogni | Void | Legendary | Grow Shield | Only champion with Grow Shield — non-negotiable for Infinity |
| Wixwell / Vault Keeper Wixwell | Void | Legendary | Shield + Intercept (eats stun) | Alt to Brogni for Infinity variants |
| Cardiel | Magic | Legendary | Ally Attack + Inc CR/CD | "Partly responsible for the Unkillable world record" (HellHades) |
| Lanakis | Magic | Legendary | Ally Attack + buff extender | Key to 1.1B world record team |
| Krisk the Ageless | Spirit | Legendary | Buff extender + SPD aura | 3T CD, Infinity core |
| Lady Mikage | Void | Legendary | Buff extender | HellHades notes "gainable over time by any player" |
| Hellborn Sprite | Force | Legendary | Buff extender + Weaken | Featured in 1.1B record |
| Corvis the Corruptor | Void | Legendary | Buff extender + Poisons | 2nd-source Demytha extender |
| Sicia Flametongue | Force | Legendary | HP Burn activator | More a Spider champ than CB mainstay, but enables burn-instant combos |

## Composition archetypes beyond DWJ's trichotomy

1. **Infinity Shield (Brogni-core)** — Brogni + 3 AoE buff-extenders on 3T CDs + 1 DPS. Shields grow 30% of damage dealt via Brogni's A2 "Cavern's Grasp". Spirit-day cheese teams clear >500M. Canonical 1.1B composition: Brogni / Krisk / Lanakis / Hellborn Sprite / Corpulent Cadaver.

2. **Infinity Shield (Wixwell-core)** — Replace Brogni with Wixwell. Shield growth lower but Intercept buff eats CB stun. "More flexible" (HellHades) for non-Spirit days. Typical: Demytha / Anchorite / Geomancer / Gnut / Wixwell.

3. **2:1 Speed Tune (Ally-Attack nuker)** — 250+ SPD on all. Lanakis/Cardiel/Fahrakin enable 2 extra hits per CB turn. HellHades: "the only way to consistently reach 100M+ on UNM."

4. **Myth-Heir** — Demytha + Heiress + Seeker. Heiress's passive extends Demytha's Block Damage. Seeker TM boost fits extra attacks per cycle.

5. **Kymar double-rotation** — Experimental. Kymar + burst nuker for double-ability turns. Not yet in DWJ's 103 tunes.

## Record holders (UNM unless noted)

| Team | Heroes | Damage | Source | Reproducibility |
|------|--------|--------|--------|-----------------|
| Infinity Gauntlet | Brogni + Krisk + Lanakis + Hellborn Sprite + Corpulent Cadaver (184/286/269/245/195 SPD) | **1.1B** competition record | DeadwoodJedi `/infinity-gauntlet-clan-boss/` | Spirit day + world-class gear only |
| VictorTES Infinity Shield | Brogni-based, Spirit affinity | **570M+** | Ayumilove | Spirit day only |
| HellHades Ninja Unkillable | Ninja-anchored Unkillable | **132.89M single key** (self-claimed world record for Unkillable) | HellHades | Realistic upper bound for skilled F2P |
| Wixwell Infinity (Ayumilove) | Demytha 274 / Anchorite 253 / Geomancer 215 / Gnut 155 / Wixwell 257 | ~250M | Ayumilove | Requires Wixwell pull |
| High Khatun Wixwell | HK 285 / Geo 215 / Anchorite 253 / Godseeker Aniri 226 / Wixwell 257 | ~130M | Community | Requires Wixwell pull |

## Gaps vs DeadwoodJedi's 103 tunes

- **Ninja-specific Unkillable archetype** — HellHades has "Utilizing Ninja in CB" with Saphyrra's StarCraft Eater, Easy Double ManEater, Budget Unkillable variants *built around* Ninja's A1 TM-boost quirk. DWJ has Ninja in tunes but no archetype centered on solving his TM timing.
- **Acrizia boss-nuker** — No DWJ tune named for her. HellHades + community spotlight her as top single-target nuker.
- **Infinity Gauntlet 3-extender loop** — DWJ has Wixwell-Infinity but the Brogni "Infinity Gauntlet" world-record-pattern requires verifying our tune data has the exact 184/286/269/245/195 SPDs.
- **Kymar double-rotation** — Community experimental, no production-ready tune.

## Not recommended for CB (avoid research rabbit holes)

- **Tormin the Cold** — HellHades: "freeze-based mechanics not well-suited" for CB.
- **Tormin + Tuhanarak** — Arena focus.
- **Sabrael the Distant / Mavara the Web Diviner** — New 2026 Legendaries; Arena-focused, not CB meta.

## Synergy cheat-sheet

- **Ninja must wear Life Drinker** to avoid being the stun target.
- **Wixwell Intercept** blocks one debuff per stack — negates CB stun while stacks hold.
- **Demytha + Heiress** — Heiress extends Demytha's Block Damage for full CB-turn coverage.
- **Brogni needs a Shield-set wearer** (usually Geomancer) so his A2 grows both shield layers.
- **Buff extender alignment**: Krisk/Lanakis/Sprite/Mikage all on 3T CDs — Infinity requires every CB turn has an AoE extender active.
- **Sicia A2** instantly activates HP Burns *and* decrements duration by 1.
- **Cardiel A3** = ally-attack + Inc CR + Inc CD; stacks with Warmaster + Giant Slayer procs.
- **ACC baseline**: Easy 20 / Normal 50 / Hard 70 / Brutal 140 / NM 220 / UNM 220 (debuffs land reliably).
- **Speed-tune primacy**: "a perfectly tuned Unkillable team with average champions out-damages a poorly tuned team of top-tier Legendaries" (Metammo). Validates our DWJ-centric approach for sub-150M runs; Infinity / 2:1 become necessary above.

## Sources

- HellHades Guide to Clan Boss — https://hellhades.com/hellhades-guide-to-clan-boss/
- HellHades Utilizing Ninja in CB — https://hellhades.com/utilizing-ninja-in-clan-boss/
- HellHades Wixwell Infinity CB Team Guide — https://hellhades.com/wixwell-infinity-clan-boss-team-guide/
- HellHades Best Boss Damage Champions — https://hellhades.com/best-boss-damage-champions-in-raid-shadow-legends-top-single-target-nukers/
- HellHades Best Ally Attackers for CB — https://hellhades.com/raid-shadow-legends-best-ally-attackers-for-clan-boss/
- HellHades Mythbusted (Demytha) — https://hellhades.com/mythbusted-a-new-clan-unkillable-boss-team/
- HellHades Cardiel — https://hellhades.com/raid/champions/cardiel/
- DeadwoodJedi Infinity Gauntlet — https://deadwoodjedi.com/infinity-gauntlet-clan-boss/
- DeadwoodJedi Wixwell Infinity — https://deadwoodjedi.com/wixwell-infinity-clan-boss-team-guide/
- DeadwoodJedi Cardiel Guide — https://deadwoodjedi.com/the-golden-boy-of-clan-boss-cardiel/
- DeadwoodJedi Double Demytha — https://deadwoodjedi.com/speed-tunes/double-demytha/
- DeadwoodJedi Myth Heir — https://deadwoodjedi.com/speed-tunes/myth-heir/
- DeadwoodJedi Ma'shalled White Whale — https://deadwoodjedi.com/speed-tunes/mashalled-white-whale/
- Ayumilove Infinity Shield — https://ayumilove.net/raid-shadow-legends-infinity-shield-clan-boss-team-guide/
- Ayumilove CB Ranking — https://ayumilove.net/raid-shadow-legends-champion-ranking-in-clan-boss/
- Metammo 2026 CB Guide — https://metammo.com/guides/raid-shadow-legends-clan-boss-guide-unkillable-teams
- InTeleria Speed-Tuned CB Teams — https://www.inteleria.com/raid-speed-tuned-clan-boss-teams/
