#!/usr/bin/env python3
"""M6 (full) — the multi-location "no-cheating" rediscovery / coverage harness.

THESIS (docs/organic_team_milestones.md):
    The known meta comps are *emergent* instances of one abstract structure:
        survival-currency + enabler + amplifier-channel + damage-engine
    If our GENERATIVE engine (game-truth role tags + M2 resolve + M3 boss
    feasibility + M5 fitness) independently produces comps whose ROLE SIGNATURE
    matches the known answer-key comps the roster can field — WITHOUT being shown
    the scraped templates — then we are *reasoning*, not *replaying*.

WHAT CHANGED vs the CB-only proof-of-concept
    The old harness drove ``cb_team_explorer.generate_candidate_teams`` — a broad
    CB enumerator that HARDCODES a UK-or-BD survival requirement, so it could
    never emit a shield-only stall (it missed 2 of 19 CB signatures, 89%).  This
    harness re-points the generator at the committed GENERATIVE pipeline:

        team_generator.generate(location, roster, GenOpts) -> [CandidateComp]

    which is location-agnostic and uses per-location M3 feasibility
    (``boss_constraints``) instead of a UK/BD hardcode — so a shield-only comp is
    valid wherever the boss allows it.  Cited engine functions:
      - team_generator.generate / GenOpts / CandidateComp   (M2+M3+M5 pipeline)
      - team_generator.build_named_skeletons                (channel skeletons)
      - boss_constraints.{faction_lock,acc_floor,is_effect_useful}  (M3 filters)
      - fitness.score (heuristic | cb_sim) via team_generator (M5 fitness)
      - cb_team_explorer.{discover_roles,load_dwj_tunes,
        fill_dwj_tune_with_owned,predict_score}  (game-truth role tags + the
        held-out CB answer key — NEVER fed into generation)

TWO MODES (selected by --location)
  CB  (clan_boss / cb): REDISCOVERY against the held-out DWJ tune answer key.
      Reports the distinct-signature rediscovery rate and classifies every miss.
  non-CB (dragon / fire_knight / ...): there is no DWJ answer key, so we use a
      held-out COMMUNITY reference — the HellHades per-location tier list
      (data/hh/parsed/tierlist.json).  Reports a COVERAGE figure: of the
      high-tier champions the OWNED roster can field for that location, how many
      does the generator's top-K actually surface?  (Limits: HH rates individual
      heroes, not team structures, and is a community signal — not game-truth.)

HONESTY NOTES
    - Role discovery, generation and signatures are computed from game-truth
      only.  DWJ tunes (CB) / HH ratings (non-CB) are used ONLY as held-out
      references, never as generation input.
    - The generative engine is a constraint-satisfaction generator, NOT a broad
      enumerator: it deliberately PRUNES sub-viable comps.  Its hit/wm_gs
      ``channel_consistent`` rule requires a hit amplifier (Dec-DEF/Weaken), so
      amp-less pure-hit WM/GS stall tunes are *structurally* excluded — those
      misses are reported as such, not hidden.
    - cb_sim is known to UNDER-survive (see memory), so any CB-sim novelty label
      is an ESTIMATE.  Off-CB there is no outcome simulator; novelty there is
      validated by the M5 *heuristic* fitness only, and labelled accordingly.

Usage:
    python tools/rediscovery_harness.py                       # CB rediscovery
    python tools/rediscovery_harness.py --location dragon     # non-CB coverage
    python tools/rediscovery_harness.py --sim 10              # CB-sim top novel
    python tools/rediscovery_harness.py --json out.json
"""
from __future__ import annotations

import os
import sys

# Reproducibility: the generative engine and the DWJ answer-key fill both iterate
# `set`/`dict` structures whose order depends on Python's per-process string-hash
# randomization, which makes the reported rate wobble run-to-run. Pin the hash
# seed once so the CLI's rate is deterministic, re-exec'ing before any import
# runs. Guarded to __main__ ONLY so an importer (pytest) is never os.execv'd.
if __name__ == "__main__" and os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable] + sys.argv)

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import cb_team_explorer as cte    # noqa: E402  (role discovery + CB answer key)
import team_generator as tg       # noqa: E402  (the generative engine)


