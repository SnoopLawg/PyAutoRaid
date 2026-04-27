#!/bin/bash
# Recover from wedged PlariumPlay state (mod fails to attach despite Raid launching).
# See CLAUDE.md "Recovery: mod fails to attach" + memory project_pp_wedged_state.
# Usage: ./tools/reset_pp.sh
#
# This will require you to re-login in the PP window — only run when the mod
# is actually broken. For normal mod redeploys, just kill Raid.exe and relaunch.

set -e

PP="$LOCALAPPDATA/PlariumPlay/PlariumPlay.exe"
[[ -f "$PP" ]] || { echo "PP not found at $PP"; exit 1; }

echo "[reset_pp] checking mod first..."
if curl -s -m 2 http://localhost:6790/status | grep -q '"mod"'; then
    echo "[reset_pp] mod already responding — nothing to do"
    curl -s -m 2 http://localhost:6790/status; echo
    exit 0
fi

echo "[reset_pp] killing Raid + all PlariumPlay user processes..."
taskkill //F //IM Raid.exe                 2>/dev/null || true
taskkill //F //IM PlariumPlay.exe          2>/dev/null || true
taskkill //F //IM PlariumPlay.NetHost.exe  2>/dev/null || true
sleep 3

echo "[reset_pp] launching PlariumPlay..."
"$PP" >/dev/null 2>&1 &
disown
sleep 8

echo "[reset_pp] launching Raid via PP (-gameid=101 -tray-start)..."
echo "  if PP shows a login dialog, log in now — script will wait up to 5 min"
"$PP" --args -gameid=101 -tray-start >/dev/null 2>&1 &
disown

echo "[reset_pp] waiting for mod on localhost:6790..."
for i in $(seq 1 60); do
    RESP=$(curl -s -m 2 http://localhost:6790/status 2>/dev/null || true)
    if echo "$RESP" | grep -q '"mod"'; then
        echo "[reset_pp] mod up after $((i*5))s:"
        echo "  $RESP"
        exit 0
    fi
    sleep 5
done

echo "[reset_pp] timeout: mod did not come up in 5 min"
echo "  current Raid procs:"
tasklist //FI "IMAGENAME eq Raid.exe" 2>/dev/null | tail -n +4
exit 1
