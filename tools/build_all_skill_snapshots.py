"""Extract depth-8 static-data snapshots for EVERY skill in the game (not
just owned-hero skills). Merges into existing all_skills_depth8.json.

Source of skill_ids: `data/static/hero_types.json` skill_ids[] + leader_skills[]
across all 8177 hero rows (1307 unique base heroes, 1132 unique names).

Output: same file `data/static/snapshots/all_skills_depth8.json` (combined).
The per-hero by_hero/ files keep the owned-hero subset since hero_types
doesn't have hero names mapped per-skill cleanly.

Usage:
    python3 tools/build_all_skill_snapshots.py
    python3 tools/build_all_skill_snapshots.py --force  # re-fetch existing
"""
from __future__ import annotations
import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HERO_TYPES = PROJECT_ROOT / "data" / "static" / "hero_types.json"
OUT_FILE = PROJECT_ROOT / "data" / "static" / "snapshots" / "all_skills_depth8.json"
MOD_BASE = "http://localhost:6790"


def fetch_skill(skill_id: int, retries: int = 2):
    url = (f"{MOD_BASE}/static-export?path=SkillData.SkillTypeById."
           f"Item%5B{skill_id}%5D&depth=8")
    last_err = None
    for _ in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            time.sleep(1.0)
    raise RuntimeError(f"fetch sid={skill_id} failed: {last_err}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="Re-fetch skills already in the snapshot")
    args = ap.parse_args()

    ht = json.loads(HERO_TYPES.read_text(encoding="utf-8"))
    rows = ht.get("hero_types") or []

    all_ids: set[int] = set()
    for h in rows:
        for sid in (h.get("skill_ids") or []):
            if isinstance(sid, int):
                all_ids.add(sid)
        for sid in (h.get("leader_skills") or []):
            if isinstance(sid, int):
                all_ids.add(sid)
    print(f"hero_types entries: {len(rows)}")
    print(f"Unique skill_ids across the universe: {len(all_ids)}")

    # Load existing snapshot to merge into
    if OUT_FILE.exists():
        existing_doc = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        existing_skills = existing_doc.get("skills") or {}
    else:
        existing_skills = {}
    have_ids = {int(k) for k in existing_skills.keys()}
    if args.force:
        to_fetch = sorted(all_ids)
    else:
        to_fetch = sorted(all_ids - have_ids)
    print(f"Already in snapshot: {len(have_ids)}")
    print(f"To fetch: {len(to_fetch)}")
    if not to_fetch:
        print("Nothing to do.")
        return 0

    # Verify mod
    try:
        with urllib.request.urlopen(f"{MOD_BASE}/status", timeout=5) as r:
            json.loads(r.read())
    except Exception as e:
        print(f"mod unreachable: {e}")
        return 1

    failures: list[tuple[int, str]] = []
    progress_every = 200

    for i, sid in enumerate(to_fetch, 1):
        try:
            skill = fetch_skill(sid)
            existing_skills[str(sid)] = skill
        except Exception as e:
            failures.append((sid, str(e)[:80]))
        if i % progress_every == 0:
            print(f"  {i}/{len(to_fetch)} fetched ({len(failures)} fails) "
                  f"-- total now {len(existing_skills)}")

    payload = {
        "_meta": {
            "source": "live mod /static-export depth=8",
            "skill_count": len(existing_skills),
            "universe_skill_ids": len(all_ids),
            "fetch_failures_this_run": len(failures),
        },
        "skills": existing_skills,
    }
    OUT_FILE.write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote: {OUT_FILE} ({len(existing_skills)} skills)")
    if failures:
        print(f"\n{len(failures)} fetch failures:")
        for sid, err in failures[:10]:
            print(f"  {sid}: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
