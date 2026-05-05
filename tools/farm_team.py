#!/usr/bin/env python3
"""Build a campaign farm team: a user-picked carry + auto-selected food fodder.

Workflow:
  1. User picks a CARRY hero (slot 1) — should be strong enough to solo/carry
     the chosen campaign stage. No XP leader skill is needed; XP is uniform
     across the team in Raid.
  2. Tool fills the remaining slots with food champs from the eligible pool
     (passes ALL the protection filters: not legendary, not protected, not a
     Faction Guardian, not empowered, not a fusion ingredient, not in Master
     Vault, not locked, etc.).
  3. Tool writes the team to a preset slot you specify, ready for battle.
  4. (Loop integration: tools/level_food.py drives the actual battle replay
     + auto-rank-up after each pass.)

Why a separate tool from level_food.py: this one is purely "build the team
and save the preset". The actual leveling loop is `level_food.py --preset N`.

Usage:
    python3 tools/farm_team.py --carry-name "Demytha" --preset 5
    python3 tools/farm_team.py --carry 18860 --preset 5 --slots 4 --max-grade 2
    python3 tools/farm_team.py --list-carries          # see eligible carry options
    python3 tools/farm_team.py --carry 18860 --dry-run # show team, don't save
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"
RARITY_NAME = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary"}


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
        return {"exclude_all_legendaries": True, "exclude_all_epics": True,
                "protected_names": [], "fusion_targets": [],
                "exclude_empowered": True, "exclude_reserve_vault": False}
    return json.loads(p.read_text())


def is_food_eligible(h: dict, reserved: set[int], protected: dict,
                     max_rarity: int = 3, max_grade: int = 6) -> bool:
    """Same gates as champ_manager.is_food_eligible PLUS rarity/grade caps
    so we only pick LOW-INVESTMENT heroes (commons/uncommons/rares at low grade).
    Goal: feed cheap heroes that we'd be happy to consume after they max out."""
    if h.get("id") in reserved or h.get("locked") or h.get("in_storage"):
        return False
    if h.get("is_faction_guardian"):
        return False
    if h.get("is_fusion_ingredient"):
        return False
    if protected.get("exclude_empowered", True) and (h.get("empower") or 0) > 0:
        return False
    if protected.get("exclude_reserve_vault", False) and h.get("in_bathhouse"):
        return False
    rarity = h.get("rarity", 0)
    if protected.get("exclude_all_legendaries", True) and rarity == 5:
        return False
    if protected.get("exclude_all_epics", False) and rarity == 4:
        return False
    if rarity > max_rarity:
        return False
    if (h.get("grade") or 0) > max_grade:
        return False
    name = h.get("name", "")
    if name in protected.get("protected_names", []):
        return False
    if name in protected.get("fusion_targets", []):
        return False
    return True


def list_carry_candidates(heroes: list[dict]) -> list[dict]:
    """Reasonable carry candidates: rarity >= Rare, not in Master Vault,
    not locked. Faction Guardians ARE allowed — they can fight in battles
    even though they can't be sacrificed. Sorted by rarity → grade → level.
    The user picks from this list based on preference + which stage they want
    to farm."""
    out = []
    for h in heroes:
        if h.get("locked") or h.get("in_storage"):
            continue
        if (h.get("rarity") or 0) < 3:
            continue
        out.append(h)
    out.sort(key=lambda h: (-(h.get("rarity") or 0),
                             -(h.get("grade") or 0),
                             -(h.get("level") or 0),
                             h.get("name") or ""))
    return out


def pick_food(heroes: list[dict], reserved: set[int], protected: dict,
              n_slots: int, exclude_id: int,
              max_rarity: int = 3, max_grade: int = 6) -> list[dict]:
    """Pick `n_slots` food candidates. Strategy: prioritize heroes whose level
    is FAR FROM their grade cap (most XP runway). Among those, pick lowest
    rarity first (cheapest to lose). Within rarity, lowest grade first."""
    pool = [h for h in heroes
            if h.get("id") != exclude_id
            and is_food_eligible(h, reserved, protected, max_rarity, max_grade)]

    def runway(h: dict) -> int:
        cap = (h.get("grade") or 0) * 10
        return max(0, cap - (h.get("level") or 0))

    pool.sort(key=lambda h: (
        -runway(h),                  # most XP runway first
        h.get("rarity", 99),         # then lowest rarity
        h.get("grade", 99),          # then lowest grade
        h.get("level", 0),           # tie-break: lowest level
        h.get("name", ""),
    ))
    return pool[:n_slots]


