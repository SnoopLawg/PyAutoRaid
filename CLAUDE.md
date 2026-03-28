# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyAutoRaid automates daily tasks in Raid: Shadow Legends. It runs on a Windows 10 LTSC VM on a homelab server, combining three automation layers:

1. **MelonLoader mod API** — C# plugin injected into the game, exposes HTTP API on port 6790 for direct Unity Button.onClick invocation
2. **IL2CPP memory reading** — pymem reads game state directly from process memory (resources, heroes, events, battle state, ViewKey)
3. **Screen automation** — pyautogui image matching and coordinate clicks as fallback

The controller tries mod API first, falls back to memory-verified coordinate clicks, then to image matching.

## Build & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run daily automation (default)
python Modules/hybrid_controller.py

# Run without memory reading (screen-only fallback)
python Modules/hybrid_controller.py --no-memory

# Show active events and farming recommendations
python Modules/hybrid_controller.py --events

# Dungeon farming only (event-aware)
python Modules/hybrid_controller.py --farm
python Modules/hybrid_controller.py --farm --dungeon=dragon --runs=20 --energy-floor=1000

# Run tests
python -m pytest tests/ -v
```

## Architecture

### Hybrid Controller (`Modules/hybrid_controller.py`)

Primary automation controller. Runs daily tasks in order:
1. Gem Mine collection
2. Shop rewards (free offers)
3. Timed rewards (sidebar icons)
4. Clan check-in + treasure
5. Quest claims (regular + advanced)
6. Inbox collection (energy, brew, forge, potions)
7. Arena battles (10 fights, weakest opponent targeting via memory)
8. Clan Boss (Ultra-Nightmare, instant fight detection)
9. Dungeon farming (event-aware, auto-detects best dungeon)

**Navigation:** Uses `_click_nav(name, fallback_coords)` which tries mod API button click first, then coordinate fallback. Village nav buttons (shop, quests, clan, battle, inbox) all go through the mod.

**Battle detection:** Memory-based via `BattleProcessingState` enum. Two-phase wait: Started → Finished. Supports instant/quick fights via `wait_for_battle_or_view_change()`.

### Memory Reader (`Modules/memory_reader.py`)

Direct IL2CPP memory reading via pymem. Reads game state from `GameAssembly.dll` process memory.

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
| Resources (energy, silver, gems, tokens, keys) | `get_resources()` | Skip tasks when empty |
| Account level & power | `get_account_level()`, `get_total_power()` | Logging |
| Hero roster (500+ heroes with names, grade, faction, rarity) | `get_heroes()` | Future team building |
| Artifacts (rank, rarity, set, level, sell price) | `get_artifacts()` | Future auto-sell |
| Arena opponents (name, power, status) | `get_arena_opponents()` | Pick weakest target |
| Battle state (Started/Finished/Stopped) | `get_battle_state()` | Instant battle detection |
| Current screen (497 ViewKeys) | `get_current_view()` | Navigation verification |
| Active events & tournaments | `get_active_events()` | Event-aware farming |
| Farming recommendations | `should_farm_dungeons/arena/artifacts/summon/train()` | Double-dip decisions |

**Key TypeInfo RVAs (in GameAssembly.dll):**
- AppModel: `0x4DC1558`
- AppViewModel: `0x4DC2A28`

**Offsets source:** Il2CppDumper v6.7.46 output for Raid v11.30.0 (metadata v31, Unity 6000.0.60).
Dump files at `C:\Tools\Il2CppDumper\output\` on the VM. ViewKey map at `C:\PyAutoRaid\offsets\viewkeys.json`.

### MelonLoader Mod (`mod/RaidAutomationMod.cs`)

C# MelonPlugin (not MelonMod — bypasses game compatibility check) running inside the game process.

**HTTP API on port 6790:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/status` | GET | Scene name, root object count |
| `/buttons` | GET | All active interactable buttons with full paths |
| `/click?path=X` | POST | Click button by GameObject path (Button.onClick.Invoke) |
| `/find?name=X` | GET | Search GameObjects by name |
| `/scene?depth=N` | GET | Dump scene hierarchy |

