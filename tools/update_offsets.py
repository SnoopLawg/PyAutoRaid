"""
Offset Update Tool for PyAutoRaid memory reader.

Run this after a Raid game update to re-dump IL2CPP metadata and
detect if any offsets changed. Generates a diff report.

Usage (on the VM):
    python update_offsets.py              # full dump + diff
    python update_offsets.py --dump-only  # just re-dump, no diff
    python update_offsets.py --check      # verify current offsets work

Requires Il2CppDumper at C:\\Tools\\Il2CppDumper\\
"""

import json
import os
import sys
import subprocess
import shutil
import re
from datetime import datetime


GAME_PATH = r"C:\Users\snoop\AppData\Local\PlariumPlay\StandAloneApps\raid-shadow-legends\build"
DUMPER_PATH = r"C:\Tools\Il2CppDumper"
OFFSETS_DIR = r"C:\PyAutoRaid\offsets"
DUMP_OUTPUT = os.path.join(DUMPER_PATH, "output")

# Key classes and fields we care about (class name -> list of field names)
WATCHED_CLASSES = {
    "AppModel": ["_userWrapper", "BattleStateNotifier"],
    "UserWrapper": ["Account", "Heroes", "Artifacts", "Arena", "Battle"],
    "AccountWrapperReadOnly": ["AccountData"],
    "UserAccount": ["TotalPower", "Level", "Resources"],
    "Resources": ["RawValues"],
    "UserHeroData": ["HeroById"],
    "Hero": ["_type", "Id", "TypeId", "Grade", "Level", "Experience", "EmpowerLevel", "Locked", "InStorage"],
    "HeroType": ["Name", "Fraction", "Rarity"],
    "UserArenaData": ["ArenaPoints", "Opponents"],
    "ArenaOpponent": ["Status", "ArenaPoints", "TeamSetup", "Name"],
    "TeamSetup": ["CombatPower"],
    "BattleStateNotifier": ["State"],
    "Artifact": ["_id", "_level", "_kindId", "_rankId", "_rarityId", "_setKindId", "_sellPrice", "_primaryBonus", "_secondaryBonuses"],
    "RoutingManager": ["_activeBranch"],
    "OpenedNodeMeta": ["Key"],
}


def get_game_version():
    """Read Raid.exe version."""
    exe = os.path.join(GAME_PATH, "Raid.exe")
    if not os.path.exists(exe):
        return "unknown"
    try:
        import ctypes
        size = ctypes.windll.version.GetFileVersionInfoSizeW(exe, None)
        if size:
            data = ctypes.create_string_buffer(size)
            ctypes.windll.version.GetFileVersionInfoW(exe, 0, size, data)
            # Simplified — just read from file properties
            return "check_manually"
    except Exception:
        pass
    return "unknown"


def run_dump():
    """Run Il2CppDumper on the game files."""
    ga = os.path.join(GAME_PATH, "GameAssembly.dll")
    meta = os.path.join(GAME_PATH, "Raid_Data", "il2cpp_data", "Metadata", "global-metadata.dat")

    if not os.path.exists(ga):
        print(f"ERROR: GameAssembly.dll not found at {ga}")
        return False

    # Backup previous dump
    if os.path.exists(DUMP_OUTPUT):
        backup = DUMP_OUTPUT + f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copytree(DUMP_OUTPUT, backup)
        print(f"Backed up previous dump to {backup}")

    # Run Il2CppDumper
    dumper = os.path.join(DUMPER_PATH, "Il2CppDumper.exe")
    print(f"Running Il2CppDumper...")
    result = subprocess.run(
        [dumper, ga, meta, DUMP_OUTPUT],
        capture_output=True, text=True, input="y\n", timeout=300
    )
    print(result.stdout[-500:] if result.stdout else "No stdout")
    if result.returncode != 0 and "Done!" not in (result.stdout or ""):
        print(f"Dumper may have failed (exit {result.returncode})")
        return False

    print("Dump complete!")
    return True


