<a name="readme-top"></a>

[![Downloads][downloads-shield]][downloads-url]
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]

<br />
<div align="center">
  <a href="https://github.com/SnoopLawg/PyAutoRaid">
    <img src="https://user-images.githubusercontent.com/30202466/181846024-930b7120-0af6-4280-b727-87bdd4ade7b8.jpeg" alt="Logo">
  </a>

<h3 align="center">PyAutoRaid</h3>

  <p align="center">
    Full-stack automation for Raid: Shadow Legends — from daily task farming to UNM Clan Boss optimization with real-time battle telemetry.
    <br />
    <a href="#features">Features</a>
    &middot;
    <a href="#architecture">Architecture</a>
    &middot;
    <a href="https://github.com/SnoopLawg/PyAutoRaid/issues">Report Bug</a>
  </p>
</div>

## About

PyAutoRaid started as a simple PyAutoGUI screen clicker and evolved into a full game-data automation platform. It now uses a **BepInEx IL2CPP mod** injected into the Unity game process to read and control everything via an HTTP API — no screen scraping needed for most tasks.

Runs headless on a Windows 10 VM (QEMU/KVM), fully automated on a cron schedule.

### Built With

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![C#](https://img.shields.io/badge/c%23-%23239120.svg?style=for-the-badge&logo=csharp&logoColor=white)
![.NET](https://img.shields.io/badge/.NET-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Features

### Game Injection — BepInEx Mod
- HTTP API on port 6790 with 30+ endpoints
- Full hero roster (500+ heroes with stats, skills, masteries, artifacts)
- All artifacts (2,600+ including vault) with substats, glyphs, Divine enhancement
- Account data (Great Hall, Arena league, Clan level)
- Game's own stat calculator integration for exact values
- UI control: button clicks, navigation, dialog dismiss, MVVM context calls
- Artifact equip/unequip/swap/bulk-equip
- Mastery open/reset

### Battle Telemetry
- Per-turn snapshots of ALL heroes (HP, TM, skills, status flags)
- **Direct buff/debuff tracking** — every active effect with StatusEffectTypeId, turns remaining, and who placed it
- Complete StatusEffectTypeId enum (110 effects mapped from IL2CPP dump: Unkillable=320, Block Damage=60, Poison=80, HP Burn=470, etc.)
- Stat-mod effects with exact values (DEF Down, ATK Down, Weaken)
- Absorbed damage by effect kind

### Daily Automation (11 tasks)
- Gem Mine, Shop Rewards, Timed Rewards, Quests, Clan, Inbox
- Arena (10 battles with weakest-opponent targeting via memory reading)
- Clan Boss (difficulty selection, instant fight detection)
- Market Shards, Artifact Auto-Sell, Dungeon Farming (20 runs)
- Three-tier control: Mod API > Memory Reading > Screen Fallback

### Clan Boss Simulator
- DWJ-accurate turn-by-turn engine (tick-based TM, tie-breaking, buff timing)
- Force-Affinity damage caps calibrated against real battle data
- `--use-current-gear` — uses hero's actual equipped artifacts for exact stat matching
- `--validate-against <log>` — compares sim output vs real battle log
- Survival model: HP tracking, Gathering Fury, Lifesteal, Leech, Ally Protect
- Monte Carlo mode for RNG variance testing

### CB Team Optimizer
- Evaluates 3,600+ team combinations at full potential
- Constraint-based gear assignment with speed tune targets
- Myth Eater speed tune presets (Maneater 287-290, Demytha 171-174, etc.)
- 343 heroes auto-profiled from game skill data with exact StatusEffectTypeIds

### Battle Log Analyzer
- UK/BD coverage gap detection per boss turn
- Buff/debuff lifecycle with turn-by-turn transitions
- Skill rotation inference from cooldown tracking
- Damage attribution per hero per source type

### Memory Reader
- Direct IL2CPP process memory reading via pymem
- Resources, battle state, current screen (497 ViewKeys), arena opponents
- No game modification needed — read-only observation

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Architecture

```
                    +-------------------+
                    |   Cron Schedule   |
                    |  7am / 1pm / 7pm  |
                    +--------+----------+
                             |
                    +--------v----------+
                    | hybrid_controller |  (Python, Win10 VM)
                    |   11 daily tasks  |
                    +--+------+------+--+
                       |      |      |
              +--------+  +---+---+  +--------+
              |           |       |           |
     +--------v---+  +---v----+  +v--------+  +--------+
     | Mod API    |  | Memory |  | Screen  |  | WinRM  |
     | port 6790  |  | Reader |  | Fallback|  | Deploy |
     +--------+---+  +--------+  +---------+  +--------+
              |
     +--------v-------------------------------------------+
     |          BepInEx IL2CPP Plugin (C#)                |
     |  RaidAutomationPlugin.cs (~8K lines)               |
     |  - HTTP server, Harmony hooks, IL2CPP reflection   |
     |  - Battle telemetry, buff/debuff tracking          |
     |  - Artifact/mastery commands                       |
     +----------------------------------------------------+
              |
     +--------v---------+
     |  Raid.exe         |
     |  Unity 6000.0.60  |
     +-------------------+

     +-------------------+       +-------------------+
     |   CB Simulator    |       |  Gear Optimizer   |
     |   cb_sim.py       |<----->|  gear_optimizer.py|
     +-------------------+       +-------------------+
              |
     +--------v----------+
     | Battle Analyzer   |
     | battle_log_analyze |
     +-------------------+
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites
- Windows 10 VM (or bare metal) with Raid: Shadow Legends installed
- Python 3.12+
- BepInEx 6.0.0-be.755 (for Unity 6000.0.60f1 support)
- .NET 6.0 SDK (for building the mod)

### Installation

```bash
# Clone
git clone https://github.com/SnoopLawg/PyAutoRaid.git
cd PyAutoRaid

# Install Python deps
pip install -r requirements.txt

# Build the BepInEx mod (on the VM)
cd mod/bepinex
dotnet build RaidAutomationPlugin.csproj -c Release
# Copy DLL to BepInEx/plugins/
```

See `CLAUDE.md` for full setup instructions including BepInEx configuration, port forwarding, and VM deployment.

### Usage

```bash
# Daily automation (runs all 11 tasks)
python Modules/hybrid_controller.py

# Fetch fresh game data from mod API
python tools/refresh_data.py

# CB simulator with current gear
python tools/cb_sim.py --team "Maneater,Demytha,Ninja,Geomancer,Venomage" --use-current-gear

# Validate sim against real battle log
python tools/cb_sim.py --team "..." --use-current-gear --validate-against battle_log.json

# Rank all possible CB team combos
python tools/cb_potential.py

# Optimize gear for a team
python tools/gear_optimizer.py --team "..."

# Analyze a captured battle log
python tools/battle_log_analyze.py battle_log.json
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

- [x] Screen automation via PyAutoGUI
- [x] Direct IL2CPP memory reading via pymem
- [x] BepInEx mod with HTTP API (30+ endpoints)
- [x] Battle telemetry with direct buff/debuff tracking
- [x] Complete StatusEffectTypeId enum from IL2CPP dump
- [x] CB turn-by-turn simulator (DWJ-accurate)
- [x] CB team optimizer (3,600+ combos evaluated)
- [x] Gear optimizer with speed tune constraints
- [x] Sim validation against real battle logs
- [ ] Relic bonus calculation
- [ ] Leader skill auras in sim
- [ ] 4-piece set bonuses in gear optimizer
- [ ] Full auto dungeon team optimizer

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

No License. See `LICENSE.txt` for more information.

## Contact

Project Link: [https://github.com/SnoopLawg/PyAutoRaid](https://github.com/SnoopLawg/PyAutoRaid)

## Acknowledgments

* [DeadwoodJedi](https://www.deadwoodjedi.com/) for speed tune theory
* [BepInEx](https://github.com/BepInEx/BepInEx) for Unity IL2CPP mod injection
* [Raid](https://plarium.com/) for not being free-to-play friendly for a busy man

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[downloads-shield]: https://img.shields.io/github/downloads/SnoopLawg/PyAutoRaid/total.svg?style=for-the-badge
[downloads-url]: https://github.com/SnoopLawg/PyAutoRaid/releases
[contributors-shield]: https://img.shields.io/github/contributors/SnoopLawg/PyAutoRaid.svg?style=for-the-badge
[contributors-url]: https://github.com/SnoopLawg/PyAutoRaid/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/SnoopLawg/PyAutoRaid.svg?style=for-the-badge
[forks-url]: https://github.com/SnoopLawg/PyAutoRaid/network/members
[stars-shield]: https://img.shields.io/github/stars/SnoopLawg/PyAutoRaid.svg?style=for-the-badge
[stars-url]: https://github.com/SnoopLawg/PyAutoRaid/stargazers
[issues-shield]: https://img.shields.io/github/issues/SnoopLawg/PyAutoRaid.svg?style=for-the-badge
[issues-url]: https://github.com/SnoopLawg/PyAutoRaid/issues
