"""
Fetch all hero + artifact data from the BepInEx mod API.
Handles large responses by paginating and using base64 file transfer.
"""
import json
import base64
import time
import sys
import winrm

VM_HOST = "192.168.0.244"
API_PORT = 6790
PAGE_SIZE = 5  # Small pages to avoid truncation

def get_session():
    return winrm.Session(
        f'http://{VM_HOST}:5985/wsman',
        auth=('snoop', 'raid'),
        transport='ntlm',
        read_timeout_sec=120,
        operation_timeout_sec=90,
    )

def api_call(s, endpoint):
    """Call mod API via curl on VM, transfer result via base64."""
    # Use curl to save to file, then base64 transfer
    url = f"http://localhost:{API_PORT}{endpoint}"
    s.run_cmd('cmd', ['/c', f'curl -s -o C:\\PyAutoRaid\\api_resp.json "{url}" 2>nul'])
    r = s.run_ps(r'''
$bytes = [System.IO.File]::ReadAllBytes("C:\PyAutoRaid\api_resp.json")
[Convert]::ToBase64String($bytes)
''')
    b64 = r.std_out.decode().strip()
    if not b64:
        return None
    raw = base64.b64decode(b64)
    return json.loads(raw.decode('utf-8'))


def fetch_all_heroes(s, min_grade=0):
    """Fetch all heroes with pagination to handle large responses."""
    all_heroes = []
    offset = 0
    total = None

    while True:
        url = f"/all-heroes?offset={offset}&limit={PAGE_SIZE}"
        if min_grade > 0:
            url += f"&min_grade={min_grade}"

        data = api_call(s, url)
        if data is None:
            print("ERROR: No response from API")
            break

        if 'error' in data:
            print(f"API error: {data['error']}")
            break

        if total is None:
            total = data.get('count', 0)

        heroes = data.get('heroes', [])
        if not heroes:
            break

        all_heroes.extend(heroes)
        if len(all_heroes) % 20 == 0 or len(all_heroes) >= total:
            print(f"  Fetched {len(all_heroes)}/{total} heroes...")

        offset += PAGE_SIZE
        if min_grade > 0:
            # With filtering, offset is based on filtered results
            offset = len(all_heroes)
            if len(heroes) < PAGE_SIZE:
                break
        else:
            if offset >= total:
                break

    return {"count": total, "heroes": all_heroes}


def fetch_account(s):
    """Fetch account-wide data (Great Hall, Arena, etc)."""
    return api_call(s, "/account")


def main():
    print("Connecting to VM...")
    s = get_session()

    # Check status
    status = api_call(s, "/status")
    if status is None:
        print("ERROR: Mod API not responding")
        sys.exit(1)
    print(f"Status: scene={status.get('scene')}, logged_in={status.get('logged_in')}")

    if not status.get('logged_in'):
        print("ERROR: Game not logged in")
        sys.exit(1)

    # Fetch account data
    print("\nFetching account data...")
    account = fetch_account(s)
    with open('account_data.json', 'w') as f:
        json.dump(account, f, indent=2)
    print(f"  Arena: league={account.get('arena', {}).get('league')}")
    print(f"  Account level: {account.get('account_level')}")

    # Fetch 6-star heroes (for CB optimizer)
    print("\nFetching 6-star heroes...")
    heroes_6 = fetch_all_heroes(s, min_grade=6)
    with open('heroes_6star.json', 'w') as f:
        json.dump(heroes_6, f, indent=2)

    good = [h for h in heroes_6['heroes'] if 'error' not in h]
    errors = [h for h in heroes_6['heroes'] if 'error' in h]
    with_arts = sum(1 for h in good if h.get('artifacts'))

    print(f"\n=== Results ===")
    print(f"Total 6-star heroes: {len(heroes_6['heroes'])}")
    print(f"  Good: {len(good)}, Errors: {len(errors)}")
    print(f"  With artifacts: {with_arts}")

    # Print summary
    STAT_NAMES = {1: "HP", 2: "ATK", 3: "DEF", 4: "SPD", 5: "RES", 6: "ACC", 7: "CR%", 8: "CD%"}
    ELEMENT = {0: "Mag", 1: "Frc", 2: "Spt", 3: "Voi", 4: "???"}
    RARITY = {3: "R", 4: "E", 5: "L", 6: "M"}
    SET_NAMES = {
        0: "None", 1: "HP", 2: "ATK", 3: "DEF", 4: "Speed", 5: "CritRate",
        6: "CritDmg", 7: "ACC", 8: "RES", 9: "Lifesteal", 10: "Savage",
        11: "Fury", 13: "Daze", 14: "Cursed", 16: "Toxic", 17: "Shield",
        18: "Frost", 22: "Stalwart", 24: "Counterattack", 26: "Destroy",
        29: "Perception", 30: "Regeneration", 34: "Relentless",
        35: "Unkillable", 36: "Immortal", 38: "Reflex",
    }

    print(f"\n{'Name':22s} {'R':1s} {'E':3s} {'emp':3s} {'arts':4s} {'Sets':30s}")
    print("-" * 70)
    for h in sorted(good, key=lambda x: (-x.get('rarity', 0), -x.get('empower', 0))):
        arts = h.get('artifacts', [])
        sets = {}
        for a in arts:
            sn = SET_NAMES.get(a.get('set', 0), f"?{a.get('set')}")
            sets[sn] = sets.get(sn, 0) + 1
        set_str = ", ".join(f"{v}x{k}" for k, v in sorted(sets.items(), key=lambda x: -x[1]) if k != "None")
        print(f"{h.get('name', '?'):22s} {RARITY.get(h.get('rarity'), '?'):1s} "
              f"{ELEMENT.get(h.get('element'), '?'):3s} {h.get('empower', 0):3d} "
              f"{len(arts):4d} {set_str}")

    # Also fetch all heroes for completeness
    print("\nFetching ALL heroes...")
    heroes_all = fetch_all_heroes(s)
    with open('heroes_all.json', 'w') as f:
        json.dump(heroes_all, f)
    print(f"Saved {len(heroes_all['heroes'])} heroes to heroes_all.json")

    # Fetch skill data for ALL heroes (not just 6-star)
    print("\nFetching skill data for ALL heroes (min_grade=0)...")
    skills_all = api_call(s, "/skill-data?min_grade=0")
    if skills_all and 'skills' in skills_all:
        with open('skills_data_all.json', 'w') as f:
            json.dump(skills_all, f, indent=2)
        # Cross-reference with hero names
        id_to_name = {h['id']: h['name'] for h in heroes_all['heroes']}
        heroes_with_skills = set()
        for sk in skills_all['skills']:
            hid = sk.get('hero_id')
            if hid in id_to_name:
                heroes_with_skills.add(id_to_name[hid])
        print(f"Saved skill data: {len(skills_all['skills'])} skills for {len(heroes_with_skills)} heroes")
    else:
        print("  WARNING: No skill data returned (mod may need redeploying)")


if __name__ == "__main__":
    main()
