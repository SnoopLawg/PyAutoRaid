"""Compare per-hero turn cadence between sim and real battle log per BT.

If sim and real have the same UK/BD coverage divergence but similar total
damage, the heroes are casting at different cb_turns. This tool shows
exactly that: how many turns each hero has taken at each boss turn,
side by side.

Usage:
    python3 tools/turn_cadence_diff.py battle_logs_cb_<ts>.json \\
        --cb-element magic --preset-snapshot presets_cb_<ts>.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def extract_real_cadence(log_path: Path) -> dict[int, dict[int, int]]:
    """Return {boss_turn: {hero_type_id: max turn_n observed}}.

    Real battle log: each poll entry has `heroes[]` with `turn_n` per
    unit. We take the MAX per (BT, hero) since one BT spans several
    polls and turn_n only increments.
    """
    d = json.loads(log_path.read_text(encoding="utf-8"))
    out: dict[int, dict[int, int]] = {}
    for e in d.get("log", []):
        if "poll" not in e or "heroes" not in e:
            continue
        bt = None
        for h in e["heroes"]:
            if h.get("side") == "enemy":
                bt = h.get("turn_n")
                break
        if bt is None or bt < 0:
            continue
        slot = out.setdefault(bt, {})
        for h in e["heroes"]:
            if h.get("side") != "player":
                continue
            tid = h.get("type_id")
            tn = h.get("turn_n", 0) or 0
            slot[tid] = max(slot.get(tid, 0), tn)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("battle_log")
    ap.add_argument("--cb-element", default="magic",
                    choices=["magic", "force", "spirit", "void"])
    ap.add_argument("--max-turns", type=int, default=50)
    ap.add_argument("--preset-snapshot",
                    help="Path to presets_cb_<ts>.json captured with this fixture.")
    args = ap.parse_args()
    elem_map = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
    cb_element_int = elem_map[args.cb_element]

    log_path = Path(args.battle_log)
    if not log_path.exists():
        print(f"file not found: {log_path}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    from cb_calibrate import extract_real_data, run_sim_for_team

    real_cadence = extract_real_cadence(log_path)
    print(f"# Real: {len(real_cadence)} boss turns")

    real_data = extract_real_data(log_path)
    type_id_to_name = {
        1070: "Maneater", 1076: "Maneater",
        6510: "Demytha", 6516: "Demytha",
        6200: "Ninja", 6206: "Ninja",
        4880: "Geomancer", 4886: "Geomancer",
        6280: "Venomage", 6286: "Venomage",
    }
    team = []
    tid_to_name = {}
    for tid in real_data.get("team_type_ids", []):
        n = type_id_to_name.get(tid)
        if n and n not in team:
            team.append(n)
            tid_to_name[tid] = n
    print(f"# Team: {team}")

    sim = run_sim_for_team(team, cb_element=cb_element_int,
                           force_affinity=True, max_cb_turns=50,
                           use_preset=True,
                           preset_snapshot_path=args.preset_snapshot)
    snapshots = sim.get("turn_snapshots", [])
    print(f"# Sim: cb_turns={sim['cb_turns']}, total={sim['total']:,.0f}")
    if args.preset_snapshot:
        print(f"# Preset: {args.preset_snapshot}")
    else:
        print(f"# Preset: live mod (NOT snapshot — may not match fixture)")
    print()

    # Build hero-id ordering from first real BT
    first_bt = min(real_cadence.keys()) if real_cadence else 0
    real_hids = list(real_cadence.get(first_bt, {}).keys())[:len(team)]

    print(f"{'BT':>3}  " + "  ".join(f"{n[:7]:>7}/{n[:7]:>7}" for n in team) + "  Note")
    print(f"{'':>3}  " + "  ".join(f"{'real':>7}/{'sim':>7}" for _ in team))
    print("-" * (5 + 17 * len(team) + 10))

    sim_by_bt = {s["cb_turn"]: s for s in snapshots}
    max_bt = min(args.max_turns,
                  max(max(real_cadence.keys(), default=0),
                      max(sim_by_bt.keys(), default=0)))

    drift = {n: 0 for n in team}
    for bt in range(1, max_bt + 1):
        rr = real_cadence.get(bt, {})
        ss = sim_by_bt.get(bt) or {}
        cells = []
        delta_str = ""
        for tid, name in zip(real_hids, team):
            r_t = rr.get(tid, 0)
            s_t = (ss.get("hero_turns") or {}).get(name, 0)
            cells.append(f"{r_t:>7d}/{s_t:>7d}")
            d = s_t - r_t
            drift[name] = d
            if d != 0:
                delta_str += f" {name[:3]}{'+' if d>0 else ''}{d}"
        print(f"{bt:>3}  " + "  ".join(cells) + ("  " + delta_str if delta_str else ""))

    # Final drift summary
    print()
    print("# Final drift (sim_turns - real_turns at end):")
    for name in team:
        d = drift[name]
        marker = "  " if d == 0 else (" !" if abs(d) >= 3 else " *")
        print(f"#  {name:12s} {d:+d}{marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
