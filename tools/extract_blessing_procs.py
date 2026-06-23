"""Extract game-truth blessing proc formulas, grade-by-grade.

Joins the authoritative blessing -> proc-skill mapping (from
`data/static/blessings.json`, which now carries `skill_type_id` after the
GetBlessingsTruth Nullable<int> fix) with each proc skill's effect formulas
(from `data/static/skills_all.json`), resolving the grade via the
`ownersDoubleAscendLevel==N` conditions.

This REPLACES the community-sourced hardcoded blessing values in
`tools/extract_blessing_manifest.py` with game-truth. NOTE on naming:
`blessings.json` `id` is the internal CODE enum name, while the UI display
name = the proc skill's localized name. They differ:
    code 'MagicOrb'     -> UI 'Phantom Touch' (600050, Rare)
    code 'Meteor'       -> UI 'Brimstone'     (600190, Legendary)
    code 'Exterminator' -> UI 'Cruelty'       (600040, Epic)
    code 'EnhancedWeapon' -> UI 'Heavencast'  (600090, Epic)
    code 'NatureBalance'  -> UI 'Nature's Wrath' (600270, Epic)
So the community/cb_sim names (Brimstone/Cruelty/Phantom Touch/Heavencast/
Nature's Wrath) are UI names and ARE valid — match by EITHER code id or
ui_name; `skill_type_id` is the authoritative link. Only "PerfectHeal" has
no current match (renamed/removed).

Output:
    data/static/blessing_procs.json — per-blessing, per-effect, per-grade
        {formula, kind, target, condition} game-truth.
    docs/m5_blessing_procs.md        — readable summary.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"
OUT_JSON = STATIC / "blessing_procs.json"
OUT_DOC = ROOT / "docs" / "m5_blessing_procs.md"

# Each grade-conditioned effect names the grades it applies to via
# `ownersDoubleAscendLevel==N` (possibly OR-joined). Extract the set of N.
_GRADE = re.compile(r"ownersDoubleAscendLevel\s*==\s*(\d+)")


def _load(name: str):
    with (STATIC / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def _skills_by_id() -> dict[int, dict]:
    sa = _load("skills_all.json")
    rows = sa.get("data") if isinstance(sa, dict) else sa
    if isinstance(sa, dict) and not rows:
        for k, v in sa.items():
            if k != "_meta" and isinstance(v, list):
                rows = v
                break
    return {s.get("Id"): s for s in (rows or [])}


def grades_for(condition: str) -> list[int]:
    if not condition:
        return []
    return sorted({int(m) for m in _GRADE.findall(condition)})


def main() -> None:
    blessings = _load("blessings.json")
    bl = blessings.get("blessings", blessings) if isinstance(blessings, dict) else blessings
    skills = _skills_by_id()

    out = []
    for b in bl:
        bid = b.get("id")
        # Distinct proc skill ids across grade bonuses.
        skill_ids = sorted({g["skill_type_id"] for g in b.get("grade_bonuses", [])
                            if "skill_type_id" in g})
        proc = []
        for sk_id in skill_ids:
            sk = skills.get(sk_id)
            if not sk:
                proc.append({"skill_id": sk_id, "missing": True})
                continue
            effects = []
            for e in sk.get("Effects") or []:
                cond = e.get("Condition") or ""
                effects.append({
                    "kind": e.get("KindId"),
                    "formula": e.get("MultiplierFormula") or "",
                    "target": e.get("TargetType"),
                    "grades": grades_for(cond),
                    "condition": cond[:160],
                })
            proc.append({
                "skill_id": sk_id,
                "skill_name": (sk.get("Name") or {}).get("DefaultValue", ""),
                "effects": effects,
            })
        # UI display name = the proc skill's name (Plarium shows the blessing
        # under its skill's localized name, NOT the internal code enum `id`).
        # e.g. code id "MagicOrb" displays as "Phantom Touch"; "Meteor" shows
        # as "Brimstone"; "Exterminator" as "Cruelty". cb_sim's has_brimstone /
        # phantom_touch / heavencast / natures_wrath key off these UI names.
        ui_name = next((p.get("skill_name") for p in proc if p.get("skill_name")), None)
        out.append({
            "blessing_code_id": bid,
            "ui_name": ui_name,
            "rarity": b.get("rarity"),
            "divinity": b.get("divinity"),
            "proc_skills": proc,
        })

    payload = {
        "_meta": {
            "generated_by": "tools/extract_blessing_procs.py",
            "total_blessings": len(out),
            "note": ("Authoritative blessing->skill link from blessings.json "
                     "skill_type_id (GetBlessingsTruth Nullable fix 2026-06-23). "
                     "Grade resolved via ownersDoubleAscendLevel==N conditions."),
        },
        "blessings": out,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Doc — focus on damage/proc-bearing effects (skip pure stat passives).
    import datetime
    lines = [
        "# Blessing proc formulas — game-truth (grade-by-grade)",
        "",
        f"_Generated by `tools/extract_blessing_procs.py` on {datetime.date.today().isoformat()}_",
        "",
        f"All {len(out)} blessings, their authoritative proc skill, and each effect's",
        "`MultiplierFormula` with the ascend grades it applies to. Source: game-truth",
        "`blessings.json` skill link + `skills_all.json` formulas.",
        "",
        "## Legendary blessings (proc-bearing)",
        "",
    ]
    for b in [x for x in out if x["rarity"] == "Legendary"]:
        ui = f" — UI: **{b['ui_name']}**" if b.get("ui_name") else ""
        lines.append(f"### {b['blessing_code_id']} ({b['divinity']}){ui}")
        for p in b["proc_skills"]:
            if p.get("missing"):
                lines.append(f"- skill {p['skill_id']} — _not in skills_all_")
                continue
            lines.append(f"- **skill {p['skill_id']}** ({p['skill_name']}):")
            # Collapse duplicate (kind, formula) across grades.
            seen = {}
            for e in p["effects"]:
                key = (e["kind"], e["formula"], e["target"])
                seen.setdefault(key, set()).update(e["grades"])
            for (kind, formula, target), grades in seen.items():
                g = f" grades {sorted(grades)}" if grades else ""
                lines.append(f"  - `{kind}` {formula or '(no formula)'} → {target}{g}")
        lines.append("")

    OUT_DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON}  ({len(out)} blessings)")
    print(f"Wrote {OUT_DOC}")
    print()
    legendary = [x for x in out if x["rarity"] == "Legendary"]
    print(f"Legendary blessings with proc skills: {len(legendary)}")
    for b in legendary:
        sids = [p["skill_id"] for p in b["proc_skills"]]
        print(f"  {b['blessing']:24s} -> {sids}")


if __name__ == "__main__":
    main()
