"""Audit sim skill-effect coverage across every owned hero.

Reads the depth-8 snapshots from build_skill_snapshots and compares to
what load_game_profiles.load_profiles() produces. Reports:

  - Per-hero coverage (%modeled), sorted lowest-first
  - Most-common un-modeled effect kinds (translator priority queue)
  - Skills with zero modeled effects (urgent gaps)

Usage:
    python3 tools/skill_coverage_report.py
    python3 tools/skill_coverage_report.py --top-heroes 30 --top-kinds 20
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

SNAPSHOT_FILE = PROJECT_ROOT / "data" / "static" / "snapshots" / "all_skills_depth8.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-heroes", type=int, default=25)
    ap.add_argument("--top-kinds", type=int, default=20)
    args = ap.parse_args()

    if not SNAPSHOT_FILE.exists():
        print(f"missing {SNAPSHOT_FILE} — run tools/build_skill_snapshots.py first")
        return 1
    snap = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    all_skills = snap.get("skills", {})  # {str(sid): skill_dict}

    # Universe-wide hero list: use hero_profiles_game.json (which now covers
    # all 1100+ heroes after build_all_hero_profiles.py runs).
    hp = json.loads((PROJECT_ROOT / "hero_profiles_game.json").read_text(encoding="utf-8"))
    hero_skill_ids: dict[str, set[int]] = {}
    for hero_name, prof in hp.items():
        ids = set()
        for s in (prof.get("skills") or []):
            sid = s.get("id")
            if isinstance(sid, int):
                ids.add(sid)
        if ids:
            hero_skill_ids[hero_name] = ids

    from load_game_profiles import load_profiles
    sd, se, pd, sids_map = load_profiles()

    # Per-hero stats
    hero_stats: dict[str, dict] = {}
    unmodeled_kinds_total = Counter()
    zero_modeled_skills: list[tuple[str, int]] = []  # (hero, skill_id)

    for hero, hero_sids in hero_skill_ids.items():
        hero_labels = sids_map.get(hero, {})  # {"A1": sid, ...}
        # Reverse: sid -> label
        sid_to_label = {sid: lbl for lbl, sid in hero_labels.items()}
        hero_effects = se.get(hero, {})
        hero_skill_data = sd.get(hero, {})

        total_static = 0
        total_modeled = 0
        labeled_skills = 0  # sim has the skill labeled (A1/A2/A3) — passives often not
        passive_skills = 0  # static skill but no sim label
        for sid in hero_sids:
            skill = all_skills.get(str(sid))
            if not skill:
                continue
            static_effs = skill.get("Effects") or []
            total_static += len(static_effs)
            label = sid_to_label.get(sid)
            if label:
                labeled_skills += 1
                sim_effs = hero_effects.get(label, [])
                sim_skill = hero_skill_data.get(label, {})
                # Approx modeled = effects + team_buffs + mult + tm fills
                modeled = (
                    len(sim_effs)
                    + len(sim_skill.get("team_buffs", []))
                    + (1 if sim_skill.get("mult", 0) > 0 else 0)
                    + (1 if sim_skill.get("team_tm_fill", 0) > 0 else 0)
                    + (1 if sim_skill.get("self_tm_fill", 0) > 0 else 0)
                )
                total_modeled += modeled
                if modeled == 0 and static_effs:
                    zero_modeled_skills.append((hero, sid))
            else:
                passive_skills += 1
                # Passives are processed into `passive_data` (sim flag map).
                # Credit them if the hero has ANY passive_data flag set.
                # Per-effect mapping isn't 1:1 — a passive with 6 static
                # effects may produce 1-2 flags (e.g. Stoneguard's 6
                # effects → team_dmg_reduction + dmg_reduction). Credit at
                # 70% to acknowledge partial modeling without overclaiming.
                hero_passive_flags = pd.get(hero, {})
                if hero_passive_flags:
                    # Approximate credit: count flags as ~half of static effects
                    static_count = len(static_effs)
                    flag_count = len(hero_passive_flags)
                    # Credit min(static_count, max(flag_count, static_count/2))
                    credited = min(
                        static_count,
                        max(flag_count, static_count // 2))
                    total_modeled += credited
                    if credited < static_count:
                        # Still count the un-modeled excess
                        for e in static_effs[credited:]:
                            kind = e.get("KindId") or e.get("Kind") or "?"
                            unmodeled_kinds_total[kind] += 1
                else:
                    # No passive flags at all — fully un-modeled
                    for e in static_effs:
                        kind = e.get("KindId") or e.get("Kind") or "?"
                        unmodeled_kinds_total[kind] += 1
                    zero_modeled_skills.append((hero, sid))

        if total_static:
            hero_stats[hero] = {
                "static": total_static,
                "modeled": total_modeled,
                "coverage": total_modeled / total_static,
                "labeled": labeled_skills,
                "passive": passive_skills,
            }

    # Sort heroes by coverage (worst first)
    print(f"\n=== SUMMARY ===")
    total_static = sum(s["static"] for s in hero_stats.values())
    total_modeled = sum(s["modeled"] for s in hero_stats.values())
    print(f"  Heroes audited: {len(hero_stats)}")
    print(f"  Total static effects: {total_static}")
    print(f"  Total modeled (approx): {total_modeled}")
    print(f"  Overall coverage: {total_modeled / max(total_static, 1) * 100:.0f}%")
    print(f"  Skills with zero modeled effects: {len(zero_modeled_skills)}")

    print(f"\n=== {args.top_heroes} LOWEST-COVERAGE HEROES ===")
    sorted_heroes = sorted(hero_stats.items(), key=lambda x: x[1]["coverage"])
    for hero, st in sorted_heroes[:args.top_heroes]:
        print(f"  {hero:30s} {st['coverage']*100:3.0f}%  "
              f"({st['modeled']:3d}/{st['static']:3d})  "
              f"labeled={st['labeled']} passive={st['passive']}")

    print(f"\n=== TOP {args.top_kinds} UN-MODELED EFFECT KINDS ===")
    for kind, count in unmodeled_kinds_total.most_common(args.top_kinds):
        print(f"  {kind:40s} {count:4d}")

    print(f"\n=== SKILLS WITH ZERO MODELED EFFECTS (first 20) ===")
    for hero, sid in zero_modeled_skills[:20]:
        skill = all_skills.get(str(sid)) or {}
        name = skill.get("Name", {}).get("DefaultValue", "?") if isinstance(skill.get("Name"), dict) else skill.get("Name", "?")
        eff_count = len(skill.get("Effects") or [])
        print(f"  {hero:25s} sid={sid:8d} effects={eff_count:2d} {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
