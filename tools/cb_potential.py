"""
CB Full Potential Team Ranker — finds the best possible team assuming:
- Every hero 6★ L60, fully booked, full masteries (WM/GS + offense tree)
- Optimal gear from the full artifact pool
- Speed-tuned for Budget Unkillable

Uses the turn-by-turn simulator (cb_sim.py) for game-accurate damage.

Usage:
    python3 tools/cb_potential.py                    # rank all teams
    python3 tools/cb_potential.py --team "ME,ME,Venus,OB,Geo"  # test specific team
"""
import json
import sys
from pathlib import Path
from copy import deepcopy
from itertools import combinations
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))

from cb_sim import (CBSimulator, build_sim_champion, SimChampion, SimSkill,
                    SKILL_DATA, SKILL_EFFECTS, MASTERY_IDS,
                    HP, ATK, DEF, SPD, ACC, CR, CD,
                    _eff, TM_THRESHOLD)
from cb_optimizer import (calc_stats, PROFILES, optimal_artifacts_for_hero,
                          UK_ME_SPD_RANGE, EMPOWERMENT_BONUSES,
                          L60_HP_MULT, L60_AD_MULT)
from raid_data import UNM_DEF


# =============================================================================
# Load game data
# =============================================================================
base = Path(__file__).parent.parent

with open(base / "heroes_all.json") as f:
    heroes_all = json.load(f)
with open(base / "all_artifacts.json") as f:
    artifacts_data = json.load(f)
with open(base / "account_data.json") as f:
    account = json.load(f)
with open(base / "skills_db.json") as f:
    skills_db = json.load(f)

all_arts = [a for a in artifacts_data.get("artifacts", []) if not a.get("error")]


# =============================================================================
# Build "potential" hero — 6★ L60, fully booked, full masteries
# =============================================================================
def get_booked_cd(skills_list):
    """Extract booked cooldowns from skill data."""
    best = {}
    for sk in skills_list:
        tid = sk.get("skill_type_id", 0)
        lvl = sk.get("level", 0)
        if tid not in best or lvl > best[tid].get("level", 0):
            best[tid] = sk

    cds = {}
    for tid, sk in sorted(best.items()):
        cd = sk.get("cooldown", 0)
        if cd > 0:
            bonuses = sk.get("level_bonuses", [])
            cd_reductions = sum(1 for b in bonuses if b.get("type") == 3)
            booked_cd = cd - cd_reductions
            is_a1 = sk.get("is_a1", False)
            if is_a1:
                cds["A1"] = booked_cd
            elif "A2" not in cds:
                cds["A2"] = booked_cd
            else:
                cds["A3"] = booked_cd
    return cds


# Estimated ascension bonuses per star (from comparing 5★ vs 6★ game data)
# Format: {rarity: {stat: bonus_per_missing_star}}
ASCENSION_BONUSES_PER_STAR = {
    3: {"HP": 3, "ATK": 3, "DEF": 3, "SPD": 1},       # Rare
    4: {"HP": 3, "ATK": 3, "DEF": 2, "SPD": 1},       # Epic
    5: {"HP": 2, "ATK": 3, "DEF": 2, "SPD": 2, "CD": 5, "RES": 5, "ACC": 5},  # Legendary
}


def build_potential_hero(name: str) -> dict:
    """Create a synthetic 6★ fully built hero entry.
    Adds estimated ascension stat bonuses for heroes below 6★."""
    # Find best version in roster
    best = None
    for h in heroes_all["heroes"]:
        if h.get("name") == name:
            if best is None or h.get("grade", 0) > best.get("grade", 0):
                best = h
    if not best:
        return None

    hero = dict(best)
    current_grade = hero.get("grade", 1)

    # Add ascension bonuses for missing stars
    if current_grade < 6:
        rarity = hero.get("rarity", 3)
        bonuses = ASCENSION_BONUSES_PER_STAR.get(rarity, ASCENSION_BONUSES_PER_STAR[3])
        missing_stars = 6 - current_grade
        base = dict(hero.get("base_stats", {}))
        for stat, per_star in bonuses.items():
            base[stat] = base.get(stat, 0) + per_star * missing_stars
        hero["base_stats"] = base

    hero["grade"] = 6
    hero["level"] = 60
    # Preserve REAL empowerment level from live hero data — Epic emp3 adds +5 SPD,
    # Legendary emp3 adds +10 SPD, etc. This matters for Myth-Eater tune targeting.
    hero["empower"] = best.get("empower", 0)
    hero["mastery_count"] = 15
    # Preserve REAL masteries if the hero has them (including Lore of Steel 500343 which
    # amplifies set bonuses by 15% — confirmed impact on in-game SPD). Fall back to a
    # minimal "optimal" mastery set only if the hero has no masteries configured.
    real_masteries = best.get("masteries") or []
    if real_masteries:
        hero["masteries"] = list(real_masteries)
    else:
        hero["masteries"] = [
            MASTERY_IDS["warmaster"],
            MASTERY_IDS["bring_it_down"],
            MASTERY_IDS["keen_strike"],
        ]
    hero["artifacts"] = []  # will be assigned by optimizer
    return hero


