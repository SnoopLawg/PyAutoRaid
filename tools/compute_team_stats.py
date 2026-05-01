#!/usr/bin/env python3
"""Compute gear-inclusive battle stats for specified heroes using mod /all-heroes.

Usage:
    python tools/compute_team_stats.py --team "Maneater,Demytha,Ninja,Geomancer,Venomage"
    python tools/compute_team_stats.py --team "ME,Demy,Ninja,Geo,Venomage" --tune myth_eater

Shows actual SPD/HP/ATK/DEF/ACC/RES vs tune targets so you can tell which heroes
are mis-tuned.
"""
import argparse, json, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from gear_constants import SET_BONUSES, STAT_HP, STAT_ATK, STAT_DEF, STAT_SPD, STAT_CR, STAT_CD, STAT_ACC, STAT_RES
from raid_data import EMPOWERMENT_BONUSES

# SET_BONUSES now derives from data/static/artifact_sets.json via
# gear_constants. The previous hand-coded Divine-set override (set IDs
# 24/25/27/61/33) was using wrong IDs — set 24 is Counterattack in the
# live game, not DivineSpeed. Anyone using actual Divine relics should
# refresh static data and the right values will load automatically.

RARITY_TO_EMPOWER = {4: "epic", 5: "legendary"}

MOD = "http://localhost:6790"
try:
    from raid_data import MASTERY_IDS as _MASTERY_IDS
    LORE_OF_STEEL = _MASTERY_IDS["lore_of_steel"]
except Exception:
    LORE_OF_STEEL = 500343
from gear_constants import STAT_NAMES  # noqa: E402, F401


def fetch_heroes():
    with urllib.request.urlopen(f"{MOD}/all-heroes?page_size=600", timeout=30) as r:
        return json.loads(r.read())["heroes"]


def match_hero(heroes, query):
    q = query.lower()
    aliases = {"me": "maneater", "demy": "demytha", "geo": "geomancer", "ven": "venomage", "ninja": "ninja"}
    q = aliases.get(q, q)
    matches = [h for h in heroes if q in (h.get("name") or "").lower()]
    # Prefer 6-star
    matches.sort(key=lambda h: (-h.get("grade", 0), -(h.get("level") or 0)))
    return matches[0] if matches else None


def compute_stats(hero):
    base = hero["base_stats"]  # percent/flat base at current level
    # Start with base HP/ATK/DEF/SPD/RES/ACC/CR/CD
    flat = {k: float(base.get(k, 0)) for k in ["HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD"]}

    art_flat = dict.fromkeys(flat, 0.0)
    art_pct = dict.fromkeys(flat, 0.0)
    sets = {}
    for a in hero.get("artifacts", []):
        fb = a.get("flat_bonus") or {}
        pb = a.get("pct_bonus") or {}
        for k in flat:
            art_flat[k] += float(fb.get(k, 0) or 0)
            art_pct[k] += float(pb.get(k, 0) or 0)
        s = a.get("set", 0)
        if s:
            sets[s] = sets.get(s, 0) + 1

    # Set bonuses — each 2 pieces = 1 bonus application. Lore of Steel is
    # tracked as a separate "mastery" contribution (matches the in-game Total
    # Stats breakdown: base set bonus in Artifacts column, LoS 15% delta in
    # Masteries column).
    has_los = LORE_OF_STEEL in (hero.get("masteries") or [])
    set_pct = dict.fromkeys(flat, 0.0)
    set_flat = dict.fromkeys(flat, 0.0)
    mastery_pct = dict.fromkeys(flat, 0.0)
    for set_id, count in sets.items():
        spec = SET_BONUSES.get(set_id)
        if not spec:
            continue
        pieces_per, stats = spec
        applications = count // pieces_per
        for stat_id, val in stats.items():
            stat_key = STAT_NAMES.get(stat_id)
            if not stat_key:
                continue
            # ACC/RES set bonuses are FLAT; all others are %
            if stat_key in ("ACC", "RES"):
                set_flat[stat_key] += val * applications
            else:
                base_pct = (val / 100.0) * applications
                set_pct[stat_key] += base_pct
                if has_los:
                    mastery_pct[stat_key] += base_pct * 0.15

    # Empowerment bonus (flat SPD/ACC/RES + % HP/ATK/DEF + CD/CR)
    emp_lvl = int(hero.get("empower", 0) or 0)
    rarity = hero.get("rarity", 4)
    emp_tbl = EMPOWERMENT_BONUSES.get(RARITY_TO_EMPOWER.get(rarity, "epic"), EMPOWERMENT_BONUSES["epic"])
    if 0 <= emp_lvl < len(emp_tbl):
        hp_atk_def_pct, flat_acc, flat_res, flat_spd, cd_pct, cr_pct = emp_tbl[emp_lvl]
        emp_flat = {
            "HP": 0, "ATK": 0, "DEF": 0, "SPD": flat_spd, "ACC": flat_acc, "RES": flat_res,
            "CR": 0, "CD": 0,
        }
        emp_pct = {
            "HP": hp_atk_def_pct / 100.0, "ATK": hp_atk_def_pct / 100.0, "DEF": hp_atk_def_pct / 100.0,
            "SPD": 0, "ACC": 0, "RES": 0,
            "CR": cr_pct / 100.0, "CD": cd_pct / 100.0,
        }
    else:
        emp_flat = dict.fromkeys(flat, 0.0)
        emp_pct = dict.fromkeys(flat, 0.0)

    # Columnar sum — matches in-game "Total Stats" screen (Basic + Artifacts +
    # Masteries + Empowerment). Each column rounded/floored independently so
    # fractional drift doesn't shave a SPD off the total.
    final = {}
    breakdown = {}
    import math as _math
    for k in flat:
        base_v = flat[k]
        art_v = art_flat[k] + flat[k] * art_pct[k] + flat[k] * set_pct[k]  # flat + %substats + base set
        mast_v = flat[k] * mastery_pct[k]  # LoS delta
        emp_v = emp_flat[k] + flat[k] * emp_pct[k]
        set_flat_v = set_flat[k]
        if k in ("HP", "ATK", "DEF", "SPD", "ACC", "RES"):
            cols = [int(base_v), int(art_v + set_flat_v), round(mast_v), int(emp_v)]
            final[k] = sum(cols)
            breakdown[k] = {"basic": cols[0], "artifacts": cols[1], "masteries": cols[2], "empower": cols[3]}
        else:
            final[k] = round(base_v + art_v + mast_v + emp_v, 1)
    return {
        "base": flat,
        "art_flat": art_flat,
        "art_pct": art_pct,
        "set_pct": set_pct,
        "set_flat": set_flat,
        "sets": sets,
        "final": final,
        "breakdown": breakdown,
        "has_lore_of_steel": has_los,
    }


