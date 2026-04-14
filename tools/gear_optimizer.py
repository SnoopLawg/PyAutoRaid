"""
Constraint-Based Gear Optimizer for CB Teams

Instead of greedy per-slot scoring, this optimizer:
1. Enforces hard speed constraints (ME: 212-229, DPS: 171-189, stun: ≤118)
2. Enforces ACC floor (250+ for debuffers/poisoners)
3. Runs the turn-by-turn sim to score each gear assignment
4. Uses iterative improvement (swap pieces between heroes to find better combos)

Usage:
    python3 tools/gear_optimizer.py --team "ME,ME,Venus,OB,Geo"
"""
import json
import sys
import random
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent))

from cb_optimizer import (calc_stats, PROFILES, optimal_artifacts_for_hero,
                          UK_ME_SPD_RANGE, HP, ATK, DEF, SPD, ACC, CR, CD,
                          MASTERY_IDS, SET_BONUSES)
from cb_sim import CBSimulator, build_sim_champion
from cb_potential import build_potential_hero, stun_priority, simulate_team

base = Path(__file__).parent.parent

# Auto-refresh data from live mod if requested or if stale (>30 min).
# Can be skipped with PYAUTORAID_NO_REFRESH=1 env var.
import os, time, subprocess
def _maybe_refresh():
    if os.environ.get("PYAUTORAID_NO_REFRESH"):
        return
    paths = [base / "heroes_all.json", base / "all_artifacts.json", base / "heroes_6star.json"]
    # refresh if any file missing or older than 30 min
    now = time.time()
    stale = not all(p.exists() for p in paths)
    if not stale:
        stale = any((now - p.stat().st_mtime) > 1800 for p in paths)
    if stale:
        print("Data stale — refreshing from live mod...", file=sys.stderr)
        try:
            subprocess.run([sys.executable, str(base / "tools" / "refresh_data.py")],
                           check=True, timeout=300)
        except Exception as ex:
            print(f"  refresh failed ({ex}), using cached data", file=sys.stderr)

_maybe_refresh()

with open(base / "all_artifacts.json") as f:
    artifacts_data = json.load(f)
with open(base / "account_data.json") as f:
    account = json.load(f)
with open(base / "heroes_all.json") as f:
    all_heroes_data = json.load(f)

all_arts = [a for a in artifacts_data.get("artifacts", []) if not a.get("error") and a.get("rank", 0) >= 5]

# Optional: restrict to equipped-only artifacts (for swap-only mode)
_equipped_art_ids = None
def _load_equipped_ids():
    global _equipped_art_ids
    if _equipped_art_ids is None:
        try:
            with open(base / "equipped_art_ids.json") as f:
                _equipped_art_ids = set(json.load(f))
        except FileNotFoundError:
            _equipped_art_ids = set()
    return _equipped_art_ids


# =============================================================================
# Constraint checker
# =============================================================================
def check_constraints(hero_name, profile, stats, is_uk, is_stun, has_uk_team=True,
                       spd_range=None):
    """Check if stats meet CB constraints. Returns (ok, violations).

    spd_range: optional (min_spd, max_spd) tuple to override default speed range.
    """
    violations = []

    if spd_range:
        spd_min, spd_max = spd_range
        if stats[SPD] < spd_min:
            violations.append(f"SPD {stats[SPD]:.0f} < {spd_min} (too slow)")
        if stats[SPD] > spd_max:
            violations.append(f"SPD {stats[SPD]:.0f} > {spd_max} (too fast)")
    elif has_uk_team:
        # UK team: strict speed constraints
        if is_uk:
            if stats[SPD] < UK_ME_SPD_RANGE[0]:
                violations.append(f"SPD {stats[SPD]:.0f} < {UK_ME_SPD_RANGE[0]} (too slow)")
            if stats[SPD] > UK_ME_SPD_RANGE[1]:
                violations.append(f"SPD {stats[SPD]:.0f} > {UK_ME_SPD_RANGE[1]} (too fast)")
        elif is_stun:
            if stats[SPD] > 118:
                violations.append(f"SPD {stats[SPD]:.0f} > 118 (stun target too fast)")
        else:
            if stats[SPD] < 171:
                violations.append(f"SPD {stats[SPD]:.0f} < 171 (DPS too slow)")
            if stats[SPD] > 189:
                violations.append(f"SPD {stats[SPD]:.0f} > 189 (DPS too fast)")
    # Non-UK: no speed constraints, just want fast heroes

    if profile and profile.needs_acc and stats[ACC] < 250:
        violations.append(f"ACC {stats[ACC]:.0f} < 250")

    # Non-UK: check HP floor (need 25K+ to survive)
    if not has_uk_team and stats[HP] < 25000:
        violations.append(f"HP {stats[HP]:.0f} < 25000")

    return len(violations) == 0, violations


