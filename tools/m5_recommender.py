"""Milestone 5 — Per-location team recommender (prototype).

Ties the M5 substrate together: given the OWNED roster + a location, assemble
a 5-hero team that covers the location's required synergy axes, ranked by a
score that blends:
    - synergy coverage (game-truth provides/needs from m5_synergy.jsonl)
    - HH per-location rating (data/hh/parsed/tierlist.json — ADDITIVE signal
      per CLAUDE.md, never authoritative; the game wins on any conflict)

Location requirement profiles encode what a good team NEEDS there. They are
grounded where possible:
    - ACC floors derived from boss RES in data/static/alliance_bosses.json
    - control debuffs (Stun/Freeze/Provoke) marked useless vs bosses immune
      to CC (CB / most dungeon bosses)
The rest is documented team-composition knowledge, clearly separated from the
game-truth synergy data it scores against.

CLI:
    python3 tools/m5_recommender.py --location cb
    python3 tools/m5_recommender.py --location dragon --size 5
    python3 tools/m5_recommender.py --list-locations
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"
SYNERGY = ROOT / "data" / "m5_synergy.jsonl"
HH_TIERLIST = ROOT / "data" / "hh" / "parsed" / "tierlist.json"
OWNED = ROOT / "heroes_all.json"

# Per-location requirement profile. `axes` = synergy provide-tags the team
# wants covered (weight = how important). `hh_key` = column in HH tierlist.
# `boss_immune_cc` = control debuffs do nothing (downweight CC providers).
LOCATION_PROFILES: dict[str, dict] = {
    "cb": {
        "label": "Clan Boss / Demon Lord",
        "hh_key": "clan_boss",
        "boss_immune_cc": True,
        "axes": {
            "team_buff:Block Damage": 5,
            "team_buff:Unkillable": 5,
            "team_buff:Shield": 3,
            "enemy_debuff:Decrease DEF": 4,
            "enemy_debuff:Weaken": 4,
            "enemy_debuff:Decrease ATK": 3,
            "team_buff:Increase ATK": 2,
            "team_buff:Increase SPD": 2,
            "cleanse": 2,
            "heal": 2,
        },
    },
    "dragon": {
        "label": "Dragon (Dungeon)",
        "hh_key": "dragon",
        "boss_immune_cc": True,
        "axes": {
            "enemy_debuff:Decrease DEF": 5,
            "enemy_debuff:Weaken": 4,
            "enemy_debuff:Decrease ATK": 4,   # boss hits hard — mitigate
            "team_buff:Increase ATK": 3,
            "team_buff:Increase C. RATE": 2,
            "team_buff:Increase C. DMG": 2,
            "heal": 2,
            "cleanse": 1,
        },
    },
    "spider": {
        "label": "Spider's Den (Dungeon)",
        "hh_key": "spider",
        "boss_immune_cc": True,
        "axes": {
            "enemy_debuff:Decrease DEF": 4,
            "team_buff:Counterattack": 4,     # spiderlings → counter value
            "team_buff:Increase ATK": 3,
            "team_buff:Ally Protection": 3,
            "heal": 3,
            "team_buff:Reflect Damage": 2,
        },
    },
    "fire_knight": {
        "label": "Fire Knight (Dungeon)",
        "hh_key": "fire_knight",
        "boss_immune_cc": True,
        "axes": {
            "enemy_debuff:Decrease DEF": 4,
            "team_buff:Increase ATK": 3,
            "team_buff:Increase SPD": 3,      # shield-break race needs hits
            "enemy_debuff:Decrease SPD": 2,
            "team_buff:Counterattack": 3,     # extra hits chip the shield
            "heal": 2,
        },
    },
    "ice_golem": {
        "label": "Ice Golem (Dungeon)",
        "hh_key": "ice_golem",
        "boss_immune_cc": True,
        "axes": {
            "enemy_debuff:Decrease DEF": 4,
            "enemy_debuff:Decrease ATK": 3,
            "team_buff:Increase ATK": 3,
            "heal": 3,
            "cleanse": 2,
        },
    },
    "hydra": {
        "label": "Hydra",
        "hh_key": "hydra",
        "boss_immune_cc": True,
        "axes": {
            "dot:Poison": 4,
            "dot:HP Burn": 3,
            "dot_detonate": 3,
            "enemy_debuff:Decrease DEF": 4,
            "enemy_debuff:Weaken": 3,
            "team_buff:Block Damage": 3,
            "heal": 3,
            "cleanse": 2,
        },
    },
    "chimera": {
        "label": "Chimera",
        "hh_key": "chimera",
        "boss_immune_cc": True,
        "axes": {
            "enemy_debuff:Decrease DEF": 4,
            "enemy_debuff:Weaken": 3,
            "team_buff:Block Damage": 3,
            "team_buff:Increase ATK": 3,
            "heal": 3,
            "cleanse": 3,                      # chimera applies nasty debuffs
        },
    },
    "arena": {
        "label": "Classic Arena (PVP)",
        "hh_key": "overall_user",
        "boss_immune_cc": False,              # CC WORKS in PVP
        "axes": {
            "team_buff:Increase SPD": 5,      # speed-lead + nuke
            "enemy_debuff:Decrease SPD": 4,
            "enemy_debuff:Stun": 4,
            "enemy_debuff:Freeze": 3,
            "team_buff:Increase ATK": 3,
            "team_buff:Increase C. DMG": 3,
            "team_buff:Block Damage": 2,
        },
    },
}


# Map recommender location → stage area in stage_stat_targets.json, so the
# ACC floor (game-truth boss RES) can be surfaced per recommendation.
LOCATION_TO_STAGE_AREA = {
    "cb": "AllianceBoss", "dragon": "Dungeon", "spider": "Dungeon",
    "fire_knight": "Dungeon", "ice_golem": "Dungeon",
    "hydra": "Hydra", "chimera": "Chimera", "arena": None,
}
STAT_TARGETS = STATIC / "stage_stat_targets.json"


def _acc_floor_for(location: str) -> int | None:
    """Max ACC floor (effective boss RES) across the location's stages."""
    area = LOCATION_TO_STAGE_AREA.get(location)
    if not area or not STAT_TARGETS.exists():
        return None
    data = json.loads(STAT_TARGETS.read_text(encoding="utf-8"))
    floors = [r["acc_floor"] for r in data.get("stages", [])
              if r.get("area") == area and r.get("acc_floor")]
    return max(floors) if floors else None


