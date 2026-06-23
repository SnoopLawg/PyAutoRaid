"""Compare sim hero buff state vs real battle log per CB turn.

Identifies the exact CB turn where sim's UK/BD coverage diverges
from real, so we can trace the cause (skill timing, extension chain,
buff tick mechanics).

Usage:
    python3 tools/uk_chain_diff.py battle_logs_cb_<timestamp>.json

Output: per-CB-turn table showing hero buff state in real vs sim.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Effect-id → human name (from raid_data / status_effect_map). Subset
# we care about for UK-chain coverage analysis.
EFFECT_NAMES = {
    320: "unkillable",
    60: "block_damage",
    100: "block_debuffs",
    280: "shield",
    91: "cont_heal_15",
    481: "perfect_veil",
    310: "ally_protect",
    311: "ally_protect_25",
    240: "inc_cr",
    241: "inc_cr_30",
    260: "inc_cd",
    261: "inc_cd_30",
}


def extract_real_hero_buffs(log_path: Path) -> dict[int, dict[int, dict[int, int]]]:
    """Read the battle log polls and return per-(boss_turn, hero_id) buff state.

    Returns: {boss_turn: {hero_id: {status_effect_type_id: duration_remaining}}}

    Each hero's `buffs` field is a list of {t: type_id, d: duration,
    src: source_hero_idx}. This is the GAME's authoritative buff list
    (e.g. UK = type_id 320, BD = 60, Shield = 280).
    """
    d = json.loads(log_path.read_text(encoding="utf-8"))
    log = d.get("log", [])
    by_turn: dict[int, dict[int, dict[int, int]]] = {}
    for e in log:
        if "poll" not in e or "heroes" not in e:
            continue
        # IMPORTANT: e["turn"] is a unit-turn-count (increments per
        # unit action, ~6-7x per boss turn). Boss turn lives on the
        # enemy hero's `turn_n` field — that's the authoritative BT.
        bt = None
        for h in e.get("heroes", []):
            if h.get("side") == "enemy":
                bt = h.get("turn_n")
                break
        if bt is None or bt < 0:
            continue
        if bt not in by_turn:
            by_turn[bt] = {}
        for h in e.get("heroes", []):
            if h.get("side") != "player":
                continue
            hid = h.get("id")
            buffs: dict[int, int] = {}
            for b in h.get("buffs") or []:
                if isinstance(b, dict) and "t" in b:
                    tid = b.get("t")
                    dur = b.get("d", 0) or 0
                    # Keep MAX duration if multiple polls hit same buff
                    buffs[tid] = max(buffs.get(tid, 0), dur)
            # Merge across polls in same turn (OR by max duration)
            existing = by_turn[bt].get(hid, {})
            for tid, dur in buffs.items():
                existing[tid] = max(existing.get(tid, 0), dur)
            by_turn[bt][hid] = existing
    return by_turn


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("battle_log", help="Path to battle_logs_cb_<timestamp>.json")
    ap.add_argument("--cb-element", default="magic",
                    choices=["magic", "force", "spirit", "void"])
    ap.add_argument("--max-turns", type=int, default=50)
    ap.add_argument("--only-divergence", action="store_true",
                    help="Only print rows where sim and real disagree.")
    ap.add_argument("--preset-snapshot",
                    help="Path to presets_cb_<ts>.json captured with this "
                         "fixture. When omitted, uses live mod preset — "
                         "may differ from what real battle ran with.")
    args = ap.parse_args()
    elem_map = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
    cb_element_int = elem_map[args.cb_element]
    log_path = Path(args.battle_log)
    if not log_path.exists():
        print(f"file not found: {log_path}", file=sys.stderr)
        return 1
    real_buffs = extract_real_hero_buffs(log_path)
    print(f"# Real battle log: {len(real_buffs)} boss turns")

    # Run sim against same team
    sys.path.insert(0, str(PROJECT_ROOT / "tools"))
    from cb_calibrate import extract_real_data  # type: ignore[import-not-found]
    real_data = extract_real_data(log_path)
    type_id_to_name = {
        1070: "Maneater", 1076: "Maneater",  # base + transformed forms
        6510: "Demytha", 6516: "Demytha",
        6200: "Ninja", 6206: "Ninja",
        4880: "Geomancer", 4886: "Geomancer",
        6280: "Venomage", 6286: "Venomage",
    }
    team = []
    for tid in real_data.get("team_type_ids", []):
        n = type_id_to_name.get(tid)
        if n and n not in team:
            team.append(n)
    print(f"# Team: {team}")

    from cb_calibrate import run_sim_for_team  # type: ignore[import-not-found]
    sim = run_sim_for_team(team, cb_element=cb_element_int, force_affinity=True,
                           max_cb_turns=50, use_preset=True,
                           preset_snapshot_path=args.preset_snapshot)
    sim_snapshots = sim.get("turn_snapshots", [])
    print(f"# Sim: cb_turns={sim['cb_turns']}, total={sim['total']:,.0f}, element={args.cb_element}")
    print()

    # Stable hero-id ordering: take first poll's player heroes in slot order.
    team_real_hids = []
    for bt in sorted(real_buffs.keys()):
        team_real_hids = sorted(real_buffs[bt].keys())
        if len(team_real_hids) >= len(team):
            team_real_hids = team_real_hids[:len(team)]
            break

    print(f"{'BT':>3}  {'Hero':<10}  {'Real buffs':<25}  {'Sim buffs':<25}  Match")
    print("-" * 80)
    sim_by_turn = {s["cb_turn"]: s for s in sim_snapshots}
    max_real = max(real_buffs.keys()) if real_buffs else 0
    max_t = min(args.max_turns, max_real)
    summary = {"total": 0, "diff": 0, "real_uk_yes_sim_no": 0,
               "real_uk_no_sim_yes": 0, "real_bd_yes_sim_no": 0,
               "real_bd_no_sim_yes": 0}
    for bt in range(1, max_t + 1):
        r_h = real_buffs.get(bt, {})
        s_snap = sim_by_turn.get(bt)
        if not s_snap:
            continue
        s_h = s_snap.get("hero_buffs", {})
        for hid_real, name in zip(team_real_hids, team):
            hero_real = r_h.get(hid_real, {})
            sim_buffs = s_h.get(name, {})
            r_uk = hero_real.get(320, 0)
            r_bd = hero_real.get(60, 0)
            r_sh = hero_real.get(280, 0)
            s_uk = sim_buffs.get("unkillable", 0)
            s_bd = sim_buffs.get("block_damage", 0)
            s_sh = sim_buffs.get("shield", 0)
            uk_diff = bool(r_uk) != bool(s_uk)
            bd_diff = bool(r_bd) != bool(s_bd)
            sh_diff = bool(r_sh) != bool(s_sh)
            is_diff = uk_diff or bd_diff or sh_diff
            summary["total"] += 1
            if is_diff:
                summary["diff"] += 1
            if r_uk and not s_uk: summary["real_uk_yes_sim_no"] += 1
            if s_uk and not r_uk: summary["real_uk_no_sim_yes"] += 1
            if r_bd and not s_bd: summary["real_bd_yes_sim_no"] += 1
            if s_bd and not r_bd: summary["real_bd_no_sim_yes"] += 1
            match = "OK" if not is_diff else "DIFF"
            if args.only_divergence and not is_diff:
                continue
            r_str = f"UK={r_uk} BD={r_bd} SH={r_sh}"
            s_str = f"UK={s_uk} BD={s_bd} SH={s_sh}"
            print(f"{bt:>3}  {name:<10}  {r_str:<25}  {s_str:<25}  {match}")
    print()
    print(f"# Summary: {summary['diff']}/{summary['total']} rows diverge "
          f"(UK: real-up/sim-down={summary['real_uk_yes_sim_no']}, "
          f"real-down/sim-up={summary['real_uk_no_sim_yes']}; "
          f"BD: real-up/sim-down={summary['real_bd_yes_sim_no']}, "
          f"real-down/sim-up={summary['real_bd_no_sim_yes']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
