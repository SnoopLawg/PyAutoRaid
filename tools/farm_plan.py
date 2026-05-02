"""Phase 7 — smart farm recommender.

Given a list of needed artifact sets (or a target preset's
preferred_sets), surfaces which dungeons drop them. Estimates run
counts using the per-set max_prob from `data/static/drops.json`.

Per CLAUDE.md, drop rates per slot/rarity aren't fully exposed in the
static export — we work with set-level probability and rough heuristics.
The real value here is "tell me which dungeon to farm for set X" so
the user stops guessing, not "exact run count to ±1".

Usage:
    python3 tools/farm_plan.py --target cb-unm
    python3 tools/farm_plan.py --target dragon-25 --max-energy 5000
    python3 tools/farm_plan.py --sets "Lifesteal,Accuracy,Speed"
    python3 tools/farm_plan.py --list-sources

Output: a ranked list of (dungeon, difficulty, sets-it-drops, energy-per-run)
plus a recommendation. The recommendation is greedy: rank by sets-covered
weighted by drop-probability, descending; print enough rows to cover
the target's preferred_sets.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))


# Energy cost per dungeon run (game-published values; verify per
# location). These are baseline costs — actual energy varies by
# stage. The recommender uses these as the "cost per attempt" estimate.
_ENERGY_COST = {
    "Normal": 6,
    "Brutal": 9,
    "Nightmare": 12,
    "Hard": 9,
}


def _set_id_to_name() -> dict[int, str]:
    """Build set id -> human name from artifact_sets.json."""
    p = PROJECT_ROOT / "data" / "static" / "artifact_sets.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[int, str] = {}
    for s in raw.get("sets", []):
        sid = s.get("id")
        nm = s.get("set")
        if sid is not None and nm:
            out[sid] = nm
    return out


# In-game UI uses user-friendly names ("Lifesteal", "Speed"); the
# static data uses internal codenames ("LifeDrain", "AttackSpeed"). This
# alias map bridges so target presets can use either.
_SET_ALIASES = {
    "lifesteal": "LifeDrain",
    "speed": "AttackSpeed",
    "stun": "StunChance",
    "toxic": "DotRate",
    "immunity": "BlockDebuff",
    "offense": "AttackPower",
    "defense": "Defense",
    "perception": "Accuracy",
    "lethal": "IgnoreDefense",
    "cruel": "DecreaseMaxHp",
    "savage": "IgnoreDefense",
    "stoneskin": "DamageIncreaseOnHpDecrease",
    "resist": "Resistance",
    "atk": "AttackPower",
    "hp": "Hp",
    "def": "Defense",
    "cr": "CriticalChance",
    "cd": "CriticalDamage",
    "acc": "Accuracy",
    "res": "Resistance",
}


def _set_name_to_id() -> dict[str, int]:
    """Friendly-name → set ID. Includes both internal codenames
    ("LifeDrain") and aliased UI names ("Lifesteal"). Case-insensitive."""
    by_internal = {v.lower(): k for k, v in _set_id_to_name().items()}
    out = dict(by_internal)
    for alias_lower, internal in _SET_ALIASES.items():
        sid = by_internal.get(internal.lower())
        if sid is not None:
            out[alias_lower] = sid
    return out


def _load_drops() -> dict:
    """Load drops.json regions map."""
    p = PROJECT_ROOT / "data" / "static" / "drops.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("regions", {})


def _all_sources() -> list[dict]:
    """Flatten drops into [(region, difficulty, set_ids, max_prob)] rows."""
    drops = _load_drops()
    set_name = _set_id_to_name()
    rows: list[dict] = []
    for region_name, info in drops.items():
        for diff_block in info.get("by_difficulty") or []:
            diff = diff_block.get("difficulty") or "Normal"
            energy = _ENERGY_COST.get(diff, 6)
            for set_id_str, sd in (diff_block.get("set_drops") or {}).items():
                sid = int(set_id_str)
                rows.append({
                    "region": region_name,
                    "difficulty": diff,
                    "set_id": sid,
                    "set_name": set_name.get(sid, f"set_{sid}"),
                    "max_prob": float(sd.get("max_prob") or 0),
                    "stages": int(sd.get("stages") or 0),
                    "energy_per_run": energy,
                })
    return rows


def _list_sources() -> int:
    rows = _all_sources()
    if not rows:
        print("(no drops data — run `python3 tools/refresh_static_data.py --section drops`)",
              file=sys.stderr)
        return 1
    rows.sort(key=lambda r: (r["region"], r["difficulty"], r["set_name"]))
    print(f"=== {len(rows)} (region × difficulty × set) drops ===\n")
    print(f"  {'region':<20s} {'diff':<10s} {'set':<25s} {'prob':>5s} {'stages':>6s} {'eng':>3s}")
    print(f"  {'-'*20} {'-'*10} {'-'*25} {'-'*5} {'-'*6} {'-'*3}")
    for r in rows:
        print(f"  {r['region']:<20s} {r['difficulty']:<10s} {r['set_name']:<25s} "
              f"{r['max_prob']:>5.2f} {r['stages']:>6d} {r['energy_per_run']:>3d}")
    return 0


def _pick_for_sets(needed_sets: list[str], max_energy: int | None = None) -> int:
    """Rank dungeons by coverage of the needed sets; print plan."""
    rows = _all_sources()
    if not rows:
        print("(no drops data)", file=sys.stderr)
        return 1
    name_to_id = _set_name_to_id()
    needed_ids: set[int] = set()
    needed_unmatched: list[str] = []
    for name in needed_sets:
        sid = name_to_id.get(name.lower())
        if sid is None:
            needed_unmatched.append(name)
        else:
            needed_ids.add(sid)
    if needed_unmatched:
        print(f"  [warn] sets not found in artifact_sets.json: {needed_unmatched}", file=sys.stderr)

    # Group rows by (region, difficulty), aggregate which needed sets land there.
    by_dungeon: dict[tuple[str, str], dict] = {}
    for r in rows:
        if r["set_id"] not in needed_ids:
            continue
        key = (r["region"], r["difficulty"])
        d = by_dungeon.setdefault(key, {
            "region": r["region"],
            "difficulty": r["difficulty"],
            "energy_per_run": r["energy_per_run"],
            "sets": [],
            "score": 0.0,
        })
        d["sets"].append(r["set_name"])
        d["score"] += r["max_prob"]
    if not by_dungeon:
        print(f"  ❌ none of the requested sets ({', '.join(needed_sets)}) drop in any indexed dungeon.")
        return 1

    # Sort by score per energy (efficiency).
    plan = list(by_dungeon.values())
    plan.sort(key=lambda d: (d["score"] / max(1, d["energy_per_run"])), reverse=True)

    # id_to_internal needs to use the canonical (un-aliased) names so
    # set membership checks against d["sets"] (which holds internal
    # names like "LifeDrain") work. Build it directly from the static
    # data rather than the merged alias dict.
    id_to_internal = _set_id_to_name()
    print(f"=== Farm plan: {len(needed_ids)} sets, {len(plan)} candidate dungeons ===\n")
    needed_names_sorted = sorted(id_to_internal.get(sid, str(sid)) for sid in needed_ids)
    print(f"  Needed sets: {', '.join(needed_names_sorted)}\n")
    print(f"  {'rank':<4s} {'region':<20s} {'diff':<10s} {'sets-dropped':<40s} {'score':>5s} {'eng':>3s} {'eff':>5s}")
    print(f"  {'-'*4} {'-'*20} {'-'*10} {'-'*40} {'-'*5} {'-'*3} {'-'*5}")
    for i, d in enumerate(plan):
        eff = d["score"] / max(1, d["energy_per_run"])
        sets_str = ", ".join(d["sets"][:5])
        if len(d["sets"]) > 5:
            sets_str += f" (+{len(d['sets'])-5})"
        print(f"  {i+1:<4d} {d['region']:<20s} {d['difficulty']:<10s} {sets_str:<40s} "
              f"{d['score']:>5.2f} {d['energy_per_run']:>3d} {eff:>5.2f}")

    # Greedy coverage: pick dungeons until all needed sets are reached.
    covered: set[str] = set()
    chosen: list[dict] = []
    energy_spent = 0
    for d in plan:
        new_sets = [s for s in d["sets"] if s not in covered]
        if not new_sets:
            continue
        chosen.append({**d, "new_sets": new_sets})
        covered.update(new_sets)
        if max_energy is not None:
            # Estimate runs to "expect" 1 of each new set: 1 / max_prob.
            # Using a conservative 10 runs per dungeon as a rough budget.
            energy_spent += d["energy_per_run"] * 10

    print(f"\n  Recommended (greedy coverage):")
    if not chosen:
        print(f"    (none — needed sets don't drop)")
    for c in chosen:
        print(f"    farm {c['region']} ({c['difficulty']}): {', '.join(c['new_sets'])}  "
              f"~{c['energy_per_run']*10}e per ~10 runs")
    if max_energy is not None:
        print(f"\n  Estimated total at ~10 runs/dungeon: {energy_spent}e (budget: {max_energy}e)")

    missing_ids = needed_ids - {sid for sid in needed_ids
                                 if any(id_to_internal.get(sid) in d["sets"] for d in chosen)}
    if missing_ids:
        missing_names = [id_to_internal.get(sid, str(sid)) for sid in sorted(missing_ids)]
        print(f"\n  Missing (no source found in indexed dungeons): {', '.join(missing_names)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", help="Target slug (data/targets/<slug>.json) — uses its preferred_sets.")
    ap.add_argument("--role", help="Role within the target (default: first).")
    ap.add_argument("--sets",
                    help="Comma-separated set names (e.g. 'Lifesteal,Speed').")
    ap.add_argument("--max-energy", type=int, default=None,
                    help="Optional energy budget (informational; the recommender's "
                         "10-runs/dungeon estimate is rough).")
    ap.add_argument("--list-sources", action="store_true",
                    help="Print every (region × difficulty × set) row.")
    args = ap.parse_args()

    if args.list_sources:
        return _list_sources()

    needed_sets: list[str] = []
    if args.target:
        from gear_targets import load_target, get_role
        try:
            t = load_target(args.target)
        except KeyError as e:
            print(f"ERR: {e}", file=sys.stderr)
            return 1
        role = get_role(t, args.role)
        needed_sets = list(role.get("preferred_sets") or [])
        if not needed_sets:
            print(f"ERR: target {args.target!r} role has no preferred_sets",
                  file=sys.stderr)
            return 1
    elif args.sets:
        needed_sets = [s.strip() for s in args.sets.split(",") if s.strip()]
    else:
        ap.error("--target or --sets required (or --list-sources)")

    return _pick_for_sets(needed_sets, max_energy=args.max_energy)


if __name__ == "__main__":
    sys.exit(main())
