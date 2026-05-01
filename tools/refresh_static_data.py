"""Refresh canonical static reference data from the live mod.

Pulls every static endpoint the mod exposes and writes a versioned JSON to
data/static/. This is the single source of truth for the rest of the
project — sim, dashboard, optimizer all read from here. Each output file
includes a `_meta` block with timestamp + game scene at fetch time.

Usage:
    python3 tools/refresh_static_data.py            # pull all
    python3 tools/refresh_static_data.py --section masteries blessings
    python3 tools/refresh_static_data.py --check    # report stale files

Sections (tracked in SECTIONS below):
    masteries — mastery tree definitions, stat bonuses by mastery_id
    blessings — blessing values keyed by blessing id
    drops     — per-region/per-difficulty artifact set drops
    forge_sets — forge crafting set list
    revision  — game revision + scene + fetch timestamp

Future sections (see docs/static_data_roadmap.md):
    bosses    — per-stage boss stats (HP/ATK/DEF/SPD/CR/CD/RES/ACC)
    effects   — buff/debuff catalog (id → name + properties)
    sets      — artifact set bonus definitions
    heroes    — base stats per hero type
    skills    — full skill schemas
    gameplay  — global tunables
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "static"
MOD_BASE = "http://localhost:6790"

# Each section: (filename, mod path, optional transform fn).
# Transform fn receives the parsed JSON; returns a (possibly-restructured)
# dict that gets written. Wrap raw dumps with _meta automatically.
SECTIONS: dict = {
    "masteries":  ("masteries.json",  "/masteries-truth", None),
    "blessings":  ("blessings.json",  "/blessings-truth", None),
    "drops":      ("drops.json",      "/dungeon-drops",   None),
    "forge_sets": ("forge_sets.json", "/forge-sets",      None),
}


def _get(path: str, timeout: int = 90) -> dict:
    url = MOD_BASE + path
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _status() -> dict | None:
    try:
        return _get("/status", timeout=5)
    except Exception:
        return None


def _wrap_meta(payload: dict, mod_status: dict | None) -> dict:
    """Add _meta block: timestamp, scene, mod version. Keep payload flat
    under remaining keys so consumers don't have to re-key."""
    meta = {
        "fetched_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "scene": (mod_status or {}).get("scene"),
        "mod_version": (mod_status or {}).get("version"),
        "unity": (mod_status or {}).get("unity"),
    }
    if isinstance(payload, dict):
        out = {"_meta": meta}
        out.update(payload)
        return out
    # Wrap non-dict payloads under "data"
    return {"_meta": meta, "data": payload}


def fetch_section(name: str, mod_status: dict | None) -> tuple[Path, dict] | None:
    if name not in SECTIONS:
        print(f"  [skip] unknown section {name!r}", file=sys.stderr)
        return None
    filename, mod_path, transform = SECTIONS[name]
    try:
        raw = _get(mod_path)
    except urllib.error.URLError as e:
        print(f"  [err] {name}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  [err] {name}: {type(e).__name__}: {e}", file=sys.stderr)
        return None
    if isinstance(raw, dict) and raw.get("error"):
        print(f"  [err] {name}: mod returned {raw['error']!r}", file=sys.stderr)
        return None
    payload = transform(raw) if transform else raw
    out = _wrap_meta(payload, mod_status)
    target = DATA_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2))
    return target, out


def write_revision(mod_status: dict | None) -> Path:
    """Tiny pin file so consumers can detect when mod version changed."""
    out = {
        "_meta": {
            "fetched_at": datetime.datetime.now(datetime.UTC).isoformat(),
        },
        "scene": (mod_status or {}).get("scene"),
        "mod_version": (mod_status or {}).get("version"),
        "unity": (mod_status or {}).get("unity"),
    }
    target = DATA_DIR / "revision.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2))
    return target


def check_freshness(stale_minutes: int = 60 * 24) -> int:
    """Report which files are stale or missing. Exit code 1 if any are."""
    import time
    cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=stale_minutes)
    stale: list[str] = []
    for name, (filename, _, _) in SECTIONS.items():
        path = DATA_DIR / filename
        if not path.exists():
            stale.append(f"{name} (missing)")
            continue
        try:
            obj = json.loads(path.read_text())
            ts = obj.get("_meta", {}).get("fetched_at")
            if not ts:
                stale.append(f"{name} (no _meta)")
                continue
            fetched = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if fetched < cutoff:
                age_h = (datetime.datetime.now(datetime.UTC) - fetched).total_seconds() / 3600
                stale.append(f"{name} ({age_h:.1f}h old)")
        except Exception as e:
            stale.append(f"{name} (parse: {e})")
    if stale:
        print(f"Stale or missing ({len(stale)}):")
        for s in stale:
            print(f"  - {s}")
        return 1
    print(f"All {len(SECTIONS)} static-data sections fresh.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--section", nargs="*",
                    help=f"sections to refresh (default all: {','.join(SECTIONS)})")
    ap.add_argument("--check", action="store_true",
                    help="report stale files (exit 1 if any are stale)")
    ap.add_argument("--stale-minutes", type=int, default=60 * 24,
                    help="threshold for --check (default: 24h)")
    args = ap.parse_args()

    if args.check:
        return check_freshness(args.stale_minutes)

    mod = _status()
    if mod is None:
        print("ERR: mod not reachable at " + MOD_BASE, file=sys.stderr)
        return 2
    if not mod.get("logged_in"):
        print("WARN: mod available but logged_in=False; static data may be empty",
              file=sys.stderr)

    sections = args.section or list(SECTIONS.keys())
    print(f"Refreshing {len(sections)} sections (mod {mod.get('version')}, scene {mod.get('scene')})")
    refreshed: list[str] = []
    failed: list[str] = []
    for name in sections:
        result = fetch_section(name, mod)
        if result:
            path, data = result
            size_kb = path.stat().st_size / 1024
            count = ""
            for k, v in data.items():
                if k == "_meta":
                    continue
                if isinstance(v, list):
                    count = f" ({len(v)} items)"
                    break
                if isinstance(v, dict):
                    count = f" ({len(v)} keys)"
                    break
            print(f"  {name:12s} → {path.relative_to(PROJECT_ROOT)}  {size_kb:.1f}KB{count}")
            refreshed.append(name)
        else:
            failed.append(name)

    rev = write_revision(mod)
    print(f"  revision     → {rev.relative_to(PROJECT_ROOT)}")

    print(f"\nRefreshed {len(refreshed)} sections" +
          (f", {len(failed)} failed" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