# Myth Eater speed tune (DWJ official Ninja UNM preset):
# ME 288, Demytha 172, Ninja 205, 1:1 DPS 178, 1:1 DPS 160
# All 3 DPS are 1:1 ratio (NOT 4:3)
# Opening delays: ME A3=1, Demytha A3=2, Ninja A3=1
MYTH_EATER_SPEEDS = {
    "Maneater":  (287, 290),   # 288 target, tight buffer
    "Demytha":   (171, 174),   # 172 target
    "Ninja":     (204, 207),   # 205 target (1:1 ratio, NOT 4:3!)
    "dps_1to1":  (177, 180),   # 178 target (Geomancer)
    "dps_slow":  (159, 162),   # 160 target (Venomage)
}


# =============================================================================
# Artifact scoring with constraints
# =============================================================================
def score_artifact_for_hero(art, profile, scaling_stat, is_uk, is_stun,
                             current_spd=0, spd_target=None, spd_max=None,
                             current_acc=0, acc_target=250,
                             current_cr=0, cr_target=100, needs_cr=False):
    """Score an artifact considering constraints."""
    s = 0
    art_spd = 0
    art_acc = 0

    for b in [art.get("primary")] + art.get("substats", []):
        if not b:
            continue
        stat, val, flat = b.get("stat", 0), b.get("value", 0) + b.get("glyph", 0), b.get("flat", True)

        if stat == SPD:
            art_spd += val
            if is_stun:
                s -= val * 200  # heavily penalize SPD on stun target
            elif spd_max and current_spd + val > spd_max:
                s -= val * 100  # hard penalize going over cap
            elif spd_target and current_spd + val < spd_target:
                s += val * 15   # high priority when under minimum
            elif spd_target and spd_max:
                s += val * 2    # In UK range — moderate value
            elif not is_uk and not is_stun:
                # Non-UK: SPD is important (need > CB speed 190)
                s += val * 10
            else:
                s += val * 3
        elif stat == ACC:
            art_acc += val
            if profile and profile.needs_acc:
                if current_acc < acc_target:
                    s += val * (12 if flat else 8)  # high priority if under target
                else:
                    s += val * 2  # diminishing returns over target
            else:
                s += val * 0.5
        elif stat == CR:
            if needs_cr and current_cr < cr_target:
                s += val * 15  # highest priority when under 100% CR
            elif needs_cr:
                s += val * 1   # diminishing returns over target
            else:
                s += val * 2
        elif stat == CD:
            if needs_cr and current_cr >= cr_target:
                s += val * 5   # CD is valuable once CR is capped
            else:
                s += val * 2.5
        elif stat == ATK:
            if scaling_stat == "ATK":
                s += val * (0.08 if flat else 4)
            else:
                s += val * 0.02
        elif stat == DEF:
            if scaling_stat == "DEF":
                s += val * (0.08 if flat else 4)
            else:
                s += val * 0.03
        elif stat == HP:
            if not is_uk and not is_stun:
                # Non-UK: HP is critical for survival
                s += val * (0.05 if flat else 6)
            else:
                s += val * (0.01 if flat else 1)

    s += art.get("rank", 0) * 15
    s += art.get("level", 0) * 4
    if art.get("rank", 0) == 6:
        s += 30

    # CritRate set bonus when CR is under target
    if needs_cr and current_cr < cr_target:
        art_set = art.get("set", 0)
        if art_set == 5:  # CritRate set = +12% CR per 2 pieces
            s += 150  # high priority to reach 100% CR

    # Non-UK: Lifesteal set is critical for survival
    if not is_uk and not is_stun:
        if art.get("set") == 9:  # Lifesteal
            s += 200  # strong preference for Lifesteal pieces

    # Speed set bonus for heroes that need very high SPD (e.g., ME at 286)
    if spd_target and spd_target >= 250 and art.get("set") == 4:
        s += 300  # strong preference for Speed set to hit extreme SPD targets

    return s


