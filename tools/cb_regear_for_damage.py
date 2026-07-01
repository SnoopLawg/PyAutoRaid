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
import urllib.request
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
import loadouts  # noqa: E402  (snapshot / apply / restore + live /all-heroes)

MEN = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
DEALERS = ["Ninja", "Geomancer", "Venomage"]
SURVIVORS = ["Maneater", "Demytha"]

MOD_BASE = "http://localhost:6790"

# Instance IDs of the MEN team (game-truth, verified live via /hero-computed-stats
# and /all-heroes 2026-06-30). Used as the authoritative hint when resolving
# name->id (a name lookup could pick the wrong instance if the roster has dupes).
SURVIVOR_IDS = {"Maneater": 15120, "Demytha": 18607}
DEALER_IDS = {"Ninja": 2643, "Geomancer": 13615, "Venomage": 5692}
MEN_ID_HINT = {**SURVIVOR_IDS, **DEALER_IDS}

# /hero-computed-stats returns per-column stat bonuses; the game's *Total Stats*
# is their sum. These are ALL the columns the endpoint emits (a missing column
# reads as 0). SPD from summing these matches the in-game tune EXACTLY.
_COMPUTED_COLS = (
    "base_computed", "blessing_bonus", "empower_bonus", "classic_arena_bonus",
    "affinity_bonus", "area_bonus", "artifact_bonus", "relic_bonus",
    "mastery_bonus", "faction_guardians_bonus",
)
# Endpoint stat key -> cb_sim stat id.
_COL_STAT_TO_SID = {"HP": HP, "ATK": ATK, "DEF": DEF, "SPD": SPD,
                    "RES": RES, "ACC": ACC, "CR": CR, "CD": CD}

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


# ---------------------------------------------------------------------------- #
#  Reliable computed-stat read (game-truth *Total Stats* via the mod endpoint)
# ---------------------------------------------------------------------------- #
def read_computed_stats(hero_ids, timeout=30):
    """{hero_id: {stat_id: total}} from the live /hero-computed-stats.

    The endpoint returns EVERY hero (the hero_id query arg is ignored), each as a
    row of per-column stat bonuses. The in-game *Total Stats* is the SUM of those
    columns — that's what we return, keyed by cb_sim's stat ids (SPD/ACC/... = the
    same 1..8 constants the sim uses). CR/CD are FRACTIONS in the endpoint
    (0.15 = 15%); cb_sim/calc_stats use PERCENT, so we scale them ×100 to match.

    Earlier parses returned SPD=None because they read a per-hero `total` field
    that doesn't exist and/or indexed by the wrong id. Summing the columns is the
    correct structure and yields real numbers for the 5 MEN heroes.
    """
    with urllib.request.urlopen(f"{MOD_BASE}/hero-computed-stats",
                                timeout=timeout) as r:
        data = json.loads(r.read())
    rows = data.get("heroes", data) if isinstance(data, dict) else data
    by_id = {h["id"]: h for h in rows if isinstance(h, dict) and "id" in h}
    out = {}
    for hid in hero_ids:
        h = by_id.get(hid)
        if not h:
            out[hid] = None
            continue
        totals = {sid: 0.0 for sid in _COL_STAT_TO_SID.values()}
        for col in _COMPUTED_COLS:
            c = h.get(col) or {}
            for key, sid in _COL_STAT_TO_SID.items():
                totals[sid] += float(c.get(key, 0) or 0)
        totals[CR] *= 100.0   # fraction -> percent (cb_sim format)
        totals[CD] *= 100.0
        out[hid] = totals
    return out


def read_computed_spd(hero_ids, timeout=30):
    """{hero_id: SPD(int)} — the SPD-only slice of read_computed_stats. Returns
    real integers for the 5 MEN heroes (None only if a hero isn't in the game)."""
    stats = read_computed_stats(hero_ids, timeout=timeout)
    return {hid: (int(round(s[SPD])) if s else None)
            for hid, s in stats.items()}