Thread-safe via `ConcurrentQueue<Action>` processed on Unity's main thread in `MelonEvents.OnUpdate`.

**Build (Mac cross-compile):**
```bash
cd /tmp/raid-mod
/opt/homebrew/opt/dotnet@6/bin/dotnet build -c Release
# Deploy to VM: {gameDir}\Plugins\RaidAutomationMod.dll
# MUST stop Raid before deploying (file lock)
```

**Key button paths:**
- Shop: `UIManager/Canvas (Ui Root)/Dialogs/[DV] VillageHUD/Workspace/Bottom/LeftButtonLayout 1/ShopButton`
- Battle: `.../Bottom/RightButtonLayout 2/WorldMapButton`
- Clan: `.../Bottom/RightButtonLayout 2/AllianceButton`
- Quests: `.../Bottom/LeftButtonLayout 1/QuestButton`
- Inbox: `.../Top/TopButtonLayout/InboxButton`

### Mod Client (`Modules/mod_client.py`)

Python HTTP client for the MelonLoader mod API. `VILLAGE_BUTTONS` dict maps friendly names to full Unity GameObject paths. Graceful fallback if mod unavailable.

### Screen State (`Modules/screen_state.py`)

Game window management and image-based fallback:
- Window resize/center to 900x600
- Popup clearing (`exitAdd.png`, `closeLO.png`)
- `ensure_village()` — ESC + goBack + quit dialog handling + village verification
- `smart_click()` — locate image and click with retries

### Shared Base (`Modules/base.py`)

- `locate_and_click()` — single-scan locate + click
- `locate_and_click_loop()` — repeatedly click until image disappears (capped by `MAX_RETRIES`)
- `asset()` — cross-platform asset path builder

### Offset Update Tool (`tools/update_offsets.py`)

Re-runs Il2CppDumper after game patches, parses dump.cs for watched class offsets, diffs against previous, extracts TypeInfo RVAs from script.json.

### Legacy Modules (Dead Code)

- `rtk_client.py`, `game_state.py` — RTK WebSocket API. Dead: RTK v2.8.22 can't parse IL2CPP metadata v31.
- `PyAutoRaid.py`, `DailyQuests.py` — Original GUI-based automation with Command pattern and Tkinter. Superseded by `hybrid_controller.py`.
- `PullMysteryShards.py`, `CreateTask.py` — Old standalone scripts.

## Event-Aware Farming Strategy

Energy is stockpiled (128K+) and should ONLY be spent during active events/tournaments that reward the activity being done. Every dungeon run should count toward both gear drops AND event points ("double-dipping").

**How it works:**
1. `get_active_events()` reads solo events and tournaments from IL2CPP memory
2. `should_farm_*()` methods check event names for activity keywords
3. `_detect_best_dungeon()` picks the optimal dungeon matching active events
4. `run_dungeon_farming()` runs the loop with energy floor protection

**Event data chain:**
```
UserWrapper (+0x130) → SoloEventsWrapper
  → _globalEvents (+0x58) → GlobalEventsWrapperReadOnly
    → _data (+0x20) → UpdatableGlobalEventsData
      → _soloEvents (+0x20) → ICollection<GlobalEvent>
      → _tournaments (+0x28) → ICollection<GlobalEvent>
```

**Events to watch:** Dungeon Divers, Champion Training, Artifact Enhancement, Dragon/Spider/Ice Golem/Fire Knight Tournaments, Summon Rush, Champion Chase.

## VM Deployment (mothership2)

PyAutoRaid runs headless on a Windows 10 LTSC VM on the homelab server.

### VM Details