# --------------------------------------------------------------------------
# Role-signature abstraction (the structural axes of the unifying model).
# A SIGNATURE describes a team by FUNCTION, never by champion name, so a
# generated comp can be "role-equivalent" to a reference comp without sharing
# heroes. This abstraction is location-agnostic and unchanged from the POC.
# --------------------------------------------------------------------------

# role-tag (from cb_team_explorer.ROLE_KEYWORDS) -> survival-currency category
SURVIVAL_MAP = {
    "uk": "unkillable",
    "bd": "block_damage",
    "shield": "shield",
    "ally_protect": "ally_protect",
    "revive": "revive_on_death",
}
ENABLER_TAGS = {"cd_reset"}                  # the "enabler" (sustains keystone)
AMP_HIT_TAGS = {"def_down", "weaken"}        # amplify hits + WM/GS
AMP_POISON_TAGS = {"poison_sens"}            # amplify poison only
ENGINE_TAGS = {                              # how a team deals damage
    "dps": "hit",
    "poisoner": "poison",
    "burner": "hp_burn",
}


def _base_name(name: str) -> str:
    """Strip a duplicate-instance suffix ('<hero>_2' -> '<hero>').

    team_generator emits Name_2 instances for owned duplicates; the role table
    is keyed by base name. A non-numeric tail (e.g. 'UK_A' in a unit test) is
    left untouched.
    """
    if "_" in name:
        head, _, tail = name.rpartition("_")
        if tail.isdigit() and head:
            return head
    return name


@dataclass(frozen=True)
class RoleSignature:
    """Abstract structural fingerprint of a team (hashable / comparable)."""
    survival: frozenset      # ⊆ {unkillable, block_damage, shield, ...}
    enabler: bool            # has a cooldown-reduction / keystone enabler
    amp: frozenset           # ⊆ {hit, poison}
    engine: frozenset        # ⊆ {hit, poison, hp_burn}

    def short(self) -> str:
        surv = "+".join(sorted(self.survival)) or "none"
        amp = "+".join(sorted(self.amp)) or "none"
        eng = "+".join(sorted(self.engine)) or "none"
        return f"surv[{surv}] enab[{int(self.enabler)}] amp[{amp}] eng[{eng}]"


def team_signature(team: list[str],
                   roles_by_hero: dict[str, set[str]]) -> RoleSignature:
    """Reduce a 5-hero team to its abstract role signature (game-truth roles).

    Tolerant of duplicate-instance suffixes (Name_2 -> Name)."""
    flat: set[str] = set()
    for h in team:
        roles = roles_by_hero.get(h)
        if roles is None:
            roles = roles_by_hero.get(_base_name(h), set())
        flat |= roles
    survival = frozenset(SURVIVAL_MAP[t] for t in flat if t in SURVIVAL_MAP)
    enabler = bool(flat & ENABLER_TAGS)
    amp = set()
    if flat & AMP_HIT_TAGS:
        amp.add("hit")
    if flat & AMP_POISON_TAGS:
        amp.add("poison")
    engine = frozenset(ENGINE_TAGS[t] for t in flat if t in ENGINE_TAGS)
    return RoleSignature(survival=survival, enabler=enabler,
                         amp=frozenset(amp), engine=engine)


def generatable_by_engine(sig: RoleSignature) -> bool:
    """Whether team_generator's feasibility model CAN, in principle, emit a comp
    with this signature.

    The engine's `channel_consistent` hard rule requires a hit amplifier
    (Dec-DEF/Weaken) for the hit & wm_gs channels, and a poison amplifier for
    the poison channel; only the hp_burn channel needs no amplifier. So a comp
    with NO amplifier is generatable iff it carries an hp_burn engine. A comp
    WITH an amplifier (hit or poison) always has a channel it can be routed
    through. (This is a structural property of the engine, not of the roster.)
    """
    if sig.amp:
        return True
    return "hp_burn" in sig.engine


# --------------------------------------------------------------------------
# Game-truth role discovery (mirrors cb_team_explorer.main wiring). Used ONLY
# to compute role SIGNATURES (the metric) and the CB answer-key fill — never to
# drive generation (team_generator reasons over its own M1 records).
# --------------------------------------------------------------------------