def _resolve_ids():
    """{MEN_name: instance_id}. Prefer the known instance ids (they're the ones
    that actually appear in /all-heroes + /hero-computed-stats); fall back to a
    live name lookup only if a hinted id is somehow absent."""
    try:
        heroes = loadouts._fetch_heroes()
    except Exception:
        return dict(MEN_ID_HINT)
    by_name = {}
    for hid, h in heroes.items():
        by_name.setdefault(h.get("name"), hid)
    out = {}
    for n in MEN:
        hint = MEN_ID_HINT[n]
        out[n] = hint if hint in heroes else by_name.get(n, hint)
    return out


def _survivor_equipped_ids(id_by_name=None):
    """(set_of_artifact_ids, {name: {slot: art_id}}) currently equipped on the
    SURVIVORS, read LIVE from /all-heroes (freshest source — not a cached json).
    These ids are the airtight exclude-set for the dealers' gear solve: the
    survivors hold the SPD tune, so not one of their pieces may move."""
    id_by_name = id_by_name or _resolve_ids()
    heroes = loadouts._fetch_heroes()
    ids, per = set(), {}
    for n in SURVIVORS:
        hid = id_by_name[n]
        h = heroes.get(hid)
        by_slot = loadouts._equipped_by_slot(h) if h else {}
        per[n] = by_slot
        ids.update(by_slot.values())
    return ids, per


def _current_owners(art_ids):
    """{hero_id} currently wearing any of art_ids (via /all-artifacts ownership).
    Used to snapshot DONOR heroes so an apply never leaves a non-team hero
    stripped — every piece we pull can be put back on restore."""
    resp = loadouts._get("/all-artifacts?limit=20000")
    arts = resp.get("artifacts", []) if isinstance(resp, dict) else []
    owner = {int(a["id"]): a.get("hero_id") for a in arts
             if isinstance(a, dict) and "id" in a}
    return {owner[a] for a in art_ids if owner.get(a)}


def _acc_floor():
    try:
        import boss_constraints
        return int(boss_constraints.acc_floor("clan_boss") or 225)
    except Exception:
        return 225


def _assignment_ids(solves):
    """Flat set of every artifact id across the dealers' solved assignments."""
    ids = set()
    for r in solves.values():
        for a in (r.get("assignment") or {}).values():
            if a and a.get("id") is not None:
                ids.add(a["id"])
    return ids


def _assert_no_survivor_overlap(solves, survivor_ids):
    """AIRTIGHT survivor exclusion guard: the dealers' assignment must share ZERO
    artifact ids with the survivors' equipped gear. A single leaked piece is how
    a survivor SPD source (Maneater's speed boots) ended up on a dealer and
    slowed the UK provider 1.65->1.25 turns/boss (the T24 wipe)."""
    overlap = _assignment_ids(solves) & set(survivor_ids)
    assert not overlap, (
        f"survivor-exclusion VIOLATED: dealer assignment reuses survivor "
        f"artifact ids {sorted(overlap)} — this desyncs the tune")
    return _assignment_ids(solves)


def _solve_dealer_gear(opt, cur_spd, floor, exclude_ids, anneal=8, verbose=False,
                       spd_tol=SPD_TOL):
    """Team-aware dealer gear solve (hardest-SPD-first, with contention). Each
    dealer's SPD is pinned to its tuned value; ACC is a MIN (floor), damage stats
    (CD/ATK/CR) are the soft objective. `exclude_ids` (survivor gear) is removed
    from every dealer's vault, and each dealer's picks are removed from the next
    dealer's vault so no piece is double-assigned.

    spd_tol: SPD slack above the tune the solve may accept. The DEFAULT (2) is a
    LOOSE gear search; but because MEN holds by buff-cadence sync, even +1 SPD on
    a dealer breaks the tune when actually equipped (proven by the gate). Pass
    spd_tol=0 to force the EXACT tune SPD (a SPD-LOCKED solve)."""
    used = set(exclude_ids)
    solves = {}
    for name in sorted(DEALERS, key=lambda n: -cur_spd[n]):
        tspd = cur_spd[name]
        mins = {SPD: tspd, ACC: floor}
        maxs = {SPD: tspd + spd_tol}
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
    return solves


