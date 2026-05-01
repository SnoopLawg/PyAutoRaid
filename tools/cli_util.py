"""Shared CLI helpers for tools/*.py scripts.

Common boilerplate that every CLI entrypoint needed:
- project_root() — locate the repo root from any tool file
- ensure_path(root) — make tools/ + root importable when run as a script
- fetch_heroes_from_mod() — live-pull /all-heroes (returns [] on error)

Keep this file tiny. Anything bigger probably belongs in a domain module.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

DEFAULT_MOD_URL = "http://localhost:6790"


def project_root() -> Path:
    """Repo root (parent of `tools/`). Works from any tools/ script."""
    return Path(__file__).resolve().parent.parent


def ensure_path(root: Path | None = None) -> Path:
    """Add root + root/tools to sys.path so `import <toolname>` works when
    the script was run via `python3 tools/<x>.py`. Returns the root."""
    root = root or project_root()
    for p in (str(root), str(root / "tools")):
        if p not in sys.path:
            sys.path.insert(0, p)
    return root


def fetch_heroes_from_mod(mod_url: str = DEFAULT_MOD_URL,
                          timeout: int = 30) -> list[dict]:
    """Live-pull /all-heroes from the mod. Returns [] on any error.
    Used by CLI scripts that need to enrich battle logs / artifacts /
    etc. with current per-hero data without going through Modules.mod_client.
    """
    try:
        with urllib.request.urlopen(f"{mod_url}/all-heroes", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")).get("heroes", [])
    except Exception:
        return []
