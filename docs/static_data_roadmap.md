# Static Data Roadmap

Goal: replace hardcoded constants and partial scrapes with **authoritative
in-memory `StaticData` reads from the live mod**, mirroring how HellHades
extracts the same information from Plarium's runtime.

## Reference: how HellHades does it

1. Acquires `SeDebugPrivilege` via UAC at install.
2. `OpenProcess(PROCESS_VM_READ, RaidPid)` → walks the IL2CPP managed-heap
   pointer graph from a known root (`AppModel.Instance.UserWrapper.*`).
3. Reads **on-disk `static-data/<version>/<hash>`** for game reference
   data (custom MessagePack — Plarium ExtType-wrapped).
4. Reads **`battle-results/battleResults`** for the last battle outcome
   per stage, persisted across sessions.
5. Pushes everything to `raidoptimiser.hellhades.com` via SignalR for
   server-side aggregation + UI display.

We have a strict superset of (1)+(2)+(3) because we run **inside** Raid via
BepInEx — the `StaticData` root is fully decoded by the IL2CPP runtime, so
we don't need to crack the on-disk MessagePack format. We can just read
typed fields off the live object graph.

## Current state

### `data/static/` — refreshed via `tools/refresh_static_data.py`

| File | Source endpoint | Records | Used by |
|---|---|---|---|
| `masteries.json`  | `/masteries-truth`  | 66  | (none yet — replaces `data/masteries_truth.json`) |
| `blessings.json`  | `/blessings-truth`  | 30  | (none yet — replaces hardcoded blessing values) |
| `drops.json`      | `/dungeon-drops`    | 46 regions | `tools/gear_gap_analysis.py` |
| `forge_sets.json` | `/forge-sets`       | 49 recipes | (reference) |
| `revision.json`   | `/status`           | meta | cache-bust signal |

Run `python3 tools/refresh_static_data.py` to refresh after a Raid update.
`python3 tools/refresh_static_data.py --check` reports stale files.

## Gaps — known, prioritized

### P1 — Boss stat profiles per stage  (impact: cb_sim accuracy)

**What's hardcoded today** (in `tools/cb_sim.py`):
```python
CB_ATK = 3950          # back-solved from real BT 1 AOE1 data (2026-04-23)
UNM_DEF = 11000
CB_AOE_MULT = 3.5
CB_SPEED_BY_DIFFICULTY = {"unm": 190, "nm": 170, ...}
```

**Where it lives in the game**: `StaticData.BattleQuestData.BattleQuestTypes`
(35 entries — CB Magic/Force/Spirit/Void × Easy/Normal/Hard/Brutal/NM/UNM,
Hydra, Chimera, Doom Tower, etc.). Each entry has the boss's full stat
block (HP, ATK, DEF, SPD, CR, CD, RES, ACC) and skill rotation pattern.

**Mod endpoint to add**: `/cb-bosses` that walks `BattleQuestData` and
emits per-difficulty boss profile JSON. Single endpoint, ~35 entries —
manageable.

**Wire-up**: `cb_sim.py` reads from `data/static/bosses.json`, indexes by
`(quest_type, difficulty)`. Removes `CB_ATK`, `UNM_DEF`, `CB_AOE_MULT`,
`CB_SPEED_BY_DIFFICULTY` constants.

### P2 — Effect (buff/debuff) catalog  (impact: schema drift safety)

**What's hardcoded today**: in `tools/raid_data.py` and various sim files —
status effect type IDs, durations, max-stack rules, FA caps. These shift
when Plarium adds new effects (recently: `Stone Skin`, etc.).

**Where it lives**: `StaticData.EffectData.AllEffectTypes` — every buff
and debuff with its kind, group, target, max-stack, dispellable, etc.

**Mod endpoint to add**: `/effects-truth` (mirroring `/masteries-truth` /
`/blessings-truth` shape).

**Wire-up**: `tools/sell_rules.py` reads effect catalog for the editor's
"useful substats" auto-suggest. cb_sim's effect dispatcher cross-checks
against the catalog so a missing effect id is loud, not silent.

### P3 — Artifact set bonus definitions  (impact: optimizer correctness)

**What's hardcoded today**: `tools/cb_optimizer.py` `SET_BONUSES` table.
2026-04-29 we burned a session because the table had Speed = 4-piece +25%
when real game says 2-piece +12%; manually re-derived from in-game
screenshot.

