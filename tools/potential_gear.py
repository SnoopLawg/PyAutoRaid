"""Per-tune gear plan computation for PotentialTeam.

Wraps `tools/global_gear_solver.solve_global_gear` so the dashboard can
get a serializable artifact plan per DWJ tune without paying for the
solver's stdout chatter or the full 5000-iter SA budget.

Caches results to `data/gear_plans_cache.json` keyed by tune_slug +
team-name tuple. Cache is invalidated by `vault_signature` (a hash of
the user's artifact ids), so re-solving runs whenever inventory shifts.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "gear_plans_cache.json"


def _vault_signature() -> str:
    """Hash of artifact ids — invalidates cache when inventory changes."""
    try:
        with open(ROOT / "all_artifacts.json") as f:
            data = json.load(f)
        ids = sorted(a.get("id", 0) for a in data.get("artifacts", []) if not a.get("error"))
        return hashlib.sha1(",".join(map(str, ids)).encode()).hexdigest()[:12]
    except Exception:
        return "no-vault"


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def _cache_key(slug: str, team_names: List[str]) -> str:
    return f"{slug}|{','.join(team_names)}"


def _serialize_plan(assignment, team_names: List[str], score: float,
                    sim_result: dict) -> dict:
    """Turn a GearAssignment into a JSON-serializable plan."""
    from cb_optimizer import HP, ATK, DEF, SPD, ACC, CR, CD, SET_NAMES
    from gear_constants import SLOT_NAMES

    plan_heroes = []
    for i, name in enumerate(team_names):
        stats = assignment.calc_hero_stats(i)
        slots = []
        sets_count: Dict[int, int] = {}
        for slot_id in assignment.SLOTS:
            art = assignment.assignment[i].get(slot_id)
            if not art:
                continue
            sets_count[art.get("set", 0)] = sets_count.get(art.get("set", 0), 0) + 1
            primary = art.get("primary") or {}
            slots.append({
                "slot": slot_id,
                "slot_name": SLOT_NAMES.get(slot_id, f"s{slot_id}"),
                "artifact_id": art.get("id"),
                "set_id": art.get("set", 0),
                "set_name": SET_NAMES.get(art.get("set", 0), "?"),
                "rank": art.get("rank", 0),
                "rarity": art.get("rarity", 0),
                "primary_stat": primary.get("stat"),
                "primary_value": primary.get("value"),
                "level": art.get("level", 0),
            })
        plan_heroes.append({
            "name": name,
            "projected_stats": {
                "HP": int(stats.get(HP, 0)),
                "ATK": int(stats.get(ATK, 0)),
                "DEF": int(stats.get(DEF, 0)),
                "SPD": int(stats.get(SPD, 0)),
                "ACC": int(stats.get(ACC, 0)),
                "CR": round(stats.get(CR, 0), 1),
                "CD": round(stats.get(CD, 0), 1),
            },
            "active_sets": [{"set_id": s, "set_name": SET_NAMES.get(s, "?"), "count": c}
                            for s, c in sorted(sets_count.items(), key=lambda x: -x[1]) if c > 0],
            "slots": slots,
        })

    return {
        "score": int(score),
        "total_damage": int(sim_result.get("total", 0) or 0),
        "boss_turns": int(sim_result.get("cb_turns", 0) or 0),
        "team": plan_heroes,
    }


def compute_gear_plan(team_names: List[str],
                      speed_ranges: Dict[str, Tuple[int, int]],
                      cache_key: Optional[str] = None,
                      cb_element: int = 4,
                      sa_iterations: int = 500,
                      force_affinity: bool = True) -> dict:
    """Run the global gear solver and return a serializable plan.

    `sa_iterations` defaults to 500 (vs the CLI tool's 5000) so the
    dashboard can fetch on demand without 30+ second waits. Cached
    results from `data/gear_plans_cache.json` are returned when the
    vault hasn't changed.
    """
    sig = _vault_signature()
    cache = _load_cache()
    if cache_key and cache.get(cache_key, {}).get("vault_signature") == sig:
        return cache[cache_key]["plan"]

    # Suppress the solver's stdout chatter (200+ print lines per call).
    buf = io.StringIO()
    from global_gear_solver import solve_global_gear
    with contextlib.redirect_stdout(buf):
        result = solve_global_gear(
            team_names, speed_ranges=speed_ranges, cb_element=cb_element,
            force_affinity=force_affinity, sa_iterations=sa_iterations,
            verbose=False,
        )
    if not result:
        return {"error": "solver returned None — likely a non-6★ hero in team"}
    assignment, score, sim_result = result
    plan = _serialize_plan(assignment, team_names, score, sim_result)

    if cache_key:
        cache[cache_key] = {"vault_signature": sig, "plan": plan}
        _save_cache(cache)
    return plan


def compute_gear_plan_for_tune(tune_slug: str, projection_team: List[dict],
                               sa_iterations: int = 500,
                               cb_element: int = 4) -> dict:
    """Convenience wrapper that takes a PotentialTeam's resolved team
    list (with target_speed per slot) and produces a gear plan."""
    team_names = [s.get("hero") for s in projection_team if s.get("hero")]
    speed_ranges = {}
    for s in projection_team:
        nm = s.get("hero")
        spd = s.get("target_speed")
        if nm and spd:
            # ±2 band around target speed.
            speed_ranges[nm] = (max(0, int(spd) - 2), int(spd) + 2)
    return compute_gear_plan(
        team_names, speed_ranges, cache_key=tune_slug,
        cb_element=cb_element, sa_iterations=sa_iterations,
    )