| Property | Value |
|----------|-------|
| Host | mothership2 (`192.168.0.244`) |
| Hypervisor | QEMU/KVM (SeaBIOS, not UEFI) |
| VM specs | 4 vCPUs, 4GB RAM, 60GB AHCI/SATA disk, e1000 NIC |
| OS | Windows 10 Enterprise LTSC 2021 |
| VM user | `snoop` / `raid` |
| VM files | `/home/snoop/vms/win10-raid/` |
| Code | `C:\PyAutoRaid` (deployed via certutil base64 decode over WinRM) |
| Python | 3.12.4 (system-wide, on PATH) |

### Port Forwarding (QEMU user-mode networking)

| Host Port | VM Port | Service |
|-----------|---------|---------|
| 3389 | 3389 | RDP (Windows Remote Desktop) |
| 5985 | 5985 | WinRM (PowerShell remoting) |
| 9090 | 9090 | (unused, was RTK) |

### Scripts (`/home/snoop/vms/win10-raid/`)

- `start-vm.sh` — Boot the VM. Pass ISO path as arg for reinstall.
- `stop-vm.sh` — ACPI shutdown via QEMU monitor
- `type-cmd.py <text>` — Type a command into the VM via QEMU monitor sendkey

### Automation Schedule

**Linux cron (host):**
```
50 6 * * *  start-vm.sh   # Boot VM 10 min before first run
0 22 * * *  stop-vm.sh    # Shut down to free RAM
```

**Windows Scheduled Task "PyAutoRaid":**
- Runs `python C:\PyAutoRaid\Modules\hybrid_controller.py` at **7am, 1pm, 7pm**
- LogonType Interactive (runs in session 1 where the game is visible)
- Plarium Play auto-starts with Windows and launches Raid

### Daily Flow

1. **6:50am** — Linux cron starts the VM
2. **Boot** — Windows auto-logs in → Plarium Play launches Raid → MelonLoader hooks in
3. **7am, 1pm, 7pm** — Scheduled Task runs `hybrid_controller.py`
4. **10pm** — Linux cron shuts down the VM

### Connecting to the VM

- **RDP:** `192.168.0.244:3389` (user `snoop`, pass `raid`)
- **WinRM from Mac:** SSH tunnel (`ssh -L 15985:localhost:5985 snoop@192.168.0.244`), then pywinrm with NTLM auth
- **QEMU monitor:** `python3 type-cmd.py 'command'` from the server

### Deploying Code to VM

```bash
# From Mac through SSH tunnel + WinRM:
# 1. Base64 encode the file
# 2. Write chunks via: <nul set /p="chunk" >> file_b64.txt
# 3. Decode: certutil -decode file_b64.txt file.py
# 4. MUST stop Raid before deploying mod DLL (file lock)
```

## Roadmap

### Done
- Phase 1: Screen automation (coordinate clicks, image matching, daily tasks)
- Phase 2: IL2CPP memory reading (resources, heroes, artifacts, arena, battle state, ViewKey)
- Phase 3: MelonLoader mod (HTTP API, direct Button.onClick)
- Event-aware dungeon farming (reads events from memory, auto-detects best dungeon)

### Next Up
1. **Auto-sell bad artifacts** — Score artifacts (rank * rarity * substat quality), auto-sell below threshold. Keep 5-6 star epic/legendary with speed subs on useful sets.
2. **Market shard buying** — Buy free mystery shard + ancient shards daily from in-game market.
3. **Advanced content** — Doom Tower boss farming, Tag Team Arena 3v3, Hydra weekly, Campaign 12-3.
4. **Gear optimization engine** — Score all artifacts, recommend gear per champion, speed tuning.

## Key Constraints

- **Windows-only**: Uses pywin32, PyGetWindow, Windows Task Scheduler
- **Resolution-dependent**: Game window resized to 900x600 by ScreenState
- **Offsets break on game updates**: TypeInfo RVAs and field offsets change. Use `tools/update_offsets.py` to re-dump.
- **WinRM session isolation**: WinRM runs in session 0, game in session 1. Use Scheduled Tasks with `LogonType Interactive` for anything that needs to see the game window.
