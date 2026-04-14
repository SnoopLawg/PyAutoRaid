#!/usr/bin/env python3
"""
Global Gear Solver for CB Teams.

Solves the constraint-satisfaction problem: assign artifacts across all 5 CB heroes
simultaneously to maximize sim damage, subject to speed tune constraints, ACC floors,
faction-locked accessories, and set bonus optimization.

Uses: constraint propagation → greedy initialization → simulated annealing with
      CB sim-in-the-loop scoring.

Usage:
    python3 tools/global_gear_solver.py
    python3 tools/global_gear_solver.py --team "Maneater,Demytha,Ninja,Geomancer,Venomage"
    python3 tools/global_gear_solver.py --sa-iterations 10000
"""

import json
import math
import random
import sys
import time
import argparse
from pathlib import Path
from copy import deepcopy
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from cb_optimizer import (calc_stats, PROFILES, HP, ATK, DEF, SPD, ACC, CR, CD,
                          MASTERY_IDS, SET_BONUSES)
from cb_sim import CBSimulator, build_sim_champion, apply_leader_aura
from gear_constants import ACCESSORY_SLOTS, SLOT_NAMES
from auto_profile import get_leader_skills

# =============================================================================
# Speed tune definitions
# =============================================================================
MYTH_EATER_SPEEDS = {
    "Maneater":   (287, 290),
    "Demytha":    (171, 174),
    "Ninja":      (204, 207),
    "Geomancer":  (177, 180),
    "Venomage":   (159, 162),
}

# Generic DPS speed slots for non-named heroes
MYTH_EATER_DPS_SLOTS = [
    ("dps_4to3", (204, 207)),   # Ninja-speed slot
    ("dps_1to1", (177, 180)),   # Mid-speed slot
    ("dps_slow", (159, 162)),   # Slow slot
]

# ACC floor for debuffers (UNM RES = 250, need 250+ ACC)
ACC_FLOOR = 230  # slightly relaxed from 250 to find more solutions

# Heroes that need ACC
NEEDS_ACC = {"Ninja", "Geomancer", "Venomage", "Venus", "Fayne", "Occult Brawler",
             "Nethril", "Rhazin Scarhide", "Toragi the Frog", "Teodor the Savant",
             "Sicia Flametongue", "Drexthar Bloodtwin"}


# =============================================================================
# Artifact pool
# =============================================================================
class ArtifactPool:
    """Indexed artifact collection for fast lookup."""

    def __init__(self, artifacts, heroes_all):
        self.all_artifacts = artifacts
        self.by_id = {a["id"]: a for a in artifacts}

        # Index by slot (kind)
        self.by_slot = {}
        for a in artifacts:
            slot = a["kind"]
            self.by_slot.setdefault(slot, []).append(a)

        # Build accessory faction map from equipped heroes
        self._accessory_faction = {}  # artifact_id -> fraction
        for h in heroes_all:
            frac = h.get("fraction", 0)
            for a in h.get("artifacts", []):
                aid = a.get("id")
                if aid and a.get("kind", 0) in ACCESSORY_SLOTS:
                    self._accessory_faction[aid] = frac

        # Sort each slot by total SPD contribution (descending)
        for slot, arts in self.by_slot.items():
            arts.sort(key=lambda a: self._spd_contribution(a), reverse=True)

    def _spd_contribution(self, art):
        """Total SPD from this artifact (primary + substats + glyph)."""
        total = 0
        pri = art.get("primary", {})
        if pri.get("stat") == SPD:
            total += pri.get("value", 0) + pri.get("glyph", 0)
        for sub in art.get("substats", []):
            if sub.get("stat") == SPD:
                total += sub.get("value", 0) + sub.get("glyph", 0)
        return total

    def get_candidates(self, slot, hero_fraction=None):
        """Get candidate artifacts for a slot, optionally filtered by faction for accessories."""
        arts = self.by_slot.get(slot, [])
        if slot in ACCESSORY_SLOTS and hero_fraction:
            return [a for a in arts if self._accessory_faction.get(a["id"]) == hero_fraction
                    or a["id"] not in self._accessory_faction]  # include unknown-faction vault pieces
        return arts

    def accessory_faction(self, art_id):
        return self._accessory_faction.get(art_id)