def build_roles_and_roster(include_unowned: bool):
    """Return (roles_by_hero, eligible, owned, has_2me).

    roles_by_hero is built for EVERY catalog hero; `eligible` is the owned 6★
    roster (the universe the generator + answer key field from)."""
    ah = json.loads((PROJECT_ROOT / "all_heroes.json").read_text(encoding="utf-8"))
    hs6 = json.loads((PROJECT_ROOT / "heroes_6star.json").read_text(encoding="utf-8"))
    owned = {h["name"] for h in hs6.get("heroes", []) if h.get("name")}

    ht = json.loads((PROJECT_ROOT / "data" / "static" / "hero_types.json")
                    .read_text(encoding="utf-8"))["hero_types"]
    ht_by_name: dict[str, dict] = {}
    for h in ht:
        n = h.get("name")
        if not n:
            continue
        cur = ht_by_name.get(n)
        if cur is None or (h.get("is_max_ascended") and not cur.get("is_max_ascended")):
            ht_by_name[n] = h

    sa = json.loads((PROJECT_ROOT / "data" / "static" / "skills_all.json")
                    .read_text(encoding="utf-8"))["data"]
    sk_idx = {s["Id"]: s for s in sa if "Id" in s}

    sd_path = PROJECT_ROOT / "data" / "static" / "skill_descriptions_all.json"
    sd_text: dict = {}
    if sd_path.exists():
        blob = json.loads(sd_path.read_text(encoding="utf-8"))
        sd_text = blob.get("skill_descriptions") or blob.get("data") or {}

    roles_by_hero = {
        name: cte.discover_roles(name, entry, sk_idx, sd_text)
        for name, entry in ht_by_name.items()
    }
    eligible = sorted(owned if not include_unowned else set(ht_by_name.keys()))
    has_2me = len([h for h in ah["heroes"] if h.get("name") == "Maneater"]) >= 2
    return roles_by_hero, eligible, owned, has_2me


# --------------------------------------------------------------------------
# Generative engine driver (the swap: team_generator instead of
# cb_team_explorer.generate_candidate_teams).
# --------------------------------------------------------------------------

def _gen_opts(args, elem_id: int, location: str) -> "tg.GenOpts":
    """Bounded GenOpts. We rank with the HEURISTIC (NOT cb_sim) here: the
    rediscovery/coverage metric is STRUCTURAL (does the generator's feasible set
    span the reference signatures?), so spending ~0.3-4s/comp on cb_sim ranking
    buys nothing — and would make a full sweep intractable. `top` is set to the
    whole feasible set so we measure ALL comps the engine deems valid, not just
    the fitness top-30. (cb_sim is still used, opt-in, for --sim novelty.)"""
    return tg.GenOpts(
        pool="owned",
        top=args.max_candidates,            # return the whole feasible set
        max_candidates=args.max_candidates,
        rank_with="heuristic",              # structural metric -> no cb_sim rank
        cb_element=elem_id,
        bucket_cap=args.bucket_cap,
        cores_per_anchor=args.cores,
    )


def generate_comps(location: str, args, elem_id: int):
    """Run the generative engine; return its _Result (list[CandidateComp] +
    .report). roster=None lets team_generator load its own owned roster
    (including Name_2 duplicate instances)."""
    opts = _gen_opts(args, elem_id, location)
    return tg.generate(location, None, opts)


# ==========================================================================
# MODE 1 — CB rediscovery vs the held-out DWJ tune answer key.
# ==========================================================================

