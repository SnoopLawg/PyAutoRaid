#!/usr/bin/env python3
"""DeadwoodJedi scrape session — thin wrapper around scrape_common.SiteSession.

Keeps the DWJ-specific data dir + provides the `DwjSession` name that
scrape_dwj.py / scrape_dwj_calc.py / dwj_tunes.py already import.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scrape_common import PROJECT_ROOT, SiteSession, USER_AGENT, DEFAULT_RATE_LIMIT_SEC

DATA_DIR = PROJECT_ROOT / "data" / "dwj"
RAW_DIR = DATA_DIR / "raw"
PARSED_DIR = DATA_DIR / "parsed"
MANIFEST_PATH = PARSED_DIR / "manifest.json"


@dataclass
class DwjSession(SiteSession):
    """DWJ scrape session — fixes site="dwj"."""
    site: str = "dwj"


def load_manifest() -> dict:
    import json
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_manifest(manifest: dict) -> None:
    import json
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def write_parsed(name: str, obj) -> Path:
    import json
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PARSED_DIR / f"{name}.json"
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
