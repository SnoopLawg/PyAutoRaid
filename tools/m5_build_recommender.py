"""Milestone 5 — Per-hero build recommender (masteries + blessing + stat focus).

The team recommender (`m5_recommender.py`) says WHICH heroes to bring. This
says HOW to build each one for a given location: which masteries to slot,
which blessing, and what stats to prioritize.

Grounding (game-truth) vs heuristic is kept explicit:
  - GAME-TRUTH inputs: the hero's actual kit (`data/m5_synergy.jsonl` provides/
    role, derived from skill descriptions), per-location mastery relevance
    (`data/static/mastery_relevance.json`), blessing relevance + proc formulas
    (`data/static/blessing_relevance.json` / `blessing_procs.json`), and ACC
    floors (`data/static/stage_stat_targets.json`).
  - HEURISTIC layer: rules mapping a kit profile -> recommended masteries/
    blessing/stats. These encode standard team-building knowledge and are
    clearly separated; the game wins on any conflict.

A mastery is only recommended if it is `relevant` (not `no_op`) at the target
location AND fits the hero's kit. Same for blessings.

CLI:
    python3 tools/m5_build_recommender.py --hero Venomage --location cb
    python3 tools/m5_build_recommender.py --hero Geomancer --location dragon
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"

# Named mastery IDs we reference in rules (subset; full set in mastery_relevance).
M = {
    "warmaster": 500161, "giant_slayer": 500163, "helmsmasher": 500162,
    "flawless_execution": 500164, "keen_strike": 500122, "methodical": 500151,
    "heart_of_glory": 500121, "grim_resolve": 500124, "single_out": 500131,
    "ruthless_ambush": 500134, "wrath_of_slain": 500142,
    "sniper": 500353, "master_hexer": 500354, "oppressor": 500363,
    "lore_of_steel": 500343, "lasting_gifts": 500351, "cycle_of_magic": 500342,
    "eagle_eye": 500364, "evil_eye": 500344, "spirit_haste": 500352,
    "iron_skin": 500261, "blastproof": 500221, "improved_parry": 500224,
    "bulwark": 500262, "retribution": 500253, "elixir_of_life": 500361,
    "healing_savior": 500331, "rapid_response": 500332, "arcane_celerity": 500334,
    "timely_intervention": 500362, "merciful_aid": 500341, "shieldbearer": 500322,
    "bring_it_down": 500141,
}
ID_TO_KEY = {v: k for k, v in M.items()}


# The team recommender uses fine-grained location codes (dragon, spider, ...)
# but mastery/blessing relevance is tagged by the coarse area code. Map the
# specific dungeon bosses to the shared `dungeon` relevance bucket.
LOC_TO_RELEVANCE = {
    "dragon": "dungeon", "spider": "dungeon", "fire_knight": "dungeon",
    "ice_golem": "dungeon", "minotaur": "dungeon",
}


def _rel_loc(location: str) -> str:
    return LOC_TO_RELEVANCE.get(location, location)


def _load_synergy() -> dict:
    out = {}
    with (ROOT / "data" / "m5_synergy.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            out[r["name"].lower()] = r
    return out


def _load_mastery_relevance() -> dict:
    raw = json.loads((STATIC / "mastery_relevance.json").read_text(encoding="utf-8"))
    return {m["id"]: m for m in raw["masteries"]}


def _load_blessing_relevance() -> list:
    raw = json.loads((STATIC / "blessing_relevance.json").read_text(encoding="utf-8"))
    return raw["blessings"]


def _load_valid_sets() -> set:
    raw = json.loads((STATIC / "artifact_sets.json").read_text(encoding="utf-8"))
    rows = next((v for k, v in raw.items() if k != "_meta" and isinstance(v, list)), [])
    return {r["set"] for r in rows}


_COMPUTED_COLS = ["base_computed", "artifact_bonus", "mastery_bonus",
                  "affinity_bonus", "classic_arena_bonus", "blessing_bonus",
                  "empower_bonus", "relic_bonus", "faction_guardians_bonus"]


def _load_computed_stats() -> dict:
    """name(lower) -> {stat: total} summed from the game's column breakdown.

    `hero_computed_stats.json` carries the GAME's own Total-Stats columns for
    the user's geared heroes; summing them gives the authoritative total stat
    (matches the in-game Total Stats screen). It is a cached snapshot of the
    live `/hero-computed-stats` mod endpoint — refresh full-roster coverage with:
        curl -s "http://localhost:6790/hero-computed-stats?min_grade=4" \
            -o hero_computed_stats.json
    Heroes absent from the snapshot simply get no readiness annotation.
    """
    p = ROOT / "hero_computed_stats.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    rows = raw.get("heroes", raw) if isinstance(raw, dict) else raw
    ha = {x["id"]: x["name"]
          for x in json.loads((ROOT / "heroes_all.json").read_text(encoding="utf-8"))["heroes"]}
    out = {}
    for r in rows:
        name = ha.get(r.get("id"))
        if not name:
            continue
        totals = {}
        for c in _COMPUTED_COLS:
            v = r.get(c) or {}
            if isinstance(v, dict):
                for stat, amt in v.items():
                    totals[stat] = totals.get(stat, 0) + (amt or 0)
        # keep the highest-stat copy if duplicate names (best geared)
        if name.lower() not in out or totals.get("ACC", 0) > out[name.lower()].get("ACC", 0):
            out[name.lower()] = totals
    return out


def _acc_floor(location: str) -> int | None:
    area = {"cb": "AllianceBoss", "dragon": "Dungeon", "spider": "Dungeon",
            "fire_knight": "Dungeon", "ice_golem": "Dungeon",
            "hydra": "Hydra", "chimera": "Chimera"}.get(location)
    p = STATIC / "stage_stat_targets.json"
    if not area or not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    floors = [r["acc_floor"] for r in data["stages"]
              if r.get("area") == area and r.get("acc_floor")]
    return max(floors) if floors else None


def recommend_masteries(hero: dict, location: str, mrel: dict) -> dict:
    """Return {tree: [mastery_ids]} recommended, filtered by location relevance."""
    provides = set(hero.get("provides", []))
    role = hero.get("synergy_role", "")
    game_role = hero.get("game_role", "")

    rloc = _rel_loc(location)

    def relevant(mid: int) -> bool:
        m = mrel.get(mid)
        if not m:
            return False
        return m["relevance"].get(rloc) in ("relevant", "stat_bonus")

    picks: list[int] = []
    is_attacker = game_role == "Attack" or role in ("attacker", "dot")
    is_debuffer = any(p.startswith("enemy_debuff:") for p in provides) or "dot" in role
    is_dot = any(p.startswith("dot:") for p in provides)
    is_support = role in ("support", "healer/support") or game_role == "Support"
    is_tank = game_role in ("Defense", "Health")

    # Offense tree
    if is_attacker:
        # WM for multi-hit/low-base, GS for high-base nukers — default WM.
        picks += [M["warmaster"], M["helmsmasher"], M["flawless_execution"],
                  M["keen_strike"]]
        picks += [M["bring_it_down"]]   # +6% vs higher-MAX-HP target (always true vs bosses)
        # First-cast / HP-condition damage where it applies broadly.
        picks += [M["ruthless_ambush"], M["single_out"]]
    # Debuff support tree
    if is_debuffer:
        picks += [M["sniper"], M["master_hexer"]]
        if is_dot:
            picks += [M["oppressor"]]   # TM per active debuff — huge for DoT stackers
    # Support / utility
    if is_support:
        picks += [M["lore_of_steel"], M["lasting_gifts"], M["cycle_of_magic"]]
        if "heal" in provides:
            picks += [M["healing_savior"], M["merciful_aid"]]
        if any(p.startswith("team_buff:Shield") for p in provides):
            picks += [M["shieldbearer"]]
    # Tank / defensive
    if is_tank:
        picks += [M["iron_skin"], M["blastproof"], M["improved_parry"],
                  M["bulwark"], M["retribution"], M["elixir_of_life"]]
    # ACC for debuffers who must land vs high-RES bosses
    if is_debuffer:
        picks += [M["eagle_eye"]]

    # Dedup, filter by location relevance, group by tree.
    seen = set()
    by_tree: dict[str, list] = {"Attack": [], "Defence": [], "Support": []}
    for mid in picks:
        if mid in seen or not relevant(mid):
            continue
        seen.add(mid)
        m = mrel.get(mid, {})
        by_tree.setdefault(m.get("tree", "?"), []).append(
            {"id": mid, "name": m.get("name", ID_TO_KEY.get(mid, str(mid)))})
    return by_tree


# Artifact set recommendations by kit role. The set BONUSES are game-truth
# (data/static/artifact_sets.json); the role->set mapping is standard
# team-building heuristic. Internal set code -> UI name for readability
# (set names differ from UI, like blessings — see artifact_relic_mechanics).
SET_UI_NAME = {
    "CriticalDamage": "Savage/Cruel (C.DMG)", "CriticalChance": "Crit Rate",
    "AttackPower": "Offense (ATK%)", "IgnoreDefense": "Stalwart-ish / IgnoreDef",
    "LifeDrain": "Lifesteal", "AttackAndCritRate": "Atk+CR",
    "AccuracyAndSpeed": "Perception (ACC+SPD)", "Accuracy": "Accuracy",
    "AttackSpeed": "Speed", "SpeedAndResistance": "Speed+RES",
    "Hp": "Life (HP%)", "Defense": "Defense", "Shield": "Shield",
    "Resistance": "Resistance", "HpAndHeal": "Immortal",
    "Counterattack": "Retaliation", "Stamina": "Relentless (TM)",
    "DotRate": "Toxic", "BlockDebuff": "Immunity",
    "ResistanceAndBlockDebuff": "Resist+Immunity",
    "UnkillableAndSpdAndCrDmg": "Frenzy/Unkillable-ish",
}


def recommend_sets(hero: dict, location: str, valid_sets: set) -> list:
    provides = set(hero.get("provides", []))
    role = hero.get("synergy_role", "")
    game_role = hero.get("game_role", "")
    is_attacker = game_role == "Attack" or role in ("attacker", "dot")
    is_debuffer = any(p.startswith("enemy_debuff:") for p in provides) or "dot" in role
    is_support = role in ("support", "healer/support") or game_role == "Support"
    is_tank = game_role in ("Defense", "Health")

    picks: list[str] = []
    # Debuffers/DoT carries lead with Speed + Accuracy (cadence + landing
    # matter most), then damage. Pure attackers lead with damage sets.
    if is_debuffer:
        picks += ["AttackSpeed", "AccuracyAndSpeed", "Accuracy"]
    if is_attacker:
        picks += ["CriticalDamage", "AttackPower", "CriticalChance",
                  "IgnoreDefense", "LifeDrain"]
    if is_support or is_tank:
        picks += ["AttackSpeed", "SpeedAndResistance", "Hp", "Defense",
                  "Resistance", "HpAndHeal", "Shield"]
    if location in ("arena", "tt"):
        picks = ["AttackSpeed", "CriticalDamage", "CriticalChance"] + picks
    # Dedup preserving order, keep only sets that exist in game data.
    # Returns INTERNAL codes (callers map to UI via SET_UI_NAME for display
    # and pass codes to recommend_farm for the drop-location lookup).
    seen, out = set(), []
    for s in picks:
        if s in seen or s not in valid_sets:
            continue
        seen.add(s)
        out.append(s)
    return out[:5]


# Region code -> readable farm location (named dungeons; RegionN = campaign).
FARM_REGION_NAME = {
    "DragonsLair": "Dragon's Lair", "IceGolemCave": "Ice Golem Peak",
    "FireGolemCave": "Fire Knight Castle", "SpiderCave": "Spider's Den",
    "MinotaurLabyrinth": "Minotaur", "EventDungeon": "Event Dungeon",
}


def _set_drop_regions() -> dict:
    """internal set name -> sorted list of readable drop locations (named
    dungeons first; campaign RegionN bucketed as 'Campaign')."""
    af = json.loads((STATIC / "artifact_sets.json").read_text(encoding="utf-8"))
    arows = next((v for k, v in af.items() if k != "_meta" and isinstance(v, list)), [])
    id_to_name = {r["id"]: r["set"] for r in arows}
    name_to_id = {r["set"]: r["id"] for r in arows}
    drops = json.loads((STATIC / "drops.json").read_text(encoding="utf-8")).get("regions", {})
    from collections import defaultdict
    id_to_regions = defaultdict(set)
    for rname, info in drops.items():
        for diff in info.get("by_difficulty", []):
            for sid in (diff.get("set_drops") or {}).keys():
                id_to_regions[int(sid)].add(rname)
    out = {}
    for sname, sid in name_to_id.items():
        locs = []
        for r in sorted(id_to_regions.get(sid, [])):
            if r in FARM_REGION_NAME:
                locs.append(FARM_REGION_NAME[r])
            elif "Campaign" not in locs:
                locs.append("Campaign")
        out[sname] = locs
    return out


def recommend_farm(rec_set_internal: list, drop_map: dict) -> list:
    """Given recommended internal set codes, return 'Set -> location(s)' lines.
    Only sets that drop in a named dungeon are actionable to farm."""
    lines = []
    for code in rec_set_internal:
        locs = [l for l in drop_map.get(code, []) if l != "Campaign"]
        if locs:
            ui = SET_UI_NAME.get(code, code)
            lines.append(f"{ui}: {', '.join(locs)}")
    return lines


def recommend_blessing(hero: dict, location: str, brel: list) -> list:
    provides = set(hero.get("provides", []))
    role = hero.get("synergy_role", "")
    is_damage = role in ("attacker", "dot") or any(
        p.startswith("dot:") for p in provides)

    # Blessing UI/known good picks by role (game-truth procs in blessing_procs).
    # Damage carries: Phantom Touch (MagicOrb) / Brimstone (Meteor) for raw
    # damage; supports: utility. Filter to blessings relevant at the location.
    rloc = _rel_loc(location)
    rel_by_loc = {b["id"]: b["relevance"].get(rloc) for b in brel}
    out = []
    if is_damage:
        for code in ("MagicOrb", "Meteor", "Necromancy", "WildImpulses"):
            if rel_by_loc.get(code) == "relevant":
                out.append(code)
    else:
        for code in ("LeadershipDomination", "Tranquility", "AdvancedHeal",
                     "ChainBreaker"):
            if rel_by_loc.get(code) == "relevant":
                out.append(code)
    return out[:3]


def recommend_stats(hero: dict, location: str, computed: dict | None = None) -> list:
    provides = set(hero.get("provides", []))
    role = hero.get("synergy_role", "")
    game_role = hero.get("game_role", "")
    out = []
    is_debuffer = any(p.startswith("enemy_debuff:") for p in provides) or "dot" in role
    if is_debuffer:
        floor = _acc_floor(location)
        if floor:
            line = f"ACC >= {floor} (game-truth boss RES -- land debuffs at 100% base chance)"
            # Readiness check: compare the user's actual total ACC if known.
            cur = (computed or {}).get(hero["name"].lower(), {}).get("ACC")
            if cur is not None:
                if cur >= floor:
                    line += f"  [READY: you have {cur:.0f}]"
                else:
                    line += f"  [GAP: you have {cur:.0f}, need +{floor - cur:.0f}]"
            out.append(line)
        else:
            out.append("ACC high enough to land debuffs (check boss RES)")
    if role in ("attacker", "dot"):
        out.append("ATK%, C.RATE -> ~100%, C.DMG (damage)")
    if game_role in ("Defense", "Health") or role.startswith("heal"):
        out.append("HP / DEF (survivability)")
    if "SPD" in str(provides) or location in ("arena", "tt"):
        out.append("SPD (turn order / speed tune)")
    if not out:
        out.append("Role-standard stats")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hero", required=True)
    ap.add_argument("--location", required=True)
    ap.add_argument("--optimize", action="store_true",
                    help="also run the gear optimizer to build an ACHIEVABLE loadout "
                         "to the recommended targets (slower)")
    args = ap.parse_args()

    syn = _load_synergy()
    hero = syn.get(args.hero.lower())
    if not hero:
        print(f"Hero '{args.hero}' not found in synergy graph.")
        return
    mrel = _load_mastery_relevance()
    brel = _load_blessing_relevance()
    computed = _load_computed_stats()

    print(f"=== Build for {hero['name']} @ {args.location} ===")
    print(f"  kit: role={hero['synergy_role']} | provides: {', '.join(hero['provides'])}")
    print()
    print("  Masteries (relevant at this location, matched to kit):")
    by_tree = recommend_masteries(hero, args.location, mrel)
    for tree in ("Attack", "Defence", "Support"):
        picks = by_tree.get(tree) or []
        if picks:
            names = ", ".join(p["name"] for p in picks)
            print(f"    {tree}: {names}")
    print()
    sets = recommend_sets(hero, args.location, _load_valid_sets())
    sets_ui = [SET_UI_NAME.get(s, s) for s in sets]
    print(f"  Artifact sets (role-fit): {', '.join(sets_ui) if sets_ui else '(role-standard)'}")
    farm = recommend_farm(sets, _set_drop_regions())
    if farm:
        print("  Farm sets from:")
        for f in farm:
            print(f"    - {f}")
    print()
    bl = recommend_blessing(hero, args.location, brel)
    print(f"  Blessing (relevant + role-fit): {', '.join(bl) if bl else '(role-standard)'}")
    print()
    print("  Stat focus:")
    for s in recommend_stats(hero, args.location, computed):
        print(f"    - {s}")

    if args.optimize:
        _run_optimizer(hero, args.location)


def _run_optimizer(hero: dict, location: str) -> None:
    """Translate the recommended targets into an achievable gear build via
    tools/gear_target_optimizer.py (M6 #1). ACC floor -> hard min; role -> mode."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gear_target_optimizer", ROOT / "tools" / "gear_target_optimizer.py")
    gto = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gto)

    role = hero.get("synergy_role", "")
    provides = set(hero.get("provides", []))
    is_debuffer = any(p.startswith("enemy_debuff:") for p in provides) or "dot" in role
    if role in ("attacker", "dot"):
        mode = "damage"
    elif role in ("support", "healer/support") or hero.get("game_role") in ("Defense", "Health"):
        mode = "survivability"
    else:
        mode = "balanced"

    mins = {}
    if is_debuffer:
        floor = _acc_floor(location)
        if floor:
            mins[gto.ACC] = floor
    targets = gto.build_targets(mins, {}, {}, mode)

    print()
    print(f"  [optimize] building achievable loadout (mode={mode}"
          + (f", ACC>={mins[gto.ACC]:.0f}" if mins else "") + ") ...")
    try:
        arts, heroes, account = gto.load_data()
        opt = gto.Optimizer(arts, heroes, account)
        res = opt.optimize(hero["name"], targets, anneal=6)
    except Exception as ex:
        print(f"    optimizer failed: {ex}")
        return
    st = res["stats"]
    line = "  ".join(f"{gto.STAT_ID_TO_NAME[s]}={st.get(s,0):.0f}"
                     for s in (gto.SPD, gto.ACC, gto.ATK, gto.CR, gto.CD, gto.HP, gto.DEF))
    print(f"    mins_met={res['mins_met']}  {line}")
    from collections import Counter
    setc = Counter(a["set"] for a in res["assignment"].values() if a)
    print(f"    sets: {dict(setc)}")


if __name__ == "__main__":
    main()
