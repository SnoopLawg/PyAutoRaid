"""Build a glance-gate lookup: for every skill referenced by hero_profiles_game.json,
record which effect indices have `Relation.ActivateOnGlancingHit == False`.

Output: data/static/glance_gates.json
  {
    "skill_id": [list of glance-gated effect indices],
    ...
  }

Glance gates are the mechanism by which weak-affinity attacks "miss" secondary
effects (TM boosts, debuff placements, DoT applications). On a glance:
  - The damage roll still applies (at glance penalty, -30% per gameplay.json)
  - Effects with ActivateOnGlancingHit=false are SKIPPED for that cast

For MEN's Force-day failure, this is the missing model component — Ninja and
Venomage glance ~35% on Force boss, suppressing their debuff/TM contributions
and breaking the BD/UK cycle indirectly via lower damage and missed DEC DEF.

Usage:
    python3 tools/build_glance_gates.py
    # → data/static/glance_gates.json
"""
from __future__ import annotations
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = PROJECT_ROOT / "hero_profiles_game.json"
OUT_PATH = PROJECT_ROOT / "data" / "static" / "glance_gates.json"
MOD_BASE = "http://localhost:6790"


def fetch_skill(skill_id: int, retries: int = 2):
    """Fetch a single skill at depth=8 from the live mod."""
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


def gated_indices(skill: dict) -> list[int]:
    """Return effect indices where Relation.ActivateOnGlancingHit is False."""
    indices = []
    for i, eff in enumerate(skill.get("Effects") or []):
        rel = eff.get("Relation") or {}
        if rel.get("ActivateOnGlancingHit") is False:
            indices.append(i)
    return indices


def main() -> int:
    if not PROFILES_PATH.exists():
        print(f"missing {PROFILES_PATH} — run build_hero_profiles.py first")
        return 1
    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))

    # Collect every (hero, skill_id) pair we care about.
    skill_ids: set[int] = set()
    for hero, prof in profiles.items():
        for sk in prof.get("skills") or []:
            sid = sk.get("id")
            if isinstance(sid, int):
                skill_ids.add(sid)

    print(f"profiles cover {len(profiles)} heroes, {len(skill_ids)} unique skills")

    # Verify mod is up.
    try:
        with urllib.request.urlopen(f"{MOD_BASE}/status", timeout=5) as r:
            json.loads(r.read())
    except Exception as e:
        print(f"mod not reachable at {MOD_BASE}: {e}")
        return 2

    gates: dict[str, list[int]] = {}
    missing: list[int] = []
    failures: list[tuple[int, str]] = []
    progress_every = 50

    for i, sid in enumerate(sorted(skill_ids), 1):
        try:
            skill = fetch_skill(sid)
        except Exception as e:
            failures.append((sid, str(e)))
            continue
        if not skill or skill.get("Id") != sid:
            missing.append(sid)
            continue
        gi = gated_indices(skill)
        if gi:
            gates[str(sid)] = gi
        if i % progress_every == 0:
            print(f"  {i}/{len(skill_ids)} fetched; {len(gates)} gated so far")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "source": "live mod /static-export at depth=8",
            "skills_scanned": len(skill_ids),
            "skills_with_gates": len(gates),
            "skills_missing": len(missing),
            "fetch_failures": len(failures),
        },
        "gates": gates,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    print(f"scanned: {len(skill_ids)} skills")
    print(f"with glance gates: {len(gates)}")
    print(f"missing from static: {len(missing)}")
    print(f"fetch failures: {len(failures)}")
    print(f"wrote: {OUT_PATH}")
    if failures[:5]:
        print("first failures:")
        for sid, err in failures[:5]:
            print(f"  {sid}: {err[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
