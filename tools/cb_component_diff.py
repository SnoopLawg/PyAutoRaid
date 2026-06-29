"""Per-hero PER-COMPONENT real-vs-sim damage diff (direct / WM / DoT).

`cb_attribution_diff.py` compares per-hero TOTALS, which can hide compensating
errors inside a hero (e.g. direct under + Warmaster over that cancel). This
tool splits each hero's damage into its components and compares each one, so a
stacked pair of compensating wrongs is visible instead of netting to a small
total.

How the real split works (from the tick log, hero -> boss target=5):
  - kind_id 6000 is BOTH direct hits AND the Warmaster/Giant-Slayer flat proc.
    The game folds them into the same bucket, but the WM proc is a distinct
    event with `calc_raw == 75000` (the flat cap, pre-mitigation). So:
        real WM     = sum(dealt) where kind_id==6000 and calc_raw==75000
        real direct = sum(dealt) where kind_id==6000 and calc_raw!=75000
  - kind_id 3007 = poison, 3014 = HP burn, 4017 = deflect, 3021 = firemark.

Sim split comes from each SimChampion DamageTracker (direct / wm_gs / poison /
hp_burn / passive). real WM <-> sim wm_gs; real direct <-> sim direct; real
deflect+firemark <-> sim passive.

GROUNDED FINDING 2026-06-29 (task #35): on 090946 (Spirit) the sim
under-attributes DIRECT ~42% team-wide and over-attributes WARMASTER ~4x. DEF
mitigation is confirmed exact (#32), so direct-under is crit / effective-ATK /
Escalation / cast-count, NOT mitigation. The two must be un-stacked TOGETHER
(lowering WM alone drops the total; it is currently propping up direct-under).

Usage:
    python tools/cb_component_diff.py 20260629_090946
    python tools/cb_component_diff.py 20260629_090946 --cb-element 3
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# The Warmaster/Giant-Slayer flat proc, pre-mitigation. 75000 = base cap on UNM;
# 93750 = 75000 x 1.25 when the boss is Weakened (game-truth: WM IS multiplied by
# Weaken — calc_raw 93750 vs 75000 proves the x1.25). BOTH must be isolated or the
# Weaken-boosted procs (the majority, given ~98% Weaken uptime) get misclassified
# as direct, falsely inflating real direct and deflating real WM (the cause of the
# bogus "+320% WM / -42% direct" split seen 2026-06-29 before this fix).
WM_FLAT_CALC_RAW = {75000, 93750}
DEFAULT_TEAM = "Maneater,Demytha,Ninja,Geomancer,Venomage"


def real_components(ts: str, team: list[str]) -> dict:
    d = json.loads((ROOT / f"tick_log_cb_{ts}.json").read_text(encoding="utf-8"))
    ticks = d.get("ticks") or d
    idx = {i: n for i, n in enumerate(team)}
    out = {n: defaultdict(float) for n in team}
    counts = {n: defaultdict(int) for n in team}
    for e in ticks:
        if not (isinstance(e, dict) and e.get("kind") == "damage"
                and e.get("target") == 5):
            continue
        p = e.get("producer")
        if p not in idx:
            continue
        n = idx[p]
        kid = e.get("kind_id")
        dealt = e.get("dealt") or 0
        if kid == 6000:
            if (e.get("calc_raw") or 0) in WM_FLAT_CALC_RAW:
                out[n]["wm"] += dealt
                counts[n]["wm"] += 1
            else:
                out[n]["direct"] += dealt
                counts[n]["direct"] += 1
        elif kid == 3007:
            out[n]["poison"] += dealt
        elif kid == 3014:
            out[n]["hp_burn"] += dealt
        elif kid in (4017, 3021):
            out[n]["passive"] += dealt
    return out, counts


def sim_components(team: list[str], cb_element: int, ts: str) -> dict:
    from cb_calibrate import run_sim_for_team
    preset = ROOT / f"presets_cb_{ts}.json"
    build = ROOT / f"build_cb_{ts}.json"
    res = run_sim_for_team(
        team, cb_element=cb_element, force_affinity=True, max_cb_turns=50,
        use_preset=True,
        preset_snapshot_path=str(preset) if preset.exists() else None,
        build_snapshot_path=str(build) if build.exists() else None,
    )
    out = {}
    for h in res.get("heroes", []):
        out[h["name"]] = {
            "direct": h.get("direct", 0.0), "wm": h.get("wm_gs", 0.0),
            "hp_burn": h.get("hp_burn", 0.0), "poison": h.get("poison", 0.0),
            "passive": h.get("passive", 0.0), "total": h.get("total", 0.0),
        }
    out["_cb_turns"] = res.get("cb_turns")
    return out


def _detect_element(ts: str) -> int:
    from collections import Counter
    try:
        d = json.loads((ROOT / f"tick_log_cb_{ts}.json").read_text(encoding="utf-8"))
        ticks = d.get("ticks") or d
        c = Counter(e.get("t_elem") for e in ticks
                    if isinstance(e, dict) and e.get("kind") == "damage"
                    and e.get("target") == 5 and e.get("t_elem"))
        return c.most_common(1)[0][0] if c else 4
    except Exception:
        return 4


COMPONENTS = ["direct", "wm", "hp_burn", "poison", "passive"]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("timestamp")
    ap.add_argument("--cb-element", type=int, default=None,
                    help="1=Magic 2=Force 3=Spirit 4=Void (default: read tick log)")
    ap.add_argument("--team", default=DEFAULT_TEAM)
    args = ap.parse_args()
    team = [t.strip() for t in args.team.split(",")]
    ts = args.timestamp
    elem = args.cb_element if args.cb_element is not None else _detect_element(ts)

    real, counts = real_components(ts, team)
    sim = sim_components(team, elem, ts)
    print(f"=== Component diff {ts} (cb_element={elem}, sim cb_turns="
          f"{sim.get('_cb_turns')}) ===\n")

    comp_tot = {c: [0.0, 0.0] for c in COMPONENTS}
    for n in team:
        r, s = real[n], sim.get(n, {})
        print(f"-- {n}  (real WM procs={counts[n]['wm']}, "
              f"direct hits={counts[n]['direct']})")
        for c in COMPONENTS:
            rv, sv = r.get(c, 0.0), s.get(c, 0.0)
            if rv == 0 and sv == 0:
                continue
            comp_tot[c][0] += rv
            comp_tot[c][1] += sv
            dp = (sv - rv) / rv * 100 if rv else float("inf")
            print(f"   {c:>9} {rv:>12,.0f} {sv:>12,.0f} {sv-rv:>+12,.0f} {dp:>+7.1f}%")
        rt = sum(r.values())
        st = s.get("total", 0.0)
        print(f"   {'TOTAL':>9} {rt:>12,.0f} {st:>12,.0f} {st-rt:>+12,.0f} "
              f"{(st-rt)/rt*100 if rt else 0:>+7.1f}%\n")

    print("=== TEAM by component (the un-stack view) ===")
    for c in COMPONENTS:
        rv, sv = comp_tot[c]
        if rv == 0 and sv == 0:
            continue
        dp = (sv - rv) / rv * 100 if rv else float("inf")
        print(f"  {c:>9} real {rv:>13,.0f}  sim {sv:>13,.0f}  {sv-rv:>+13,.0f} {dp:>+7.1f}%")


if __name__ == "__main__":
    main()
