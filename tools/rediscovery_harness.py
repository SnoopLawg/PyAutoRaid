#!/usr/bin/env python3
"""M6 (CB-only proof-of-concept) — the "no-cheating" rediscovery test.

THESIS (docs/organic_team_milestones.md):
    DWJ's 103 CB tunes are *emergent* instances of one abstract structure:
        survival-currency + enabler + amplifier-channel + damage-engine
    If our ORGANIC generator (role-discovery from game-truth skill text +
    CB sim) independently produces comps whose ROLE SIGNATURE matches the
    known DWJ tunes the roster can field — WITHOUT ever being shown the
    scraped templates — then we are *reasoning*, not *replaying*.

WHAT THIS HARNESS DOES
    1. Builds `roles_by_hero` from game-truth alone using
       `cb_team_explorer.discover_roles` (skill descriptions → role tags via
       ROLE_KEYWORDS). No DWJ/HH input feeds role discovery.
    2. Abstracts every team into a ROLE SIGNATURE over four structural axes
       derived from the unifying model (NOT champion names).
    3. ANSWER KEY: loads the held-out DWJ tunes, fields each from the owned
       roster (`cb_team_explorer.fill_dwj_tune_with_owned`), and records the
       distinct role signatures the roster can actually field. These are the
       targets the generator must re-derive.
    4. GENERATOR: enumerates candidate comps with
       `cb_team_explorer.generate_candidate_teams` using ONLY the game-truth
       role tags (the DWJ tune list is NOT passed in). Computes their signatures.
    5. REDISCOVERY RATE: fraction of fieldable DWJ signatures that the
       generator's output independently reproduces.
    6. NOVELTY: generated signatures matching NO DWJ tune. With --sim, the top
       novel candidates are validated through the CB sim (cb_potential /
       cb_sim) and flagged by survival/damage. cb_sim is known to
       UNDER-survive (see memory), so sim output is labelled an ESTIMATE.

HONESTY NOTES
    - Role discovery, candidate generation, and signatures are computed from
      game-truth only. The DWJ tunes are used ONLY as the held-out answer key
      and to gate "fieldable from this roster".
    - If a stage can't run (thin roster, sim error), it is reported as such —
      no rediscovery rate is fabricated.

Usage:
    python tools/rediscovery_harness.py
    python tools/rediscovery_harness.py --cb-element magic --candidate-pool 8000
    python tools/rediscovery_harness.py --sim 12          # sim top novel candidates
    python tools/rediscovery_harness.py --include-unowned # full-universe roster
    python tools/rediscovery_harness.py --json out.json
"""
from __future__ import annotations

import os
import sys

# Reproducibility: cb_team_explorer iterates `set`s (roster / role fill /
# generic-slot substitution). Python randomizes string hashing per process,
# so set iteration order — and therefore which 8000 comps the generator caps
# to and which substitute fills a DWJ generic slot — varies run-to-run,
# making the rediscovery rate wobble (~81-93%). Pin the hash seed once so the
# CLI's reported rate is deterministic, re-exec'ing before any set-using
# import runs. Guarded to __main__ ONLY so an importer (pytest) is never
# os.execv'd out from under itself.
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

import cb_team_explorer as cte  # noqa: E402  (role discovery + generator)


# --------------------------------------------------------------------------
# Role-signature abstraction (the structural axes of the unifying model).
# A SIGNATURE describes a team by FUNCTION, never by champion name, so a
# generated comp can be "role-equivalent" to a DWJ tune without sharing heroes.
# --------------------------------------------------------------------------

# role-tag (from cb_team_explorer.ROLE_KEYWORDS) -> survival-currency category
SURVIVAL_MAP = {
    "uk": "unkillable",
    "bd": "block_damage",
    "shield": "shield",
    "ally_protect": "ally_protect",
    "revive": "revive_on_death",
}
# role-tags that act as the "enabler" (sustains the survival keystone)
ENABLER_TAGS = {"cd_reset"}
# amplifier channels: which damage channel a buff/debuff multiplies
AMP_HIT_TAGS = {"def_down", "weaken"}      # amplify hits + WM/GS + bring-it-down
AMP_POISON_TAGS = {"poison_sens"}          # amplify poison only
# engine channels: how a team actually deals damage
ENGINE_TAGS = {
    "dps": "hit",          # any direct-damage skill -> hit channel
    "poisoner": "poison",
    "burner": "hp_burn",
}


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
    """Reduce a 5-hero team to its abstract role signature (game-truth roles)."""
    flat: set[str] = set()
    for h in team:
        flat |= roles_by_hero.get(h, set())
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


# --------------------------------------------------------------------------
# Game-truth role discovery (mirrors cb_team_explorer.main wiring).
# --------------------------------------------------------------------------

