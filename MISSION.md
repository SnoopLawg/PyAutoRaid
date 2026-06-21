# PyAutoRaid Mission

The "why". Evergreen. Companion to `CLAUDE.md` (the "how") and
`docs/roadmap.md` (the "what's next").

## Purpose

Enhance my Raid: Shadow Legends experience by automating its grind,
logging its battles with forensic precision, reverse-engineering its
mechanics from the running game, and using that understanding to
recommend better teams, gear, and progression decisions than any
external source could.

The end-state is a system that:

1. **Runs** every battle the game offers — daily, weekly, monthly,
   tournament, event, CB, Hydra, Chimera, Arena, Tag Team Arena, and
   beyond — only when resources support it, and with smart skip when
   they don't.
2. **Logs** what happened during the battle (per-tick state) and what
   resulted from it (resources spent, drops won, leaderboard delta).
3. **Understands** every boss AI, every hero kit, every mastery,
   blessing, set, and gear contribution — sourced from the game's
   IL2CPP runtime, not from third parties.
4. **Recommends** teams, gear, and hero investment organically from
   that understanding. External sources (HellHades, DeadwoodJedi) stay
   as sanity-checks only — never as authoritative inputs.

## Non-negotiables

- **Mod API only for game actions.** No screen automation for clicks
  or input. Read-only screen access (screenshots, OCR) is permitted
  *only* as a diagnostic fallback when the mod API returns ambiguous
  state. Game inputs always go through `RaidAutomationPlugin`.
- **Game data is ground truth.** When sim, logger, or recommender
  diverges from observed game behavior, the divergence is a
  *symptom* — the fix is to find the literal mechanic in
  `GameAssembly.dll` or `data/static/*.json`, never to band-aid a
  constant. See `CLAUDE.md` → "Reverse-Engineering Methodology" for
  the extraction pipeline.
- **CLI is the source of truth.** Every feature has a `tools/<x>.py`
  entrypoint with `if __name__ == "__main__"`. The dashboard, the
  scheduler, and any future surface are thin wrappers calling the
  same domain functions.
- **Prompt before destructive actions.** Battles run autonomously.
  Sells, equips, preset writes, rank-ups, and any mutation visible
  in-game require user confirmation (one-tap). Reads, sims, plans,
  and recommendations always auto.
- **Recommendations gated on ±5% sim accuracy.** Per-affinity,
  per-tune, per-location, single-run. The sim must hit ±5% on a
  representative capture before its output ships as a prescriptive
  recommendation. Below the bar = sanity-check only, surfaced with a
  confidence label.

## The four pillars

### Run

A resource-aware orchestrator that drives every battle type the game
offers. Reads energy / keys / tokens / tickets before each attempt.
Skips when resources are too low. Picks the right preset for the
location. Logs every action through `CmdQueue.Enqueue` so we have an
audit trail.

### Log

Every battle captures per-tick state (TM, HP, buffs, debuffs, cooldowns,
skill selections, damage events with intermediates) via the mod's
Harmony hooks. Every battle also captures the *result*: items dropped,
silver gained, energy/keys/tickets debited, leaderboard delta, quest
counters ticked. Both streams flow to disk and SQLite for replay and
regression testing.

### Understand

A full game-data model maintained by `tools/refresh_static_data.py`
and the il2cpp dumper. Covers:

- Every hero (8100 rows × form × ascend grade): base stats, leader
  skill, skill IDs, effects, masteries, blessings.
- Every artifact: stat ranges, set rules, divine enhancement, glyph
  caps, faction locks.
- Every location: stage layout, enemy lineups, boss skill rotations,
  per-stage modifiers, drop tables.
- Every formula: damage mitigation, hit-type bonus, status-effect
  multipliers, TM math, AI selection — extracted literally from
  `GameAssembly.dll` and `data/static/*.json`.

### Recommend

Built on top of the Understand layer. Produces:

- **Team picks** for a given location, derived from kit synergies and
  boss mechanics, not from copying any external comp.
- **Gear loadouts** that hit per-location stat targets and maximize
  the location's scoring function (CB damage, Dragon clear time,
  Doom-Tower survival, etc.).
