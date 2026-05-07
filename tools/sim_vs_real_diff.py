"""Per-CB-turn buff-state diff between cb_sim and a real battle log.

Pulls the buff state of each champion at the END of every CB turn from
both sources and prints a side-by-side comparison. Used to debug the
"6 compensating wrongs" in the sim's survival model — without this we
can't tell whether removing a hack breaks calibration because of buff
timing, gear stats, or scheduler ordering.

Usage:
    python3 tools/sim_vs_real_diff.py [--log battle_logs_cb_latest.json]

Output: a table per CB turn showing each hero's buffs in real vs sim.
Discrepancies are flagged with `!!` so you can see immediately where
the sim drifts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# Buff-type-id → short label (matches real-game effect ids)
BUFF_LABELS = {
    320: "UK",
    100: "BkD",      # Block Debuffs
    60: "BD",        # Block Damage
    280: "Shi",      # Shield
    481: "Veil",     # Perfect Veil
    280: "Shi",
    250: "ContH",    # Continuous Heal
    20: "Atk+",      # Increase ATK
    21: "Def+",      # Increase DEF
    22: "Spd+",      # Increase SPD
    220: "CR+",      # Increase CR
    221: "CD+",      # Increase CD
}

# sim buff name → label so they line up visually
SIM_BUFF_LABELS = {
    "unkillable": "UK",
    "block_debuffs": "BkD",
    "block_damage": "BD",
    "shield": "Shi",
    "veil": "Veil",
    "cont_heal_15": "ContH",
    "inc_atk": "Atk+",
    "inc_def": "Def+",
    "inc_spd": "Spd+",
    "inc_cr": "CR+",
    "inc_cd": "CD+",
}

HERO_BY_TYPE_ID = {
    1070: "Maneater",
    6510: "Demytha",
    6200: "Ninja",
    4880: "Geomancer",
    6280: "Venomage",
}


def fmt_buffs_real(hero: dict) -> str:
    buffs = hero.get("buffs") or []
    if not buffs:
        return "—"
    return ",".join(
        f"{BUFF_LABELS.get(b['t'], 't'+str(b['t']))}/{b['d']}"
        for b in buffs
    )


def fmt_buffs_sim(c) -> str:
    if not c.buffs:
        return "—"
    return ",".join(
        f"{SIM_BUFF_LABELS.get(name, name[:5])}/{d}"
        for name, d in c.buffs.items()
    )


def real_per_cb_turn(log_path: Path) -> dict[int, dict[str, str]]:
    """Group snapshots by CB turn (boss-action interval), capture state
    at the boss-attack tick — that's when "did UK cover this turn?"
    becomes meaningful.

    The log's `turn` field is a global tick counter that increments per
    hero action. CB turn N starts after CB turn (N-1)'s boss action and
    ends at CB turn N's boss action.
    """
    with open(log_path) as f:
        data = json.load(f)
    log = data.get("log", [])

    # Identify boss-action ticks (active_hero==5).
    boss_ticks = [
        e["turn"] for e in log
        if isinstance(e, dict) and e.get("active_hero") == 5 and "turn" in e
    ]
    # Map tick → CB turn index (1-based).
    by_turn: dict[int, dict[str, str]] = {}
    for cb_idx, boss_tick in enumerate(boss_ticks, start=1):
        # Find the snapshot whose `turn` field == boss_tick — that's the
        # state right when the boss is about to attack.
        snap = next(
            (e for e in log
             if isinstance(e, dict) and e.get("turn") == boss_tick and "heroes" in e),
            None,
        )
        if not snap:
            continue
        per_hero = {}
        for h in snap["heroes"]:
            if h.get("side") != "player":
                continue
            nm = HERO_BY_TYPE_ID.get(h.get("type_id"), "?")
            per_hero[nm] = fmt_buffs_real(h)
        by_turn[cb_idx] = per_hero
    return by_turn


def sim_per_cb_turn(team_names: list[str], cb_element: int = 1,
                    max_turns: int = 50) -> dict[int, dict[str, str]]:
    """Capture per-CB-turn champion buff state from cb_sim. Uses
    run_potential_team for hero resolution so the user's primary
    Maneater (with full masteries + correct gear) is picked rather
    than a secondary inventory copy.
    """
    from cb_sim import run_potential_team
    from potential_team import build_potential_team, load_data

    data = load_data()
    tune = next(t for t in data["tunes"] if t["slug"] == "myth-eater")
    affinity_map = {1: "magic", 2: "force", 3: "spirit", 4: "void"}
    affinity = affinity_map.get(cb_element, "magic")
    pt = build_potential_team(tune, data, affinity)
    result = run_potential_team(
        pt, cb_element=cb_element, force_affinity=True,
        max_cb_turns=max_turns,
        generic_fillers=team_names[2:],  # fill 4:3 DPS / 1:1 DPS / 1:1 DPS slots
        projection=True,
    )
    by_turn: dict[int, dict[str, str]] = {}
    for snap in result.get("turn_snapshots", []):
        cb_t = snap.get("cb_turn")
        hb = snap.get("hero_buffs") or {}
        if cb_t is None:
            continue
        per_hero = {}
        for nm in team_names:
            buffs_dict = hb.get(nm, {})
            if not buffs_dict:
                per_hero[nm] = "—"
            else:
                per_hero[nm] = ",".join(
                    f"{SIM_BUFF_LABELS.get(name, name[:5])}/{d}"
                    for name, d in buffs_dict.items()
                )
        by_turn[cb_t] = per_hero
    return by_turn


def diff(real: dict, sim: dict, team_names: list[str], max_turn: int = 25):
    print(f"{'CB':>3} | " + " | ".join(f"{nm[:8]:^32s}" for nm in team_names))
    print("-" * (5 + (35) * len(team_names)))
    for t in range(1, max_turn + 1):
        r = real.get(t) or {}
        s = sim.get(t) or {}
        cells = []
        for nm in team_names:
            rb = r.get(nm, "—")
            sb = s.get(nm, "—")
            if rb == sb:
                cells.append(f"{rb:^32s}")
            else:
                cells.append(f"{rb}!!{sb}".center(32))
        print(f"{t:>3} | " + " | ".join(cells))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log", default="battle_logs_cb_latest.json")
    p.add_argument("--cb-element", type=int, default=1, help="1=Magic 2=Force 3=Spirit 4=Void")
    p.add_argument("--turns", type=int, default=25)
    args = p.parse_args()

    team = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
    real = real_per_cb_turn(ROOT / args.log)
    sim = sim_per_cb_turn(team, cb_element=args.cb_element, max_turns=args.turns)
    diff(real, sim, team, max_turn=args.turns)


if __name__ == "__main__":
    main()