**Where it lives**: `StaticData.ArtifactData.SetKindToSetData` — every
set, its piece count, stat granted, value, plus any conditional/proc
effects (Stoneskin, Untouchable, etc.).

**Mod endpoint to add**: `/artifact-sets`.

**Wire-up**: `tools/cb_optimizer.py` and `tools/global_gear_solver.py`
read `data/static/artifact_sets.json` instead of the hand-coded table.
Lore of Steel mastery's +15% multiplier still applies — that part stays
in `cb_optimizer`.

### P4 — Hero base stats + leader skills

**What's mixed today**: `heroes_all.json` (live data via `/all-heroes`)
contains current per-account stats including gear bonuses; it does NOT
contain pristine BASE stats per hero type or the leader skill effect.

**Where it lives**: `StaticData.HeroData.HeroTypeById` (8,100 entries —
every hero × form × ascend grade). Each `HeroType` has BaseStats and a
LeaderSkill DTO with stat affected, value, target faction filter.

**Mod endpoint to add**: `/hero-types` — full schema, paginated.

**Wire-up**: cb_sim's stat composition reads base stats from static; live
gear stats stack on top. Fixes "speed aura" inconsistencies where we hand-
codeMa'Shalled +24% SPD aura instead of reading the LeaderSkill DTO.

### P5 — Persistent battle history (`battleResults` file)

**What HH does**: tails `%LOCALAPPDATA%/Plarium/Raid_ Shadow Legends/battle-results/battleResults`
to track "last team used per location" even when the user closes/reopens
the game. We currently track this only for our own `cb_run.py` invocations.

**Implementation**: `tools/battle_history_tail.py` watches that file (it's
small MessagePack, ~10 bytes for a single battle). On change, decode and
append to `data/battle_history.jsonl`. Dashboard reads to render
"per-location last team" panels.

## Architecture

```
Raid.exe
  ├─ memory: AppModel.Instance.UserWrapper          ← live account state
  │   └─ /all-heroes /all-artifacts /battle-state    (mod endpoints we have)
  │
  └─ memory: AppModel.Instance.StaticData            ← reference data (this doc)
      ├─ MasteryData    → /masteries-truth   ✅
      ├─ EffectData     → /effects-truth     P2
      ├─ ArtifactData   → /artifact-sets     P3
      ├─ BattleQuestData→ /cb-bosses         P1
      ├─ HeroData       → /hero-types        P4
      ├─ StageData      → /dungeon-drops     ✅ (partial — drops only)
      ├─ ForgeData      → /forge-sets        ✅
      └─ ...           (50+ sections; only what we need gets endpoints)

%LOCALAPPDATA%/Plarium/Raid_ Shadow Legends/
  ├─ battle-results/battleResults                    ← persistent history (P5)
  └─ static-data/<ver>/<hash>                        ← MessagePack ref data
                                                       (NOT NEEDED — mod gives
                                                        decoded equivalent)

PyAutoRaid/
  └─ data/static/             refreshed by tools/refresh_static_data.py
      ├─ masteries.json         ✅
      ├─ blessings.json         ✅
      ├─ drops.json             ✅
      ├─ forge_sets.json        ✅
      ├─ bosses.json            P1 (next)
      ├─ effects.json           P2
      ├─ artifact_sets.json     P3
      ├─ heroes.json            P4
      └─ revision.json          ✅
```

## Workflow

### After a Raid version bump
```bash
# Mod auto-relaunches. Then:
python3 tools/refresh_static_data.py
# Inspect data/static/revision.json to confirm new mod_version
```

### Before any sim correctness work
```bash
python3 tools/refresh_static_data.py --check
# Bails if any section is older than 24h — prevents silent staleness
```

### Adding a new section
1. Add a mod endpoint in `RaidAutomationPlugin.cs` that walks the
   relevant `StaticData.<X>` subtree and emits clean JSON.
2. Register it in `tools/refresh_static_data.py` `SECTIONS` dict.
3. Run `python3 tools/refresh_static_data.py --section <new>` to verify.
4. Wire consumers (cb_sim / optimizer / etc.) to read the JSON.

## Non-goals (intentional)

- **Cross-account team library** — HH's 6,716-team CB UNM database is a
  community feature, not a tech gap. Solo use doesn't need it.
- **Hero portraits** — only matters for richer dashboard UI; not a sim
  correctness issue. Out of scope until we want a shipped UI.
- **Cracking Plarium's MessagePack format** — the in-memory mod path
  bypasses the need to decode the on-disk `static-data/<hash>` file.