# =============================================================================
# Updated SKILL_DATA with booked CDs from game
# =============================================================================
def build_booked_skill_data():
    """Generate SKILL_DATA with booked cooldowns from skills_db."""
    data = dict(SKILL_DATA)  # start with existing

    for name, skills in skills_db.items():
        if name not in PROFILES and name not in SKILL_DATA:
            continue

        booked_cds = get_booked_cd(skills)

        if name in data:
            for label, cd in booked_cds.items():
                if label in data[name]:
                    data[name][label]["cd"] = cd
        # For heroes in SKILL_DATA, update their CDs
    return data


BOOKED_SKILL_DATA = build_booked_skill_data()


# =============================================================================
# Stun target selection
# =============================================================================
def stun_priority(p):
    """Lower = better stun target (less impactful when slowed)."""
    if not p:
        return 0
    score = 0
    if p.def_down or p.weaken:
        score += 10
    if p.poisons_per_turn > 1:
        score += 5
    if p.hp_burn_uptime > 0:
        score += 3
    if p.needs_acc:
        score += 2
    return score


# =============================================================================
# Run a single team through the sim
# =============================================================================
def simulate_team(team_names: list, verbose: bool = False) -> dict:
    """Simulate a team with full potential (6★, booked, mastered, optimal gear)."""
    # Build heroes
    team_h = []
    team_p = []
    me_count = 0
    hero_cache = {}

    for tname in team_names:
        if tname == "Maneater":
            me_count += 1

        if tname not in hero_cache:
            h = build_potential_hero(tname)
            if h is None:
                return {"error": f"Hero not found: {tname}", "total": 0}
            hero_cache[tname] = h

        # Use a copy so artifacts don't conflict
        h = dict(hero_cache[tname])
        if tname == "Maneater" and me_count > 1:
            h = dict(h)
            h["id"] = h["id"] + 100000  # unique ID for 2nd ME
        team_h.append(h)

        p = PROFILES.get(tname)
        if not p:
            return {"error": f"No profile for: {tname}", "total": 0}
        team_p.append(p)

    # Assign optimal gear
    has_uk = sum(1 for p in team_p if p.unkillable) >= 2
    dps_idx = [i for i, p in enumerate(team_p) if not p.unkillable]
    stun_idx = min(dps_idx, key=lambda i: stun_priority(team_p[i])) if dps_idx else -1

    used = set()
    assigned = [[] for _ in range(5)]
    priority = sorted(range(5), key=lambda i: (
        0 if team_p[i].unkillable else
        (3 if i == stun_idx else (1 if team_p[i].needs_acc else 2))
    ))
    for pi in priority:
        avail = [a for a in all_arts if a.get("id") not in used and a.get("rank", 0) >= 5]
        spd_max = UK_ME_SPD_RANGE[1] if (has_uk and team_p[pi].unkillable) else None
        is_stun = has_uk and pi == stun_idx
        arts, _ = optimal_artifacts_for_hero(
            team_h[pi], team_p[pi], avail, account,
            spd_max=spd_max, is_stun_target=is_stun)
        assigned[pi] = arts
        for a in arts:
            used.add(a.get("id"))

    # Build SimChampions with speed overrides
    sim_champs = []
    me_idx = 0
    for i, tname in enumerate(team_names):
        stats = calc_stats(team_h[i], assigned[i], account)
        opening = []
        if tname == "Maneater":
            me_idx += 1
            opening = ["A3"] if me_idx == 1 else ["A1", "A3"]
            if has_uk:
                stats[SPD] = 228 if me_idx == 1 else 215
        elif has_uk and i == stun_idx:
            stats[SPD] = min(stats[SPD], 118)
        elif has_uk:
            stats[SPD] = max(171, min(stats[SPD], 189))

        hero_element = team_h[i].get("element", 4)
        champ = build_sim_champion(
            tname, stats, i + 1,
            masteries=team_h[i].get("masteries", []),
            opening=opening,
            element=hero_element)
        sim_champs.append(champ)

    # Run simulation — model_survival=True so UK heroes survive gaps with HP
    has_uk = sum(1 for p in team_p if p and p.unkillable) >= 2
    max_turns = 50 if has_uk else 0  # UK: 50 turn cap, non-UK: run until all dead

    # Default to Void CB (best case). Use cb_element param to test specific affinities.
    cb_element = 4  # Void
    sim = CBSimulator(deepcopy(sim_champs), deterministic=True, verbose=verbose,
                      model_survival=True, cb_element=cb_element)
    result = sim.run(max_cb_turns=max_turns)

    stun_name = team_names[stun_idx] if stun_idx >= 0 else "?"
    result["stun_target"] = stun_name
    result["team_names"] = team_names
    result["stats"] = [{SPD: c.speed, ACC: c.stats.get(ACC, 0),
                         ATK: c.stats.get(ATK, 0), DEF: c.stats.get(DEF, 0)}
                        for c in sim_champs]
    return result


