#!/usr/bin/env python3
"""Build data/reserved_heroes.json — instance ids that should NEVER be
used as food/sacrifice. Sources:

  1. Members of every saved preset (read via /presets + /preset-deep).
     Covers the user's CB / Dragon / Spider / Iron Twins / Live Arena
     comps without manual flagging.
  2. (Future) HH wishlist heroes the user has marked as "team I want
     to build". Not implemented yet — placeholder hook.
  3. (Future) Champion-of-the-month / event-locked heroes (so they don't
     get fed accidentally during their bonus-XP window).

The food picker in tools/level_food.py reads this set and excludes
matching heroes from the candidate pool.

Usage:
    python3 tools/build_reserved_set.py
    python3 tools/build_reserved_set.py --include-cb-only   # narrower
    python3 tools/build_reserved_set.py --extra 12345,67890 # add by id
"""
from __future__ import annotations
import argparse
import json
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"
OUT_PATH = PROJECT_ROOT / "data" / "reserved_heroes.json"


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=20) as r:
        return json.loads(r.read())


def collect_preset_members(only_cb: bool = False) -> dict[int, list[str]]:
    """Return {hero_id: [preset_name, ...]} across all saved presets.
    only_cb=True restricts to type-1 PvE presets (CB / dungeon)."""
    presets = _get("/presets").get("presets", [])
    out: dict[int, list[str]] = {}
    for p in presets:
        if p.get("empty"):
            continue
        if only_cb and p.get("type") != 1:
            continue
        try:
            deep = _get(f"/preset-deep?id={p['id']}")
        except Exception as e:
            print(f"  WARN: deep-read failed for preset {p['id']}: {e}",
                  file=sys.stderr)
            continue
        for setup in deep.get("setups", []):
            hid = setup.get("hero_id")
            if hid:
                out.setdefault(hid, []).append(f"{p['name']} (id={p['id']})")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-cb-only", action="store_true",
                    help="Only reserve heroes from type-1 PvE presets")
    ap.add_argument("--extra", default="",
                    help="Comma-separated extra hero ids to reserve")
    args = ap.parse_args()

    preset_members = collect_preset_members(only_cb=args.include_cb_only)

    reserved = set(preset_members.keys())

    extra_ids = []
    if args.extra:
        for x in args.extra.split(","):
            x = x.strip()
            if x:
                try:
                    extra_ids.append(int(x))
                except ValueError:
                    print(f"  WARN: invalid id {x!r} in --extra", file=sys.stderr)
    reserved.update(extra_ids)

    # Resolve hero names for the manifest
    heroes = _get("/all-heroes").get("heroes", [])
    name_by_id = {h["id"]: h.get("name", "?") for h in heroes if "id" in h}

    out = {
        "reserved": sorted(reserved),
        "sources": {
            "presets": {
                str(hid): {"name": name_by_id.get(hid, "?"),
                           "presets": members}
                for hid, members in preset_members.items()
            },
            "extra": sorted(extra_ids),
        },
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT_PATH}: {len(reserved)} reserved heroes")
    print(f"  from {len(preset_members)} preset memberships, "
          f"{len(extra_ids)} extras")

    print("\nReserved heroes:")
    for hid in sorted(reserved):
        nm = name_by_id.get(hid, "?")
        presets = preset_members.get(hid, [])
        marker = " (preset:" + " | ".join(presets) + ")" if presets else " (extra)"
        print(f"  {hid:>6}  {nm}{marker}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
