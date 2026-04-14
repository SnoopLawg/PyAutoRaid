# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyAutoRaid is a Windows-only automation tool for Raid: Shadow Legends. It combines three control strategies — a BepInEx mod HTTP API, direct IL2CPP memory reading, and screen automation — to fully automate daily in-game tasks. Runs headless on a Windows 10 VM (1024x768 resolution), triggered by scheduled tasks. Also distributed as a Windows installer (PyInstaller + Inno Setup) for standalone use.

## Build & Run

```bash
pip install -r requirements.txt
python Modules/PyAutoRaid.py          # Main app (legacy screen automation)
python Modules/DailyQuests.py         # Daily quests only (legacy)
python Modules/hybrid_controller.py   # Primary entry point (mod API + memory + fallback)
python -m pytest tests/ -v
```

## Architecture

### Hybrid Controller (`Modules/hybrid_controller.py`) — Primary Entry Point

Three-tier control strategy (fastest first):
1. **Mod API** — BepInEx HTTP on port 6790 for Unity UI clicks, navigation, artifact equip/sell, masteries
2. **Memory reading** — pymem for game state (resources, battle state, ViewKey, arena, artifacts)
3. **Coordinate/image matching** — fixed positions + pyautogui fallback

**11 automated tasks:** Gem Mine, Shop Rewards, Timed Rewards, Quests, Clan, Inbox, Arena (10 battles), Clan Boss, Market Shards, Artifact Sell, Dungeon Farming (20 runs).