def run_cb(args, elem_id: int) -> dict:
    print("Building game-truth role tags (no DWJ/HH input)...", file=sys.stderr)
    roles_by_hero, eligible, owned, has_2me = build_roles_and_roster(False)
    print(f"  catalog heroes classified: {len(roles_by_hero)}", file=sys.stderr)
    print(f"  eligible owned roster: {len(eligible)}", file=sys.stderr)

    # ---- ANSWER KEY: fieldable DWJ tune signatures (held out) ---------------
    dwj_tunes = cte.load_dwj_tunes()
    if not dwj_tunes:
        print("ABORT: no DWJ tunes loaded (data/dwj/parsed/tunes.json missing).",
              file=sys.stderr)
        return {"error": "no DWJ answer key"}

    fieldable: list[tuple[dict, RoleSignature]] = []
    for tune in dwj_tunes:
        filled = cte.fill_dwj_tune_with_owned(tune["slots"], set(eligible),
                                              roles_by_hero)
        if filled:
            fieldable.append((tune, team_signature(sorted(filled), roles_by_hero)))
    if not fieldable:
        print("NOTE: zero DWJ tunes fieldable from roster — rate undefined.",
              file=sys.stderr)
        return {"error": "no fieldable DWJ tune"}

    dwj_sig_to_tunes: dict[RoleSignature, list[str]] = defaultdict(list)
    for tune, sig in fieldable:
        dwj_sig_to_tunes[sig].append(tune.get("name") or tune.get("slug") or "?")
    dwj_sigs = set(dwj_sig_to_tunes)

    # ---- GENERATOR: comps from game-truth only (DWJ NOT supplied) -----------
    print("Generating candidate comps with team_generator (M2+M3+M5; DWJ NOT "
          "supplied)...", file=sys.stderr)
    res = generate_comps("clan_boss", args, elem_id)
    if not res:
        print("ABORT: generator produced 0 feasible comps.", file=sys.stderr)
        return {"error": "generator produced nothing", "report": res.report}
    print(f"  generator produced {len(res)} feasible comps "
          f"(skeletons={res.report.get('skeletons_run')})", file=sys.stderr)

    gen_sig_to_teams: dict[RoleSignature, list[list[str]]] = defaultdict(list)
    for c in res:
        gen_sig_to_teams[team_signature(c.team, roles_by_hero)].append(c.team)
    gen_sigs = set(gen_sig_to_teams)

    # ---- REDISCOVERY METRIC -------------------------------------------------
    matched = sorted(dwj_sigs & gen_sigs, key=lambda s: s.short())
    missed = sorted(dwj_sigs - gen_sigs, key=lambda s: s.short())
    rate = len(matched) / len(dwj_sigs)

    # classify misses: structurally-impossible (engine can never emit this
    # signature) vs under-produced (engine could, but didn't within budget).
    impossible = [s for s in missed if not generatable_by_engine(s)]
    underproduced = [s for s in missed if generatable_by_engine(s)]
    # ceiling = the rate achievable if every generatable signature were emitted
    ceiling = (len(dwj_sigs) - len(impossible)) / len(dwj_sigs)

    tunes_total = len(fieldable)
    tunes_redisc = sum(1 for _t, sig in fieldable if sig in gen_sigs)

    # ---- the 2 shield-only signatures the POC structurally MISSED -----------
    shield_only = sorted((s for s in dwj_sigs if s.survival == frozenset({"shield"})),
                         key=lambda s: s.short())
    shield_status = [{"sig": s.short(),
                      "rediscovered": s in gen_sigs,
                      "dwj_tunes": sorted(set(dwj_sig_to_tunes[s]))[:6]}
                     for s in shield_only]

    novel_sigs = sorted(gen_sigs - dwj_sigs, key=lambda s: s.short())
    novel_ranked = sorted(novel_sigs, key=lambda s: -len(gen_sig_to_teams[s]))

    # ---- OUTPUT -------------------------------------------------------------
    print("\n" + "=" * 78)
    print(f"  M6 CB REDISCOVERY  (engine=team_generator, cb_element={args.cb_element})")
    print("=" * 78)
    print(f"DWJ tunes known .............. {len(dwj_tunes)}")
    print(f"  fieldable from roster ...... {tunes_total}")
    print(f"  distinct role signatures ... {len(dwj_sigs)}  (the answer key)")
    print(f"Generated comps .............. {len(res)}")
    print(f"  distinct role signatures ... {len(gen_sigs)}")
    print()
    print(f">> REDISCOVERY RATE (distinct signatures): "
          f"{len(matched)}/{len(dwj_sigs)} = {rate*100:.0f}%")
    print(f">> Per-tune rediscovered: {tunes_redisc}/{tunes_total} "
          f"= {tunes_redisc/tunes_total*100:.0f}%")
    print(f">> Engine ceiling (excl. {len(impossible)} signatures the engine's "
          f"channel rule structurally forbids): {ceiling*100:.0f}%")

    print("\n--- SHIELD-ONLY signatures (the 2 the UK/BD-hardcoded POC MISSED) ---")
    for st in shield_status:
        flag = "FIXED (rediscovered)" if st["rediscovered"] else "still missed"
        print(f"  [{'OK' if st['rediscovered'] else '--'}] {st['sig']}  -> {flag}")
        print(f"        DWJ tunes: {', '.join(st['dwj_tunes'])}")

    if impossible:
        print("\n--- MISSED: structurally excluded by the engine ---")
        print("    (amp-less pure-hit/WM-GS stalls; the channel_consistent rule "
              "requires a hit amplifier, so these are out of the engine's "
              "feasible set BY DESIGN, not a search failure)")
        for s in impossible:
            print(f"  [xx] {s.short()}  -> {', '.join(sorted(set(dwj_sig_to_tunes[s]))[:5])}")
    if underproduced:
        print("\n--- MISSED: generatable but under-produced (budget / single "
              "survival-slot depth) ---")
        for s in underproduced:
            print(f"  [--] {s.short()}  -> {', '.join(sorted(set(dwj_sig_to_tunes[s]))[:5])}")
    if not missed:
        print("\n--- MISSED signatures: none ---")

    print(f"\n--- NOVEL signatures (generated, matching NO DWJ tune) ---")
    print(f"  {len(novel_sigs)} novel signatures across "
          f"{sum(len(gen_sig_to_teams[s]) for s in novel_sigs)} comps")

    sim_results = _maybe_sim_novel(args, elem_id, novel_ranked, gen_sig_to_teams,
                                   roles_by_hero)
    if not sim_results:
        for sig in novel_ranked[:12]:
            ex = gen_sig_to_teams[sig][0]
            print(f"  [NOVEL] {sig.short()}  ({len(gen_sig_to_teams[sig])} comps) "
                  f"e.g. {', '.join(ex)}")
        if not args.sim:
            print("  (run with --sim N to CB-sim-validate the top novel comps; "
                  "structural-only above)")

    return {
        "mode": "cb_rediscovery",
        "cb_element": args.cb_element,
        "dwj_tunes_known": len(dwj_tunes),
        "dwj_fieldable_tunes": tunes_total,
        "dwj_distinct_signatures": len(dwj_sigs),
        "generated_comps": len(res),
        "generated_distinct_signatures": len(gen_sigs),
        "rediscovery_rate_signatures": rate,
        "rediscovered_signatures": len(matched),
        "engine_ceiling": ceiling,
        "per_tune_rediscovered": tunes_redisc,
        "per_tune_total": tunes_total,
        "shield_only_status": shield_status,
        "matched": [{"sig": s.short(),
                     "dwj_tunes": sorted(set(dwj_sig_to_tunes[s])),
                     "gen_example": gen_sig_to_teams[s][0]} for s in matched],
        "missed_structural": [{"sig": s.short(),
                               "dwj_tunes": sorted(set(dwj_sig_to_tunes[s]))}
                              for s in impossible],
        "missed_underproduced": [{"sig": s.short(),
                                  "dwj_tunes": sorted(set(dwj_sig_to_tunes[s]))}
                                 for s in underproduced],
        "novel_signatures": [{"sig": s.short(),
                              "n_comps": len(gen_sig_to_teams[s]),
                              "example": gen_sig_to_teams[s][0]}
                             for s in novel_ranked],
        "sim_validated": sim_results,
        "engine_report": res.report,
    }


