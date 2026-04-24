#!/usr/bin/env python3
"""DeadwoodJedi Phase 2 scraper: mine the Next.js calculator.

Every `/cb/<hash>` page on deadwoodjedi.info ships its full state inline as
`__NEXT_DATA__` — no browser / JS execution needed. Each page contains:

- `pageProps.allChampions`: metadata for all 859 champions (base stats, all 4
  skills with base + booked cooldowns, `effect` lists with structured
  `{id, amount, turns, champions, buff}` entries, `passive` lists)
- `pageProps.champions`: the 5 champions configured in THIS tune, with
  `skillConfigs` = per-skill {priority, delay, cooldown} plus total_speed /
  base_speed / speed_bonus / has_lore_of_steel
- `pageProps.clanboss`: `{speed, difficulty, affinity}` for this variant
- `pageProps.speed_aura`: aura SPD %

`allChampions` is identical across every calc page — we fetch it ONCE and then
visit each unique calc hash (251 from our 103 tunes × 4 variants) to collect
the per-tune configs.

Usage:
    python3 tools/scrape_dwj_calc.py              # fetch all 251 variants
    python3 tools/scrape_dwj_calc.py --limit 5    # only first 5 (smoke test)
    python3 tools/scrape_dwj_calc.py --only <hash>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dwj_common import DwjSession, RAW_DIR, save_manifest, write_parsed

CALC_BASE = "https://deadwoodjedi.info/cb/"
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
    re.DOTALL,
)


def extract_next_data(html_bytes: bytes) -> dict | None:
    m = NEXT_DATA_RE.search(html_bytes.decode("utf-8", errors="replace"))
    if not m:
        return None
    return json.loads(m.group(1))


def fetch_calc_hash(sess: DwjSession, hash_id: str) -> dict | None:
    """Fetch /cb/<hash>, archive raw __NEXT_DATA__ JSON, return parsed dict."""
    url = CALC_BASE + hash_id
    raw = sess.fetch_and_archive(url, Path("calc") / f"{hash_id}.html", gzipped=True)
    if raw is None:
        # 304 — read from cache
        prev = sess.manifest.get(url, {})
        if prev.get("raw_path"):
            path = RAW_DIR / prev["raw_path"]
            if path.suffix == ".gz":
                import gzip
                with gzip.open(path, "rb") as fh:
                    raw = fh.read()
            elif path.exists():
                raw = path.read_bytes()
    if not raw:
        return None
    return extract_next_data(raw)


def load_tune_hashes() -> list[tuple[str, str, str]]:
    """Return [(hash, tune_slug, variant_name)] for every unique tune+variant."""
    path = Path(__file__).resolve().parent.parent / "data" / "dwj" / "parsed" / "tunes.json"
    tunes = json.loads(path.read_text(encoding="utf-8"))
    seen_hashes = {}
    ordered = []
    for t in tunes:
        for cl in t.get("calculator_links") or []:
            h = cl.get("hash")
            if not h or h in seen_hashes:
                continue
            seen_hashes[h] = True
            ordered.append((h, t["slug"], cl.get("name") or ""))
    return ordered


def slim_tune_state(next_data: dict) -> dict:
    """Strip allChampions from per-tune state to keep the file small."""
    pp = (next_data.get("props") or {}).get("pageProps") or {}
    return {
        "build_id": next_data.get("buildId"),
        "query": next_data.get("query"),
        "clanboss": pp.get("clanboss"),
        "speed_aura": pp.get("speed_aura"),
        "champions": pp.get("champions"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=float, default=0.8, help="seconds between requests")
    ap.add_argument("--limit", type=int, default=0, help="only fetch first N hashes (smoke test)")
    ap.add_argument("--only", help="fetch exactly one hash (for debugging)")
    ap.add_argument("--skip-champions", action="store_true", help="skip the global allChampions dump")
    args = ap.parse_args()

    sess = DwjSession(rate_limit_sec=args.rate)
    hashes = load_tune_hashes()
    if args.only:
        hashes = [h for h in hashes if h[0] == args.only]
    elif args.limit:
        hashes = hashes[: args.limit]
    print(f"will fetch {len(hashes)} calc variants")

    # First hash doubles as source for allChampions
    all_champions = None
    tune_states = {}
    for i, (h, slug, variant) in enumerate(hashes):
        print(f"  [{i+1}/{len(hashes)}] {h} ({slug} / {variant})")
        try:
            nd = fetch_calc_hash(sess, h)
        except Exception as exc:
            print(f"    error: {exc}")
            continue
        if nd is None:
            print("    (no __NEXT_DATA__)")
            continue
        pp = (nd.get("props") or {}).get("pageProps") or {}
        if all_champions is None and not args.skip_champions:
            all_champions = pp.get("allChampions")
            if all_champions:
                write_parsed("calc_champions", all_champions)
                print(f"    saved allChampions ({len(all_champions)} heroes)")
        tune_states[h] = {
            "hash": h,
            "slug": slug,
            "variant": variant,
            **slim_tune_state(nd),
        }

    if tune_states:
        write_parsed("calc_tunes", tune_states)
        print(f"wrote calc_tunes.json ({len(tune_states)} entries)")

    save_manifest(sess.manifest)


if __name__ == "__main__":
    main()
