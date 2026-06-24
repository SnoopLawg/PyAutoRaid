"""Speed-tune FINDER — search SPD-space for combinations that hold a CB tune.

The original M6 ask: DeadwoodJedi helps you *find* tunes; we only replayed known
ones. This searches per-hero SPD ranges and reports the combinations where the
team holds — survives to turn 50 with no Unkillable/Block-Damage coverage gap —
validated by the VERIFIED cb_sim (full survival model: UK/BD/Shield + heal + HP),
NOT a coverage-only sim (those give false failures — see
project_maneater_uk_2turns_gametruth).

It's the multi-hero generalization of cb_sim's (stub) --sweep-hero: build each
hero from their REAL gear-derived stats (HP/DEF/element from the computed-stat
columns) and override only SPD per the search grid. Heroes not in --vary keep
their current real SPD.

CLI:
    python3 tools/speed_tune_finder.py \
        --team "Maneater,Demytha,Ninja,Geomancer,Venomage" \
        --vary "Maneater=280..292:2,Demytha=168..176:2" \
        --cb-element void

    # single-hero sweep (the old --sweep-hero, now real):
    python3 tools/speed_tune_finder.py --team "Maneater,Demytha,Ninja,Geomancer,Venomage" \
        --vary "Ninja=200..230:2"

Notes:
  - Validity = survive 50 boss turns AND zero UK/BD coverage gaps past the sync
    turn (the stall criterion). The team also passing on damage is a separate
    question (run cb_sim directly for damage).
  - Default-AI skill order is used (highest-CD skill first). Pass --men-openers
    to force the Maneater-A3 / Demytha-A3 protective openers, which most stall
    tunes rely on at turn 0.
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

ELEMENT_NAME_TO_ID = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
_SYNC_TURN = 6


def parse_vary(spec: str) -> dict:
    """'Maneater=280..292:2,Demytha=168..176' -> {name: [spd values]}."""
    out = {}
    for part in (spec or "").split(","):
        part = part.strip()
        if "=" not in part:
            continue
        name, rng = part.split("=", 1)
        step = 2
        if ":" in rng:
            rng, step_s = rng.split(":", 1)
            step = int(step_s)
        lo, hi = rng.split("..")
        out[name.strip()] = list(range(int(lo), int(hi) + 1, step))
    return out


def _validity(res):
    """(survived, gaps) from a cb_sim result — the stall criterion."""
    gaps = 0
    for bt, prot in (res.get("protection_by_turn") or {}).items():
        if bt < _SYNC_TURN:
            continue
        alive = [n for n, p in prot.items() if p.get("alive")]
        if alive and not all(prot[n].get("uk") or prot[n].get("bd") for n in alive):
            gaps += 1
    survived = res.get("cb_turns", 0) >= 50
    return survived, gaps


def find(team, vary, cb_element=4, use_current_gear=True, max_combos=400,
         mc_trials=0, verbose=True):
    """Search SPD-space using the user's REAL gear + flagship preset (opener +
    skill priority), overriding only SPD per the grid.

    mc_trials=0 → deterministic pass/fail (a tune holds iff it survives T50 with
    no UK/BD gap). Good for affinities the team genuinely holds (Void).

    mc_trials>0 → Monte Carlo: run each combo N times with RNG, so weak-affinity
    glance variance (Ninja's A1 TM-fill landing or not on Force) actually rolls.
    Reports per-combo CONSISTENCY (reach-50 rate, median/worst survival turns) so
    you can rank speeds by leeway even when no combo reaches 50 every time.

    Returns (base, grids, results) where results = [(combo, metrics_dict)]."""
    import statistics
    from cb_sim import _build_team_setup, _build_sim_champs_from_setup, CBSimulator, SPD

    setup = _build_team_setup(team, use_current_gear=use_current_gear)
    if isinstance(setup, dict) and setup.get("error"):
        raise SystemExit(f"team setup failed: {setup['error']} "
                         f"(is the mod up / preset available?)")
    hero_names = setup["hero_names"]
    base_spd = [int(round(setup["stats_per_hero"][i][SPD])) for i in range(len(hero_names))]

    # Grid is over the VARIED heroes only; others keep their geared SPD.
    grids = [vary.get(nm, [base_spd[i]]) for i, nm in enumerate(hero_names)]
    total = 1
    for g in grids:
        total *= len(g)
    if total > max_combos:
        raise SystemExit(f"search grid is {total} combos (> --max-combos {max_combos}); "
                         f"narrow the ranges or raise the cap")
    if verbose:
        nvar = sum(1 for g in grids if len(g) > 1)
        mode = f"MC×{mc_trials}" if mc_trials else "deterministic"
        print(f"Searching {total} SPD combination(s) over {nvar} varied hero(es) "
              f"with real gear+preset, cb_element={cb_element} [{mode}]...")

    results = []
    for combo in itertools.product(*grids):
        for i, spd in enumerate(combo):
            setup["stats_per_hero"][i][SPD] = float(spd)
        if mc_trials > 0:
            ts = []
            for seed in range(mc_trials):
                champs = _build_sim_champs_from_setup(setup)
                sim = CBSimulator(champs, cb_difficulty="ultra-nightmare", cb_element=cb_element,
                                  deterministic=False, rng_seed=seed,
                                  model_survival=True, force_affinity=True)
                ts.append(sim.run(max_cb_turns=50)["cb_turns"])
            ts.sort()
            results.append((combo, {
                "reach50": sum(1 for t in ts if t >= 50) / len(ts),
                "median": statistics.median(ts),
                "p25": ts[max(0, len(ts) // 4 - 1)],  # worst-quartile (bad-luck floor)
                "min": ts[0], "trials": mc_trials,
            }))
        else:
            champs = _build_sim_champs_from_setup(setup)
            sim = CBSimulator(champs, cb_difficulty="ultra-nightmare", cb_element=cb_element,
                              deterministic=True, model_survival=True, force_affinity=True)
            res = sim.run(max_cb_turns=50)
            survived, gaps = _validity(res)
            results.append((combo, {"valid": survived and gaps == 0,
                                    "gaps": gaps, "turns": res["cb_turns"]}))

    base = list(zip(hero_names, base_spd))
    return base, grids, results


def _fmt_combo(team, combo):
    return ", ".join(f"{nm}={spd}" for nm, spd in zip(team, combo))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", required=True, help="comma-separated hero names (5)")
    ap.add_argument("--vary", default="", help="'Maneater=280..292:2,Demytha=168..176'")
    ap.add_argument("--cb-element", default="void", choices=list(ELEMENT_NAME_TO_ID))
    ap.add_argument("--mc", type=int, default=0,
                    help="Monte Carlo trials per combo — rank speeds by Force/weak-affinity "
                         "CONSISTENCY (glance variance rolls). 0 = deterministic pass/fail.")
    ap.add_argument("--max-combos", type=int, default=400)
    args = ap.parse_args()

    team = [t.strip() for t in args.team.split(",") if t.strip()]
    vary = parse_vary(args.vary)
    for nm in vary:
        if nm not in team:
            raise SystemExit(f"--vary hero '{nm}' is not in --team")

    base, grids, results = find(team, vary, ELEMENT_NAME_TO_ID[args.cb_element],
                                max_combos=args.max_combos, mc_trials=args.mc)
    team = [nm for nm, _ in base]  # canonical order from the setup

    if args.mc > 0:
        # Rank by consistency: reach-50 rate, then median, then worst-quartile floor.
        results.sort(key=lambda r: (r[1]["reach50"], r[1]["median"], r[1]["p25"]),
                     reverse=True)
        any50 = any(r[1]["reach50"] > 0 for r in results)
        print(f"\n=== Force/weak-affinity consistency (MC×{args.mc}) — ranked best-first ===")
        print(f"  {'reach50':>7} {'median':>7} {'p25':>5} {'min':>4}  combo")
        for combo, m in results[:20]:
            print(f"  {m['reach50']*100:>6.0f}% {m['median']:>7.0f} {m['p25']:>5.0f} "
                  f"{m['min']:>4.0f}  {_fmt_combo(team, combo)}")
        if not any50:
            best = results[0]
            print(f"\n  No speed combo reaches T50 even occasionally — the team can't hold "
                  f"this affinity by SPD alone.\n  Best leeway: {_fmt_combo(team, best[0])} "
                  f"(median {best[1]['median']:.0f} turns, worst {best[1]['min']:.0f}).")
        else:
            n = sum(1 for r in results if r[1]["reach50"] > 0)
            print(f"\n  {n} combo(s) reach T50 at least sometimes — top one clears "
                  f"{results[0][1]['reach50']*100:.0f}% of runs. Speed CAN buy Force grace.")
        return

    holds = [c for c, m in results if m["valid"]]
    print(f"\n=== Holding tunes ({len(holds)} found) — survive T50, 0 UK/BD gaps ===")
    if not holds:
        print("  (none — widen ranges, try --mc N for consistency ranking, "
              "or the team may not hold this affinity)")
    else:
        for combo in holds[:40]:
            print(f"  {_fmt_combo(team, combo)}")
        if len(holds) > 40:
            print(f"  ... +{len(holds) - 40} more")
        for i, nm in enumerate(team):
            if len(grids[i]) > 1:
                vals = sorted({c[i] for c in holds})
                if vals:
                    print(f"  {nm} holds at SPD: {min(vals)}-{max(vals)} "
                          f"({len(vals)}/{len(grids[i])} tried)")


if __name__ == "__main__":
    main()
