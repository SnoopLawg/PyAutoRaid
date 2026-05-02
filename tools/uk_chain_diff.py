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


def extract_real_hero_buffs(log_path: Path) -> dict[int, dict[int, set[int]]]:
    """Read the battle log polls and return per-(boss_turn, hero_id) buff sets.

    Returns: {boss_turn: {hero_id: {effect_id, ...}}}
    """
    d = json.loads(log_path.read_text(encoding="utf-8"))
    log = d.get("log", [])
    by_turn: dict[int, dict[int, set[int]]] = {}
    for e in log:
        if "poll" not in e or "heroes" not in e:
            continue
        bt = e.get("turn", 0)
        if bt < 0:
            continue
        if bt not in by_turn:
            by_turn[bt] = {}
        for h in e.get("heroes", []):
            if h.get("side") != "player":
                continue
            hid = h.get("id")
            buffs: set[int] = set()
            # `eff` is a list of {ph, e: [{id, k, c}]} blocks
            for ph_block in h.get("eff", []) or []:
                for ent in ph_block.get("e", []) or []:
                    eff_id = ent.get("k") or 0
                    # eff_id is StatusEffectKindId; not the same as type_id.
                    # We capture both id and k — typical buffs we care about
                    # are identified by `k` (kind).
                    buffs.add(eff_id)
                    type_id = ent.get("id") or 0
                    buffs.add(type_id)
            # Update OR-merge across multiple polls in the same boss turn
            existing = by_turn[bt].get(hid, set())
            by_turn[bt][hid] = existing | buffs
    return by_turn


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("battle_log", help="Path to battle_logs_cb_<timestamp>.json")
    ap.add_argument("--cb-element", default="magic")
    ap.add_argument("--max-turns", type=int, default=25)
    args = ap.parse_args()
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
    sim = run_sim_for_team(team, cb_element=1, force_affinity=True,
                           max_cb_turns=50, use_preset=True)
    sim_snapshots = sim.get("turn_snapshots", [])
    print(f"# Sim: cb_turns={sim['cb_turns']}, total={sim['total']:,.0f}")
    print()

    # Side-by-side comparison
    print(f"{'BT':>3}  {'Hero':<10}  {'Real buffs':<35}  {'Sim buffs':<35}  Match")
    print("-" * 100)
    sim_by_turn = {s["cb_turn"]: s for s in sim_snapshots}
    max_t = min(args.max_turns, max(real_buffs.keys()) if real_buffs else 0)
    for bt in range(1, max_t + 1):
        r_h = real_buffs.get(bt, {})
        s_snap = sim_by_turn.get(bt)
        if not s_snap:
            continue
        s_h = s_snap.get("hero_buffs", {})
        for hid_real, name in zip(sorted(r_h.keys())[:5], team):
            real_set = r_h.get(hid_real, set())
            sim_buffs = s_h.get(name, {})
            # Map sim buff names to canonical
            sim_buffs_set = set(sim_buffs.keys())
            # Care about UK/BD coverage
            r_uk = 320 in real_set
            r_bd = 60 in real_set
            s_uk = "unkillable" in sim_buffs_set
            s_bd = "block_damage" in sim_buffs_set
            match = "OK" if (r_uk == s_uk and r_bd == s_bd) else "DIFF"
            r_str = f"UK={'Y' if r_uk else 'N'} BD={'Y' if r_bd else 'N'} ({len(real_set)} effs)"
            s_str = f"UK={'Y' if s_uk else 'N'} BD={'Y' if s_bd else 'N'} ({len(sim_buffs_set)} buffs)"
            print(f"{bt:>3}  {name:<10}  {r_str:<35}  {s_str:<35}  {match}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