def tune_targets(tune_id):
    """Map Myth Eater / Budget UK / etc. SPD slot targets to hero-by-name."""
    from tune_library import TUNES
    t = TUNES.get(tune_id)
    if not t:
        return {}
    return {slot.role: slot for slot in t.slots}


def print_hero(name, hero, team_tune_slot=None):
    s = compute_stats(hero)
    f = s["final"]
    print(f"\n=== {name} (lvl {hero.get('level')}, empower {hero.get('empower',0)}, {len(hero.get('artifacts',[]))} artifacts) ===")
    import math
    print(f"  SPD {math.floor(f['SPD'])}  HP {math.floor(f['HP'])}  ATK {math.floor(f['ATK'])}  DEF {math.floor(f['DEF'])}  "
          f"ACC {math.floor(f['ACC'])}  RES {math.floor(f['RES'])}  CR {f['CR']:.1f}%  CD {f['CD']:.1f}%")
    print(f"  sets: {s['sets']}  LoS: {s['has_lore_of_steel']}")
    if team_tune_slot:
        lo, hi = team_tune_slot.speed_range
        status = "[on target]" if lo <= f['SPD'] <= hi else (
            f"[+{f['SPD']-hi:.0f} TOO FAST]" if f['SPD'] > hi else f"[-{lo-f['SPD']:.0f} TOO SLOW]"
        )
        print(f"  tune: {team_tune_slot.role} target {lo}-{hi} SPD -> {status}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", required=True, help="comma-separated hero names or aliases")
    ap.add_argument("--tune", default=None, help="optional tune id (myth_eater, budget_uk, etc.)")
    args = ap.parse_args()

    heroes = fetch_heroes()
    tune = tune_targets(args.tune) if args.tune else {}
    # Myth Eater slot→hero heuristic: Maneater is fast_uk, Demytha is block_damage, Ninja is dps_4to3
    slot_for = {}
    names = [n.strip() for n in args.team.split(",")]
    for name in names:
        h = match_hero(heroes, name)
        if not h:
            print(f"[no match] {name}")
            continue
        # Assign tune slot heuristic
        actual_name = h.get("name", "")
        slot_obj = None
        if tune:
            nm = actual_name.lower()
            if "maneater" in nm and "fast_uk" in tune: slot_obj = tune["fast_uk"]
            elif "demytha" in nm and "block_damage" in tune: slot_obj = tune["block_damage"]
            elif "ninja" in nm and "dps_4to3" in tune: slot_obj = tune["dps_4to3"]
            # assign remaining DPS slots by SPD ranking later if needed
        print_hero(actual_name, h, slot_obj)


if __name__ == "__main__":
    main()