def build_roles_and_roster(include_unowned: bool):
    """Return (roles_by_hero, eligible, owned, has_2me).

    roles_by_hero is built for EVERY catalog hero (so DWJ-tune fill can find
    substitutes); `eligible` is the roster the generator is allowed to use.
    """
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
# Main harness.
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cb-element", default="magic",
                    choices=("magic", "force", "spirit", "void"))
    ap.add_argument("--candidate-pool", type=int, default=8000,
                    help="Feasible comps the generator enumerates (default 8000)")
    ap.add_argument("--sim", type=int, default=0,
                    help="Validate the top-N NOVEL candidates through the CB "
                         "sim (default 0 = structural only). Each sim ~4s.")
    ap.add_argument("--include-unowned", action="store_true",
                    help="Let the generator use the full hero universe "
                         "(default: owned 6-star roster only).")
    ap.add_argument("--json", help="Also write the full result as JSON here.")
    args = ap.parse_args()

    elem_id = {"magic": 1, "force": 2, "spirit": 3, "void": 4}[args.cb_element]

    print("Building game-truth role tags (no DWJ/HH input)...", file=sys.stderr)
    roles_by_hero, eligible, owned, has_2me = build_roles_and_roster(args.include_unowned)
    print(f"  catalog heroes classified: {len(roles_by_hero)}", file=sys.stderr)
    print(f"  eligible roster for generator: {len(eligible)}", file=sys.stderr)

    # ---- ANSWER KEY: fieldable DWJ tune signatures --------------------------
    dwj_tunes = cte.load_dwj_tunes()
    fieldable: list[tuple[dict, list[str], RoleSignature]] = []
    for tune in dwj_tunes:
        filled = cte.fill_dwj_tune_with_owned(tune["slots"], set(eligible), roles_by_hero)
        if not filled:
            continue
        sig = team_signature(filled, roles_by_hero)
        fieldable.append((tune, sorted(filled), sig))

    if not dwj_tunes:
        print("ABORT: no DWJ tunes loaded (data/dwj/parsed/tunes.json missing). "
              "Cannot run rediscovery — nothing to rediscover.", file=sys.stderr)
        return 1
    if not fieldable:
        print(f"NOTE: {len(dwj_tunes)} DWJ tunes known, but ZERO are fieldable "
              f"from the {len(eligible)}-hero roster. Rediscovery rate is "
              f"undefined (no targets). Roster too thin / role-fill failed.",
              file=sys.stderr)
        return 1

    # distinct answer-key signatures
    dwj_sig_to_tunes: dict[RoleSignature, list[str]] = defaultdict(list)
    for tune, _team, sig in fieldable:
        dwj_sig_to_tunes[sig].append(tune.get("name") or tune.get("slug") or "?")
    dwj_sigs = set(dwj_sig_to_tunes)

    # ---- GENERATOR: comps from game-truth only (NO DWJ input) ---------------
    print("Generating candidate comps from game-truth roles "
          "(DWJ NOT supplied)...", file=sys.stderr)
    candidates = cte.generate_candidate_teams(
        eligible, roles_by_hero,
        max_combos=args.candidate_pool,
        has_double_maneater=has_2me,
    )
    print(f"  generator produced {len(candidates)} feasible comps", file=sys.stderr)
    if not candidates:
        print("ABORT: generator produced 0 feasible comps "
              "(need survivor + sustainer + 3 DPS in roster).", file=sys.stderr)
        return 1

    gen_sig_to_teams: dict[RoleSignature, list[list[str]]] = defaultdict(list)
    for team in candidates:
        gen_sig_to_teams[team_signature(team, roles_by_hero)].append(team)
    gen_sigs = set(gen_sig_to_teams)

    # ---- REDISCOVERY METRIC -------------------------------------------------
    matched = sorted(dwj_sigs & gen_sigs, key=lambda s: s.short())
    missed = sorted(dwj_sigs - gen_sigs, key=lambda s: s.short())
    rate = len(matched) / len(dwj_sigs)

    # per-tune view (a tune is rediscovered if its signature is generated)
    tunes_total = len(fieldable)
    tunes_redisc = sum(1 for _, _, sig in fieldable if sig in gen_sigs)

    # ---- NOVELTY: generated signatures matching no DWJ tune -----------------
    novel_sigs = sorted(gen_sigs - dwj_sigs, key=lambda s: s.short())

    # ---- OUTPUT -------------------------------------------------------------
    print("\n" + "=" * 78)
    print(f"  M6 CB REDISCOVERY HARNESS  (cb_element={args.cb_element}, "
          f"roster={'universe' if args.include_unowned else 'owned 6*'})")
    print("=" * 78)
    print(f"DWJ tunes known .............. {len(dwj_tunes)}")
    print(f"  fieldable from roster ...... {tunes_total}")
    print(f"  distinct role signatures ... {len(dwj_sigs)}  (the answer key)")
    print(f"Generated comps .............. {len(candidates)}")
    print(f"  distinct role signatures ... {len(gen_sigs)}")
    print()
    print(f">> REDISCOVERY RATE (distinct signatures): "
          f"{len(matched)}/{len(dwj_sigs)} = {rate*100:.0f}%")
    print(f">> Per-tune rediscovered (fieldable tunes whose signature the "
          f"generator re-derived): {tunes_redisc}/{tunes_total} "
          f"= {tunes_redisc/tunes_total*100:.0f}%")

    print("\n--- MATCHED signatures (re-derived from game-truth alone) ---")
    for sig in matched:
        ex = gen_sig_to_teams[sig][0]
        print(f"  [OK] {sig.short()}")
        print(f"        DWJ tunes: {', '.join(sorted(set(dwj_sig_to_tunes[sig]))[:6])}")
        print(f"        gen example: {', '.join(ex)}")

    if missed:
        print("\n--- MISSED signatures (fieldable DWJ but generator did NOT "
              "produce) ---")
        for sig in missed:
            print(f"  [--] {sig.short()}")
            print(f"        DWJ tunes: {', '.join(sorted(set(dwj_sig_to_tunes[sig]))[:6])}")
    else:
        print("\n--- MISSED signatures: none ---")

    # novelty: rank novel signatures by how many comps realize them
    print(f"\n--- NOVEL signatures (sim-valid candidates matching NO DWJ tune) ---")
    print(f"  {len(novel_sigs)} novel signatures across "
          f"{sum(len(gen_sig_to_teams[s]) for s in novel_sigs)} comps")
    novel_ranked = sorted(novel_sigs,
                          key=lambda s: -len(gen_sig_to_teams[s]))

    sim_results = []
    if args.sim > 0 and novel_ranked:
        print(f"\n  Validating top novel candidates through CB sim "
              f"(ESTIMATE; cb_sim under-survives) ...", file=sys.stderr)
        from cb_potential import simulate_team as _sim
        # one representative comp per novel signature (the best by predict_score)
        reps: list[tuple[RoleSignature, list[str]]] = []
        for sig in novel_ranked:
            best = max(gen_sig_to_teams[sig],
                       key=lambda t: cte.predict_score(t, roles_by_hero))
            reps.append((sig, best))
        for sig, team in reps[:args.sim]:
            try:
                r = _sim(team, cb_element=elem_id)
                total = float(r.get("total", 0) or 0)
                turns = int(r.get("cb_turns", 0) or 0)
                valid = bool(r.get("valid"))
            except Exception as ex:
                total, turns, valid = 0.0, 0, False
                print(f"    sim error on {team}: {ex}", file=sys.stderr)
            sim_results.append({"sig": sig.short(), "team": team,
                                "total": total, "cb_turns": turns,
                                "valid": valid})
        sim_results.sort(key=lambda d: (-d["cb_turns"], -d["total"]))
        print(f"\n  {'turns':>5} {'damage(M)':>10} {'valid':>6}  team  (signature)")
        print("  " + "-" * 90)
        for d in sim_results:
            print(f"  {d['cb_turns']:>5} {d['total']/1e6:>10.1f} "
                  f"{str(d['valid']):>6}  {', '.join(d['team'])}")
            print(f"        {d['sig']}")
        survivors = [d for d in sim_results if d["cb_turns"] >= 50 or d["valid"]]
        print(f"\n  sim-validated (held to T50): {len(survivors)}/"
              f"{len(sim_results)}  (cb_sim ESTIMATE -- under-survives; "
              f"non-survivors ranked by turns then damage)")
    else:
        # structural-only: list the top novel signatures
        for sig in novel_ranked[:12]:
            ex = gen_sig_to_teams[sig][0]
            print(f"  [NOVEL] {sig.short()}  "
                  f"({len(gen_sig_to_teams[sig])} comps) e.g. {', '.join(ex)}")
        if not args.sim:
            print("  (run with --sim N to CB-sim-validate the top novel "
                  "candidates; structural-only above)")

    if args.json:
        out = {
            "cb_element": args.cb_element,
            "include_unowned": args.include_unowned,
            "dwj_tunes_known": len(dwj_tunes),
            "dwj_fieldable_tunes": tunes_total,
            "dwj_distinct_signatures": len(dwj_sigs),
            "generated_comps": len(candidates),
            "generated_distinct_signatures": len(gen_sigs),
            "rediscovery_rate_signatures": rate,
            "rediscovered_signatures": len(matched),
            "per_tune_rediscovered": tunes_redisc,
            "per_tune_total": tunes_total,
            "matched": [{"sig": s.short(),
                         "dwj_tunes": sorted(set(dwj_sig_to_tunes[s])),
                         "gen_example": gen_sig_to_teams[s][0]} for s in matched],
            "missed": [{"sig": s.short(),
                        "dwj_tunes": sorted(set(dwj_sig_to_tunes[s]))} for s in missed],
            "novel_signatures": [{"sig": s.short(),
                                  "n_comps": len(gen_sig_to_teams[s]),
                                  "example": gen_sig_to_teams[s][0]}
                                 for s in novel_ranked],
            "sim_validated": sim_results,
        }
        Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
