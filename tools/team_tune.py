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

# Adaptive search (coarse->fine). The COARSE pass sweeps these WIDE offsets per
# hero (so a tune needing a big move — e.g. MEN Ninja +18, see memory
# project_speed_tune_finder — is reachable, which the narrow auto grid above
# misses). The FINE pools refine around the basin the coarse pass located.
_ADAPT_WIDE = (-20, -10, 0, 10, 20)
_FINE_POOLS = (
    (-6, -3, 0, 3, 6),         # 5 values
    (-6, 0, 6),                # 3 values
    (-6, 0),                   # 2 values
    (0,),                      # 1 value
)

# CB UNM ACC floor (boss RES derived) — game-truth from boss_constraints; the
# literal is only the fallback if that table can't be imported.
_DEFAULT_ACC_FLOOR = 225


def _resolve_element(element) -> int:
    if isinstance(element, int):
        return element
    key = str(element).strip().lower()
    if key not in ELEMENT_NAME_TO_ID:
        raise ValueError(f"unknown element {element!r} "
                         f"(use one of {list(ELEMENT_NAME_TO_ID)})")
    return ELEMENT_NAME_TO_ID[key]


def auto_grids(base_spd: list[int], max_combos: int,
               lever_idx: Optional[list[int]] = None,
               pools=_OFFSET_POOLS) -> dict:
    """Build a bounded per-hero SPD grid (as a finder --vary dict keyed by
    slot index) that searches SPD-space without exceeding `max_combos`.

    Varies every hero by default (lever_idx=None); pass lever_idx to restrict
    the search to specific slots. Picks the richest offset pool whose cartesian
    product fits the budget, so the search is as fine as the time allows.
    `pools` overrides the offset schedule (the adaptive FINE pass passes a
    centered small-offset schedule).
    """
    n = len(base_spd)
    vary_idx = list(range(n)) if lever_idx is None else list(lever_idx)
    chosen = pools[-1]
    for pool in pools:
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


def _coarse_basin(score_fn, base_spd, wide_offsets, budget) -> tuple:
    """COARSE pass of the adaptive search: coordinate-descent over WIDE offsets.

    Sweep each hero across `wide_offsets` (holding the others at the running-best
    center) and keep the offset that most improves survival, then move to the
    next hero. Cost is ≤ 1 + n*(len(wide)-1) sims — it finds the survival BASIN
    without paying for a full wide cartesian (5 wide values over 5 heroes would
    be 3125 sims, way over budget). Returns (center_spd_list, sims_used).
    `score_fn` is the memoized scorer, so re-tried combos are free.
    """
    center = list(base_spd)
    base_m = score_fn(tuple(center))
    best_key = (base_m["holds"], base_m["turns"], base_m["total"])
    used = 1
    for i in range(len(center)):
        local_best = center[i]
        for off in wide_offsets:
            cand = max(1, base_spd[i] + off)
            if cand == center[i]:
                continue
            if used >= budget:
                break
            trial = list(center)
            trial[i] = cand
            m = score_fn(tuple(trial))
            used += 1
            key = (m["holds"], m["turns"], m["total"])
            if key > best_key:
                best_key, local_best = key, cand
        center[i] = local_best
        if used >= budget:
            break
    return center, used


def _base_name(name: str) -> str:
    """Strip a duplicate-instance suffix ('Maneater_2' -> 'Maneater') so the gear
    optimizer (keyed by real hero name) resolves the champion."""
    if "_" in name:
        head, _, tail = name.rpartition("_")
        if tail.isdigit() and head:
            return head
    return name


