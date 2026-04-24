# DeadwoodJedi scrape

Archive + normalized copy of public DeadwoodJedi content, refreshed on demand.

## Source

https://deadwoodjedi.com — all content pulled from the site's public JSON APIs + sitemaps + speed-tune HTML. Non-commercial personal-use archive; original authorship belongs to DWJ and contributors.

## Layout

```
data/dwj/
  raw/              # gitignored: archival HTML.gz + JSON responses
  parsed/
    tunes.json      # 103 speed tunes (id, slots with SPDs + masteries, calculator hashes)
    tier_list.json  # 40 curated tunes w/ tier metadata
    posts.json      # 155 blog posts (title, slug, content_html)
    pages.json      # static pages (guides, calculator references)
    manifest.json   # URL -> etag/content_hash/fetched_at for incremental refresh
docs/dwj/
  tunes_index.md    # human-readable index grouped by type
  tunes/<slug>.md   # per-tune writeup (slots table, slot rules, notes, calc links, videos)
  legacy/           # pre-scrape hand-maintained DWJ notes (kept for diffing)
```

## Refresh

```bash
# Full refresh (incremental — uses manifest etags)
python3 tools/scrape_dwj.py

# Drill into one stage
python3 tools/scrape_dwj.py --only api
python3 tools/scrape_dwj.py --only tunes-html

# Ignore manifest, refetch everything
python3 tools/scrape_dwj.py --force

# Regenerate the markdown docs after a scrape
python3 tools/render_dwj_docs.py
```

The scraper respects DWJ's `robots.txt`, rate-limits at 1 req/sec, and identifies itself via `User-Agent: PyAutoRaid-Research/0.1`.

## What's not archived

- `/wp-admin/`, `/mp/v1/` (MemberPress) — paywalled course content. Requests return 401 for non-members; no auth bypass.
- WooCommerce shop product detail (irrelevant to sim calibration).
- Images / video. Only text + structured data.

## Phase 2 (planned)

`tools/scrape_dwj_calc.py` will use Claude-in-Chrome MCP tools to mine the `deadwoodjedi.info` calculator's Next.js bundle for champion base stats, skill cooldowns, and turn-meter passive rules — so our sim can model cases like Ninja's A2 passive TM fill without per-hero hardcoding.
