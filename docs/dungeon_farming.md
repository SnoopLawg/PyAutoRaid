# Dungeon Farming — Stage Reference

Verified from `data/hh/regions.json` + community sources (2026-05). Replaces
the outdated "Stage 20 is best" guidance found in older articles, which
predates Hard mode entirely.

## Dungeon layouts

| Dungeon       | Normal      | Hard       | Notes                                |
|---------------|-------------|------------|--------------------------------------|
| Spider's Den  | Stages 1-25 | Stages 1-10 | Hard unlocks after clearing Normal 25 |
| Dragon's Lair | Stages 1-25 | Stages 1-10 | Speed + Lifesteal sets — meta CRITICAL |
| Fire Knight   | Stages 1-25 | Stages 1-10 | Stoneskin / Resilience               |
| Ice Golem     | Stages 1-25 | Stages 1-10 | Reflex / Provoke                     |
| Minotaur      | multi-difficulty (Easy / Normal / Hard / Brutal / NM / UNM) × stages | — | Scrolls, daily-capped per hero |

**Hard mode caps at stage 10**, NOT 20. Older guides referencing "Hard 20"
or "Hard 26" are wrong — they conflated Normal 20 with the Hard tier or
predate the Hard-mode launch.

## Drop tier by stage

| Stage tier              | Enemy level | 6★ rate | Mythical chance |
|-------------------------|-------------|---------|-----------------|
| Normal 1-19             | 7-260       | low     | none            |
| Normal 20-24            | 280-340     | medium  | none            |
| Normal 25               | 350         | medium  | none            |
| Hard 1                  | 350         | medium  | very small      |
| Hard 5-7                | 350         | high    | small           |
| Hard 10                 | 350         | high    | ~1%             |

**Mythical artifacts only drop in Hard mode** (1-10). They cannot drop in
Normal, regardless of stage. Higher Hard stage = higher Mythical chance.

**Hard 1 is strictly better than Normal 25** — same enemy level, same 6★
rate ballpark, plus a non-zero Mythical chance.

## Per-dungeon farm priority

The "best stage" is the highest Hard you can clear in **<40 seconds
reliably** (≥90% WR). If Hard is locked, Normal 20-25 is the best you can
do — Normal 20 is mid-game floor, Normal 25 is the unlock-Hard goal.

| Dungeon       | What it gives                          | Priority order                                  |
|---------------|----------------------------------------|-------------------------------------------------|
| Dragon        | Speed, Lifesteal, Crit Damage sets     | **HIGHEST** — Speed sets unlock everything else |
| Spider        | Reflex, Affinity Break, generic        | High — also drops accessories                   |
| Fire Knight   | Stoneskin, Resilience, generic         | Medium — needed for boss-immunity comps         |
| Ice Golem     | Reflex, Provoke, generic               | Medium                                          |
| Minotaur      | Mastery scrolls (capped per hero/day)  | Daily — always run highest cleared              |

## What's "fast enough" to farm?

| Clear time | Verdict                                         |
|------------|-------------------------------------------------|
| <30 s     | Optimal — go higher stage if reliable           |
| 30-50 s   | Good farm pace                                  |
| 50-90 s   | Acceptable but consider dropping a stage         |
| >90 s     | Going too high — drop a stage for better rate   |

If you can drop down a stage and clear it 2× as fast, the loot-per-minute
math usually favors the lower stage (drop quality differential between
adjacent Hard stages is small; speed differential is large).

## Endpoint references

- Stage tile text: `/get-text?path=...DungeonsDialog/Workspace/Content/Scroll View/Viewport/Content/{idx}` shows "Best Time" + "Lowest Turns" per stage — that's the user's current proven clear.
- Drop tables (canonical, from game data): `/dungeon-drops` (mod) snapshots every stage's possible drops. Cache to `data/dungeon_drops.json` for offline gear-gap analysis (see `tools/gear_gap_analysis.py`).
- HH-verified team comps: `data/hh/teams/{Dungeon}/Stage_{N}/teams_*.json` (variant list) and `details_*.json` (full stat targets + masteries + sets per hero). Cross-reference with owned roster in `data/hh/owned_typeids.json` to find buildable comps.

## Notes on the "Stage 20" myth

Older Raid farming guides (pre-2023) recommend "Stage 20" as the optimal
farm. This refers to **Normal 20**, not Hard. It was correct before Hard
mode shipped (March 2023). After Hard launched, Hard 1+ outclasses Normal
20 for any account that has Hard unlocked. Don't confuse the two.
