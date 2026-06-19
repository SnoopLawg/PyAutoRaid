"""Per-champion skill audit: compare each skill's static-data effects against
what the sim has loaded in SKILL_EFFECTS + SKILL_DATA.

Identifies effect-by-effect gaps so we can prioritize sim modeling work.

Usage:
    python3 tools/skill_audit.py --team "Maneater,Demytha,Ninja,Geomancer,Venomage"
    python3 tools/skill_audit.py --team "Maneater" --verbose
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))


def static_effects_for(snapshot: dict, hero: str, sid: int) -> list[dict]:
    """Return the Effects array for a given hero+skill from the snapshot."""
    h = snapshot.get(hero) or {}
    skill = h.get(str(sid)) or h.get(sid)
    if not skill:
        return []
    return skill.get("Effects") or []


def kind_label(kind: str | None) -> str:
    """Short label for an effect kind so the audit table fits on one line."""
    if not kind:
        return "?"
    return kind.replace("Status", "").replace("AoEC", "AoE_C")[:24]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", required=True,
                    help="Comma-separated hero names")
    ap.add_argument("--snapshot",
                    default="data/static/snapshots/men_skills_depth8.json",
                    help="Depth-8 skill snapshot to use as ground truth")
    ap.add_argument("--verbose", action="store_true",
                    help="Show per-effect details, not just summaries")
    args = ap.parse_args()

    snap_path = PROJECT_ROOT / args.snapshot
    if not snap_path.exists():
        print(f"snapshot not found: {snap_path}")
        print("Run the snapshot extractor first.")
        return 1
    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))

    from load_game_profiles import load_profiles
    sd, se, pd, sids = load_profiles()

    team = [n.strip() for n in args.team.split(",") if n.strip()]
    total_static = 0
    total_modeled = 0
    issues: list[str] = []

    for hero in team:
        if hero not in snapshot:
            print(f"  {hero}: NOT IN SNAPSHOT — skipping")
            continue
        print(f"\n=== {hero} ===")
        hero_sids = sids.get(hero, {})  # {"A1": 62001, "A2": 62002, "A3": 62003}
        hero_skill_data = sd.get(hero, {})
        hero_skill_effects = se.get(hero, {})
        # Map skill_id -> label
        sid_to_label = {sid: lbl for lbl, sid in hero_sids.items()}

        for sid_str, skill in snapshot[hero].items():
            sid = int(sid_str)
            label = sid_to_label.get(sid, f"skill_{sid}")
            static_effs = skill.get("Effects") or []
            sim_effs = hero_skill_effects.get(label, [])
            sim_skill = hero_skill_data.get(label, {})
            sim_buffs = sim_skill.get("team_buffs", [])
            sim_tm_fill = sim_skill.get("team_tm_fill", 0)
            sim_self_tm = sim_skill.get("self_tm_fill", 0)
            sim_mult = sim_skill.get("mult", 0)

            total_static += len(static_effs)
            # Approx count of what's modeled: each SkillEffect + each team_buff +
            # 1 if mult>0 + 1 per tm fill
            modeled_approx = len(sim_effs) + len(sim_buffs)
            if sim_mult > 0:
                modeled_approx += 1
            if sim_tm_fill > 0:
                modeled_approx += 1
            if sim_self_tm > 0:
                modeled_approx += 1
            total_modeled += modeled_approx

            print(f"  {label} (id={sid}, {len(static_effs)} static effects, "
                  f"~{modeled_approx} modeled):")
            # List static effects
            for i, e in enumerate(static_effs):
                kind = e.get("KindId") or e.get("Kind")
                ttype = e.get("TargetType", "?")
                mult = e.get("MultiplierFormula", "")
                chance = e.get("Chance")
                ses = e.get("StatusEffectInfos") or []
                target_params = e.get("TargetParams") or {}
                if isinstance(target_params, dict):
                    tp_target = target_params.get("TargetType", "")
                else:
                    tp_target = ""
                rel = e.get("Relation") or {}
                glance_gated = " [GG]" if rel.get("ActivateOnGlancingHit") is False else ""
                label_kind = kind_label(kind)
                if args.verbose:
                    print(f"    E[{i}]: {label_kind:24s} -> {ttype or tp_target}  "
                          f"mult={mult}  chance={chance}  status={ses}{glance_gated}")
                else:
                    print(f"    E[{i}]: {label_kind:24s} -> {ttype or tp_target} {mult}{glance_gated}")

            # List what sim has
            if sim_mult or sim_buffs or sim_effs or sim_tm_fill or sim_self_tm:
                print(f"    [sim] mult={sim_mult} buffs={sim_buffs}")
                for e in sim_effs:
                    et = e.get("effect_type") if isinstance(e, dict) else getattr(e, "effect_type", "?")
                    ep = e.get("params") if isinstance(e, dict) else getattr(e, "params", {})
                    print(f"    [sim] {et}: {ep}")
                if sim_tm_fill:
                    print(f"    [sim] team_tm_fill={sim_tm_fill}")
                if sim_self_tm:
                    print(f"    [sim] self_tm_fill={sim_self_tm}")
            else:
                issues.append(f"{hero}.{label}: NO modeled effects ({len(static_effs)} static)")
                print(f"    [sim] EMPTY — modeling gap")

    print(f"\n=== Summary ===")
    print(f"  Static effects total: {total_static}")
    print(f"  Sim-modeled approx:   {total_modeled}")
    print(f"  Coverage: {total_modeled/max(total_static,1)*100:.0f}%")
    if issues:
        print(f"\n  Skills with no modeled effects ({len(issues)}):")
        for i in issues:
            print(f"    - {i}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
