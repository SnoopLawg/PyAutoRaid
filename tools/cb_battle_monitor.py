#!/usr/bin/env python3
"""
CB Battle Monitor — polls /battle-state during a live CB fight
and saves turn-by-turn snapshots to a JSON log file.

Usage: python3 tools/cb_battle_monitor.py
  - Run BEFORE starting the CB fight
  - It polls every 2 seconds waiting for battle to start
  - Once battle is detected, polls every 0.5 seconds
  - Saves all snapshots to cb_battle_log.json when fight ends
"""
import winrm
import json
import time
import sys
from pathlib import Path

s = winrm.Session('http://localhost:5985/wsman', auth=('snoop', 'raid'), transport='ntlm', read_timeout_sec=30)

def get_battle_state():
    try:
        r = s.run_ps('curl.exe -s --max-time 5 "http://localhost:6790/battle-state"')
        return json.loads(r.std_out.decode())
    except:
        return None

print("CB Battle Monitor — waiting for battle to start...")
print("Navigate to CB and start the UNM fight in-game.")
print()

# Phase 1: Wait for battle
snapshots = []
while True:
    state = get_battle_state()
    if state and 'heroes' in state and len(state.get('heroes', [])) > 0:
        print(f"BATTLE DETECTED! {len(state['heroes'])} heroes found")
        print(f"  Found via: {state.get('found_via', '?')}")
        break
    elif state and 'error' in state:
        sys.stdout.write(f"\r  Waiting... ({state.get('error', '')[:60]})")
        sys.stdout.flush()
    else:
        sys.stdout.write("\r  Waiting for battle...")
        sys.stdout.flush()
    time.sleep(2)

# Phase 2: Record battle
print("\nRecording battle snapshots (Ctrl+C to stop)...")
last_turn_counts = {}
snapshot_num = 0

try:
    while True:
        state = get_battle_state()
        if not state or 'heroes' not in state:
            print("Battle ended or lost connection.")
            break

        heroes = state.get('heroes', [])
        if not heroes:
            print("No heroes — battle may have ended.")
            break

        # Check if any hero took a new turn
        turn_changed = False
        for h in heroes:
            hid = h.get('id', 0)
            tc = h.get('turn_count', 0)
            if hid not in last_turn_counts or tc != last_turn_counts[hid]:
                turn_changed = True
                last_turn_counts[hid] = tc

        if turn_changed or snapshot_num == 0:
            snapshot_num += 1
            state['snapshot'] = snapshot_num
            state['timestamp'] = time.time()
            snapshots.append(state)

            # Print summary
            line = f"#{snapshot_num:3d} "
            for h in heroes:
                name = h.get('name', h.get('type_id', '?'))
                if isinstance(name, int):
                    name = str(name)
                tm = h.get('stamina', 0)
                hp = h.get('health', 0)
                tc = h.get('turn_count', 0)
                uk = h.get('is_unkillable', False)
                effects = h.get('effects', [])
                n_buffs = len([e for e in effects if not e.get('is_debuff', True)])
                n_debuffs = len([e for e in effects if e.get('is_debuff', False)])

                # Compact display
                uk_str = "UK" if uk else "  "
                line += f"| {name[:6]:6s} T{tc:2d} TM={tm:4.0f} {uk_str} B{n_buffs}D{n_debuffs} "

            print(line)

        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nStopped by user.")

# Save log
outfile = Path(__file__).parent.parent / "cb_battle_log.json"
with open(outfile, 'w') as f:
    json.dump(snapshots, f, indent=2)
print(f"\nSaved {len(snapshots)} snapshots to {outfile}")
