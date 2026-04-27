#!/usr/bin/env python3
"""
Artifact gap analysis — what gear should you farm next?

Aggregates demand across all owned heroes who score above a threshold in each
game area (per HellHades tierlist), using HH's per-hero set/stat
recommendations. Compares to inventory, surfaces gaps by:

  - SET (which sets are under-supplied, and for which areas)
  - PRIMARY STAT × SLOT (e.g. SPD-Boots, CD-Gloves)
  - SUBSTAT (which substats are scarce)

Usage:
    python3 tools/gear_gap_analysis.py                       # all areas, top gaps
    python3 tools/gear_gap_analysis.py --threshold 4.5       # tighter filter
    python3 tools/gear_gap_analysis.py --area clan_boss      # one area
    python3 tools/gear_gap_analysis.py --top 20 --format json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

from gear_constants import SET_NAMES, STAT_NAMES, SLOT_NAMES  # noqa: E402

HEROES_PATH = PROJECT_ROOT / "heroes_all.json"
ARTIFACTS_PATH = PROJECT_ROOT / "all_artifacts.json"
HH_CHAMPS_PATH = PROJECT_ROOT / "data" / "hh" / "parsed" / "champions.json"
HH_TIERLIST_PATH = PROJECT_ROOT / "data" / "hh" / "parsed" / "tierlist.json"
DUNGEON_DROPS_PATH = PROJECT_ROOT / "data" / "dungeon_drops.json"

# Game's RegionTypeId → friendly dungeon label (only the dungeons users farm
# for gear). Drives the "what to farm" priority section. Story regions and
# faction wars are filtered out — they're not gear farms.
DUNGEON_LABELS = {
    "DragonsLair":     "Dragon's Lair",
    "IceGolemCave":    "Ice Golem Peak",
    "FireGolemCave":   "Fire Knight Castle",
    "SpiderCave":      "Spider's Den",
    "EventDungeon":    "Event Dungeon",
}

# Areas we report on. Most use HH's `pve_*` build; arena uses `pvp_*`.
PVE_AREAS = [
    "clan_boss", "hydra", "dragon", "spider", "fire_knight", "ice_golem",
    "iron_twins", "sand_devil", "kuldath", "agreth", "borgoth",
]
PVP_AREAS = ["arena_rating"]
ALL_AREAS = PVE_AREAS + PVP_AREAS

# Heuristic: which slots a primary stat goes on. Helmet/Chest/Gloves/Boots are
# the "stat-bearing" slots; ring/amulet/banner have fixed primaries (HP/ATK/DEF
# variations). We assign primary-stat demand only to slots that allow choice.
PRIMARY_SLOT_MAP = {
    "SPD":  4,   # Boots
    "CR":   3,   # Gloves
    "CD":   3,   # Gloves
    "ACC":  9,   # Banner
    "RES":  9,   # Banner
    "HP%":  2,   # Chest
    "DEF%": 2,   # Chest
    "ATK%": 2,   # Chest
}

# Aliases between HH's stat strings and our internal stat-id names.
# is_flat reflects the *primary stat* convention in inventory:
#   SPD/ACC/RES primaries are flat; CR/CD primaries are %; HP/ATK/DEF have both.
STAT_ALIAS = {
    "SPD": ("SPD", True), "CR": ("CR", False), "CD": ("CD", False),
    "ACC": ("ACC", True), "RES": ("RES", True),
    "HP%": ("HP", False), "ATK%": ("ATK", False), "DEF%": ("DEF", False),
    "HP": ("HP", True), "ATK": ("ATK", True), "DEF": ("DEF", True),
}


def _norm(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _set_name_to_id() -> dict[str, int]:
    """Lowercased HH set name → set_id. Use first id if duplicates exist."""
    out = {}
    for sid, sname in SET_NAMES.items():
        key = sname.lower()
        out.setdefault(key, sid)
        # also accept space-stripped variants
        out.setdefault(key.replace(" ", ""), sid)
    return out


def _stat_name_to_id(stat_alias: str) -> tuple[int | None, bool]:
    """HH stat string ('SPD', 'HP%', 'ACC') → (stat_id, is_flat)."""
    pair = STAT_ALIAS.get(stat_alias.upper())
    if not pair:
        return None, False
    base, is_flat = pair
    for sid, name in STAT_NAMES.items():
        if name.upper() == base.upper():
            return sid, is_flat
    return None, False


def _parse_csv(s: str) -> list[str]:
    return [t.strip() for t in (s or "").split(",") if t.strip()]


def load_roster() -> dict[str, dict]:
    """Owned heroes keyed by normalized name (max grade per name)."""
    if not HEROES_PATH.exists():
        return {}
    data = _load_json(HEROES_PATH)
    heroes = data.get("heroes", []) if isinstance(data, dict) else data
    by_name = {}
    for h in heroes:
        nm = h.get("name") or ""
        key = _norm(nm)
        if not key:
            continue
        prev = by_name.get(key)
        cur = (h.get("grade", 0), h.get("level", 0), h.get("empower", 0))
        if not prev or cur > (prev.get("grade", 0), prev.get("level", 0), prev.get("empower", 0)):
            by_name[key] = h
    return by_name


def load_hh_lookup() -> tuple[dict[str, dict], dict[str, dict]]:
    """Return (champions_by_norm_name, tierlist_by_norm_name)."""
    champs = _load_json(HH_CHAMPS_PATH) if HH_CHAMPS_PATH.exists() else []
    tier = _load_json(HH_TIERLIST_PATH) if HH_TIERLIST_PATH.exists() else []
    return ({_norm(c.get("name", "")): c for c in champs},
            {_norm(t.get("name", "")): t for t in tier})


def _rating(t: dict | None, area: str) -> float:
    if not t:
        return 0.0
    v = t.get(area)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def viable_heroes(roster, champs, tierlist, area: str, threshold: float) -> list[dict]:
    """List of {name, hh_champ, rating} for owned heroes scoring >= threshold in area."""
    out = []
    for nm, hero in roster.items():
        tl = tierlist.get(nm)
        rating = _rating(tl, area)
        if rating < threshold:
            continue
        ch = champs.get(nm)
        if not ch:
            continue
        out.append({"name": hero.get("name"), "rating": rating, "champ": ch})
    out.sort(key=lambda r: -r["rating"])
    return out


def hero_demand(champ: dict, area: str, max_sets: int = 2) -> dict:
    """Per-hero demand vector for one area.

    Returns {sets: [(set_id, weight)], primaries: [(slot, stat_id, is_flat)],
              substats: [stat_id]}.
    Weight on sets is decreasing — top set gets 1.0, runner-up 0.5, etc.
    """
    is_pvp = area in PVP_AREAS
    set_field = "pvp_sets" if is_pvp else "pve_sets"
    stat_field = "pvp_stats" if is_pvp else "pve_stats"

    set_n2i = _set_name_to_id()
    sets_demand = []
    for i, sn in enumerate(_parse_csv(champ.get(set_field) or "")[:max_sets]):
        sid = set_n2i.get(sn.lower()) or set_n2i.get(sn.lower().replace(" ", ""))
        if sid is None:
            continue
        weight = 1.0 if i == 0 else 0.5 if i == 1 else 0.25
        sets_demand.append((sid, weight))

    stats = _parse_csv(champ.get(stat_field) or "")
    primaries = []
    substats = []
    for s in stats:
        sid, is_flat = _stat_name_to_id(s)
        if sid is None:
            continue
        slot = PRIMARY_SLOT_MAP.get(s.upper())
        if slot:
            primaries.append((slot, sid, is_flat))
        substats.append(sid)
    return {"sets": sets_demand, "primaries": primaries, "substats": substats}


def aggregate_demand(roster, champs, tierlist, areas: Iterable[str], threshold: float):
    """Per-hero demand summed once per hero, with per-area attribution.

    Each hero contributes their gear demand once (gear is shared across areas).
    Areas a hero is viable in are tagged so we can show "this set is needed
    most for X area" without double-counting.

    Returns {
      sets: {set_id: {total: weight_sum, areas: {area: weight_sum}}},
      primaries: {(slot,stat,flat): {total: count, areas: {area: count}}},
      substats: {stat_id: {total: count, areas: {area: count}}},
      viable_per_area: {area: int},
      unique_viable_heroes: int,
    }
    """
    areas = list(areas)
    # Map: hero_norm_name -> list of areas they're viable in
    hero_areas: dict[str, list[str]] = defaultdict(list)
    viable_per_area: dict[str, int] = {}
    for area in areas:
        v = viable_heroes(roster, champs, tierlist, area, threshold)
        viable_per_area[area] = len(v)
        for vh in v:
            hero_areas[_norm(vh["name"])].append(area)

    sets_acc: dict[int, dict] = defaultdict(lambda: {"total": 0.0, "areas": defaultdict(float)})
    prim_acc: dict[tuple, dict] = defaultdict(lambda: {"total": 0, "areas": defaultdict(int)})
    sub_acc: dict[int, dict] = defaultdict(lambda: {"total": 0, "areas": defaultdict(int)})

    for hero_norm, hero_areas_list in hero_areas.items():
        ch = champs.get(hero_norm)
        if not ch:
            continue
        # Use PvE recs unless the hero is *only* viable in PvP areas.
        primary_area = hero_areas_list[0]
        d = hero_demand(ch, primary_area)
        # For attribution, distribute weight equally across the hero's viable areas.
        share = 1.0 / len(hero_areas_list)
        for sid, weight in d["sets"]:
            sets_acc[sid]["total"] += weight
            for a in hero_areas_list:
                sets_acc[sid]["areas"][a] += weight * share
        for slot, sid, is_flat in d["primaries"]:
            prim_acc[(slot, sid, is_flat)]["total"] += 1
            for a in hero_areas_list:
                prim_acc[(slot, sid, is_flat)]["areas"][a] += share
        for sid in d["substats"]:
            sub_acc[sid]["total"] += 1
            for a in hero_areas_list:
                sub_acc[sid]["areas"][a] += share

    return {
        "sets": sets_acc,
        "primaries": prim_acc,
        "substats": sub_acc,
        "viable_per_area": viable_per_area,
        "unique_viable_heroes": len(hero_areas),
    }


def inventory_supply(min_rarity: int = 4, min_rank: int = 4):
    """Count Epic+ rank-4+ artifacts by set / primary-slot-stat / substat.

    Most low-rarity gear isn't worth using; default Epic+ rank4+.
    """
    arts = _load_json(ARTIFACTS_PATH).get("artifacts", []) if ARTIFACTS_PATH.exists() else []
    sets = defaultdict(int)
    primaries = defaultdict(int)   # (slot, stat_id, is_flat) -> count
    substats = defaultdict(int)    # stat_id -> count
    for a in arts:
        if (a.get("rarity") or 0) < min_rarity:
            continue
        if (a.get("rank") or 0) < min_rank:
            continue
        sid = a.get("set", 0)
        if sid:
            sets[sid] += 1
        prim = a.get("primary") or {}
        ps = prim.get("stat")
        if ps:
            primaries[(a.get("slot", 0), ps, bool(prim.get("flat")))] += 1
        for sub in a.get("substats") or []:
            ss = sub.get("stat")
            if ss:
                substats[ss] += 1
    return {"sets": dict(sets), "primaries": dict(primaries), "substats": dict(substats),
            "total_considered": sum(1 for a in arts
                                   if (a.get("rarity") or 0) >= min_rarity
                                   and (a.get("rank") or 0) >= min_rank)}


def _stat_label(stat_id: int, is_flat: bool) -> str:
    base = STAT_NAMES.get(stat_id, f"s{stat_id}")
    # SPD/ACC/RES are always written without %; CR/CD always with %.
    if base in ("SPD", "ACC", "RES"):
        return base
    if base in ("CR", "CD"):
        return f"{base}%"
    return base if is_flat else f"{base}%"


def build_gap_report(threshold: float = 4.0,
                     min_rarity: int = 4, min_rank: int = 4,
                     areas: Iterable[str] | None = None,
                     top: int = 15):
    areas = list(areas or ALL_AREAS)
    roster = load_roster()
    champs, tierlist = load_hh_lookup()
    demand = aggregate_demand(roster, champs, tierlist, areas, threshold)
    supply = inventory_supply(min_rarity, min_rank)

    # Set gaps.
    set_rows = []
    for sid, info in demand["sets"].items():
        d = info["total"]
        s = supply["sets"].get(sid, 0)
        top_areas = sorted(info["areas"].items(), key=lambda kv: -kv[1])[:3]
        set_rows.append({
            "set_id": sid,
            "set_name": SET_NAMES.get(sid, f"set{sid}"),
            "demand": round(d, 1),
            "supply": s,
            "gap": round(s - d, 1),
            "top_areas": [{"area": a, "demand": round(v, 1)} for a, v in top_areas],
        })
    set_rows.sort(key=lambda r: r["gap"])

    # Primary-stat x slot gaps.
    primary_rows = []
    for (slot, sid, is_flat), info in demand["primaries"].items():
        d = info["total"]
        s = supply["primaries"].get((slot, sid, is_flat), 0)
        top_areas = sorted(info["areas"].items(), key=lambda kv: -kv[1])[:3]
        primary_rows.append({
            "slot": slot,
            "slot_name": SLOT_NAMES.get(slot, f"slot{slot}"),
            "stat": _stat_label(sid, is_flat),
            "demand": d,
            "supply": s,
            "gap": s - d,
            "top_areas": [{"area": a, "demand": round(v, 1)} for a, v in top_areas],
        })
    primary_rows.sort(key=lambda r: r["gap"])

    # Substat gaps.
    sub_rows = []
    for sid, info in demand["substats"].items():
        d = info["total"]
        s = supply["substats"].get(sid, 0)
        top_areas = sorted(info["areas"].items(), key=lambda kv: -kv[1])[:3]
        sub_rows.append({
            "stat_id": sid,
            "stat": STAT_NAMES.get(sid, f"s{sid}"),
            "demand": d,
            "supply": s,
            "gap": s - d,
            "top_areas": [{"area": a, "demand": round(v, 1)} for a, v in top_areas],
        })
    sub_rows.sort(key=lambda r: r["gap"])

    # Per-dungeon farming priority: for each known farm, sum the absolute
    # value of negative gaps for sets that dungeon drops, plus a bonus for
    # accessory gaps if the dungeon drops accessories. Higher = better target.
    dungeon_rows = build_dungeon_priority(set_rows, primary_rows)

    return {
        "threshold": threshold,
        "min_rarity": min_rarity,
        "min_rank": min_rank,
        "areas": areas,
        "viable_per_area": demand["viable_per_area"],
        "unique_viable_heroes": demand["unique_viable_heroes"],
        "inventory_total": supply["total_considered"],
        "sets": set_rows[:top],
        "primaries": primary_rows[:top],
        "substats": sub_rows[:top],
        "dungeons": dungeon_rows,
    }


def load_dungeon_drops() -> dict:
    """Return {region_name: {id, sets, accessory_kinds, difficulties}}.

    Schema in data/dungeon_drops.json is per-difficulty; this flattens to a
    union of sets/accessories across difficulties (you farm whichever band
    makes sense), while keeping per-difficulty detail under "difficulties".

    Empty dict if data/dungeon_drops.json is missing — callers handle gracefully.
    """
    if not DUNGEON_DROPS_PATH.exists():
        return {}
    raw = _load_json(DUNGEON_DROPS_PATH)
    out = {}
    for name, info in (raw.get("regions") or {}).items():
        # New schema: by_difficulty=[{difficulty, set_drops, accessory_kinds, ...}]
        # Old schema: set_drops dict at top level. Support both.
        difficulties = info.get("by_difficulty") or []
        sets_union: set[int] = set()
        acc_union: set[int] = set()
        diff_detail = []
        if difficulties:
            for d in difficulties:
                sids = [int(k) for k in (d.get("set_drops") or {}).keys()]
                sets_union.update(sids)
                acc_union.update(d.get("accessory_kinds") or [])
                diff_detail.append({
                    "difficulty": d.get("difficulty"),
                    "stages": d.get("stages", 0),
                    "sets": sorted(sids),
                    "accessory_kinds": list(d.get("accessory_kinds") or []),
                })
        else:
            # Old flat schema fallback.
            sets_union = {int(k) for k in (info.get("set_drops") or {}).keys()}
            acc_union = set(info.get("accessory_kinds") or [])
        out[name] = {
            "id": info.get("id"),
            "sets": sorted(sets_union),
            "accessory_kinds": sorted(acc_union),
            "difficulties": diff_detail,
        }
    return out


def build_dungeon_priority(set_rows: list, primary_rows: list) -> list:
    """Rank dungeons by gap-points they close.

    For each dungeon in DUNGEON_LABELS, sum |gap| for under-supplied sets it
    drops. Dungeons that drop accessories (rings/amulets/banners) also pick
    up a bonus equal to the sum of |gap| for primary-stat rows whose slot
    matches an accessory slot (7=Ring, 8=Amulet, 9=Banner).
    """
    drops = load_dungeon_drops()
    if not drops:
        return []

    set_gap_by_id = {r["set_id"]: r for r in set_rows}
    # Primary gaps grouped by slot id, summed for accessory bonus.
    accessory_gap_by_slot: dict[int, float] = defaultdict(float)
    accessory_top_by_slot: dict[int, list] = defaultdict(list)
    for r in primary_rows:
        if r["gap"] < 0 and r["slot"] in (7, 8, 9):
            accessory_gap_by_slot[r["slot"]] += abs(r["gap"])
            accessory_top_by_slot[r["slot"]].append(r)

    out = []
    for region_name, info in drops.items():
        if region_name not in DUNGEON_LABELS:
            continue
        label = DUNGEON_LABELS[region_name]
        gap_sets = []
        score = 0.0
        for sid in info["sets"]:
            row = set_gap_by_id.get(sid)
            if not row or row["gap"] >= 0:
                continue
            gap_sets.append({"set_id": sid, "set_name": row["set_name"], "gap": row["gap"]})
            score += abs(row["gap"])
        gap_sets.sort(key=lambda x: x["gap"])

        accessory_bonus = 0.0
        accessory_gaps = []
        for slot in info["accessory_kinds"]:
            if slot in accessory_gap_by_slot:
                accessory_bonus += accessory_gap_by_slot[slot]
                for r in accessory_top_by_slot[slot]:
                    accessory_gaps.append({
                        "slot_name": r["slot_name"], "stat": r["stat"], "gap": r["gap"]
                    })
        score += accessory_bonus
        if score <= 0 and not info["accessory_kinds"]:
            continue
        out.append({
            "region": region_name,
            "label": label,
            "id": info["id"],
            "difficulties": info.get("difficulties") or [],
            "score": round(score, 1),
            "gap_sets": gap_sets,
            "accessory_kinds": info["accessory_kinds"],
            "accessory_gaps": accessory_gaps,
            "accessory_bonus": round(accessory_bonus, 1),
        })
    out.sort(key=lambda r: -r["score"])
    return out


def render_text(report) -> str:
    lines = []
    lines.append("=== Artifact Gap Analysis ===")
    lines.append(f"Filter: heroes rated >={report['threshold']} per area; "
                 f"inventory: rarity >={report['min_rarity']}, rank >={report['min_rank']} "
                 f"({report['inventory_total']} pieces considered)")
    lines.append(f"Unique viable heroes (in any area): {report['unique_viable_heroes']}")
    lines.append("")
    lines.append("Viable heroes per area (HH rating >= threshold):")
    for area, n in report["viable_per_area"].items():
        lines.append(f"  {area:18s} {n:3d}")
    lines.append("")
    lines.append("--- SET GAPS (most under-supplied first) ---")
    lines.append(f"{'Set':<20} {'Demand':>7} {'Supply':>7} {'Gap':>7}  Top areas")
    for r in report["sets"]:
        ta = ", ".join(f"{a['area']}:{a['demand']}" for a in r["top_areas"])
        lines.append(f"{r['set_name']:<20} {r['demand']:>7} {r['supply']:>7} {r['gap']:>+7}  {ta}")
    lines.append("")
    lines.append("--- PRIMARY STAT x SLOT GAPS ---")
    lines.append(f"{'Slot':<8} {'Stat':<6} {'Demand':>7} {'Supply':>7} {'Gap':>7}  Top areas")
    for r in report["primaries"]:
        ta = ", ".join(f"{a['area']}:{a['demand']}" for a in r["top_areas"])
        lines.append(f"{r['slot_name']:<8} {r['stat']:<6} {r['demand']:>7} {r['supply']:>7} {r['gap']:>+7}  {ta}")
    lines.append("")
    if report.get("dungeons"):
        lines.append("--- DUNGEON FARMING PRIORITY ---")
        lines.append(f"{'Dungeon':<22} {'Score':>6}  Closes")
        for d in report["dungeons"]:
            sets_str = ", ".join(f"{s['set_name']}({s['gap']:+g})" for s in d["gap_sets"][:6])
            acc_str = ""
            if d["accessory_bonus"] > 0:
                acc_str = f"  + accessories ({d['accessory_bonus']:.0f})"
            lines.append(f"{d['label']:<22} {d['score']:>6}  {sets_str}{acc_str}")
        lines.append("")
    lines.append("--- SUBSTAT GAPS ---")
    lines.append(f"{'Stat':<6} {'Demand':>7} {'Supply':>7} {'Gap':>7}  Top areas")
    for r in report["substats"]:
        ta = ", ".join(f"{a['area']}:{a['demand']}" for a in r["top_areas"])
        lines.append(f"{r['stat']:<6} {r['demand']:>7} {r['supply']:>7} {r['gap']:>+7}  {ta}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--threshold", type=float, default=4.0,
                   help="HH rating threshold for 'viable in area' (default 4.0)")
    p.add_argument("--min-rarity", type=int, default=4,
                   help="Inventory: minimum artifact rarity (1=Common…5=Legendary, default 4=Epic)")
    p.add_argument("--min-rank", type=int, default=4,
                   help="Inventory: minimum artifact rank/stars (default 4)")
    p.add_argument("--area", action="append", help="Restrict to one or more areas")
    p.add_argument("--top", type=int, default=15, help="Top-N rows per section (default 15)")
    p.add_argument("--format", choices=("text", "json"), default="text")
    args = p.parse_args()

    rep = build_gap_report(
        threshold=args.threshold,
        min_rarity=args.min_rarity,
        min_rank=args.min_rank,
        areas=args.area or ALL_AREAS,
        top=args.top,
    )
    if args.format == "json":
        print(json.dumps(rep, indent=2))
    else:
        print(render_text(rep))


if __name__ == "__main__":
    main()