def _maybe_sim_novel(args, elem_id, novel_ranked, gen_sig_to_teams,
                     roles_by_hero) -> list:
    """Validate the top novel signatures' best representative through the CB sim
    (ESTIMATE — cb_sim under-survives, see memory)."""
    if args.sim <= 0 or not novel_ranked:
        return []
    print(f"\n  Validating top novel candidates through CB sim "
          f"(ESTIMATE; cb_sim under-survives) ...", file=sys.stderr)
    from cb_potential import simulate_team as _sim
    reps = []
    for sig in novel_ranked:
        best = max(gen_sig_to_teams[sig],
                   key=lambda t: cte.predict_score([_base_name(n) for n in t],
                                                   roles_by_hero))
        reps.append((sig, best))
    out = []
    for sig, team in reps[:args.sim]:
        try:
            r = _sim([_base_name(n) for n in team], cb_element=elem_id)
            total = float(r.get("total", 0) or 0)
            turns = int(r.get("cb_turns", 0) or 0)
            valid = bool(r.get("valid"))
        except Exception as ex:
            total, turns, valid = 0.0, 0, False
            print(f"    sim error on {team}: {ex}", file=sys.stderr)
        out.append({"sig": sig.short(), "team": team, "total": total,
                    "cb_turns": turns, "valid": valid})
    out.sort(key=lambda d: (-d["cb_turns"], -d["total"]))
    print(f"\n  {'turns':>5} {'dmg(M)':>9} {'valid':>6}  team  (signature)")
    print("  " + "-" * 88)
    for d in out:
        print(f"  {d['cb_turns']:>5} {d['total']/1e6:>9.1f} {str(d['valid']):>6}  "
              f"{', '.join(d['team'])}")
        print(f"        {d['sig']}")
    survivors = [d for d in out if d["cb_turns"] >= 50 or d["valid"]]
    print(f"\n  sim-validated (held to T50): {len(survivors)}/{len(out)}  "
          f"(cb_sim ESTIMATE -- under-survives; non-survivors ranked by turns)")
    return out