- **Hero investment guidance** (rank-up, book, ascend, mastery scrolls)
  prioritized by team gaps and event ROI.
- **Daily/weekly action plans** that score the highest-yield use of
  remaining resources.

External signals (HellHades tier ratings, DeadwoodJedi tunes) are
kept as cross-references that flag divergence ("sim says X, HH says
Y — investigate") but never as recommendation inputs.

## Methodology

When sim, logger, or recommender disagrees with the game:

1. **Check static first.** `grep MultiplierFormula
   data/static/skills_all.json`, `data/static/effects.json`,
   `data/static/gameplay.json`. Most "magic numbers" live in plain
   JSON.
2. **Decompile second.** If the value is computed (not stored), use
   the il2cpp dumper → capstone → pefile pipeline. See
   `CLAUDE.md` → "Refresh procedure for a new game version" for the
   command sequence.
3. **Capture live.** Add a Harmony hook in `RaidAutomationPlugin` to
   emit the value into the tick log. Verify in Python.
4. **Wire and remove the hack.** New constant or function lands in
   `tools/cb_constants.py` (or area equivalent); the hand-coded value
   in the sim is deleted.

Compensating wrongs (two bugs masking each other) are the methodology's
recurring enemy. When un-stacking, fix together — never piecemeal.

## Delivery model

- **Game-preset substrate.** Recommended teams and gear land in the
  game's 15 saved presets per hero via `/save-preset` /
  `/update-preset` / `/apply-preset`. The recommender drives what
  gets saved; the game does the apply. The user sees the result
  in-game in the same UI they already use.
- **Prompt-on-destructive.** Anything that mutates game state asks
  once. The audit log captures the request, the user response, and
  the resulting state delta.
- **Audit log.** Every destructive action and every battle result
  appends to a queryable record. Nothing happens silently.

## Test sandbox & key economy

Keys are the scarcest resource — 2 CB keys/day caps our empirical
iteration cycle. The sandbox philosophy maximizes data-per-key:

- **Kill-Raid-mid-fight preserves keys.** `taskkill /F /IM Raid.exe`
  during a CB battle does not debit the key (only successful
  completion does). Use this freely when redeploying mod fixes,
  capturing partial battle data, or aborting a doomed run.
- **Death-watcher pattern.** A background poller detects first hero
  death and kills Raid before the boss finishes the team. Maximizes
  pre-death tick data without spending the key. See planned
  `tools/cb_watcher.py`.
- **Fixture library.** Every real capture archives into a replayable
  fixture set. Sim changes regress against the full fixture battery
  on every commit. Live capture stays the oracle; replay is the
  iteration loop. Zero key cost per sim-code iteration.
- **Restart when in doubt.** Recovery hierarchy: `/overlay-state` →
  `/overlay-close-all` → kill Raid → full PP reset. Documented in
  `CLAUDE.md` → "Recovery: mod fails to attach".

## Knowledge persistence

Three tiers, intentionally separated:

- **`.claude/skills/`** — procedural know-how for future sessions
  (how to extract a formula, how to debug a wedged mod, how to
  capture a CB run). Long-lived. Composable.
- **`tools/<feature>.py`** — execution. Every domain function has a
  CLI. The skill explains *how*; the tool *does*.
- **SQLite (`pyautoraid.db`)** — runtime state. Captures, results,
  loadout snapshots, calibration history, recommendation audit.

Auto-memory is for cross-session *context* (user's roster, current
calibration baseline, known quirks). It is not where project specs,
roadmaps, or build instructions live — those go in the repo.

## What we do NOT do

- Screen automation for game actions (clicks, drags, keyboard).
- Back-fitting empirical constants when the literal value can be
  extracted from the game.
- Copying recommendations from HellHades, DeadwoodJedi, RSL Helper,
  or any external source into the recommendation path.
- Shipping prescriptive recommendations from a sim that hasn't hit
  the ±5% bar on the relevant affinity/tune/location.
- Half-finished features, dead code, or speculative abstractions.
  Three similar lines beats a premature framework.
- Catching errors we can't recover from. Silent `except` is a smell.
