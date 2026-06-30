"""Stage 2 of the organic team system — TUNE a generated comp, then score it.

THE PROBLEM (task #46): `tools/team_generator.py` finds role-valid ARCHETYPES
but does NOT speed-tune them. Its cb_sim damage numbers are therefore UNTUNED
floors: a comp is simmed at whatever SPD its current/optimal gear happens to
give, with no search for the SPD assignment that lets the team hold the boss
cadence to T50. A dialed speed-tune like MEN (Maneater/Demytha/Ninja/Geomancer/
Venomage, ~36M real, fully tuned) is therefore NOT comparable to a generated
comp's natural number — and a survival-stall comp floats to the top partly
because it needs no tune AND cb_sim over-rates stalls.

Stage 2 closes that gap: given a comp, SEARCH SPD-space for the assignment that
holds the tune (reusing the existing optimizer), then score the *tuned* config.
Now comps compare tune-vs-tune.

Reuse anchors (cited functions — this module imports, never re-implements):
  - speed_tune_finder.find / .parse_vary / ._validity / .ELEMENT_NAME_TO_ID
        the SPD-space search + the stall validity criterion (survive T50, 0
        UK/BD coverage gaps past the sync turn). Uses the game-truth survival
        model (bugfix_buff_tick=False) exactly as the finder does.
  - cb_sim._build_team_setup / ._build_sim_champs_from_setup / .CBSimulator / .SPD
        build the team once (real gear + flagship preset), override only SPD per
        the search grid, and run the full survival sim for damage.
  - cb_potential.simulate_team
        potential-gear fallback when a comp can't be set up on current gear.
  - team_generator.generate
        the stage-1 archetype generator whose top-K comps --compare can tune.

HONESTY (do not paper over — see memory project_cb_sim_calibration_state):
  * cb_sim UNDER-survives the real game (heroes often die T23-29 deterministic
    vs real T50) and OVER-rates pure stalls. Even a TUNED number here is an
    ESTIMATE and a RANKING signal, not an absolute clear check. Every result is
    labelled accordingly.
  * speed_tune_finder is CB-only and ~1s per SPD combo (deterministic). A full
    5-hero fine grid is intractable, so the auto search is BOUNDED: it picks the
    richest symmetric offset set whose cartesian product fits --max-combos
    (default 243 = a 3-value {-10,0,+6} grid over 5 heroes). Pass --vary for a
    precise, finer search (passed straight through to the finder).
  * If a comp already holds at its base speeds (a pure buff-coverage stall that
    needs no tune) or can't be tuned better, that is REPORTED as tune_found=
    False with the natural survival score — not faked as a found tune.

CLI:
    python tools/team_tune.py --team "Maneater,Demytha,Ninja,Geomancer,Venomage" \
        --element spirit
    python tools/team_tune.py --compare --validate --element spirit
    python tools/team_tune.py --compare \
        --teams "A,B,C,D,E; F,G,H,I,J" --element spirit
    python tools/team_tune.py --compare --from-generator clan_boss --top 5 \
        --element spirit
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speed_tune_finder as stf  # noqa: E402
from speed_tune_finder import ELEMENT_NAME_TO_ID, parse_vary, _validity  # noqa: E402

# The two comps the task asks to A/B test on a fair tuned-vs-tuned basis.
NOVEL_COMP = ["Arbiter", "Coldheart", "Demytha", "Ninja", "Teodor the Savant"]
MEN_COMP = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]

# Auto-search offset pools, richest-first. Each hero's SPD grid is base+offset.
# 0 is always present so the comp's NATURAL (untuned) speeds are evaluated and
# the tune is measured as the delta over them. Reaches -10 (slow a keystone, the
# common MEN lever: Demytha 184->174) and +6/+8 (speed a lead) within budget.
_OFFSET_POOLS = (
    (-10, -6, -2, 0, 4, 8),    # 6 values
    (-10, -5, 0, 5),           # 4 values
    (-10, 0, 6),               # 3 values  (5 heroes -> 243 combos)
    (-10, 0),                  # 2 values
    (0,),                      # 1 value   (single-point = natural only)
)


def _resolve_element(element) -> int:
    if isinstance(element, int):
        return element
    key = str(element).strip().lower()
    if key not in ELEMENT_NAME_TO_ID:
        raise ValueError(f"unknown element {element!r} "
                         f"(use one of {list(ELEMENT_NAME_TO_ID)})")
    return ELEMENT_NAME_TO_ID[key]


def auto_grids(base_spd: list[int], max_combos: int,
               lever_idx: Optional[list[int]] = None) -> dict:
    """Build a bounded per-hero SPD grid (as a finder --vary dict keyed by
    slot index) that searches SPD-space without exceeding `max_combos`.

    Varies every hero by default (lever_idx=None); pass lever_idx to restrict
    the search to specific slots. Picks the richest offset pool whose cartesian
    product fits the budget, so the search is as fine as the time allows.
    """
    n = len(base_spd)
    vary_idx = list(range(n)) if lever_idx is None else list(lever_idx)
    chosen = _OFFSET_POOLS[-1]
    for pool in _OFFSET_POOLS:
        if len(pool) ** len(vary_idx) <= max_combos:
            chosen = pool
            break
    grids: dict[int, list[int]] = {}
    for i in range(n):
        if i in vary_idx:
            vals = sorted({max(1, base_spd[i] + o) for o in chosen})
        else:
            vals = [base_spd[i]]
        grids[i] = vals
    return {"grids": grids, "offsets": list(chosen),
            "n_vary": len(vary_idx),
            "combos": _product([len(v) for v in grids.values()])}


def _product(xs):
    out = 1
    for x in xs:
        out *= x
    return out


def _score_combo(setup, combo, element_id) -> dict:
    """Run ONE full survival sim at the given SPD combo; return survival +
    damage. Mirrors speed_tune_finder's deterministic branch (same game-truth
    survival model, bugfix_buff_tick=False) but ALSO captures total damage,
    which the finder's pass/fail metric drops.
    """
    from cb_sim import (_build_sim_champs_from_setup, CBSimulator, SPD)
    for i, spd in enumerate(combo):
        setup["stats_per_hero"][i][SPD] = float(spd)
    champs = _build_sim_champs_from_setup(setup)
    res = CBSimulator(champs, cb_difficulty="ultra-nightmare",
                      cb_element=element_id, deterministic=True,
                      model_survival=True, force_affinity=True,
                      bugfix_buff_tick=False).run(max_cb_turns=50)
    survived, gaps = _validity(res)
    return {"turns": res.get("cb_turns", 0), "gaps": gaps,
            "holds": bool(survived and gaps == 0),
            "total": float(res.get("total", 0.0) or 0.0)}


_SCHEMA_KEYS = ("spd_assignment", "tuned_fitness", "holds_t50",
                "tune_found", "notes")


def tune_and_score(comp: list[str], *, element="spirit", gear: str = "current",
                   vary: Optional[dict] = None, max_combos: int = 243,
                   lever_idx: Optional[list[int]] = None,
                   verbose: bool = False) -> dict:
    """TUNE `comp` (search SPD-space for the holding assignment) then SCORE the
    tuned config via cb_sim. The stage-2 primitive.

    Args:
      comp: 5 hero names.
      element: "magic"|"force"|"spirit"|"void" or the int id (1..4).
      gear: "current" (real equipped gear, owned heroes) or "potential"
            (optimal 6* gear via the artifact optimizer).
      vary: optional finder vary spec — either a {name: [spd...]} / {idx: [...]}
            dict or a "Name=lo..hi:step,..." string (parsed). When given it is
            used VERBATIM (finer, precise search); else a bounded auto grid is
            built under `max_combos`.
      max_combos: hard cap on the auto search (≈ seconds at ~1s/combo).
      lever_idx: restrict the auto search to these slot indices (default: all).

    Returns a dict with the requested schema keys:
      spd_assignment {name: spd}, tuned_fitness (best total damage, float),
      holds_t50 (bool), tune_found (bool — did the search beat the natural
      speeds), notes [str].
    Plus extras: base_spd, natural (the offset-0 result), best (the chosen
    result), combos_evaluated, gear, element, source.
    """
    element_id = _resolve_element(element)
    notes: list[str] = []

    # --- build the team once (real gear + flagship preset). ----------------- #
    try:
        from cb_sim import _build_team_setup, SPD
        setup = _build_team_setup(comp, use_current_gear=(gear == "current"))
    except Exception as e:  # surfacing > swallowing
        setup = {"error": f"{type(e).__name__}: {e}"}

    if isinstance(setup, dict) and setup.get("error"):
        # Can't set up on current/optimal gear (e.g. unowned + no gear). Fall
        # back to the potential-gear NATURAL sim — UNTUNED, clearly labelled.
        return _potential_fallback(comp, element_id, gear, setup["error"], notes)

    hero_names = setup["hero_names"]
    base_spd = [int(round(setup["stats_per_hero"][i][SPD]))
                for i in range(len(hero_names))]

    # --- build the SPD search grid (slot-indexed). -------------------------- #
    if vary:
        gv = _normalize_vary(vary, hero_names)
        grids = {i: gv.get(i, [base_spd[i]]) for i in range(len(hero_names))}
        for i in range(len(hero_names)):       # ensure natural speeds are tried
            if base_spd[i] not in grids[i]:
                grids[i] = sorted(set(grids[i]) | {base_spd[i]})
        offsets = None
    else:
        ag = auto_grids(base_spd, max_combos, lever_idx)
        grids = ag["grids"]
        offsets = ag["offsets"]

    combos = _product([len(grids[i]) for i in range(len(hero_names))])
    if combos > max_combos:
        raise ValueError(f"search grid is {combos} combos (> max_combos "
                         f"{max_combos}); narrow --vary or raise --max-combos")
    if verbose:
        mode = "explicit --vary" if vary else f"auto offsets {offsets}"
        print(f"[team_tune] {','.join(comp)} | {gear} gear | "
              f"element={element_id} | {combos} combos ({mode})")

    # --- evaluate every combo (survival + damage in one sim each). ---------- #
    import itertools
    base_combo = tuple(base_spd)
    natural = None
    best = None
    best_combo = None
    n_eval = 0
    for combo in itertools.product(*(grids[i] for i in range(len(hero_names)))):
        m = _score_combo(setup, combo, element_id)
        n_eval += 1
        if combo == base_combo:
            natural = m
        # rank: holds first, then survival depth, then damage.
        key = (m["holds"], m["turns"], m["total"])
        if best is None or key > (best["holds"], best["turns"], best["total"]):
            best, best_combo = m, combo
        if verbose:
            print(f"    {dict(zip(hero_names, combo))} -> "
                  f"T{m['turns']} gaps={m['gaps']} {m['total']/1e6:.2f}M"
                  f"{' HOLDS' if m['holds'] else ''}")
    if natural is None:                         # base not in an explicit grid
        natural = _score_combo(setup, base_combo, element_id)
        n_eval += 1

    # --- did the search actually improve on the natural speeds? ------------- #
    nat_key = (natural["holds"], natural["turns"], natural["total"])
    best_key = (best["holds"], best["turns"], best["total"])
    tune_found = best_combo != base_combo and best_key > nat_key

    if best["holds"] and not tune_found and natural["holds"]:
        notes.append("Comp already HOLDS at its natural speeds — no tune needed "
                     "(its 'tune' is the trivial buff-coverage stall). Reporting "
                     "the natural survival score.")
    elif not best["holds"]:
        notes.append(f"No SPD combo searched reaches T50 with 0 UK/BD gaps "
                     f"(best survives {best['turns']} turns). cb_sim UNDER-"
                     f"survives the real game, so this often understates a comp "
                     f"that holds live — treat survival as a lower bound.")
    if tune_found:
        deltas = {hero_names[i]: best_combo[i] - base_spd[i]
                  for i in range(len(hero_names))
                  if best_combo[i] != base_spd[i]}
        notes.append(f"Tune found: SPD deltas vs natural {deltas} lift "
                     f"survival {natural['turns']}->{best['turns']} turns / "
                     f"damage {natural['total']/1e6:.1f}M->"
                     f"{best['total']/1e6:.1f}M.")
    notes.append("TUNED damage is a cb_sim ESTIMATE (sim under-survives, over-"
                 "rates stalls); use it to rank tune-vs-tune, not as an absolute "
                 "clear check.")

    return {
        "spd_assignment": dict(zip(hero_names, best_combo)),
        "tuned_fitness": best["total"],
        "holds_t50": best["holds"],
        "tune_found": tune_found,
        "notes": notes,
        # extras
        "base_spd": dict(zip(hero_names, base_spd)),
        "natural": natural,
        "best": best,
        "combos_evaluated": n_eval,
        "gear": gear,
        "element": element_id,
        "source": "speed_tune_finder SPD search + cb_sim survival sim",
        "team": list(hero_names),
    }


def _normalize_vary(vary, hero_names) -> dict:
    """Accept a finder vary string, a {name:[...]} dict, or a {idx:[...]} dict;
    return {slot_idx: [spd...]}."""
    if isinstance(vary, str):
        vary = parse_vary(vary)
    idx_by_name = {nm: i for i, nm in enumerate(hero_names)}
    out: dict[int, list[int]] = {}
    for k, vals in vary.items():
        if isinstance(k, int):
            out[k] = list(vals)
        elif k in idx_by_name:
            out[idx_by_name[k]] = list(vals)
        else:
            raise ValueError(f"--vary hero {k!r} not in comp {hero_names}")
    return out


def _potential_fallback(comp, element_id, gear, err, notes) -> dict:
    """Current/optimal-gear setup failed — report the potential-gear NATURAL
    (untuned) sim so the caller still gets a comparable number, clearly flagged
    as UNTUNED."""
    notes.append(f"Could not build the comp on {gear} gear ({err}). "
                 f"speed_tune_finder needs gearable (owned) heroes to tune; "
                 f"falling back to the potential-gear NATURAL sim — UNTUNED.")
    try:
        import cb_potential
        r = cb_potential.simulate_team(list(comp), cb_element=element_id)
    except Exception as e:
        r = {"error": f"{type(e).__name__}: {e}", "total": 0}
    if r.get("error"):
        notes.append(f"Potential-gear sim also failed: {r['error']}.")
        return {"spd_assignment": None, "tuned_fitness": 0.0,
                "holds_t50": False, "tune_found": False, "notes": notes,
                "natural": None, "best": None, "combos_evaluated": 0,
                "gear": "potential", "element": element_id,
                "source": "fallback (failed)", "team": list(comp)}
    total = float(r.get("total", 0.0) or 0.0)
    holds = (r.get("cb_turns", 0) >= 50) and bool(r.get("valid"))
    notes.append("TUNED damage is a cb_sim ESTIMATE; this is the UNTUNED "
                 "potential-gear floor (no SPD search ran).")
    return {"spd_assignment": None, "tuned_fitness": total,
            "holds_t50": holds, "tune_found": False, "notes": notes,
            "natural": {"turns": r.get("cb_turns"), "gaps": None,
                        "holds": holds, "total": total},
            "best": {"turns": r.get("cb_turns"), "gaps": None,
                     "holds": holds, "total": total},
            "combos_evaluated": 0, "gear": "potential",
            "element": element_id,
            "source": "cb_potential.simulate_team (UNTUNED fallback)",
            "team": list(comp)}


# ====================================================================== compare
def compare(comps: list, *, element="spirit", gear: str = "current",
            max_combos: int = 243, verbose: bool = False) -> list:
    """Tune+score each comp; return rows sorted by TUNED damage (desc) so the
    comps are comparable tune-vs-tune. `comps` is a list of (label, team)
    tuples or bare team lists."""
    rows = []
    for item in comps:
        if isinstance(item, tuple):
            label, team = item
        else:
            label, team = ", ".join(item), list(item)
        if verbose:
            print(f"\n=== tuning: {label} ===")
        res = tune_and_score(team, element=element, gear=gear,
                             max_combos=max_combos, verbose=verbose)
        rows.append((label, team, res))
    rows.sort(key=lambda r: (r[2]["holds_t50"], r[2]["tuned_fitness"]),
              reverse=True)
    return rows


def _print_compare(rows, element_id: int) -> None:
    elem = {v: k for k, v in ELEMENT_NAME_TO_ID.items()}.get(element_id, element_id)
    print(f"\n=== TUNED side-by-side (element={elem}) — ranked by tuned damage ===")
    print("  cb_sim under-survives + over-rates stalls; numbers are ESTIMATES "
          "for tune-vs-tune ranking.\n")
    print(f"  {'#':>2} {'tuned dmg':>10} {'holds':>5} {'tuned?':>6} "
          f"{'turns':>5}  team")
    print("  " + "-" * 96)
    for i, (label, team, res) in enumerate(rows, 1):
        dmg = f"{res['tuned_fitness']/1e6:.2f}M"
        holds = "Y" if res["holds_t50"] else "."
        tuned = "Y" if res["tune_found"] else "."
        turns = res["best"]["turns"] if res.get("best") else "?"
        print(f"  {i:>2} {dmg:>10} {holds:>5} {tuned:>6} {str(turns):>5}  {label}")
    print()
    for label, team, res in rows:
        spd = res.get("spd_assignment")
        spd_s = (", ".join(f"{k}={v}" for k, v in spd.items())
                 if spd else "(no SPD tune — see notes)")
        nat = res.get("natural") or {}
        nat_s = (f"natural T{nat.get('turns')}/"
                 f"{(nat.get('total') or 0)/1e6:.1f}M"
                 if nat else "n/a")
        print(f"  • {label}")
        print(f"      tuned SPD: {spd_s}")
        print(f"      tuned: T{res['best']['turns'] if res.get('best') else '?'}"
              f"/{res['tuned_fitness']/1e6:.1f}M   vs   {nat_s}   "
              f"(combos={res['combos_evaluated']}, gear={res['gear']})")
        for n in res["notes"]:
            print(f"      - {n}")
    print()


# ========================================================================== CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", help="comma-separated 5 hero names (single tune)")
    ap.add_argument("--compare", action="store_true",
                    help="tune+score a LIST of comps and rank by tuned damage")
    ap.add_argument("--validate", action="store_true",
                    help="with --compare: tune the novel pick vs MEN side by side")
    ap.add_argument("--teams", help="with --compare: 'A,B,C,D,E; F,G,H,I,J'")
    ap.add_argument("--from-generator", dest="from_generator",
                    help="with --compare: pull top-K comps from team_generator "
                         "for this location (e.g. clan_boss)")
    ap.add_argument("--top", type=int, default=5,
                    help="--from-generator: how many top comps to tune")
    ap.add_argument("--element", default="spirit",
                    choices=list(ELEMENT_NAME_TO_ID))
    ap.add_argument("--gear", default="current", choices=["current", "potential"])
    ap.add_argument("--vary", default="",
                    help="explicit finder vary, 'Name=lo..hi:step,...' "
                         "(precise search; overrides the auto grid)")
    ap.add_argument("--max-combos", type=int, default=243,
                    help="cap on the auto SPD search (~1s/combo)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    element_id = ELEMENT_NAME_TO_ID[args.element]

    if args.compare:
        comps = _gather_comps(args)
        if not comps:
            ap.error("--compare needs one of --validate / --teams / "
                     "--from-generator")
        rows = compare(comps, element=args.element, gear=args.gear,
                       max_combos=args.max_combos, verbose=args.verbose)
        _print_compare(rows, element_id)
        return 0

    if not args.team:
        ap.error("pass --team for a single tune, or --compare for a side-by-side")
    team = [t.strip() for t in args.team.split(",") if t.strip()]
    res = tune_and_score(team, element=args.element, gear=args.gear,
                         vary=(args.vary or None), max_combos=args.max_combos,
                         verbose=args.verbose)
    _print_single(team, res)
    return 0


def _gather_comps(args) -> list:
    comps: list = []
    if args.validate:
        comps.append(("NOVEL: " + ", ".join(NOVEL_COMP), list(NOVEL_COMP)))
        comps.append(("MEN: " + ", ".join(MEN_COMP), list(MEN_COMP)))
    if args.teams:
        for chunk in args.teams.split(";"):
            names = [t.strip() for t in chunk.split(",") if t.strip()]
            if names:
                comps.append((", ".join(names), names))
    if args.from_generator:
        comps.extend(_comps_from_generator(args.from_generator, args.top,
                                           ELEMENT_NAME_TO_ID[args.element]))
    return comps


def _comps_from_generator(location: str, top: int, element_id: int) -> list:
    """Pull the top-K stage-1 archetype comps from team_generator (UNTUNED) so
    --compare can tune them and show how the ranking shifts once tuned."""
    import team_generator as tg
    opts = tg.GenOpts(top=top, cb_element=element_id, rank_with="auto")
    res = tg.generate(location, None, opts)
    return [(f"gen#{i+1} {c.skeleton}", list(c.team))
            for i, c in enumerate(res[:top])]


def _print_single(team, res) -> None:
    elem = {v: k for k, v in ELEMENT_NAME_TO_ID.items()}.get(
        res["element"], res["element"])
    print(f"\n=== team_tune: {', '.join(team)} (element={elem}, "
          f"gear={res['gear']}) ===")
    spd = res.get("spd_assignment")
    if spd:
        print("tuned SPD:", ", ".join(f"{k}={v}" for k, v in spd.items()))
    nat = res.get("natural") or {}
    print(f"natural : T{nat.get('turns')} / "
          f"{(nat.get('total') or 0)/1e6:.2f}M")
    print(f"tuned   : T{res['best']['turns'] if res.get('best') else '?'} / "
          f"{res['tuned_fitness']/1e6:.2f}M  "
          f"holds_t50={res['holds_t50']}  tune_found={res['tune_found']}  "
          f"(combos={res['combos_evaluated']})")
    print("notes:")
    for n in res["notes"]:
        print("  -", n)
    print()


if __name__ == "__main__":
    raise SystemExit(main())
