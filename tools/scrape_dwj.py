#!/usr/bin/env python3
"""DeadwoodJedi Phase 1 scraper.

Fetches everything publicly exposed on deadwoodjedi.com:
- /wp-json/dwj-api/v1/tunes         (103 tunes w/ slot + calc-link metadata)
- /wp-json/dwj-api/v1/tier-list
- /wp-json/wp/v2/posts               (paginated blog posts)
- /wp-json/wp/v2/pages               (static pages: guides, calculator refs, etc.)
- speed-tune HTML pages              (for embedded guide content not in REST)
- sitemaps                           (URL enumeration + freshness)

Writes raw responses under data/dwj/raw/, normalized structured output under
data/dwj/parsed/.

Usage:
    python3 tools/scrape_dwj.py              # full fetch, incremental via manifest
    python3 tools/scrape_dwj.py --dry-run    # print URLs, no writes
    python3 tools/scrape_dwj.py --force      # ignore manifest, refetch all
    python3 tools/scrape_dwj.py --only tunes # run a single stage
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dwj_common import DwjSession, save_manifest, write_parsed

BASE = "https://deadwoodjedi.com"
SITEMAPS = [
    "/sitemap_index.xml",
    "/post-sitemap.xml",
    "/page-sitemap.xml",
    "/product-sitemap.xml",
    "/product_cat-sitemap.xml",
    "/memberpressgroup-sitemap.xml",
    "/creator_events-sitemap.xml",
]
API_ENDPOINTS = [
    ("tunes", "/wp-json/dwj-api/v1/tunes"),
    ("tier_list", "/wp-json/dwj-api/v1/tier-list"),
]


def sitemap_urls(xml_bytes: bytes) -> list[str]:
    """Extract <loc> URLs from a Yoast sitemap XML blob."""
    return re.findall(r"<loc>([^<]+)</loc>", xml_bytes.decode("utf-8", errors="replace"))


def slug_from_url(url: str) -> str:
    """Extract slug from a DWJ URL (last path segment, stripped of trailing slash)."""
    return url.rstrip("/").rsplit("/", 1)[-1] or "index"


def scrape_sitemaps(sess: DwjSession, dry_run: bool) -> dict[str, list[str]]:
    """Fetch all sitemaps, return {sitemap_name: [urls]}."""
    print("=== sitemaps ===")
    out = {}
    for path in SITEMAPS:
        url = BASE + path
        if dry_run:
            print(f"  would fetch {url}")
            continue
        raw = sess.fetch_and_archive(url, Path("sitemaps") / Path(path).name)
        if raw is None:
            # 304 — read from manifest's existing raw file
            prev = sess.manifest.get(url, {})
            if prev.get("raw_path"):
                raw_path = Path("data/dwj/raw") / prev["raw_path"]
                if raw_path.exists():
                    raw = raw_path.read_bytes()
        if raw:
            urls = sitemap_urls(raw)
            out[Path(path).stem] = urls
            print(f"  {path}: {len(urls)} urls")
    return out


def scrape_api(sess: DwjSession, dry_run: bool) -> dict:
    """Fetch DWJ custom API endpoints."""
    print("=== dwj-api ===")
    out = {}
    for name, path in API_ENDPOINTS:
        url = BASE + path
        if dry_run:
            print(f"  would fetch {url}")
            continue
        raw = sess.fetch_and_archive(url, Path("api") / f"dwj-api-v1-{name}.json", accept_json=True)
        if raw is None:
            prev = sess.manifest.get(url, {})
            if prev.get("raw_path"):
                raw_path = Path("data/dwj/raw") / prev["raw_path"]
                if raw_path.exists():
                    raw = raw_path.read_bytes()
        if raw:
            try:
                data = json.loads(raw)
                out[name] = data
                count = len(data.get("tunes", data)) if isinstance(data, dict) else len(data)
                print(f"  {name}: {count} records")
            except Exception as exc:
                print(f"  {name}: parse error {exc}")
    return out


def scrape_wp_posts(sess: DwjSession, dry_run: bool, endpoint: str, label: str) -> list[dict]:
    """Fetch all posts/pages via paginated WP REST API. endpoint = 'posts' or 'pages'."""
    print(f"=== wp-json /wp/v2/{endpoint} ===")
    all_items = []
    page = 1
    while True:
        url = f"{BASE}/wp-json/wp/v2/{endpoint}?per_page=100&page={page}&_embed=1"
        if dry_run:
            print(f"  would fetch {url}")
            if page >= 3:  # limit dry-run output
                break
            page += 1
            continue
        raw_path = Path(label) / f"page-{page:02d}.json"
        try:
            raw = sess.fetch_and_archive(url, raw_path, accept_json=True)
        except RuntimeError as exc:
            # rest_post_invalid_page_number returns 400 when page exceeds total
            print(f"  {endpoint} page {page}: {exc}")
            break
        if raw is None:
            # 304; read cached
            prev = sess.manifest.get(url, {})
            if prev.get("raw_path"):
                p = Path("data/dwj/raw") / prev["raw_path"]
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
        all_items.extend(items)
        print(f"  page {page}: {len(items)} items (cumulative {len(all_items)})")
        if len(items) < 100:
            break
        page += 1
    return all_items


def scrape_speed_tune_html(sess: DwjSession, dry_run: bool, slugs: Iterable[str]) -> None:
    """Archive the HTML of each speed tune page (for long-form notes not in REST)."""
    print("=== speed-tune HTML ===")
    for slug in slugs:
        url = f"{BASE}/speed-tune/{slug}/"
        if dry_run:
            print(f"  would fetch {url}")
            continue
        try:
            sess.fetch_and_archive(url, Path("speed-tunes") / f"{slug}.html", gzipped=True)
        except Exception as exc:
            print(f"  {slug}: {exc}")


def normalize_tunes(api_tunes: dict) -> list[dict]:
    """Flatten the /dwj-api/v1/tunes payload into a committed JSON."""
    tunes_in = api_tunes.get("tunes", []) if isinstance(api_tunes, dict) else []
    out = []
    for t in tunes_in:
        slots = []
        for i in range(1, 6):
            slot = t.get(f"Slot {i}") or {}
            slots.append({
                "index": i,
                "hero": slot.get("Name"),
                "portrait": slot.get("Portrait"),
                "min_spd": _to_int(slot.get("Min Speed")),
                "max_spd": _to_int(slot.get("Max Speed")),
                "special_rules_html": slot.get("Special Rules"),
                "mastery": slot.get("T6 Offence Mastery"),
                "relentless": _to_bool(slot.get("Relentless?")),
                "cycle_of_magic": _to_bool(slot.get("Cycle of Magic?")),
                "lasting_gifts": _to_bool(slot.get("Lasting Gifts?")),
            })
        calc_links = []
        for k in ("Link 1", "Link 2", "Link 3", "Link 4"):
            link = t.get(k)
            if isinstance(link, dict) and link.get("Calculator Link"):
                calc_links.append({
                    "name": link.get("Name"),
                    "hash": link.get("Calculator Link"),
                    "url": f"https://deadwoodjedi.info/cb/{link['Calculator Link']}",
                })
        community_videos = [v for v in (t.get("Community Video 1"), t.get("Community Video 2")) if v]
        out.append({
            "id": t.get("id"),
            "name": t.get("Name"),
            "slug": slug_from_url(t.get("Url", "")),
            "url": t.get("Url"),
            "type": t.get("Type"),
            "difficulty": t.get("Difficulty"),
            "key_capability": t.get("Key Capability"),
            "affinity": t.get("Affinity"),
            "created_by": t.get("Created By"),
            "description": t.get("Description"),
            "notes_html": t.get("Notes"),
            "slots": slots,
            "youtube_id": t.get("Youtube"),
            "calculator_links": calc_links,
            "community_videos": community_videos,
        })
    return out


def normalize_tier_list(api_tier: dict) -> list[dict]:
    items = api_tier.get("tunes", []) if isinstance(api_tier, dict) else []
    # Tier list has similar shape but may include tier/rank field
    out = []
    for t in items:
        out.append({
            "id": t.get("id"),
            "name": t.get("Name"),
            "url": t.get("Url"),
            "tier": t.get("Tier") or t.get("tier"),
            "raw": t,  # keep full record; we'll trim when we understand the extra fields
        })
    return out


def normalize_posts(items: list[dict]) -> list[dict]:
    """Flatten WP post/page records to the fields we actually use."""
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


def _to_int(v):
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None or v == "" or v == "None":
        return None
    if isinstance(v, str):
        return v.strip().lower() in ("true", "yes", "1")
    return bool(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print URLs, don't fetch")
    ap.add_argument("--force", action="store_true", help="ignore manifest etags, refetch all")
    ap.add_argument("--only", choices=["sitemaps", "api", "posts", "pages", "tunes-html"],
                    help="run only the named stage")
    ap.add_argument("--rate", type=float, default=1.0, help="seconds between requests")
    args = ap.parse_args()

    sess = DwjSession(rate_limit_sec=args.rate)
    if args.force:
        sess.manifest = {}

    run = lambda stage: args.only is None or args.only == stage

    sm_urls = {}
    if run("sitemaps"):
        sm_urls = scrape_sitemaps(sess, args.dry_run)

    api_data = {}
    if run("api"):
        api_data = scrape_api(sess, args.dry_run)

    posts = []
    if run("posts"):
        posts = scrape_wp_posts(sess, args.dry_run, "posts", "posts")

    pages = []
    if run("pages"):
        pages = scrape_wp_posts(sess, args.dry_run, "pages", "pages")

    if run("tunes-html"):
        # Speed-tune slugs from the page sitemap (under /speed-tune/ singular)
        tune_slugs = []
        for url in sm_urls.get("page-sitemap", []):
            if "/speed-tune/" in url and url != f"{BASE}/speed-tune/":
                tune_slugs.append(slug_from_url(url))
        # Also derive from tunes API (uses /speed-tunes/ plural)
        for t in api_data.get("tunes", {}).get("tunes", []) if isinstance(api_data.get("tunes"), dict) else []:
            url = t.get("Url", "")
            if url:
                tune_slugs.append(slug_from_url(url))
        tune_slugs = sorted(set(tune_slugs))
        scrape_speed_tune_html(sess, args.dry_run, tune_slugs)

    # Persist normalized JSON
    if not args.dry_run:
        save_manifest(sess.manifest)
        if api_data.get("tunes"):
            tunes_norm = normalize_tunes(api_data["tunes"])
            p = write_parsed("tunes", tunes_norm)
            print(f"wrote {p} ({len(tunes_norm)} tunes)")
        if api_data.get("tier_list"):
            tl_norm = normalize_tier_list(api_data["tier_list"])
            p = write_parsed("tier_list", tl_norm)
            print(f"wrote {p} ({len(tl_norm)} entries)")
        if posts:
            p = write_parsed("posts", normalize_posts(posts))
            print(f"wrote {p} ({len(posts)} posts)")
        if pages:
            p = write_parsed("pages", normalize_posts(pages))
            print(f"wrote {p} ({len(pages)} pages)")
        print(f"manifest: {len(sess.manifest)} URLs tracked")


if __name__ == "__main__":
    main()