def _load_synergy() -> dict[str, dict]:
    recs = {}
    with SYNERGY.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            recs[r["name"]] = r
    return recs


def _load_hh() -> dict[str, dict]:
    raw = json.loads(HH_TIERLIST.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else (raw.get("champions") or [])
    # Key by lowercased name; HH may list multiple forms — keep highest overall.
    out: dict[str, dict] = {}
    for r in items:
        nm = (r.get("name") or "").strip()
        if not nm:
            continue
        key = nm.lower()
        if key not in out or (r.get("overall_user") or 0) > (out[key].get("overall_user") or 0):
            out[key] = r
    return out


def _load_owned() -> list[dict]:
    raw = json.loads(OWNED.read_text(encoding="utf-8"))
    heroes = raw.get("heroes", raw) if isinstance(raw, dict) else raw
    # Dedup by name, keep highest grade*level as the "best copy".
    best: dict[str, dict] = {}
    for h in heroes:
        nm = h.get("name")
        if not nm:
            continue
        score = (h.get("grade", 0) or 0) * 100 + (h.get("level", 0) or 0)
        if nm not in best or score > best[nm]["_score"]:
            h = dict(h)
            h["_score"] = score
            best[nm] = h
    return list(best.values())


def recommend(location: str, size: int = 5, pool: str = "owned") -> dict:
    prof = LOCATION_PROFILES[location]
    syn = _load_synergy()
    hh = _load_hh()
    axes = prof["axes"]
    hh_key = prof["hh_key"]

    # Build candidate list.
    if pool == "owned":
        owned = _load_owned()
        cand_names = [h["name"] for h in owned if h["name"] in syn]
    else:
        cand_names = list(syn.keys())

    def hh_rating(name: str) -> float:
        row = hh.get(name.lower())
        if not row:
            return 0.0
        v = row.get(hh_key)
        return float(v) if isinstance(v, (int, float)) else 0.0

    def base_score(name: str) -> float:
        """Standalone hero quality for this location: HH rating (0-5)."""
        return hh_rating(name)

    # Greedy: repeatedly add the hero that maximizes
    #   marginal axis coverage (weighted, with diminishing returns) + HH rating.
    chosen: list[str] = []
    covered: dict[str, int] = {}  # axis -> how many providers already chosen

    def marginal(name: str) -> float:
        r = syn[name]
        provides = set(r["provides"])
        gain = 0.0
        for axis, w in axes.items():
            if axis in provides:
                # diminishing returns: first provider full weight, 2nd half, etc.
                already = covered.get(axis, 0)
                gain += w / (already + 1)
        # HH rating contributes on a comparable scale (0-5 → ×1.5 so a
        # 5-star hero ≈ one strong axis). Game-truth synergy dominates.
        return gain + base_score(name) * 1.5

    while len(chosen) < size and cand_names:
        best_name = max(cand_names, key=marginal)
        chosen.append(best_name)
        cand_names.remove(best_name)
        for axis in axes:
            if axis in set(syn[best_name]["provides"]):
                covered[axis] = covered.get(axis, 0) + 1

    # Coverage report
    coverage = {axis: covered.get(axis, 0) for axis in axes}
    uncovered = [a for a, n in coverage.items() if n == 0]

    detail = []
    for name in chosen:
        r = syn[name]
        covers = [a for a in axes if a in set(r["provides"])]
        detail.append({
            "name": name,
            "element": r["element"],
            "role": r["synergy_role"],
            "hh_rating": hh_rating(name),
            "covers_axes": covers,
        })

    return {
        "location": location,
        "label": prof["label"],
        "team": chosen,
        "detail": detail,
        "axis_coverage": coverage,
        "uncovered_axes": uncovered,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--location", help="location code (see --list-locations)")
    ap.add_argument("--size", type=int, default=5, help="team size (default 5)")
    ap.add_argument("--pool", choices=["owned", "all"], default="owned",
                    help="'owned' (your roster) or 'all' (whole game)")
    ap.add_argument("--list-locations", action="store_true")
    ap.add_argument("--builds", action="store_true",
                    help="also print per-hero mastery/blessing/stat build for each pick")
    args = ap.parse_args()

    if args.list_locations or not args.location:
        print("Locations:")
        for code, p in LOCATION_PROFILES.items():
            print(f"  {code:12s} — {p['label']}")
        return

    if args.location not in LOCATION_PROFILES:
        print(f"Unknown location '{args.location}'. Use --list-locations.")
        return

    res = recommend(args.location, size=args.size, pool=args.pool)
    print(f"=== Recommended team for {res['label']} ({args.pool} pool) ===\n")
    acc_floor = _acc_floor_for(args.location)
    if acc_floor:
        print(f"  [stat target] debuffers need ACC >= {acc_floor} "
              f"(game-truth effective boss RES) to land at 100% of skill base chance\n")
    for d in res["detail"]:
        covers = ", ".join(a.split(":")[-1] for a in d["covers_axes"]) or "(filler)"
        print(f"  {d['name']:24s} [{d['role']:14s}] HH={d['hh_rating']:.1f}  covers: {covers}")
    print()
    print("Axis coverage:")
    for axis, n in res["axis_coverage"].items():
        mark = "[x]" if n else "[ ]"
        print(f"  {mark} {axis:32s} x{n}")
    if res["uncovered_axes"]:
        print()
        print("UNCOVERED (roster gap for this location):")
        for a in res["uncovered_axes"]:
            print(f"  - {a}")

    if args.builds:
        # Per-hero build (masteries/blessing/stats) from m5_build_recommender.
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "m5_build_recommender", ROOT / "tools" / "m5_build_recommender.py")
        brmod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(brmod)
        syn = brmod._load_synergy()
        mrel = brmod._load_mastery_relevance()
        brel = brmod._load_blessing_relevance()
        print()
        print("=== Per-hero builds ===")
        for name in res["team"]:
            hero = syn.get(name.lower())
            if not hero:
                continue
            by_tree = brmod.recommend_masteries(hero, args.location, mrel)
            bl = brmod.recommend_blessing(hero, args.location, brel)
            masts = "; ".join(
                f"{t}: {', '.join(p['name'] for p in by_tree[t])}"
                for t in ("Attack", "Defence", "Support") if by_tree.get(t))
            print(f"\n  {name}:")
            print(f"    masteries: {masts}")
            print(f"    blessing:  {', '.join(bl) if bl else '(role-standard)'}")
            for s in brmod.recommend_stats(hero, args.location):
                print(f"    stat: {s}")


if __name__ == "__main__":
    main()
