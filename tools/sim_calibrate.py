"""Phase 5 — sim damage calibration regression suite.

Reads every `battle_logs_cb_*.json` produced by `cb_run.py` /
`cb_daily.py`, extracts the team + final boss damage, runs the sim
with the same team / difficulty, and reports the per-log error
distribution. Pure measurement — no parameter tweaking.

The point is to surface the picture *before* anyone touches sim
constants, so the un-stacking of the "6 compensating wrongs" (per
project_cb_sim_calibration_state memory) can be planned with full
data instead of one-off per-hero tweaks.

Usage:
    python3 tools/sim_calibrate.py             # all logs, summary table
    python3 tools/sim_calibrate.py --logs '*.json'   # custom glob
    python3 tools/sim_calibrate.py --json      # machine-readable

Output columns (per log):
    file        battle log filename
    boss        UNM/NM/Brutal/...
    real_dmg    total damage taken by boss (millions)
    sim_dmg     sim's predicted damage (millions, default Void affinity)
    delta       (sim - real) / real, percent
    real_turns  CB turns used in real run
    sim_turns   CB turns used in sim

Reads the user's owned roster from heroes_*.json so heroes resolve to
real stats / gear; the sim runs in "current gear" mode. Element is
defaulted to Void — for per-element accuracy, pass --cb-element.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

# Maps the live mod's boss type_id to (difficulty_slug, label).
# CB boss type IDs encode BOTH difficulty AND day-of-week affinity. The
# difficulty determines HP/ATK/DEF; the type-id-of-the-day determines
# affinity (which is also stored in HeroType.DefaultElement). Verified
# 2026-05-01 via /static-export HeroData.HeroTypeById:
#   22210=Void, 22220=Magic, 22230=Force, 22240=Spirit
#   22250=Void, 22260=Magic, 22270=Force, 22280=Spirit
# All 22210/20/30/40 share Easy-Brutal HP profile; 22250/60/70/80 share
# the Nightmare/UltraNightmare HP profile. The HP value distinguishes
# difficulty within each affinity group, NOT the type id alone.
_BOSS_TYPE_TO_AFFINITY = {
    22210: "void",   22220: "magic",  22230: "force",  22240: "spirit",
    22250: "void",   22260: "magic",  22270: "force",  22280: "spirit",
}
_AFFINITY_TO_INT = {"void": 4, "magic": 1, "force": 2, "spirit": 3}
# Mapping from type id → difficulty is ambiguous because the same id is
# reused across days. Best signal is the boss's hp_max field captured in
# the battle log — match it against cb_constants.CB_HP_BY_DIFFICULTY.
_BOSS_TYPE_TO_DIFFICULTY = {
    # The original mapping below was wrong (treated 22260 as always UNM).
    # Keep the difficulty inferred from boss HP at runtime; this dict
    # is a fallback only.
    22210: ("easy",   "Easy"),
    22220: ("normal", "Normal"),
    22230: ("hard",   "Hard"),
    22240: ("brutal", "Brutal"),
    22250: ("nm",     "Nightmare"),
    22260: ("unm",    "UltraNightmare"),
    22270: ("unm",    "UltraNightmare"),
    22280: ("unm",    "UltraNightmare"),
}


def _load_log(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _extract_summary(log_data: dict) -> dict | None:
    """Pull team + boss + damage from a battle log's last poll."""
    log = log_data.get("log") or []
    last_poll = None
    for e in log:
        if isinstance(e, dict) and "heroes" in e:
            last_poll = e
    if not last_poll:
        return None
    heroes = last_poll.get("heroes") or []
    players = [h for h in heroes if h.get("side") == "player"]
    enemy = next((h for h in heroes if h.get("side") == "enemy"), None)
    if not enemy or not players:
        return None
    return {
        "boss_type_id": enemy.get("type_id"),
        "boss_dmg": enemy.get("dmg_taken") or 0,
        "boss_turns": enemy.get("turn_n") or 0,
        "boss_hp_max": enemy.get("hp_max") or 0,
        "player_type_ids": [p.get("type_id") for p in players],
        "player_turns": [p.get("turn_n") or 0 for p in players],
    }


