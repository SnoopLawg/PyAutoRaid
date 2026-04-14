#!/usr/bin/env python3
"""
CB Hero Gap Analysis.

Two modes:
1. ROSTER ANALYSIS: Which owned heroes (not on current team) would most improve CB damage?
2. PULL ANALYSIS: Which unowned heroes from skills_db would be game-changers?

Uses auto-generated profiles from skills_db.json for all 343 heroes.

Usage:
    python3 tools/cb_gap_analysis.py                    # both analyses
    python3 tools/cb_gap_analysis.py --roster-only      # owned heroes only
    python3 tools/cb_gap_analysis.py --pull-only        # unowned heroes only
"""

import json
import sys
import time
import argparse
from pathlib import Path
from itertools import combinations

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from auto_profile import auto_generate_profiles, get_leader_skills
from cb_optimizer import HeroProfile, PROFILES as MANUAL_PROFILES

# Synthetic base stats for heroes not in roster (approximate legendary L60)
HYPOTHETICAL_BASE_STATS = {
    "HP": 100, "ATK": 100, "DEF": 90, "SPD": 100,
    "RES": 30, "ACC": 0, "CR": 15, "CD": 63,
}


def load_all_data():
    """Load heroes, skills, and generate profiles."""
    with open(PROJECT_ROOT / "heroes_all.json") as f:
        heroes_all = json.load(f)
    with open(PROJECT_ROOT / "skills_db.json") as f:
        skills_db = json.load(f)

    owned_names = set(h["name"] for h in heroes_all.get("heroes", []))
    owned_6star = set(h["name"] for h in heroes_all.get("heroes", []) if h.get("grade", 0) >= 6)

    # Auto-generate profiles for ALL heroes in skills_db
    auto_profiles = auto_generate_profiles()

    # Merge: manual profiles override auto where they exist
    merged_profiles = dict(auto_profiles)
    merged_profiles.update(MANUAL_PROFILES)

    # Heroes in skills_db but NOT owned
    skills_heroes = set(skills_db.keys())
    unowned = skills_heroes - owned_names

    # Leader skills
    leaders = get_leader_skills()

    return {
        "heroes_all": heroes_all,
        "skills_db": skills_db,
        "owned_names": owned_names,
        "owned_6star": owned_6star,
        "unowned": unowned,
        "profiles": merged_profiles,
        "auto_profiles": auto_profiles,
        "leaders": leaders,
    }


def find_current_best(data):
    """Find best team from current 6-star roster using quick sim."""
    from cb_potential import simulate_team

    profiles = data["profiles"]
    owned_6star = data["owned_6star"]

    # Only heroes with profiles
    profiled = [n for n in owned_6star if n in profiles]

    # Unkillable providers
    uk_heroes = [n for n in profiled if profiles[n].unkillable]
    dps_pool = [n for n in profiled if not profiles[n].unkillable]

    # Quick: just test ME + Demytha + 3 DPS combos (most likely best)
    best_score = 0
    best_team = None

    if "Maneater" in profiled and "Demytha" in profiled:
        dd_or_wk = [n for n in dps_pool if n not in ("Maneater", "Demytha") and
                    (profiles[n].def_down or profiles[n].weaken)]
        other_dps = [n for n in dps_pool if n not in ("Maneater", "Demytha")]

        for combo in combinations(other_dps, 3):
            has_dd_wk = any(profiles[n].def_down or profiles[n].weaken for n in combo)
            if not has_dd_wk:
                continue
            team = ["Maneater", "Demytha"] + list(combo)
            result = simulate_team(team, verbose=False)
            score = result.get("total", 0)
            if score > best_score:
                best_score = score
                best_team = team

    return best_team, best_score


def evaluate_hero_swap(data, base_team, base_score, candidate_name):
    """Evaluate swapping each DPS slot with the candidate hero."""
    from cb_potential import simulate_team
    import cb_potential

    profiles = data["profiles"]

    # Make sure the candidate has a profile
    if candidate_name not in profiles:
        return None, 0

    # Ensure candidate is in cb_potential's heroes_all (for build_potential_hero)
    hero_entry = None
    for h in data["heroes_all"].get("heroes", []):
        if h["name"] == candidate_name:
            hero_entry = h
            break

    # If unowned, inject a synthetic hero
    if not hero_entry:
        hero_entry = {
            "id": 99000 + abs(hash(candidate_name)) % 10000,
            "type_id": 99000 + abs(hash(candidate_name)) % 10000,
            "name": candidate_name,
            "grade": 6, "level": 60, "empower": 0,
            "fraction": 1, "rarity": 5, "element": 4, "role": 1,
            "base_stats": HYPOTHETICAL_BASE_STATS.copy(),
            "masteries": [500161, 500141, 500122],
            "artifacts": [],
        }
        # Inject into cb_potential's data
        cb_potential.heroes_all["heroes"].append(hero_entry)

    # Also inject the profile
    MANUAL_PROFILES[candidate_name] = profiles[candidate_name]

    best_score = 0
    best_team = None

    # Try swapping candidate into each non-UK DPS slot
    for slot_idx in range(2, len(base_team)):
        team = list(base_team)
        team[slot_idx] = candidate_name
        # Skip if duplicate
        if len(set(team)) < len(team):
            continue
        try:
            result = simulate_team(team, verbose=False)
            score = result.get("total", 0)
            if score > best_score:
                best_score = score
                best_team = team
        except Exception:
            continue

    # Also try the candidate in a fresh Myth Eater team
    dps_pool = [n for n in data["owned_6star"] if n in profiles and
                not profiles[n].unkillable and n not in ("Maneater", "Demytha")]
    if candidate_name not in dps_pool:
        dps_pool.append(candidate_name)

    # Try candidate + 2 best existing DPS
    for combo in combinations([n for n in dps_pool if n != candidate_name], 2):
        has_dd_wk = (profiles.get(candidate_name, HeroProfile("?")).def_down or
                     profiles.get(candidate_name, HeroProfile("?")).weaken or
                     any(profiles.get(n, HeroProfile("?")).def_down or
                         profiles.get(n, HeroProfile("?")).weaken for n in combo))
        if not has_dd_wk:
            continue
        team = ["Maneater", "Demytha", candidate_name] + list(combo)
        try:
            result = simulate_team(team, verbose=False)
            score = result.get("total", 0)
            if score > best_score:
                best_score = score
                best_team = team
        except Exception:
            continue

    delta = best_score - base_score
    return best_team, delta


