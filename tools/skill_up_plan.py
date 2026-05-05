#!/usr/bin/env python3
"""Plan skill-ups using same-name duplicate sacrifices.

In Raid, skill-up fodder = sacrifice a same-name dup to increase skill levels
on the kept copy (random distribution across not-yet-maxed skills).

This planner:
  - Groups heroes by name
  - For each name with 2+ copies, picks the "primary" (highest grade/level)
  - Computes which primaries still have skill levels to gain
  - Plans which dups to sacrifice (lowest grade/level first)
  - Skips dups that are reserved or in the active food chain (rank_up_plan)

Read-only by default. --execute hits /skill-up.

Usage:
    python3 tools/skill_up_plan.py                 # full plan
    python3 tools/skill_up_plan.py --name Coldheart # one name only
    python3 tools/skill_up_plan.py --max-feeds 3   # cap dups per primary
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"


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


def load_protected() -> dict:
    p = PROJECT_ROOT / "data" / "protected_heroes.json"
    if not p.exists():
        return {"exclude_all_legendaries": True, "exclude_all_epics": False,
                "protected_names": [], "fusion_targets": []}
    return json.loads(p.read_text())


def is_feed_eligible(h: dict, reserved: set[int], protected: dict) -> bool:
    """A hero is allowed as skill-up fodder?"""
    if h.get("id") in reserved or h.get("locked") or h.get("in_storage"):
        return False
    # Faction Guardian assignment hard-blocks the skill-up cmd too.
    if h.get("is_faction_guardian"):
        return False
    # Empowered heroes — opt-in exclusion (default true).
    if protected.get("exclude_empowered", True) and (h.get("empower") or 0) > 0:
        return False
    # Fusion ingredients — hard exclude.
    if h.get("is_fusion_ingredient"):
        return False
    # in_bathhouse = "Reserve Vault" in the game UI. Opt-in exclusion.
    if protected.get("exclude_reserve_vault", False) and h.get("in_bathhouse"):
        return False
    rarity = h.get("rarity", 0)
    if protected.get("exclude_all_legendaries", True) and rarity == 5:
        return False
    if protected.get("exclude_all_epics", False) and rarity == 4:
        return False
    name = h.get("name", "")
    if name in protected.get("protected_names", []):
        return False
    if name in protected.get("fusion_targets", []):
        return False
    return True


def load_skills_db() -> dict[str, list[dict]]:
    """Map hero_name -> list of skill rows (with level_bonuses)."""
    p = PROJECT_ROOT / "skills_db.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def hero_skill_levels(name: str, hero_id: int, skills_db: dict,
                      hero_skills_live: list[dict]) -> list[dict]:
    """For a given hero, return per-skill {name, current, max, remaining}."""
    rows = skills_db.get(name, [])
    rows = [r for r in rows if r.get("hero_id") == hero_id]
    by_type = {r.get("skill_type_id"): r for r in rows}
    out = []
    for s in hero_skills_live:
        tid = s.get("type_id")
        cur = s.get("level", 1)
        row = by_type.get(tid, {})
        max_level = 1 + len(row.get("level_bonuses", []))
        out.append({
            "type_id": tid,
            "name": row.get("name", "?"),
            "current": cur,
            "max": max_level,
            "remaining": max(0, max_level - cur),
            "is_a1": row.get("is_a1", False),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=None,
                    help="Plan skill-ups for one hero name only")
    ap.add_argument("--max-feeds", type=int, default=0,
                    help="Cap number of dup sacrifices per primary (0 = use all)")
    ap.add_argument("--min-remaining", type=int, default=1,
                    help="Skip primaries with fewer than this many skill levels remaining")
    ap.add_argument("--execute", action="store_true",
                    help="Actually call /skill-up (DESTRUCTIVE)")
    args = ap.parse_args()

    heroes = _get("/all-heroes").get("heroes", [])
    reserved = load_reserved()
    protected = load_protected()
    skills_db = load_skills_db()

    # Group by name
    groups: dict[str, list[dict]] = defaultdict(list)
    for h in heroes:
        if h.get("locked"):
            continue
        groups[h.get("name", "?")].append(h)

    plans = []
    skipped_no_dups = 0
    skipped_maxed = 0

    for name, hs in groups.items():
        if args.name and name != args.name:
            continue
        if len(hs) < 2:
            skipped_no_dups += 1
            continue
        # Primary = highest grade, then highest level, then highest rarity
        hs_sorted = sorted(hs, key=lambda h: (
            -h.get("grade", 0),
            -h.get("level", 0),
            -h.get("rarity", 0),
            h.get("id", 0),
        ))
        primary = hs_sorted[0]
        dups = hs_sorted[1:]
        # Primary can be anything (incl. legendary/protected).
        # But feed dups must pass the protected/reserved gates.
        feedable_dups = [d for d in dups if is_feed_eligible(d, reserved, protected)]
        if not feedable_dups:
            skipped_no_dups += 1
            continue
        skill_levels = hero_skill_levels(
            name, primary.get("id"), skills_db, primary.get("skills", []))
        total_remaining = sum(s["remaining"] for s in skill_levels)
        if total_remaining < args.min_remaining:
            skipped_maxed += 1
            continue
        feeds = feedable_dups
        if args.max_feeds > 0:
            feeds = feeds[:args.max_feeds]
        plans.append({
            "primary": primary,
            "feeds": feeds,
            "skill_levels": skill_levels,
            "total_remaining": total_remaining,
            "reserved_primary": primary.get("id") in reserved,
        })

    plans.sort(key=lambda p: (
        -p["total_remaining"],
        -p["primary"].get("rarity", 0),
        -p["primary"].get("grade", 0),
    ))

    print(f"=== Skill-Up Plan ({len(plans)} primaries with feed-able dups) ===\n")
    excl = []
    if protected.get("exclude_all_legendaries"): excl.append("legendaries")
    if protected.get("exclude_all_epics"): excl.append("epics")
    if protected.get("fusion_targets"): excl.append(f"fusions={protected['fusion_targets']}")
    if protected.get("protected_names"): excl.append(f"protected={protected['protected_names']}")
    if excl:
        print(f"Protected from feeds: {', '.join(excl)}")
    print(f"Skipped: {skipped_no_dups} (no dups), {skipped_maxed} (skills maxed)\n")

    for i, p in enumerate(plans, 1):
        pri = p["primary"]
        rmark = "  [RESERVED]" if p["reserved_primary"] else ""
        print(f"[{i:>2}] {pri.get('name')} (id {pri.get('id')}, "
              f"R{pri.get('rarity')}/G{pri.get('grade')}/L{pri.get('level')}){rmark}")
        for s in p["skill_levels"]:
            tag = "(A1)" if s["is_a1"] else "    "
            bar = "*" * s["current"] + "." * s["remaining"]
            print(f"     {tag} {s['name']:<26} {s['current']}/{s['max']}  [{bar}]")
        print(f"     feeds available: {len(p['feeds'])}, "
              f"skill levels remaining: {p['total_remaining']}")
        for f in p["feeds"][:3]:
            print(f"       feed: id={f.get('id')} R{f.get('rarity')}/G{f.get('grade')}/L{f.get('level')}")
        if len(p["feeds"]) > 3:
            print(f"       ... and {len(p['feeds']) - 3} more")
        print()

    if args.execute and plans:
        print(f"\n=== EXECUTING skill-ups ===")
        executed = 0
        for p in plans:
            pri = p["primary"]
            food_csv = ",".join(str(f["id"]) for f in p["feeds"])
            try:
                r = _get(f"/skill-up?hero_id={pri['id']}&food={food_csv}")
            except Exception as ex:
                print(f"  ERR {pri.get('name')}: {ex}")
                continue
            if r.get("ok"):
                print(f"  + {pri.get('name')}: fed {len(p['feeds'])} dups")
                executed += 1
            else:
                print(f"  ! {pri.get('name')}: {r.get('error')}")
        print(f"\nExecuted {executed}/{len(plans)} skill-ups")
    elif plans:
        print(f"(plan only -- pass --execute to actually skill up)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