# ---- tune_compat (UNTUNABLE-by-construction detection, task #50 B2) --------- #
# A comp containing a `hard_breaker` (a hero whose kit puts FLAT, team-wide
# Increase SPD on every cycle — e.g. Teodor the Savant) cannot hold a FIXED
# speed-tune: the recurring SPD buff shifts every champion's turn-meter gain, so
# any cadence the search "finds" desyncs the moment the buff lands/expires. The
# M1 record's `tune_compat` field (data/m5_synergy.jsonl) flags this:
#   hard_breaker = flat team Increase SPD -> NO fixed tune holds (untunable).
#   manageable   = conditional/self TM only (Ninja) -> tunes build around it.
#   ok           = no cadence interference.
# We DETECT hard_breaker and EXPLAIN it instead of reporting a doomed tune.
def _tune_compat(name: str) -> str:
    """`tune_compat` for one hero (hard_breaker | manageable | ok), safe-default
    'ok' if the hero is missing from m5_synergy.jsonl or the loader is absent."""
    try:
        import fitness.synergy_data as sd
        rec = sd.get_record(_base_name(name))
        if rec:
            return str(rec.get("tune_compat") or "ok").lower()
    except Exception:
        pass
    return "ok"


def _hard_breakers(comp: list[str]) -> list[str]:
    """Names in `comp` flagged hard_breaker (flat team Increase SPD). A non-empty
    list means the comp is UNTUNABLE by construction — no fixed speed-tune holds.
    `manageable` (Ninja) and `ok` are NOT breakers (full tune search as today)."""
    return [nm for nm in comp if _tune_compat(nm) == "hard_breaker"]


def _untunable_reason(breakers: list[str]) -> str:
    """Human reason for the untunable verdict, naming the offending hero(es)."""
    names = ", ".join(breakers)
    return f"{names}'s Increase SPD breaks the speed-tune cadence"


def _untunable_marker(breakers: list[str]) -> str:
    """Short --compare marker, e.g. 'UNTUNABLE (Teodor the Savant Increase SPD)'."""
    return f"UNTUNABLE ({', '.join(breakers)} Increase SPD)"


def _cb_acc_floor(location: str = "clan_boss") -> int:
    """ACC floor (boss-RES-derived) from game-truth boss_constraints; falls back
    to the CB-UNM literal if the constraint table can't be loaded."""
    try:
        import boss_constraints
        v = boss_constraints.acc_floor(location)
        if v:
            return int(v)
    except Exception:
        pass
    return _DEFAULT_ACC_FLOOR


