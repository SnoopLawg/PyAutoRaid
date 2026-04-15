# CLAUDE.md

## Project Overview

PyAutoRaid automates Raid: Shadow Legends via a BepInEx mod HTTP API (port 6790) running on a Windows 10 VM. Primary focus: CB optimization with a turn-by-turn damage simulator calibrated to -7% of real battle data.

**NEVER use UI/screen automation.** All game actions go through the mod API context-calls.

## Quick Commands

```bash
# CB battle (navigate → start → poll → log → calibrate)
python3 tools/cb_run.py --calibrate --cb-element void

# Daily CB automation (cron-ready, runs all keys)
python3 tools/cb_daily.py --wait --cb-element force

# Deploy mod to VM (one command)
./tools/deploy_mod.sh

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
```

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
| `tools/deploy_mod.sh` | One-command mod build + deploy to VM |
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

## Reference IDs

**Slots**: 1=Helmet, 2=Chest, 3=Gloves, 4=Boots, 5=Weapon, 6=Shield, 7=Ring, 8=Amulet, 9=Banner
**Stats**: 1=HP, 2=ATK, 3=DEF, 4=SPD, 5=RES, 6=ACC, 7=CR, 8=CD
**Effects**: Poison=80, HPBurn=470, DEFDown=151, Weaken=350, Unkillable=320, DecATK=131, Leech=460, PoisonSens=500
**Masteries**: Format `500XYZ` (X=tree, Y=tier, Z=col). Warmaster=500161, Lore of Steel=500343
**Full mappings**: `tools/gear_constants.py`, `tools/status_effect_map.py`

## BepInEx Mod

HTTP API on port 6790. Key endpoints: `/status`, `/all-heroes`, `/all-artifacts`, `/skill-data`, `/skill-texts`, `/navigate`, `/context-call`, `/battle-state`, `/battle-log`, `/equip`, `/presets`, `/buttons`, `/click`.

Build & deploy: `./tools/deploy_mod.sh` (or manually: serve source → `C:\dotnet\dotnet.exe build` → copy DLL → relaunch Raid).

**NEVER kill PlariumPlay** — breaks session. Only kill `Raid.exe` for redeploys.

## VM

| Property | Value |
|----------|-------|
| Host | mothership2, QEMU/KVM, 4 vCPUs, 4GB RAM |
| Ports | 3389 (RDP), 5900 (VNC), 5985 (WinRM `snoop`/`raid`), 6790 (mod) |
| Schedule | 6:50 AM boot, 7/13/19 CB runs, 10 PM shutdown |
| Scripts | `/home/snoop/vms/win10-raid/` (start-vm.sh, stop-vm.sh) |

## Key Rules

- **NEVER use screen automation** for game actions — mod API only
- Rings/Amulets cannot roll SPD substats
- Accessories are faction-locked
- `ArtifactKindId` 1 = Helmet (NOT Weapon)
- Fixed-point encoding: **32.32** (raw >> 32)
- Equip from vault unreliable — swap between heroes instead
