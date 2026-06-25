"""Survival-first comp finder -- M7 Phase B1 (coverage-chain enumerator).

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
comp survives -- that's M7 Gate B (validation through the HARDENED survival sim),
which is blocked on Gate A (survival-model calibration vs a real fixture
battery). Every comp here is a CANDIDATE: "has the providers to *attempt* the
pattern." Use `--validate` to run each through cb_sim survival (clearly marked
UNVALIDATED until Gate A -- the sim currently over-predicts survival).

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
SKILLS_DB = PROJECT_ROOT / "skills_db.json"
EFFECTS = PROJECT_ROOT / "data" / "static" / "effects.json"

# Archetype -> the internal effect KindId(s) of its PRIMARY defensive buff.
# Mapped to concrete type-ids at runtime from data/static/effects.json
# (game-truth catalog). ShareDamage is the internal name for [Ally Protection].
ARCHETYPE_BUFF_KINDS = {
    "uk":      ["Unkillable"],
    "bd":      ["BlockDamage"],
    "counter": ["StatusCounterattack", "DamageCounter"],
    "protect": ["ShareDamage"],
    "heal":    ["ContinuousHeal"],
    "revive":  ["ReviveOnDeath"],
}

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


def load_skills_db():
    """Per-account skills (book-status-accurate): {hero_name -> [skill,...]}.
    Returns {} if absent (classifier then reports 'unknown')."""
    if not SKILLS_DB.exists():
        return {}
    try:
        return json.loads(SKILLS_DB.read_text(encoding="utf-8"))
    except Exception:
        return {}


def buff_type_ids(kindids):
    """Resolve a list of effect KindId names to their integer type-ids using
    the game-truth catalog (one KindId can map to several ids, e.g.
    ContinuousHeal -> {90, 91})."""
    ids = set()
    if not EFFECTS.exists():
        return ids
    try:
        rows = json.loads(EFFECTS.read_text(encoding="utf-8"))["data"]
    except Exception:
        return ids
    want = set(kindids)
    for r in rows:
        if str(r.get("KindId")) in want and r.get("Id") is not None:
            ids.add(r.get("Id"))
    return ids


def _providers_with_timing(team, skills_db, target_ids):
    """For each hero in `team`, find skills that PLACE one of `target_ids`
    (an ApplyBuff-style status effect) and return (hero, skill_name, cd, dur).
    dur=None means the buff has no listed duration (treated as permanent /
    passive, e.g. Revive on Death)."""
    out = []
    for hero in team:
        for s in skills_db.get(hero, []):
            cd = s.get("cooldown", 0) or 0
            best_dur = None
            placed = False
            for e in s.get("effects", []):
                for se in (e.get("status_effects") or []):
                    if se.get("type") in target_ids:
                        placed = True
                        d = se.get("duration")
                        if d is not None:
                            best_dur = d if best_dur is None else max(best_dur, d)
            if placed:
                out.append((hero, s.get("name", "?"), cd, best_dur))
    return out


def classify_cast_pattern(team, archetype, skills_db, syn):
    """Structural auto-vs-manual classifier (M7 B3).

    Answers: can the archetype's defensive buff be kept GAPLESS by a static
    preset (opener + priority = "cast on cooldown"), or does it require a
    *timed hold/delay* that a preset cannot express?

    Game-truth inputs only: per-skill cooldown + buff duration (skills_db,
    book-accurate) and the buff_extension synergy axis. This is a property of
    the CAST CADENCE, NOT a survival prediction -- a comp can be 'AUTO' here
    and still wipe (survival is Gate A/B).

    Returns (label, reason) where label in {AUTO, MANUAL, UNKNOWN}.
    """
    if not skills_db:
        return ("UNKNOWN", "no skills_db (run from a synced account)")
    # Revive is a passive/last-resort safety net cast on cooldown -- no hold.
    if archetype == "revive":
        return ("AUTO", "revive is passive / cast-on-cooldown -- no manual hold")

    ids = buff_type_ids(ARCHETYPE_BUFF_KINDS.get(archetype, []))
    if not ids:
        return ("UNKNOWN", f"no catalog ids for {archetype}")
    provs = _providers_with_timing(team, skills_db, ids)
    if not provs:
        return ("UNKNOWN", "no owned-skill provider of the archetype buff in team")

    # 1) Gapless by spam: a provider whose buff lasts at least as long as its
    #    own cooldown (or an A1 / permanent buff) keeps it up cast-on-cooldown.
    for hero, sk, cd, dur in provs:
        if dur is None:
            return ("AUTO", f"{hero} {sk}: permanent/passive buff -- gapless")
        if cd == 0:
            return ("AUTO", f"{hero} {sk}: A1-placed (cd0), buff {dur}t -- gapless on spam")
        if dur >= cd:
            return ("AUTO", f"{hero} {sk}: buff {dur}t >= cd {cd} -- gapless on spam")

    # 2) Extension ally re-ups a short buff each cycle (Demytha-A2 style).
    extenders = [h for h in team if "buff_extension" in syn.get(h, {}).get("provides", [])]
    if extenders:
        worst = min((d for *_, d in provs if d is not None), default="?")
        return ("AUTO",
                f"buff_extension ({', '.join(extenders)}) covers the cd>dur gap "
                f"(buff {worst}t) -- preset-expressible (gated on speed-tune, not manual play)")

    # 3) Stagger: 2+ distinct providers alternate to tile the timeline.
    if len({h for h, *_ in provs}) >= 2:
        names = ", ".join(sorted({h for h, *_ in provs}))
        return ("AUTO", f"multiple providers ({names}) stagger to cover the gap")

    # 4) Single short-buff provider, no extension, no stagger: the only way to
    #    hold it is a timed delay/hold a static preset cannot express.
    hero, sk, cd, dur = provs[0]
    return ("MANUAL",
            f"{hero} {sk}: buff {dur}t < cd {cd}, no extension/stagger -- needs a "
            f"timed hold (not preset-expressible); NOT auto-recommended")


def has_any(hero, tags):
    prov = hero.get("provides", []) if hero else []
    return any(t in prov for t in tags)


def is_dps(hero):
    if not hero:
        return False
    if hero.get("synergy_role") in ("dot", "nuker", "dps"):
        return True
    return any(p.startswith("dot:") or p.startswith("debuff:Decrease DEF") for p in hero.get("provides", []))


def find(owned_names, syn, archetype, top=8, max_comps=2000, skills_db=None):
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
                cast = classify_cast_pattern(list(team), archetype, skills_db or {}, syn)
                candidates.append((score, team, sorted(axes), n_dps, cast))
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
    ap.add_argument("--auto-only", action="store_true",
                    help="show only comps whose cast pattern is preset-expressible "
                         "(AUTO); hides MANUAL-delay comps (B3: never auto-recommend manual)")
    args = ap.parse_args(argv)

    syn = load_synergy()
    owned = load_owned(args.min_grade)
    skills_db = load_skills_db()
    print(f"owned comp-viable heroes (grade>={args.min_grade}): {len(owned)} | synergy-graph heroes: {len(syn)}")
    archs = list(ARCHETYPES) if args.archetype == "all" else [args.archetype]

    val = None
    if args.validate:
        from cb_survival_diff import run_sim, ELEMENT_MAP
        print("\n!!! --validate uses cb_sim survival, which OVER-PREDICTS until M7 Gate A. "
              "Treat survival turns as OPTIMISTIC, not trustworthy. !!!")

    for a in archs:
        r = find(owned, syn, a, top=args.top, skills_db=skills_db)
        print(f"\n=== {a.upper()} -- {r['label']} ===")
        print(f"  owned providers ({len(r['providers'])}): {', '.join(r['providers'][:20]) or '(none)'}")
        if not r["candidates"]:
            print("  (no candidate comps -- missing a provider or DPS fillers)")
            continue
        print(f"  candidate comps (game-truth synergy score; survival UNVALIDATED):")
        shown = 0
        for score, team, axes, n_dps, cast in r["candidates"]:
            label, reason = cast
            if args.auto_only and label != "AUTO":
                continue
            line = (f"    [{score:>3}] {', '.join(team)}  | dps={n_dps} "
                    f"axes={len(axes)} | cast={label}")
            if args.validate:
                try:
                    sim = run_sim(list(team), ELEMENT_MAP[args.element])
                    line += f"  | sim~T{sim['cb_turns']}(optimistic)"
                except Exception as ex:
                    line += f"  | sim_err:{str(ex)[:30]}"
            print(line)
            print(f"          cast: {reason}")
            shown += 1
        if args.auto_only and shown == 0:
            print("  (no AUTO-classified comps -- all candidates need manual delay-tuning)")
    print("\nNOTE: 'survival UNVALIDATED' -- these are candidates that HAVE the providers "
          "to attempt the pattern. Ranking is game-truth synergy coverage only (no HH/DWJ). "
          "Trustworthy survive/wipe verdicts require M7 Gate A (hardened survival sim).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