def main():
    parser = argparse.ArgumentParser(description="CB Hero Gap Analysis")
    parser.add_argument("--roster-only", action="store_true", help="Only analyze owned heroes")
    parser.add_argument("--pull-only", action="store_true", help="Only analyze unowned heroes")
    parser.add_argument("--top", type=int, default=15, help="Show top N results")
    args = parser.parse_args()

    print("Loading data and generating profiles...")
    data = load_all_data()
    profiles = data["profiles"]
    leaders = data["leaders"]

    print(f"  Total profiled heroes: {len(profiles)}")
    print(f"  Owned (any grade): {len(data['owned_names'])}")
    print(f"  Owned (6-star): {len(data['owned_6star'])}")
    print(f"  Unowned in skills_db: {len(data['unowned'])}")

    print("\nFinding current best team...")
    t0 = time.time()
    base_team, base_score = find_current_best(data)
    print(f"  Best: {', '.join(base_team)} = {base_score/1e6:.1f}M ({time.time()-t0:.1f}s)")

    # =========================================================================
    # ROSTER ANALYSIS: owned 6-star heroes NOT on current team
    # =========================================================================
    if not args.pull_only:
        print(f"\n{'='*70}")
        print(f"ROSTER ANALYSIS: Owned 6-star heroes that could improve the team")
        print(f"{'='*70}")

        candidates = [n for n in data["owned_6star"]
                      if n in profiles and n not in base_team]
        print(f"Evaluating {len(candidates)} candidates...")

        roster_results = []
        for name in candidates:
            t0 = time.time()
            best_team, delta = evaluate_hero_swap(data, base_team, base_score, name)
            elapsed = time.time() - t0
            if best_team:
                p = profiles[name]
                ls = leaders.get(name)
                ls_str = ""
                if ls:
                    stat_names = {1:'HP', 2:'ATK', 3:'DEF', 4:'SPD', 5:'RES', 6:'ACC', 7:'CR', 8:'CD'}
                    sn = stat_names.get(ls['stat'], '?')
                    flat = '' if ls['absolute'] else '%'
                    ls_str = f" | Lead: +{ls['amount']}{flat} {sn}"

                roster_results.append({
                    "hero": name,
                    "delta": delta,
                    "best_team": best_team,
                    "notes": (p.notes or "") + ls_str,
                })

        roster_results.sort(key=lambda x: x["delta"], reverse=True)

        print(f"\n{'#':>3s} {'Hero':25s} {'Delta':>10s} {'Notes'}")
        print("-" * 90)
        for rank, r in enumerate(roster_results[:args.top], 1):
            team_str = ", ".join(r["best_team"])
            sign = "+" if r["delta"] >= 0 else ""
            print(f"{rank:>3d} {r['hero']:25s} {sign}{r['delta']/1e6:>8.1f}M  {r['notes']}")
            print(f"    Team: {team_str}")

    # =========================================================================
    # PULL ANALYSIS: unowned heroes from skills_db
    # =========================================================================
    if not args.roster_only:
        print(f"\n{'='*70}")
        print(f"PULL ANALYSIS: Unowned heroes that would be game-changers")
        print(f"{'='*70}")

        # Filter unowned heroes to CB-relevant ones
        unowned_candidates = []
        for name in data["unowned"]:
            p = profiles.get(name)
            if not p:
                continue
            is_relevant = (p.poisons_per_turn > 1.0 or p.hp_burn_uptime > 0.3 or
                           p.def_down or p.weaken or p.unkillable or
                           p.counterattack or p.ally_attack > 0)
            if is_relevant:
                unowned_candidates.append(name)

        print(f"CB-relevant unowned heroes: {len(unowned_candidates)}")
        for name in sorted(unowned_candidates):
            p = profiles[name]
            print(f"  {name:25s} {p.notes or 'N/A'}")

        if unowned_candidates:
            print(f"\nEvaluating {len(unowned_candidates)} candidates...")
            pull_results = []
            for name in unowned_candidates:
                t0 = time.time()
                best_team, delta = evaluate_hero_swap(data, base_team, base_score, name)
                elapsed = time.time() - t0
                if best_team:
                    p = profiles[name]
                    pull_results.append({
                        "hero": name,
                        "delta": delta,
                        "best_team": best_team,
                        "notes": p.notes or "",
                    })

            pull_results.sort(key=lambda x: x["delta"], reverse=True)

            print(f"\n{'#':>3s} {'Hero':25s} {'Delta':>10s} {'Notes'}")
            print("-" * 90)
            for rank, r in enumerate(pull_results[:args.top], 1):
                team_str = ", ".join(r["best_team"])
                sign = "+" if r["delta"] >= 0 else ""
                print(f"{rank:>3d} {r['hero']:25s} {sign}{r['delta']/1e6:>8.1f}M  {r['notes']}")
                print(f"    Team: {team_str}")


if __name__ == "__main__":
    main()
