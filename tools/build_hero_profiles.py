#!/usr/bin/env python3
"""Build hero_profiles_game.json from skills_db.json.

load_game_profiles.py consumes this file with shape:
    {hero_name: {skills: [{id, type, cooldown, hits, mult, stat, effects}...]}}

The source skills_db.json is already keyed by hero name with per-skill details
(refreshed via `python tools/refresh_data.py`). This just reshapes it so
cb_sim can consume it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _skill_type(sk):
    if sk.get("is_a1"):
        return "A1"
    if sk.get("cooldown", 0) > 0:
        return "active"
    return "passive"


def _parse_mult_stat(effects):
    """Sum across ALL kind=6000 (damage) effects → (TOTAL mult, stat, total hits).

    The sim's `_calc_skill_damage` multiplies the scaling stat by `mult` ONCE
    (it does NOT multiply by hit_count), so `mult` must be the TOTAL multiplier
    across every hit of the skill:
        Demytha A1 = 3.2*ATK x Count 2         -> mult 6.4, hits 2
        Ninja  A2  = three separate 2*ATK      -> mult 6.0, hits 3
        Venom  A1  = two separate 2.4*ATK      -> mult 4.8, hits 2
        Maneater A1= one 5.5*ATK               -> mult 5.5, hits 1 (unchanged)
    This mirrors `build_all_hero_profiles._parse_mult_stat_from_static` (the
    un-owned path, which already sums). Previously this returned only the FIRST
    effect's per-hit mult, halving/thirding multi-hit OWNED heroes' direct
    damage — the dominant CB direct-under (task #35: real direct vs sim -42%
    team-wide). Caller passes boss-applicable effects only (Condition-filtered
    upstream), so summing here won't pull in !targetIsBoss splashes.
    """
    total_mult = 0.0
    total_hits = 0
    stat = "ATK"
    for eff in effects or []:
        if eff.get("kind") != 6000:
            continue
        f = (eff.get("formula") or "").strip()
        count = eff.get("count", 1) or 1
        m = re.match(r"^([\d.]+)\*(ATK|DEF|HP)", f)
        if m:
            total_mult += float(m.group(1)) * count
            stat = m.group(2)
            total_hits += count
            continue
        m = re.match(r"^(ATK|DEF|HP)\*([\d.]+)", f)
        if m:
            stat = m.group(1)
            total_mult += float(m.group(2)) * count
            total_hits += count
            continue
        m = re.match(r"^(ATK|DEF|HP)$", f)
        if m:
            stat = m.group(1)
            total_mult += 1.0 * count
            total_hits += count
            continue
    if total_hits == 0:
        return 0.0, "ATK", 1
    return total_mult, stat, total_hits


def main():
    skills_db = json.loads((ROOT / "skills_db.json").read_text())
    profiles = {}
    for hero_name, skill_list in skills_db.items():
        # skills_db can contain duplicate entries per hero (one per in-game
        # copy — Maneater×2 duplicates Pummel/Syphon/Ancient Blood twice).
        # Dedupe by skill_type_id before emitting or load_game_profiles will
        # map A3 to the wrong skill when actives have the same CD.
        seen_ids = set()
        profile_skills = []
        for sk in skill_list:
            sid = sk.get("skill_type_id") or sk.get("id", 0)
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            mult, stat, hits = _parse_mult_stat(sk.get("effects", []))
            profile_skills.append({
                "id": sid,
                "type": _skill_type(sk),
                "cooldown": sk.get("cooldown", 0) or 0,
                "hits": hits,
                "mult": mult,
                "stat": stat,
                "effects": sk.get("effects", []),
            })
        profiles[hero_name] = {"skills": profile_skills}
    out = ROOT / "hero_profiles_game.json"
    out.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(profiles)} hero profiles to {out.name}")


if __name__ == "__main__":
    main()
