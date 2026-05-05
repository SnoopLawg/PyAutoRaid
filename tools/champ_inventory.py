#!/usr/bin/env python3
"""Roster overview — RSL Helper-style "Champion Manager" view.

Surfaces:
  - Total roster + breakdown by rarity / grade / level
  - Food-eligible vs reserved counts (per current preset memberships)
  - Heroes locked / vaulted
  - Same-name duplicates (skill-up fodder candidates)
  - Bottlenecks ("you have 12 unleveled rares — N+ food per rank-up needed")

Read-only. Useful before kicking off level_food.py to know what's in the
pool and what cleanup might help.

Usage:
    python3 tools/champ_inventory.py              # full table + summary
    python3 tools/champ_inventory.py --duplicates # just same-name dup groups
    python3 tools/champ_inventory.py --reserved   # show reserved heroes only
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"

# Plarium internal: rarity int -> name
RARITY_NAME = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary"}
# Per-rank level cap (food-target table from RSL Helper community)
LEVEL_CAP = {1: 7, 2: 13, 3: 19, 4: 25, 5: 31, 6: 37}


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=20) as r:
        return json.loads(r.read())


def load_reserved() -> set[int]:
    p = PROJECT_ROOT / "data" / "reserved_heroes.json"
    if not p.exists():
        return set()
    try:
        return set(int(x) for x in json.loads(p.read_text()).get("reserved", []))
    except Exception:
        return set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duplicates", action="store_true",
                    help="Show same-name duplicate groups (skill-up fodder)")
    ap.add_argument("--reserved", action="store_true",
                    help="Show reserved heroes only")
    ap.add_argument("--bottlenecks", action="store_true",
                    help="Show food-vs-target rank-up bottlenecks")
    args = ap.parse_args()

    heroes = _get("/all-heroes").get("heroes", [])
    reserved = load_reserved()

    if args.reserved:
        print(f"Reserved heroes ({len(reserved)}):")
        for h in heroes:
            if h.get("id") in reserved:
                print(f"  {h.get('id'):>6}  R{h.get('rarity')}/G{h.get('grade')}/L{h.get('level')}  {h.get('name','?')}")
        return 0

    if args.duplicates:
        groups: dict[str, list[dict]] = defaultdict(list)
        for h in heroes:
            if h.get("id") in reserved or h.get("locked"):
                continue
            groups[h.get("name", "?")].append(h)
        dup_groups = {n: hs for n, hs in groups.items() if len(hs) >= 2}
        print(f"Duplicate groups ({len(dup_groups)} names with 2+ copies, "
              f"{sum(len(v) for v in dup_groups.values())} total dups):")
        for name in sorted(dup_groups, key=lambda n: -len(dup_groups[n])):
            hs = sorted(dup_groups[name], key=lambda h: (-h.get("grade", 0), -h.get("level", 0)))
            tags = [f"R{h.get('rarity')}/G{h.get('grade')}/L{h.get('level')}" for h in hs]
            print(f"  {name:<26} ({len(hs)}x): {', '.join(tags)}")
        return 0

    # Full overview
    print(f"=== Champion Inventory ({len(heroes)} total) ===\n")

    rarity_counts = Counter(h.get("rarity") for h in heroes)
    grade_counts = Counter(h.get("grade") for h in heroes)

    print("By rarity:")
    for r, c in sorted(rarity_counts.items()):
        print(f"  {RARITY_NAME.get(r, '?'+str(r)):<10} {c:>4}")

    print("\nBy grade (stars):")
    for g, c in sorted(grade_counts.items()):
        print(f"  Grade {g} (stars):  {c:>4}")

    locked = sum(1 for h in heroes if h.get("locked"))
    vaulted = sum(1 for h in heroes if h.get("in_storage"))
    reserved_count = sum(1 for h in heroes if h.get("id") in reserved)
    food_eligible = sum(1 for h in heroes
                        if h.get("id") not in reserved
                        and not h.get("locked")
                        and not h.get("in_storage"))

    print(f"\nFood-eligible:           {food_eligible:>4}")
    print(f"  Reserved (preset):     {reserved_count:>4}")
    print(f"  Locked:                {locked:>4}")
    print(f"  Vaulted:               {vaulted:>4}")

    # Maxed-level food (ready for rank-up)
    target_overrides = LEVEL_CAP
    maxed = []
    for h in heroes:
        if h.get("id") in reserved or h.get("locked"):
            continue
        cap = target_overrides.get(h.get("grade", 0), 99)
        if h.get("level", 0) >= cap:
            maxed.append(h)
    print(f"\nMaxed (at level cap, ready for rank-up):  {len(maxed)}")
    if maxed and args.bottlenecks:
        by_grade = Counter(h.get("grade") for h in maxed)
        print("  By grade:", dict(by_grade))
        # Rank-up math: need N=grade copies of same grade as fodder
        fodder = Counter(h.get("grade") for h in heroes
                         if h.get("id") not in reserved
                         and not h.get("locked")
                         and h.get("level", 0) < target_overrides.get(h.get("grade", 0), 99))
        print(f"\n  Available fodder per grade: {dict(fodder)}")
        for g in sorted(by_grade.keys()):
            need = g  # rank-up needs `g` copies of grade `g` per target
            ready = by_grade[g]
            avail_fodder = fodder.get(g, 0)
            possible = avail_fodder // need
            verdict = "OK" if possible >= ready else f"BOTTLENECK ({possible}/{ready} possible)"
            print(f"    Grade {g}: {ready} maxed targets, need {need}x grade-{g} food each, "
                  f"have {avail_fodder} fodder -> {verdict}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