def save_preset(preset_id: int, name: str, hero_ids: list[int]) -> dict:
    """Build a preset with hero_ids in slots 0..N. Uses /save-preset which
    writes a fresh preset by id (overwrites any existing one at that id).
    Note: name length cap is 15 chars (per preset_manage memory)."""
    if len(name) > 15:
        name = name[:15]
    qs = urllib.parse.urlencode({
        "id": preset_id,
        "name": name,
        "heroes": ",".join(str(i) for i in hero_ids),
    })
    return _get(f"/save-preset?{qs}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--carry", type=int, default=None,
                    help="Carry hero instance id (slot 1)")
    ap.add_argument("--carry-name", default=None,
                    help="Carry hero name (first match wins)")
    ap.add_argument("--list-carries", action="store_true",
                    help="List eligible carry heroes and exit")
    ap.add_argument("--preset", type=int, default=None,
                    help="Preset id to write the team to (1..15). Required unless --dry-run")
    ap.add_argument("--preset-name", default="food-farm",
                    help="Preset name (max 15 chars)")
    ap.add_argument("--slots", type=int, default=4,
                    help="Number of food slots (default 4 = 5-hero team)")
    ap.add_argument("--max-rarity", type=int, default=3,
                    help="Max food rarity (1=Common, 2=Uncommon, 3=Rare, default 3)")
    ap.add_argument("--max-grade", type=int, default=6,
                    help="Max food grade (default 6 = no cap)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show team but don't save preset")
    args = ap.parse_args()

    heroes = _get("/all-heroes").get("heroes", [])
    reserved = load_reserved()
    protected = load_protected()
    by_id = {h.get("id"): h for h in heroes}
    by_name = {}
    for h in heroes:
        by_name.setdefault(h.get("name", ""), h)

    if args.list_carries:
        cands = list_carry_candidates(heroes)
        print(f"=== Carry candidates ({len(cands)}) ===")
        print(f"{'id':<8} {'rarity':<10} {'grade':<3} {'level':<5} {'name'}")
        for h in cands[:60]:
            print(f"{h.get('id', 0):<8} {RARITY_NAME.get(h.get('rarity'), '?'):<10} "
                  f"G{h.get('grade'):<2} L{h.get('level'):<4} {h.get('name')}")
        if len(cands) > 60:
            print(f"... and {len(cands)-60} more")
        return 0

    if not args.carry and not args.carry_name:
        ap.error("Specify --carry HEROID or --carry-name NAME (or --list-carries)")
    if args.carry:
        carry = by_id.get(args.carry)
        if not carry:
            print(f"ERROR: hero id {args.carry} not in roster", file=sys.stderr)
            return 1
    else:
        carry = by_name.get(args.carry_name)
        if not carry:
            print(f"ERROR: no hero named '{args.carry_name}'", file=sys.stderr)
            return 1

    if carry.get("is_faction_guardian"):
        print(f"WARNING: carry {carry['name']} is a Faction Guardian; the game "
              f"won't let you put a guardian in a battle preset slot.")
    if carry.get("in_storage"):
        print(f"WARNING: carry {carry['name']} is in Master Vault; move to "
              f"Champion list before saving the preset.")

    food = pick_food(heroes, reserved, protected, args.slots, carry["id"],
                     args.max_rarity, args.max_grade)
    if len(food) < args.slots:
        print(f"WARNING: pool only had {len(food)} eligible food, "
              f"requested {args.slots}. Filling with what we have.")

    print("=== Farm team ===")
    print(f"  carry  | id={carry['id']:<6} R{carry['rarity']}/G{carry['grade']}/"
          f"L{carry['level']:<3} {carry['name']}")
    for i, f in enumerate(food, 1):
        cap = (f.get("grade") or 0) * 10
        runway = max(0, cap - (f.get("level") or 0))
        loc = ('Reserve Vault' if f.get('in_bathhouse')
               else 'Master Vault' if f.get('in_storage')
               else 'Champion list')
        print(f"  food#{i} | id={f['id']:<6} R{f['rarity']}/G{f['grade']}/"
              f"L{f['level']:<3} {f['name']:<22} (XP runway: {runway} levels, "
              f"in {loc})")

    if not food:
        print("\nNo food candidates available. Either tighten exclusions or "
              "summon some commons/uncommons.")
        return 0

    hero_ids = [carry["id"]] + [f["id"] for f in food]
    print(f"\nProposed preset hero_ids: {hero_ids}")

    if args.dry_run:
        print("(dry-run — preset not saved)")
        return 0
    if args.preset is None:
        ap.error("--preset N required unless --dry-run is set")

    print(f"\n=== Saving to preset #{args.preset} as '{args.preset_name}' ===")
    r = save_preset(args.preset, args.preset_name, hero_ids)
    if r.get("ok") or r.get("preset_id") or r.get("id"):
        print(f"  + saved")
        print(f"\nNext step: open the campaign stage in-game, then run:")
        print(f"  python3 tools/level_food.py --preset {args.preset} \\")
        print(f"    --runs 50 --auto-rank-up --max-fails 3")
    else:
        print(f"  ! save failed: {r}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
