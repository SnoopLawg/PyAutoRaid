#!/bin/bash
# Deploy mod to VM — one command: serve → build → kill Raid → copy DLL → relaunch
# Usage: ./tools/deploy_mod.sh [--no-relaunch]

set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
RELAUNCH=true
[[ "$1" == "--no-relaunch" ]] && RELAUNCH=false

echo "=== Mod Deploy ==="

# Start HTTP server if not running
if ! fuser 8877/tcp &>/dev/null; then
    echo "Starting HTTP server on :8877..."
    python3 -m http.server 8877 --directory "$DIR" &>/dev/null &
    HTTP_PID=$!
    sleep 2
    echo "  PID=$HTTP_PID"
else
    HTTP_PID=""
    echo "  HTTP server already running on :8877"
fi

echo "Downloading source to VM..."
python3 -c "
import winrm
s = winrm.Session('http://localhost:5985/wsman', auth=('snoop','raid'), transport='ntlm', read_timeout_sec=60)
s.run_ps(r\"\"\"Invoke-WebRequest -Uri 'http://10.0.2.2:8877/mod/bepinex/RaidAutomationPlugin.cs' -OutFile 'C:\PyAutoRaid\mod\bepinex\RaidAutomationPlugin.cs'\"\"\")
print('  Source downloaded')
"

echo "Killing Raid..."
python3 -c "
import winrm
s = winrm.Session('http://localhost:5985/wsman', auth=('snoop','raid'), transport='ntlm', read_timeout_sec=30)
s.run_cmd('taskkill', ['/IM', 'Raid.exe', '/F'])
print('  Raid killed')
" 2>/dev/null || echo "  (Raid not running)"

echo "Building mod..."
python3 -c "
import winrm
s = winrm.Session('http://localhost:5985/wsman', auth=('snoop','raid'), transport='ntlm', read_timeout_sec=120)
r = s.run_ps(r\"\"\"& 'C:\dotnet\dotnet.exe' build 'C:\PyAutoRaid\mod\bepinex\RaidAutomationPlugin.csproj' -c Release 2>&1 | Out-String\"\"\")
out = r.std_out.decode()
if 'Build succeeded' in out:
    print('  Build OK')
else:
    print(out[-500:])
    exit(1)
"

echo "Deploying DLL..."
python3 -c "
import winrm
s = winrm.Session('http://localhost:5985/wsman', auth=('snoop','raid'), transport='ntlm', read_timeout_sec=30)
s.run_ps(r\"\"\"Copy-Item 'C:\PyAutoRaid\mod\bepinex\bin\Release\net6.0\RaidAutomationPlugin.dll' 'C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build\BepInEx\plugins\RaidAutomationPlugin.dll' -Force\"\"\")
print('  DLL deployed')
"

if $RELAUNCH; then
    echo "Relaunching Raid..."
    python3 -c "
import winrm
s = winrm.Session('http://localhost:5985/wsman', auth=('snoop','raid'), transport='ntlm', read_timeout_sec=30)
s.run_cmd('schtasks', ['/run', '/tn', 'LaunchRaid'])
print('  Raid launching (wait ~2 min for mod)')
"
fi

# Cleanup HTTP server if we started it
[[ -n "$HTTP_PID" ]] && kill $HTTP_PID 2>/dev/null

echo "=== Deploy complete ==="