# =============================================================================
# Main
# =============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="CB Full Potential Ranker")
    parser.add_argument("--team", help="Comma-separated team (e.g. ME,ME,Venus,OB,Geo)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--top", type=int, default=15, help="Show top N teams")
    args = parser.parse_args()

    if args.team:
        names = [n.strip() for n in args.team.split(",")]
        names = ["Maneater" if n == "ME" else n for n in names]
        result = simulate_team(names, verbose=args.verbose)
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        print(f"\n{'='*70}")
        print(f"TEAM: {', '.join(names)}  (stun={result['stun_target']})")
        print(f"TOTAL: {result['total']/1e6:.1f}M over {result['cb_turns']} CB turns")
        gaps = len(result["errors"])
        print(f"Tune: {'VALID' if result['valid'] else f'INVALID ({gaps} gaps)'}")
        print(f"{'='*70}")
        for hd in result["heroes"]:
            parts = []
            for key, lbl in [("direct", "Dir"), ("poison", "Poi"), ("hp_burn", "Burn"),
                              ("wm_gs", "WM"), ("passive", "Pass")]:
                v = hd.get(key, 0)
                if v > 0:
                    parts.append(f"{lbl}:{v/1e6:.1f}M")
            print(f"  {hd['name']:25s} {hd['total']/1e6:6.1f}M  {hd['turns']:>3}T  [{', '.join(parts)}]")
        if args.verbose:
            for line in result.get("log", [])[:100]:
                print(line)
        return

    # Rank all teams
    print(f"=== CB Full Potential Ranker ===")
    print(f"All heroes assumed 6★ L60, fully booked, full masteries, optimal gear\n")

    # Get all profiled heroes that exist in roster
    # NOTE: TM breakers (Ninja, Ma'Shalled, etc.) are included — DWJ tunes
    # like Myth Eater specifically handle their TM manipulation at correct ratios.
    # The sim assumes correct speed tuning for all teams.
    available = []
    for name, prof in PROFILES.items():
        # Check if hero exists in roster (any grade)
        exists = any(h.get("name") == name for h in heroes_all["heroes"])
        if exists or name in ["Maneater"]:  # always include ME
            available.append((name, prof))

    print(f"Available heroes: {len(available)} (including TM manipulators)")
    print(f"Heroes: {', '.join(n for n, _ in available)}\n")

    # Must have 2x Maneater + 3 DPS
    me_count = sum(1 for n, _ in available if n == "Maneater")
    dps_heroes = [(n, p) for n, p in available if not p.unkillable]

    print(f"DPS candidates: {len(dps_heroes)}")
    combos = list(combinations(range(len(dps_heroes)), 3))
    print(f"3-DPS combinations: {len(combos)}")
    print(f"Simulating...\n")

    results = []
    for ci, combo in enumerate(combos):
        team_names = ["Maneater", "Maneater"]
        team_names += [dps_heroes[i][0] for i in combo]

        result = simulate_team(team_names)
        if "error" in result:
            continue
        results.append((result["total"], team_names, result))

        if (ci + 1) % 50 == 0:
            print(f"  {ci+1}/{len(combos)} evaluated...", end="\r")

    results.sort(key=lambda x: -x[0])

    print(f"\nTOP {args.top} TEAMS (Full Potential, Turn-by-Turn Sim)")
    print(f"{'Rank':<5} {'Damage':>8} {'Team':55s} {'Stun':>15} {'Gaps':>5}")
    print("-" * 90)
    for rank, (dmg, names, res) in enumerate(results[:args.top]):
        dps_names = ", ".join(n for n in names if n != "Maneater")
        gaps = len(res["errors"])
        stun = res.get("stun_target", "?")
        print(f"#{rank+1:<4} {dmg/1e6:7.1f}M  ME+ME+{dps_names:45s} {stun:>15} {gaps:>5}")

    # Detailed top 3
    for rank, (dmg, names, res) in enumerate(results[:3]):
        print(f"\n{'='*70}")
        print(f"#{rank+1} ME+ME+{'+'.join(n for n in names if n!='Maneater')}: {dmg/1e6:.1f}M  (stun={res.get('stun_target')})")
        for hd in res["heroes"]:
            parts = []
            for key, lbl in [("direct", "Dir"), ("poison", "Poi"), ("hp_burn", "Burn"),
                              ("wm_gs", "WM"), ("passive", "Pass")]:
                v = hd.get(key, 0)
                if v > 0:
                    parts.append(f"{lbl}:{v/1e6:.1f}M")
            print(f"  {hd['name']:25s} {hd['total']/1e6:6.1f}M  {hd['turns']:>3}T  [{', '.join(parts)}]")


if __name__ == "__main__":
    main()