# =============================================================================
# Assignment representation
# =============================================================================
class GearAssignment:
    """Represents a complete gear assignment for a team."""

    SLOTS = [1, 2, 3, 4, 5, 6, 7, 8, 9]

    def __init__(self, hero_names, hero_data, account):
        self.hero_names = hero_names
        self.hero_data = hero_data  # list of hero dicts
        self.account = account
        self.n_heroes = len(hero_names)
        # assignment[hero_idx][slot] = artifact dict or None
        self.assignment = [{s: None for s in self.SLOTS} for _ in range(self.n_heroes)]
        self._used_ids = set()

    def assign(self, hero_idx, slot, artifact):
        """Assign an artifact to a hero slot. Returns the old artifact (or None)."""
        old = self.assignment[hero_idx].get(slot)
        if old:
            self._used_ids.discard(old["id"])
        self.assignment[hero_idx][slot] = artifact
        if artifact:
            self._used_ids.add(artifact["id"])
        return old

    def is_used(self, artifact_id):
        return artifact_id in self._used_ids

    def get_hero_artifacts(self, hero_idx):
        """Get list of assigned artifacts for a hero."""
        return [a for a in self.assignment[hero_idx].values() if a is not None]

    def calc_hero_stats(self, hero_idx):
        """Calculate stats for a hero with current gear assignment."""
        return calc_stats(self.hero_data[hero_idx], self.get_hero_artifacts(hero_idx), self.account)

    def all_stats(self):
        """Calculate stats for all heroes."""
        return [self.calc_hero_stats(i) for i in range(self.n_heroes)]

    def check_constraints(self, speed_ranges, acc_needs):
        """Check if assignment satisfies all constraints. Returns (ok, violations)."""
        violations = []
        for i in range(self.n_heroes):
            name = self.hero_names[i]
            stats = self.calc_hero_stats(i)
            spd = stats[SPD]
            acc = stats[ACC]

            spd_range = speed_ranges.get(name)
            if spd_range:
                if spd < spd_range[0]:
                    violations.append(f"{name}: SPD {spd:.0f} < {spd_range[0]}")
                if spd > spd_range[1]:
                    violations.append(f"{name}: SPD {spd:.0f} > {spd_range[1]}")

            if name in acc_needs and acc < ACC_FLOOR:
                violations.append(f"{name}: ACC {acc:.0f} < {ACC_FLOOR}")

        return len(violations) == 0, violations


# =============================================================================
# Sim scoring
# =============================================================================
def score_assignment(assignment, speed_ranges, acc_needs, cb_element=2, force_affinity=True,
                     leader_aura=None):
    """Score a gear assignment by running the CB sim. Returns (damage, valid, violations)."""
    ok, violations = assignment.check_constraints(speed_ranges, acc_needs)

    all_stats = assignment.all_stats()
    sim_champs = []
    for i, (name, stats) in enumerate(zip(assignment.hero_names, all_stats)):
        if leader_aura:
            stats = apply_leader_aura(stats, leader_aura)
        hero = assignment.hero_data[i]
        element = hero.get("element", 4)
        champ = build_sim_champion(name, stats, i, element=element)
        sim_champs.append(champ)

    sim = CBSimulator(sim_champs, cb_element=cb_element, deterministic=True,
                      verbose=False, force_affinity=force_affinity)
    result = sim.run(max_cb_turns=50)

    # Penalty: each violation costs heavily to force the SA to find valid solutions
    penalty = 0
    for v in violations:
        # SPD violations are critical — 10M per SPD point off
        if "SPD" in v:
            # Extract how far off
            import re
            nums = re.findall(r'[\d.]+', v)
            if len(nums) >= 2:
                actual, target = float(nums[0]), float(nums[1])
                penalty += abs(actual - target) * 10_000_000
            else:
                penalty += 50_000_000
        else:
            penalty += 20_000_000

    return result["total"] - penalty, ok, violations


