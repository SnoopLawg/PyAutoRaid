"""Preset management CLI — create / list / remove / update saved
team presets via the BepInEx mod's HTTP API.

Until now we could only read presets (`tools/preset_loader.py`) and
edit existing ones via direct curl to `/update-preset`. Adding new
presets required hand-crafting `/save-preset` curls, which were
fiddly: hero names → IDs lookup, URL encoding (especially spaces),
preset type IDs, etc. This tool wraps that.

Usage:
    # List all presets
    python3 tools/preset_manage.py list

    # Create a new preset by hero NAME (auto-resolves to instance IDs)
    python3 tools/preset_manage.py create \
        --name "CB UNM Spirit" \
        --heroes "Maneater,Demytha,Ninja,Geomancer,Venomage" \
        --type 1

    # Create with explicit hero instance IDs (when you have multiples
    # like 2x Maneater and want specific ones)
    python3 tools/preset_manage.py create \
        --name "Budget UK" \
        --hero-ids "15120,18357,2643,13615,5692" \
        --type 1

    # Apply skill priorities at the same time. Format per hero:
    #   <hero_id>:<skill_id>=<pri>,<skill_id>=<pri>;...
    # Priorities: 0=Default, 1=First, 2=Second, 3=Third, 4=NotUsed
    python3 tools/preset_manage.py create \
        --name "Myth Eater Magic" \
        --heroes "Maneater,Demytha,Ninja,Geomancer,Venomage" \
        --priorities "18607:65102=1,65103=2;2643:62003=2"

    # Remove
    python3 tools/preset_manage.py remove --id 99

Preset types (from observation):
    1 = General PvE / CB / Dungeons
    7 = Alternate slot some users tag as "fast"
    Others — as Plarium adds slots/categories the enum may grow.
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


def _mod_get(endpoint: str, params: dict | None = None,
             timeout: float = 30.0) -> dict:
    """GET request to the mod with proper URL encoding (handles names
    with spaces, &, etc. — quote_via=quote keeps `+` literal instead
    of mangling it to space-as-plus).
    """
    if params:
        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"{MOD_BASE}{endpoint}?{qs}"
    else:
        url = f"{MOD_BASE}{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = r.read().decode("utf-8")
        return json.loads(data)
    except urllib.error.URLError as e:
        return {"error": f"connection failed: {e.reason}"}
    except json.JSONDecodeError as e:
        return {"error": f"invalid JSON response: {e}"}
    except Exception as e:
        return {"error": str(e)}


def _resolve_heroes_to_ids(names: list[str]) -> list[int]:
    """Resolve a list of hero NAMES to instance IDs by querying
    `/all-heroes`. When a name has multiple owned instances (e.g. 2x
    Maneater), picks the highest-grade then highest-level one.
    """
    r = _mod_get("/all-heroes")
    if "error" in r:
        raise SystemExit(f"failed to fetch /all-heroes: {r['error']}")
    heroes = r.get("heroes", [])
    by_name: dict[str, list[dict]] = {}
    for h in heroes:
        n = h.get("name")
        if n:
            by_name.setdefault(n, []).append(h)

    ids: list[int] = []
    used: set[int] = set()
    for name in names:
        candidates = [h for h in by_name.get(name, []) if h.get("id") not in used]
        if not candidates:
            # No more instances of this name available — could be a
            # "Maneater, Maneater" pair where we already used the only one
            raise SystemExit(
                f"hero not found (or already used): {name!r}. "
                f"Owned: {sorted(by_name.keys())[:10]}..."
            )
        candidates.sort(key=lambda h: (-h.get("grade", 0), -h.get("level", 0)))
        chosen = candidates[0]
        ids.append(int(chosen["id"]))
        used.add(int(chosen["id"]))
    return ids


def cmd_list(args) -> int:
    r = _mod_get("/presets")
    if "error" in r:
        print(f"ERROR: {r['error']}", file=sys.stderr)
        return 1
    presets = r.get("presets", [])
    print(f"{'id':>5}  {'name':<35}  type  empty  setups")
    print("-" * 70)
    for p in presets:
        empty = "yes" if p.get("is_empty") else "no"
        setups = len(p.get("skill_priorities_setups") or [])
        print(f"{p.get('id'):>5}  {p.get('name','?'):<35}  "
              f"{p.get('type'):>4}  {empty:>5}  {setups:>6}")
    return 0


def cmd_create(args) -> int:
    # Validate name — game's AssertIsValidName rejects certain
    # characters. Spaces and alphanumerics work; '+' and possibly
    # other special chars trigger the ERROR popup. Restricting here
    # so the user gets a clean error instead of an in-game popup.
    if args.name and any(c in args.name for c in "+&<>"):
        print(f"ERROR: name contains characters the game rejects ('+', '&', etc.). "
              f"Use spaces and alphanumerics.", file=sys.stderr)
        return 2

    hero_ids: list[int] = []
    if args.empty:
        pass  # no heroes needed
    elif args.hero_ids:
        try:
            hero_ids = [int(x.strip()) for x in args.hero_ids.split(",") if x.strip()]
        except ValueError as e:
            print(f"ERROR: invalid hero-ids: {e}", file=sys.stderr)
            return 2
    elif args.heroes:
        names = [n.strip() for n in args.heroes.split(",") if n.strip()]
        try:
            hero_ids = _resolve_heroes_to_ids(names)
        except SystemExit as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        print(f"Resolved {names} -> {hero_ids}")
    else:
        print("ERROR: provide --heroes, --hero-ids, or --empty", file=sys.stderr)
        return 2

    if not args.empty and (len(hero_ids) < 1 or len(hero_ids) > 6):
        print(f"ERROR: need 1-6 heroes, got {len(hero_ids)}", file=sys.stderr)
        return 2

    params = {
        "name": args.name,
        "type": str(args.type),
    }
    if args.empty:
        params["empty"] = "1"
    else:
        params["heroes"] = ",".join(str(h) for h in hero_ids)
    descr = "empty" if args.empty else f"heroes={hero_ids}"
    print(f"Creating preset: name={args.name!r}, type={args.type}, {descr}")
    r = _mod_get("/save-preset", params)
    if "error" in r:
        print(f"ERROR: {r['error']}", file=sys.stderr)
        return 1
    if not r.get("ok"):
        print(f"ERROR: save returned non-ok: {r}", file=sys.stderr)
        return 1
    print(f"Saved (server-id assignment is async).")
    debug = r.get("debug", {})
    print(f"  strategy: {debug.get('strategy')}")
    print(f"  added to in-memory list: {r.get('addedToList')}")

    # Apply priorities + starters in a follow-up update if provided.
    # `/save-preset` doesn't accept those params; the existing
    # `/update-preset` endpoint does.
    if args.priorities or args.starters:
        # We need the new preset's id. List presets and find the new one.
        listing = _mod_get("/presets")
        if "error" in listing:
            print(f"WARN: created but couldn't fetch id for follow-up update: {listing['error']}",
                  file=sys.stderr)
            return 0
        presets = listing.get("presets", [])
        # The newly-created preset may have id=0 transiently; or it may
        # already have a server-assigned id by the time we list.
        # Match by name + recency (last item with our name).
        candidates = [p for p in presets if p.get("name") == args.name]
        if not candidates:
            print(f"WARN: new preset not found in /presets after save (name={args.name!r}); "
                  "priorities/starters not applied.", file=sys.stderr)
            return 0
        new_id = candidates[-1].get("id")
        print(f"  new id: {new_id}")
        update_params = {"id": str(new_id)}
        if args.priorities:
            update_params["priorities"] = args.priorities
        if args.starters:
            update_params["starters"] = args.starters
        ur = _mod_get("/update-preset", update_params)
        if "error" in ur:
            print(f"WARN: priorities/starters update failed: {ur['error']}", file=sys.stderr)
            return 1
        print(f"  priorities/starters applied")
    return 0


def cmd_remove(args) -> int:
    r = _mod_get("/remove-preset", {"id": str(args.id)})
    if "error" in r:
        print(f"ERROR: {r['error']}", file=sys.stderr)
        return 1
    print(f"Removed preset id={args.id}")
    return 0


def cmd_update(args) -> int:
    if args.name and any(c in args.name for c in "+&<>"):
        print(f"ERROR: name contains characters the game rejects ('+', '&', etc.). "
              f"Use spaces and alphanumerics.", file=sys.stderr)
        return 2
    params = {"id": str(args.id)}
    if args.priorities:
        params["priorities"] = args.priorities
    if args.starters:
        params["starters"] = args.starters
    if args.name:
        params["name"] = args.name
    r = _mod_get("/update-preset", params)
    if "error" in r:
        print(f"ERROR: {r['error']}", file=sys.stderr)
        return 1
    print(f"Updated preset id={args.id}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_list = sub.add_parser("list", help="List all saved presets")

    sp_create = sub.add_parser("create", help="Create a new preset")
    sp_create.add_argument("--name", required=True, help="Preset display name")
    sp_create.add_argument("--heroes", help="Comma-separated hero names")
    sp_create.add_argument("--hero-ids", help="Comma-separated instance IDs (alt to --heroes)")
    sp_create.add_argument("--type", type=int, default=1,
                            help="Preset type (1=GeneralPvE/CB, default)")
    sp_create.add_argument("--priorities", default=None,
                            help="Skill priorities: heroId:sid=pri,sid=pri;... "
                                 "(0=Default 1=First 2=Second 3=Third 4=NotUsed)")
    sp_create.add_argument("--starters", default=None,
                            help="Forced openers: heroId:sid,sid;heroId:sid;...")
    sp_create.add_argument("--empty", action="store_true",
                            help="Create an empty preset (no hero setups). "
                                 "Useful as a shell to populate via update.")
    sp_create.add_argument("--allow-unsafe", action="store_true",
                            help=argparse.SUPPRESS)  # legacy; kept for compat

    sp_remove = sub.add_parser("remove", help="Remove a preset by id")
    sp_remove.add_argument("--id", type=int, required=True)

    sp_update = sub.add_parser("update", help="Update priorities/starters/name on existing")
    sp_update.add_argument("--id", type=int, required=True)
    sp_update.add_argument("--priorities", default=None)
    sp_update.add_argument("--starters", default=None)
    sp_update.add_argument("--name", default=None,
                            help="Rename the preset. Spaces + alphanumerics only.")

    args = p.parse_args()
    return {"list": cmd_list, "create": cmd_create,
            "remove": cmd_remove, "update": cmd_update}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
