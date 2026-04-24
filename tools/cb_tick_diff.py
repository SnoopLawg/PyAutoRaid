#!/usr/bin/env python3
"""Diff real per-tick TM + cast data against cb_sim predictions.

Real data: tick_log_*.json saved by cb_tick_capture.py.
Sim data: run cb_sim with the same team and record its predicted cast
sequence per hero per boss-turn.

Output: side-by-side table of casts-per-BT for each hero, highlighting
where real and sim diverge. That's the exact boss-turn we need to look
at to find our sync error.

Usage:
    python3 tools/cb_tick_diff.py tick_log_bt20_*.json
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


DEFAULT_ID_MAP = {
    0: "Maneater", 1: "Demytha", 2: "Ninja",
    3: "Geomancer", 4: "Venomage", 5: "Boss",
}


def real_casts_per_bt(tick_file):
    """Return {hero_name: {bt: num_casts}} from the captured tick log.

    A "cast" is detected by turn_n (tn) incrementing between two snapshots.
    We bucket each cast into the boss_tn at the time of the cast.
    """
    data = json.loads(Path(tick_file).read_text())
    id_map_str = data.get("id_map", {})
    id_map = {int(k): v for k, v in id_map_str.items()}
    if not id_map:
        id_map = DEFAULT_ID_MAP
    ticks = data.get("ticks", [])

    # Track prev tn per hero id
    last_tn = {}
    result = defaultdict(lambda: defaultdict(int))
    for entry in ticks:
        # Find boss_tn in this entry
        boss_tn = 0
        for u in entry.get("units", []):
            if u.get("s") == "e":
                boss_tn = u.get("tn", 0) or 0
        for u in entry.get("units", []):
            uid = u.get("id")
            tn = u.get("tn", 0) or 0
            prev = last_tn.get(uid, tn)
            if tn > prev:
                # Hero cast between prev and now. Attribute to boss_tn.
                name = id_map.get(uid, f"id{uid}")
                # Casts happen DURING the current boss window: boss_tn is
                # the boss's last-known turn_n, so BT = boss_tn.
                result[name][boss_tn] += (tn - prev)
            last_tn[uid] = tn
    return result


def sim_casts_per_bt_tune(tune_id, team, cb_element, spd_overrides=None):
    """Run sim with tune-aware config (openings + priorities) and return {hero: {bt: casts}}."""
    from cb_sim import run_tune
    from collections import defaultdict
    res = run_tune(tune_id, team, cb_element=cb_element, force_affinity=True,
                   spd_override=spd_overrides)
    result = defaultdict(lambda: defaultdict(int))
    cur_bt = 0
    for ev in res.get("timeline", []):
        kind = ev.get("kind")
        if kind == "cb_action":
            cur_bt = ev.get("cb_turn", 0)
        elif kind == "hero_cast":
            nm = ev.get("hero")
            if nm:
                result[nm][cur_bt] += 1
    return result, res


def sim_casts_per_bt(team=None, cb_element=4, cb_speed=190, spd_overrides=None):
    """Run cb_sim and return {hero_name: {bt: num_casts}}."""
    from cb_sim import CBSimulator, build_champion_minimal

    # Use current-gear team if possible via cb_calibrate; fall back to defaults
    if team is None:
        team = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]

    # Build with REAL gear-computed stats (critical for SPD accuracy)
    from cb_optimizer import calc_stats
    heroes_data = json.loads((ROOT / "heroes_6star.json").read_text())["heroes"]
    hero_by_name = {}
    for h in heroes_data:
        if h.get("name") not in hero_by_name:
            hero_by_name[h["name"]] = h
    account = {"GreatHall": {}, "AcademyBonuses": {}, "Blessings": {}}
    champs = []
    for i, nm in enumerate(team, start=1):
        h = hero_by_name.get(nm)
        if not h:
            print(f"WARN: hero {nm} not in heroes_6star.json", file=sys.stderr)
            continue
        stats = calc_stats(h, h.get("artifacts", []), account)
        spd = int(round(stats.get(4, 100)))
        if spd_overrides and nm in spd_overrides:
            spd = int(round(spd_overrides[nm]))
        champs.append(build_champion_minimal(
            name=nm, position=i,
            speed=spd,
            hp=int(round(stats.get(1, 40000))),
            defense=int(round(stats.get(3, 1000))),
            element=h.get("element", 4),
        ))
        src = " (OVERRIDE)" if spd_overrides and nm in spd_overrides else ""
        print(f"  {nm}: SPD={spd}{src} HP={int(round(stats.get(1,40000)))} DEF={int(round(stats.get(3,1000)))}")

    sim = CBSimulator(champs, cb_speed=cb_speed, cb_element=cb_element,
                      deterministic=True, model_survival=True)
    res = sim.run(max_cb_turns=50)
    result = defaultdict(lambda: defaultdict(int))
    cur_bt = 0
    for ev in res.get("timeline", []):
        kind = ev.get("kind")
        if kind == "cb_action":
            cur_bt = ev.get("cb_turn", 0)
        elif kind == "hero_cast":
            nm = ev.get("hero")
            if nm:
                result[nm][cur_bt] += 1
    return result


def diff_table(real, sim, max_bt=25):
    heroes = sorted(set(real) | set(sim))
    bts = range(0, max_bt + 1)
    header = f"{'BT':>3} | " + " | ".join(f"{h[:9]:<9}" for h in heroes)
    print(header)
    print("-" * len(header))
    totals_real = defaultdict(int)
    totals_sim = defaultdict(int)
    total_mismatch = 0
    for bt in bts:
        cells = []
        for h in heroes:
            r = real.get(h, {}).get(bt, 0)
            s = sim.get(h, {}).get(bt, 0)
            totals_real[h] += r
            totals_sim[h] += s
            if r == 0 and s == 0:
                cells.append(" " * 9)
            elif r == s:
                cells.append(f"{r}         ")
            else:
                d = r - s
                cells.append(f"{r}/{s} {d:+d}  ")
                total_mismatch += abs(d)
        print(f"{bt:>3} | " + " | ".join(c[:9] for c in cells))
    print()
    print(f"{'TOT':>3} | " + " | ".join(f"{totals_real[h]}/{totals_sim[h]:<5}"[:9] for h in heroes))
    print(f"\nTotal cast mismatches (sum |real-sim| per BT): {total_mismatch}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tick_file", help="tick_log_*.json from cb_tick_capture.py")
    p.add_argument("--cb-element", default="force",
                   choices=["magic", "force", "spirit", "void"])
    p.add_argument("--spd-overrides", help="JSON file with {hero: {inferred_spd: n}} (e.g. team_spd_real.json)")
    p.add_argument("--tune", help="Tune id (e.g. myth_eater) — uses real openings + priorities")
    p.add_argument("--team", default="Maneater,Demytha,Ninja,Geomancer,Venomage")
    args = p.parse_args()

    elem = {"magic": 1, "force": 2, "spirit": 3, "void": 4}[args.cb_element]
    overrides = None
    if args.spd_overrides:
        data = json.loads(Path(args.spd_overrides).read_text())
        overrides = {k: v.get("inferred_spd") for k, v in data.items() if isinstance(v, dict)}
    real = real_casts_per_bt(args.tick_file)
    sim_meta = None
    if args.tune:
        team = [n.strip() for n in args.team.split(",")]
        sim, sim_meta = sim_casts_per_bt_tune(args.tune, team, elem, spd_overrides=overrides)
    else:
        sim = sim_casts_per_bt(cb_element=elem, spd_overrides=overrides)
    print(f"Real casts per BT ({Path(args.tick_file).name}):")
    print(f"Sim assumes cb_element={args.cb_element}{' tune='+args.tune if args.tune else ''}")
    if sim_meta:
        print(f"Sim total dmg: {sim_meta.get('total',0):,.0f}  valid={'no' if sim_meta.get('errors') else 'yes'}")
        for e in sim_meta.get('errors', [])[:3]:
            print(f"  ! {e}")
    print()
    diff_table(real, sim)
    return 0


if __name__ == "__main__":
    sys.exit(main())