def parse_offsets(dump_cs_path):
    """Parse dump.cs to extract field offsets for watched classes."""
    offsets = {}
    current_class = None

    with open(dump_cs_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            # Detect class definition
            class_match = re.match(r'\s*public\s+(?:sealed\s+|abstract\s+)?class\s+(\w+)', line)
            if class_match:
                name = class_match.group(1)
                if name in WATCHED_CLASSES:
                    current_class = name
                    offsets[name] = {}
                else:
                    current_class = None
                continue

            # Detect field with offset
            if current_class and '// 0x' in line:
                field_match = re.search(r'(\w+)\s*;\s*//\s*(0x[0-9A-Fa-f]+)', line)
                if field_match:
                    field_name = field_match.group(1)
                    offset = field_match.group(2)
                    # Check if this field is one we watch
                    for watched in WATCHED_CLASSES[current_class]:
                        if watched.lower() in field_name.lower():
                            offsets[current_class][field_name] = offset
                            break

    return offsets


def diff_offsets(old_offsets, new_offsets):
    """Compare two offset dicts and report changes."""
    changes = []
    for cls in set(list(old_offsets.keys()) + list(new_offsets.keys())):
        old_fields = old_offsets.get(cls, {})
        new_fields = new_offsets.get(cls, {})
        for field in set(list(old_fields.keys()) + list(new_fields.keys())):
            old_val = old_fields.get(field)
            new_val = new_fields.get(field)
            if old_val != new_val:
                changes.append({
                    "class": cls,
                    "field": field,
                    "old": old_val,
                    "new": new_val,
                    "status": "CHANGED" if old_val and new_val else ("ADDED" if new_val else "REMOVED"),
                })
    return changes


def save_offsets(offsets, path):
    """Save offsets to JSON."""
    with open(path, 'w') as f:
        json.dump(offsets, f, indent=2)


def main():
    os.makedirs(OFFSETS_DIR, exist_ok=True)
    current_offsets_file = os.path.join(OFFSETS_DIR, "offsets.json")

    if "--check" in sys.argv:
        # Quick check: verify pymem can read game data
        sys.path.insert(0, r"C:\PyAutoRaid\Modules")
        from memory_reader import MemoryReader
        r = MemoryReader()
        if r.attach():
            snap = r.get_snapshot()
            print(f"Offsets OK! Level={snap['level']}, Power={snap['power']:,}")
            r.detach()
        else:
            print("FAILED: Could not attach or read data. Offsets may be stale.")
        return

    # Run the dump
    if not run_dump():
        return

    # Parse new offsets
    dump_cs = os.path.join(DUMP_OUTPUT, "dump.cs")
    if not os.path.exists(dump_cs):
        print("ERROR: dump.cs not found after dump")
        return

    new_offsets = parse_offsets(dump_cs)
    print(f"\nParsed {sum(len(v) for v in new_offsets.values())} fields from {len(new_offsets)} classes")

    # Compare with previous
    if os.path.exists(current_offsets_file) and "--dump-only" not in sys.argv:
        with open(current_offsets_file) as f:
            old_offsets = json.load(f)
        changes = diff_offsets(old_offsets, new_offsets)
        if changes:
            print(f"\n{'='*50}")
            print(f"WARNING: {len(changes)} OFFSET CHANGES DETECTED!")
            print(f"{'='*50}")
            for c in changes:
                print(f"  {c['class']}.{c['field']}: {c['old']} -> {c['new']} [{c['status']}]")
            print(f"\nYou need to update memory_reader.py with the new offsets!")
        else:
            print("\nNo offset changes detected. memory_reader.py is up to date.")
    else:
        print("\nNo previous offsets to compare (first run).")

    # Save new offsets
    save_offsets(new_offsets, current_offsets_file)
    print(f"Saved offsets to {current_offsets_file}")

    # Also parse TypeInfo RVAs from script.json
    script_json = os.path.join(DUMP_OUTPUT, "script.json")
    if os.path.exists(script_json):
        print("\nParsing TypeInfo RVAs from script.json...")
        with open(script_json, 'r') as f:
            data = json.load(f)
        rvas = {}
        for entry in data.get("ScriptMetadata", []):
            name = entry.get("Name", "")
            if name in ("Client.Model.AppModel_TypeInfo", "Client.ViewModel.AppViewModel_TypeInfo"):
                rvas[name] = hex(entry["Address"])
        if rvas:
            print("TypeInfo RVAs:")
            for k, v in rvas.items():
                print(f"  {k}: {v}")
            rvas_file = os.path.join(OFFSETS_DIR, "typeinfo_rvas.json")
            with open(rvas_file, 'w') as f:
                json.dump(rvas, f, indent=2)


if __name__ == "__main__":
    main()
