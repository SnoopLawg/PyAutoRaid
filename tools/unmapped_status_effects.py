"""Find StatusEffect TypeIds referenced by static skill data that aren't in
SE_TO_SIM (load_game_profiles.py). These are the buffs/debuffs the sim
silently drops when translating skill effects.

Reads the depth-8 snapshot, walks every Apply{Buff,Debuff} effect's
StatusEffectInfos array, counts TypeIds not in SE_TO_SIM. Reports each
unmapped TypeId with: count, sample heroes, sample skill names, the
effect's group (Active/Passive) so the user can prioritize.

Usage:
    python3 tools/unmapped_status_effects.py
    python3 tools/unmapped_status_effects.py --top 30
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

SNAPSHOT_FILE = PROJECT_ROOT / "data" / "static" / "snapshots" / "all_skills_depth8.json"
EFFECTS_FILE = PROJECT_ROOT / "data" / "static" / "effects.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    snap = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    all_skills = snap.get("skills", {})

    from load_game_profiles import SE_TO_SIM

    # Effect kind name lookup (Id -> KindId)
    effects_static = json.loads(EFFECTS_FILE.read_text(encoding="utf-8"))
    effect_items = effects_static.get("data") or effects_static.get("effects") or []
    if not effect_items:
        # try root-level list
        effect_items = effects_static if isinstance(effects_static, list) else []
    id_to_kind = {}
    if isinstance(effect_items, list):
        for it in effect_items:
            if isinstance(it, dict):
                eid = it.get("Id") or it.get("id")
                kind = it.get("KindId") or it.get("kind_id")
                if eid is not None and kind:
                    id_to_kind[int(eid)] = kind

    # Build skill_id -> hero_name + skill_name lookup
    skills_db = json.loads((PROJECT_ROOT / "skills_db.json").read_text(encoding="utf-8"))
    sid_to_hero_name: dict[int, tuple[str, str]] = {}
    for hero, skills in skills_db.items():
        for s in skills:
            if isinstance(s, dict):
                sid = s.get("skill_type_id")
                if isinstance(sid, int) and sid not in sid_to_hero_name:
                    sid_to_hero_name[sid] = (hero, s.get("name") or f"skill_{sid}")

    # Walk every ApplyBuff/ApplyDebuff and check TypeIds
    unmapped: dict[int, dict] = defaultdict(lambda: {
        "count": 0,
        "samples": [],  # (hero, skill, kind_id, status_kind, group)
    })

    for sid_str, skill in all_skills.items():
        sid = int(sid_str)
        hero, skill_name = sid_to_hero_name.get(sid, ("?", "?"))
        for eff in (skill.get("Effects") or []):
            kind = eff.get("KindId") or eff.get("Kind", "")
            if kind not in (
                "ApplyBuff", "ApplyDebuff",
                "ApplyOrProlongBuff", "ApplyOrProlongDebuff",
            ):
                continue
            group = eff.get("Group", "")
            # TypeIds live at ApplyStatusEffectParams.StatusEffectInfos (the
            # bare StatusEffectInfos at effect-root is None at depth=8).
            ase_params = eff.get("ApplyStatusEffectParams") or {}
            for sei in (ase_params.get("StatusEffectInfos") or []):
                tid = sei.get("TypeId")
                if not isinstance(tid, int):
                    continue
                # Skip if already mapped
                if tid in SE_TO_SIM:
                    continue
                slot = unmapped[tid]
                slot["count"] += 1
                if len(slot["samples"]) < 3:
                    status_kind = id_to_kind.get(tid, "?")
                    slot["samples"].append(
                        (hero, skill_name, kind, status_kind, group))

    print(f"\n=== UNMAPPED StatusEffect TypeIds ({len(unmapped)} unique) ===")
    sorted_unmapped = sorted(
        unmapped.items(), key=lambda x: -x[1]["count"])
    for tid, info in sorted_unmapped[:args.top]:
        # Resolve a kind label
        first_kind = info["samples"][0][3] if info["samples"] else "?"
        print(f"\n  TypeId {tid}  ({first_kind})  uses={info['count']}")
        for hero, skill_name, apply_kind, status_kind, group in info["samples"]:
            print(f"    {hero:25s}  {skill_name:40s}  [{apply_kind}, group={group}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