# ==========================================================================
# MODE 2 — non-CB coverage vs the held-out HellHades tier list.
# ==========================================================================

# canonical location -> HH tierlist column (only locations HH actually rates).
HH_COLUMN = {
    "dragon": "dragon", "fire_knight": "fire_knight", "ice_golem": "ice_golem",
    "spider": "spider", "hydra": "hydra", "chimera": "chimera",
}


def run_noncb(args, location: str, elem_id: int) -> dict:
    canon = tg._is_cb  # noqa: F841 (kept for symmetry/readability)
    hh_col = HH_COLUMN.get(_norm_loc(location))
    if hh_col is None:
        print(f"NOTE: no HellHades tier column for '{location}'. Known non-CB "
              f"references: {', '.join(sorted(HH_COLUMN))}.", file=sys.stderr)

    roles_by_hero, eligible, owned, _has2 = build_roles_and_roster(False)

    # ---- HELD-OUT REFERENCE: HH high-tier owned heroes for this location ----
    top_tier, rated_n = [], 0
    if hh_col:
        hh = json.loads((PROJECT_ROOT / "data" / "hh" / "parsed" /
                         "tierlist.json").read_text(encoding="utf-8"))
        owned_set = set(owned)
        rated = [(r["name"], r.get(hh_col)) for r in hh
                 if isinstance(r.get(hh_col), (int, float)) and r["name"] in owned_set]
        rated.sort(key=lambda x: -x[1])
        rated_n = len(rated)
        top_tier = [n for n, v in rated if v >= args.hh_threshold]
        # fallback: if the >=threshold band is thin, take the top decile.
        if len(top_tier) < 8 and rated:
            top_tier = [n for n, _ in rated[:max(8, len(rated)//10)]]

    # ---- GENERATOR -----------------------------------------------------------
    print(f"Generating candidate comps with team_generator for '{location}' "
          f"(HH NOT supplied)...", file=sys.stderr)
    res = generate_comps(location, args, elem_id)
    if not res:
        print("ABORT: generator produced 0 feasible comps for this location.",
              file=sys.stderr)
        return {"error": "generator produced nothing", "report": res.report}

    topk = list(res)[:args.top]                 # res is fitness-sorted
    used: set[str] = set()
    for c in topk:
        used.update(_base_name(n) for n in c.team)
    dropped = {d["hero"] for d in res.report.get("dropped_heroes", [])}

    covered = [n for n in top_tier if n in used]
    missing = [n for n in top_tier if n not in used]
    coverage = (len(covered) / len(top_tier)) if top_tier else None

    print("\n" + "=" * 78)
    print(f"  M6 NON-CB COVERAGE  (location={location}, "
          f"reference=HellHades '{hh_col}' tier list)")
    print("=" * 78)
    print(f"owned roster ................. {len(owned)}")
    print(f"  HH-rated for {hh_col} ....... {rated_n}")
    print(f"  high-tier (>= {args.hh_threshold}) owned ... {len(top_tier)}  "
          f"(the held-out 'expected core')")
    print(f"generated comps .............. {len(res)}  "
          f"(top-{args.top} examined; skeletons={res.report.get('skeletons_run')})")
    if coverage is None:
        print("\n  No HH reference available -> no coverage figure.")
    else:
        print()
        print(f">> COVERAGE: generator top-{args.top} fields "
              f"{len(covered)}/{len(top_tier)} = {coverage*100:.0f}% of the "
              f"high-tier owned champions HH flags for {hh_col}")
        if missing:
            print("\n--- high-tier HH champions NOT surfaced in top-K ---")
            for n in missing:
                why = ("dropped by M3 (boss no-ops its value)" if n in dropped
                       else "below the top-K fitness cut / no skeleton slot fit")
                print(f"  [--] {n}: {why}")
        print("\n  LIMITS: HH rates INDIVIDUAL champions, not team structures; a "
              "tanky/utility pick can be HH-strong yet not fill any amplifier/"
              "engine slot. HH is a community signal, NOT game-truth.")

    # ---- NOVELTY (off-CB: heuristic only) -----------------------------------
    # Comps the generator ranks highly that DON'T lean on the community core
    # (<=1 HH-top hero) — surfaced as novel, validated by M5 heuristic fitness
    # (there is no off-CB outcome simulator, so this is a heuristic label).
    top_set = set(top_tier)
    novel = [c for c in topk
             if sum(1 for n in c.team if _base_name(n) in top_set) <= 1]
    novel.sort(key=lambda c: -c.fitness)
    print(f"\n--- NOVEL comps (<=1 HH-top hero; M5 HEURISTIC fitness, no outcome "
          f"sim off-CB) ---")
    for c in novel[:8]:
        print(f"  [NOVEL] fit={c.fitness:.2f} {c.skeleton}  {', '.join(c.team)}")
    if not novel:
        print("  (none — every top-K comp leans on >=2 HH-top champions)")

    return {
        "mode": "noncb_coverage",
        "location": location,
        "hh_column": hh_col,
        "owned": len(owned),
        "hh_rated": rated_n,
        "high_tier_threshold": args.hh_threshold,
        "high_tier_owned": top_tier,
        "generated_comps": len(res),
        "top_k_examined": args.top,
        "coverage": coverage,
        "covered": covered,
        "missing_high_tier": [
            {"hero": n, "dropped_by_m3": n in dropped} for n in missing],
        "novel_comps": [{"team": c.team, "skeleton": c.skeleton,
                         "fitness": c.fitness, "fitness_kind": c.fitness_kind}
                        for c in novel[:8]],
        "engine_report": res.report,
    }


def _norm_loc(location: str) -> str:
    return str(location).strip().lower().replace("-", "_").replace(" ", "_")


# ==========================================================================
# CLI
# ==========================================================================

_CB_KEYS = {"clan_boss", "cb", "clanboss", "demon_lord", "demon_lord_unm"}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--location", default="clan_boss",
                    help="boss_constraints location key/alias (default clan_boss "
                         "-> CB rediscovery; e.g. dragon -> non-CB coverage).")
    ap.add_argument("--cb-element", default="magic",
                    choices=("magic", "force", "spirit", "void"))
    ap.add_argument("--sim", type=int, default=0,
                    help="CB only: validate the top-N NOVEL signatures through "
                         "the CB sim (ESTIMATE; cb_sim under-survives).")
    ap.add_argument("--top", type=int, default=200,
                    help="non-CB: top-K generated comps examined for coverage "
                         "(default 200).")
    ap.add_argument("--hh-threshold", type=float, default=4.5,
                    help="non-CB: HellHades rating floor for 'high-tier' "
                         "(default 4.5 on the 0.5-5 scale).")
    ap.add_argument("--bucket-cap", type=int, default=24,
                    help="generator per-slot bucket cap (breadth/runtime knob; "
                         "default 24, ~30s for CB; the CB rate plateaus here).")
    ap.add_argument("--cores", type=int, default=30,
                    help="generator cores kept per anchor (default 30).")
    ap.add_argument("--max-candidates", type=int, default=60000,
                    help="cap on the feasible comps enumerated (default 60000).")
    ap.add_argument("--json", help="also write the full result as JSON here.")
    args = ap.parse_args()

    elem_id = {"magic": 1, "force": 2, "spirit": 3, "void": 4}[args.cb_element]

    if _norm_loc(args.location) in _CB_KEYS:
        result = run_cb(args, elem_id)
    else:
        result = run_noncb(args, args.location, elem_id)

    if args.json and "error" not in result:
        Path(args.json).write_text(json.dumps(result, indent=2, default=str),
                                   encoding="utf-8")
        print(f"\nwrote {args.json}", file=sys.stderr)

    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
