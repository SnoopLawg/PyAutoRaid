# CLAUDE.md

## Project Overview

PyAutoRaid automates Raid: Shadow Legends via a BepInEx mod HTTP API (port 6790) running on the local Windows PC (no VM). Primary focus: CB optimization with a turn-by-turn damage simulator calibrated to -7% of real battle data.

**NEVER use UI/screen automation.** All game actions go through the mod API context-calls.

## Quick Commands

```bash
# CB battle (navigate → start → poll → log → calibrate)
python3 tools/cb_run.py --calibrate --cb-element void

# Daily CB automation (cron-ready, runs all keys)
python3 tools/cb_daily.py --wait --cb-element force

# Rebuild + redeploy mod (local)
"/c/Program Files/dotnet/dotnet" build -c Release mod/bepinex
taskkill //F //IM Raid.exe   # PlariumPlay stays up
cp mod/bepinex/bin/Release/net6.0/RaidAutomationPlugin.dll \
   "C:/Users/logan/AppData/Local/PlariumPlay/StandAloneApps/raid/build/BepInEx/plugins/RaidAutomationPlugin.dll"

# Mod fails to attach (localhost:6790 dead despite Raid running) — full PP reset
./tools/reset_pp.sh

# Full data refresh + rebuild
python3 tools/refresh_all.py --calibrate        # from live mod
python3 tools/refresh_all.py --offline           # rebuild from cached JSON

# Sim & optimization
python3 tools/cb_sim.py --team "ME,Demytha,Ninja,Geo,Venomage" --cb-element void
python3 tools/cb_sim.py --tune myth_eater --team "ME,Demytha,Ninja,Geo,Venomage"
python3 tools/cb_sim.py --list-tunes
python3 tools/cb_team_search.py --top 20
python3 tools/cb_gap_analysis.py
python3 tools/global_gear_solver.py --team "ME,Demytha,Ninja,Geo,Venomage"
python3 tools/auto_profile.py --hero Venus
python3 tools/desc_profiler.py --compare

# DWJ-parity work (unified entry: tools/cb.py)
python3 tools/cb.py potential --runnable                  # DWJ tunes you can run today
python3 tools/cb.py potential --missing 1                 # 1 hero away
python3 tools/cb.py sim --slug myth-eater --turns 25      # DWJ-parity scheduler
python3 tools/cb.py sim --hash <variant_hash> --trace     # per-action TM dump
python3 tools/cb.py inspect list                          # 103 scraped tune slugs
python3 tools/cb.py inspect tune myth-eater               # variants + slot configs
python3 tools/cb.py inspect champion Ninja                # skills + effects
python3 tools/cb.py parity --hash <h> --text-file dwj.txt # diff sim vs live DWJ
python3 tools/cb.py gaps --roster-only                    # HH cross-reference
python3 tools/cb.py dungeon --dungeon dragon --stage 20 --start  # Village->battle
```

`tools/cb.py` thin-dispatches into `comp_finder`, `calc_parity_sim`,
`calc_parity_check`, `dwj_inspect`, `hh_vs_dwj`, `dungeon_run`. The
dashboard's `potential teams` + `cast timeline` panels (port 6791)
read the same data.

## CB Sim Accuracy

Calibrated to **-7%** vs real battle data (46.15M actual, 38M sim, Void affinity).

Key mechanics:
- All fights uncapped (no FA damage caps)
- CB element defaults Void; pass `--cb-element` for day's affinity (Magic heroes do -30% vs Force)
- WM/GS: flat 75K per proc, NOT multiplied by DEF Down/Weaken
- Debuff placement: >=50% chance places immediately, <50% uses fractional accumulator
- Debuff duration: `remaining < 0` expiry (2-turn debuff lasts 2 CB turns)
- Book bonuses on debuff chances auto-applied from skills_db level_bonuses
- Desc-profiler auto-corrects all skill effects from game descriptions
- Ninja Escalation: capped at +100% ATK (5 stacks), increments per full A1+A2+A3 cycle
- Turn 50 enrage: no hero actions after final CB turn
- Geomancer passive: deflect scales with Gathering Fury + HP Burn presence

### Skill Effect Mapping (kind → sim)

