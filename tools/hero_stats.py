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


def compute_hero_actual_stats(hero, *, base_computed: dict | None = None):
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
        # Mod-supplied level-scaled base (matches in-game Basic column).
        flat = {k: float(base_computed.get(k, 0) or 0)
                for k in ["HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD"]}
        # The mod returns CR/CD as fractions (0.1 / 0.5). Convert to
        # percentage shape that downstream code expects.
        flat["CR"] *= 100
        flat["CD"] *= 100
    else:
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
    # base and underflows badly.
    ours = compute_hero_actual_stats(hero, base_computed=mod_computed.get("base_computed"))
    rows: list[dict] = []

    base = mod_computed.get("base_computed") or {}
    blessing = mod_computed.get("blessing_bonus") or {}
    empower = mod_computed.get("empower_bonus") or {}
    affinity = mod_computed.get("great_hall_bonus") or {}  # mod misnamed; this is Affinity
    arena = mod_computed.get("arena_bonus") or {}
    relic = mod_computed.get("relic_bonus") or {}

    for stat in ("HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD"):
        b = base.get(stat, 0)
        bl = blessing.get(stat, 0)
        em = empower.get(stat, 0)
        af = affinity.get(stat, 0)
        ar = arena.get(stat, 0)
        rl = relic.get(stat, 0)
        # Sum what the mod gave us; the rest (Artifacts, Classic Arena,
        # Masteries, Faction Guardians, Area Bonuses) we currently miss.
        mod_partial = b + bl + em + af + ar + rl
        our_val = ours.get(stat, 0)
        delta = our_val - mod_partial
        rows.append({
            "stat": stat,
            "our": our_val,
            "mod_partial": round(mod_partial, 2),
            "delta": round(delta, 2),
            "breakdown": {
                "base": b, "blessing": bl, "empower": em,
                "affinity_(great_hall_misnamed)": af,
                "arena_(unknown_meaning)": ar,
                "relic": rl,
            },
            # ok ignored for now — the mod isn't returning everything yet,
            # so deltas are expected. Surfaces the GAP, doesn't gate on it.
        })
    return rows


def _format_breakdown_full(name: str, hero_meta: dict, mod_computed: dict | None) -> str:
    """Render the per-column Total Stats breakdown."""
    ours = compute_hero_actual_stats(
        hero_meta,
        base_computed=mod_computed.get("base_computed") if mod_computed else None,
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
        # compact breakdown string — only nonzero parts
        parts = []
        for k in ("base", "blessing", "empower"):
            if b[k]:
                parts.append(f"{k[:3]}={b[k]:.0f}")
        if b["affinity_(great_hall_misnamed)"]:
            parts.append(f"aff={b['affinity_(great_hall_misnamed)']:.0f}")
        if b["arena_(unknown_meaning)"]:
            parts.append(f"arena?={b['arena_(unknown_meaning)']:.0f}")
        if b["relic"]:
            parts.append(f"rel={b['relic']:.0f}")
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