def gear_feasibility(comp: list[str], spd_targets: dict, element="spirit", *,
                     acc_floor: Optional[int] = None, location: str = "clan_boss",
                     anneal: int = 3, opt=None, spd_tol: int = 2) -> dict:
    """Feasibility-check a FOUND tune against the user's ACTUAL VAULT gear.

    A tune from `tune_and_score` only re-assigns SPD INSIDE the sim — it does NOT
    prove the user can BUILD those speeds (plus the debuffers' ACC floor) from
    their vault. This wires in the existing per-champion gear optimizer
    (`gear_target_optimizer.Optimizer.optimize` — the M6 stat-target solver, the
    same one `cb_recommender._solve_rec` uses for on-demand regear feasibility)
    to answer "buildable on your gear?".

    Per hero the targets are {SPD: tuned spd} and, for DEBUFFERS only (heroes the
    game-truth `cb_profiles` profile flags `needs_acc`), {ACC: acc_floor}. Heroes
    are solved hardest-SPD-first with artifact CONTENTION — a piece assigned to
    one hero is removed from the next hero's candidate vault (`exclude_ids`),
    exactly as `_solve_rec` does — so the verdict reflects the whole team sharing
    ONE vault, not five independent solves double-counting the same speed boots.

    Args:
      comp: the 5 hero names (order is informational; the solve order is by SPD).
      spd_targets: {hero_name: spd} — the tuned SPD assignment to feasibility-check.
      element: accepted for symmetry / validation; the ACC floor is the CB-UNM
               boss-RES floor (the only location with a fixed CB tune today).
      acc_floor: override the boss_constraints floor (else 225 for clan_boss).
      opt: a pre-built gear_target_optimizer.Optimizer to REUSE across comps
           (building it loads + indexes the whole vault). Built on demand if None.

    Returns:
      {feasible: bool, acc_floor: int,
       per_hero: {name: {reachable, spd_gap, acc_ok, achieved_spd, achieved_acc,
                         target_spd, needs_acc, notes}}}.
    """
    from cb_optimizer import SPD, ACC
    import cb_profiles
    import gear_target_optimizer as gto

    _resolve_element(element)          # validate the element name/id
    floor = int(acc_floor) if acc_floor is not None else _cb_acc_floor(location)

    if opt is None:
        arts, heroes, account = gto.load_data()
        opt = gto.Optimizer(arts, heroes, account)

    names = list(comp) if comp else list(spd_targets.keys())
    needs_acc = {}
    for nm in names:
        try:
            needs_acc[nm] = bool(cb_profiles.resolve(_base_name(nm)).needs_acc)
        except Exception:
            needs_acc[nm] = False

    per_hero: dict = {}
    used: set = set()
    order = sorted(names, key=lambda nm: -int(spd_targets.get(nm, 0)))
    for nm in order:
        tspd = int(round(spd_targets.get(nm, 0)))
        mins = {SPD: tspd}
        if needs_acc[nm]:
            mins[ACC] = floor
        targets = gto.build_targets(mins, {}, {}, None)
        notes: list[str] = []
        try:
            r = opt.optimize(_base_name(nm), targets, anneal=anneal,
                             exclude_ids=used)
        except Exception as e:
            per_hero[nm] = {"reachable": False, "spd_gap": tspd, "acc_ok": False,
                            "achieved_spd": None, "achieved_acc": None,
                            "target_spd": tspd, "needs_acc": needs_acc[nm],
                            "notes": [f"gear solve failed: {type(e).__name__}: {e}"]}
            continue
        for a in (r.get("assignment") or {}).values():
            if a and a.get("id") is not None:
                used.add(a["id"])
        stats = r["stats"]
        aspd = int(round(stats.get(SPD, 0)))
        aacc = int(round(stats.get(ACC, 0)))
        spd_gap = (tspd - aspd) if aspd < tspd - spd_tol else 0
        acc_ok = (not needs_acc[nm]) or aacc >= floor
        reachable = (spd_gap == 0) and acc_ok
        if spd_gap:
            notes.append(f"needs +{spd_gap} SPD (vault best {aspd}, target {tspd})")
        if needs_acc[nm] and not acc_ok:
            notes.append(f"short {floor - aacc} ACC (vault best {aacc}, "
                         f"floor {floor})")
        if reachable:
            notes.append("buildable on your gear")
        per_hero[nm] = {"reachable": reachable, "spd_gap": spd_gap,
                        "acc_ok": acc_ok, "achieved_spd": aspd,
                        "achieved_acc": aacc, "target_spd": tspd,
                        "needs_acc": needs_acc[nm], "notes": notes}
    feasible = bool(per_hero) and all(h["reachable"] for h in per_hero.values())
    return {"feasible": feasible, "acc_floor": floor, "per_hero": per_hero}


def _gear_feasibility_note(gf: dict) -> str:
    """One-line human summary of a gear_feasibility result for the CLI/notes."""
    if not gf:
        return ""
    if gf["feasible"]:
        return "GEAR: buildable on your vault (all SPD targets + ACC floor met)."
    shorts = []
    for nm, h in gf["per_hero"].items():
        if h["reachable"]:
            continue
        bits = []
        if h["spd_gap"]:
            bits.append(f"+{h['spd_gap']} SPD")
        if h["needs_acc"] and not h["acc_ok"] and h["achieved_acc"] is not None:
            bits.append(f"{gf['acc_floor'] - h['achieved_acc']} ACC")
        shorts.append(f"{nm} short {' / '.join(bits) or 'gear'}")
    return "GEAR: NOT buildable as-is — " + "; ".join(shorts) + "."