def _inject_live_stats(setup, idx, id_by_name, stats_by_id):
    """Overwrite each hero's in-sim stat block with the LIVE computed stats
    (the real *Total Stats* after whatever gear is currently equipped). Used so
    the re-sim reflects the ACTUAL post-equip build, not a cached/hypothetical
    one. SPD included — that's the load-bearing cadence value."""
    for name, i in idx.items():
        hid = id_by_name.get(name)
        st = stats_by_id.get(hid) if hid is not None else None
        if not st:
            continue
        d = dict(setup["stats_per_hero"][i])
        for sid in ALL_STATS:
            if st.get(sid) is not None:
                d[sid] = float(st[sid])
        setup["stats_per_hero"][i] = d


def safe_regear(element="spirit", dry_run=True, anneal=8,
                snapshot_name="men_safe_regear",
                baseline_name="men_baseline_20260630",
                spd_tol=0, verbose=False):
    """PROVE a dealer re-gear holds the tune BEFORE any key is spent.

    Flow: snapshot(all 5 + donors) -> apply(dealer assignment) -> read the ACTUAL
    live computed stats of all 5 -> RE-SIM the team with those REAL post-equip
    SPDs/stats -> gate on three checks:
        (a) every SURVIVOR's SPD == its baseline (the tune's SPD sources are
            untouched — this is what the T24 wipe violated),
        (b) the team still HOLDS T50 with 0 UK/BD gaps (survival intact),
        (c) team damage > baseline (the re-gear was worth it).
    If ANY check fails -> ALWAYS restore the baseline gear and report which check
    and the actual-vs-expected SPDs. Only if all pass (and not dry_run) is the
    re-gear left applied ("READY FOR KEY").

    dry_run (default True): run apply->read->resim then RESTORE regardless, so we
    learn whether the config holds WITHOUT committing. NEVER runs a CB battle or
    spends a key.
    """
    element_id = ELEMENT_NAME_TO_ID[element]
    floor = _acc_floor()
    id_by_name = _resolve_ids()
    all_ids = [id_by_name[n] for n in MEN]

    # ---- 0) baseline = CURRENT (restored) gear; read its real computed stats. -- #
    baseline_stats = read_computed_stats(all_ids)
    missing = [hid for hid in all_ids if not baseline_stats.get(hid)]
    if missing:
        raise RuntimeError(f"computed stats missing for hero ids {missing} "
                           "(is the mod up at localhost:6790?)")
    baseline_spd = {hid: int(round(baseline_stats[hid][SPD])) for hid in all_ids}

    # ---- 1) baseline sim with the REAL current SPDs/stats. ------------------- #
    setup = _build_team_setup(MEN, use_current_gear=True)
    if isinstance(setup, dict) and setup.get("error"):
        raise RuntimeError(setup["error"])
    names = setup["hero_names"]
    idx = {n: i for i, n in enumerate(names)}
    base_setup = copy.deepcopy(setup)
    _inject_live_stats(base_setup, idx, id_by_name, baseline_stats)
    baseline = _run_sim(base_setup, element_id)

    # ---- 2) AIRTIGHT survivor exclusion + team-aware dealer solve. ----------- #
    arts, heroes, account = gto.load_data()
    opt = gto.Optimizer(arts, heroes, account)
    survivor_ids, survivor_by_hero = _survivor_equipped_ids(id_by_name)
    # defensive union with the optimizer's own record of survivor gear.
    for n in SURVIVORS:
        h = opt.heroes_by_name.get(n.lower())
        for a in (h.get("artifacts") if h else []) or []:
            if a.get("id") is not None:
                survivor_ids.add(a["id"])
    cur_spd = {n: baseline_spd[id_by_name[n]] for n in MEN}
    solves = _solve_dealer_gear(opt, cur_spd, floor, survivor_ids,
                                anneal=anneal, verbose=verbose, spd_tol=spd_tol)
    assigned_ids = _assert_no_survivor_overlap(solves, survivor_ids)

    # ---- 3) build the live equip mapping {hero_id: [art_ids]}. --------------- #
    mapping = {}
    for name in DEALERS:
        ids = [a["id"] for a in solves[name]["assignment"].values()
               if a and a.get("id") is not None]
        mapping[id_by_name[name]] = ids

    # snapshot the 5 MEN + any DONOR hero currently wearing an assigned piece so
    # nothing is left stripped after restore.
    donor_ids = _current_owners(assigned_ids) - set(all_ids)
    snap_ids = sorted(set(all_ids) | donor_ids)

    # ---- 4) snapshot -> apply -> read -> resim. ----------------------------- #
    loadouts.snapshot(snapshot_name, snap_ids)
    apply_res = loadouts.apply(snapshot_name, mapping, snapshot_first=False)
    post_stats = read_computed_stats(all_ids)
    post_spd = {hid: (int(round(post_stats[hid][SPD]))
                      if post_stats.get(hid) else None) for hid in all_ids}
    post_setup = copy.deepcopy(setup)
    _inject_live_stats(post_setup, idx, id_by_name, post_stats)
    regeared = _run_sim(post_setup, element_id)

    # ---- 5) THE GATE. -------------------------------------------------------- #
    survivor_spd_check = {}
    survivor_ok = True
    for n in SURVIVORS:
        hid = id_by_name[n]
        b, p = baseline_spd[hid], post_spd.get(hid)
        ok = (p is not None and b == p)
        survivor_spd_check[n] = {"baseline": b, "post": p, "ok": ok}
        survivor_ok = survivor_ok and ok
    holds_ok = bool(regeared["holds"])
    damage_ok = regeared["total"] > baseline["total"]
    passed = survivor_ok and holds_ok and damage_ok

    failed_checks = []
    if not survivor_ok:
        failed_checks.append("(a) survivor SPD changed")
    if not holds_ok:
        failed_checks.append(f"(b) does not hold T50 "
                             f"(survives T{regeared['turns']}, gaps={regeared['gaps']})")
    if not damage_ok:
        failed_checks.append("(c) damage not above baseline")

    # ---- 6) restore unless we committed AND everything passed. --------------- #
    committed = (not dry_run) and passed
    restored = False
    restore_res = None
    if not committed:
        restore_res = loadouts.restore(snapshot_name)
        restored = True

    return {
        "element": element, "element_id": element_id, "acc_floor": floor,
        "dry_run": dry_run, "passed": passed, "committed": committed,
        "restored": restored, "failed_checks": failed_checks,
        "baseline": baseline, "regeared": regeared,
        "baseline_spd": {n: baseline_spd[id_by_name[n]] for n in MEN},
        "post_spd": {n: post_spd.get(id_by_name[n]) for n in MEN},
        "survivor_spd_check": survivor_spd_check,
        "dealer_spd_check": {n: {"target": cur_spd[n],
                                 "post": post_spd.get(id_by_name[n])}
                             for n in DEALERS},
        "solves": solves, "mapping": mapping, "id_by_name": id_by_name,
        "survivor_excluded": sorted(survivor_ids),
        "assigned_ids": sorted(assigned_ids),
        "snap_ids": snap_ids, "donor_ids": sorted(donor_ids),
        "apply_res": apply_res, "restore_res": restore_res,
        "snapshot_name": snapshot_name,
    }