# =============================================================================
# Iterative gear assignment with constraint satisfaction
# =============================================================================
def assign_gear_constrained(team_names, team_heroes, team_profiles, speed_ranges=None):
    """Assign gear to a team with hard speed/ACC constraints.

    speed_ranges: optional dict mapping hero index → (min_spd, max_spd).
                  If provided, overrides default Budget UK ranges.

    Strategy:
    1. Greedy initial assignment (like before but constraint-aware)
    2. Check constraints
    3. Iteratively swap pieces to fix violations
    4. Score with the sim
    """
    n = len(team_names)
    has_uk = sum(1 for p in team_profiles if p and p.unkillable) >= 2
    dps_idx = [i for i, p in enumerate(team_profiles) if p and not p.unkillable]

    # When explicit speed_ranges provided, don't auto-assign stun target
    if speed_ranges:
        stun_idx = -1
    else:
        stun_idx = min(dps_idx, key=lambda i: stun_priority(team_profiles[i])) if (dps_idx and has_uk) else -1

    # Determine scaling stats
    from cb_sim import SKILL_DATA
    scaling_stats = []
    for tname in team_names:
        sd = SKILL_DATA.get(tname, {})
        a1 = sd.get("A1", {})
        scaling_stats.append(a1.get("stat", "ATK"))

    # Phase 1: Greedy initial assignment (per-hero, constraint-aware)
    used_ids = set()
    assigned = [[] for _ in range(n)]
    by_slot = {s: [] for s in range(1, 10)}
    for a in all_arts:
        slot = a.get("kind", 0)
        if slot in by_slot:
            by_slot[slot].append(a)

    # Priority: when speed_ranges given, assign highest-speed heroes first (they need fastest gear)
    # Otherwise: UK heroes first, then stun target, then DPS
    if speed_ranges:
        priority = sorted(range(n), key=lambda i: -speed_ranges.get(i, (0, 0))[0])
    else:
        priority = sorted(range(n), key=lambda i: (
            0 if team_profiles[i] and team_profiles[i].unkillable else
            (1 if i == stun_idx else 2)
        ))

    # Pre-compute per-hero config
    hero_configs = {}
    for pi in range(n):
        is_uk = team_profiles[pi] and team_profiles[pi].unkillable
        is_stun = has_uk and pi == stun_idx
        if speed_ranges and pi in speed_ranges:
            spd_target, spd_max = speed_ranges[pi]
        elif not has_uk:
            spd_target, spd_max = None, None
        elif is_uk:
            spd_target, spd_max = UK_ME_SPD_RANGE[0], UK_ME_SPD_RANGE[1]
        elif is_stun:
            spd_target, spd_max = 0, 118
        else:
            spd_target, spd_max = 171, 189
        hero_configs[pi] = {
            "is_uk": is_uk, "is_stun": is_stun,
            "spd_target": spd_target, "spd_max": spd_max,
            "faction": team_heroes[pi].get("fraction", 0),
            "needs_cr": not is_uk and not is_stun,
        }

    # When speed_ranges given, use slot-by-slot round-robin: assign each slot to all heroes
    # before moving to the next, prioritizing SPD-hungry heroes per slot.
    # This prevents one hero from hoarding all high-SPD pieces.
    if speed_ranges:
        # Assign boots first (highest SPD impact), then other main gear, then accessories
        slot_order = [4, 5, 1, 6, 2, 3, 7, 8, 9]
        for slot in slot_order:
            # For each slot, assign to heroes in order of how much more SPD they need
            slot_heroes = list(range(n))
            # Sort by SPD deficit (how far below target)
            def spd_deficit(pi):
                stats = calc_stats(team_heroes[pi], assigned[pi], account)
                sr = speed_ranges.get(pi, (0, 999))
                return sr[0] - stats[SPD]  # positive = needs more
            slot_heroes.sort(key=lambda pi: -spd_deficit(pi))  # most needy first

            for pi in slot_heroes:
                cfg = hero_configs[pi]
                available = [a for a in by_slot.get(slot, []) if a.get("id") not in used_ids]

                if slot >= 7 and cfg["faction"] > 0:
                    same_faction_art_ids = set()
                    for h2 in all_heroes_data.get("heroes", []):
                        if h2.get("fraction") == cfg["faction"]:
                            for a2 in h2.get("artifacts", []):
                                if a2.get("kind") == slot:
                                    same_faction_art_ids.add(a2["id"])
                    available = [a for a in available if a["id"] in same_faction_art_ids]

                if not available:
                    continue

                current_stats = calc_stats(team_heroes[pi], assigned[pi], account)
                scored = []
                for a in available:
                    sc = score_artifact_for_hero(
                        a, team_profiles[pi], scaling_stats[pi],
                        cfg["is_uk"], cfg["is_stun"],
                        current_spd=current_stats[SPD],
                        spd_target=cfg["spd_target"], spd_max=cfg["spd_max"],
                        current_acc=current_stats[ACC],
                        current_cr=current_stats.get(CR, 15),
                        cr_target=100, needs_cr=cfg["needs_cr"])
                    scored.append((sc, a))

                scored.sort(key=lambda x: -x[0])
                best = scored[0][1]
                assigned[pi].append(best)
                used_ids.add(best.get("id"))
    else:
        for pi in priority:
            cfg = hero_configs[pi]

            for slot in range(1, 10):
                available = [a for a in by_slot.get(slot, []) if a.get("id") not in used_ids]

                if slot >= 7 and cfg["faction"] > 0:
                    same_faction_art_ids = set()
                    for h2 in all_heroes_data.get("heroes", []):
                        if h2.get("fraction") == cfg["faction"]:
                            for a2 in h2.get("artifacts", []):
                                if a2.get("kind") == slot:
                                    same_faction_art_ids.add(a2["id"])
                    available = [a for a in available if a["id"] in same_faction_art_ids]

                if not available:
                    continue

                current_stats = calc_stats(team_heroes[pi], assigned[pi], account)
                scored = []
                for a in available:
                    sc = score_artifact_for_hero(
                        a, team_profiles[pi], scaling_stats[pi],
                        cfg["is_uk"], cfg["is_stun"],
                        current_spd=current_stats[SPD],
                        spd_target=cfg["spd_target"], spd_max=cfg["spd_max"],
                        current_acc=current_stats[ACC],
                        current_cr=current_stats.get(CR, 15),
                        cr_target=100, needs_cr=cfg["needs_cr"])
                    scored.append((sc, a))

                scored.sort(key=lambda x: -x[0])
                best = scored[0][1]
                assigned[pi].append(best)
                used_ids.add(best.get("id"))

    # Phase 2: Check constraints and iteratively fix violations
    # Supports multi-piece progressive swaps: swap the piece that brings SPD closest to target,
    # even if it doesn't fully fix the constraint. Repeat until fixed or no progress.
    for iteration in range(30):
        all_ok = True
        for i in range(n):
            stats = calc_stats(team_heroes[i], assigned[i], account)
            is_uk = team_profiles[i] and team_profiles[i].unkillable
            is_stun = has_uk and i == stun_idx
            hero_spd_range = speed_ranges.get(i) if speed_ranges else None
            ok, violations = check_constraints(team_names[i], team_profiles[i], stats, is_uk, is_stun,
                                                has_uk_team=has_uk, spd_range=hero_spd_range)

            if not ok:
                all_ok = False
                # Determine if hero is too fast or too slow
                spd_target_mid = (hero_spd_range[0] + hero_spd_range[1]) / 2 if hero_spd_range else 0
                is_too_fast = hero_spd_range and stats[SPD] > hero_spd_range[1]
                is_too_slow = hero_spd_range and stats[SPD] < hero_spd_range[0]

                # Try swapping pieces to fix — find the swap that brings SPD closest to target
                best_swap = None
                best_dist = abs(stats[SPD] - spd_target_mid)

                for vi, art in enumerate(assigned[i]):
                    slot = art.get("kind", 0)
                    art_spd = sum(b.get("value", 0) + b.get("glyph", 0)
                                  for b in [art.get("primary")] + art.get("substats", [])
                                  if b and b.get("stat") == SPD)

                    for alt in by_slot.get(slot, []):
                        if alt.get("id") in used_ids and alt.get("id") != art.get("id"):
                            continue
                        if alt.get("id") == art.get("id"):
                            continue

                        alt_spd = sum(b.get("value", 0) + b.get("glyph", 0)
                                      for b in [alt.get("primary")] + alt.get("substats", [])
                                      if b and b.get("stat") == SPD)

                        # Skip if swap goes wrong direction
                        if is_too_fast and alt_spd >= art_spd:
                            continue
                        if is_too_slow and alt_spd <= art_spd:
                            continue

                        new_arts = list(assigned[i])
                        new_arts[vi] = alt
                        new_stats = calc_stats(team_heroes[i], new_arts, account)
                        dist = abs(new_stats[SPD] - spd_target_mid)

                        if dist < best_dist:
                            best_dist = dist
                            best_swap = (vi, art, alt, new_arts)

                if best_swap:
                    vi, old_art, new_art, new_arts = best_swap
                    used_ids.discard(old_art.get("id"))
                    used_ids.add(new_art.get("id"))
                    assigned[i] = new_arts

        if all_ok:
            break

    # Phase 3: Cross-hero swaps — if hero A is too slow and hero B has surplus SPD
    # on the same slot, try swapping that piece
    if speed_ranges:
        for iteration in range(30):
            improved = False
            for i in range(n):
                stats_i = calc_stats(team_heroes[i], assigned[i], account)
                sr_i = speed_ranges.get(i)
                if not sr_i or stats_i[SPD] >= sr_i[0]:
                    continue  # hero i is fine

                # Hero i is too slow — find another hero with surplus SPD on a shared slot
                for j in range(n):
                    if i == j:
                        continue
                    sr_j = speed_ranges.get(j)
                    stats_j = calc_stats(team_heroes[j], assigned[j], account)
                    if not sr_j:
                        continue

                    for vi, art_i in enumerate(assigned[i]):
                        slot = art_i.get("kind", 0)
                        # Find same slot in hero j
                        for vj, art_j in enumerate(assigned[j]):
                            if art_j.get("kind") != slot:
                                continue

                            spd_i = sum(b.get("value",0) for b in [art_i.get("primary")] + art_i.get("substats",[])
                                        if b and b.get("stat") == SPD)
                            spd_j = sum(b.get("value",0) for b in [art_j.get("primary")] + art_j.get("substats",[])
                                        if b and b.get("stat") == SPD)

                            if spd_j <= spd_i:
                                continue  # j's piece isn't faster

                            # Try swapping
                            new_i = list(assigned[i]); new_i[vi] = art_j
                            new_j = list(assigned[j]); new_j[vj] = art_i
                            ns_i = calc_stats(team_heroes[i], new_i, account)
                            ns_j = calc_stats(team_heroes[j], new_j, account)

                            ok_i, _ = check_constraints(team_names[i], team_profiles[i], ns_i, False, False,
                                                         spd_range=sr_i)
                            ok_j, _ = check_constraints(team_names[j], team_profiles[j], ns_j, False, False,
                                                         spd_range=sr_j)

                            if ok_i and ok_j:
                                assigned[i] = new_i
                                assigned[j] = new_j
                                improved = True
                                break
                            # Even if not both OK, check if i improved without breaking j's SPD constraint
                            elif ns_i[SPD] > stats_i[SPD] and sr_j[0] <= ns_j[SPD] <= sr_j[1]:
                                assigned[i] = new_i
                                assigned[j] = new_j
                                improved = True
                                break
                        if improved:
                            break
                    if improved:
                        break
            if not improved:
                break

    # Return final stats
    team_stats = [calc_stats(team_heroes[i], assigned[i], account) for i in range(n)]
    return assigned, team_stats