| Kind | Sim Effect | Per-Hero |
|------|-----------|----------|
| 5000 | debuff placement | All (chance from desc + books) |
| 4000 | buff placement | All |
| 4007 | extra turn | Sicia A3, Ma'Shalled A2, OB A2 |
| 5008 | extend debuffs | Sicia A1 (HP Burn only), Teodor A3 (poison+burn), others (all) |
| 9002 | activate DoTs | Ninja A2 (burns, once/skill), Sicia A2 (burns), Venomage A1 (poisons, max 2), Teodor A3 (all DoTs) |
| 7001 | ignore DEF | Ninja A3 (50%), OB A2 (30%), per desc |
| 4006 | ally attack | Fahrakin A3, Cardiel A3 (with Inc CR/CD buffs) |

## DWJ Calculator Parity

`tools/calc_parity_sim.py` is a separate, **100%-matching** Python port of
DeadwoodJedi's calc scheduler (turn-meter ticks, priority/CD/delay picking,
buff/debuff effect dispatcher). Verified action-for-action on 4 diverse
variants (Myth Eater Ninja, Myth Eater std UNM, Batman Forever, Endless
Speed). Spec lives in `docs/dwj/calc_algorithm.md`; data lives in
`data/dwj/parsed/` (103 tunes + 246 calc variants + 859 champion configs)
and `data/hh/parsed/` (1013 HellHades champion ratings).

Use `tools/cb.py` for everything DWJ-parity: `potential` (roster vs tunes),
`sim` (turn-by-turn cast timeline), `parity` (diff sim vs live DWJ text),
`inspect` (browse scraped data), `gaps` (HH cross-reference). The dashboard
(port 6791) renders the same data in `potential teams` + `cast timeline`
panels.

### How to Start CB Battle (mod API only)
```
curl /navigate?target=cb
curl /context-call?path=...AllianceEnemiesDialog/.../RightPanel&method=OnStartClick
curl /context-call?path=...AllianceBossHeroesSelectionDialog&method=StartBattle
```

## Tools

| Tool | Purpose |
|------|---------|
| `tools/cb_run.py` | One-command CB battle runner (start → poll → log → calibrate) |
| `tools/cb_daily.py` | Cron-ready daily CB (runs all keys, stores to DB) |
| `tools/refresh_all.py` | Full pipeline: fetch → rebuild DB → verify profiles → calibrate |
| `tools/cb_sim.py` | Turn-by-turn damage simulator with DWJ tune support |
| `tools/tune_library.py` | DWJ speed tune definitions (Myth Eater, Budget UK, Batman Forever, etc.) |
| `tools/desc_profiler.py` | Parse skill descriptions → auto-correct sim effects |
| `tools/auto_profile.py` | Auto-generate CB profiles for all 343 heroes |
| `tools/cb_calibrate.py` | Per-turn sim vs real battle log comparison |
| `tools/global_gear_solver.py` | Constraint + SA gear optimizer across 5 heroes |
| `tools/cb_team_search.py` | Exhaustive team evaluation (4000+ combos) |
| `tools/cb_gap_analysis.py` | Hero gap analysis (roster + pull priority) |
| `tools/db_init.py` | SQLite database builder (pyautoraid.db) |
| `tools/refresh_data.py` | Fetch heroes/artifacts/skills from mod API |
| `tools/cb.py` | Unified CLI for DWJ-parity work (potential / sim / parity / inspect / gaps) |
| `tools/calc_parity_sim.py` | DWJ-parity turn scheduler (100% match, 4/4 variants tested) |
| `tools/comp_finder.py` | Score 103 DWJ tunes against owned roster (runnable / N-away) |
| `tools/dwj_inspect.py` | Browse scraped DWJ tunes, variants, champions |
| `tools/calc_parity_check.py` | Diff sim cast order vs live DWJ rendered text |
| `tools/hh_vs_dwj.py` | HellHades cross-reference (gap finder, roster snapshot) |
| `tools/scrape_dwj.py` / `scrape_dwj_calc.py` | DWJ WordPress + calculator scrapers |
| `tools/scrape_hellhades.py` | HH WordPress scraper (champions + tierlist + posts) |
| `tools/dashboard_server.py` | HTTP dashboard server (port 6791) |

## Data Files