def _resolve_team_names(player_type_ids: list[int]) -> list[str]:
    """Map type_ids to canonical hero names via heroes_6star.json."""
    p = PROJECT_ROOT / "heroes_6star.json"
    if not p.exists():
        return []
    raw = json.loads(p.read_text(encoding="utf-8"))
    by_typeid: dict[int, str] = {}
    for h in raw.get("heroes", []):
        # Canonical type_id is hero_type_id // 10 (the base, not the
        # rarity/ascend tier suffix). Battle logs poll the per-rarity
        # type_id (e.g. 1074 for L60 6★ Maneater); roster entries also
        # store the per-rarity type_id, so a direct match works.
        tid = h.get("type_id")
        nm = h.get("name")
        if tid and nm:
            by_typeid[tid] = nm
            # Also map the //10 form so logs that strip the rarity tier
            # still resolve.
            by_typeid[tid // 10 * 10] = nm
    return [by_typeid.get(tid) or by_typeid.get((tid // 10) * 10) or f"<typeid_{tid}>"
            for tid in player_type_ids]


def _run_sim(team: list[str], cb_difficulty: str, cb_element: int) -> dict:
    """Run cb_potential.simulate_team and return its result dict."""
    from cb_potential import simulate_team
    return simulate_team(team, verbose=False,
                         cb_element=cb_element,
                         cb_difficulty=cb_difficulty)


def calibrate_one(log_path: str, cb_element: int = 4,
                  use_log_affinity: bool = True) -> dict:
    """Run one log through the sim and compute the delta. Returns a row
    dict with all the comparison fields, suitable for tabulation.

    If use_log_affinity is True (default), the boss's affinity is derived
    from the captured boss type_id (rotates per day) — overrides
    cb_element. Use cb_element only as a fallback when type id lookup
    fails.
    """
    log_data = _load_log(log_path)
    if not log_data:
        return {"file": os.path.basename(log_path), "error": "load_failed"}
    summary = _extract_summary(log_data)
    if not summary:
        return {"file": os.path.basename(log_path), "error": "no_polls"}
    diff_slug, diff_label = _BOSS_TYPE_TO_DIFFICULTY.get(
        summary["boss_type_id"], ("unm", f"unknown_{summary['boss_type_id']}"))
    team_names = _resolve_team_names(summary["player_type_ids"])
    if not team_names or any(n.startswith("<typeid_") for n in team_names):
        return {"file": os.path.basename(log_path),
                "error": f"team_unresolved: {team_names}"}
    # Derive actual boss affinity from type id when possible — different
    # battle logs were on different rotation days.
    actual_element = cb_element
    affinity_name = None
    if use_log_affinity:
        affinity_name = _BOSS_TYPE_TO_AFFINITY.get(summary["boss_type_id"])
        if affinity_name:
            actual_element = _AFFINITY_TO_INT.get(affinity_name, cb_element)
    sim = _run_sim(team_names, cb_difficulty=diff_slug, cb_element=actual_element)
    if "error" in sim:
        return {"file": os.path.basename(log_path),
                "error": f"sim: {sim['error']}",
                "team": team_names, "difficulty": diff_slug}
    real_dmg = summary["boss_dmg"]
    sim_dmg = sim.get("total", 0)
    delta_pct = ((sim_dmg - real_dmg) / real_dmg * 100) if real_dmg > 0 else 0.0
    return {
        "file": os.path.basename(log_path),
        "boss": diff_label,
        "affinity": affinity_name or "?",
        "team": ",".join(team_names),
        "real_dmg": real_dmg,
        "sim_dmg": sim_dmg,
        "delta_pct": delta_pct,
        "real_turns": summary["boss_turns"],
        "sim_turns": sim.get("cb_turns", 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--logs", default="battle_logs_cb_*.json",
                    help="Glob for battle log files (default: battle_logs_cb_*.json)")
    ap.add_argument("--cb-element", default="void",
                    choices=["magic", "force", "spirit", "void"],
                    help="Affinity to sim under (default: void). "
                         "Real logs span multiple element days; for now "
                         "we sim them all under one element to surface "
                         "the systematic delta.")
    ap.add_argument("--json", action="store_true",
                    help="Emit JSON rows instead of formatted table.")
    args = ap.parse_args()

    elem_id = {"magic": 1, "force": 2, "spirit": 3, "void": 4}[args.cb_element]
    files = sorted(glob.glob(args.logs))
    if not files:
        print(f"No files matched {args.logs!r}", file=sys.stderr)
        return 2
    rows = [calibrate_one(f, cb_element=elem_id) for f in files]

    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    # Headline summary
    ok = [r for r in rows if "error" not in r]
    err = [r for r in rows if "error" in r]
    print(f"=== sim calibration over {len(files)} battle logs (boss affinity from log type id) ===\n")
    print(f"  {'file':<40s} {'boss':<14s} {'aff':<6s} {'real':>8s} {'sim':>8s} {'delta':>7s} {'real_T':>6s} {'sim_T':>5s}")
    print(f"  {'-'*40} {'-'*14} {'-'*6} {'-'*8} {'-'*8} {'-'*7} {'-'*6} {'-'*5}")
    for r in rows:
        if "error" in r:
            print(f"  {r['file']:<40s} ERR: {r['error']}")
            continue
        print(f"  {r['file']:<40s} {r['boss']:<14s} {r.get('affinity', '?'):<6s} "
              f"{r['real_dmg']/1e6:>7.2f}M {r['sim_dmg']/1e6:>7.2f}M "
              f"{r['delta_pct']:>+6.1f}% {r['real_turns']:>6d} {r['sim_turns']:>5d}")

    if ok:
        # Filter to *complete* battles (boss_turns >= 48 of 50). Partial
        # battles are usually the user pausing/aborting; comparing them
        # to the sim's full-50-turn run is meaningless.
        complete = [r for r in ok if r["real_turns"] >= 48]
        partial = [r for r in ok if r["real_turns"] < 48]

        if complete:
            deltas = [r["delta_pct"] for r in complete]
            by_diff: dict[str, list[float]] = {}
            for r in complete:
                by_diff.setdefault(r["boss"], []).append(r["delta_pct"])
            print(f"\n  Complete battles only (real_turns >= 48):")
            print(f"    n={len(complete)}  mean_abs_delta={sum(abs(d) for d in deltas)/len(deltas):.1f}%  "
                  f"min={min(deltas):+.1f}%  max={max(deltas):+.1f}%")
            for diff_label, ds in sorted(by_diff.items()):
                mean = sum(ds) / len(ds)
                absmean = sum(abs(d) for d in ds) / len(ds)
                print(f"    {diff_label:<14s} n={len(ds):>2d}  mean={mean:+.1f}%  abs_mean={absmean:.1f}%  "
                      f"range=[{min(ds):+.1f}, {max(ds):+.1f}]")

            # Phase 5 calibration target line: each difficulty's mean
            # should land within ±5% (per project_cb_sim_calibration_state
            # memory; "94% accuracy" was the best UNM-Void run, not a
            # mean across runs).
            failing = [(d, sum(ds)/len(ds)) for d, ds in by_diff.items()
                       if abs(sum(ds)/len(ds)) > 5.0]
            if failing:
                print(f"\n  Difficulties failing ±5% target:")
                for d, m in failing:
                    print(f"    {d:<14s} mean={m:+.1f}%  ({'over' if m > 0 else 'under'} by {abs(m):.1f}%)")
            else:
                print(f"\n  ✅ All difficulties within ±5% target.")

        if partial:
            print(f"\n  Partial battles (skipped from headline; user aborted before turn 48):")
            for r in partial:
                print(f"    {r['file']:<40s} real_turns={r['real_turns']:>2d}  real={r['real_dmg']/1e6:.1f}M")
    if err:
        print(f"\n  {len(err)} log(s) skipped (see ERR lines above).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
