"""Phase 6 — gear-target evaluator + suggestion CLI.

Bridges the new per-location target presets (`data/targets/*.json`,
loaded via `gear_targets.py`) with the user's current gear state. For
the named hero, fetches stats from the live mod, runs them through
the target's stat_floors / stat_caps, and reports which thresholds
are missed.

Usage:
    python3 tools/gear_solve.py --list-targets
    python3 tools/gear_solve.py --hero "Cardiel" --location cb-unm
    python3 tools/gear_solve.py --hero "Maneater" --location cb-unm --role unkillable

Output: a verdict (PASS / FAIL with delta list). When the hero fails,
the output also enumerates which substats from the user's vault could
plug each gap — a starting point for the swap planner. Full
auto-optimization stays in `tools/global_gear_solver.py` for CB; this
CLI surfaces the target schema's intent for any location.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from gear_targets import (TARGETS_DIR, evaluate_gear, list_targets,
                          load_target, get_role)


_STAT_ID_TO_KEY = {1: "HP", 2: "ATK", 3: "DEF", 4: "SPD",
                   5: "RES", 6: "ACC", 7: "CR", 8: "CD"}


def _vault_substat_inventory(target_stat: str, min_value: float = 0) -> list[dict]:
    """Scan all_artifacts.json for unequipped artifacts that roll the
    target stat as a substat at >= min_value. Returns a sorted list
    (highest substat value first)."""
    p = PROJECT_ROOT / "all_artifacts.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    arts = raw.get("artifacts") or []
    out = []
    for a in arts:
        if a.get("hero_id"):
            continue  # equipped
        for ss in (a.get("substats") or []):
            stat_key = _STAT_ID_TO_KEY.get(ss.get("stat"))
            if stat_key != target_stat:
                continue
            v = float(ss.get("value", 0) or 0) + float(ss.get("glyph", 0) or 0)
            if v < min_value:
                continue
            out.append({
                "artifact_id": a.get("id"),
                "kind": a.get("kind"),
                "rank": a.get("rank"),
                "rarity": a.get("rarity"),
                "set": a.get("set"),
                "primary": a.get("primary"),
                "substat_value": v,
                "substat_flat": ss.get("flat"),
            })
    out.sort(key=lambda x: x["substat_value"], reverse=True)
    return out


def _print_target_summary(slug: str) -> None:
    target = load_target(slug)
    print(f"=== {target.get('label', slug)} ({slug}) ===")
    for role_name, role_cfg in (target.get("role_targets") or {}).items():
        print(f"\n  role: {role_name}")
        if role_cfg.get("stat_floors"):
            floors = role_cfg["stat_floors"]
            print(f"    floors: {floors}")
        if role_cfg.get("stat_caps"):
            print(f"    caps: {role_cfg['stat_caps']}")
        if role_cfg.get("preferred_sets"):
            print(f"    preferred sets: {', '.join(role_cfg['preferred_sets'])}")
        if role_cfg.get("notes"):
            print(f"    notes: {role_cfg['notes']}")


def _run_evaluation(hero_name: str, slug: str, role: str | None) -> int:
    """Fetch live hero stats, evaluate against target, report verdict."""
    from cli_util import fetch_heroes_from_mod
    from hero_stats import compute_hero_actual_stats, find_hero, fetch_computed_from_mod

    heroes = fetch_heroes_from_mod()
    if not heroes:
        print("ERR: mod not reachable at http://localhost:6790", file=sys.stderr)
        return 2
    hero = find_hero(heroes, hero_name)
    if not hero:
        print(f"ERR: no hero matching {hero_name!r}", file=sys.stderr)
        return 1

    # Use the mod's computed stats when available — these are the
    # exact-match values from Phase 1. Fall back to our calc if not.
    mod_computed = fetch_computed_from_mod().get(hero["id"])
    stats = compute_hero_actual_stats(
        hero,
        base_computed=(mod_computed or {}).get("base_computed"),
        mod_bonuses=mod_computed,
    )
    # Inject base HP/ATK/DEF/SPD for "_pct_of_base" floor evaluation.
    if mod_computed and mod_computed.get("base_computed"):
        bc = mod_computed["base_computed"]
        for k in ("HP", "ATK", "DEF", "SPD"):
            stats[f"base_{k}"] = bc.get(k, 0)

    try:
        target = load_target(slug)
    except KeyError as e:
        print(f"ERR: {e}", file=sys.stderr)
        print(f"Available: {', '.join(list_targets())}", file=sys.stderr)
        return 1

    verdict = evaluate_gear(stats, target, role=role)

    label = target.get("label", slug)
    print(f"=== {hero.get('name')} vs {label} (role={verdict['role']}) ===\n")
    print(f"  Current stats: HP={stats.get('HP')} ATK={stats.get('ATK')} "
          f"DEF={stats.get('DEF')} SPD={stats.get('SPD')} "
          f"RES={stats.get('RES')} ACC={stats.get('ACC')} "
          f"CR={stats.get('CR')}% CD={stats.get('CD')}%")

    if verdict["passes"]:
        print(f"\n  ✅ PASSES all stat floors.")
        if verdict["headroom"]:
            print(f"\n  Cap headroom (over by):")
            for h in verdict["headroom"]:
                print(f"    {h['stat']:5s}  +{h['delta']:>5d}  (have {h['have']}, cap {h['cap']})")
        return 0

    print(f"\n  ❌ {len(verdict['violations'])} floor violation(s):")
    for v in verdict["violations"]:
        rule = v.get("rule", "")
        print(f"    {v['stat']:5s}  have {v['have']:>6}  need {v['need_floor']:>6}  "
              f"Δ {v['delta']:>+6}  {rule}")

    # For each missed stat, scan vault for substat rolls that could plug
    # the gap. Helps the user see "which artifacts in storage matter
    # for this fight" without running the full optimizer.
    print(f"\n  Vault substat candidates (top 5 per missed stat):")
    for v in verdict["violations"]:
        stat = v["stat"]
        gap = -v["delta"]  # positive number = how much we need
        candidates = _vault_substat_inventory(stat, min_value=1)
        print(f"\n    {stat} (need +{gap}):")
        if not candidates:
            print(f"      (no unequipped artifacts roll {stat})")
            continue
        for c in candidates[:5]:
            sf = "flat" if c["substat_flat"] else "%"
            print(f"      art#{c['artifact_id']:>5}  rank {c['rank']}{c['rarity'] and 'r'+str(c['rarity']) or ''}  "
                  f"slot {c['kind']}  set {c['set']}  +{c['substat_value']:.0f}{sf}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Per-location gear evaluator — reads target presets "
                    "from data/targets/, checks current hero against floors.")
    ap.add_argument("--list-targets", action="store_true",
                    help="Print all available target slugs and exit.")
    ap.add_argument("--show", help="Print a target preset's roles + thresholds.")
    ap.add_argument("--hero", help="Hero name (case-insensitive substring).")
    ap.add_argument("--location", "-l",
                    help="Target slug (e.g. cb-unm, dragon-25). See --list-targets.")
    ap.add_argument("--role",
                    help="Which role inside the target to check against. "
                         "Default: first role in the file.")
    args = ap.parse_args()

    if args.list_targets:
        slugs = list_targets()
        if not slugs:
            print(f"(no targets found in {TARGETS_DIR})", file=sys.stderr)
            return 1
        print(f"=== {len(slugs)} gear targets ===")
        for s in slugs:
            t = load_target(s)
            roles = list((t.get("role_targets") or {}).keys())
            print(f"  {s:<20s}  {t.get('label', '?')}  [roles: {', '.join(roles)}]")
        return 0

    if args.show:
        try:
            _print_target_summary(args.show)
        except KeyError as e:
            print(f"ERR: {e}", file=sys.stderr)
            return 1
        return 0

    if not args.hero or not args.location:
        ap.error("--hero and --location are required (or pass --list-targets / --show <slug>)")

    return _run_evaluation(args.hero, args.location, args.role)


if __name__ == "__main__":
    sys.exit(main())