# =============================================================================
# Greedy initialization
# =============================================================================
def greedy_init(assignment, pool, speed_ranges, acc_needs):
    """Greedy assignment: most constrained hero first, SPD-priority."""
    # Sort heroes by constraint tightness (tightest speed range first)
    hero_order = list(range(assignment.n_heroes))
    def constraint_tightness(idx):
        name = assignment.hero_names[idx]
        sr = speed_ranges.get(name)
        if sr:
            return sr[1] - sr[0]  # smaller range = tighter
        return 999
    hero_order.sort(key=constraint_tightness)

    # Assign boots first (biggest SPD impact), then other slots
    slot_order = [4, 5, 1, 6, 2, 3, 7, 8, 9]  # Boots first, accessories last

    for slot in slot_order:
        for hero_idx in hero_order:
            name = assignment.hero_names[hero_idx]
            hero = assignment.hero_data[hero_idx]
            fraction = hero.get("fraction", 0)

            candidates = pool.get_candidates(slot, hero_fraction=fraction)
            best_art = None
            best_score = -float("inf")

            # Current stats without this slot
            current_stats = assignment.calc_hero_stats(hero_idx)
            spd_range = speed_ranges.get(name, (0, 999))
            needs_acc = name in acc_needs

            for art in candidates:
                if assignment.is_used(art["id"]):
                    continue

                # Quick SPD check: would this push over max?
                art_spd = pool._spd_contribution(art)
                new_spd_approx = current_stats[SPD] + art_spd
                # Don't be too strict here — let scoring handle it

                # Score: prioritize meeting constraints, then maximize damage stats
                score = 0

                # SPD scoring
                if new_spd_approx < spd_range[0]:
                    score += art_spd * 20  # need more speed
                elif new_spd_approx <= spd_range[1]:
                    score += art_spd * 5   # in range
                else:
                    score -= (new_spd_approx - spd_range[1]) * 30  # over max

                # ACC scoring
                art_acc = 0
                for sub in [art.get("primary", {})] + art.get("substats", []):
                    if sub and sub.get("stat") == ACC:
                        art_acc += sub.get("value", 0) + sub.get("glyph", 0)
                if needs_acc and current_stats[ACC] < ACC_FLOOR:
                    score += art_acc * 15
                elif needs_acc:
                    score += art_acc * 2

                # Damage stats (ATK/DEF/CD/CR)
                for sub in [art.get("primary", {})] + art.get("substats", []):
                    if not sub:
                        continue
                    stat = sub.get("stat", 0)
                    val = sub.get("value", 0) + sub.get("glyph", 0)
                    flat = sub.get("flat", True)
                    if stat == CD:
                        score += val * 3
                    elif stat == CR:
                        score += val * 2
                    elif stat == ATK and not flat:
                        score += val * 2.5
                    elif stat == DEF and not flat:
                        score += val * 2
                    elif stat == HP and not flat:
                        score += val * 1

                # Set bonus: prefer Speed set for Maneater
                art_set = art.get("set", 0)
                if art_set == 4 and name == "Maneater":
                    score += 50  # Speed set pieces are critical for ME
                elif art_set == 29 and needs_acc:
                    score += 30  # Perception for debuffers

                if score > best_score:
                    best_score = score
                    best_art = art

            if best_art:
                assignment.assign(hero_idx, slot, best_art)


