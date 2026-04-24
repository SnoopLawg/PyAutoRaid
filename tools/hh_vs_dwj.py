#!/usr/bin/env python3
"""Cross-reference HellHades data against DeadwoodJedi scrape.

Produces three reports:

1. **CB-top HH champions missing from DWJ tunes** — HH-rated CB=5 champions
   that no DWJ tune lists in any slot. These are candidates for new tunes or
   user research.

2. **HH CB posts grouped by topic** — 92 filtered posts indexed so the user
   can browse for specific tune writeups DWJ doesn't carry.

3. **User-roster gear/blessings snapshot** — for each champion the user
   owns (see memory/user_cb_roster.md), print HH's PvE sets/stats/blessings/
   masteries recommendations.

Usage:
    python3 tools/hh_vs_dwj.py
    python3 tools/hh_vs_dwj.py --roster-only
    python3 tools/hh_vs_dwj.py --posts-only
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HH_DIR = PROJECT_ROOT / "data" / "hh" / "parsed"
DWJ_DIR = PROJECT_ROOT / "data" / "dwj" / "parsed"

# User's roster is auto-derived from heroes_all.json (mod API dump).
# Override via USER_FUSABLE for champions they don't own but can fuse.
HEROES_ALL_PATH = PROJECT_ROOT / "heroes_all.json"
USER_FUSABLE = ["Lady Mikage"]


def _norm(s: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _load_user_roster() -> dict[str, dict]:
    """Return {normalized_name: hero_dict} for owned heroes at max grade."""
    if not HEROES_ALL_PATH.exists():
        return {}
    data = load_json(HEROES_ALL_PATH)
    heroes = data.get("heroes", []) if isinstance(data, dict) else []
    by_name = {}
    for h in heroes:
        nm = h.get("name") or ""
        key = _norm(nm)
        if not key:
            continue
        prev = by_name.get(key)
        if not prev:
            by_name[key] = h
            continue
        # keep highest (grade, level, empower)
        cur_rank = (h.get("grade", 0), h.get("level", 0), h.get("empower", 0))
        prev_rank = (prev.get("grade", 0), prev.get("level", 0), prev.get("empower", 0))
        if cur_rank > prev_rank:
            by_name[key] = h
    return by_name


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def heroes_in_dwj_tunes() -> set[str]:
    """Collect every hero name that appears in any DWJ tune slot."""
    tunes = load_json(DWJ_DIR / "tunes.json")
    heroes = set()
    for t in tunes:
        for s in t.get("slots", []) or []:
            name = (s.get("hero") or "").strip()
            if name and name.upper() != "DPS":
                heroes.add(name)
    return heroes


def hh_top_cb_champions(min_rating: float = 5.0):
    tl = load_json(HH_DIR / "tierlist.json")
    out = []
    for r in tl:
        cb = r.get("clan_boss")
        try:
            cb = float(cb)
        except (TypeError, ValueError):
            continue
        if cb >= min_rating:
            out.append({
                "name": r.get("name"),
                "cb": cb,
                "overall": r.get("overall_user"),
                "faction": r.get("faction"),
                "url": r.get("url"),
            })
    out.sort(key=lambda r: (-r["cb"], -(r.get("overall") or 0), r["name"]))
    return out


def cb_champions_missing_from_dwj() -> list[dict]:
    dwj_heroes = heroes_in_dwj_tunes()
    top = hh_top_cb_champions()
    missing = [c for c in top if c["name"] not in dwj_heroes]
    return missing


def classify_post(title: str, slug: str) -> str:
    t = (title or "").lower() + " " + (slug or "").lower()
    buckets = [
        ("Unkillable tune", ["unkillable", "myth-eater", "bateater", "maneater", "demytha"]),
        ("Infinity / Shield", ["infinity", "wixwell", "brogni", "shield"]),
        ("Heiress / Myth Heir", ["heiress", "myth-heir"]),
        ("Counter Attack / 2:1", ["counter-attack", "counter attack", "2-1", "2:1", "ally-attack", "cardiel", "lanakis"]),
        ("Poison / Debuff", ["poison", "debuff", "poison-sensitivity", "venomage"]),
        ("Fusion / event", ["fusion", "summoning event", "vault keeper", "x10-maneater", "x10-cardiel"]),
        ("Hydra (not CB)", ["hydra"]),
        ("New champion reveal", ["new clan boss", "skills-announced", "skillset", "spotlight"]),
        ("General guide", ["guide", "how-to", "master-class", "best-", "top-", "update", "challenge"]),
    ]
    for label, keys in buckets:
        if any(k in t for k in keys):
            return label
    return "Other"


def print_missing_cb_champions():
    missing = cb_champions_missing_from_dwj()
    print(f"=== CB=5 champions (per HellHades) that NO DWJ tune uses ({len(missing)}) ===\n")
    for c in missing:
        print(f"  {c['name']:<30} CB={c['cb']}  overall={c.get('overall','?')}  ({c.get('faction','?')})")
    print("\nThese are gap candidates — champions HH ranks top-tier for CB that our")
    print("DWJ scrape of 103 tunes doesn't place in any slot. Either DWJ's covered")
    print("under a different hero name (check HH's URL slug) or there's no public")
    print("DWJ tune for them yet.\n")


def print_hh_cb_posts():
    posts = load_json(HH_DIR / "posts.json")
    by_bucket = defaultdict(list)
    for p in posts:
        bucket = classify_post(p.get("title"), p.get("slug"))
        by_bucket[bucket].append(p)
    print(f"=== HH CB posts ({len(posts)}) grouped by topic ===\n")
    for bucket in sorted(by_bucket):
        items = sorted(by_bucket[bucket], key=lambda p: p.get("date") or "", reverse=True)
        print(f"\n--- {bucket} ({len(items)}) ---")
        for p in items:
            title = html.unescape(p.get("title") or "")
            date = (p.get("date") or "")[:10]
            print(f"  [{date}]  {title}")
            print(f"    {p.get('link')}")


def print_roster_snapshot(min_cb: float = 4.0):
    """Build from heroes_all.json — show every owned hero with CB >= min_cb,
    plus any fusable additions."""
    champs = load_json(HH_DIR / "champions.json")
    tl = load_json(HH_DIR / "tierlist.json")
    champs_by_norm = {_norm(c["name"]): c for c in champs}
    ratings_by_norm = {_norm(r["name"]): r for r in tl}
    owned = _load_user_roster()

    def show(hero_entry: dict | None, name: str, label: str):
        key = _norm(name)
        c = champs_by_norm.get(key)
        r = ratings_by_norm.get(key)
        if not c:
            # try partial
            for nkey, rec in champs_by_norm.items():
                if key in nkey or nkey in key:
                    c = rec; r = ratings_by_norm.get(nkey); break
        if not c:
            print(f"\n  [{label}] {name}: not in HH data"); return
        cb = (r or {}).get("clan_boss", "?")
        overall = (r or {}).get("overall_user", "?")
        bl = c.get("blessings") or {}
        masteries = c.get("masteries") or {}
        mast_pve = masteries.get("pve") if isinstance(masteries, dict) else None
        grade = (hero_entry or {}).get("grade", "?")
        empower = (hero_entry or {}).get("empower", 0)
        grade_str = f"{grade}*" + (f"+{empower}" if empower else "")
        print(f"\n  [{label} {grade_str}] {c['name']}  ({c.get('rarity')} {c.get('affinity')}  faction={c.get('faction')})")
        print(f"    CB: {cb}   overall: {overall}")
        print(f"    PvE sets:   {c.get('pve_sets')}")
        print(f"    PvE stats:  {c.get('pve_stats')}")
        print(f"    Blessings:  pve_low={bl.get('blessing_pve_low')}  pve_high={bl.get('blessing_pve_high')}  alt={bl.get('blessing_pve_alternate')}")
        if mast_pve:
            preview = str(mast_pve)[:160]
            print(f"    Masteries PvE (truncated): {preview}...")

    # Gather owned heroes with CB >= min_cb
    rows = []
    for key, hero in owned.items():
        r = ratings_by_norm.get(key)
        if not r:
            # partial match
            for nkey, rec in ratings_by_norm.items():
                if key in nkey or nkey in key:
                    r = rec; break
        if not r:
            continue
        try:
            cb = float(r.get("clan_boss") or 0)
        except (TypeError, ValueError):
            cb = 0
        if cb < min_cb:
            continue
        rows.append((cb, r.get("overall_user", 0) or 0, hero, r.get("name")))

    rows.sort(key=lambda x: (-x[0], -x[1], x[3]))
    print(f"=== Owned CB-viable roster (CB >= {min_cb}, {len(rows)} heroes) ===")
    for cb, ovr, hero, hh_name in rows:
        show(hero, hh_name, "OWNED")

    print("\n\n=== Fusable (not yet owned, user can obtain) ===")
    for name in USER_FUSABLE:
        show(None, name, "FUSABLE")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--missing-only", action="store_true")
    ap.add_argument("--posts-only", action="store_true")
    ap.add_argument("--roster-only", action="store_true")
    args = ap.parse_args()

    if args.missing_only:
        print_missing_cb_champions()
        return
    if args.posts_only:
        print_hh_cb_posts()
        return
    if args.roster_only:
        print_roster_snapshot()
        return

    print_missing_cb_champions()
    print()
    print_roster_snapshot()
    print()
    print_hh_cb_posts()


if __name__ == "__main__":
    main()
