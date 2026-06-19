"""Extract depth-8 static-data snapshots for every owned-hero skill.

Output: `data/static/snapshots/all_skills_depth8.json` — a single dict keyed
by skill_type_id (str) with the full IL2CPP Effects array per skill.

This is the foundation for first-principles skill modeling — every kind,
condition, target type, multiplier formula, and Relation flag is preserved.
The sim's load_game_profiles.py can then translate these systematically.

Usage:
    python3 tools/build_skill_snapshots.py
    # → data/static/snapshots/all_skills_depth8.json
    # → also per-hero files in data/static/snapshots/by_hero/<Name>.json
"""
from __future__ import annotations
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DB = PROJECT_ROOT / "skills_db.json"
HEROES_ALL = PROJECT_ROOT / "heroes_all.json"
OUT_DIR = PROJECT_ROOT / "data" / "static" / "snapshots"
OUT_ALL = OUT_DIR / "all_skills_depth8.json"
OUT_BY_HERO = OUT_DIR / "by_hero"
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
    raise RuntimeError(f"fetch skill_id={skill_id} failed: {last_err}")


def main() -> int:
    heroes_all = json.loads(HEROES_ALL.read_text(encoding="utf-8"))["heroes"]
    skills_db = json.loads(SKILLS_DB.read_text(encoding="utf-8"))

    # Build hero -> [skill_ids] map. skills_db has per-hero arrays.
    hero_skills: dict[str, set[int]] = {}
    for hero_name, skills in skills_db.items():
        ids = set()
        for s in skills:
            if isinstance(s, dict):
                sid = s.get("skill_type_id")
                if isinstance(sid, int):
                    ids.add(sid)
        if ids:
            hero_skills[hero_name] = ids

    # Verify mod is up
    try:
        with urllib.request.urlopen(f"{MOD_BASE}/status", timeout=5) as r:
            json.loads(r.read())
    except Exception as e:
        print(f"mod unreachable: {e}")
        return 1

    # Unique skill_ids to fetch
    all_ids = set()
    for ids in hero_skills.values():
        all_ids.update(ids)
    sorted_ids = sorted(all_ids)
    print(f"Heroes: {len(hero_skills)}")
    print(f"Unique skill_ids: {len(sorted_ids)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_BY_HERO.mkdir(parents=True, exist_ok=True)

    all_skills: dict[str, dict] = {}
    failures: list[tuple[int, str]] = []
    every_n = 100
    for i, sid in enumerate(sorted_ids, 1):
        try:
            skill = fetch_skill(sid)
            all_skills[str(sid)] = skill
        except Exception as e:
            failures.append((sid, str(e)[:80]))
        if i % every_n == 0:
            print(f"  {i}/{len(sorted_ids)} fetched ({len(failures)} failures)")

    # Save the combined file
    payload = {
        "_meta": {
            "source": "live mod /static-export depth=8",
            "skill_count": len(all_skills),
            "failures": len(failures),
        },
        "skills": all_skills,
    }
    OUT_ALL.write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote: {OUT_ALL} ({len(all_skills)} skills)")

    # Per-hero files for easier browsing/diff
    for hero_name, sids in hero_skills.items():
        hero_payload = {
            "_meta": {"hero": hero_name, "skill_count": len(sids)},
            "skills": {str(sid): all_skills.get(str(sid))
                       for sid in sids if str(sid) in all_skills},
        }
        safe_name = hero_name.replace("/", "_").replace(" ", "_")
        (OUT_BY_HERO / f"{safe_name}.json").write_text(
            json.dumps(hero_payload, indent=2, default=str), encoding="utf-8")
    print(f"wrote: {OUT_BY_HERO}/ ({len(hero_skills)} files)")

    if failures:
        print(f"\n{len(failures)} failures:")
        for sid, err in failures[:10]:
            print(f"  {sid}: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