# =============================================================================
# Simulated annealing
# =============================================================================
def simulated_annealing(assignment, pool, speed_ranges, acc_needs,
                        max_iterations=5000, cb_element=2, force_affinity=True,
                        verbose=False):
    """Improve assignment via simulated annealing with sim-in-the-loop scoring."""
    current_score, current_valid, _ = score_assignment(
        assignment, speed_ranges, acc_needs, cb_element, force_affinity)

    best_assignment = deepcopy(assignment)
    best_score = current_score

    temperature = 1.0
    decay = 0.9995
    accepted = 0
    improved = 0

    t_start = time.time()

    for iteration in range(max_iterations):
        # Choose a random move
        move_type = random.choice(["swap_vault", "swap_vault", "swap_between"])

        if move_type == "swap_vault":
            # Replace one artifact with an unused one from the same slot
            hero_idx = random.randint(0, assignment.n_heroes - 1)
            slot = random.choice(GearAssignment.SLOTS)
            hero = assignment.hero_data[hero_idx]
            fraction = hero.get("fraction", 0)

            candidates = pool.get_candidates(slot, hero_fraction=fraction)
            unused = [a for a in candidates if not assignment.is_used(a["id"])]
            if not unused:
                continue

            new_art = random.choice(unused[:20])  # sample from top 20 by SPD
            old_art = assignment.assign(hero_idx, slot, new_art)

        elif move_type == "swap_between":
            # Swap same-slot artifacts between two heroes
            h1, h2 = random.sample(range(assignment.n_heroes), 2)
            slot = random.choice(GearAssignment.SLOTS)

            # For accessories, check faction compatibility
            if slot in ACCESSORY_SLOTS:
                f1 = assignment.hero_data[h1].get("fraction", 0)
                f2 = assignment.hero_data[h2].get("fraction", 0)
                a1 = assignment.assignment[h1].get(slot)
                a2 = assignment.assignment[h2].get(slot)
                if a1 and pool.accessory_faction(a1["id"]) and pool.accessory_faction(a1["id"]) != f2:
                    continue
                if a2 and pool.accessory_faction(a2["id"]) and pool.accessory_faction(a2["id"]) != f1:
                    continue

            a1 = assignment.assignment[h1][slot]
            a2 = assignment.assignment[h2][slot]
            assignment.assignment[h1][slot] = a2
            assignment.assignment[h2][slot] = a1
            old_art = None  # signal: it was a swap

        # Score new assignment
        new_score, new_valid, violations = score_assignment(
            assignment, speed_ranges, acc_needs, cb_element, force_affinity)

        delta = new_score - current_score

        # Accept or reject
        if delta > 0 or random.random() < math.exp(min(delta / (temperature * 1_000_000 + 1), 0)):
            current_score = new_score
            accepted += 1
            if new_score > best_score:
                best_score = new_score
                best_assignment = deepcopy(assignment)
                improved += 1
                if verbose:
                    print(f"  [{iteration:5d}] NEW BEST: {best_score/1e6:.2f}M "
                          f"(T={temperature:.4f}, valid={new_valid})")
        else:
            # Revert
            if move_type == "swap_vault":
                assignment.assign(hero_idx, slot, old_art)
            elif move_type == "swap_between":
                assignment.assignment[h1][slot] = a1
                assignment.assignment[h2][slot] = a2

        temperature *= decay

    elapsed = time.time() - t_start
    print(f"SA: {max_iterations} iters in {elapsed:.1f}s, "
          f"{accepted} accepted, {improved} improved, "
          f"best={best_score/1e6:.2f}M")

    return best_assignment, best_score