| File | Content |
|------|---------|
| `heroes_all.json` | 482 heroes with stats, artifacts, masteries |
| `all_artifacts.json` | 2684 artifacts (equipped + vault) |
| `skills_db.json` | 1370 skills with effects + descriptions |
| `skill_descriptions.json` | Game-localized skill text for 321 heroes |
| `hero_profiles_game.json` | 137 game-extracted skill profiles |
| `hero_computed_stats.json` | Game-computed stats for 511 heroes |
| `account_data.json` | Great Hall, Arena, Clan level |
| `pyautoraid.db` | SQLite with all data unified |
| `battle_logs_cb_*.json` | Per-turn battle telemetry |
| `data/dwj/parsed/tunes.json` | 103 DWJ tunes with slot configs |
| `data/dwj/parsed/calc_tunes.json` | 246 calculator variants (hash-keyed) |
| `data/dwj/parsed/calc_champions.json` | 859 champion configs (skills + effects) |
| `data/hh/parsed/champions.json` | 1013 HellHades champion metadata + sets |
| `data/hh/parsed/tierlist.json` | 1013 HH tier ratings (CB / overall / etc.) |
| `docs/dwj/calc_algorithm.md` | Reverse-engineered DWJ scheduler spec |

## Reference IDs

**Slots**: 1=Helmet, 2=Chest, 3=Gloves, 4=Boots, 5=Weapon, 6=Shield, 7=Ring, 8=Amulet, 9=Banner
**Stats**: 1=HP, 2=ATK, 3=DEF, 4=SPD, 5=RES, 6=ACC, 7=CR, 8=CD
**Effects**: Poison=80, HPBurn=470, DEFDown=151, Weaken=350, Unkillable=320, DecATK=131, Leech=460, PoisonSens=500
**Masteries**: Format `500XYZ` (X=tree, Y=tier, Z=col). Warmaster=500161, Lore of Steel=500343
**Full mappings**: `tools/gear_constants.py`, `tools/status_effect_map.py`

## BepInEx Mod

HTTP API on port 6790. Key endpoints: `/status`, `/all-heroes`, `/all-artifacts`, `/skill-data`, `/skill-texts`, `/navigate`, `/context-call`, `/battle-state`, `/battle-log`, `/equip`, `/presets`, `/buttons`, `/click`.

Build & deploy: see Quick Commands above (dotnet build → kill Raid.exe → copy DLL).

### Launching Raid (mod-attached)

Standard invocation (used by `Modules/base.py:open_raid`):
```bash
"$LOCALAPPDATA/PlariumPlay/PlariumPlay.exe" --args -gameid=101 -tray-start
```
PP launches Raid; doorstop's local `winhttp.dll` hooks; BepInEx loads `RaidAutomationPlugin.dll`; mod binds `localhost:6790`. Verify: `curl localhost:6790/status` → `{"logged_in":true,"scene":"Village",...}`.

**Mod URL**: listener prefix is `http://localhost:6790/` — `127.0.0.1:6790` returns HTTP.sys "Invalid Hostname".

**Normal redeploy** (mod-only changes): `taskkill /F /IM Raid.exe` → copy DLL → relaunch via PP command above. PP stays up; you keep the session.

### Recovery: mod fails to attach

Symptom: Raid runs but `localhost:6790` is dead, or BepInEx log mtime doesn't update on launch, or `Get-Process -Module` shows local `winhttp.dll` loaded but no `BepInEx\*` modules.

Cause: PlariumPlay session can wedge (often visible as 6+ stale `PlariumPlay.exe` processes). Wedged PP launches Raid in a state where doorstop hooks but BepInEx core never initializes.

Fix — full PP reset:
```bash
taskkill //F //IM Raid.exe
taskkill //F //IM PlariumPlay.exe         # kills all PP.exe instances
taskkill //F //IM PlariumPlay.NetHost.exe # broker
# Leave PlariumPlayClientService.exe alone (Windows service)
"$LOCALAPPDATA/PlariumPlay/PlariumPlay.exe" &
sleep 8
"$LOCALAPPDATA/PlariumPlay/PlariumPlay.exe" --args -gameid=101 -tray-start
```
Re-login may be required in the PP window. After Raid is in-game, expect ~218 DLLs from `raid/build` and ~157 BepInEx assemblies in the Raid process — that's the "healthy" mod-attached state.

**`NEVER kill PlariumPlay`** for normal mod redeploy (breaks session, costs a re-login). Only do the full PP reset when the mod fails to attach despite Raid launching.

## Key Rules

- **NEVER use screen automation** for game actions — mod API only
- Rings/Amulets cannot roll SPD substats
- Accessories are faction-locked
- `ArtifactKindId` 1 = Helmet (NOT Weapon)
- Fixed-point encoding: **32.32** (raw >> 32)
- Equip from vault unreliable — swap between heroes instead
