#!/usr/bin/env python3
"""
CB Simulator Calibration Tool.

Compares sim predictions against real battle log data on a per-boss-turn basis.
Identifies which damage sources are over/underestimated.

Usage:
    python3 tools/cb_calibrate.py --log battle_logs_cb_synced.json
    python3 tools/cb_calibrate.py --log battle_logs_cb_synced.json --cb-element force
    python3 tools/cb_calibrate.py --log battle_logs_cb_synced.json --cb-element void
"""

import json
import sys
import argparse
from pathlib import Path
from copy import deepcopy

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from cb_sim import CBSimulator, build_sim_champion, SimChampion, apply_leader_aura
from cb_optimizer import calc_stats, PROFILES
from auto_profile import get_leader_skills


ELEMENT_MAP = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
ELEMENT_NAMES = {1: "Magic", 2: "Force", 3: "Spirit", 4: "Void"}


def extract_real_data(log_path: Path) -> dict:
    """Extract per-boss-turn damage from a real battle log."""
    data = json.loads(log_path.read_text())
    log_entries = data.get("log", data) if isinstance(data, dict) else data

    # Extract boss damage at each boss turn_n change
    snapshots = []  # [(boss_turn, cumul_dmg)]
    last_tn = -1
    last_dmg = 0

    # Also extract team composition (type_ids of player heroes)
    team_type_ids = []

    for entry in log_entries:
        if "heroes" not in entry:
            continue

        # Capture team on first poll
        if not team_type_ids:
            for h in entry["heroes"]:
                if h.get("side") == "player":
                    team_type_ids.append(h.get("type_id"))

        for h in entry["heroes"]:
            if h.get("side") == "enemy":
                tn = h.get("turn_n", 0)
                dmg = h.get("dmg_taken", 0)
                if tn != last_tn and tn > 0:
                    snapshots.append([tn, dmg])
                    last_tn = tn
                elif tn == last_tn and dmg > last_dmg:
                    if snapshots and snapshots[-1][0] == tn:
                        snapshots[-1][1] = dmg
                last_dmg = dmg
                break

    # Compute per-turn deltas
    turns = []
    prev_dmg = 0
    for tn, cumul in snapshots:
        turns.append({
            "boss_turn": tn,
            "cumul_dmg": cumul,
            "delta": cumul - prev_dmg,
        })
        prev_dmg = cumul

    return {
        "turns": turns,
        "total_damage": snapshots[-1][1] if snapshots else 0,
        "boss_turns": len(snapshots),
        "team_type_ids": team_type_ids,
        "source": log_path.name,
    }


def run_sim_for_team(team_names, cb_element, force_affinity, max_cb_turns,
                     use_current_gear=True, bugfix_buff_tick=False):
    """Run the CB sim and return result with turn snapshots."""
    base = PROJECT_ROOT

    with open(base / "heroes_6star.json") as f:
        heroes_data = json.load(f)
    with open(base / "all_artifacts.json") as f:
        artifacts_data = json.load(f)
    with open(base / "account_data.json") as f:
        account = json.load(f)

    all_arts = [a for a in artifacts_data.get("artifacts", []) if not a.get("error")]

    # Resolve heroes
    hero_by_name = {}
    for h in heroes_data["heroes"]:
        name = h.get("name", "")
        if name and name not in hero_by_name:
            hero_by_name[name] = h
        elif name == "Maneater" and "Maneater_2" not in hero_by_name:
            hero_by_name["Maneater_2"] = h

    # Get leader skill aura (first hero in team is leader)
    leader_skills = get_leader_skills()
    leader_aura = leader_skills.get(team_names[0])

    sim_champs = []
    missing_at_6star = []
    for idx, name in enumerate(team_names):
        hero = hero_by_name.get(name)
        if not hero:
            print(f"  WARNING: Hero '{name}' not found in 6-star roster", file=sys.stderr)
            missing_at_6star.append(name)
            continue

        profile = PROFILES.get(name, PROFILES.get("generic", {}))

        if use_current_gear:
            hero_arts = hero.get("artifacts", [])
        else:
            from cb_optimizer import optimal_artifacts_for_hero
            hero_arts = optimal_artifacts_for_hero(hero, all_arts, profile, account)

        stats = calc_stats(hero, hero_arts, account)
        stats = apply_leader_aura(stats, leader_aura)
        element = hero.get("element", 4)
        champ = build_sim_champion(name, stats, idx, element=element)
        sim_champs.append(champ)

    sim = CBSimulator(
        sim_champs,
        cb_element=cb_element,
        deterministic=True,
        verbose=False,
        force_affinity=force_affinity,
        bugfix_buff_tick=bugfix_buff_tick,
    )
    result = sim.run(max_cb_turns=max_cb_turns)
    # Surface partial-team runs so callers don't treat them as authoritative.
    if missing_at_6star:
        result["partial_team"] = True
        result["missing_at_6star"] = missing_at_6star
    return result


