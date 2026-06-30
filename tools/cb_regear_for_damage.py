"""Task #48 — push the MEN clan-boss tune past its ~37M ceiling by RE-GEARING
its damage dealers for damage (stop overcapping ACC; reallocate into CD/ATK/CR).

THESIS
    The MEN tune (Maneater / Demytha / Ninja / Geomancer / Venomage) holds the
    boss cadence to T50 and does ~37M (cb_sim estimate). Its three DEBUFFERS
    (Ninja / Geomancer / Venomage) are OVERCAPPED on ACC vs the CB-UNM floor
    (boss_constraints.acc_floor("clan_boss") = 225). That overcap is dead stat
    budget. Reallocating it into C.DMG / ATK% / C.RATE on the damage engines
    should raise team damage with no survival cost — because we hold the SPD
    tune exactly (cadence unchanged) and keep the survival heroes' gear frozen.

WHAT THIS DOES (and what it deliberately does NOT touch)
    * Survival heroes (Maneater SPD 288 + Demytha SPD 184) keep their CURRENT
      gear. Their equipped artifacts are EXCLUDED from the dealers' candidate
      vault (`exclude_ids`) so the re-gear can never steal the speed boots that
      hold the tune.
    * The three dealers are re-geared one at a time, hardest-SPD-first, with
      artifact CONTENTION (a piece given to one dealer leaves the next dealer's
      vault) — exactly the team-aware pattern team_tune.gear_feasibility /
      cb_recommender._solve_rec use.
    * Each dealer's SPD is pinned to its CURRENT tuned value (min==target,
      max==target+SPD_TOL in the solve; then FORCED exactly in the re-score
      sim) so the boss cadence is identical between baseline and re-gear — the
      delta is PURE damage, not a survival artifact.

HONESTY
    cb_sim UNDER-survives the real game and OVER-rates stalls (memory
    project_cb_sim_calibration_state). Absolute numbers are ESTIMATES. The
    signal is the BEFORE->AFTER delta from the SAME harness, run here for both
    the baseline (current gear) and the re-geared build. The gear is from the
    real vault (all_artifacts.json), so any reported swap is feasible.

REUSE (imports, never re-implements)
    * gear_target_optimizer.Optimizer.optimize  — M6 per-champion stat-target
      gear solver with calc_stats(hypothetical=True) oracle + exclude_ids
      contention (memory project_gear_target_optimizer).
    * gear_target_optimizer.build_targets / load_data / STAT_ID_TO_NAME.
    * cb_sim._build_team_setup / ._build_sim_champs_from_setup / .CBSimulator
      — build the team (current gear + flagship preset), override the dealers'
      stats, run the full survival sim (same call team_tune._score_combo uses).
    * speed_tune_finder._validity / .ELEMENT_NAME_TO_ID — survival/holds check.
    * boss_constraints.acc_floor — game-truth CB-UNM ACC floor.

CLI
    python tools/cb_regear_for_damage.py                 # spirit, deterministic
    python tools/cb_regear_for_damage.py --element magic
    python tools/cb_regear_for_damage.py --json out.json
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from cb_sim import (_build_team_setup, _build_sim_champs_from_setup,  # noqa: E402
                    CBSimulator, SPD, ACC, ATK, CR, CD, HP, DEF, RES)
import gear_target_optimizer as gto  # noqa: E402
from gear_target_optimizer import STAT_ID_TO_NAME  # noqa: E402
from gear_constants import SLOT_NAMES  # noqa: E402
from speed_tune_finder import _validity, ELEMENT_NAME_TO_ID  # noqa: E402
import team_tune  # noqa: E402

MEN = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
DEALERS = ["Ninja", "Geomancer", "Venomage"]
SURVIVORS = ["Maneater", "Demytha"]

# SPD slack the gear solve may use above the pinned tune value. The re-score
# sim FORCES SPD back to the exact tune, so this only loosens the gear search
# (a piece with SPD+CD isn't rejected for 1-2 extra SPD); cadence is unchanged.
SPD_TOL = 2

# Damage-importance weights for the dealers' re-gear. CD first (cheap, scales
# the whole crit term), then ATK%, then CR (soft-capped at 100 in the scorer —
# surplus flows to CD/ATK automatically). ACC is a MIN (floor), never maximized.
DAMAGE_WEIGHTS = {CD: 4, ATK: 3, CR: 2}

ALL_STATS = (HP, ATK, DEF, SPD, RES, ACC, CR, CD)


def _load_set_names():
    try:
        af = json.loads((ROOT / "data" / "static" / "artifact_sets.json")
                        .read_text(encoding="utf-8"))
        rows = next((v for k, v in af.items() if k != "_meta" and isinstance(v, list)), [])
        return {r["id"]: r.get("name", f"set#{r['id']}") for r in rows}
    except Exception:
        return {}


SET_NAMES = _load_set_names()


def _set_name(sid):
    return SET_NAMES.get(sid, f"set#{sid}")


def _run_sim(setup, element_id):
    """One full deterministic survival sim from a (possibly stat-overridden)
    setup. Same call shape as team_tune._score_combo — game-truth survival
    model (bugfix_buff_tick=False, force_affinity), 50 CB turns."""
    champs = _build_sim_champs_from_setup(setup)
    res = CBSimulator(champs, cb_difficulty="ultra-nightmare",
                      cb_element=element_id, deterministic=True,
                      model_survival=True, force_affinity=True,
                      bugfix_buff_tick=False).run(max_cb_turns=50)
    survived, gaps = _validity(res)
    return {"total": float(res.get("total", 0.0) or 0.0),
            "turns": int(res.get("cb_turns", 0) or 0),
            "gaps": gaps,
            "holds": bool(survived and gaps == 0)}


def _describe_art(a):
    """Compact stat-line for an artifact: slot, set, primary, substats."""
    if not a:
        return "(empty)"
    slot = SLOT_NAMES.get(a.get("kind"), a.get("kind"))
    prim = a.get("primary") or {}
    pn = STAT_ID_TO_NAME.get(prim.get("stat"), "?")
    pv = prim.get("value", 0)
    pflag = "" if prim.get("flat") else "%"
    subs = []
    for s in (a.get("substats") or []):
        sn = STAT_ID_TO_NAME.get(s.get("stat"), "?")
        sv = s.get("value", 0)
        sflag = "" if s.get("flat") else "%"
        subs.append(f"{sn}{sv:.0f}{sflag}")
    return (f"{slot:7s} {_set_name(a.get('set')):12s} "
            f"P:{pn}{pv:.0f}{pflag:1s} | " + ", ".join(subs)
            + f"  (id {a.get('id')})")


def _apply_spd(setup, idx, spd_by_name):
    """Pin each hero's in-sim SPD to the holding-tune value (the override
    team_tune._score_combo does). Cadence is then identical across runs."""
    for n, spd in spd_by_name.items():
        if n in idx:
            setup["stats_per_hero"][idx[n]][SPD] = float(spd)


def regear(element="spirit", anneal=8, max_combos=200, verbose=False):
    element_id = ELEMENT_NAME_TO_ID[element]
    try:
        import boss_constraints
        floor = int(boss_constraints.acc_floor("clan_boss") or 225)
    except Exception:
        floor = 225

    # ---- find the HOLDING SPD tune (the ~37.7M T50 config) via team_tune. ---- #
    # The current-gear natural SPDs do NOT hold in cb_sim (it under-survives);
    # the tuned config does. We pin BOTH baseline and re-gear to this same tune
    # so the comparison is pure damage (identical boss cadence). NOT hardcoded —
    # re-derived here in the same harness each run.
    tune = team_tune.tune_and_score(MEN, element=element, gear="current",
                                    adaptive=True, max_combos=max_combos,
                                    verbose=verbose)
    tune_spd = tune.get("spd_assignment") or {}
    if verbose:
        print(f"[tune] holding SPDs: {tune_spd}  "
              f"(team_tune tuned={tune['tuned_fitness']/1e6:.2f}M "
              f"holds={tune['holds_t50']})")

    # ---- build the team on CURRENT gear + flagship preset. ------------------- #
    setup = _build_team_setup(MEN, use_current_gear=True)
    if isinstance(setup, dict) and setup.get("error"):
        raise RuntimeError(setup["error"])
    names = setup["hero_names"]
    idx = {n: i for i, n in enumerate(names)}

    # SPD per dealer for the gear solve = the holding-tune SPD (fall back to
    # current gear SPD if the tuner couldn't assign one).
    cur_spd = {n: int(round(tune_spd.get(
        n, setup["stats_per_hero"][idx[n]][SPD]))) for n in names}
    cur_stats = {n: dict(setup["stats_per_hero"][idx[n]]) for n in names}

    # baseline = current gear, SPD pinned to the holding tune (apples-to-apples
    # with the re-gear; should reproduce team_tune's tuned number).
    base_setup = copy.deepcopy(setup)
    _apply_spd(base_setup, idx, cur_spd)
    baseline = _run_sim(base_setup, element_id)

    # ---- gear solve for the 3 dealers (team-aware contention). --------------- #
    arts, heroes, account = gto.load_data()
    opt = gto.Optimizer(arts, heroes, account)

    # exclude survival heroes' CURRENT equipped gear from the dealers' vault.
    used = set()
    for sn in SURVIVORS:
        h = opt.heroes_by_name.get(sn.lower())
        for a in (h.get("artifacts") if h else []) or []:
            if a.get("id") is not None:
                used.add(a["id"])

    solves = {}
    # hardest-SPD-first so the tightest tune claims its boots before the others.
    for name in sorted(DEALERS, key=lambda n: -cur_spd[n]):
        tspd = cur_spd[name]
        mins = {SPD: tspd, ACC: floor}
        maxs = {SPD: tspd + SPD_TOL}
        targets = gto.build_targets(mins, maxs, dict(DAMAGE_WEIGHTS), None)
        r = opt.optimize(name, targets, anneal=anneal, exclude_ids=used)
        for a in (r.get("assignment") or {}).values():
            if a and a.get("id") is not None:
                used.add(a["id"])
        solves[name] = r
        if verbose:
            st = r["stats"]
            print(f"[solve] {name}: SPD {st[SPD]:.0f} ACC {st[ACC]:.0f} "
                  f"ATK {st[ATK]:.0f} CR {st[CR]:.0f} CD {st[CD]:.0f} "
                  f"mins_met={r['mins_met']}")

    # ---- re-score: override dealer stats, FORCE SPD to the holding tune. ----- #
    # Survivors keep current-gear stats; all 5 SPDs are pinned to the same
    # holding tune as the baseline, so only the dealers' damage stats differ.
    setup2 = copy.deepcopy(setup)
    _apply_spd(setup2, idx, cur_spd)
    for name in DEALERS:
        new = dict(setup2["stats_per_hero"][idx[name]])
        new.update(solves[name]["stats"])     # combat stats from hypothetical solve
        new[SPD] = float(cur_spd[name])        # re-pin cadence (solve may drift +TOL)
        setup2["stats_per_hero"][idx[name]] = new
    regeared = _run_sim(setup2, element_id)

    return {
        "element": element, "element_id": element_id, "acc_floor": floor,
        "baseline": baseline, "regeared": regeared, "tune": tune,
        "cur_spd": cur_spd, "cur_stats": cur_stats,
        "solves": solves, "names": names, "idx": idx, "opt": opt,
    }


def _print_report(R):
    floor = R["acc_floor"]
    base, re = R["baseline"], R["regeared"]
    print("\n" + "=" * 78)
    print(f" MEN re-gear for damage  -  element={R['element']}  "
          f"(CB UNM, deterministic cb_sim ESTIMATE)")
    print("=" * 78)
    print(" holding SPD tune (pinned for BOTH runs): "
          + ", ".join(f"{n}={R['cur_spd'][n]}" for n in R["names"]))

    # --- per-dealer stat before/after + swaps --------------------------------- #
    for name in DEALERS:
        cs = R["cur_stats"][name]
        ns = R["solves"][name]["stats"]
        print(f"\n--- {name} ---")
        print(f"  {'stat':4s} {'before':>8s} {'after':>8s}  {'delta':>8s}")
        for sid in (ACC, CD, ATK, CR, SPD):
            b, a = cs.get(sid, 0), ns.get(sid, 0)
            tag = ""
            if sid == ACC:
                tag = f"   (floor {floor}; was +{b - floor:.0f} over)"
            print(f"  {STAT_ID_TO_NAME[sid]:4s} {b:8.0f} {a:8.0f}  "
                  f"{a - b:+8.0f}{tag}")

        # swaps: diff current equipped vs solved assignment, per slot.
        opt = R["opt"]
        h = opt.heroes_by_name.get(name.lower())
        cur = {a.get("kind"): a for a in (h.get("artifacts") if h else []) or []}
        new = R["solves"][name]["assignment"]
        changed = 0
        print("  gear swaps (only changed slots):")
        for slot in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            ca, na = cur.get(slot), new.get(slot)
            cid = ca.get("id") if ca else None
            nid = na.get("id") if na else None
            if cid == nid:
                continue
            changed += 1
            print(f"    [{SLOT_NAMES.get(slot, slot)}]")
            print(f"      old: {_describe_art(ca)}")
            print(f"      new: {_describe_art(na)}")
        if not changed:
            print("    (none — already optimal for damage at this SPD/ACC)")

    # --- headline before/after ------------------------------------------------ #
    print("\n" + "-" * 78)
    print(" TEAM cb_sim (tuned, same harness, element=" + R["element"] + "):")
    print(f"   BEFORE (current gear):  {base['total']/1e6:7.2f}M   "
          f"holds_T50={base['holds']}  (survives T{base['turns']}, gaps={base['gaps']})")
    print(f"   AFTER  (re-geared):     {re['total']/1e6:7.2f}M   "
          f"holds_T50={re['holds']}  (survives T{re['turns']}, gaps={re['gaps']})")
    delta = re["total"] - base["total"]
    pct = (delta / base["total"] * 100.0) if base["total"] else 0.0
    print(f"   DELTA:                  {delta/1e6:+7.2f}M  ({pct:+.1f}%)")
    print("-" * 78)

    # --- verdict -------------------------------------------------------------- #
    print("\n VERDICT:")
    if not base["holds"]:
        print("   - cb_sim does NOT hold the baseline to T50 (it under-survives;"
              " see memory project_cb_sim_calibration_state). Damage delta below"
              " is still apples-to-apples (same cadence, SPD pinned).")
    survival_ok = re["holds"] == base["holds"] and re["turns"] >= base["turns"]
    if delta > 0.05e6 and survival_ok:
        print(f"   - Re-gearing the dealers for damage LIFTS team damage by "
              f"{delta/1e6:+.2f}M ({pct:+.1f}%) with no survival cost "
              f"(holds unchanged, SPD tune held).")
        print("   - Gear is from the real vault (all_artifacts.json) with team "
              "contention + survivor gear frozen, so the swap list is feasible.")
    elif delta > 0.05e6 and not survival_ok:
        print(f"   - Damage rises {delta/1e6:+.2f}M but survival changed "
              f"(baseline T{base['turns']}/{base['holds']} vs re-gear "
              f"T{re['turns']}/{re['holds']}). Treat with caution.")
    else:
        print(f"   - No meaningful gain ({delta/1e6:+.2f}M). The dealers are "
              "already near-optimal for damage at the tuned SPD/ACC, OR the ACC "
              "overcap sits on pieces whose alternatives don't add CD/ATK. Not "
              "manufacturing an improvement.")
    print("   - cb_sim numbers are ESTIMATES (under-survives, over-rates stalls);"
          " the BEFORE->AFTER delta is the signal, not the absolute M.\n")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--element", default="spirit", choices=list(ELEMENT_NAME_TO_ID))
    ap.add_argument("--anneal", type=int, default=8,
                    help="gear-solve SA restarts per dealer (higher=better/slower)")
    ap.add_argument("--max-combos", type=int, default=200,
                    help="cap on the team_tune SPD search that finds the holding tune")
    ap.add_argument("--json", help="also dump the result dict to this path")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    R = regear(element=args.element, anneal=args.anneal,
               max_combos=args.max_combos, verbose=args.verbose)
    _print_report(R)

    if args.json:
        dump = {
            "element": R["element"], "acc_floor": R["acc_floor"],
            "baseline": R["baseline"], "regeared": R["regeared"],
            "dealers": {
                n: {
                    "before": {STAT_ID_TO_NAME[s]: R["cur_stats"][n].get(s, 0)
                               for s in ALL_STATS},
                    "after": {STAT_ID_TO_NAME[s]: R["solves"][n]["stats"].get(s, 0)
                              for s in ALL_STATS},
                    "mins_met": R["solves"][n]["mins_met"],
                    "assignment": {SLOT_NAMES.get(k, k): (a.get("id") if a else None)
                                   for k, a in R["solves"][n]["assignment"].items()},
                } for n in DEALERS
            },
        }
        Path(args.json).write_text(json.dumps(dump, indent=2), encoding="utf-8")
        print(f"[json] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
