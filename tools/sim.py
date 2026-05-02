"""Universal sim dispatcher — pick a battle, sim a team.

Front door for any battle PyAutoRaid can simulate. Backed by per-engine
implementations:
- engine=cb        → tools/cb_sim.py (CBSimulator) — fully implemented
- engine=hydra     → not yet implemented (multi-head + decapitation)
- engine=chimera   → not yet implemented
- engine=doom_tower → not yet implemented

Usage:
    python3 tools/sim.py --list-locations
    python3 tools/sim.py --location cb-unm-void --team "ME,Demytha,Ninja,Geo,Venomage"
    python3 tools/sim.py --location cb-nm-force --team "..." --verbose

The --location slug shape comes from boss_profiles.py (e.g. cb-unm-void,
hydra-unm, chimera-brutal, dt-hard-f120). New engines plug in by adding
a dispatch arm below.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make `from boss_profiles import ...` work when running this directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from boss_profiles import BossProfile, list_locations, lookup


def _print_locations() -> None:
    """Tabular listing of every profile in the registry."""
    profiles = list_locations()
    print(f"=== {len(profiles)} battle profiles ===\n")
    print(f"  {'slug':30s} {'engine':12s} {'difficulty':10s} {'hp':>14s} {'speed':>6s}")
    print(f"  {'-'*30} {'-'*12} {'-'*10} {'-'*14} {'-'*6}")
    cur_engine = None
    for p in profiles:
        if p.engine != cur_engine:
            cur_engine = p.engine
            status = "" if p.engine == "cb" else "  (not yet implemented)"
            print(f"\n  -- engine={p.engine}{status} --")
        hp_s = f"{p.hp:,}" if p.hp else "-"
        spd_s = f"{p.speed:g}" if p.speed else "-"
        print(f"  {p.slug:30s} {p.engine:12s} {(p.difficulty or '-'):10s} {hp_s:>14s} {spd_s:>6s}")


_CB_DIFFICULTY_SLUG_TO_CLI = {
    "easy": "easy", "normal": "normal", "hard": "hard",
    "brutal": "brutal", "nm": "nightmare", "unm": "ultra-nightmare",
}
_CB_ELEMENT_NAME = {1: "magic", 2: "force", 3: "spirit", 4: "void"}


def _run_cb(profile: BossProfile, team: list[str], *, verbose: bool,
            force_affinity: bool, max_cb_turns: int, speed_aura: float,
            use_current_gear: bool) -> int:
    """Dispatch to cb_potential.simulate_team with the BossProfile's
    difficulty + element threaded through. After the Phase 3 follow-up
    landed, simulate_team accepts cb_difficulty/cb_element kwargs and
    cb_constants.CB_HP_BY_DIFFICULTY / CB_SPEED_BY_DIFFICULTY do the
    rest.
    """
    from cb_potential import simulate_team
    result = simulate_team(
        team,
        verbose=verbose,
        cb_element=profile.element if profile.element else 4,
        cb_difficulty=_CB_DIFFICULTY_SLUG_TO_CLI.get(profile.difficulty or "unm"),
    )
    if "error" in result:
        print(f"ERR: {result['error']}", file=sys.stderr)
        return 1

    print(f"\n=== {profile.name} ===")
    print(f"Team: {', '.join(team)}")
    total_m = result.get("total", 0) / 1e6
    cb_turns = result.get("cb_turns", "?")
    print(f"Total damage: {total_m:.2f}M over {cb_turns} CB turns\n")
    print(f"  {'Hero':20s} {'Total':>10s} {'Direct':>10s} {'Poison':>10s} {'Burn':>10s} {'WM/GS':>10s} {'Pass':>10s}")
    for h in result.get("heroes", []):
        print(f"  {h['name']:20s} {h.get('total', 0):>10,.0f} {h.get('direct', 0):>10,.0f} "
              f"{h.get('poison', 0):>10,.0f} {h.get('hp_burn', 0):>10,.0f} {h.get('wm_gs', 0):>10,.0f} "
              f"{h.get('passive', 0):>10,.0f}")
    return 0


def _run_stub(profile: BossProfile) -> int:
    """Placeholder for engines whose sim isn't built yet — but surface
    whatever metadata we already have for the profile, so the user
    sees stage IDs / modifiers / element / etc. without needing the
    engine to land."""
    print(f"=== {profile.name} ===")
    print(f"slug={profile.slug}  engine={profile.engine}  location={profile.location}")
    if profile.difficulty:
        print(f"difficulty={profile.difficulty}")
    if profile.element:
        from boss_profiles import ELEMENT_NAME_BY_ID
        print(f"element={ELEMENT_NAME_BY_ID.get(profile.element, profile.element)}")
    if profile.head_count > 1:
        print(f"head_count={profile.head_count}")
    # Doom Tower stashes stage metadata in head_specific_skills for now.
    meta = profile.head_specific_skills if isinstance(profile.head_specific_skills, dict) else {}
    if meta:
        print()
        for k in ("stage_id", "scene", "has_boss", "has_double_boss",
                  "is_secret_chamber", "region_variants"):
            if k in meta:
                print(f"{k}: {meta[k]}")
        modifiers = meta.get("modifiers") or []
        if modifiers:
            print(f"\nPer-round modifiers ({len(modifiers)}):")
            for m in modifiers[:12]:
                rnd = m.get("Round", "?")
                kind = m.get("KindId", "?")
                val = m.get("Value", "?")
                abs_str = "abs" if m.get("IsAbsolute") else "%"
                target = "boss" if m.get("BossOnly") else "all"
                print(f"  R{rnd}: {kind} +{val}{abs_str} ({target})")
            if len(modifiers) > 12:
                print(f"  ... +{len(modifiers) - 12} more")
    print(f"\nThe {profile.engine} sim engine is not yet implemented.")
    print(f"Profile loaded successfully — when the engine ships,")
    print(f"`python3 tools/sim.py --location {profile.slug}` will route to it.")
    return 3


def _print_profile(hero_name: str) -> int:
    """Show the auto-derived skill profile for any hero (owned or not).

    Sources (in priority order):
    - skill_descriptions.json — per-account, books-applied (owned heroes)
    - data/static/skill_descriptions_all.json — static text for all 1121 heroes

    Output is the desc_profiler structured kit: hits, debuffs (type +
    chance + duration), buffs, extra_turn flag, ignore_def %, TM fills,
    activate-DoT triggers, ally-attack flag, etc.
    """
    from desc_profiler import parse_all_descriptions
    parsed = parse_all_descriptions()
    # Case-insensitive substring match against canonical names.
    matches = [n for n in parsed if hero_name.lower() in n.lower()]
    if not matches:
        print(f"ERR: no hero matching {hero_name!r}", file=sys.stderr)
        print("Try: python3 tools/desc_profiler.py  (lists all parsed heroes)", file=sys.stderr)
        return 1
    # Prefer exact / shortest match if multiple.
    matches.sort(key=lambda n: (hero_name.lower() != n.lower(), len(n)))
    name = matches[0]
    h = parsed[name]
    is_static = any(p.get("_static") for p in h.values())
    src = "static (unowned)" if is_static else "owned (book-aware)"
    print(f"=== {name} ===  source: {src}")
    for label in sorted(h.keys()):
        p = h[label]
        skill_name = p.get("name") or label
        stid = p.get("skill_type_id") or ""
        print(f"\n  {label}: {skill_name} [{stid}]")
        print(f"    Hits: {p.get('hits', 1)}")
        for db in p.get("debuffs", []):
            self_str = " (SELF)" if db.get("on_self") else ""
            print(f"    Debuff: {db['type']} dur={db['duration']} "
                  f"chance={db['chance']*100:.0f}% x{db['count']}{self_str}")
        for buf in p.get("buffs", []):
            print(f"    Buff: {buf['type']} dur={buf['duration']} target={buf['target']}")
        if p.get("extra_turn"):
            print(f"    Extra Turn")
        if p.get("ignore_def_pct"):
            print(f"    Ignore DEF: {p['ignore_def_pct']*100:.0f}%")
        if p.get("tm_fill_self"):
            print(f"    TM fill self: {p['tm_fill_self']*100:.0f}%")
        if p.get("tm_fill_team"):
            print(f"    TM fill team: {p['tm_fill_team']*100:.0f}%")
        if p.get("activate_burns"):
            print(f"    Activate HP Burns")
        if p.get("activate_poisons"):
            print(f"    Activate Poisons")
        if p.get("activate_dots"):
            print(f"    Activate ALL DoTs")
        if p.get("extend_debuffs"):
            print(f"    Extend debuffs: {p['extend_debuffs']}")
        if p.get("extend_buffs"):
            print(f"    Extend buffs")
        if p.get("ally_attack"):
            print(f"    Ally Attack")
        if p.get("cd_reduction"):
            print(f"    CD Reduction: {p['cd_reduction']}")
    if is_static:
        print(f"\n  (Note: parsed from static localization. Owned-hero descriptions in")
        print(f"  skill_descriptions.json reflect book upgrades + multipliers; this static")
        print(f"  text doesn't. Sim consumers should overlay hand-curated cb_profiles.py")
        print(f"  values when present.)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Universal sim dispatcher — pick a battle, sim a team.")
    ap.add_argument("--list-locations", action="store_true",
                    help="Print all known battle profiles and exit.")
    ap.add_argument("--location", "-l",
                    help="Profile slug (e.g. cb-unm-void). See --list-locations.")
    ap.add_argument("--team", help="Comma-separated hero names")
    ap.add_argument("--hero",
                    help="Hero name (with --print-profile)")
    ap.add_argument("--print-profile", action="store_true",
                    help="Print the auto-derived skill profile for the named hero. "
                         "Requires --hero <name>.")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--no-force-affinity", action="store_true",
                    help="CB only: disable Force-Affinity per-skill damage caps.")
    ap.add_argument("--max-cb-turns", type=int, default=50,
                    help="CB only: cap simulation at N CB turns. Default 50.")
    ap.add_argument("--speed-aura", type=float, default=0.0,
                    help="CB only: team-wide SPD aura percentage.")
    ap.add_argument("--use-current-gear", action="store_true",
                    help="CB only: use currently-equipped artifacts (no re-optimize).")
    args = ap.parse_args()

    if args.list_locations:
        _print_locations()
        return 0

    if args.print_profile:
        if not args.hero:
            ap.error("--print-profile requires --hero <name>")
        return _print_profile(args.hero)

    if not args.location:
        ap.error("--location required (or pass --list-locations / --hero ... --print-profile)")

    try:
        profile = lookup(args.location)
    except KeyError as e:
        print(f"ERR: {e}", file=sys.stderr)
        print("Try --list-locations to see all available profiles.", file=sys.stderr)
        return 1

    if profile.engine == "cb":
        if not args.team:
            ap.error("--team required for CB profiles")
        team = [n.strip() for n in args.team.split(",") if n.strip()]
        return _run_cb(
            profile, team,
            verbose=args.verbose,
            force_affinity=not args.no_force_affinity,
            max_cb_turns=args.max_cb_turns,
            speed_aura=args.speed_aura,
            use_current_gear=args.use_current_gear,
        )

    return _run_stub(profile)


if __name__ == "__main__":
    sys.exit(main())