def calibrate(real_data, sim_result):
    """Compare real vs sim per-boss-turn and print analysis."""
    real_turns = real_data["turns"]
    sim_snapshots = sim_result.get("turn_snapshots", [])

    print(f"\n{'='*80}")
    print(f"CALIBRATION: {real_data['source']}")
    print(f"{'='*80}")
    print(f"Real: {real_data['total_damage']:>12,} over {real_data['boss_turns']} boss turns")
    print(f"Sim:  {sim_result['total']:>12,} over {sim_result['cb_turns']} CB turns")
    diff_pct = (sim_result["total"] - real_data["total_damage"]) / real_data["total_damage"] * 100
    print(f"Diff: {diff_pct:+.1f}%")
    print(f"CB Element: {ELEMENT_NAMES.get(sim_result.get('cb_element', 4), '?')}")

    # Per-hero breakdown
    print(f"\n--- Per-Hero Damage ---")
    print(f"{'Hero':20s} {'Total':>10s} {'Direct':>10s} {'Poison':>10s} {'Burn':>10s} {'WM/GS':>10s} {'Pass':>10s} {'Turns':>6s}")
    for hd in sim_result["heroes"]:
        print(f"{hd['name']:20s} {hd['total']:>10,.0f} {hd['direct']:>10,.0f} "
              f"{hd['poison']:>10,.0f} {hd['hp_burn']:>10,.0f} {hd['wm_gs']:>10,.0f} "
              f"{hd['passive']:>10,.0f} {hd['turns']:>6d}")

    # Damage source totals
    total_direct = sum(h["direct"] for h in sim_result["heroes"])
    total_poison = sum(h["poison"] for h in sim_result["heroes"])
    total_burn = sum(h["hp_burn"] for h in sim_result["heroes"])
    total_wmgs = sum(h["wm_gs"] for h in sim_result["heroes"])
    total_pass = sum(h["passive"] for h in sim_result["heroes"])
    sim_total = sim_result["total"]

    print(f"\n--- Damage Source Breakdown ---")
    print(f"  Direct hits: {total_direct:>12,.0f} ({total_direct/sim_total*100:.1f}%)")
    print(f"  Poison:      {total_poison:>12,.0f} ({total_poison/sim_total*100:.1f}%)")
    print(f"  HP Burn:     {total_burn:>12,.0f} ({total_burn/sim_total*100:.1f}%)")
    print(f"  WM/GS:       {total_wmgs:>12,.0f} ({total_wmgs/sim_total*100:.1f}%)")
    print(f"  Passive:     {total_pass:>12,.0f} ({total_pass/sim_total*100:.1f}%)")

    # Per-boss-turn comparison
    if sim_snapshots and real_turns:
        print(f"\n--- Per-Boss-Turn Comparison ---")
        print(f"{'BT':>3s} {'Real_Delta':>12s} {'Sim_Delta':>12s} {'Diff':>12s} "
              f"{'Real_Cumul':>12s} {'Sim_Cumul':>12s} {'Err%':>7s} "
              f"{'Poi':>3s} {'Burn':>4s} {'DD':>2s} {'WK':>2s} {'Bar':>3s}")

        max_turns = min(len(real_turns), len(sim_snapshots))
        prev_sim_dmg = 0

        for i in range(max_turns):
            rt = real_turns[i]
            ss = sim_snapshots[i]

            sim_delta = ss["cumulative_damage"] - prev_sim_dmg
            real_delta = rt["delta"]
            delta_diff = sim_delta - real_delta
            cumul_err = (ss["cumulative_damage"] - rt["cumul_dmg"]) / max(rt["cumul_dmg"], 1) * 100

            print(f"{rt['boss_turn']:>3d} {real_delta:>12,} {sim_delta:>12,.0f} {delta_diff:>+12,.0f} "
                  f"{rt['cumul_dmg']:>12,} {ss['cumulative_damage']:>12,.0f} {cumul_err:>+6.1f}% "
                  f"{ss['poison_count']:>3d} {'Y' if ss['hp_burn_active'] else 'N':>4s} "
                  f"{'Y' if ss['def_down_active'] else 'N':>2s} "
                  f"{'Y' if ss['weaken_active'] else 'N':>2s} "
                  f"{ss['debuff_bar_size']:>3d}")

            prev_sim_dmg = ss["cumulative_damage"]

    # Tune validity
    errors = sim_result.get("errors", [])
    if errors:
        print(f"\n--- Speed Tune Errors ({len(errors)}) ---")
        for e in errors[:10]:
            print(f"  {e}")


def main():
    parser = argparse.ArgumentParser(description="CB Sim Calibration Tool")
    parser.add_argument("--log", required=True, help="Path to battle log JSON file")
    parser.add_argument("--cb-element", default="void",
                        choices=["magic", "force", "spirit", "void"],
                        help="CB element for sim (default: void). Set to today's affinity.")
    parser.add_argument("--team", default="Maneater,Demytha,Ninja,Geomancer,Venomage",
                        help="Comma-separated hero names (default: Myth Eater team)")
    parser.add_argument("--no-force-affinity", action="store_true",
                        help="Disable FA damage caps (pre-defeat CB)")
    parser.add_argument("--max-cb-turns", type=int, default=50)
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.is_absolute():
        log_path = PROJECT_ROOT / log_path

    print(f"Extracting real data from: {log_path.name}")
    real_data = extract_real_data(log_path)
    print(f"  Boss turns: {real_data['boss_turns']}")
    print(f"  Total damage: {real_data['total_damage']:,}")
    print(f"  Team type_ids: {real_data['team_type_ids']}")

    team_names = [n.strip() for n in args.team.split(",")]
    cb_element = ELEMENT_MAP[args.cb_element]
    force_affinity = not args.no_force_affinity

    print(f"\nRunning sim: {', '.join(team_names)}")
    print(f"  CB element: {args.cb_element} ({cb_element})")
    print(f"  Force affinity: {force_affinity}")

    sim_result = run_sim_for_team(
        team_names, cb_element, force_affinity,
        max_cb_turns=args.max_cb_turns,
        use_current_gear=True,
    )

    calibrate(real_data, sim_result)


if __name__ == "__main__":
    main()
