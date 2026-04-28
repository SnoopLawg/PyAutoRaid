#!/usr/bin/env python3
"""Roster-aware comp finder: match user's owned heroes to DWJ tunes.

Reads:
- heroes_all.json (mod API dump) — owned heroes with grade/level/empower
- data/dwj/parsed/tunes.json + calc_tunes.json — 103 DWJ tunes with slot requirements
- data/hh/parsed/tierlist.json — HH CB ratings for prioritization

For each DWJ tune, scores how many slots the user can fill. Outputs three
buckets:
- RUNNABLE: every named slot filled at 6-star
- 1 AWAY: one named slot missing (or needs ascending)
- 2 AWAY: two named slots missing

Within each bucket, sorts by HH CB rating of the key heroes + key_capability.

Usage:
    python3 tools/comp_finder.py                            # all tunes, text report
    python3 tools/comp_finder.py --runnable                 # only fully-runnable
    python3 tools/comp_finder.py --missing 1                # only 1-away
    python3 tools/comp_finder.py --affinity "All Affinities"
    python3 tools/comp_finder.py --key "2 Key UNM"
    python3 tools/comp_finder.py --md docs/comp_feasibility.md   # emit markdown report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

HEROES_ALL = PROJECT_ROOT / "heroes_all.json"
DWJ_TUNES = PROJECT_ROOT / "data" / "dwj" / "parsed" / "tunes.json"
DWJ_CALC_TUNES = PROJECT_ROOT / "data" / "dwj" / "parsed" / "calc_tunes.json"
HH_TIERLIST = PROJECT_ROOT / "data" / "hh" / "parsed" / "tierlist.json"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def load_roster() -> dict[str, dict]:
    """Return {norm_name: hero_dict_at_max_grade}."""
    data = json.loads(HEROES_ALL.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for h in data.get("heroes", []):
        nm = h.get("name") or ""
        key = norm(nm)
        if not key:
            continue
        prev = out.get(key)
        if not prev or (h.get("grade", 0), h.get("level", 0), h.get("empower", 0)) > (
            prev.get("grade", 0), prev.get("level", 0), prev.get("empower", 0)
        ):
            out[key] = h
    return out


def load_tunes() -> list[dict]:
    return json.loads(DWJ_TUNES.read_text(encoding="utf-8"))


def load_calc_variants() -> dict:
    """Return {variant_hash: variant_dict}. Empty if calc_tunes.json missing."""
    if not DWJ_CALC_TUNES.exists():
        return {}
    return json.loads(DWJ_CALC_TUNES.read_text(encoding="utf-8"))


def enrich_tune_slots_with_calc(tune: dict, calc_variants: dict) -> dict:
    """Replace generic "DPS" / "Block Debuff" / etc. slot names with the
    actual hero from the tune's calc variant, when available.

    Why: tunes like Myth Hare have slot[3].hero="Block Debuff" (generic),
    but the calc variant pins that role to "Underpriest Brogni" (specific).
    Treating it as generic = matches anyone, which falsely scores the tune
    as runnable. Pulling the specific name from the calc variant turns
    those slots into real "missing" gates.

    Returns a new tune dict with `slots` updated in place; original tune
    untouched. If no calc variant exists, the tune is returned as-is.
    """
    if not calc_variants:
        return tune
    links = tune.get("calculator_links") or []
    if not links:
        return tune
    # Prefer Ultimate Nightmare > Nightmare > Brutal > first.
    def _rank(c):
        n = (c.get("name") or "").lower()
        if "ultra" in n or "ultimate" in n: return 0
        if "nightmare" in n: return 1
        if "brutal" in n: return 2
        return 3
    sorted_links = sorted(links, key=_rank)
    variant = None
    for c in sorted_links:
        v = calc_variants.get(c.get("hash"))
        if v and v.get("champions"):
            variant = v
            break
    if not variant:
        return tune
    variant_champs = list(variant.get("champions") or [])
    # Match tune.slots to variant.champions by name first, leaving the
    # leftover variant champions to fill the tune's generic slots.
    tune_slots = list(tune.get("slots") or [])
    used_variant_idxs = set()
    for s in tune_slots:
        sn = norm(s.get("hero") or "")
        if not sn or is_generic_slot(s.get("hero") or ""):
            continue
        for vi, vc in enumerate(variant_champs):
            if vi in used_variant_idxs:
                continue
            vn = norm(vc.get("name") or "")
            if vn and (vn == sn or vn in sn or sn in vn):
                used_variant_idxs.add(vi)
                break
    leftover = [variant_champs[i] for i in range(len(variant_champs)) if i not in used_variant_idxs]
    # Now walk slots, replacing generic ones with leftover variant champions
    # (in order). If we run out of leftovers, leave the slot generic.
    new_slots = []
    leftover_iter = iter(leftover)
    for s in tune_slots:
        s = dict(s)
        if is_generic_slot(s.get("hero") or ""):
            try:
                vc = next(leftover_iter)
                # Only override with a SPECIFIC hero name (not another
                # placeholder). DWJ tunes like Myth Eater keep "1:1 DPS 1"
                # in calc variants too — those stay generic.
                if vc.get("name") and not is_generic_slot(vc["name"]):
                    s["hero"] = vc["name"]
                    s["_from_calc"] = True
            except StopIteration:
                pass
        new_slots.append(s)
    return {**tune, "slots": new_slots}


def load_hh_ratings() -> dict[str, dict]:
    tl = json.loads(HH_TIERLIST.read_text(encoding="utf-8"))
    return {norm(r.get("name") or ""): r for r in tl if r.get("name")}


# Placeholder / role-marker names that shouldn't count as "required hero"
GENERIC_SLOTS = {
    "dps", "dps1", "dps2", "43dps", "4:3dps",
    "11dps", "11dps1", "11dps2", "1:1dps",
    "blockdebuffchamp", "cleanserdps", "stuntargettank",
    "stuntarget", "counterattack1", "counterattacker2",
    "4:3champion", "43champion", "speedbooster",
    "blockdebuff", "cleanser", "slowboi",
    # SPD-variant labels for same hero (Maneater fast/slow etc.)
    "fastmaneater", "slowmaneater", "maneaterfast", "maneaterslow",
    "counterattacker", "debuffblocker", "speedbooster1", "speedbooster2",
    "counterattacker1", "dpscleanser", "cleanserdps",
    # Abstract role labels that should allow substitution
    "blockdebuff2turnduration",
}


# Heroes that are FLEXIBLE role slots — named champions that are placeholders
# for "this role". Most DWJ tunes use generic "DPS" labels but some label
# the slot with a representative hero name to hint at the role.
ROLE_HEROES = {
    # e.g. "Drokgul" used as "Drokgul-type DPS"
}


def is_generic_slot(hero_name: str) -> bool:
    n = norm(hero_name)
    if not n:
        return True
    if n in GENERIC_SLOTS:
        return True
    # Heuristic: anything containing "dps", "cleanser", "blockdebuff",
    # "counter" under reasonable length
    if len(n) < 20 and any(k in n for k in ("dps", "cleanser", "blockdebuff", "counterattacker")):
        return True
    return False


def match_hero(hero_name: str, roster: dict[str, dict]) -> dict | None:
    key = norm(hero_name)
    hit = roster.get(key)
    if hit:
        return hit
    # Partial match both directions
    for k, v in roster.items():
        if key in k or k in key:
            return v
    return None


def slot_status(slot: dict, roster: dict[str, dict]) -> tuple[str, dict | None]:
    """Return (status, hero_entry) where status ∈
        'filled_6star' | 'filled_ascending' | 'missing' | 'generic'."""
    hero_name = slot.get("hero") or ""
    if is_generic_slot(hero_name):
        return "generic", None
    hero = match_hero(hero_name, roster)
    if hero is None:
        return "missing", None
    grade = hero.get("grade") or 0
    if grade >= 6:
        return "filled_6star", hero
    return "filled_ascending", hero


def evaluate_tune(tune: dict, roster: dict[str, dict]) -> dict:
    slots = tune.get("slots") or []
    slot_results = []
    generic_count = 0
    filled_count = 0
    ascending_count = 0
    missing_count = 0
    missing_heroes = []
    ascending_heroes = []
    filled_heroes = []
    for s in slots:
        status, hero = slot_status(s, roster)
        slot_results.append({"index": s.get("index"), "hero": s.get("hero"),
                             "status": status, "min_spd": s.get("min_spd"),
                             "max_spd": s.get("max_spd"),
                             "roster_grade": (hero or {}).get("grade")})
        if status == "generic":
            generic_count += 1
        elif status == "filled_6star":
            filled_count += 1
            filled_heroes.append(s.get("hero"))
        elif status == "filled_ascending":
            ascending_count += 1
            ascending_heroes.append((s.get("hero"), (hero or {}).get("grade")))
        else:
            missing_count += 1
            missing_heroes.append(s.get("hero"))
    return {
        "tune": tune,
        "slots": slot_results,
        "generic": generic_count,
        "filled": filled_count,
        "ascending": ascending_count,
        "missing": missing_count,
        "missing_heroes": missing_heroes,
        "ascending_heroes": ascending_heroes,
        "filled_heroes": filled_heroes,
    }


def hh_cb_score_for(hero: str, hh_ratings: dict) -> float:
    r = hh_ratings.get(norm(hero)) or {}
    try:
        return float(r.get("clan_boss") or 0)
    except (TypeError, ValueError):
        return 0


def rank_tunes(evaluated: list[dict], hh_ratings: dict) -> list[dict]:
    # Sort by: fewer missing, then higher avg HH CB score of filled heroes,
    # then tune key capability (1 key > 2 key > ...), then tune name
    key_order = {"1 Key UNM": 1, "2 Key UNM": 2, "3 Key UNM": 3, "4 Key UNM": 4, "5 Key UNM": 5}
    def sort_key(ev):
        t = ev["tune"]
        filled_score = sum(hh_cb_score_for(h, hh_ratings) for h in ev["filled_heroes"])
        return (
            ev["missing"],                 # fewer missing first
            -filled_score,                 # higher HH score first (via negative)
            key_order.get(t.get("key_capability") or "", 99),
            t.get("name") or "",
        )
    return sorted(evaluated, key=sort_key)


def format_slot_line(s: dict) -> str:
    grade = s.get("roster_grade")
    grade_str = f" [{grade}*]" if grade else ""
    hero = s.get("hero") or "?"
    spd_lo = s.get("min_spd")
    spd_hi = s.get("max_spd")
    spd = f"{spd_lo}-{spd_hi}" if spd_lo or spd_hi else "?"
    mark = {"filled_6star": "✓", "filled_ascending": "~",
            "generic": "·", "missing": "✗"}.get(s.get("status"), "?")
    return f"    {mark} slot{s.get('index')} {hero:<25} SPD {spd}{grade_str}"


def print_report(evaluated: list[dict], min_missing: int, max_missing: int, only_runnable: bool, affinity: str | None, key_cap: str | None):
    filtered = []
    for ev in evaluated:
        t = ev["tune"]
        if affinity and (t.get("affinity") or "") != affinity:
            continue
        if key_cap and (t.get("key_capability") or "") != key_cap:
            continue
        if only_runnable:
            if ev["missing"] > 0 or ev["ascending"] > 0:
                continue
        else:
            if not (min_missing <= ev["missing"] <= max_missing):
                continue
        filtered.append(ev)

    print(f"=== comp_finder: {len(filtered)} tunes match filters ===\n")
    buckets = defaultdict(list)
    for ev in filtered:
        buckets[ev["missing"]].append(ev)
    for miss_count in sorted(buckets):
        label = "RUNNABLE" if miss_count == 0 else f"{miss_count} hero(es) missing"
        print(f"\n### {label} — {len(buckets[miss_count])} tune(s)\n")
        for ev in buckets[miss_count]:
            t = ev["tune"]
            print(f"  [{t.get('key_capability','?'):<10}] [{t.get('difficulty','?'):<9}] {t.get('name')}  ({t.get('affinity')})")
            print(f"    {t.get('url')}")
            for s in ev["slots"]:
                print(format_slot_line(s))
            if ev["ascending"]:
                asc_list = ", ".join(f"{h} ({g}*)" for h, g in ev["ascending_heroes"])
                print(f"    NOTE: ascending required — {asc_list}")
            if ev["missing_heroes"]:
                print(f"    NOTE: need to acquire — {', '.join(ev['missing_heroes'])}")
            print()


def render_markdown(evaluated: list[dict]) -> str:
    lines = ["# Comp feasibility report", "",
             f"Total DWJ tunes evaluated: **{len(evaluated)}**. Generated from "
             "`heroes_all.json` + `data/dwj/parsed/tunes.json`.", "",
             "Legend: ✓ = owned at 6★  ·  ~ = owned but needs ascending  "
             "·  · = generic DPS slot (any)  ·  ✗ = not owned"]
    buckets = defaultdict(list)
    for ev in evaluated:
        buckets[ev["missing"]].append(ev)
    for miss_count in sorted(buckets):
        label = "Runnable (all slots filled)" if miss_count == 0 else f"{miss_count} hero(es) missing"
        lines.append(f"\n## {label} — {len(buckets[miss_count])} tune(s)\n")
        lines.append("| Tune | Key | Affinity | Filled | Missing |")
        lines.append("|------|-----|----------|--------|---------|")
        for ev in buckets[miss_count][:30]:
            t = ev["tune"]
            filled = ", ".join(ev["filled_heroes"]) or "—"
            missing = ", ".join(ev["missing_heroes"]) or "—"
            lines.append(
                f"| [{t.get('name')}]({t.get('url')}) | {t.get('key_capability','?')} | "
                f"{t.get('affinity','?')} | {filled} | {missing} |"
            )
        if len(buckets[miss_count]) > 30:
            lines.append(f"\n*(+{len(buckets[miss_count]) - 30} more)*")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runnable", action="store_true", help="only fully-runnable at 6★")
    ap.add_argument("--missing", type=int, help="exact number of missing named heroes")
    ap.add_argument("--max-missing", type=int, default=2, help="max missing when no --missing/--runnable")
    ap.add_argument("--affinity", help="filter by tune affinity (e.g. 'All Affinities', 'Void Only')")
    ap.add_argument("--key", help="filter by key capability (e.g. '1 Key UNM')")
    ap.add_argument("--md", help="write markdown report to this path instead of printing")
    args = ap.parse_args()

    roster = load_roster()
    tunes = load_tunes()
    hh = load_hh_ratings()

    print(f"roster size: {len(roster)} heroes; DWJ tunes: {len(tunes)}", file=sys.stderr)

    evaluated = [evaluate_tune(t, roster) for t in tunes]
    ranked = rank_tunes(evaluated, hh)

    if args.md:
        Path(args.md).write_text(render_markdown(ranked), encoding="utf-8")
        print(f"wrote {args.md}")
        return

    min_miss, max_miss = 0, args.max_missing
    if args.missing is not None:
        min_miss = max_miss = args.missing
    print_report(ranked, min_miss, max_miss, args.runnable, args.affinity, args.key)


if __name__ == "__main__":
    main()
