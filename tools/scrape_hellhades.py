#!/usr/bin/env python3
"""HellHades scraper — complements DWJ data with CB guides + champion metadata.

Sources:
- /wp-json/hh-api/v3/raid/export        (1013 champions: pve_sets, pve_stats,
                                          pvp_sets, blessings dict, masteries dict,
                                          book-priority, arena_roles)
- /wp-json/hh-api/v1/champions/tierlist  (per-content-mode ratings: clan_boss,
                                          hydra, chimera, spider, dragon, etc.)
- /wp-json/wp/v2/posts?per_page=100      (blog posts — filter for CB tune guides)
- /wp-json/wp/v2/pages?per_page=100      (static pages)
- sitemaps                                (URL enumeration)
- hand-picked CB tune-guide URLs         (archive HTML for extractors)

Writes:
- data/hh/raw/                 (archival, gitignored)
- data/hh/parsed/              (committed)
    champions.json             ─ HH's /raid/export flattened to one-per-champ
    tierlist.json              ─ per-content ratings
    posts.json                 ─ CB-related blog posts w/ content_html
    pages.json
    manifest.json

Usage:
    python3 tools/scrape_hellhades.py               # full refresh (incremental)
    python3 tools/scrape_hellhades.py --dry-run     # list URLs only
    python3 tools/scrape_hellhades.py --only api
    python3 tools/scrape_hellhades.py --only posts
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrape_common import SiteSession

BASE = "https://hellhades.com"

SITEMAPS = [
    "/sitemap_index.xml",
    "/post-sitemap.xml",
    "/post-sitemap2.xml",
    "/post-sitemap3.xml",
    "/page-sitemap.xml",
    "/champions-sitemap.xml",
    "/champions-sitemap2.xml",
    "/boss_guide-sitemap.xml",
]

API_ENDPOINTS = [
    ("raid_export", "/wp-json/hh-api/v3/raid/export"),
    ("tierlist", "/wp-json/hh-api/v1/champions/tierlist"),
]

# URL keywords that identify CB-related guide content
CB_KEYWORDS = (
    "clan-boss", "unkillable", "speed-tune", "myth-", "demytha", "maneater",
    "infinity-", "wixwell", "cardiel", "heartkeeper", "heiress",
    "lydia", "valkyrie", "krisk", "acrizia", "eater", "unm", "tuhanarak",
    "mikage", "lanakis", "sprite",
)


@dataclass
class HhSession(SiteSession):
    site: str = "hh"


def sitemap_urls(xml_bytes: bytes) -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", xml_bytes.decode("utf-8", errors="replace"))


def slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1] or "index"


def is_cb_related(url: str) -> bool:
    low = url.lower()
    return any(k in low for k in CB_KEYWORDS)


def scrape_sitemaps(sess: HhSession, dry_run: bool) -> dict[str, list[str]]:
    print("=== sitemaps ===")
    out = {}
    for path in SITEMAPS:
        url = BASE + path
        if dry_run:
            print(f"  would fetch {url}")
            continue
        raw = sess.fetch_and_archive(url, Path("sitemaps") / Path(path).name)
        if raw is None:
            prev = sess.manifest.get(url, {})
            if prev.get("raw_path"):
                p = sess.raw_dir / prev["raw_path"]
                if p.exists():
                    raw = p.read_bytes()
        if raw:
            urls = sitemap_urls(raw)
            out[Path(path).stem] = urls
            print(f"  {path}: {len(urls)} urls")
    return out


def scrape_api(sess: HhSession, dry_run: bool) -> dict:
    print("=== hh-api ===")
    out = {}
    for name, path in API_ENDPOINTS:
        url = BASE + path
        if dry_run:
            print(f"  would fetch {url}")
            continue
        raw = sess.fetch_and_archive(url, Path("api") / f"hh-api-{name}.json", accept_json=True)
        if raw is None:
            prev = sess.manifest.get(url, {})
            if prev.get("raw_path"):
                p = sess.raw_dir / prev["raw_path"]
                if p.exists():
                    raw = p.read_bytes()
        if raw:
            try:
                data = json.loads(raw)
                out[name] = data
                if isinstance(data, dict) and "champions" in data:
                    print(f"  {name}: {len(data['champions'])} champions")
                else:
                    print(f"  {name}: {len(data) if hasattr(data, '__len__') else '?'} records")
            except Exception as exc:
                print(f"  {name}: parse error {exc}")
    return out


def scrape_wp_posts(sess: HhSession, dry_run: bool, endpoint: str, label: str) -> list[dict]:
    """Paginated WP REST fetch; filters for CB-related content."""
    print(f"=== wp-json /wp/v2/{endpoint} (filtered: CB-related only) ===")
    all_items: list[dict] = []
    page = 1
    while True:
        url = f"{BASE}/wp-json/wp/v2/{endpoint}?per_page=100&page={page}"
        if dry_run:
            print(f"  would fetch {url}")
            if page >= 4:
                break
            page += 1
            continue
        try:
            raw = sess.fetch_and_archive(url, Path(label) / f"page-{page:02d}.json", accept_json=True)
        except RuntimeError as exc:
            print(f"  {endpoint} page {page}: stopped ({exc})")
            break
        if raw is None:
            prev = sess.manifest.get(url, {})
            if prev.get("raw_path"):
                p = sess.raw_dir / prev["raw_path"]
                if p.exists():
                    raw = p.read_bytes()
        if not raw:
            break
        try:
            items = json.loads(raw)
        except Exception as exc:
            print(f"  {endpoint} page {page}: parse error {exc}")
            break
        if not isinstance(items, list) or not items:
            break
        cb_items = [x for x in items if is_cb_related(x.get("link", ""))]
        all_items.extend(cb_items)
        print(f"  page {page}: {len(items)} items, {len(cb_items)} CB-related (cumulative CB: {len(all_items)})")
        if len(items) < 100:
            break
        page += 1
    return all_items


def normalize_champions(raid_export: dict) -> list[dict]:
    """Flatten the /raid/export payload to fields we actually use."""
    champs = raid_export.get("champions", []) if isinstance(raid_export, dict) else []
    out = []
    for c in champs:
        out.append({
            "id": c.get("id"),
            "hero_id": c.get("heroId"),
            "name": c.get("champion"),
            "url": c.get("url"),
            "faction": (c.get("faction") or "").rsplit("/", 1)[-1].split(".")[0] or None,
            "affinity": (c.get("affinity") or "").rsplit("/", 1)[-1].split(".")[0] or None,
            "rarity": c.get("rarity"),
            "book_value": c.get("book-value"),
            "book_priority": c.get("book-priority"),
            "pve_sets": c.get("pve_sets"),
            "pve_stats": c.get("pve_stats"),
            "pvp_sets": c.get("pvp_sets"),
            "pvp_stats": c.get("pvp_stats"),
            "arena_roles": c.get("arena_roles"),
            "blessings": c.get("blessings"),
            "masteries": c.get("masteries"),
            "forms": c.get("forms"),
            "youtube": c.get("youtube"),
            "last_updated": c.get("last_updated"),
        })
    return out


def normalize_tierlist(tierlist: dict) -> list[dict]:
    """Flatten ratings — one record per champion with per-mode scores."""
    champs = tierlist.get("champions", []) if isinstance(tierlist, dict) else []
    out = []
    for c in champs:
        # Copy the rating fields directly (they're already scalar)
        rec = {
            "id": c.get("id"),
            "hero_id": c.get("heroId"),
            "name": c.get("champion"),
            "faction": c.get("faction"),
            "form": c.get("form"),
            "url": c.get("url"),
        }
        for k in (
            "overall_user", "clan_boss", "hydra", "chimera", "amius", "spider",
            "dragon", "fire_knight", "ice_golem", "spider_hard", "dragon_hard",
            "fire_knight_hard", "ice_golem_hard", "iron_twins", "sand_devil",
            "phantom_grove", "kuldath", "agreth", "borgoth", "sorath", "iragoth",
            "grythion", "akumori", "hellrazor",
        ):
            if k in c:
                rec[k] = c[k]
        out.append(rec)
    return out


def normalize_posts(items: list[dict]) -> list[dict]:
    out = []
    for p in items:
        out.append({
            "id": p.get("id"),
            "slug": p.get("slug"),
            "link": p.get("link"),
            "title": (p.get("title") or {}).get("rendered"),
            "date": p.get("date"),
            "modified": p.get("modified"),
            "status": p.get("status"),
            "type": p.get("type"),
            "excerpt_html": (p.get("excerpt") or {}).get("rendered"),
            "content_html": (p.get("content") or {}).get("rendered"),
            "categories": p.get("categories"),
            "tags": p.get("tags"),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore manifest, refetch all")
    ap.add_argument("--only", choices=["sitemaps", "api", "posts", "pages"])
    ap.add_argument("--rate", type=float, default=1.0)
    args = ap.parse_args()

    sess = HhSession(rate_limit_sec=args.rate)
    if args.force:
        sess.manifest = {}

    run = lambda s: args.only is None or args.only == s

    if run("sitemaps"):
        scrape_sitemaps(sess, args.dry_run)

    api_data = {}
    if run("api"):
        api_data = scrape_api(sess, args.dry_run)

    posts = []
    if run("posts"):
        posts = scrape_wp_posts(sess, args.dry_run, "posts", "posts")
    pages = []
    if run("pages"):
        pages = scrape_wp_posts(sess, args.dry_run, "pages", "pages")

    if args.dry_run:
        return

    sess.save_manifest()

    if api_data.get("raid_export"):
        c = normalize_champions(api_data["raid_export"])
        sess.write_parsed("champions", c)
        print(f"wrote champions.json ({len(c)} champions)")
    if api_data.get("tierlist"):
        tl = normalize_tierlist(api_data["tierlist"])
        sess.write_parsed("tierlist", tl)
        print(f"wrote tierlist.json ({len(tl)} records)")
    if posts:
        sess.write_parsed("posts", normalize_posts(posts))
        print(f"wrote posts.json ({len(posts)} CB-related posts)")
    if pages:
        sess.write_parsed("pages", normalize_posts(pages))
        print(f"wrote pages.json ({len(pages)} CB-related pages)")

    print(f"manifest tracked {len(sess.manifest)} URLs")


if __name__ == "__main__":
    main()
