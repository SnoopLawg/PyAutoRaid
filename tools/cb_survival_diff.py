"""CB survival diff — sim vs real, per boss turn (M7 Phase A3).

The damage calibrator (`cb_calibrate.py` / `cb_truth_diff.py`) answers
"did the sim's DAMAGE match real". This answers the orthogonal question the
M7 survival engine is gated on: **did the sim's SURVIVAL match real** — i.e.
per boss turn, did each hero have the same HP trajectory and the same
Unkillable / Block-Damage coverage, and did they die on the same turn?

Why this exists: 2026-06-24 a live Force run wiped at boss turn 32 while the
sim predicted T50. The sim keeps UK coverage gapless so the fragile DPS never
die. This tool makes that failure mode measurable on every capture instead of
hand-rolled, so the survival model can be hardened against a fixture battery.

Real side  : `poll_log_cb_*.json` (per-poll hero state — hp + buffs).
Sim side   : `cb_sim` `protection_by_turn` (hp_pct + uk/bd/sh per CB turn).
Team build : a `build_cb_*.json` snapshot if present (exact stats); else the
             live current gear via `_build_team_setup`, with optional
             `--speeds` overrides to match the fixture's tune.

Survival bar (M7 A1): sim death-turn within ±SURV_TOL boss turns of real for
every hero, AND the same survive-to-50 vs wipe classification. Exit 0 = pass.

CLI:
    python3 tools/cb_survival_diff.py                      # newest fixture
    python3 tools/cb_survival_diff.py --battle battle_logs_cb_<ts>.json
    python3 tools/cb_survival_diff.py --element force \
        --speeds "Maneater=292,Demytha=174,Ninja=225,Geomancer=178,Venomage=162"
    python3 tools/cb_survival_diff.py --json out.json
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

UK_TYPE = 320          # Unkillable buff type id
BD_TYPE = 60           # Block Damage buff type id
SURV_TOL = 3           # death-turn tolerance (boss turns) — M7 A1 bar
ELEMENT_MAP = {"magic": 1, "force": 2, "spirit": 3, "void": 4}


# --------------------------------------------------------------------------
# Real side — parse poll_log into per-boss-turn hero state
# --------------------------------------------------------------------------
def _poll_log_for(battle_log: str) -> str | None:
    cand = battle_log.replace("battle_logs_cb_", "poll_log_cb_")
    return cand if cand != battle_log and os.path.exists(cand) else None


def parse_real(poll_log_path: str) -> dict:
    """Return {boss_turn: {type_id_base: {hp_pct, uk, bd, dead}}} + death_turn
    per hero + max boss turn, from the real poll log. Hero key is the
    battle-log/poll-log type_id (already the truncated base form)."""
    by_turn: dict[int, dict] = {}
    death_turn: dict[int, int] = {}
    max_turn = 0
    for line in open(poll_log_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            bs = json.loads(line).get("state", {})
        except Exception:
            continue
        hs = bs.get("heroes", []) if isinstance(bs, dict) else []
        boss = next((h for h in hs if h.get("side") == "enemy"), None)
        if not boss:
            continue
        turn = boss.get("turn_n", 0) or 0
        max_turn = max(max_turn, turn)
        row = {}
        for p in hs:
            if p.get("side") != "player":
                continue
            tid = p.get("type_id")
            if tid is None:
                continue
            buffs = {(b.get("t") if isinstance(b, dict) else None) for b in (p.get("buffs") or [])}
            dead = "dead" in (p.get("st") or [])
            mx = p.get("hp_max") or 0
            cur = p.get("hp_cur")
            if cur is None and "hp_pct" in p:
                hp_pct = p.get("hp_pct")
            else:
                hp_pct = (cur / mx * 100) if (mx and cur is not None) else (0 if dead else None)
            row[tid] = {"hp_pct": hp_pct, "uk": UK_TYPE in buffs, "bd": BD_TYPE in buffs, "dead": dead}
            if dead and tid not in death_turn:
                death_turn[tid] = turn
        by_turn[turn] = row
    return {"by_turn": by_turn, "death_turn": death_turn, "max_turn": max_turn}


# --------------------------------------------------------------------------
# Sim side — run cb_sim, capture protection_by_turn (hp_pct + uk/bd)
# --------------------------------------------------------------------------
def run_sim(team_names, element, speeds=None, build=None):
    """Run cb_sim with the game-truth survival cadence (bugfix_buff_tick=False)
    and return {boss_turn: {name: {hp_pct, uk, bd, alive}}} + death_turn + max.

    `build`: optional {name: {statname: value}} from a build_cb snapshot — when
    present, every hero's full stat line is overridden to the captured build, so
    the sim matches the fixture exactly (apples-to-apples). Without it, the live
    current gear is used (+ optional `speeds`)."""
    from cb_sim import (_build_team_setup, _build_sim_champs_from_setup,
                        CBSimulator, SPD)
    from cb_optimizer import HP, ATK, DEF, RES, ACC, CR, CD
    STAT = {"HP": HP, "ATK": ATK, "DEF": DEF, "SPD": SPD, "RES": RES,
            "ACC": ACC, "CR": CR, "CD": CD}
    setup = _build_team_setup(team_names, use_current_gear=True)
    if isinstance(setup, dict) and setup.get("error"):
        raise SystemExit(f"team setup failed: {setup['error']} (mod up?)")
    names = setup["hero_names"]
    idx = {n: i for i, n in enumerate(names)}
    if build:
        for n, stats in build.items():
            if n in idx:
                for sname, val in stats.items():
                    if sname in STAT and val is not None:
                        setup["stats_per_hero"][idx[n]][STAT[sname]] = float(val)
    if speeds:
        for n, v in speeds.items():
            if n in idx:
                setup["stats_per_hero"][idx[n]][SPD] = float(v)
    sim = CBSimulator(_build_sim_champs_from_setup(setup),
                      cb_difficulty="ultra-nightmare", cb_element=element,
                      deterministic=True, model_survival=True,
                      force_affinity=(element in (1, 2, 3)),
                      bugfix_buff_tick=False)
    res = sim.run(max_cb_turns=50)
    death_turn = {}
    for t in sorted(sim.protection_by_turn):
        for nm, v in sim.protection_by_turn[t].items():
            if not v.get("alive") and nm not in death_turn:
                death_turn[nm] = t
    return {"by_turn": sim.protection_by_turn, "death_turn": death_turn,
            "cb_turns": res.get("cb_turns", 0), "names": names}


# --------------------------------------------------------------------------
# Map sim hero NAME <-> real type_id (battle log truncates last digit)
# --------------------------------------------------------------------------
def name_typeid_map(team_names):
    """{name: real_type_id_base} via live /all-heroes (base = tid // 10 * 10)."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://localhost:6790/all-heroes?limit=20000", timeout=20) as r:
            heroes = json.loads(r.read()).get("heroes", [])
    except Exception:
        return {}
    want = {n.lower() for n in team_names}
    out = {}
    for h in heroes:
        nm = (h.get("name") or "")
        if nm.lower() in want and h.get("type_id"):
            # prefer the geared copy if duplicates
            base = (h["type_id"] // 10) * 10
            if nm not in out or len(h.get("artifacts") or []) > out[nm][1]:
                out[nm] = (base, len(h.get("artifacts") or []))
    return {nm: base for nm, (base, _) in out.items()}


# --------------------------------------------------------------------------
# Diff + verdict
# --------------------------------------------------------------------------
def diff(real, sim, nm2tid):
    tid2nm = {tid: nm for nm, tid in nm2tid.items()}
    rows = []
    real_dt, sim_dt = real["death_turn"], sim["death_turn"]
    per_hero = {}
    for nm, tid in nm2tid.items():
        rd = real_dt.get(tid)          # real death turn (None = survived)
        sd = sim_dt.get(nm)            # sim death turn  (None = survived)
        same_class = (rd is None) == (sd is None)
        within = True
        if rd is not None and sd is not None:
            within = abs(rd - sd) <= SURV_TOL
        per_hero[nm] = {"real_death": rd, "sim_death": sd,
                        "class_match": same_class, "within_tol": within}
    # team-level survive/wipe
    real_wipe = bool(real_dt) and len(real_dt) >= len(nm2tid)
    sim_wipe = bool(sim_dt) and len(sim_dt) >= len(nm2tid)
    real_first = min(real_dt.values()) if real_dt else None
    sim_first = min(sim_dt.values()) if sim_dt else None
    return {"per_hero": per_hero, "tid2nm": tid2nm,
            "real_first_death": real_first, "sim_first_death": sim_first,
            "real_team_wipe": real_wipe, "sim_team_wipe": sim_wipe,
            "real_max_turn": real["max_turn"], "sim_cb_turns": sim["cb_turns"]}


def print_report(real, sim, d, nm2tid):
    print("\n=== CB SURVIVAL DIFF (sim vs real) ===")
    print(f"  real: first death T{d['real_first_death']}  team-wipe={d['real_team_wipe']}  reached T{d['real_max_turn']}")
    print(f"  sim : first death T{d['sim_first_death']}  team-wipe={d['sim_team_wipe']}  survived to T{d['sim_cb_turns']}")
    print("\n  per-hero death turn (real vs sim, tol ±%d):" % SURV_TOL)
    ok = True
    for nm, ph in d["per_hero"].items():
        cm = "OK" if ph["class_match"] and ph["within_tol"] else "MISS"
        if cm == "MISS":
            ok = False
        print(f"    {nm:11s} real={str(ph['real_death']):>4}  sim={str(ph['sim_death']):>4}  {cm}")
    # per-turn coverage/HP at a few checkpoints around the real first death
    anchor = d["real_first_death"] or d["real_max_turn"] or 30
    print(f"\n  coverage/HP around T{anchor} (sim | real):")
    tid2nm = d["tid2nm"]
    for t in range(max(1, anchor - 4), anchor + 3):
        sturn = sim["by_turn"].get(t, {})
        rturn = real["by_turn"].get(t, {})
        cells = []
        for nm, tid in nm2tid.items():
            sv = sturn.get(nm, {})
            rv = rturn.get(tid, {})
            scov = "U" if sv.get("uk") else ("B" if sv.get("bd") else ".")
            rcov = "U" if rv.get("uk") else ("B" if rv.get("bd") else ".")
            shp = sv.get("hp_pct"); rhp = rv.get("hp_pct")
            cells.append(f"{nm[:4]} s{('%.0f' % shp) if shp is not None else '-'}{scov}/r{('%.0f' % rhp) if rhp is not None else '-'}{rcov}")
        if sturn or rturn:
            print(f"    T{t:>2}: " + "  ".join(cells))
    verdict = ok and (d["real_team_wipe"] == d["sim_team_wipe"])
    print(f"\n  SURVIVAL VERDICT: {'PASS' if verdict else 'FAIL'} "
          f"(death-turns within ±{SURV_TOL} AND survive/wipe class matches)")
    return verdict


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--battle", help="battle_logs_cb_*.json (default: newest)")
    ap.add_argument("--team", default="Maneater,Demytha,Ninja,Geomancer,Venomage")
    ap.add_argument("--element", default="force", choices=list(ELEMENT_MAP))
    ap.add_argument("--speeds", help='SPD overrides "Maneater=292,Demytha=174,..."')
    ap.add_argument("--json", help="write the diff to this JSON path")
    args = ap.parse_args(argv)

    battle = args.battle
    if not battle:
        logs = sorted(glob.glob(str(PROJECT_ROOT / "battle_logs_cb_*.json")), key=os.path.getmtime)
        if not logs:
            print("no battle_logs_cb_*.json found", file=sys.stderr)
            return 2
        battle = logs[-1]
    poll = _poll_log_for(battle)
    if not poll:
        print(f"no poll_log alongside {os.path.basename(battle)} — survival diff needs per-poll state", file=sys.stderr)
        return 2

    team = [n.strip() for n in args.team.split(",") if n.strip()]
    speeds = {}
    if args.speeds:
        for kv in args.speeds.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                speeds[k.strip()] = float(v)

    # Use the fixture's build snapshot (exact stats) if it exists.
    build = None
    build_path = battle.replace("battle_logs_cb_", "build_cb_")
    if build_path != battle and os.path.exists(build_path):
        try:
            bd = json.loads(Path(build_path).read_text())
            build = {h["name"]: h.get("stats", {}) for h in bd.get("team", []) if h.get("name")}
            print(f"  using build snapshot {os.path.basename(build_path)} (exact stats)")
        except Exception as ex:
            print(f"  [warn] build snapshot unreadable ({ex}); using live gear")

    print(f"fixture: {os.path.basename(battle)}  (element={args.element})")
    real = parse_real(poll)
    sim = run_sim(team, ELEMENT_MAP[args.element], speeds=speeds or None, build=build)
    nm2tid = name_typeid_map(sim["names"])
    if not nm2tid:
        print("warning: could not map hero names->type_ids (mod down?); per-hero diff limited", file=sys.stderr)
    d = diff(real, sim, nm2tid)
    verdict = print_report(real, sim, d, nm2tid)
    if args.json:
        Path(args.json).write_text(json.dumps({"fixture": os.path.basename(battle), **d}, indent=2, default=str))
        print(f"  wrote {args.json}")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