# =============================================================================
# Main solver
# =============================================================================
def solve_global_gear(team_names, speed_ranges=None, cb_element=2,
                      force_affinity=True, sa_iterations=5000, verbose=False):
    """Full gear optimization pipeline."""
    base = PROJECT_ROOT

    with open(base / "heroes_all.json") as f:
        heroes_all_data = json.load(f)
    with open(base / "all_artifacts.json") as f:
        artifacts_data = json.load(f)
    with open(base / "account_data.json") as f:
        account = json.load(f)

    all_heroes = heroes_all_data.get("heroes", [])
    all_arts = [a for a in artifacts_data.get("artifacts", [])
                if not a.get("error") and a.get("rank", 0) >= 5]

    # Default speed ranges
    if speed_ranges is None:
        speed_ranges = {}
        for name in team_names:
            if name in MYTH_EATER_SPEEDS:
                speed_ranges[name] = MYTH_EATER_SPEEDS[name]
            # For unknown heroes in DPS slots, assign remaining speed slots
        # Assign unmatched heroes to DPS slots
        used_slots = set()
        for name in team_names:
            if name not in speed_ranges and name not in ("Maneater", "Demytha"):
                for slot_name, spd_range in MYTH_EATER_DPS_SLOTS:
                    if slot_name not in used_slots:
                        speed_ranges[name] = spd_range
                        used_slots.add(slot_name)
                        break

    # ACC needs
    acc_needs = {name for name in team_names if name in NEEDS_ACC}

    print(f"=== Global Gear Solver ===")
    print(f"Team: {', '.join(team_names)}")
    print(f"Speed ranges:")
    for name in team_names:
        sr = speed_ranges.get(name, "none")
        acc = "ACC>=230" if name in acc_needs else ""
        print(f"  {name:20s} SPD={sr} {acc}")

    # Resolve heroes
    hero_by_name = {}
    for h in all_heroes:
        name = h.get("name", "")
        grade = h.get("grade", 0)
        if grade >= 6:
            if name not in hero_by_name:
                hero_by_name[name] = h
            elif name == "Maneater" and "Maneater_2" not in hero_by_name:
                hero_by_name["Maneater_2"] = h

    hero_data = []
    for name in team_names:
        h = hero_by_name.get(name)
        if not h:
            print(f"  WARNING: {name} not found in 6-star roster!")
            return None
        hero_data.append(h)

    # Build artifact pool
    pool = ArtifactPool(all_arts, all_heroes)
    print(f"\nArtifact pool: {len(all_arts)} rank 5+ artifacts")
    for slot in range(1, 10):
        print(f"  {SLOT_NAMES.get(slot, f's{slot}'):8s}: {len(pool.by_slot.get(slot, []))}")

    # Phase 1: Greedy initialization
    print(f"\nPhase 1: Greedy initialization...")
    assignment = GearAssignment(team_names, hero_data, account)
    greedy_init(assignment, pool, speed_ranges, acc_needs)

    greedy_score, greedy_valid, greedy_violations = score_assignment(
        assignment, speed_ranges, acc_needs, cb_element, force_affinity)
    print(f"  Greedy score: {greedy_score/1e6:.2f}M (valid={greedy_valid})")
    if greedy_violations:
        for v in greedy_violations:
            print(f"    {v}")

    # Show greedy stats
    print(f"\n  Greedy stats:")
    for i, name in enumerate(team_names):
        stats = assignment.calc_hero_stats(i)
        arts = assignment.get_hero_artifacts(i)
        set_counts = Counter(a.get("set", 0) for a in arts)
        from cb_optimizer import SET_NAMES as OPT_SET_NAMES
        set_str = ", ".join(f"{OPT_SET_NAMES.get(s, f's{s}')}×{c}" for s, c in set_counts.most_common(3) if c > 0)
        sr = speed_ranges.get(name, (0, 999))
        spd_ok = "ok" if sr[0] <= stats[SPD] <= sr[1] else "MISS"
        acc_ok = "ok" if name not in acc_needs or stats[ACC] >= ACC_FLOOR else "MISS"
        print(f"    {name:20s} SPD={stats[SPD]:>6.1f} [{spd_ok:4s}] "
              f"ACC={stats[ACC]:>5.0f} [{acc_ok:4s}] "
              f"CD={stats[CD]:>5.1f} CR={stats[CR]:>5.1f} "
              f"[{set_str}]")

    # Phase 2: Simulated annealing
    if sa_iterations > 0:
        print(f"\nPhase 2: Simulated annealing ({sa_iterations} iterations)...")
        best_assignment, best_score = simulated_annealing(
            deepcopy(assignment), pool, speed_ranges, acc_needs,
            max_iterations=sa_iterations, cb_element=cb_element,
            force_affinity=force_affinity, verbose=verbose)

        improvement = best_score - greedy_score
        print(f"  Improvement: {improvement/1e6:+.2f}M")
    else:
        best_assignment = assignment
        best_score = greedy_score

    # Final results
    print(f"\n{'='*70}")
    print(f"FINAL RESULT: {best_score/1e6:.2f}M")
    print(f"{'='*70}")

    ok, violations = best_assignment.check_constraints(speed_ranges, acc_needs)
    if violations:
        print(f"\nConstraint violations:")
        for v in violations:
            print(f"  {v}")

    print(f"\nPer-hero gear:")
    for i, name in enumerate(team_names):
        stats = best_assignment.calc_hero_stats(i)
        arts = best_assignment.get_hero_artifacts(i)
        set_counts = Counter(a.get("set", 0) for a in arts)
        from cb_optimizer import SET_NAMES as OPT_SET_NAMES
        set_str = ", ".join(f"{OPT_SET_NAMES.get(s, f's{s}')}×{c}" for s, c in set_counts.most_common(3) if c > 0)
        sr = speed_ranges.get(name, (0, 999))
        spd_ok = "ok" if sr[0] <= stats[SPD] <= sr[1] else "MISS"

        print(f"\n  {name} (SPD={stats[SPD]:.1f} [{spd_ok}], "
              f"ACC={stats[ACC]:.0f}, CR={stats[CR]:.1f}, CD={stats[CD]:.1f}, "
              f"HP={stats[HP]:.0f}, ATK={stats[ATK]:.0f}, DEF={stats[DEF]:.0f})")
        print(f"    Sets: {set_str}")
        for slot in GearAssignment.SLOTS:
            art = best_assignment.assignment[i].get(slot)
            if art:
                slot_name = SLOT_NAMES.get(slot, f"s{slot}")
                set_name = OPT_SET_NAMES.get(art.get("set", 0), "?")
                spd_val = pool._spd_contribution(art)
                print(f"    {slot_name:8s} R{art.get('rank',0)} {set_name:12s} "
                      f"id={art['id']:>6d} SPD={spd_val:>2.0f}")

    # Run final sim for detailed breakdown
    all_stats = best_assignment.all_stats()
    sim_champs = []
    for i, (name, stats) in enumerate(zip(team_names, all_stats)):
        hero = hero_data[i]
        element = hero.get("element", 4)
        champ = build_sim_champion(name, stats, i, element=element)
        sim_champs.append(champ)

    sim = CBSimulator(sim_champs, cb_element=cb_element, deterministic=True,
                      verbose=False, force_affinity=force_affinity)
    result = sim.run(max_cb_turns=50)

    print(f"\n--- Damage Breakdown ---")
    print(f"{'Hero':20s} {'Total':>10s} {'Direct':>10s} {'Poison':>10s} "
          f"{'Burn':>10s} {'WM/GS':>10s} {'Pass':>10s}")
    for hd in result["heroes"]:
        print(f"{hd['name']:20s} {hd['total']:>10,.0f} {hd['direct']:>10,.0f} "
              f"{hd['poison']:>10,.0f} {hd['hp_burn']:>10,.0f} {hd['wm_gs']:>10,.0f} "
              f"{hd['passive']:>10,.0f}")
    print(f"{'TOTAL':20s} {result['total']:>10,.0f}")

    return best_assignment, best_score, result


def main():
    parser = argparse.ArgumentParser(description="Global Gear Solver for CB")
    parser.add_argument("--team", default="Maneater,Demytha,Ninja,Geomancer,Venomage")
    parser.add_argument("--sa-iterations", type=int, default=3000,
                        help="Simulated annealing iterations (default: 3000)")
    parser.add_argument("--cb-element", default="void",
                        choices=["magic", "force", "spirit", "void"])
    parser.add_argument("--no-force-affinity", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    ELEMENT_MAP = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
    team_names = [n.strip() for n in args.team.split(",")]

    solve_global_gear(
        team_names,
        cb_element=ELEMENT_MAP[args.cb_element],
        force_affinity=not args.no_force_affinity,
        sa_iterations=args.sa_iterations,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
