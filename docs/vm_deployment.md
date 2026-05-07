# VM Deployment (mothership2)

PyAutoRaid runs headless on a Windows 10 LTSC VM on the homelab server (Dell Optiplex i5-9600T, 16GB RAM).

## VM Details

| Property | Value |
|----------|-------|
| Host | mothership2 (`192.168.0.244`) |
| Hypervisor | QEMU/KVM (SeaBIOS, not UEFI) |
| VM specs | 4 vCPUs, 4GB RAM, 60GB AHCI/SATA disk, e1000 NIC |
| OS | Windows 10 Enterprise LTSC 2021 |
| VM user | `snoop` / `raid` |
| VM files | `/home/snoop/vms/win10-raid/` |
| Code | `C:\PyAutoRaid` (zip download from GitHub) |
| Game | `C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build\` |
| Python | 3.12.4 (system-wide, on PATH) |

## Port Forwarding (QEMU user-mode networking)

| Host Port | Service |
|-----------|---------|
| 3389 | RDP (Windows Remote Desktop) — guest-forwarded |
| 5900 | VNC (QEMU native `-vnc :0`, NOT guest-forwarded) |
| 5985 | WinRM (PowerShell remoting) — guest-forwarded |
| 6790 | RaidAutomation BepInEx mod HTTP API — guest-forwarded |
| 9090 | RTK WebSocket API (legacy, unused) — guest-forwarded |

**VM screen resolution:** 1024x768 (game window resized to 900x600 by ScreenState)

## Scripts (`/home/snoop/vms/win10-raid/`)

- `start-vm.sh` — Boot the VM. Pass ISO path as arg for reinstall: `./start-vm.sh Win10.iso`
- `stop-vm.sh` — ACPI shutdown via QEMU monitor (Python, no socat needed)
- `type-cmd.py <text>` — Type a command into the VM via QEMU monitor sendkey
- `run-pyautoraid.sh` — Trigger automation (WinRM or manual VNC/RDP)

## Automation Schedule

**Linux cron (host):**
```
50 6 * * *  start-vm.sh   # Boot VM 10 min before first run
0 22 * * *  stop-vm.sh    # Shut down to free RAM for Minecraft
```

**Windows Scheduled Task "PyAutoRaid":**
- Runs `python C:\PyAutoRaid\Modules\hybrid_controller.py` at **7am, 1pm, 7pm**
- Plarium Play auto-starts with Windows and launches Raid via startup shortcut

## Daily Flow

1. **6:50am** — Linux cron starts the VM
2. **Boot** — Windows auto-logs in → Plarium Play launches Raid → BepInEx injects mod
3. **7am, 1pm, 7pm** — Scheduled Task runs `hybrid_controller.py`
4. **10pm** — Linux cron shuts down the VM

## Connecting to the VM

- **RDP (interactive):** `192.168.0.244:3389` — use "Windows App" on Mac (user `snoop`, pass `raid`)
- **VNC (view only):** `vncviewer 192.168.0.244:5900` (no password, no input — use for screenshots)
- **PowerShell via monitor:** `python3 type-cmd.py 'your-command-here'` from the server

## Windows Optimizations Applied

- Services disabled: SysMain, DiagTrack, WSearch, MapsBroker, Windows Update
- UAC disabled for admin user
- High performance power plan
- Notifications disabled

## BepInEx Mod Build & Deploy (on VM)

```powershell
# Serve source from host: python3 -m http.server 8877 --directory ~/projects/pyautoraid
$build = 'C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build'
$modDir = 'C:\PyAutoRaid\mod\bepinex'
Invoke-WebRequest -Uri 'http://10.0.2.2:8877/mod/bepinex/RaidAutomationPlugin.cs' -OutFile "$modDir\RaidAutomationPlugin.cs"
C:\dotnet\dotnet.exe build $modDir\RaidAutomationPlugin.csproj -c Release
Copy-Item "$modDir\bin\Release\net6.0\RaidAutomationPlugin.dll" "$build\BepInEx\plugins\" -Force
Start-ScheduledTask -TaskName 'LaunchRaid'  # launches Raid.exe in user session
```

## Important Gotchas

- WinRM requires **Private** network profile: `Set-NetConnectionProfile -InterfaceAlias "Ethernet" -NetworkCategory Private`
- **NEVER `Stop-Process -Name PlariumPlay`** — credentials lost, Raid relaunches then exits within ~60s. Only stop `Raid.exe` for redeploys.
- After Raid restart, HTTP listener "started" log can appear before http.sys actually binds — wait 2-3 minutes.
- JSON responses > ~50KB truncated by WinRM `Invoke-WebRequest` — use `curl` on VM + base64 transfer instead.
