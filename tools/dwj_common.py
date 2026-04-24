#!/usr/bin/env python3
"""Shared HTTP client + manifest helpers for DeadwoodJedi scraping.

All DWJ scrapers go through get_session() for:
- Identifying User-Agent so DWJ's ops can tell who's hitting them
- Default 1 req/sec rate limit
- Exponential backoff on 429 / 5xx
- Manifest tracking (URL -> {etag, last_modified, content_hash, fetched_at})
  so incremental refreshes can 304 their way past unchanged content.

Raw archival lives under data/dwj/raw/, normalized output under data/dwj/parsed/.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "dwj"
RAW_DIR = DATA_DIR / "raw"
PARSED_DIR = DATA_DIR / "parsed"
MANIFEST_PATH = PARSED_DIR / "manifest.json"

USER_AGENT = "PyAutoRaid-Research/0.1 (+logan.singleton@orderprotection.com; github.com/SnoopLawg/PyAutoRaid)"
DEFAULT_RATE_LIMIT_SEC = 1.0


@dataclass
class DwjSession:
    """HTTP session with rate limiting + manifest tracking."""

    rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC
    session: requests.Session = field(default_factory=requests.Session)
    manifest: dict = field(default_factory=dict)
    _last_request_ts: float = 0.0

    def __post_init__(self):
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/html;q=0.9, */*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.manifest = load_manifest()

    def get(self, url: str, *, accept_json: bool = False, timeout: int = 30) -> requests.Response:
        """GET with rate limiting + retries.

        Sends If-None-Match / If-Modified-Since from manifest for 304 short-circuits.
        """
        elapsed = time.time() - self._last_request_ts
        if elapsed < self.rate_limit_sec:
            time.sleep(self.rate_limit_sec - elapsed)

        headers = {}
        if accept_json:
            headers["Accept"] = "application/json"
        prev = self.manifest.get(url) or {}
        if prev.get("etag"):
            headers["If-None-Match"] = prev["etag"]
        if prev.get("last_modified"):
            headers["If-Modified-Since"] = prev["last_modified"]

        last_exc = None
        for attempt in range(5):
            try:
                resp = self.session.get(url, headers=headers, timeout=timeout)
                self._last_request_ts = time.time()
                if resp.status_code == 304:
                    return resp
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    print(f"  [{resp.status_code}] retrying {url} in {delay:.1f}s (attempt {attempt+1}/5)")
                    time.sleep(delay)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                delay = (2 ** attempt) + random.uniform(0, 1)
                print(f"  [err {type(exc).__name__}] retrying {url} in {delay:.1f}s")
                time.sleep(delay)
        raise RuntimeError(f"GET {url} failed after 5 attempts: {last_exc}")

    def fetch_and_archive(
        self,
        url: str,
        raw_path: Path,
        *,
        accept_json: bool = False,
        gzipped: bool = False,
    ) -> Optional[bytes]:
        """Fetch URL, archive raw response, update manifest. Returns response bytes or None if 304.

        raw_path is relative to RAW_DIR. Parent dirs auto-created.
        """
        resp = self.get(url, accept_json=accept_json)
        if resp.status_code == 304:
            print(f"  [304] {url} (cache hit)")
            return None

        data = resp.content
        full_path = RAW_DIR / raw_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if gzipped:
            full_path = full_path.with_suffix(full_path.suffix + ".gz")
            with gzip.open(full_path, "wb") as fh:
                fh.write(data)
        else:
            full_path.write_bytes(data)

        self.manifest[url] = {
            "etag": resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
            "content_hash": hashlib.sha256(data).hexdigest(),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": resp.status_code,
            "size": len(data),
            "raw_path": str(raw_path),
        }
        return data


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_manifest(manifest: dict) -> None:
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def write_parsed(name: str, obj) -> Path:
    """Write structured JSON to data/dwj/parsed/<name>.json; returns the path."""
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PARSED_DIR / f"{name}.json"
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
