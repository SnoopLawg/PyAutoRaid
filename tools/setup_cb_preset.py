#!/usr/bin/env python3
"""
Set up the Myth Eater UNM CB preset with correct AI priorities and delays.
Run after the VM boots and Raid is logged in.

DWJ Myth Eater Ninja UNM config:
  Maneater 288: A3 delay=1 (opens A1, then A3)
  Demytha 172:  A3 delay=2 (opens A1, A2, then A3)
  Ninja 205:    A3 delay=1 (opens A1/A2, then A3)
  Geomancer 178: no delay
  Venomage 160:  no delay
"""
import winrm
import json
import time
import sys

s = winrm.Session('http://localhost:5985/wsman', auth=('snoop', 'raid'), transport='ntlm')

def vm_cmd(ps_cmd, timeout=15):
    r = s.run_ps(ps_cmd)
    return r.std_out.decode().strip()

def wait_for_game(max_wait=300):
    print("Waiting for game to be logged in...")
    for i in range(max_wait // 10):
        try:
            out = vm_cmd('curl.exe -s --max-time 5 http://localhost:6790/status')
            if out and '"logged_in":true' in out:
                print(f"  Game ready after {(i+1)*10}s")
                return True
        except:
            pass
        time.sleep(10)
        print(f"  {(i+1)*10}s...")
    print("TIMEOUT waiting for game")
    return False

def create_preset():
    heroes = '15120,18607,2643,13615,5692'
    url = f'http://localhost:6790/save-preset?name=Myth%20Eater%20UNM&heroes={heroes}&type=1'
    resp = vm_cmd(f'curl.exe -s "{url}"')
    print(f"Save preset response:\n{resp[:600]}")
    return resp

def check_presets():
    resp = vm_cmd('curl.exe -s http://localhost:6790/presets')
    persisted = '"presets":[]' not in resp
    print(f"\nPreset persisted: {persisted}")
    if persisted:
        print(resp[:400])
    return persisted

def verify_speeds():
    """Verify all CB heroes have correct speeds."""
    resp = vm_cmd('curl.exe -s "http://localhost:6790/all-heroes?min_grade=6&offset=0&limit=100"')
    data = json.loads(resp)

    targets = {15120: ('Maneater', 288), 18607: ('Demytha', 172),
               2643: ('Ninja', 205), 13615: ('Geomancer', 178), 5692: ('Venomage', 160)}

    print("\nSpeed verification:")
    for h in data.get('heroes', []):
        hid = h.get('id')
        if hid in targets:
            name, target = targets[hid]
            arts = h.get('artifacts', [])
            # Can't compute exact speed here, just verify artifact count
            print(f"  {name:12s}: {len(arts)}/9 artifacts equipped")

if __name__ == '__main__':
    if not wait_for_game():
        sys.exit(1)

    print("\n=== Creating Myth Eater UNM Preset ===")
    create_preset()

    time.sleep(3)
    persisted = check_presets()

    if not persisted:
        print("\nPreset did not persist. Trying again after 5s...")
        time.sleep(5)
        create_preset()
        time.sleep(3)
        persisted = check_presets()

    verify_speeds()

    if persisted:
        print("\n=== SUCCESS: Preset created and persisted! ===")
        print("Now set these in-game if not already handled by the preset:")
        print("  ME A3 delay=1, Demytha A3 delay=2, Ninja A3 delay=1")
    else:
        print("\n=== PRESET DID NOT PERSIST ===")
        print("Check BepInEx log for errors.")
        print("Debug info should be in the save response above.")
