# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyAutoRaid is a Windows-only screen automation tool for Raid: Shadow Legends. It uses PyAutoGUI image recognition and pixel clicking to automate daily in-game tasks (gem mine, market purchases, arena battles, clan boss fights, quest claims, etc.). Distributed as a Windows installer built via PyInstaller + Inno Setup.

## Build & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run from source
python Modules/PyAutoRaid.py     # Main app
python Modules/DailyQuests.py    # Daily quests only

# Run tests
python -m pytest tests/ -v

# Compile to exe (requires pyinstaller)
python -m PyInstaller --onefile -w \
  --icon=assets/Icons/image1.ico \
  --hidden-import=pyautogui --hidden-import=pyscreeze \
  --hidden-import=Pillow --hidden-import=pywin32 \
  --hidden-import=psutil --hidden-import=PyGetWindow \
  --hidden-import=requests --hidden-import=screeninfo \
  --hidden-import=ttkthemes --hidden-import=cv2 \
  --add-data "assets;assets" \
  Modules/PyAutoRaid.py
```

## Architecture

### Shared Base Module (`Modules/base.py`)

All screen automation modules inherit from `BaseDaily` which provides:
- **`locate_and_click()`** — single-scan locate + click (avoids the old double-lookup race condition)
- **`locate_and_click_loop()`** — repeatedly click an image until it disappears, with `max_retries` to prevent infinite loops
- **`wait_for_image()`** — poll for an image with timeout
- **`asset()`** — cross-platform asset path builder
- OS detection, Raid path finding, asset path resolution, game window management
- Common navigation: `back_to_bastion()`, `delete_popup()`, `kill_processes()`

All while-loops use `MAX_RETRIES` (default 30) to prevent runaway execution.

### Command Pattern (`Modules/PyAutoRaid.py`)

Each in-game task is a Command class with an `execute()` method. `RewardsCommand` is a composite that runs all reward sub-commands. The `Daily` class extends `BaseDaily`, manages config, and registers commands.

### DailyQuests Module (`Modules/DailyQuests.py`)

Extends `BaseDaily`. Uses `getattr()` to dynamically call methods based on `DQconfig.ini` settings. Simpler than PyAutoRaid — methods are called directly instead of through Command objects.

### Threading Model

- **Main thread**: Tkinter event loop
- **daily_thread**: Runs `Daily.run()` automation loop
- **timer_thread**: 30-minute daemon timeout to prevent runaway execution

### Configuration

- **PARconfig.ini** — PyAutoRaid: task toggles, clan boss difficulty/fight counts, coordinate overrides
- **DQconfig.ini** — DailyQuests: quest method toggles, automated mode
- Both are re-read every loop iteration; changes take effect without restart

### CI/CD

`.github/workflows/compile-and-release.yml`: PyInstaller compile, embed admin manifests via Resource Hacker, Inno Setup installer, auto-increment version tag, upload to GitHub Releases.

### Hybrid Controller (`Modules/hybrid_controller.py`) — NEW

Next-gen approach using Raid Toolkit SDK for game state + pyautogui for clicks.

**Architecture:**
- `rtk_client.py` — WebSocket client to RTK at `ws://localhost:9090`. Synchronous wrapper (uses threading Events instead of asyncio). Provides typed access to all RTK APIs: AccountApi, RealtimeApi, StaticDataApi.
- `game_state.py` — State machine layer. `View` enum maps 200+ RTK ViewKey strings. `GameState` class provides `current_view()`, `wait_for_view()`, `wait_for_battle_end()`, `ensure_village()`, `smart_click()` (click + verify via RTK).
- `hybrid_controller.py` — Closed-loop controller. Each task reads state from RTK, clicks via pyautogui, then verifies the state change via RTK. Entry point: `python Modules/hybrid_controller.py`

**Requires Raid Toolkit SDK** installed and running on Windows alongside the game. Install from https://raidtoolkit.com

**Key advantage over pure screen automation:** Screen identity is read from RTK (200+ named views) instead of fragile image matching. Battle completion is detected via RTK events instead of pixel polling.

## Key Constraints

- **Windows-only**: Uses pywin32, PyGetWindow, Windows Task Scheduler
- **Resolution-dependent**: Hardcoded pixel coordinates assume 1920x1080. Named constants for coordinates are defined at the top of each module.
- **Asset path handling**: Resolves `assets/` differently from source vs frozen PyInstaller exe (`sys._MEIPASS`)