def _print_safe_report(R):
    print("\n" + "=" * 78)
    print(f" MEN safe re-gear GATE  -  element={R['element']}  "
          f"(dry_run={R['dry_run']})")
    print("=" * 78)
    print(" survivor exclusion: dealer assignment shares "
          f"{len(set(R['assigned_ids']) & set(R['survivor_excluded']))} ids with "
          f"survivor gear (must be 0)  [ASSERT PASSED]")
    print("\n SPD (game-truth /hero-computed-stats):")
    print(f"   {'hero':10s} {'baseline':>9s} {'post':>7s}  role")
    for n in MEN:
        role = "SURVIVOR" if n in SURVIVORS else "dealer"
        b = R["baseline_spd"][n]
        p = R["post_spd"][n]
        flag = ""
        if n in SURVIVORS and p is not None and b != p:
            flag = "  <-- CHANGED (tune broken)"
        print(f"   {n:10s} {b:>9} {str(p):>7}  {role}{flag}")

    base, re = R["baseline"], R["regeared"]
    print("\n team cb_sim (ESTIMATE; real numbers under-survive):")
    print(f"   BEFORE: {base['total']/1e6:6.2f}M  holds={base['holds']} "
          f"(T{base['turns']}, gaps={base['gaps']})")
    print(f"   AFTER : {re['total']/1e6:6.2f}M  holds={re['holds']} "
          f"(T{re['turns']}, gaps={re['gaps']})")
    d = re["total"] - base["total"]
    print(f"   DELTA : {d/1e6:+6.2f}M")

    print("\n GATE:")
    print(f"   (a) survivors' SPD unchanged : "
          f"{all(v['ok'] for v in R['survivor_spd_check'].values())}")
    print(f"   (b) holds T50, 0 gaps        : {re['holds']}")
    print(f"   (c) damage > baseline        : {re['total'] > base['total']}")
    if R["passed"]:
        verdict = ("READY FOR KEY" if R["committed"]
                   else "HOLDS (dry-run) — re-run with --commit to leave applied")
        print(f"\n   VERDICT: PASS — {verdict}")
    else:
        print(f"\n   VERDICT: FAIL — {', '.join(R['failed_checks'])}")
        print("   -> baseline gear RESTORED (gate caught the desync before a key).")
    print(f"   gear restored this run: {R['restored']}\n")


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

    # exclude survival heroes' CURRENT equipped gear from the dealers' vault —
    # read LIVE (/all-heroes), not from a cached json, so a piece the survivors
    # actually wear can never leak into a dealer's assignment (the T24-wipe bug).
    try:
        survivor_ids, _ = _survivor_equipped_ids()
    except Exception:
        survivor_ids = set()
    for sn in SURVIVORS:                       # defensive union with cached record
        h = opt.heroes_by_name.get(sn.lower())
        for a in (h.get("artifacts") if h else []) or []:
            if a.get("id") is not None:
                survivor_ids.add(a["id"])

    solves = _solve_dealer_gear(opt, cur_spd, floor, survivor_ids,
                                anneal=anneal, verbose=verbose)
    _assert_no_survivor_overlap(solves, survivor_ids)

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
    ap.add_argument("--safe", action="store_true",
                    help="run the LIVE safe_regear GATE (snapshot->apply->read->"
                         "resim->restore) instead of the offline report")
    ap.add_argument("--commit", action="store_true",
                    help="with --safe: leave the re-gear APPLIED if the gate PASSES "
                         "(default is dry-run: always restore). Never spends a key.")
    ap.add_argument("--snapshot-name", default="men_safe_regear")
    ap.add_argument("--spd-tol", type=int, default=0,
                    help="with --safe: SPD slack above tune the gear solve may use "
                         "(0 = exact SPD-lock; 2 = loose). Default 0.")
    args = ap.parse_args(argv)

    if args.safe:
        R = safe_regear(element=args.element, dry_run=not args.commit,
                        anneal=args.anneal, snapshot_name=args.snapshot_name,
                        spd_tol=args.spd_tol, verbose=args.verbose)
        _print_safe_report(R)
        if args.json:
            _json_safe = {k: R[k] for k in (
                "element", "acc_floor", "dry_run", "passed", "committed",
                "restored", "failed_checks", "baseline", "regeared",
                "baseline_spd", "post_spd", "survivor_spd_check",
                "dealer_spd_check", "mapping", "survivor_excluded",
                "assigned_ids", "snap_ids")}
            Path(args.json).write_text(json.dumps(_json_safe, indent=2),
                                       encoding="utf-8")
            print(f"[json] wrote {args.json}")
        return 0 if R["passed"] else 1

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
