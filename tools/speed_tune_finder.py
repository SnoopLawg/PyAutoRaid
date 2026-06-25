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


# Affinity split (this team): Force is the only one with a glance-driven cadence
# problem (Ninja=Magic is weak into Force AND has a glance-gated self-TM-fill).
# The other three have no weak-hero-with-a-TM-effect, so they're deterministically
# stable. A daily-robust tune must hold all 4 — the stable three deterministically,
# Force by Monte-Carlo consistency.
_STABLE_AFFINITIES = {"Magic": 1, "Spirit": 3, "Void": 4}
_FORCE = 2

# Tier-1 funnel: in all-affinities mode, the expensive part is the 16-run Force
# Monte-Carlo. Before paying it, run deterministic Force (1 run = the averaged,
# best-case-ish survival). If that can't reach this many turns, the harsher
# glance-variance MC won't either, so skip the MC. Conservative threshold (dies
# clearly short of T50 enrage) so we don't prune MC-marginal combos.
FORCE_PRESCREEN_TURNS = 44


# Default preset variants the co-search tries (protector openers — the cadence
# levers). Each is {hero: {opening: [...]}}. "current" = the user's flagship
# preset untouched. The all-affinity gate auto-rejects any variant that breaks a
# stable day (e.g. Demytha-A3 opener trades Force for Magic/Spirit/Void).
PRESET_VARIANTS = [
    ("current", {}),
    ("Demytha->A3 open", {"Demytha": {"opening": ["A3"]}}),
    ("Maneater->A3 open", {"Maneater": {"opening": ["A3"]}}),
    ("Demytha+Maneater A3 open", {"Demytha": {"opening": ["A3"]},
                                  "Maneater": {"opening": ["A3"]}}),
]