**Key modules:**
- `memory_reader.py` — pymem IL2CPP reader (resources, heroes, artifacts, arena, battle state, ViewKey)
- `screen_state.py` — pyautogui window management, popup clearing, image-based nav fallback
- `mod_client.py` — HTTP client for BepInEx mod API
- `win32_input.py` — Win32 PostMessage/SendMessage (game doesn't need focus)
- `base.py` — shared helpers (`locate_and_click`, `asset()`, `BaseDaily` base class)

### Screen Automation (`Modules/PyAutoRaid.py`, `DailyQuests.py`)

Legacy modules. `BaseDaily` provides `locate_and_click()`, `locate_and_click_loop()`, `wait_for_image()`, `asset()`. Command pattern for tasks. All while-loops use `MAX_RETRIES` (default 30).

### Configuration

- **PARconfig.ini** — task toggles, CB difficulty/fight counts, coordinate overrides
- **DQconfig.ini** — quest method toggles. Both re-read every loop iteration.

### CI/CD

`.github/workflows/compile-and-release.yml`: PyInstaller compile, Inno Setup installer, auto-increment version tag, GitHub Releases.

## CB Simulation & Optimization Tools

### Tool Overview

| Tool | Purpose |
|------|---------|
| `tools/cb_sim.py` | Turn-by-turn CB damage simulator (DWJ-accurate TM engine) |
| `tools/cb_calibrate.py` | Per-turn sim vs real battle log comparison |
| `tools/global_gear_solver.py` | Constraint-based gear optimizer across 5 heroes simultaneously |
| `tools/cb_team_search.py` | Exhaustive team evaluation (4000+ combos, two-tier scoring) |
| `tools/cb_gap_analysis.py` | Hero gap analysis (roster upgrades + pull priority) |
| `tools/auto_profile.py` | Auto-generate CB profiles from skills_db for all 343 heroes |
| `tools/cb_potential.py` | Full-potential team ranker (3654+ combos) |
| `tools/gear_optimizer.py` | Per-hero constraint-based artifact assignment |
| `tools/db_init.py` | Build SQLite database (pyautoraid.db) from all JSON data |
| `tools/battle_log_analyze.py` | Battle log analysis (damage, buffs, coverage gaps, skill inference) |

### Data Pipeline

```bash
# Fetch all game data from mod API (VM must be running, game logged in)
python3 tools/refresh_data.py              # heroes, artifacts, skills (with descriptions), rebuilds skills_db.json
python3 tools/refresh_data.py --skills-only # skills only
python3 tools/db_init.py                    # rebuild SQLite DB from JSON files

# CB simulation & optimization
python3 tools/cb_sim.py --team "ME,Demytha,SC,Venomage,Sicia" -v
python3 tools/cb_sim.py --team "..." --cb-element force    # day's affinity (default: void)
python3 tools/cb_sim.py --monte-carlo 100                  # RNG variance test
python3 tools/cb_calibrate.py --log battle_logs_cb_synced.json --cb-element force
python3 tools/global_gear_solver.py --team "Maneater,Demytha,Ninja,Geomancer,Venomage"
python3 tools/cb_team_search.py --top 30 --tier2
python3 tools/cb_gap_analysis.py
python3 tools/auto_profile.py --hero Venus
```

`gear_optimizer.py` auto-invokes `refresh_data.py` if data files are older than 30 min. Skip with `PYAUTORAID_NO_REFRESH=1`.

### CB Sim Accuracy (~5.3% error after calibration)

Key fixes applied:
- **CB element**: defaults to Void; pass `--cb-element` for day's affinity
- **WM/GS**: no longer multiplied by DEF Down + Weaken (was 2.1x overinflating)
- **Debuff placement**: >=50% chance places immediately, <50% uses fractional accumulator
- **Leader aura**: `apply_leader_aura()` in cb_sim.py applies leader skill stat boosts
- **Kind 9002** (activate_dots): disabled until per-hero validation done
- **Kind 5002**: mechanic unclear per hero — disabled
- Skill descriptions now extracted by mod (`desc` field in skills_db.json) — available after mod deploy + refresh

### DWJ Speed Tune Mechanics

- **TM fill**: speed per tick, threshold 1000 (DWJ equivalent: speed*0.07, threshold 100)
- **Tie-breaking**: highest TM -> highest speed -> position
- **Buff timing**: `isAddedThisTurn` — buffs don't tick on application turn (critical for Unkillable)
- **Stun target**: highest TM with skill on cooldown
- **Gathering Fury**: round-based (+2% per round after round 4), NOT per-turn

### DWJ Myth-Eater Tune Speeds

```
Maneater   287-290   (tight)
Demytha    171-174
Ninja      204-207   (1:1 DPS variant)
DPS_1to1   177-180   (Geomancer slot)
DPS_slow   159-162   (Venomage slot)
```

### Current Best Team

ME + Demytha + SC + Venomage + Sicia = ~63M (full auto, VALID tune)

### Stat Calculation Notes

`calc_stats()` in `cb_optimizer.py` includes: base stats (L60 scaled), artifact primary+substats, Great Hall, Arena, empowerment (HP/ATK/DEF only), 2-piece set bonuses.

**Known gaps in calc_stats():**
- Empowerment SPD/ACC/RES/CR/CD not applied (in-game speed is truth for tuning)
- 4-piece set bonuses not recognized
- Relic bonus returns 0 (~900 HP missing)

**Calibration tips (learned empirically):**
- Lore of Steel mastery ID = `500343` (Support T4 col 3). Amplifies set bonuses by +15%.
- Raid rarity codes: 1=Common, 2=Uncommon, 3=Rare, 4=Epic, 5=Legendary. Legendary empowerment = +15 SPD, Epic = +10.
- `CalcEmpowerBonus` (from `/hero-computed-stats`) only returns HP/ATK/DEF — SPD/ACC/RES/CR/CD must be added from `EMPOWERMENT_BONUSES` table.
- `flat_bonus` only aggregates HP/ATK/DEF/SPD (includes Divine-rank enhancement). For ACC/RES/CR/CD, iterate primary + substats manually.

## BepInEx Mod (`mod/bepinex/RaidAutomationPlugin.cs`)

BepInEx IL2CPP plugin injected into the game process. Provides HTTP API on port 6790.

### Setup

- BepInEx 6.0.0-be.755 (supports Unity 6000.0.60f1; MelonLoader does NOT)
- Proxy DLL: rename doorstop's `winhttp.dll` to `version.dll`
- URL reservation: `netsh http add urlacl url=http://+:6790/ user=Everyone` (admin)
- Plugin: `BepInEx/plugins/RaidAutomationPlugin.dll`
- Game path: `C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build\`

### Build & Deploy (on VM)

```powershell
$build = 'C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build'
$modDir = 'C:\PyAutoRaid\mod\bepinex'
# Serve from host: python3 -m http.server 8877 --directory ~/projects/pyautoraid
Invoke-WebRequest -Uri 'http://10.0.2.2:8877/mod/bepinex/RaidAutomationPlugin.cs' -OutFile "$modDir\RaidAutomationPlugin.cs"
C:\dotnet\dotnet.exe build $modDir\RaidAutomationPlugin.csproj -c Release
Copy-Item "$modDir\bin\Release\net6.0\RaidAutomationPlugin.dll" "$build\BepInEx\plugins\" -Force
Start-ScheduledTask -TaskName 'LaunchRaid'
```

**NEVER `Stop-Process -Name PlariumPlay`** — breaks PP session, needs manual RDP re-login. Only stop `Raid.exe` for redeploys.

### API Endpoints (port 6790)

| Endpoint | Description |
|----------|-------------|
| `/status` | Mod status (scene, logged_in, unity version) |
| `/all-heroes?min_grade=6&offset=0&limit=5` | Heroes with stats, skills, masteries, artifacts |
| `/all-artifacts?offset=0&limit=200` | All artifacts (equipped + vault) |
| `/account` | Great Hall, Arena league, Clan level, Account level |
| `/skill-data?hero_id=X&min_grade=6` | Skills with effects, cooldowns, StatusEffectTypeIds, descriptions |
| `/hero-computed-stats?min_grade=6` | Game-computed stats (base + blessing + arena + GH + empower) |
| `/buttons` | Active UI buttons (Unity hierarchy paths) |
| `/click?path=X` | Click button |
| `/dismiss` | One-shot dismiss `[OV]` prefixed overlays |
| `/navigate?target=X` | Navigate to screen (arena, cb, campaign, dungeon, etc.) |
| `/equip?hero_id=X&artifact_id=Y` | Equip artifact (auto-swap if slot occupied) |
| `/unequip?hero_id=X&artifact_id=Y` | Unequip artifact |
| `/swap?hero_id=X&from_id=A&to_id=B` | Swap artifacts between heroes |
| `/bulk-equip?hero_id=X&artifacts=[ids]` | Bulk equip multiple artifacts |
| `/presets` | Get/save/update/remove team presets |
| `/mastery-data?hero_id=X` | Mastery info |
| `/open-mastery?hero_id=X&mastery_id=Y` | Open a mastery |
| `/reset-masteries?hero_id=X` | Reset all masteries |
| `/battle-state` | Current battle state (Started/Finished/Stopped) |
| `/battle-log?clear=1` | Full battle log (up to 2000 entries with heroes, turns, effects) |
| `/context-call?path=X&method=Y&arg=Z` | Call MVVM context method (bypasses button clicks) |
| `/server-info` | Server region, account details |
| `/types?q=X`, `/props?type=X` | Debug: search loaded types, inspect properties |

**Endpoints NOT implemented** (mod_client.py calls them but they don't exist): `/find`, `/toggles`, `/toggle`, `/sell`, `/artifacts`, `/overlays`, `/shopitems`, `/view-context`.

### Game Data Access (reflection-based)

`AppModel` singleton -> `UserWrapper` -> `Heroes` (HeroesWrapper), `Artifacts` (EquipmentWrapper), `Arena`, `Alliance`. Hero data via `HeroById` dict. Artifacts via `EquipmentWrapper.One(artId)` scanning 1..LastArtifactId. `Fixed` type = game's fixed-point numbers; `ToString()` returns double.

### Battle Logging

Turn-by-turn telemetry via Harmony hooks on `ProcessStartTurn`/`ProcessEndTurn`/`ProcessStartBattle`/`ProcessEndBattle`. Per-turn hero snapshots include: HP, TM, status flags (27 bool getters), skill cooldowns (`rdy` field), stat-mod effects (`mods`), absorbed damage (`abs`).

**Key semantics:**
- `_battleCommandCount` fires on every ProcessStartTurn (player + boss + passive ticks)
- In-game "Turn X" = sum of player heroes' TurnCount
- Skills used inferred from `rdy:true->false` transitions
- `ProcessStartRound`/`ApplySkillCommand` hooks don't fire in IL2CPP builds (BepInEx limitation)
- Unkillable/Block Damage buffs only observable when triggered (`uk_saved`/`block_damage` flags) or via `AbsorbedDamageByEffectKindId`

### Important Gotchas

- After Raid restart, HTTP listener needs 2-3 min before responding (even after log shows "started")
- JSON > ~50KB truncated by WinRM `Invoke-WebRequest` — use `curl` on VM + base64 file transfer
- `hero.Type` throws for some heroes — wrap in try/catch, fall back to `_type` then `StaticData` lookup
- Base stats from `HeroType.Forms[0].BaseStats` are level-1 unscaled (multiply ~15x HP, ~7.5x ATK/DEF for 6-star L60)
- Fixed-point encoding is **32.32** (raw >> 32), NOT 16.16

## Artifact Data — Critical Reference

All mappings live in `tools/gear_constants.py` — single source of truth.

### Slot IDs (ArtifactKindId)
```
1=Helmet, 2=Chest, 3=Gloves, 4=Boots, 5=Weapon, 6=Shield, 7=Ring, 8=Amulet, 9=Banner
```
**WARNING**: 1=Helmet NOT Weapon. This was wrong for months.

### Stat IDs (StatKindId + IsAbsolute)
```
1 flat=HP     1 %=HP%      5=RES
2 flat=ATK    2 %=ATK%     6=ACC
3 flat=DEF    3 %=DEF%     7=CR%
4=SPD (always flat)         8=CD%
```

### Key Rules
- **Rings/Amulets cannot roll SPD substats** (game rule)
- **Accessories are faction-locked** (Ring/Amulet/Banner only equip on matching-faction heroes)
- **Glyph values** stored in `ArtifactBonus.PowerUpValue` (separate from base `Value`; add both)
- **CR/CD detection**: use `ToStatKey()` as authoritative (IL2CPP enum getter can mismap on gloves)

## Equip System

- **SwapArtifactCmd** (hero-to-hero): reliable, persists
- **DeactivateArtifactCmd** (unequip): reliable
- **ActivateArtifactCmd from vault**: unreliable (server silently rejects)
- **Locked heroes** (ArenaDefence, 3v3, Hydra, Siege, multi-battle): equip returns ok but server rejects
- Always refresh data before optimizer; filter accessories by faction; restart Raid after failed equip session

## Mastery Tree IDs

Format `500XYZ`: X=tree (1=Offense, 2=Defense, 3=Support), Y=tier, Z=column.
Example: `500161` = Warmaster (Offense T6 col 1). Lore of Steel = `500343`.

**Note**: EffectKindIds 5001/5002/5003 are unrelated to mastery IDs (5001=TM manipulation, 5002=HP Burn, 5003=debuff placement).

## StatusEffectTypeId Reference

Exact IDs from `skills_db.json` via `EffectType.ApplyStatusEffectParams.StatusEffectInfos[i].TypeId`:
- Poison5%=80, PoisonSensitivity=500, HPBurn=470, DEFDown=151, Weaken=350
- Unkillable=320, Leech=460, BlockDebuffs=310, DecATK=130, Counterattack=200
- Full mapping in `tools/status_effect_map.py`

## VM Deployment

### VM Details

| Property | Value |
|----------|-------|
| Host | mothership2 (192.168.0.244), QEMU/KVM |
| Specs | 4 vCPUs, 4GB RAM, 60GB disk, Win10 LTSC 2021 |
| Ports | 3389 (RDP), 5900 (VNC/QEMU), 5985 (WinRM), 6790 (mod API) |
| Code | `C:\PyAutoRaid`, Game at `C:\Users\snoop\...\raid-shadow-legends\build\` |
| Python | 3.12.4, user `snoop`/`raid` |
| Scripts | `/home/snoop/vms/win10-raid/` (start-vm.sh, stop-vm.sh, type-cmd.py, run-pyautoraid.sh) |

### Schedule

- **6:50 AM** — Linux cron boots VM
- **7 AM, 1 PM, 7 PM** — Windows Scheduled Task runs `hybrid_controller.py`
- **10 PM** — Linux cron shuts down VM

### Connecting

- **RDP**: `192.168.0.244:3389` (user `snoop`, pass `raid`)
- **VNC**: `vncviewer 192.168.0.244:5900` (no password, view only)
- **PowerShell**: `python3 type-cmd.py 'command'` from host

## Key Constraints

- **Windows-only**: pywin32, PyGetWindow, Windows Task Scheduler
- **Resolution-dependent**: 1024x768 VM desktop, game 900x600. Coordinates in `hybrid_controller.py` are game-relative.
- **MainWindowHandle=0**: Raid.exe under Unity 6000 has no standard HWND. Mod API bypasses this.

## Remaining Work

- `mod_client.py` calls endpoints that don't exist (`/find`, `/toggles`, `/sell`, etc.) — remove or implement
- Relic bonus (`CalcRelicsBonus` returns 0)
- Affinity weak/strong hit modifier not modeled
- Evil Eye mastery: once per target per battle, NOT every A1
