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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heroes-only", action="store_true")
    ap.add_argument("--artifacts-only", action="store_true")
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

    if not args.artifacts_only:
        refresh_heroes()
    if not args.heroes_only:
        refresh_artifacts()
    return 0


if __name__ == "__main__":
    sys.exit(main())