def find(team, vary, cb_element=4, use_current_gear=True, max_combos=400,
         mc_trials=0, all_affinities=False, preset_vary=False, verbose=True):
    """Search SPD-space using the user's REAL gear + flagship preset, overriding
    only SPD per the grid.

    mc_trials=0 → deterministic pass/fail on `cb_element`.
    mc_trials>0 → Monte Carlo on `cb_element` (glance variance rolls); ranks by
        reach-50 rate / median / worst survival.
    all_affinities=True → DAILY-ROBUST mode: each combo must hold Magic+Spirit+Void
        (deterministic) AND is scored on Force consistency (MC). Combos that drop
        any stable affinity are disqualified (so a Force fix can't silently break
        another day). Short-circuits — skips the expensive Force MC if a stable
        affinity already fails.

    Returns (base, grids, results) where results = [(combo, metrics_dict)]."""
    import statistics
    from cb_sim import _build_team_setup, _build_sim_champs_from_setup, CBSimulator, SPD

    setup = _build_team_setup(team, use_current_gear=use_current_gear)
    if isinstance(setup, dict) and setup.get("error"):
        raise SystemExit(f"team setup failed: {setup['error']} "
                         f"(is the mod up / preset available?)")
    hero_names = setup["hero_names"]
    base_spd = [int(round(setup["stats_per_hero"][i][SPD])) for i in range(len(hero_names))]

    grids = [vary.get(nm, [base_spd[i]]) for i, nm in enumerate(hero_names)]
    total = 1
    for g in grids:
        total *= len(g)
    if total > max_combos:
        raise SystemExit(f"search grid is {total} combos (> --max-combos {max_combos}); "
                         f"narrow the ranges or raise the cap")
    if verbose:
        nvar = sum(1 for g in grids if len(g) > 1)
        mode = ("all-affinities" if all_affinities
                else f"MC×{mc_trials}" if mc_trials else "deterministic")
        print(f"Searching {total} SPD combination(s) over {nvar} varied hero(es) "
              f"with real gear+preset [{mode}]...")

    import copy
    orig_preset = copy.deepcopy(setup["preset_plan"])

    def _turns(eid, *, mc_seed=None):
        ch = _build_sim_champs_from_setup(setup)
        # bugfix_buff_tick=False is the GAME-TRUTH buff cadence: UK/BD durations
        # tick on each hero's OWN turn (not capped once-per-boss-turn). The
        # CBSimulator default (True) over-preserves UK for fast heroes → gapless
        # coverage → over-predicts Force survival (the finder wrongly reported a
        # tune "Force 100%" that wiped at boss turn 32 live, 2026-06-24). With
        # False the sim reproduces that real wipe (T29 / 15.26M vs real T32 /
        # 15.77M, -3%) and the finder correctly REJECTS Force-failing tunes while
        # still passing stable affinities. The global default stays True only
        # because the locked DAMAGE-calibration tests were baselined against it;
        # survival evaluation must use game-truth. See project_cb_tune_equip_flow
        # + project_uk_chain_buff_tick.
        sim = CBSimulator(ch, cb_difficulty="ultra-nightmare", cb_element=eid,
                          deterministic=(mc_seed is None), rng_seed=mc_seed,
                          model_survival=True, force_affinity=True,
                          bugfix_buff_tick=False)
        return sim.run(max_cb_turns=50)["cb_turns"]

    funnel = {"stable_pruned": 0, "force_prescreen_pruned": 0, "mc_ran": 0}

    def _eval_all_affinities():
        """All-affinity metrics for the CURRENT setup state (speeds + preset),
        via the tier-1 funnel: stable-3 deterministic gate → deterministic Force
        pre-screen → full Force MC only on survivors."""
        stable = {nm: _turns(eid) >= 50 for nm, eid in _STABLE_AFFINITIES.items()}
        if not all(stable.values()):
            funnel["stable_pruned"] += 1
            return {"all_stable": False, **stable, "force_reach50": 0.0,
                    "force_median": 0, "tier": "stable-fail"}
        det = _turns(_FORCE)  # tier-1: deterministic Force, 1 run
        if det < FORCE_PRESCREEN_TURNS:
            funnel["force_prescreen_pruned"] += 1
            return {"all_stable": True, **stable, "force_reach50": 0.0,
                    "force_median": det, "tier": "force-prescreen"}
        funnel["mc_ran"] += 1  # tier-2: full Force MC
        ts = sorted(_turns(_FORCE, mc_seed=s) for s in range(n_mc))
        return {"all_stable": True, **stable,
                "force_reach50": sum(1 for t in ts if t >= 50) / len(ts),
                "force_median": statistics.median(ts), "tier": "mc"}

    variants = PRESET_VARIANTS if preset_vary else [("current", {})]
    n_mc = mc_trials or 12
    results = []
    for combo in itertools.product(*grids):
        for i, spd in enumerate(combo):
            setup["stats_per_hero"][i][SPD] = float(spd)

        if all_affinities:
            # Try each preset variant; keep the best one that stays daily-robust.
            # The all-affinity gate auto-rejects preset traps (a variant that
            # lifts Force but drops a stable day scores all_stable=False).
            best = None
            for label, override in variants:
                setup["preset_plan"] = copy.deepcopy(orig_preset)
                for h, fields in override.items():
                    setup["preset_plan"].setdefault(h, {}).update(fields)
                m = _eval_all_affinities()
                m["preset"] = label
                if best is None or (m["all_stable"], m["force_reach50"]) > \
                        (best["all_stable"], best["force_reach50"]):
                    best = m
            setup["preset_plan"] = copy.deepcopy(orig_preset)
            results.append((combo, best))
        elif mc_trials > 0:
            ts = sorted(_turns(cb_element, mc_seed=s) for s in range(mc_trials))
            results.append((combo, {
                "reach50": sum(1 for t in ts if t >= 50) / len(ts),
                "median": statistics.median(ts),
                "p25": ts[max(0, len(ts) // 4 - 1)], "min": ts[0], "trials": mc_trials,
            }))
        else:
            ch = _build_sim_champs_from_setup(setup)
            # bugfix_buff_tick=False: game-truth buff cadence (see _turns above).
            res = CBSimulator(ch, cb_difficulty="ultra-nightmare", cb_element=cb_element,
                              deterministic=True, model_survival=True,
                              force_affinity=True, bugfix_buff_tick=False).run(max_cb_turns=50)
            survived, gaps = _validity(res)
            results.append((combo, {"valid": survived and gaps == 0,
                                    "gaps": gaps, "turns": res["cb_turns"]}))

    if verbose and all_affinities:
        f = funnel
        evals = f["stable_pruned"] + f["force_prescreen_pruned"] + f["mc_ran"]
        saved = (f["stable_pruned"] + f["force_prescreen_pruned"]) * (n_mc - 1)
        print(f"  [tier-1 funnel] {evals} candidate-evals: {f['stable_pruned']} pruned on "
              f"stable-3, {f['force_prescreen_pruned']} pruned on deterministic-Force "
              f"pre-screen, {f['mc_ran']} ran the {n_mc}-run Force MC "
              f"(~{saved} sim-runs saved).")

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
    ap.add_argument("--all-affinities", action="store_true",
                    help="DAILY-ROBUST mode: each combo must hold Magic+Spirit+Void "
                         "(deterministic) AND is scored on Force consistency (MC). Only "
                         "surfaces tunes that survive all four — rejects fixes that break "
                         "another day. Overrides --cb-element/--mc.")
    ap.add_argument("--preset-vary", action="store_true",
                    help="Also try protector-opener preset variants per combo (free, "
                         "no re-gear), keeping the best that stays daily-robust. Requires "
                         "--all-affinities so preset traps are auto-rejected.")
    ap.add_argument("--max-combos", type=int, default=400)
    args = ap.parse_args()

    team = [t.strip() for t in args.team.split(",") if t.strip()]
    vary = parse_vary(args.vary)
    for nm in vary:
        if nm not in team:
            raise SystemExit(f"--vary hero '{nm}' is not in --team")

    if args.preset_vary and not args.all_affinities:
        raise SystemExit("--preset-vary requires --all-affinities (so preset traps are gated)")

    base, grids, results = find(team, vary, ELEMENT_NAME_TO_ID[args.cb_element],
                                max_combos=args.max_combos, mc_trials=args.mc,
                                all_affinities=args.all_affinities,
                                preset_vary=args.preset_vary)
    team = [nm for nm, _ in base]  # canonical order from the setup

    if args.all_affinities:
        # Rank: daily-robust first (all stable affinities hold), then Force consistency.
        results.sort(key=lambda r: (r[1]["all_stable"], r[1]["force_reach50"],
                                    r[1]["force_median"]), reverse=True)
        robust = [r for r in results if r[1]["all_stable"]]
        pcol = "  preset" if args.preset_vary else ""
        print(f"\n=== Daily-robust tunes — hold Magic/Spirit/Void AND Force "
              f"({len(robust)}/{len(results)} pass the stable-3 gate) ===")
        print(f"  {'M':>1} {'S':>1} {'V':>1} {'Force':>7}  combo{pcol}")
        for combo, m in results[:25]:
            flag = lambda b: "Y" if b else "."
            ptag = f"   [{m['preset']}]" if args.preset_vary else ""
            print(f"  {flag(m['Magic'])} {flag(m['Spirit'])} {flag(m['Void'])} "
                  f"{m['force_reach50']*100:>5.0f}%  {_fmt_combo(team, combo)}{ptag}")
        if robust:
            best = robust[0]
            ptag = (f" with preset [{best[1]['preset']}]"
                    if args.preset_vary and best[1].get("preset") != "current" else "")
            print(f"\n  Best daily-robust: {_fmt_combo(team, best[0])}{ptag} "
                  f"-> all 3 stable HOLD, Force {best[1]['force_reach50']*100:.0f}% "
                  f"(median {best[1]['force_median']:.0f}).")
        else:
            print("\n  No combo holds all of Magic/Spirit/Void — every candidate breaks at "
                  "least one stable day. Widen the search or the tune isn't daily-viable.")
        return

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
