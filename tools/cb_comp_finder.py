"""Survival-first comp finder — M7 Phase B1 (coverage-chain enumerator).

Takes the game-truth synergy graph (`data/m5_synergy.jsonl`) + the owned roster
and enumerates candidate team comps that CAN form a survive-to-T50 pattern,
grouped by archetype:

  - uk       Unkillable chain (keep [Unkillable] up; [Block Debuffs] stops stun)
  - bd       Block-Damage wall (block the boss hit outright)
  - counter  Counterattack wall (+ sustain)
  - protect  Ally-Protect wall (protector soaks; + sustain)
  - heal     Heal-tank (Continuous Heal + Shield/Inc-DEF + bulk)
  - revive   Revive-on-death last resort

This is the *generation* half of the finder. It deliberately does NOT claim a
comp survives — that's M7 Gate B (validation through the HARDENED survival sim),
which is blocked on Gate A (survival-model calibration vs a real fixture
battery). Every comp here is a CANDIDATE: "has the providers to *attempt* the
pattern." Use `--validate` to run each through cb_sim survival (clearly marked
UNVALIDATED until Gate A — the sim currently over-predicts survival).

Mission-compliant: scoring uses game-truth synergy/provider coverage only.
**No HellHades / DeadwoodJedi inputs** in the path (unlike `cb_team_explorer`).

CLI:
    python3 tools/cb_comp_finder.py                       # providers + candidates, all archetypes
    python3 tools/cb_comp_finder.py --archetype uk --top 10
    python3 tools/cb_comp_finder.py --archetype counter --validate --element force
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

SYNERGY = PROJECT_ROOT / "data" / "m5_synergy.jsonl"
HEROES = PROJECT_ROOT / "heroes_all.json"

# archetype -> (required provider tags [any-of per group], label, needs-sustain)
ARCHETYPES = {
    "uk":      (["team_buff:Unkillable"], "Unkillable chain", True),
    "bd":      (["team_buff:Block Damage"], "Block-Damage wall", True),
    "counter": (["team_buff:Counterattack"], "Counterattack wall", True),
    "protect": (["team_buff:Ally Protection"], "Ally-Protect wall", True),
    "heal":    (["team_buff:Continuous Heal"], "Heal-tank", False),
    "revive":  (["revive", "team_buff:Revive On Death", "team_buff:Revive on Death"], "Revive last-resort", True),
}
SUSTAIN_TAGS = ["team_buff:Continuous Heal", "team_buff:Shield", "team_buff:Increase DEF",
                "team_buff:Block Damage", "team_buff:Unkillable", "team_buff:Ally Protection"]


def load_synergy():
    out = {}
    for line in open(SYNERGY, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        out[d["name"]] = d
    return out


def load_owned(min_grade=6):
    """Owned, comp-viable heroes (grade>=min_grade) by name. Falls back to
    live /all-heroes if the cache is missing."""
    heroes = None
    if HEROES.exists():
        try:
            heroes = json.loads(HEROES.read_text()).get("heroes", [])
        except Exception:
            heroes = None
    if heroes is None:
        import urllib.request
        with urllib.request.urlopen("http://localhost:6790/all-heroes?limit=20000", timeout=20) as r:
            heroes = json.loads(r.read()).get("heroes", [])
    names = set()
    for h in heroes:
        if (h.get("grade", 0) or 0) >= min_grade and h.get("name"):
            names.add(h["name"])
    return names


def has_any(hero, tags):
    prov = hero.get("provides", []) if hero else []
    return any(t in prov for t in tags)


def is_dps(hero):
    if not hero:
        return False
    if hero.get("synergy_role") in ("dot", "nuker", "dps"):
        return True
    return any(p.startswith("dot:") or p.startswith("debuff:Decrease DEF") for p in hero.get("provides", []))


def find(owned_names, syn, archetype, top=8, max_comps=2000):
    tags, label, needs_sustain = ARCHETYPES[archetype]
    owned = [n for n in owned_names if n in syn]
    providers = [n for n in owned if has_any(syn[n], tags)]
    sustainers = [n for n in owned if has_any(syn[n], SUSTAIN_TAGS)]
    dps = [n for n in owned if is_dps(syn[n])]
    candidates = []
    # Core = 1 provider (+1 extra sustainer if the archetype needs it), then
    # fill the rest with DPS for damage + role diversity. Sampled/capped.
    seen = set()
    for prov in providers:
        pool_sustain = [s for s in sustainers if s != prov]
        # second sustain options (or skip if not needed)
        second_opts = pool_sustain[:6] if needs_sustain else [None]
        for s2 in second_opts:
            core = [prov] + ([s2] if s2 else [])
            fill_pool = [d for d in dps if d not in core][:10]
            need = 5 - len(core)
            for combo in itertools.combinations(fill_pool, need):
                team = tuple(sorted(core + list(combo)))
                if team in seen:
                    continue
                seen.add(team)
                # provider coverage score (game-truth only): distinct survival
                # axes the team covers + dps count. NO external ratings.
                axes = set()
                for m in team:
                    for p in syn[m].get("provides", []):
                        if p in SUSTAIN_TAGS or p in tags:
                            axes.add(p)
                n_dps = sum(1 for m in team if is_dps(syn[m]))
                score = len(axes) * 10 + n_dps
                candidates.append((score, team, sorted(axes), n_dps))
                if len(candidates) >= max_comps:
                    break
            if len(candidates) >= max_comps:
                break
        if len(candidates) >= max_comps:
            break
    candidates.sort(reverse=True)
    return {"providers": providers, "label": label, "needs_sustain": needs_sustain,
            "candidates": candidates[:top]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--archetype", choices=list(ARCHETYPES) + ["all"], default="all")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--min-grade", type=int, default=6)
    ap.add_argument("--validate", action="store_true",
                    help="run each candidate through cb_sim survival (UNVALIDATED until M7 Gate A)")
    ap.add_argument("--element", default="force", choices=["magic", "force", "spirit", "void"])
    args = ap.parse_args(argv)

    syn = load_synergy()
    owned = load_owned(args.min_grade)
    print(f"owned comp-viable heroes (grade>={args.min_grade}): {len(owned)} | synergy-graph heroes: {len(syn)}")
    archs = list(ARCHETYPES) if args.archetype == "all" else [args.archetype]

    val = None
    if args.validate:
        from cb_survival_diff import run_sim, ELEMENT_MAP
        print("\n!!! --validate uses cb_sim survival, which OVER-PREDICTS until M7 Gate A. "
              "Treat survival turns as OPTIMISTIC, not trustworthy. !!!")

    for a in archs:
        r = find(owned, syn, a, top=args.top)
        print(f"\n=== {a.upper()} — {r['label']} ===")
        print(f"  owned providers ({len(r['providers'])}): {', '.join(r['providers'][:20]) or '(none)'}")
        if not r["candidates"]:
            print("  (no candidate comps — missing a provider or DPS fillers)")
            continue
        print(f"  candidate comps (game-truth synergy score; survival UNVALIDATED):")
        for score, team, axes, n_dps in r["candidates"]:
            line = f"    [{score:>3}] {', '.join(team)}  | dps={n_dps} axes={len(axes)}"
            if args.validate:
                try:
                    sim = run_sim(list(team), ELEMENT_MAP[args.element])
                    line += f"  | sim~T{sim['cb_turns']}(optimistic)"
                except Exception as ex:
                    line += f"  | sim_err:{str(ex)[:30]}"
            print(line)
    print("\nNOTE: 'survival UNVALIDATED' — these are candidates that HAVE the providers "
          "to attempt the pattern. Ranking is game-truth synergy coverage only (no HH/DWJ). "
          "Trustworthy survive/wipe verdicts require M7 Gate A (hardened survival sim).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
