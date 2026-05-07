#!/usr/bin/env python3
"""Replay a real CB battle log against cb_sim and pinpoint cycle divergence.

The sim predicts 50-turn survival for a properly tuned team; reality often
dies earlier. This tool walks the real battle log hero-turn-by-hero-turn and
compares to the sim's predicted turn-order, flagging the first boss turn
where sim and real disagree on skill usage or protection state.

Output: table per boss turn showing real vs sim actions + first divergence.

Usage:
    python tools/cb_replay_diff.py [path/to/battle_logs_cb_*.json]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

SK_LOOKUP = {
    # Team heroes — expand as needed
    10701: ("Maneater", "A1"), 10702: ("Maneater", "A2"), 10703: ("Maneater", "A3"),
    65101: ("Demytha", "A1"), 65102: ("Demytha", "A2"), 65103: ("Demytha", "A3"),
    62001: ("Ninja", "A1"), 62002: ("Ninja", "A2"), 62003: ("Ninja", "A3"),
    48801: ("Geomancer", "A1"), 48802: ("Geomancer", "A2"), 48804: ("Geomancer", "A3"),
    62801: ("Venomage", "A1"), 62802: ("Venomage", "A2"), 62803: ("Venomage", "A3"),
}
NAME_BY_TYPE = {1070: "Maneater", 6510: "Demytha", 6200: "Ninja", 4880: "Geomancer", 6280: "Venomage"}


def extract_real_casts(log_path):
    """Walk a battle log and extract (bt, hero, skill) casts via rdy flips."""
    data = json.loads(Path(log_path).read_text())
    entries = data.get("log", []) if isinstance(data, dict) else []
    last_rdy = {}
    casts = []  # (bt, hero, skill)
    boss_turn = 0
    for e in entries:
        if not isinstance(e, dict) or not e.get("heroes"):
            continue
        # Update boss turn from enemy entry
        for h in e["heroes"]:
            if h.get("side") == "enemy":
                boss_turn = h.get("turn_n", boss_turn) or boss_turn
                break
        for h in e["heroes"]:
            if h.get("side") != "player":
                continue
            slot = h.get("id")
            for sk in h.get("sk") or []:
                tid = sk.get("t")
                if tid not in SK_LOOKUP:
                    continue
                rdy = bool(sk.get("rdy", False))
                prev = last_rdy.get((slot, tid))
                if prev is True and rdy is False:
                    casts.append((boss_turn, *SK_LOOKUP[tid]))
                last_rdy[(slot, tid)] = rdy
    # Dedupe consecutive duplicates
    dedup = []
    for c in casts:
        if not dedup or c != dedup[-1]:
            dedup.append(c)
    return dedup, data


def run_sim_and_extract():
    """Run cb_sim on the team from the real log and return sim's cast list."""
    from cb_sim import CBSimulator, build_champion_minimal
    from dashboard_server import (
        build_cb_last_run, _load_battle_log, _hero_type_to_name, _fetch_all_heroes,
    )
    real = build_cb_last_run()
    team_rows = (real or {}).get("team") or []
    boss = (real or {}).get("boss") or {}
    cb_element = boss.get("element") or 4
    # HPs from log
    log = _load_battle_log() or {}
    hp_by_name = {}
    for e in (log.get("log") or [])[:40]:
        if not isinstance(e, dict) or not e.get("heroes"):
            continue
        for h in e["heroes"]:
            if h.get("side") != "player":
                continue
            nm = _hero_type_to_name().get(h.get("type_id"))
            if nm:
                hp_by_name[nm] = max(hp_by_name.get(nm, 0), int(h.get("hp_max") or 0))
    all_h = _fetch_all_heroes() or []
    elem_by_name = {h.get("name"): (h.get("element") or 4) for h in all_h}
    champs = []
    for i, h in enumerate(team_rows, start=1):
        nm = h.get("name")
        champs.append(build_champion_minimal(
            name=nm, position=i, speed=h.get("spd") or 100,
            hp=hp_by_name.get(nm) or 30000, defense=h.get("def") or 1000,
            element=elem_by_name.get(nm, 4),
        ))
    sim = CBSimulator(champs, cb_speed=190, cb_element=cb_element,
                      deterministic=True, model_survival=True)
    res = sim.run(max_cb_turns=0)
    # Convert timeline to (bt, hero, skill)
    sim_casts = []
    for ev in res.get("timeline", []):
        if ev.get("kind") == "hero_cast":
            sim_casts.append((ev.get("cb_turn", 0), ev.get("hero"), ev.get("skill")))
    return sim_casts, res


def diff(real_casts, sim_casts, max_rows=60):
    """Side-by-side per-BT comparison. Prints first divergence clearly."""
    real_by_bt = defaultdict(list)
    for bt, h, s in real_casts:
        real_by_bt[bt].append((h, s))
    sim_by_bt = defaultdict(list)
    for bt, h, s in sim_casts:
        sim_by_bt[bt].append((h, s))

    # Dedupe per BT (same hero/skill twice = multi-turn; keep ordered)
    all_bts = sorted(set(real_by_bt) | set(sim_by_bt))
    print(f"{'BT':>3}  {'REAL':<50}  {'SIM':<50}")
    print(f"{'-'*3}  {'-'*50}  {'-'*50}")
    first_div = None
    for bt in all_bts[:max_rows]:
        r = ", ".join(f"{h} {s}" for h, s in real_by_bt.get(bt, []))
        s = ", ".join(f"{h} {s}" for h, s in sim_by_bt.get(bt, []))
        match = real_by_bt.get(bt, []) == sim_by_bt.get(bt, [])
        marker = "" if match else " <-- DIFF"
        if not match and first_div is None:
            first_div = bt
        print(f"T{bt:>2}  {r[:50]:<50}  {s[:50]:<50}{marker}")
    print()
    if first_div is not None:
        print(f"First divergence: BT {first_div}")
    else:
        print("Full match within compared turns.")


def main():
    p = argparse.ArgumentParser(description="Replay diff: real CB log vs cb_sim")
    p.add_argument("log", nargs="?", help="Path to battle_logs_cb_*.json (default: most recent)")
    p.add_argument("--max-turns", type=int, default=60)
    args = p.parse_args()

    # Pick the most recent battle log if not specified
    if args.log:
        log_path = Path(args.log)
    else:
        logs = sorted(ROOT.glob("battle_logs_cb_*.json"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        logs = [p for p in logs if p.name != "battle_logs_cb_latest.json"]
        if not logs:
            print("No battle logs found.")
            return 1
        log_path = logs[0]
        print(f"Using most recent log: {log_path.name}\n")

    real_casts, _ = extract_real_casts(log_path)
    sim_casts, _ = run_sim_and_extract()
    diff(real_casts, sim_casts, max_rows=args.max_turns)
    return 0


if __name__ == "__main__":
    sys.exit(main())
