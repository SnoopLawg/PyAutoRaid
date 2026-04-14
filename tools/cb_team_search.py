#!/usr/bin/env python3
"""
Exhaustive CB Team Search.

Enumerates all viable 5-hero teams from the roster, evaluates them via the CB sim,
and ranks by total damage. Two-tier approach:
  Tier 1: Quick score with potential gear (~100ms/team) — evaluate all combos
  Tier 2: Full global gear optimization (~60s/team) — top 20 teams only

Usage:
    python3 tools/cb_team_search.py
    python3 tools/cb_team_search.py --top 30
    python3 tools/cb_team_search.py --tier2
"""

import json
import sys
import time
import argparse
from pathlib import Path
from itertools import combinations
from multiprocessing import Pool, cpu_count

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))


# =============================================================================
# Load data
# =============================================================================
def load_data():
    with open(PROJECT_ROOT / "heroes_all.json") as f:
        heroes_all = json.load(f)
    with open(PROJECT_ROOT / "skills_db.json") as f:
        skills_db = json.load(f)

    from cb_optimizer import PROFILES

    # Build 6-star hero list with profiles
    six_star = {}
    for h in heroes_all.get("heroes", []):
        if h.get("grade", 0) >= 6:
            name = h.get("name", "")
            if name and name not in six_star:
                six_star[name] = h
            elif name == "Maneater":
                six_star["Maneater_2"] = h

    return six_star, PROFILES, skills_db


# =============================================================================
# Role detection
# =============================================================================
def classify_heroes(six_star, profiles, skills_db):
    """Classify heroes by CB role."""
    roles = {
        "unkillable": [],   # Can place UK
        "def_down": [],     # Can place DEF Down 60%
        "weaken": [],       # Can place Weaken 25%
        "dec_atk": [],      # Can place Decrease ATK
        "poison": [],       # Places poisons
        "hp_burn": [],      # Places HP Burn
        "counterattack": [],
        "ally_attack": [],
        "dps": [],          # Generic DPS
    }

    for name, prof in profiles.items():
        if name not in six_star:
            continue
        if prof.unkillable:
            roles["unkillable"].append(name)
        if prof.def_down:
            roles["def_down"].append(name)
        if prof.weaken:
            roles["weaken"].append(name)
        if prof.dec_atk:
            roles["dec_atk"].append(name)
        if prof.poisons_per_turn > 0:
            roles["poison"].append(name)
        if prof.hp_burn_uptime > 0:
            roles["hp_burn"].append(name)
        if prof.counterattack:
            roles["counterattack"].append(name)
        if prof.ally_attack > 0:
            roles["ally_attack"].append(name)
        roles["dps"].append(name)

    return roles


# =============================================================================
# Team generation
# =============================================================================
def generate_teams(six_star, profiles, roles):
    """Generate viable 5-hero teams with role requirements."""
    uk_heroes = set(roles["unkillable"])
    dd_heroes = set(roles["def_down"])
    wk_heroes = set(roles["weaken"])

    # All profiled 6-star heroes
    all_profiled = [name for name in six_star if name in profiles]

    teams = []
    seen = set()

    # Template 1: ME + Demytha + 3 DPS (Myth Eater)
    if "Maneater" in six_star and "Demytha" in six_star:
        dps_pool = [n for n in all_profiled if n not in ("Maneater", "Demytha", "Maneater_2")]
        for combo in combinations(dps_pool, 3):
            team = ["Maneater", "Demytha"] + list(combo)
            team_set = frozenset(team)
            if team_set in seen:
                continue

            # Check roles: need at least DEF Down or Weaken in the DPS
            has_dd = any(n in dd_heroes for n in combo)
            has_wk = any(n in wk_heroes for n in combo)

            # Relax: at least one of DEF Down or Weaken
            if not has_dd and not has_wk:
                continue

            # Check for TM breakers (heroes that mess up speed tunes)
            tm_breakers = sum(1 for n in combo if profiles.get(n) and
                            getattr(profiles.get(n), 'breaks_speed_tune', False))
            if tm_breakers > 1:
                continue

            seen.add(team_set)
            teams.append(team)

    # Template 2: 2x Maneater + 3 DPS (Budget Unkillable)
    if "Maneater" in six_star and "Maneater_2" in six_star:
        dps_pool = [n for n in all_profiled if n not in ("Maneater", "Maneater_2")]
        for combo in combinations(dps_pool, 3):
            team = ["Maneater", "Maneater_2"] + list(combo)
            team_set = frozenset(team)
            if team_set in seen:
                continue

            has_dd = any(n in dd_heroes for n in combo)
            has_wk = any(n in wk_heroes for n in combo)
            if not has_dd and not has_wk:
                continue

            seen.add(team_set)
            teams.append(team)

    return teams


