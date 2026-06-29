"""Per-hero / per-source damage attribution diff: real fixture vs cb_sim.

Spirit-day MEN is the calibrated-total baseline, so a per-hero divergence
isolates an attribution bug (a hero/source the sim over- or under-credits)
rather than a global scaling error. This is the tool for tasks #10/#11.

Real damage comes from the tick log (`tick_log_cb_<ts>.json`, key `ticks`),
aggregated by `producer` (hero slot 0-4 hitting boss target 5) and split by
`kind_id`:
    6000  direct hit (includes WM/GS bonus, which the game folds into the hit)
    3007  ContinuousDamage  = Poison   (CB-capped 50K/tick)
    3014  AoEContinuousDamage = HP Burn
    3021  FireMark          = Brimstone/Smite blessing (CB-capped 250K)
    4017  PassiveReflectDamage = Stoneguard-style deflect (CB-capped 75K)

Sim damage comes from each SimChampion's DamageTracker (direct/poison/
hp_burn/wm_gs/passive). Note the real `6000` bucket = sim `direct + wm_gs`
(the game doesn't separate WM/GS), and real `4017`/`3021` map to sim
`passive`.

Usage:
    python3 tools/cb_attribution_diff.py <timestamp> [--cb-element N]
    python3 tools/cb_attribution_diff.py 20260623_162050 --cb-element 3
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

KIND_LABEL = {
    6000: "direct", 3007: "poison", 3014: "hp_burn",
    3021: "firemark(brimstone)", 4017: "deflect", 80: "poison", 470: "hp_burn",
}


def real_per_hero(ts: str, team: list[str]) -> dict:
    p = ROOT / f"tick_log_cb_{ts}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    ticks = d.get("ticks") or d.get("events") or (d if isinstance(d, list) else [])
    idx_to_name = {i: n for i, n in enumerate(team)}
    out = {n: defaultdict(float) for n in team}
    for e in ticks:
        if not isinstance(e, dict) or e.get("kind") != "damage":
            continue
        p_i, t_i = e.get("producer"), e.get("target")
        if p_i in idx_to_name and t_i == 5:
            out[idx_to_name[p_i]][e.get("kind_id")] += (e.get("dealt") or 0)
    return out


def sim_per_hero(team: list[str], cb_element: int, ts: str) -> dict:
    """Run the sim against the fixture's CAPTURED build + preset (not current
    gear) so the comparison is valid. Using current gear was a bug: gear drifts
    after capture, so the sim ran a different ATK/SPD/HP than the real battle ->
    spurious deltas + early death. The build snapshot (build_cb_<ts>.json) is
    the same one run_sim_for_team replays for calibration."""
    from cb_calibrate import run_sim_for_team
    preset_path = ROOT / f"presets_cb_{ts}.json"
    build_path = ROOT / f"build_cb_{ts}.json"
    if not build_path.exists():
        print(f"  WARN: no build_cb_{ts}.json — sim runs CURRENT gear, deltas "
              f"are NOT a valid attribution comparison (gear drift).",
              file=sys.stderr)
    res = run_sim_for_team(
        team, cb_element=cb_element, force_affinity=True, max_cb_turns=50,
        use_preset=True,
        preset_snapshot_path=str(preset_path) if preset_path.exists() else None,
        build_snapshot_path=str(build_path) if build_path.exists() else None,
    )
    out = {}
    for h in res.get("heroes", []):
        out[h["name"]] = {
            "direct": h.get("direct", 0.0), "poison": h.get("poison", 0.0),
            "hp_burn": h.get("hp_burn", 0.0), "wm_gs": h.get("wm_gs", 0.0),
            "passive": h.get("passive", 0.0), "total": h.get("total", 0.0),
        }
    out["_cb_turns"] = res.get("cb_turns")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("timestamp")
    ap.add_argument("--cb-element", type=int, default=None,
                    help="1=Magic 2=Force 3=Spirit 4=Void (default: read from battle log)")
    ap.add_argument("--team", default="Maneater,Demytha,Ninja,Geomancer,Venomage")
    args = ap.parse_args()
    team = [t.strip() for t in args.team.split(",")]
    ts = args.timestamp

    elem = args.cb_element
    if elem is None:
        # GROUND TRUTH: read the boss's in-battle element from the tick log
        # damage events (t_elem on hero->boss hits). battle_logs `boss_element`
        # is often null/wrong (it defaulted to 4=Void, which made 090946/112351
        # — actually SPIRIT, t_elem=3 — calibrate at the wrong affinity). The CB
        # boss is Void only below 50% HP, which the MEN team never reaches, so the
        # in-battle element is the day's affinity, captured per-hit here.
        from collections import Counter
        try:
            d = json.loads((ROOT / f"tick_log_cb_{ts}.json").read_text(encoding="utf-8"))
            ticks = d.get("ticks") or d
            c = Counter(e.get("t_elem") for e in ticks
                        if isinstance(e, dict) and e.get("kind") == "damage"
                        and e.get("target") == 5 and e.get("t_elem"))
            elem = c.most_common(1)[0][0] if c else None
        except Exception:
            elem = None
        if elem is None:
            try:
                bl = json.loads((ROOT / f"battle_logs_cb_{ts}.json").read_text(encoding="utf-8"))
                elem = bl.get("boss_element") or 4
            except Exception:
                elem = 4
        print(f"  [element] in-battle boss element = {elem} "
              f"(1=Magic 2=Force 3=Spirit 4=Void), from tick-log t_elem")

    real = real_per_hero(ts, team)
    sim = sim_per_hero(team, elem, ts)

    print(f"=== Attribution diff {ts} (cb_element={elem}) ===\n")
    rt = st = 0.0
    print(f"{'hero':10s} {'real':>12s} {'sim':>12s} {'delta':>12s} {'delta%':>8s}   real-by-kind")
    for n in team:
        r = sum(real[n].values())
        s = sim.get(n, {}).get("total", 0)
        rt += r; st += s
        dpct = (s - r) / r * 100 if r else 0
        kinds = ", ".join(f"{KIND_LABEL.get(k, k)}={v:,.0f}"
                          for k, v in sorted(real[n].items(), key=lambda x: -x[1]))
        print(f"  {n:10s} {r:>12,.0f} {s:>12,.0f} {s-r:>+12,.0f} {dpct:>+7.1f}%   {kinds}")
    print(f"  {'TOTAL':10s} {rt:>12,.0f} {st:>12,.0f} {st-rt:>+12,.0f} "
          f"{(st-rt)/rt*100 if rt else 0:>+7.1f}%")
    print()
    # Flag the biggest per-hero gaps.
    gaps = sorted(((n, sum(real[n].values()), sim.get(n, {}).get("total", 0))
                   for n in team), key=lambda x: abs(x[2] - x[1]), reverse=True)
    print("Biggest per-hero attribution gaps (fix priority):")
    for n, r, s in gaps[:3]:
        d = "UNDER" if s < r else "OVER"
        print(f"  {n}: sim {d} by {abs(s-r):,.0f} ({(s-r)/r*100 if r else 0:+.1f}%)")


if __name__ == "__main__":
    main()
