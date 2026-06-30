"""Milestone 3 — Boss / location constraint tables (hard filters).

A machine-readable per-location/boss constraint table for the team generator
(M4) and synergy resolver (M2) to use as HARD FILTERS. Each field is sourced
from game-truth where possible (data/static/{effects,skills_all,
alliance_bosses}.json + tools/m5_stat_targets.py) and flagged `community`
otherwise, so callers know what's verified vs. what still needs in-game checks.

Data lives in `data/static/boss_constraints.json`; this module is the loader
+ a small query API + a CLI.

API:
    get_constraints(location) -> dict           # full record for a location
    list_locations() -> list[str]               # canonical location keys
    is_effect_useful(location, effect_tag)      # False if the boss no-ops it
    acc_floor(location) -> int | None
    faction_lock(location) -> bool

CLI:
    python tools/boss_constraints.py                       # list locations
    python tools/boss_constraints.py clan_boss             # print one location
    python tools/boss_constraints.py --useful clan_boss stun
    python tools/boss_constraints.py --test                # acceptance checks
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "static" / "boss_constraints.json"

# Synonyms that normalise an effect tag onto a canonical control tag used in
# the per-location `cc_immunities` lists. The point: a caller can ask about
# "tm_drain" / "tm_fill" / "decrease_turn_meter" and we map them all onto the
# single canonical "turn_meter" bucket the table stores.
_TAG_ALIASES = {
    # turn-meter manipulation family
    "tm_drain": "turn_meter",
    "tm_fill": "turn_meter",
    "tm_reduce": "turn_meter",
    "tm_boost": "turn_meter",
    "tm_steal": "turn_meter",
    "decrease_turn_meter": "turn_meter",
    "increase_turn_meter": "turn_meter",
    "turnmeter": "turn_meter",
    "turn_meter_manipulation": "turn_meter",
    # decrease speed
    "decrease_speed": "dec_spd",
    "dec_speed": "dec_spd",
    "decreasespeed": "dec_spd",
    "slow": "dec_spd",
    # max-hp reduction
    "max_hp_reduction": "hp_reduction",
    "maxhp_reduction": "hp_reduction",
    "reduce_max_hp": "hp_reduction",
    "hp_reduce": "hp_reduction",
    # cc synonyms
    "petrify": "petrification",
    "petrification": "petrification",
    "sheep": "polymorph",
}

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        with DATA.open(encoding="utf-8") as fh:
            _cache = json.load(fh)
    return _cache


def _norm_tag(tag: str) -> str:
    t = str(tag).strip().lower().replace("-", "_").replace(" ", "_")
    return _TAG_ALIASES.get(t, t)


def _resolve_key(location: str) -> str:
    """Map a user-supplied location name (key or alias) to a canonical key."""
    blob = _load()
    locs = blob["locations"]
    key = str(location).strip().lower().replace("-", "_").replace(" ", "_")
    if key in locs:
        return key
    for canon, rec in locs.items():
        if key == canon or key in [a.lower() for a in rec.get("aliases", [])]:
            return canon
    raise KeyError(
        f"Unknown location {location!r}. Known: {', '.join(sorted(locs))}")


def list_locations() -> list[str]:
    return sorted(_load()["locations"])


def get_constraints(location: str) -> dict:
    """Return the full constraint record for a location (key or alias)."""
    return _load()["locations"][_resolve_key(location)]


def _field_value(rec: dict, field: str):
    """Constraint fields are {value, source, note}; unwrap to the value."""
    f = rec.get(field)
    if isinstance(f, dict) and "value" in f:
        return f["value"]
    return f


def is_effect_useful(location: str, effect_tag: str) -> bool:
    """True unless the location's boss makes `effect_tag` a no-op.

    A control/turn-meter effect listed in the location's `cc_immunities` is
    NOT useful (e.g. Stun / turn-meter manipulation on Clan Boss).
    """
    rec = get_constraints(location)
    immunities = {_norm_tag(t) for t in (_field_value(rec, "cc_immunities") or [])}
    return _norm_tag(effect_tag) not in immunities


def acc_floor(location: str):
    """Effective boss-RES-derived ACC floor (int) or None if not fixed."""
    return _field_value(get_constraints(location), "acc_floor")


def faction_lock(location: str) -> bool:
    return bool(_field_value(get_constraints(location), "faction_lock"))


def dot_reactions(location: str) -> dict:
    return _field_value(get_constraints(location), "dot_reactions") or {}


# --------------------------------------------------------------------------- CLI

def _print_location(key: str) -> None:
    rec = get_constraints(key)
    print(f"=== {key}  —  {rec.get('display_name', key)} ===")
    if rec.get("aliases"):
        print(f"  aliases: {', '.join(rec['aliases'])}")
    for field in ("cc_immunities", "dot_reactions", "acc_floor", "affinity_rule",
                  "faction_lock", "slot_caps", "survival_cliff", "script_notes"):
        f = rec.get(field)
        if not isinstance(f, dict):
            continue
        src = f.get("source", "?")
        val = f.get("value")
        print(f"\n  [{field}]  (source: {src})")
        if isinstance(val, (dict, list)):
            print("    value: " + json.dumps(val, ensure_ascii=False))
        else:
            print(f"    value: {val}")
        if f.get("note"):
            print(f"    note:  {f['note']}")


def _run_acceptance() -> int:
    """M3 acceptance checks. Returns process exit code (0 == all pass)."""
    checks = []

    def chk(label, got, expected):
        ok = got == expected
        checks.append(ok)
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {label}: got={got!r} expected={expected!r}")

    print("M3 boss_constraints acceptance:")
    chk("is_effect_useful('clan_boss','stun') == False",
        is_effect_useful("clan_boss", "stun"), False)
    chk("is_effect_useful('clan_boss','tm_drain') == False",
        is_effect_useful("clan_boss", "tm_drain"), False)
    chk("faction_lock('faction_wars') == True",
        faction_lock("faction_wars"), True)

    # Ice Golem dot_reactions flags poison (immune).
    ig = dot_reactions("ice_golem")
    ig_poison = str(ig.get("poison", "")).lower()
    poison_flagged = "immun" in ig_poison or ig.get("poison_immune") is True
    chk("ice_golem dot_reactions flags poison (immune)", poison_flagged, True)

    # clan_boss acc_floor matches m5_stat_targets' CB (UNM) value (225).
    cb_floor = acc_floor("clan_boss")
    m5_cb = _m5_cb_acc_floor()
    chk("clan_boss acc_floor matches m5_stat_targets CB value",
        cb_floor, m5_cb)

    # Bonus sanity: arena does NOT no-op stun (control is the win condition).
    chk("is_effect_useful('arena','stun') == True",
        is_effect_useful("arena", "stun"), True)

    passed = sum(checks)
    print(f"\n{passed}/{len(checks)} checks passed.")
    return 0 if passed == len(checks) else 1


def _m5_cb_acc_floor():
    """Read the CB (AllianceBoss UNM) ACC floor straight from the
    m5_stat_targets output so the acceptance check is genuinely cross-sourced,
    not a self-comparison."""
    p = ROOT / "data" / "static" / "stage_stat_targets.json"
    try:
        blob = json.loads(p.read_text(encoding="utf-8"))
    except OSError:
        return None
    floors = [r.get("acc_floor") for r in blob.get("stages", [])
              if r.get("area") == "AllianceBoss" and r.get("acc_floor") is not None]
    return max(floors) if floors else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("location", nargs="?", help="location key or alias to print")
    ap.add_argument("--useful", nargs=2, metavar=("LOCATION", "EFFECT"),
                    help="print whether EFFECT is useful at LOCATION")
    ap.add_argument("--test", action="store_true", help="run M3 acceptance checks")
    args = ap.parse_args(argv)

    if args.test:
        return _run_acceptance()

    if args.useful:
        loc, eff = args.useful
        print(is_effect_useful(loc, eff))
        return 0

    if args.location:
        try:
            _print_location(_resolve_key(args.location))
        except KeyError as e:
            print(e, file=sys.stderr)
            return 2
        return 0

    print("Locations with constraint records:")
    for k in list_locations():
        rec = _load()["locations"][k]
        af = _field_value(rec, "acc_floor")
        fl = _field_value(rec, "faction_lock")
        print(f"  {k:18s} ACC floor={str(af):>5}  faction_lock={fl}  "
              f"({rec.get('display_name','')})")
    print("\nRun `python tools/boss_constraints.py <location>` for detail, "
          "or `--test` for acceptance checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