# =============================================================================
# Tier 1: Quick scoring via simulate_team
# =============================================================================
def score_team_quick(team_names):
    """Score a team using potential gear (quick ~100ms). Returns (team, score, result)."""
    try:
        from cb_potential import simulate_team
        result = simulate_team(team_names, verbose=False)
        if "error" in result:
            return (team_names, 0, result)
        return (team_names, result.get("total", 0), result)
    except Exception as e:
        return (team_names, 0, {"error": str(e)})


def _score_worker(team_names):
    """Multiprocessing worker."""
    return score_team_quick(team_names)


# =============================================================================
# Main search
# =============================================================================
def search(top_n=20, run_tier2=False, verbose=False):
    print("Loading data...")
    six_star, profiles, skills_db = load_data()
    roles = classify_heroes(six_star, profiles, skills_db)

    print(f"\n6-star heroes with CB profiles: {len([n for n in six_star if n in profiles])}")
    print(f"Unkillable: {roles['unkillable']}")
    print(f"DEF Down:   {roles['def_down']}")
    print(f"Weaken:     {roles['weaken']}")
    print(f"Poison:     {roles['poison']}")
    print(f"HP Burn:    {roles['hp_burn']}")

    print("\nGenerating teams...")
    teams = generate_teams(six_star, profiles, roles)
    print(f"  Viable teams: {len(teams)}")

    if not teams:
        print("No viable teams found!")
        return

    # Tier 1: Quick scoring
    print(f"\n{'='*70}")
    print(f"TIER 1: Quick scoring ({len(teams)} teams)")
    print(f"{'='*70}")

    t_start = time.time()

    # Use multiprocessing for speed
    n_workers = min(cpu_count(), 6)
    print(f"Using {n_workers} workers...")

    results = []
    # Process in batches to show progress
    batch_size = 50
    for batch_start in range(0, len(teams), batch_size):
        batch = teams[batch_start:batch_start + batch_size]
        with Pool(n_workers) as pool:
            batch_results = pool.map(_score_worker, batch)
        results.extend(batch_results)
        elapsed = time.time() - t_start
        print(f"  {len(results)}/{len(teams)} teams scored ({elapsed:.1f}s)")

    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)

    elapsed = time.time() - t_start
    print(f"\nTier 1 complete: {len(results)} teams in {elapsed:.1f}s")

    # Show top results
    print(f"\n--- Top {top_n} Teams (Tier 1) ---")
    print(f"{'#':>3s} {'Team':60s} {'Damage':>12s} {'Valid':>5s}")
    print("-" * 85)
    for rank, (team, score, result) in enumerate(results[:top_n], 1):
        team_str = ", ".join(team)
        valid = "Y" if result.get("valid", False) else "N"
        err = result.get("error", "")
        if err:
            print(f"{rank:>3d} {team_str:60s} {'ERROR':>12s}  {err[:30]}")
        else:
            print(f"{rank:>3d} {team_str:60s} {score/1e6:>10.1f}M  {valid:>5s}")

    # Hero frequency in top teams
    from collections import Counter
    hero_freq = Counter()
    for team, score, _ in results[:top_n]:
        for name in team:
            hero_freq[name] += 1
    print(f"\n--- Hero Frequency (Top {top_n}) ---")
    for name, count in hero_freq.most_common(15):
        bar = "#" * count
        print(f"  {name:20s} {count:>3d} {bar}")

    # Tier 2: Full gear optimization (optional)
    if run_tier2:
        print(f"\n{'='*70}")
        print(f"TIER 2: Full gear optimization (top {min(top_n, 10)} teams)")
        print(f"{'='*70}")

        from global_gear_solver import solve_global_gear

        tier2_results = []
        for rank, (team, t1_score, _) in enumerate(results[:min(top_n, 10)], 1):
            print(f"\n--- Team #{rank}: {', '.join(team)} ---")
            try:
                assignment, score, result = solve_global_gear(
                    team, sa_iterations=3000, cb_element=2,
                    force_affinity=True, verbose=False)
                tier2_results.append((team, score, result))
                print(f"  Tier 1: {t1_score/1e6:.1f}M -> Tier 2: {score/1e6:.1f}M")
            except Exception as e:
                print(f"  ERROR: {e}")
                tier2_results.append((team, t1_score, {}))

        tier2_results.sort(key=lambda x: x[1], reverse=True)
        print(f"\n--- Final Rankings (Tier 2) ---")
        print(f"{'#':>3s} {'Team':60s} {'Damage':>12s}")
        print("-" * 80)
        for rank, (team, score, _) in enumerate(tier2_results, 1):
            team_str = ", ".join(team)
            print(f"{rank:>3d} {team_str:60s} {score/1e6:>10.1f}M")

    return results


def main():
    parser = argparse.ArgumentParser(description="Exhaustive CB Team Search")
    parser.add_argument("--top", type=int, default=20, help="Show top N teams (default: 20)")
    parser.add_argument("--tier2", action="store_true", help="Run Tier 2 gear optimization on top teams")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    search(top_n=args.top, run_tier2=args.tier2, verbose=args.verbose)


if __name__ == "__main__":
    main()
