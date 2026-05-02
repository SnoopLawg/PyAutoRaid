"""Per-skill depth=4 static-data cache.

`tools/refresh_static_data.py` fetches all skills at depth=3 because depth=4
on the bulk endpoint exceeds the mod's 60s main-thread cap. But sim work
needs the inner parameter blocks (`ForceTickParams`, `ChangeEffectLifetime
Params`, `ApplyStatusEffectParams.StatusEffectInfos`) which are opaque
placeholders at depth=3.

This tool fetches a list of skill IDs individually at depth=4 and merges
into `data/static/skills_d4.json` keyed by skill ID. Cheap to extend —
add IDs to SIM_RELEVANT_SKILLS or pass --ids on the CLI.

Use `effect_engine.normalize_skill_effects()` to consume — it prefers
depth=4 entries when available, falling back to depth=3.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "data" / "static" / "skills_d4.json"

# Skill IDs referenced by per-skill-id branches in load_game_profiles.py
# plus the active-sim hero roster. Add IDs as we extend sim coverage.
SIM_RELEVANT_SKILLS = [
    # Ninja (62001-62004)
    62001, 62002, 62003, 62004,
    # Demytha (65101-65104)
    65101, 65102, 65103, 65104,
    # Maneater (variant ID — verify with skills_db)
    # Geomancer (48801-48804)
    48801, 48802, 48803, 48804,
    # Venomage (62801-62804)
    62801, 62802, 62803, 62804,
    # Cardiel (57601-57604)
    57601, 57602, 57603, 57604,
    # Sicia Flametongue (57701-57704)
    57701, 57702, 57703, 57704,
    # Teodor the Savant (36001-36004)
    36001, 36002, 36003, 36004,
    # Artak (78601-78604)
    78601, 78602, 78603, 78604,
    # Ma'Shalled (9301-9304)
    9301, 9302, 9303, 9304,
    # OB (33001-33004) — Occult Brawler
    33001, 33002, 33003, 33004,
    # Fahrakin (56601-56604)
    56601, 56602, 56603, 56604,
    # Venus (35001-35005)
    35001, 35002, 35003, 35004, 35005,
    # Sepulcher Sentinel (38801-38804)
    38801, 38802, 38803, 38804,
    # Drexthar (variant — placeholder; refresh once IDs verified)
]


def fetch(skill_id: int, host: str, timeout: float = 30.0) -> dict | None:
    path = f"SkillData.SkillTypeById.Item%5B{skill_id}%5D"
    # depth=5 reveals ApplyStatusEffectParams.StatusEffectInfos[].(TypeId, Duration)
    # — the actual debuff/buff payloads. depth=4 stops at SEI placeholder.
    url = f"http://{host}/static-export?path={path}&depth=5&max=400"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, dict) and "error" in data:
            return None
        return data
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="localhost:6790")
    ap.add_argument("--ids", nargs="+", type=int,
                    help="Specific skill IDs to fetch (default: SIM_RELEVANT_SKILLS)")
    ap.add_argument("--all-from-d3", action="store_true",
                    help="Fetch all skill IDs found in skills_all.json (slow)")
    ap.add_argument("--force", action="store_true",
                    help="Refetch even if already cached")
    args = ap.parse_args()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache: dict[str, dict] = {}
    if OUT_PATH.exists():
        cache = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    if args.all_from_d3:
        d3_path = PROJECT_ROOT / "data" / "static" / "skills_all.json"
        if not d3_path.exists():
            print("skills_all.json missing — run refresh_static_data.py first",
                  file=sys.stderr)
            return 1
        d3 = json.loads(d3_path.read_text(encoding="utf-8"))
        arr = d3.get("data") if isinstance(d3, dict) else d3
        ids = [s["Id"] for s in (arr or []) if isinstance(s, dict) and "Id" in s]
    elif args.ids:
        ids = args.ids
    else:
        ids = SIM_RELEVANT_SKILLS

    fetched, skipped, failed = 0, 0, 0
    t0 = time.time()
    for sid in ids:
        key = str(sid)
        if not args.force and key in cache:
            skipped += 1
            continue
        data = fetch(sid, args.host)
        if data is None:
            failed += 1
            continue
        cache[key] = data
        fetched += 1
        # Save every 10 to be crash-safe on long runs
        if fetched % 10 == 0:
            OUT_PATH.write_text(json.dumps(cache), encoding="utf-8")
            print(f"  ... {fetched} fetched ({time.time()-t0:.1f}s)",
                  file=sys.stderr)

    OUT_PATH.write_text(json.dumps(cache), encoding="utf-8")
    print(f"done: fetched={fetched} skipped={skipped} failed={failed} "
          f"total_cached={len(cache)} elapsed={time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
