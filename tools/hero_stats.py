"""Gear-inclusive hero stat calculator.

Mirrors the game's Total Stats screen: base + artifacts + sets + Lore of
Steel + empowerment. NOT included: Arena bonuses, Blessings, Faction
Guardians, relic bonuses — those live in /hero-computed-stats.

Set bonuses come from data/static/artifact_sets.json via gear_constants;
LoS mastery id and empowerment table come from raid_data.

CLI usage:
    python3 tools/hero_stats.py "Maneater"
    python3 tools/hero_stats.py "Demytha" --json
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

# Masteries with stat bonuses — read from data/static/masteries.json so a
# Raid version bump auto-picks up new ones. The 13 stat-bonus masteries
# are flat or percentage; conditional ones (Warmaster, Giant Slayer, etc.)
# don't show on the in-game Masteries column and are sim-time effects only.
# Stat names use the IL2CPP enum; map to our 1-letter keys.
_MASTERY_STAT_NAME = {
    "Health": "HP", "Attack": "ATK", "Defence": "DEF", "Speed": "SPD",
    "Resistance": "RES", "Accuracy": "ACC",
    "CriticalChance": "CR", "CriticalDamage": "CD",
}
_MASTERY_STAT_BONUSES: dict[int, dict] = {}  # mastery_id -> {stat, value, absolute}
try:
    import json as _json
    from pathlib import Path as _Path
    _mp = _Path(__file__).resolve().parent.parent / "data" / "static" / "masteries.json"
    if _mp.exists():
        for _m in _json.loads(_mp.read_text()).get("masteries", []):
            sb = _m.get("stat_bonus")
            if not sb:
                continue
            stat_key = _MASTERY_STAT_NAME.get(sb.get("stat"))
            if not stat_key:
                # stat=='-1' is Lore of Steel — handled separately as a set
                # bonus multiplier, not a flat stat.
                continue
            _MASTERY_STAT_BONUSES[_m["id"]] = {
                "stat": stat_key, "value": sb["value"],
                "absolute": sb.get("absolute", True),
            }
except Exception:
    pass
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


def compute_hero_actual_stats(hero, *, base_computed: dict | None = None,
                              mod_bonuses: dict | None = None):
    """Return gear-inclusive actual stats (SPD/HP/ATK/DEF/ACC/RES/CR/CD).

    Source: hero dict from /all-heroes (must have base_stats + artifacts +
    masteries + rarity + empower). Mirrors the game's Total Stats display
    (base + artifacts + sets + Lore of Steel + empowerment). Arena/blessing/
    Faction Guardians/relic bonuses are NOT included — those come from the
    mod's /hero-computed-stats endpoint if needed.

    Bug history (2026-05-01): /all-heroes returns the rank-6 *ascended*
    base stats (e.g. Cardiel HP=119), NOT the level-60 *scaled* base
    (HP=19,650). Using the ascended base directly under-counts %-bonus
    artifacts by a factor of ~165x. Pass `base_computed` from the mod's
    /hero-computed-stats endpoint to override with the level-scaled
    Basic-column values; without it, the calc still works for low-rank
    heroes but misreports L60 6★ stats badly.
    """
    if base_computed:
        # Mod-supplied level-scaled base for HP/ATK/DEF/SPD/RES/ACC.
        flat = {k: float(base_computed.get(k, 0) or 0)
                for k in ["HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD"]}
        # The mod's /hero-computed-stats returns CR/CD as fractions
        # (e.g. 0.1, 0.5) which are NOT the in-game-displayed percentages
        # (15%, 50%). /all-heroes.base_stats has the right values. Prefer
        # those for CR/CD only.
        ah_base = hero.get("base_stats") or {}
        flat["CR"] = float(ah_base.get("CR", flat["CR"]))
        flat["CD"] = float(ah_base.get("CD", flat["CD"]))
    else:
        base = hero.get("base_stats") or {}
        flat = {k: float(base.get(k, 0) or 0) for k in ["HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD"]}
    # Aggregate artifact contributions from primary + substats directly.
    # The mod's pre-summed pct_bonus / flat_bonus dicts have known bugs:
    #   - RES/ACC/CR/CD substats are dropped from pct_bonus.
    #   - Duplicate substats per stat are sometimes only counted once
    #     (verified 2026-05-01 for Cardiel slot 7 with both flat HP and
    #     %HP subs — the % sub was missing from pct_bonus.HP).
    # Working from primary + substats matches the in-game *Total Stats*
    # screen exactly (verified +786 HP delta closes when using this path).
    art_flat = dict.fromkeys(flat, 0.0)
    art_pct = dict.fromkeys(flat, 0.0)
    _STAT_ID_TO_KEY = {1: "HP", 2: "ATK", 3: "DEF", 4: "SPD",
                       5: "RES", 6: "ACC", 7: "CR", 8: "CD"}
    # art_extra holds the absolute (flat ACC/RES/CR/CD) contributions
    # while art_flat/art_pct hold the percent + flat-base bonuses for
    # the percent stats.
    art_extra: dict[str, float] = {"RES": 0.0, "ACC": 0.0, "CR": 0.0, "CD": 0.0}
    sets = {}
    for a in (hero.get("artifacts") or []):
        # Primary stat: value field already includes any rank/level
        # scaling — pick whether to file under flat vs pct based on
        # the artifact's `primary.flat` boolean.
        pri = a.get("primary") or {}
        pri_key = _STAT_ID_TO_KEY.get(pri.get("stat"))
        if pri_key:
            v = float(pri.get("value", 0) or 0)
            if pri.get("flat"):
                if pri_key in ("RES", "ACC", "CR", "CD"):
                    art_extra[pri_key] += v
                else:
                    art_flat[pri_key] += v
            else:
                # %-stat primaries on Gloves/Chest/Boots etc. The value
                # field is the raw % (60.0 means 60%).
                if pri_key in ("CR", "CD"):
                    art_extra[pri_key] += v
                else:
                    art_pct[pri_key] += v / 100.0
        # Substats: include glyph upgrades. ss.value is the BASE substat;
        # ss.glyph is the bonus from substat-glyph upgrades (Sacred Gear).
        # The in-game UI reports the sum.
        for ss in (a.get("substats") or []):
            ss_key = _STAT_ID_TO_KEY.get(ss.get("stat"))
            if not ss_key:
                continue
            v = float(ss.get("value", 0) or 0) + float(ss.get("glyph", 0) or 0)
            if ss.get("flat"):
                if ss_key in ("RES", "ACC", "CR", "CD"):
                    art_extra[ss_key] += v
                else:
                    art_flat[ss_key] += v
            else:
                if ss_key in ("CR", "CD"):
                    art_extra[ss_key] += v
                else:
                    art_pct[ss_key] += v / 100.0
        s = a.get("set", 0)
        if s:
            sets[s] = sets.get(s, 0) + 1
    hero_masteries = hero.get("masteries") or []
    has_los = _LORE_OF_STEEL in hero_masteries
    # Base set bonus (no LoS), with the LoS amplifier tracked separately so we
    # can attribute it to the "Masteries" column like the in-game stat sheet.
    set_pct = dict.fromkeys(flat, 0.0)      # pct portion from sets, no LoS
    set_flat = dict.fromkeys(flat, 0.0)
    mastery_pct = dict.fromkeys(flat, 0.0)  # LoS delta (15% of base set pct)
    mastery_flat = dict.fromkeys(flat, 0.0)  # +75 DEF / +810 HP / +50 ACC etc.
    # Masteries that grant a flat or %-of-base stat (DEF +75, CR +5%, ...)
    for mid in hero_masteries:
        mb = _MASTERY_STAT_BONUSES.get(mid)
        if not mb:
            continue
        stat_key = mb["stat"]
        val = mb["value"]
        if mb.get("absolute"):
            mastery_flat[stat_key] += val
        else:
            # percent-of-base (e.g. 0.05 for CR +5% literally adds 5 to the
            # 0-100 CR scale; not multiplicative on an existing %)
            if stat_key in ("CR", "CD"):
                mastery_flat[stat_key] += val * 100  # 0.05 -> +5
            else:
                mastery_pct[stat_key] += val
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
        # Masteries column = flat-stat masteries (+75 DEF, +810 HP, +5 CR%, etc.)
        # PLUS the LoS delta on set bonuses. Both attribute to "Masteries"
        # in the in-game Total Stats column.
        mast_val = mastery_flat[k] + flat[k] * mastery_pct[k]
        emp_val = emp_flat[k] + flat[k] * emp_pct[k]
        set_flat_val = set_flat[k]  # ACC/RES flat-set bonuses
        # RES/ACC/CR/CD aren't in the mod's pre-summed pct/flat bonus dicts.
        extra_val = art_extra.get(k, 0.0)
        if k in ("HP", "ATK", "DEF", "SPD"):
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
        elif k in ("ACC", "RES"):
            # Flat columns (treated as ints in the in-game display).
            components = [
                int(base_val),
                int(art_val + set_flat_val + extra_val),  # +substats / +primary aggregated
                round(mast_val),
                int(emp_val),
            ]
            out[k] = sum(components)
            breakdown[k] = {"basic": components[0], "artifacts": components[1],
                            "masteries": components[2], "empower": components[3]}
        else:
            # CR / CD: artifact contribution from primary + substats only.
            out[k] = round(base_val + art_val + extra_val + mast_val + emp_val, 1)

    # Layer in the mod's per-column bonuses. Field names match the
    # in-game Total Stats columns after the 2026-05-01 mod patch:
    # - affinity_bonus (was great_hall_bonus; Village faction-guardian towers)
    # - classic_arena_bonus (was arena_bonus; user's CURRENT arena league)
    # - faction_guardians_bonus (NEW; Academy progression)
    # - mastery_bonus (NEW; replaces our static-derived calc)
    # - blessing_bonus, empower_bonus, relic_bonus (unchanged)
    if mod_bonuses:
        # NOTE: deliberately NOT layering mod's mastery_bonus — verified
        # 2026-05-01 that CalcMasteriesBonus returns CR=10% for Cardiel
        # but the in-game Total Stats screen + static data both show +5%.
        # The mod's IL2CPP call has a bug we don't yet understand; our
        # static-derived calc (computed above into mastery_flat/pct) is
        # more accurate. Revisit if/when the mod call is fixed.
        # NOT layering mod's artifact_bonus either — its IL2CPP dict
        # enumeration on Dictionary<EnumKey, Int32> always returns
        # empty for the equipped-artifact list, so CalcArtifactsBonus
        # gets called with [] and returns zero. Our manual aggregation
        # from primary+substats matches in-game HP exactly.
        column_to_field = {
            "affinity": "affinity_bonus",
            "classic_arena": "classic_arena_bonus",
            "faction_guardians": "faction_guardians_bonus",
            "blessing": "blessing_bonus",
            "empower_mod": "empower_bonus",
            "relic": "relic_bonus",
        }
        bonus_breakdown: dict[str, dict] = {}
        for col_name, field_name in column_to_field.items():
            field_data = mod_bonuses.get(field_name) or {}
            bonus_breakdown[col_name] = {}
            for stat_key, val in field_data.items():
                if stat_key not in out:
                    continue
                v = float(val or 0)
                if v == 0:
                    continue
                # CR/CD in mod come as 0.05 fractions; rest are flat numbers.
                if stat_key in ("CR", "CD"):
                    v = v * 100  # 0.18 -> 18
                out[stat_key] = round(out[stat_key] + v, 1) if isinstance(out[stat_key], float) else int(out[stat_key] + v)
                bonus_breakdown[col_name][stat_key] = v
        out["_mod_bonuses_breakdown"] = bonus_breakdown
    out["_breakdown"] = breakdown
    return out


import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from cli_util import fetch_heroes_from_mod  # noqa: E402, F401


def find_hero(heroes: list[dict], query: str) -> dict | None:
    """Case-insensitive name match; prefers max-ascended / 6-star matches."""
    q = query.lower()
    matches = [h for h in heroes if q in (h.get("name") or "").lower()]
    if not matches:
        return None
    # Prefer 6-star with most empower
    matches.sort(key=lambda h: (h.get("rank", 0), h.get("empower", 0)), reverse=True)
    return matches[0]


def _format_breakdown(name: str, stats: dict) -> str:
    breakdown = stats.get("_breakdown", {})
    out = [f"{name}", "-" * len(name)]
    out.append(f"  {'stat':5s}  {'total':>7s}  =  {'basic':>6s} + {'artifacts':>9s} + {'mastery':>7s} + {'empower':>7s}")
    for k in ("HP", "ATK", "DEF", "SPD", "RES", "ACC"):
        b = breakdown.get(k, {})
        out.append(f"  {k:5s}  {stats[k]:>7}  =  {b.get('basic',0):>6} + {b.get('artifacts',0):>9} + {b.get('masteries',0):>7} + {b.get('empower',0):>7}")
    out.append(f"  {'CR':5s}  {stats['CR']:>7}%")
    out.append(f"  {'CD':5s}  {stats['CD']:>7}%")
    return "\n".join(out)


def fetch_computed_from_mod(mod_url: str = "http://localhost:6790") -> dict[int, dict]:
    """Live-pull /hero-computed-stats and return {hero_id: stats_dict}.

    The mod returns the game's own per-column breakdown:
    base_computed, blessing_bonus, empower_bonus, great_hall_bonus
    (which is actually Affinity Bonuses), arena_bonus, and (sometimes)
    relic_bonus. Empty dict on any error.
    """
    import json as _json
    import urllib.request
    try:
        with urllib.request.urlopen(f"{mod_url}/hero-computed-stats?min_grade=6", timeout=30) as r:
            data = _json.loads(r.read().decode("utf-8"))
        return {int(h["id"]): h for h in data.get("heroes", [])}
    except Exception:
        return {}


def diff_vs_mod(hero: dict, mod_computed: dict, *, tolerance: float = 1.0) -> list[dict]:
    """Compare our PyAutoRaid calc to the mod's /hero-computed-stats.

    Returns a list of per-stat diff rows. Each row:
      {stat, our, mod_total, mod_breakdown:{base,blessing,...}, ok, delta}

    ok=True if abs(our - mod_total) <= tolerance.

    The mod doesn't break out Artifacts/Masteries/Mastery columns —
    those still come from our own calc. We compare the SUM of all
    columns we both compute (base + blessing + empower + affinity +
    arena + relic) against the corresponding components of `our`.
    """
    # Use the mod's level-scaled base_computed for an apples-to-apples
    # comparison; without it our calc applies %-artifacts to a level-1
    # base and underflows badly. Also layer the mod's per-column bonuses
    # (Affinity / Blessing / Relic / Empower / mystery arena) so the
    # final number matches what the in-game Total Stats screen shows.
    ours = compute_hero_actual_stats(
        hero,
        base_computed=mod_computed.get("base_computed"),
        mod_bonuses=mod_computed,
    )
    rows: list[dict] = []

    base = mod_computed.get("base_computed") or {}
    blessing = mod_computed.get("blessing_bonus") or {}
    empower = mod_computed.get("empower_bonus") or {}
    affinity = mod_computed.get("affinity_bonus") or {}
    classic_arena = mod_computed.get("classic_arena_bonus") or {}
    relic = mod_computed.get("relic_bonus") or {}
    mastery = mod_computed.get("mastery_bonus") or {}
    faction_guardians = mod_computed.get("faction_guardians_bonus") or {}

    for stat in ("HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD"):
        b = base.get(stat, 0)
        # CR/CD: convert mod fractions (0.1, 0.5) to percentage form (10, 50)
        if stat in ("CR", "CD"):
            b = b * 100
        bl = blessing.get(stat, 0)
        em = empower.get(stat, 0)
        af = affinity.get(stat, 0)
        ca = classic_arena.get(stat, 0)
        rl = relic.get(stat, 0)
        ms = mastery.get(stat, 0)
        fg = faction_guardians.get(stat, 0)
        if stat in ("CR", "CD"):
            af = af * 100; ca = ca * 100; rl = rl * 100
            ms = ms * 100; fg = fg * 100
        # Mod partial = sum of every column the mod can compute. Doesn't
        # include Artifacts (we still compute that) or Area Bonuses
        # (per-location, not in payload yet).
        mod_partial = b + bl + em + af + ca + rl + ms + fg
        our_val = ours.get(stat, 0)
        delta = our_val - mod_partial
        rows.append({
            "stat": stat,
            "our": our_val,
            "mod_partial": round(mod_partial, 2),
            "delta": round(delta, 2),
            "breakdown": {
                "base": b, "blessing": bl, "empower": em,
                "affinity": af, "classic_arena": ca, "relic": rl,
                "mastery_from_mod": ms, "faction_guardians": fg,
            },
        })
    return rows


def _format_breakdown_full(name: str, hero_meta: dict, mod_computed: dict | None) -> str:
    """Render the per-column Total Stats breakdown."""
    ours = compute_hero_actual_stats(
        hero_meta,
        base_computed=mod_computed.get("base_computed") if mod_computed else None,
        mod_bonuses=mod_computed if mod_computed else None,
    )
    out = [f"{name}", "=" * len(name)]
    out.append(f"  {'stat':5s}  {'our':>7s}  {'mod':>7s}  {'delta':>7s}  breakdown (mod)")
    if not mod_computed:
        out.append("  (mod /hero-computed-stats not available — only our calc shown)")
        for stat in ("HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD"):
            out.append(f"  {stat:5s}  {ours.get(stat,0):>7}")
        return "\n".join(out)
    rows = diff_vs_mod(hero_meta, mod_computed)
    for r in rows:
        b = r["breakdown"]
        parts = []
        # Compact breakdown — only nonzero parts to keep lines short.
        for label, key in [
            ("bas", "base"), ("art", None),  # placeholder
            ("aff", "affinity"), ("arn", "classic_arena"),
            ("mas", "mastery_from_mod"), ("fg", "faction_guardians"),
            ("emp", "empower"), ("ble", "blessing"), ("rel", "relic"),
        ]:
            if key is None:
                continue
            v = b.get(key, 0)
            if v:
                parts.append(f"{label}={v:.0f}")
        out.append(f"  {r['stat']:5s}  {r['our']:>7}  {r['mod_partial']:>7}  {r['delta']:>+7}  {' '.join(parts)}")
    return "\n".join(out)


def _main() -> int:
    """CLI: print gear-inclusive stats for a named hero from the live mod."""
    import argparse
    import json as _json
    import sys

    ap = argparse.ArgumentParser(
        description="Print gear-inclusive hero stats (matches in-game Total Stats)")
    ap.add_argument("name", help="hero name (or partial match)")
    ap.add_argument("--mod-url", default="http://localhost:6790")
    ap.add_argument("--json", action="store_true",
                    help="emit JSON instead of formatted text")
    ap.add_argument("--vs-mod", action="store_true",
                    help="diff our calc against the mod's /hero-computed-stats "
                         "(surfaces missing columns / mismatches)")
    args = ap.parse_args()

    heroes = fetch_heroes_from_mod(args.mod_url)
    if not heroes:
        print(f"ERR: mod not reachable at {args.mod_url}", file=sys.stderr)
        return 2
    hero = find_hero(heroes, args.name)
    if not hero:
        print(f"ERR: no hero matching {args.name!r}", file=sys.stderr)
        return 1

    if args.vs_mod:
        mod_computed = fetch_computed_from_mod(args.mod_url).get(hero["id"])
        if args.json:
            print(_json.dumps({
                "name": hero.get("name"), "id": hero.get("id"),
                "ours": compute_hero_actual_stats(hero),
                "mod_breakdown": mod_computed,
                "diff": diff_vs_mod(hero, mod_computed or {}),
            }, indent=2))
        else:
            print(_format_breakdown_full(hero.get("name", "?"), hero, mod_computed))
        return 0

    stats = compute_hero_actual_stats(hero)
    if args.json:
        print(_json.dumps({"name": hero.get("name"), "id": hero.get("id"), "stats": stats}, indent=2))
    else:
        print(_format_breakdown(hero.get("name", "?"), stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