# =============================================================================
# Main
# =============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Constraint-Based Gear Optimizer")
    parser.add_argument("--team", default="ME,ME,Venus,Occult Brawler,Geomancer",
                        help="Comma-separated team")
    parser.add_argument("--tune", choices=["budget_uk", "myth_eater"],
                        help="Speed tune preset (overrides default speed ranges)")
    parser.add_argument("--swap-only", action="store_true",
                        help="Only use artifacts equipped on heroes (swappable, no vault)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-force-affinity", action="store_true",
                        help="Disable Force-Affinity per-skill damage caps (pre-defeat CB).")
    args = parser.parse_args()

    team_names = ["Maneater" if n.strip() == "ME" else n.strip()
                  for n in args.team.split(",")]

    # Myth Eater tune preset
    if args.tune == "myth_eater":
        team_names = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
        print(f"=== Myth Eater Speed Tune ===")
    else:
        print(f"=== Constraint-Based Gear Optimizer ===")
    print(f"Team: {', '.join(team_names)}\n")

    # Build potential heroes
    team_heroes = []
    team_profiles = []
    from cb_potential import build_potential_hero
    me_count = 0
    for tname in team_names:
        h = build_potential_hero(tname)
        p = PROFILES.get(tname)
        if not h or not p:
            print(f"Missing: {tname}")
            return
        team_heroes.append(h)
        team_profiles.append(p)

    # Build per-hero speed ranges for Myth Eater tune
    speed_ranges = None
    if args.tune == "myth_eater":
        # DWJ official Myth Eater Ninja UNM: ME=288, Dem=172, Ninja=205, DPS=178, DPS=160
        speed_ranges = {}
        for i, tname in enumerate(team_names):
            if tname == "Maneater":
                speed_ranges[i] = MYTH_EATER_SPEEDS["Maneater"]
            elif tname == "Demytha":
                speed_ranges[i] = MYTH_EATER_SPEEDS["Demytha"]
            elif tname == "Ninja":
                speed_ranges[i] = MYTH_EATER_SPEEDS["Ninja"]
            elif tname == "Geomancer":
                speed_ranges[i] = MYTH_EATER_SPEEDS["dps_1to1"]
            elif tname == "Venomage":
                speed_ranges[i] = MYTH_EATER_SPEEDS["dps_slow"]
        print("Speed targets:")
        for i, tname in enumerate(team_names):
            sr = speed_ranges.get(i, ("?", "?"))
            print(f"  {tname:20s} → {sr[0]}-{sr[1]} SPD")
        print()

    # Assign gear with constraints
    print("Assigning gear with hard constraints...")
    assigned, team_stats = assign_gear_constrained(team_names, team_heroes, team_profiles,
                                                    speed_ranges=speed_ranges)

    has_uk = sum(1 for p in team_profiles if p.unkillable) >= 2
    dps_idx = [i for i, p in enumerate(team_profiles) if not p.unkillable]
    stun_idx = min(dps_idx, key=lambda i: stun_priority(team_profiles[i])) if dps_idx else -1

    # Check constraints
    print("\nConstraint check:")
    for i, tname in enumerate(team_names):
        is_uk = team_profiles[i].unkillable
        is_stun = has_uk and i == stun_idx
        hero_spd_range = speed_ranges.get(i) if speed_ranges else None
        ok, violations = check_constraints(tname, team_profiles[i], team_stats[i], is_uk, is_stun,
                                            has_uk_team=has_uk, spd_range=hero_spd_range)
        role = "UK" if is_uk else ("STUN" if is_stun else "DPS")
        target = f"({hero_spd_range[0]}-{hero_spd_range[1]})" if hero_spd_range else ""
        status = "✓" if ok else f"✗ {violations}"
        print(f"  {tname:25s} [{role:4s}] SPD:{team_stats[i][SPD]:5.0f} {target:10s} ACC:{team_stats[i][ACC]:5.0f}  {status}")

    # Run sim with constrained gear
    print("\nRunning turn-by-turn simulation...")
    sim_champs = []
    me_idx = 0
    for i, tname in enumerate(team_names):
        stats = team_stats[i]
        opening = []
        if tname == "Maneater":
            me_idx += 1
            # Fast ME (higher SPD) opens A3, Slow ME delays
            if me_idx == 1:
                opening = ["A3"]
            else:
                opening = ["A1", "A3"]

        champ = build_sim_champion(tname, stats, i + 1,
                                    masteries=team_heroes[i].get("masteries", []),
                                    opening=opening)
        sim_champs.append(champ)

    # Ensure faster ME gets position 2 (opens A3), slower ME gets position 3
    me_indices = [i for i, t in enumerate(team_names) if t == "Maneater"]
    if len(me_indices) == 2:
        i1, i2 = me_indices
        if sim_champs[i1].speed < sim_champs[i2].speed:
            # Swap openings — faster one should open A3
            sim_champs[i1].opening, sim_champs[i2].opening = sim_champs[i2].opening, sim_champs[i1].opening

    max_turns = 50 if has_uk else 0  # unlimited for non-UK (run until all dead)
    # Force Affinity mode default ON: post-defeat CB caps per-skill damage. Disable
    # with --no-force-affinity for pre-defeat CB where the full damage is dealt.
    sim = CBSimulator(deepcopy(sim_champs), deterministic=True, verbose=args.verbose,
                      model_survival=True,
                      force_affinity=not getattr(args, "no_force_affinity", False))
    result = sim.run(max_cb_turns=max_turns)

    gaps = len(result["errors"])
    print(f"\n{'='*70}")
    print(f"TOTAL: {result['total']/1e6:.1f}M over {result['cb_turns']} CB turns")
    print(f"Speed tune: {'VALID ✓' if result['valid'] else f'INVALID ✗ ({gaps} gaps)'}")
    if result["errors"]:
        print("Protection gaps:")
        for e in result["errors"][:10]:
            print(f"  ✗ {e}")
    print(f"{'='*70}")
    for i, hd in enumerate(result["heroes"]):
        parts = []
        for key, lbl in [("direct", "Dir"), ("poison", "Poi"), ("hp_burn", "Burn"),
                          ("wm_gs", "WM"), ("passive", "Pass")]:
            v = hd.get(key, 0)
            if v > 0:
                parts.append(f"{lbl}:{v/1e6:.1f}M")
        s = team_stats[i]
        print(f"  {hd['name']:25s} {hd['total']/1e6:6.1f}M  SPD:{s[SPD]:.0f} ACC:{s[ACC]:.0f} ATK:{s[ATK]:.0f} DEF:{s[DEF]:.0f}  [{', '.join(parts)}]")

    # Print artifact assignments and equip commands
    print(f"\n{'='*70}")
    print("GEAR ASSIGNMENTS")
    print(f"{'='*70}")
    equip_cmds = []
    for i, tname in enumerate(team_names):
        hero_id = team_heroes[i].get("id", "?")
        arts = assigned[i]
        print(f"\n  {tname} (hero_id={hero_id}):")
        for a in arts:
            aid = a.get("id", "?")
            kind = a.get("kind", "?")
            rank = a.get("rank", "?")
            set_id = a.get("set", "?")
            level = a.get("level", "?")
            # ArtifactKindId: 1=Helmet,2=Chest,3=Gloves,4=Boots,5=Weapon,6=Shield,7=Ring,8=Amulet,9=Banner
            slot_names = {1: "Helmet", 2: "Chest", 3: "Gloves", 4: "Boots", 5: "Weapon", 6: "Shield",
                          7: "Ring", 8: "Amulet", 9: "Banner"}
            slot = slot_names.get(kind, f"slot{kind}")
            print(f"    {slot:8s} art_id={aid:5d}  {rank}★ set={set_id} L{level}")
            equip_cmds.append((hero_id, aid))

    print(f"\n{'='*70}")
    print("AUTO-EQUIP COMMANDS (paste into browser or use mod_client)")
    print(f"{'='*70}")
    for hero_id, art_id in equip_cmds:
        print(f"  curl 'http://localhost:6790/equip?hero_id={hero_id}&artifact_id={art_id}'")

    if args.verbose and result.get("log"):
        print(f"\nTurn log:")
        for line in result["log"][:80]:
            print(line)


if __name__ == "__main__":
    main()
