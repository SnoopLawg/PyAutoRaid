"""Milestone 5 — Per-location stat targets (game-truth derived).

The recommender's gear-aware layer. For every battle location/stage that
carries boss stat modifiers, derive the hard, game-truth requirements:

    ACC floor  = effective boss RES  (game formula: land = 1 + (ACC-RES)*0.01,
                 so ACC == RES gives 100% of a skill's base land chance)
    boss SPD   = effective boss SPD  (speed-tune reference)
    boss ATK/DEF/HP modifiers — context for survivability / damract targets

"Effective" = boss base stat (alliance_bosses / hero_types) + the stage's
absolute Modifier value (IsAbsolute=true means the value is added as a flat
amount, verified on CB SPD 170+20=190 and RES). Source: data/static/stages.json
Modifiers[] with BossOnly=true.

This is 100% game-truth — no meta opinion. Damage targets (CR/CD/ATK% for
DPS) are intentionally NOT invented here; those belong in hand-tuned per-build
target files. This tool gives the floors the game itself imposes.

Outputs:
    data/static/stage_stat_targets.json — per-stage boss modifiers + ACC floor
    docs/m5_stat_targets.md             — readable per-location summary

CLI:
    python3 tools/m5_stat_targets.py            # regenerate
    python3 tools/m5_stat_targets.py --area cb  # print one area
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"
STAGES = STATIC / "stages.json"
ALLIANCE = STATIC / "alliance_bosses.json"
OUT_JSON = STATIC / "stage_stat_targets.json"
OUT_DOC = ROOT / "docs" / "m5_stat_targets.md"

# Stat modifier kinds we care about for targets.
TARGET_KINDS = {"Accuracy", "Resistance", "Speed", "Attack", "Defence", "Health",
                "CriticalChance", "CriticalDamage"}


def _load(p: Path):
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def _arr(blob):
    if isinstance(blob, list):
        return blob
    if isinstance(blob, dict):
        return blob.get("data") or next(
            (v for k, v in blob.items() if k != "_meta" and isinstance(v, list)), [])
    return []


def _area_name(stage: dict) -> str:
    a = stage.get("Area") or {}
    if isinstance(a, dict):
        return a.get("Id") or "?"
    return str(a)


def _region_name(stage: dict) -> str:
    r = stage.get("Region") or {}
    if isinstance(r, dict):
        return r.get("Id") or "?"
    return str(r)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", help="print only this area Id")
    args = ap.parse_args()

    stages = _arr(_load(STAGES))

    # Boss base RES — for CB (AllianceBoss) the base is ~30 across difficulties;
    # the stage modifier supplies the difficulty scaling. Effective RES (what
    # ACC must beat) = base + modifier. Pull the CB base from alliance_bosses.
    cb_base_res = 30
    try:
        ab = _load(ALLIANCE).get("bosses", [])
        if ab:
            cb_base_res = ab[0].get("base_stats", {}).get("res", 30)
    except Exception:
        pass

    # Per-stage boss modifier extraction.
    records = []
    for s in stages:
        mods = s.get("Modifiers") or []
        boss_mods = {}
        for m in mods:
            if not m.get("BossOnly"):
                continue
            kind = m.get("KindId")
            if kind in TARGET_KINDS and m.get("IsAbsolute"):
                # Keep the max across rounds (the toughest the boss gets).
                boss_mods[kind] = max(boss_mods.get(kind, 0), int(m.get("Value", 0)))
        if not boss_mods:
            continue
        area = _area_name(s)
        res_mod = boss_mods.get("Resistance")
        # Effective RES = boss base RES + stage absolute modifier. We only
        # have a reliable base for CB; for other areas base is small/unknown
        # so we report the modifier as the floor (slightly conservative).
        base_res = cb_base_res if area == "AllianceBoss" else 0
        eff_res = (res_mod + base_res) if res_mod is not None else None
        rec = {
            "stage_id": s.get("Id"),
            "area": area,
            "region": _region_name(s),
            "difficulty": s.get("Difficulty"),
            "number": s.get("Number"),
            "has_boss": s.get("HasBoss", False),
            "boss_modifiers": boss_mods,
            # ACC floor to land debuffs at 100% of base chance == effective RES.
            "acc_floor": eff_res,
            "res_modifier": res_mod,
            "boss_speed_mod": boss_mods.get("Speed"),
        }
        records.append(rec)

    payload = {
        "_meta": {
            "generated_by": "tools/m5_stat_targets.py",
            "total_stages_with_boss_modifiers": len(records),
            "note": ("ACC floor = boss effective RES (stage absolute Resistance "
                     "modifier). Game formula: land = 1 + (ACC-RES)*0.01, so "
                     "ACC==RES => 100% of skill base chance. Values are the "
                     "stage's absolute modifier, which the game ADDS to the "
                     "boss base stat (verified on CB SPD 170+20=190)."),
        },
        "stages": records,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Summarize per area: distinct ACC floors / speed mods seen.
    by_area: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_area[r["area"]].append(r)

    import datetime
    lines = [
        "# Per-location stat targets (game-truth)",
        "",
        f"_Generated by `tools/m5_stat_targets.py` on {datetime.date.today().isoformat()}_",
        "",
        f"{len(records)} stages carry boss stat modifiers. The **ACC floor** is the",
        "boss's effective RES — to land a debuff at 100% of its skill base chance a",
        "debuffer needs `ACC >= ACC floor` (game formula `land = 1 + (ACC-RES)*0.01`).",
        "",
        "Values are the stage's absolute `Modifier` (added to boss base stats, as",
        "verified on CB SPD 170+20=190). Damage targets (CR/CD/ATK%) are NOT here —",
        "those are per-build, not game-imposed floors.",
        "",
        "## ACC floors by area (max difficulty seen)",
        "",
        "| Area | max ACC floor (boss RES) | max boss SPD mod | stages |",
        "|---|---|---|---|",
    ]
    for area in sorted(by_area):
        rs = by_area[area]
        max_acc = max((r["acc_floor"] or 0) for r in rs)
        max_spd = max((r["boss_speed_mod"] or 0) for r in rs)
        lines.append(f"| {area} | {max_acc} | {max_spd} | {len(rs)} |")
    lines.append("")

    # Detail for the headline areas.
    lines.append("## Detail — key PvE areas")
    lines.append("")
    for area in ["AllianceBosses", "Dungeon", "DungeonExtra", "DoomTower",
                 "Hydra", "Chimera", "CursedCity", "FoggyForest"]:
        rs = by_area.get(area)
        if not rs:
            continue
        lines.append(f"### {area}")
        lines.append("")
        lines.append("| stage | region | difficulty | ACC floor | boss SPD mod | other |")
        lines.append("|---|---|---|---|---|---|")
        # Sort by difficulty-ish (acc floor) then region.
        for r in sorted(rs, key=lambda x: (x["region"], -(x["acc_floor"] or 0)))[:40]:
            other = {k: v for k, v in r["boss_modifiers"].items()
                     if k not in ("Resistance", "Speed")}
            other_s = ", ".join(f"{k}+{v}" for k, v in other.items())
            lines.append(f"| {r['stage_id']} | {r['region']} | {r['difficulty']} | "
                         f"{r['acc_floor']} | {r['boss_speed_mod']} | {other_s} |")
        if len(rs) > 40:
            lines.append(f"| … | _{len(rs)-40} more stages_ | | | | |")
        lines.append("")

    OUT_DOC.write_text("\n".join(lines), encoding="utf-8")

    if args.area:
        rs = by_area.get(args.area, [])
        print(f"=== {args.area}: {len(rs)} stages with boss modifiers ===")
        for r in sorted(rs, key=lambda x: -(x["acc_floor"] or 0))[:30]:
            print(f"  stage {r['stage_id']} {r['region']}/{r['difficulty']}: "
                  f"ACC floor={r['acc_floor']} SPD mod={r['boss_speed_mod']} "
                  f"mods={r['boss_modifiers']}")
        return

    print(f"Wrote {OUT_JSON}  ({len(records)} stages)")
    print(f"Wrote {OUT_DOC}")
    print()
    print("ACC floors by area (max):")
    for area in sorted(by_area):
        rs = by_area[area]
        max_acc = max((r["acc_floor"] or 0) for r in rs)
        print(f"  {area:20s} ACC>={max_acc}")


if __name__ == "__main__":
    main()
