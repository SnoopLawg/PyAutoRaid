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

### Hybrid Controller (`Modules/hybrid_controller.py`) — Active

The primary automation controller. Combines three strategies:
1. **Coordinate clicks** — fixed positions for known UI elements (nav bar buttons, gem mine)
2. **Memory reading** — game state via pymem (resources, battle state, ViewKey, arena opponents)
3. **Image matching** — only for dynamic/unpredictable elements (popups, battle result screens)

Entry point: `python Modules/hybrid_controller.py` (or `--no-memory` for screen-only fallback)

**Key modules:**
- `memory_reader.py` — pymem wrapper that reads IL2CPP game objects from Raid.exe process memory
- `screen_state.py` — pyautogui/pygetwindow for window management, popup clearing, image-based navigation fallback
- `base.py` — shared helpers (`locate_and_click`, `asset()`, etc.)
- `win32_input.py` — input backend (pyautogui clicks)

### Memory Reader (`Modules/memory_reader.py`) — Phase 2

Direct IL2CPP memory reading via pymem. Replaces the dead RTK dependency with process memory access.

**How it works:**
- Attaches to `Raid.exe` process via `pymem.Pymem()`
- Finds `GameAssembly.dll` base address
- Resolves `AppModel` and `AppViewModel` singletons via IL2CPP TypeInfo pointer chains
- Reads game data by following field offsets from the Il2CppDumper output

**Singleton access chain:**
```
GA_BASE + TypeInfo_RVA -> klass
  -> +0xC8 (generic class info)
  -> +0x08 (specialized klass)
  -> +0xB8 (static_fields)
  -> +0x08 (_instance)
```

**What it reads:**
| Data | Method | Used For |
|------|--------|----------|
| Resources (energy, silver, gems, arena tokens, CB keys) | `get_resources()` | Skip tasks when empty |
| Account level & power | `get_account_level()`, `get_total_power()` | Logging |
| Hero roster (500 heroes, grade/level/empower) | `get_heroes()` | Future team building |
| Arena opponents (name, power, status) | `get_arena_opponents()` | Pick weakest target |
| Battle state (Started/Finished/Stopped) | `get_battle_state()` | Instant battle detection |
| Current screen (497 ViewKeys) | `get_current_view()` | Navigation verification |

**Offsets source:** Il2CppDumper v6.7.46 output for Raid v11.30.0 (metadata v31, Unity 6000.0.60).
Dump files at `C:\Tools\Il2CppDumper\output\` on the VM. Full ViewKey map at `C:\PyAutoRaid\offsets\viewkeys.json`.

**Key TypeInfo RVAs (in GameAssembly.dll):**
- AppModel: `0x4DC1558`
- AppViewModel: `0x4DC2A28`

**RTK status:** Dead. Raid Toolkit SDK v2.8.22 cannot parse IL2CPP metadata v31. `rtk_client.py` and `game_state.py` are legacy dead code.

### Screen State (`Modules/screen_state.py`)

Handles game window management and image-based fallback navigation:
- Window resize/center to 900x600
- Popup clearing (`exitAdd.png`, `closeLO.png`)
- `ensure_village()` — ESC + goBack + quit dialog handling + village verification
- `smart_click()` — locate image and click with retries

## VM Deployment (mothership2)

PyAutoRaid runs headless on a Windows 10 LTSC VM on the homelab server (Dell Optiplex i5-9600T, 16GB RAM).

### VM Details

| Property | Value |
|----------|-------|
| Host | mothership2 (`192.168.0.244`) |
| Hypervisor | QEMU/KVM (SeaBIOS, not UEFI) |
| VM specs | 4 vCPUs, 4GB RAM, 60GB AHCI/SATA disk, e1000 NIC |
| OS | Windows 10 Enterprise LTSC 2021 |
| VM user | `snoop` / `raid` |
| VM files | `/home/snoop/vms/win10-raid/` |
| Code | `C:\PyAutoRaid` (zip download from GitHub) |
| Python | 3.12.4 (system-wide, on PATH) |

### Port Forwarding (QEMU user-mode networking)

| Host Port | Service |
|-----------|---------|
| 3389 | RDP (Windows Remote Desktop) |
| 5900 | VNC (QEMU display) |
| 5985 | WinRM (PowerShell remoting) |
| 9090 | RTK WebSocket API |

### Scripts (`/home/snoop/vms/win10-raid/`)

- `start-vm.sh` — Boot the VM. Pass ISO path as arg for reinstall: `./start-vm.sh Win10.iso`
- `stop-vm.sh` — ACPI shutdown via QEMU monitor (Python, no socat needed)
- `type-cmd.py <text>` — Type a command into the VM via QEMU monitor sendkey
- `run-pyautoraid.sh` — Trigger automation (WinRM or manual VNC/RDP)

### Automation Schedule

**Linux cron (host):**
```
50 6 * * *  start-vm.sh   # Boot VM 10 min before first run
0 22 * * *  stop-vm.sh    # Shut down to free RAM for Minecraft
```

**Windows Scheduled Task "PyAutoRaid":**
- Runs `python C:\PyAutoRaid\Modules\hybrid_controller.py` at **7am, 1pm, 7pm**
- Plarium Play auto-starts with Windows and launches Raid via startup shortcut

### Daily Flow

1. **6:50am** — Linux cron starts the VM
2. **Boot** — Windows auto-logs in → Plarium Play launches Raid → RTK starts
3. **7am, 1pm, 7pm** — Scheduled Task runs `hybrid_controller.py`
4. **10pm** — Linux cron shuts down the VM

### Connecting to the VM

- **RDP (interactive):** `192.168.0.244:3389` — use "Windows App" on Mac (user `snoop`, pass `raid`)
- **VNC (view only):** `vncviewer 192.168.0.244:5900` (no password, no input — use for screenshots)
- **PowerShell via monitor:** `python3 type-cmd.py 'your-command-here'` from the server

### Windows Optimizations Applied

- Services disabled: SysMain, DiagTrack, WSearch, MapsBroker, Windows Update
- UAC disabled for admin user
- High performance power plan
- Notifications disabled

## Future Plans

### Phase 2: Direct IL2CPP Memory Reading (ACTIVE)
Using `pymem` to read `GameAssembly.dll` process memory directly. Currently implemented:
- Account data (level, power, resources)
- Hero roster (500 heroes with stats)
- Arena opponents (name, power, win/loss status)
- Battle state detection (instant, no image polling)
- ViewKey screen identification (497 game screens mapped)
- Instant/quick fight detection

**Remaining Phase 2 work:**
- Hero type_id -> champion name mapping (needs static data extraction)
- Arena opponent team composition reading
- Artifact data reading for auto-sell
- Offset update tooling for game patches (`update_offsets.py`)

### Phase 3: DLL Injection (Future)
Inject a C#/.NET DLL into the game process for deepest access:
- Hook game functions directly (battle events, screen transitions)
- Event-driven automation (react to game events in real-time)
- **Tradeoff**: Most complex, highest anti-cheat risk

## Key Constraints

- **Windows-only**: Uses pywin32, PyGetWindow, Windows Task Scheduler
- **Resolution-dependent**: Hardcoded pixel coordinates assume 1920x1080. Named constants for coordinates are defined at the top of each module.
- **Asset path handling**: Resolves `assets/` differently from source vs frozen PyInstaller exe (`sys._MEIPASS`)

