#!/usr/bin/env python3
"""Compare real per-hero TM progression against cb_sim's predicted progression.

Raid battle logs include `tm` on every hero snapshot. We walk those snapshots
and extract (poll, hero, tm) for each player hero + the boss. Then we run
cb_sim and record its synthetic "ticks" for the same heroes. Aligning the
two by boss-turn milestones lets us see exactly where Maneater (or anyone)
starts acting later than the sim predicts — which pins down the TM sync
drift the user has observed.

Usage:
    python tools/cb_tm_diff.py [path/to/battle_logs_cb_*.json]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

NAME_BY_TYPE = {1070: "Maneater", 6510: "Demytha", 6200: "Ninja",
                4880: "Geomancer", 6280: "Venomage"}


def extract_real_tm(log_path):
    """Per-hero turn_n progression from a real battle log, keyed by boss-turn.

    Returns: {hero_name: {boss_turn: hero_turn_n}} plus boss turn_n per boss
    turn (trivially equal).
    """
    data = json.loads(Path(log_path).read_text())
    entries = data.get("log", []) if isinstance(data, dict) else []
    real = defaultdict(dict)  # hero_name -> {bt: turn_n}
    for e in entries:
        if not isinstance(e, dict) or not e.get("heroes"):
            continue
        # Find boss turn_n in this snapshot
        boss_tn = 0
        for h in e["heroes"]:
            if h.get("side") == "enemy":
                boss_tn = h.get("turn_n", 0) or 0
                break
        for h in e["heroes"]:
            if h.get("side") != "player":
                continue
            nm = NAME_BY_TYPE.get(h.get("type_id"))
            if not nm:
                continue
            tn = h.get("turn_n", 0) or 0
            prev = real[nm].get(boss_tn, 0)
            if tn > prev:
                real[nm][boss_tn] = tn
    return real


def run_sim_tm():
    """Run cb_sim and return {hero_name: {boss_turn: hero_turn_n}}."""
    from cb_sim import CBSimulator, build_champion_minimal
    from dashboard_server import (
        build_cb_last_run, _load_battle_log, _hero_type_to_name, _fetch_all_heroes,
    )
    real_info = build_cb_last_run()
    team_rows = (real_info or {}).get("team") or []
    boss = (real_info or {}).get("boss") or {}
    cb_element = boss.get("element") or 4

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
    res = sim.run(max_cb_turns=50)
    # Real battle-log snapshots show hero.turn_n AT a moment when boss.turn_n=N.
    # That measurement captures hero actions BEFORE boss did turn N AND after,
    # up until the snapshot poll. To align with the real log's convention, we
    # record the cumulative count at the END of each BT interval (right before
    # the NEXT cb_action fires). That's what real logs see after polling into
    # boss.turn_n = N (heroes have already taken their post-boss-N-1 turns).
    sim = defaultdict(dict)  # hero -> {bt: cumulative_turns}
    cumul = defaultdict(int)
    last_cb_turn = 0
    for ev in res.get("timeline", []):
        if ev.get("kind") == "hero_cast":
            cumul[ev.get("hero")] += 1
        elif ev.get("kind") == "cb_action":
            cb_bt = ev.get("cb_turn")
            # The hero casts between the previous cb_action and this one
            # belonged to BT = (cb_bt - 1). Lock in their cumul at that BT.
            bt_to_record = cb_bt - 1
            if bt_to_record >= 0:
                for hero in champs:
                    sim[hero.name][bt_to_record] = cumul.get(hero.name, 0)
            last_cb_turn = cb_bt
    # Also record the final state under the last cb_turn seen (if any)
    for hero in champs:
        sim[hero.name][last_cb_turn] = cumul.get(hero.name, 0)
    return sim


def diff(real, sim, heroes=None):
    heroes = heroes or sorted(set(real) | set(sim))
    all_bts = sorted(set(bt for h in heroes for bt in real.get(h, {})))[:30]
    # Print table
    print(f"{'BT':>3}  " + "  ".join(f"{h[:6]:>12s}" for h in heroes))
    print("-" * (5 + 14 * len(heroes)))
    for bt in all_bts:
        row = [f"T{bt:>2}"]
        for h in heroes:
            r = real.get(h, {}).get(bt)
            s = sim.get(h, {}).get(bt)
            if r is None and s is None:
                row.append(" " * 12)
            elif r is None:
                row.append(f" sim={s:>3}   ".rjust(12))
            elif s is None:
                row.append(f"real={r:>3}   ".rjust(12))
            else:
                delta = r - s
                mark = "" if delta == 0 else f" {delta:+d}"
                row.append(f"{r:>3}/{s:<3}{mark}".rjust(12))
        print("  ".join(row))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("log", nargs="?")
    args = p.parse_args()
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
        print(f"Using: {log_path.name}\n")

    real = extract_real_tm(log_path)
    sim = run_sim_tm()
    print("Per-hero turn_n by boss turn (real / sim  +delta):")
    print()
    diff(real, sim, heroes=["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"])
    print()
    # Cumulative drift summary per hero
    print("Cumulative drift (real turns - sim turns) at each BT:")
    for h in ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]:
        bts = sorted(real.get(h, {}))
        drifts = []
        for bt in bts:
            r = real[h][bt]
            s = sim.get(h, {}).get(bt, r)
            drifts.append(r - s)
        if drifts:
            print(f"  {h:10s} drift trajectory: {drifts[:20]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
