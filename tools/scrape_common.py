#!/usr/bin/env python3
"""Generic scrape session — used by both DWJ and HellHades scrapers.

Provides a requests.Session with:
- Identifying User-Agent (PyAutoRaid-Research) so the site operator can tell who's hitting them
- Default 1 req/sec rate limit
- Exponential backoff on 429 / 5xx
- Manifest tracking (URL -> {etag, last_modified, content_hash, fetched_at})
  so incremental refreshes can 304 their way past unchanged content.

Each subclass (e.g. DwjSession, HhSession) fixes the `site` slug and
data_dir but reuses all request/archival logic.
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

USER_AGENT = "PyAutoRaid-Research/0.1 (+logan.singleton@orderprotection.com; github.com/SnoopLawg/PyAutoRaid)"
DEFAULT_RATE_LIMIT_SEC = 1.0


@dataclass
class SiteSession:
    """HTTP session with rate limiting + manifest tracking for a single site."""

    site: str = "generic"
    rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC
    session: requests.Session = field(default_factory=requests.Session)
    manifest: dict = field(default_factory=dict)
    _last_request_ts: float = 0.0

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data" / self.site

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def parsed_dir(self) -> Path:
        return self.data_dir / "parsed"

    @property
    def manifest_path(self) -> Path:
        return self.parsed_dir / "manifest.json"

    def __post_init__(self):
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/html;q=0.9, */*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
        })
        if self.manifest_path.exists():
            try:
                self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception:
                self.manifest = {}

    def get(self, url: str, *, accept_json: bool = False, timeout: int = 30) -> requests.Response:
        """GET with rate limiting + retries. Sends If-None-Match / If-Modified-Since from manifest."""
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

        raw_path is relative to raw_dir. Parent dirs auto-created.
        """
        resp = self.get(url, accept_json=accept_json)
        if resp.status_code == 304:
            print(f"  [304] {url} (cache hit)")
            return None

        data = resp.content
        full_path = self.raw_dir / raw_path
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

    def save_manifest(self) -> None:
        self.parsed_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(self.manifest, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )

    def write_parsed(self, name: str, obj) -> Path:
        """Write structured JSON to parsed_dir/<name>.json."""
        self.parsed_dir.mkdir(parents=True, exist_ok=True)
        path = self.parsed_dir / f"{name}.json"
        path.write_text(
            json.dumps(obj, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path
