#!/usr/bin/env python3
"""
Refresh hero + artifact data from the live mod API on the VM.

Replaces the old WinRM-based fetch_heroes.py with a direct HTTP call
to the BepInEx mod on localhost:6790 (VM ports are forwarded).

Writes:
  heroes_all.json         — all heroes (any grade)
  heroes_6star.json       — 6★ heroes only (filtered client-side)
  all_artifacts.json      — all artifacts (equipped + vault)
  equipped_art_ids.json   — set of artifact IDs currently equipped

Usage:
    python3 tools/refresh_data.py
    python3 tools/refresh_data.py --heroes-only
    python3 tools/refresh_data.py --artifacts-only
"""
import json
import sys
import argparse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://localhost:6790"


def fetch_paginated(endpoint: str, page_size: int, timeout: int = 120, label: str = ""):
    """Fetch a paginated endpoint until an empty/short page is returned."""
    items = []
    offset = 0
    while True:
        url = f"{BASE}{endpoint}?offset={offset}&limit={page_size}"
        try:
            r = requests.get(url, timeout=timeout)
            d = r.json()
        except Exception as ex:
            print(f"  !!! {endpoint} offset={offset}: {ex}", file=sys.stderr)
            break
        # Pull the list — endpoints use different keys
        batch = d.get("heroes") or d.get("artifacts") or []
        if not batch:
            break
        items.extend(batch)
        if label and offset % (page_size * 10) == 0:
            print(f"  {label}: {len(items)} so far...")
        offset += page_size
        if len(batch) < page_size:
            break
    return items


def refresh_heroes():
    print("Refreshing heroes...")
    heroes = fetch_paginated("/all-heroes", page_size=20, label="heroes")
    json.dump({"count": len(heroes), "heroes": heroes},
              open(ROOT / "heroes_all.json", "w"))
    six = [h for h in heroes if h.get("grade", 0) >= 6]
    json.dump({"count": len(six), "heroes": six},
              open(ROOT / "heroes_6star.json", "w"))
    equipped = set()
    for h in heroes:
        for a in h.get("artifacts") or []:
            if "id" in a:
                equipped.add(a["id"])
    json.dump(sorted(equipped), open(ROOT / "equipped_art_ids.json", "w"))
    print(f"  {len(heroes)} total, {len(six)} at 6★, {len(equipped)} equipped artifacts")


def refresh_artifacts():
    print("Refreshing artifacts...")
    arts = fetch_paginated("/all-artifacts", page_size=200, label="artifacts")
    json.dump({"count": len(arts), "artifacts": arts},
              open(ROOT / "all_artifacts.json", "w"))
    print(f"  {len(arts)} artifacts")


def refresh_skills():
    """Fetch skill data + descriptions for all heroes."""
    import re

    print("Refreshing skills...")
    try:
        r = requests.get(f"{BASE}/skill-data?min_grade=0", timeout=120)
        data = r.json()
    except Exception as ex:
        print(f"  !!! skill-data failed: {ex}", file=sys.stderr)
        return

    skills_raw = data.get("skills", [])
    if not skills_raw:
        print("  No skills returned")
        return

    # Save raw skills
    json.dump(data, open(ROOT / "skills_data_all.json", "w"), indent=2)

    # Fetch descriptions via /skill-texts (uses IL2CPP localization resolver)
    desc_map = {}  # (hero_id, skill_type_id) -> {name, desc}
    try:
        r2 = requests.get(f"{BASE}/skill-texts?min_grade=0", timeout=120)
        texts = r2.json().get("skills", [])
        def clean(t):
            return re.sub(r'<color=[^>]+>|</color>', '', t) if t else t
        for t in texts:
            key = (t.get("hero_id"), t.get("skill_type_id"))
            name = clean(t.get("name", ""))
            desc = clean(t.get("desc", ""))
            if name or desc:
                desc_map[key] = {"name": name, "desc": desc}
        print(f"  Fetched {len(desc_map)} skill descriptions")
    except Exception as ex:
        print(f"  skill-texts failed (non-fatal): {ex}", file=sys.stderr)

    # Merge descriptions into skill data
    for sk in skills_raw:
        key = (sk.get("hero_id"), sk.get("skill_type_id"))
        info = desc_map.get(key, {})
        if info.get("name"):
            sk["name"] = info["name"]
        if info.get("desc"):
            sk["desc"] = info["desc"]

    # Build skills_db.json keyed by hero name
    try:
        heroes = json.load(open(ROOT / "heroes_all.json"))
        id_to_name = {}
        for h in heroes.get("heroes", []):
            hid = h.get("id")
            name = h.get("name", "")
            if hid and name:
                id_to_name[hid] = name
    except FileNotFoundError:
        print("  heroes_all.json not found, skipping skills_db rebuild")
        return

    skills_db = {}
    for sk in skills_raw:
        hid = sk.get("hero_id")
        name = id_to_name.get(hid)
        if name:
            skills_db.setdefault(name, []).append(sk)

    json.dump(skills_db, open(ROOT / "skills_db.json", "w"), indent=2)

    # Also save skill_descriptions.json (hero_name -> label -> {name, desc, skill_type_id})
    descs = {}
    for hero_name, skill_list in skills_db.items():
        for sk in skill_list:
            sname = sk.get("name", "")
            sdesc = sk.get("desc", "")
            if not sname and not sdesc:
                continue
            if hero_name not in descs:
                descs[hero_name] = {}
            is_a1 = sk.get("is_a1", False)
            cd = sk.get("cooldown")
            existing = set(descs[hero_name].keys())
            if is_a1:
                label = "A1"
            elif cd and cd > 0:
                label = "A2" if "A2" not in existing else ("A3" if "A3" not in existing else f"A{len(existing)+1}")
            else:
                label = "Passive" if "Passive" not in existing else "Passive2"
            descs[hero_name][label] = {"name": sname, "desc": sdesc, "skill_type_id": sk.get("skill_type_id")}
    with open(ROOT / "skill_descriptions.json", "w", encoding="utf-8") as fh:
        json.dump(descs, fh, indent=2, ensure_ascii=False)

    hero_count = len(skills_db)
    skill_count = sum(len(v) for v in skills_db.values())
    desc_count = sum(1 for v in skills_db.values() for sk in v if sk.get("desc"))
    print(f"  {skill_count} skills for {hero_count} heroes ({desc_count} with descriptions)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heroes-only", action="store_true")
    ap.add_argument("--artifacts-only", action="store_true")
    ap.add_argument("--skills-only", action="store_true")
    args = ap.parse_args()

    try:
        r = requests.get(f"{BASE}/status", timeout=5).json()
        if not r.get("logged_in"):
            print(f"!!! Mod up but not logged in: {r}")
            return 1
        print(f"Mod status: scene={r.get('scene')}")
    except Exception as ex:
        print(f"!!! Mod not reachable at {BASE}: {ex}", file=sys.stderr)
        return 1

    if not args.artifacts_only and not args.skills_only:
        refresh_heroes()
    if not args.heroes_only and not args.skills_only:
        refresh_artifacts()
    if not args.heroes_only and not args.artifacts_only:
        refresh_skills()

    # Update SQLite database
    if not args.heroes_only and not args.artifacts_only:
        try:
            from db_init import import_all
            print("\nUpdating database...")
            import_all(data_dir=ROOT)
        except Exception as ex:
            print(f"  DB update failed (non-fatal): {ex}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