_SCHEMA_KEYS = ("spd_assignment", "tuned_fitness", "holds_t50",
                "tune_found", "tunable", "untunable_reason", "notes")


def _untunable_result(comp_names, setup, base_spd, element_id, gear,
                      breakers, notes) -> dict:
    """A hard_breaker comp is UNTUNABLE by construction (a fixed speed-tune can't
    hold the cadence). DO NOT search SPD-space for a holding tune; instead score
    the comp ONCE on its NATURAL speeds as a STALL (a hard_breaker comp may still
    survive without a tune) and EXPLAIN why no tune is reported.
    """
    base_combo = tuple(base_spd)
    natural = _score_combo(setup, base_combo, element_id)
    reason = _untunable_reason(breakers)
    notes.append(
        f"UNTUNABLE by construction: {reason}. A FIXED speed-tune cannot hold "
        f"the boss cadence for this comp, so NO holding speed-tune is reported "
        f"(the SPD search was skipped — it would only surface a doomed pseudo-"
        f"tune).")
    notes.append(
        f"Scored as a STALL on natural speeds (untunable): T{natural['turns']} "
        f"/ {natural['total']/1e6:.1f}M — a hard_breaker comp can still survive "
        f"as a stall without a tune.")
    notes.append("Damage is a cb_sim ESTIMATE (sim under-survives, over-rates "
                 "stalls); use it to rank, not as an absolute clear check.")
    return {
        # natural speeds, clearly NOT presented as a found tune (tune_found=False,
        # tunable=False) — informational so the user sees the actual speeds.
        "spd_assignment": dict(zip(comp_names, [int(x) for x in base_combo])),
        "tuned_fitness": natural["total"],
        "holds_t50": natural["holds"],
        "tune_found": False,
        "tunable": False,
        "untunable_reason": reason,
        "notes": notes,
        # extras
        "base_spd": dict(zip(comp_names, base_spd)),
        "natural": natural,
        "best": natural,
        "combos_evaluated": 1,
        "gear": gear,
        "gear_feasibility": None,
        "element": element_id,
        "source": "hard_breaker detection -> natural-speed STALL sim "
                  "(no SPD search)",
        "team": list(comp_names),
    }


