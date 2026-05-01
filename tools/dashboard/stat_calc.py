"""Gear-inclusive hero stat calculator.

Mirrors the game's Total Stats screen: base + artifacts + sets + Lore of
Steel + empowerment. NOT included: Arena bonuses, Blessings, Faction
Guardians, relic bonuses — those live in /hero-computed-stats.

Extracted from dashboard_server.py for separation of concerns. Set
bonuses come from data/static/artifact_sets.json via gear_constants;
LoS mastery id and empowerment table come from raid_data.
"""
from __future__ import annotations


# Set bonuses sourced from data/static/artifact_sets.json via gear_constants.
# Keeping a fallback for when the dashboard runs in isolated test contexts
# without static data refreshed.
try:
    from gear_constants import SET_BONUSES as _SET_BONUSES
except Exception:
    _SET_BONUSES = {
        1: (2, {1: 15}), 2: (2, {2: 15}), 3: (2, {3: 15}), 4: (2, {4: 12}),
        5: (2, {7: 12}), 6: (2, {8: 20}), 7: (2, {6: 40}), 8: (2, {5: 40}),
    }
_STAT_KEY = {1: "HP", 2: "ATK", 3: "DEF", 4: "SPD", 5: "RES", 6: "ACC", 7: "CR", 8: "CD"}
try:
    from raid_data import MASTERY_IDS as _MASTERY_IDS
    _LORE_OF_STEEL = _MASTERY_IDS["lore_of_steel"]
except Exception:
    _LORE_OF_STEEL = 500343
# Empowerment stat bonuses per level: see raid_data.EMPOWERMENT_BONUSES
# for the canonical table; mirrored here only for offline test contexts.
try:
    from raid_data import EMPOWERMENT_BONUSES as _EMP_BONUSES
except Exception:
    _EMP_BONUSES = {
        "epic":      [(0,0,0,0,0,0), (10,10,10,0,0,0), (20,20,20,5,5,0),   (30,30,30,5,5,0),   (40,40,40,10,15,5)],
        "legendary": [(0,0,0,0,0,0), (10,15,15,0,0,0), (20,25,25,10,0,0),  (30,45,45,10,0,0),  (40,55,55,15,30,10)],
    }


def compute_hero_actual_stats(hero):
    """Return gear-inclusive actual stats (SPD/HP/ATK/DEF/ACC/RES/CR/CD).

    Source: hero dict from /all-heroes (must have base_stats + artifacts +
    masteries + rarity + empower). Mirrors the game's Total Stats display
    (base + artifacts + sets + Lore of Steel + empowerment). Arena/blessing/
    Faction Guardians/relic bonuses are NOT included — those come from the
    mod's /hero-computed-stats endpoint if needed.
    """
    base = hero.get("base_stats") or {}
    flat = {k: float(base.get(k, 0) or 0) for k in ["HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD"]}
    art_flat = dict.fromkeys(flat, 0.0)
    art_pct = dict.fromkeys(flat, 0.0)
    sets = {}
    for a in (hero.get("artifacts") or []):
        fb = a.get("flat_bonus") or {}
        pb = a.get("pct_bonus") or {}
        for k in flat:
            art_flat[k] += float(fb.get(k, 0) or 0)
            art_pct[k] += float(pb.get(k, 0) or 0)
        s = a.get("set", 0)
        if s:
            sets[s] = sets.get(s, 0) + 1
    has_los = _LORE_OF_STEEL in (hero.get("masteries") or [])
    # Base set bonus (no LoS), with the LoS amplifier tracked separately so we
    # can attribute it to the "Masteries" column like the in-game stat sheet.
    set_pct = dict.fromkeys(flat, 0.0)      # pct portion from sets, no LoS
    set_flat = dict.fromkeys(flat, 0.0)
    mastery_pct = dict.fromkeys(flat, 0.0)  # LoS delta (15% of base set pct)
    for set_id, count in sets.items():
        spec = _SET_BONUSES.get(set_id)
        if not spec:
            continue
        pieces_per, stats = spec
        apps = count // pieces_per
        for stat_id, val in stats.items():
            k = _STAT_KEY.get(stat_id)
            if not k:
                continue
            if k in ("ACC", "RES"):
                set_flat[k] += val * apps
            else:
                base_pct = (val / 100.0) * apps
                set_pct[k] += base_pct
                if has_los:
                    mastery_pct[k] += base_pct * 0.15
    emp_lvl = int(hero.get("empower", 0) or 0)
    rarity = hero.get("rarity", 4)
    emp_cat = "legendary" if rarity == 5 else "epic"
    emp_tbl = _EMP_BONUSES.get(emp_cat, _EMP_BONUSES["epic"])
    emp_flat = dict.fromkeys(flat, 0.0)
    emp_pct = dict.fromkeys(flat, 0.0)
    if 0 <= emp_lvl < len(emp_tbl):
        hp_atk_def, acc, res, spd, cd, cr = emp_tbl[emp_lvl]
        emp_flat.update({"SPD": spd, "ACC": acc, "RES": res})
        emp_pct.update({
            "HP": hp_atk_def / 100.0, "ATK": hp_atk_def / 100.0, "DEF": hp_atk_def / 100.0,
            "CD": cd / 100.0, "CR": cr / 100.0,
        })
    # Sum components the way the in-game "Total Stats" screen does: each
    # contribution is floored/rounded independently, then summed. Matches the
    # game's Basic + Artifacts + Masteries + Empowerment columns.
    out = {}
    breakdown = {}
    for k in flat:
        base_val = flat[k]
        art_val = art_flat[k] + flat[k] * art_pct[k] + flat[k] * set_pct[k]  # flat + %substats + base set
        mast_val = flat[k] * mastery_pct[k]  # LoS delta only, attributed to masteries
        emp_val = emp_flat[k] + flat[k] * emp_pct[k]
        set_flat_val = set_flat[k]  # ACC/RES flat-set bonuses
        if k in ("HP", "ATK", "DEF", "SPD", "ACC", "RES"):
            # Game floors the per-column integer display
            components = [
                int(base_val),
                int(art_val + set_flat_val),   # artifacts column aggregates set-flats too
                round(mast_val),                # masteries column uses rounding (0.5 -> 1)
                int(emp_val),
            ]
            out[k] = sum(components)
            breakdown[k] = {"basic": components[0], "artifacts": components[1],
                            "masteries": components[2], "empower": components[3]}
        else:
            out[k] = round(base_val + art_val + mast_val + emp_val, 1)
    out["_breakdown"] = breakdown
    return out