def tune_and_score(comp: list[str], *, element="spirit", gear: str = "current",
                   vary: Optional[dict] = None, max_combos: int = 243,
                   lever_idx: Optional[list[int]] = None,
                   adaptive: bool = False, check_gear: bool = False,
                   gear_opt=None, verbose: bool = False) -> dict:
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
      max_combos: hard cap on the auto search (≈ seconds at ~1s/combo). For the
            adaptive search this caps coarse + fine sims COMBINED.
      lever_idx: restrict the auto search to these slot indices (default: all).
      adaptive: COARSE-then-FINE search (only without an explicit `vary`). A
            coordinate-descent coarse pass over WIDE offsets {-20..+20} locates
            the survival basin, then a fine cartesian over small offsets refines
            around it — reaching big tune moves the narrow auto grid misses,
            still within `max_combos`.
      check_gear: also feasibility-check the found tune against the user's actual
            VAULT gear (gear_feasibility). OFF by default — the gear solve loads
            and SA-searches the whole vault per hero (a few seconds).
      gear_opt: reuse a pre-built gear_target_optimizer.Optimizer for check_gear
            (so --compare builds the vault index once, not per comp).

    Returns a dict with the requested schema keys:
      spd_assignment {name: spd}, tuned_fitness (best total damage, float),
      holds_t50 (bool), tune_found (bool — did the search beat the natural
      speeds), notes [str].
    Plus extras: base_spd, natural (the offset-0 result), best (the chosen
    result), combos_evaluated, gear, element, source.
    """
    element_id = _resolve_element(element)
    notes: list[str] = []

    # --- UNTUNABLE-by-construction gate (task #50 B2). ----------------------- #
    # If the comp contains a hard_breaker (flat team Increase SPD), no FIXED
    # speed-tune can hold the boss cadence. Detect up front so we never present a
    # doomed pseudo-tune; we still score it as a natural-speed STALL below.
    breakers = _hard_breakers(comp)

    # --- build the team once (real gear + flagship preset). ----------------- #
    try:
        from cb_sim import _build_team_setup, SPD
        setup = _build_team_setup(comp, use_current_gear=(gear == "current"))
    except Exception as e:  # surfacing > swallowing
        setup = {"error": f"{type(e).__name__}: {e}"}

    if isinstance(setup, dict) and setup.get("error"):
        # Can't set up on current/optimal gear (e.g. unowned + no gear). Fall
        # back to the potential-gear NATURAL sim — UNTUNED, clearly labelled.
        return _potential_fallback(comp, element_id, gear, setup["error"], notes,
                                   breakers=breakers)

    hero_names = setup["hero_names"]
    base_spd = [int(round(setup["stats_per_hero"][i][SPD]))
                for i in range(len(hero_names))]

    if breakers:
        # Skip the SPD search entirely — score natural speeds as a stall + explain.
        return _untunable_result(hero_names, setup, base_spd, element_id, gear,
                                 breakers, notes)

    # --- build the SPD search grid (slot-indexed). -------------------------- #
    import itertools
    n = len(hero_names)
    base_combo = tuple(base_spd)
    explicit = bool(vary)

    # memoized survival+damage scorer — one full sim per UNIQUE combo, so the
    # adaptive coarse pass and the fine grid never pay twice for the same combo.
    cache: dict = {}

    def _score(combo):
        combo = tuple(int(x) for x in combo)
        if combo not in cache:
            cache[combo] = _score_combo(setup, combo, element_id)
        return cache[combo]

    if explicit:
        gv = _normalize_vary(vary, hero_names)
        grids = {i: gv.get(i, [base_spd[i]]) for i in range(n)}
        for i in range(n):                     # ensure natural speeds are tried
            if base_spd[i] not in grids[i]:
                grids[i] = sorted(set(grids[i]) | {base_spd[i]})
        offsets = None
    elif adaptive:
        # COARSE (coordinate-descent over WIDE {-20..+20}) -> FINE (small-offset
        # cartesian centered on the basin). Budget schedule: the coarse pass uses
        # ~1+n*(len(WIDE)-1) sims (≤21 for 5 heroes); the FINE grid is then
        # picked to fit the REMAINING budget so coarse+fine ≤ max_combos.
        center, _used = _coarse_basin(_score, base_spd, _ADAPT_WIDE, max_combos)
        fine_budget = max(1, max_combos - len(cache))
        ag = auto_grids(center, fine_budget, lever_idx, pools=_FINE_POOLS)
        grids = ag["grids"]
        offsets = ag["offsets"]
        if verbose:
            print(f"[team_tune] adaptive: coarse basin "
                  f"{dict(zip(hero_names, center))} in {len(cache)} sims; "
                  f"fine offsets {offsets} (budget {fine_budget})")
    else:
        ag = auto_grids(base_spd, max_combos, lever_idx)
        grids = ag["grids"]
        offsets = ag["offsets"]

    combos = _product([len(grids[i]) for i in range(n)])
    # The fine grid is already bounded to the remaining budget; only the explicit
    # / narrow-auto paths can over-shoot, so guard those.
    if not adaptive and combos > max_combos:
        raise ValueError(f"search grid is {combos} combos (> max_combos "
                         f"{max_combos}); narrow --vary or raise --max-combos")
    if verbose and not adaptive:
        mode = "explicit --vary" if explicit else f"auto offsets {offsets}"
        print(f"[team_tune] {','.join(comp)} | {gear} gear | "
              f"element={element_id} | {combos} combos ({mode})")

    # --- evaluate the grid (coarse results already cached for adaptive). ----- #
    for combo in itertools.product(*(grids[i] for i in range(n))):
        m = _score(combo)
        if verbose:
            print(f"    {dict(zip(hero_names, tuple(int(x) for x in combo)))} -> "
                  f"T{m['turns']} gaps={m['gaps']} {m['total']/1e6:.2f}M"
                  f"{' HOLDS' if m['holds'] else ''}")
    natural = _score(base_combo)               # always evaluate natural speeds

    # best over EVERYTHING evaluated (coarse + fine + natural).
    best = best_combo = None
    for combo, m in cache.items():
        key = (m["holds"], m["turns"], m["total"])
        if best is None or key > (best["holds"], best["turns"], best["total"]):
            best, best_combo = m, combo
    n_eval = len(cache)

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

    spd_assignment = dict(zip(hero_names, [int(x) for x in best_combo]))

    # --- ACTIONABILITY: can the user actually BUILD this tune? --------------- #
    gear_feas = None
    if check_gear and gear == "current":
        try:
            gear_feas = gear_feasibility(list(hero_names), spd_assignment,
                                         element=element_id, opt=gear_opt)
            notes.append(_gear_feasibility_note(gear_feas))
        except Exception as e:                  # surface, don't swallow
            notes.append(f"GEAR: feasibility check failed "
                         f"({type(e).__name__}: {e}).")

    return {
        "spd_assignment": spd_assignment,
        "tuned_fitness": best["total"],
        "holds_t50": best["holds"],
        "tune_found": tune_found,
        "tunable": True,
        "untunable_reason": "",
        "notes": notes,
        # extras
        "base_spd": dict(zip(hero_names, base_spd)),
        "natural": natural,
        "best": best,
        "combos_evaluated": n_eval,
        "gear": gear,
        "gear_feasibility": gear_feas,
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


def _potential_fallback(comp, element_id, gear, err, notes,
                        breakers: Optional[list[str]] = None) -> dict:
    """Current/optimal-gear setup failed — report the potential-gear NATURAL
    (untuned) sim so the caller still gets a comparable number, clearly flagged
    as UNTUNED.

    `breakers` (hard_breaker members) is carried through so the result still
    reports tunable=False + the reason even when the comp couldn't be set up on
    current/optimal gear (the SPD search never runs in this path anyway)."""
    breakers = breakers or []
    tunable = not breakers
    untunable_reason = _untunable_reason(breakers) if breakers else ""
    if breakers:
        notes.append(f"UNTUNABLE by construction: {untunable_reason} "
                     f"(no fixed speed-tune holds; SPD search skipped).")
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
                "holds_t50": False, "tune_found": False,
                "tunable": tunable, "untunable_reason": untunable_reason,
                "notes": notes,
                "natural": None, "best": None, "combos_evaluated": 0,
                "gear": "potential", "gear_feasibility": None,
                "element": element_id,
                "source": "fallback (failed)", "team": list(comp)}
    total = float(r.get("total", 0.0) or 0.0)
    holds = (r.get("cb_turns", 0) >= 50) and bool(r.get("valid"))
    notes.append("TUNED damage is a cb_sim ESTIMATE; this is the UNTUNED "
                 "potential-gear floor (no SPD search ran).")
    return {"spd_assignment": None, "tuned_fitness": total,
            "holds_t50": holds, "tune_found": False,
            "tunable": tunable, "untunable_reason": untunable_reason,
            "notes": notes,
            "natural": {"turns": r.get("cb_turns"), "gaps": None,
                        "holds": holds, "total": total},
            "best": {"turns": r.get("cb_turns"), "gaps": None,
                     "holds": holds, "total": total},
            "combos_evaluated": 0, "gear": "potential",
            "gear_feasibility": None,
            "element": element_id,
            "source": "cb_potential.simulate_team (UNTUNED fallback)",
            "team": list(comp)}


# ====================================================================== compare
def compare(comps: list, *, element="spirit", gear: str = "current",
            max_combos: int = 243, adaptive: bool = False,
            check_gear: bool = False, verbose: bool = False) -> list:
    """Tune+score each comp; return rows sorted by TUNED damage (desc) so the
    comps are comparable tune-vs-tune. `comps` is a list of (label, team)
    tuples or bare team lists."""
    # Build the vault-wide gear optimizer ONCE and share it across comps (its
    # construction indexes the whole vault — per-comp rebuild would be wasteful).
    gear_opt = None
    if check_gear and gear == "current":
        try:
            import gear_target_optimizer as gto
            arts, heroes, account = gto.load_data()
            gear_opt = gto.Optimizer(arts, heroes, account)
        except Exception as e:
            if verbose:
                print(f"[team_tune] gear optimizer unavailable: {e}")
    rows = []
    for item in comps:
        if isinstance(item, tuple):
            label, team = item
        else:
            label, team = ", ".join(item), list(item)
        if verbose:
            print(f"\n=== tuning: {label} ===")
        res = tune_and_score(team, element=element, gear=gear,
                             max_combos=max_combos, adaptive=adaptive,
                             check_gear=check_gear, gear_opt=gear_opt,
                             verbose=verbose)
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
          f"{'turns':>5} {'gear':>9}  team")
    print("  " + "-" * 100)
    for i, (label, team, res) in enumerate(rows, 1):
        untunable = res.get("tunable") is False
        # For an untunable comp show the marker in place of a tuned number, so it
        # reads "UNTUNABLE (...)" rather than a fake "31.1M dies T41" tune.
        dmg = "UNTUNABLE" if untunable else f"{res['tuned_fitness']/1e6:.2f}M"
        holds = "Y" if res["holds_t50"] else "."
        tuned = "UNT" if untunable else ("Y" if res["tune_found"] else ".")
        turns = res["best"]["turns"] if res.get("best") else "?"
        gf = res.get("gear_feasibility")
        gear_c = ("buildable" if gf and gf["feasible"]
                  else "INFEAS" if gf else "-")
        print(f"  {i:>2} {dmg:>10} {holds:>5} {tuned:>6} {str(turns):>5} "
              f"{gear_c:>9}  {label}")
    print()
    for label, team, res in rows:
        untunable = res.get("tunable") is False
        spd = res.get("spd_assignment")
        spd_s = (", ".join(f"{k}={v}" for k, v in spd.items())
                 if spd else "(no SPD tune — see notes)")
        nat = res.get("natural") or {}
        nat_s = (f"natural T{nat.get('turns')}/"
                 f"{(nat.get('total') or 0)/1e6:.1f}M"
                 if nat else "n/a")
        print(f"  • {label}")
        if untunable:
            # No fake tuned number — explain the verdict instead.
            print(f"      {_untunable_marker(_hard_breakers(team))}: "
                  f"{res.get('untunable_reason', '')}")
            print(f"      scored as STALL (untunable): "
                  f"T{res['best']['turns'] if res.get('best') else '?'}"
                  f"/{res['tuned_fitness']/1e6:.1f}M natural speeds   "
                  f"(combos={res['combos_evaluated']}, gear={res['gear']})")
        else:
            print(f"      tuned SPD: {spd_s}")
            print(f"      tuned: T{res['best']['turns'] if res.get('best') else '?'}"
                  f"/{res['tuned_fitness']/1e6:.1f}M   vs   {nat_s}   "
                  f"(combos={res['combos_evaluated']}, gear={res['gear']})")
        gf = res.get("gear_feasibility")
        if gf:
            verdict = "BUILDABLE" if gf["feasible"] else "NOT buildable as-is"
            print(f"      gear feasibility: {verdict} "
                  f"(ACC floor {gf['acc_floor']}):")
            for nm, h in gf["per_hero"].items():
                mark = "ok" if h["reachable"] else "XX"
                acc_s = (f" ACC{h['achieved_acc']}" if h["needs_acc"] else "")
                print(f"        [{mark}] {nm}: SPD {h['achieved_spd']}"
                      f"/target {h['target_spd']}{acc_s}"
                      f"{('  -> ' + '; '.join(h['notes'])) if h['notes'] else ''}")
        for nt in res["notes"]:
            print(f"      - {nt}")
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
                    help="cap on the auto SPD search (~1s/combo); for --adaptive "
                         "this caps coarse + fine sims combined")
    ap.add_argument("--adaptive", action="store_true",
                    help="coarse-then-refine SPD search (wide {-20..+20} basin "
                         "scan, then fine refine) — finds big tune moves the "
                         "narrow auto grid misses, still within --max-combos")
    ap.add_argument("--check-gear", action="store_true",
                    help="feasibility-check the found tune against your actual "
                         "VAULT gear (SPD targets + CB ACC floor). Slower (gear "
                         "solve per hero); default off.")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    element_id = ELEMENT_NAME_TO_ID[args.element]

    if args.compare:
        comps = _gather_comps(args)
        if not comps:
            ap.error("--compare needs one of --validate / --teams / "
                     "--from-generator")
        rows = compare(comps, element=args.element, gear=args.gear,
                       max_combos=args.max_combos, adaptive=args.adaptive,
                       check_gear=args.check_gear, verbose=args.verbose)
        _print_compare(rows, element_id)
        return 0

    if not args.team:
        ap.error("pass --team for a single tune, or --compare for a side-by-side")
    team = [t.strip() for t in args.team.split(",") if t.strip()]
    res = tune_and_score(team, element=args.element, gear=args.gear,
                         vary=(args.vary or None), max_combos=args.max_combos,
                         adaptive=args.adaptive, check_gear=args.check_gear,
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
    untunable = res.get("tunable") is False
    nat = res.get("natural") or {}
    if untunable:
        print(_untunable_marker(_hard_breakers(team)) + ":",
              res.get("untunable_reason", ""))
        print(f"natural : T{nat.get('turns')} / "
              f"{(nat.get('total') or 0)/1e6:.2f}M")
        print(f"stall   : T{res['best']['turns'] if res.get('best') else '?'} / "
              f"{res['tuned_fitness']/1e6:.2f}M  holds_t50={res['holds_t50']}  "
              f"tunable=False  (scored as stall, no SPD search)")
    else:
        spd = res.get("spd_assignment")
        if spd:
            print("tuned SPD:", ", ".join(f"{k}={v}" for k, v in spd.items()))
        print(f"natural : T{nat.get('turns')} / "
              f"{(nat.get('total') or 0)/1e6:.2f}M")
        print(f"tuned   : T{res['best']['turns'] if res.get('best') else '?'} / "
              f"{res['tuned_fitness']/1e6:.2f}M  "
              f"holds_t50={res['holds_t50']}  tune_found={res['tune_found']}  "
              f"(combos={res['combos_evaluated']})")
    gf = res.get("gear_feasibility")
    if gf:
        verdict = "BUILDABLE" if gf["feasible"] else "NOT buildable as-is"
        print(f"gear    : {verdict} (ACC floor {gf['acc_floor']})")
        for nm, h in gf["per_hero"].items():
            mark = "ok" if h["reachable"] else "XX"
            acc_s = (f" ACC{h['achieved_acc']}" if h["needs_acc"] else "")
            print(f"          [{mark}] {nm}: SPD {h['achieved_spd']}"
                  f"/target {h['target_spd']}{acc_s}"
                  f"{('  -> ' + '; '.join(h['notes'])) if h['notes'] else ''}")
    print("notes:")
    for n in res["notes"]:
        print("  -", n)
    print()


if __name__ == "__main__":
    raise SystemExit(main())
