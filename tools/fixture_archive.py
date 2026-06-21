#!/usr/bin/env python3
"""
Fixture archive — catalogs all CB battle captures (tick + battle +
poll log triples) into a single manifest so the sim can be replayed
against them without spending keys.

Naming convention: `(tick|battle|poll)_log_cb_<YYYYMMDD_HHMMSS>.json`
Files with matching timestamps are treated as one fixture. Each
component may be missing (older captures pre-date the poll log).

Usage:
  python3 tools/fixture_archive.py rebuild
  python3 tools/fixture_archive.py list [--affinity force|magic|spirit|void]
  python3 tools/fixture_archive.py show <timestamp>
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "fixtures" / "manifest.json"

ELEMENT_NAMES = {1: "magic", 2: "force", 3: "spirit", 4: "void"}
TS_RE = re.compile(r"_cb_(\d{8}_\d{6})\.json")


def _name_lookup():
    """Build type_id -> name dict from data/static/hero_types.json
    (the game's static export, covers all 8177 HeroTypes including
    every form/ascend grade). type_id in /battle-state == HeroType.id."""
    try:
        with open(PROJECT_ROOT / "data" / "static" / "hero_types.json") as f:
            items = json.load(f).get("hero_types", [])
        return {h["id"]: h.get("name") for h in items if h.get("id")}
    except Exception:
        return {}


def _scan_logs():
    """Find all (tick|battle|poll)_log_cb_*.json files in repo root
    and group by timestamp."""
    fixtures = {}
    for prefix, key in [("tick_log_cb_", "tick_log"),
                        ("battle_logs_cb_", "battle_log"),
                        ("poll_log_cb_", "poll_log")]:
        for p in PROJECT_ROOT.glob(f"{prefix}*.json"):
            m = TS_RE.search(p.name)
            if not m:
                continue
            ts = m.group(1)
            fixtures.setdefault(ts, {})[key] = str(p.relative_to(PROJECT_ROOT))
    return fixtures


def _parse_poll_log(path):
    """Pull battle metadata from a poll log JSONL.

    Returns dict with: boss_element, hero_team_type_ids, real_damage_peak,
    real_boss_turns, poll_count. Missing fields = None."""
    out = {
        "boss_element": None,
        "hero_team_type_ids": [],
        "real_damage_peak": None,
        "real_boss_turns": None,
        "poll_count": 0,
    }
    try:
        with open(path) as f:
            polls = [json.loads(ln) for ln in f if ln.strip()]
    except Exception:
        return out
    out["poll_count"] = len(polls)
    seen_team = False
    for p in polls:
        st = p.get("state", {})
        if "error" in st:
            continue
        heroes = st.get("heroes") or []
        if not seen_team:
            tids = [h.get("type_id") for h in heroes
                    if h.get("side") == "player" and h.get("type_id")]
            if tids:
                out["hero_team_type_ids"] = tids
                seen_team = True
        for h in heroes:
            if h.get("side") == "enemy":
                if out["boss_element"] is None:
                    out["boss_element"] = h.get("element")
                dmg = h.get("dmg_taken") or 0
                turn = h.get("turn_n") or 0
                if out["real_damage_peak"] is None or dmg > out["real_damage_peak"]:
                    out["real_damage_peak"] = dmg
                if out["real_boss_turns"] is None or turn > out["real_boss_turns"]:
                    out["real_boss_turns"] = turn
    return out


def build_manifest():
    """Scan all logs, build fixture metadata, write manifest."""
    fixtures = _scan_logs()
    name_lookup = _name_lookup()
    entries = []
    for ts in sorted(fixtures.keys()):
        files = fixtures[ts]
        entry = {
            "timestamp": ts,
            "tick_log": files.get("tick_log"),
            "battle_log": files.get("battle_log"),
            "poll_log": files.get("poll_log"),
            "boss_element": None,
            "affinity": None,
            "hero_team_type_ids": [],
            "hero_team_names": [],
            "real_damage_peak": None,
            "real_boss_turns": None,
            "poll_count": 0,
            "has_full_triple": all(k in files for k in ("tick_log", "battle_log", "poll_log")),
        }
        if files.get("poll_log"):
            meta = _parse_poll_log(PROJECT_ROOT / files["poll_log"])
            entry.update(meta)
            entry["affinity"] = ELEMENT_NAMES.get(meta["boss_element"])
            entry["hero_team_names"] = [
                name_lookup.get(tid, f"type_id={tid}")
                for tid in meta["hero_team_type_ids"]
            ]
        entries.append(entry)

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1, "count": len(entries), "fixtures": entries}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_manifest():
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def cmd_rebuild(_args):
    m = build_manifest()
    triple = sum(1 for f in m["fixtures"] if f["has_full_triple"])
    with_poll = sum(1 for f in m["fixtures"] if f["poll_log"])
    by_aff = {}
    for f in m["fixtures"]:
        a = f.get("affinity") or "unknown"
        by_aff[a] = by_aff.get(a, 0) + 1
    print(f"Wrote {MANIFEST_PATH} ({m['count']} fixtures, {triple} full triples, {with_poll} with poll log)")
    print(f"By affinity: {by_aff}")
    return 0


def cmd_list(args):
    m = load_manifest()
    if not m:
        print("No manifest. Run `fixture_archive rebuild` first.")
        return 1
    fixtures = m["fixtures"]
    if args.affinity:
        fixtures = [f for f in fixtures if f.get("affinity") == args.affinity]
    if args.with_poll:
        fixtures = [f for f in fixtures if f.get("poll_log")]
    print(f"{'TIMESTAMP':<17} {'AFFINITY':<8} {'BT':>4} {'DAMAGE':>13}  TEAM")
    for f in fixtures:
        names = ",".join(f.get("hero_team_names", [])[:5]) or "?"
        dmg = f.get("real_damage_peak")
        dmg_s = f"{dmg:>13,}" if dmg else " " * 13
        print(f"{f['timestamp']:<17} {(f.get('affinity') or '?'):<8} "
              f"{(f.get('real_boss_turns') or 0):>4} {dmg_s}  {names}")
    print(f"\n{len(fixtures)} fixture(s).")
    return 0


def cmd_show(args):
    m = load_manifest()
    if not m:
        print("No manifest. Run `fixture_archive rebuild` first.")
        return 1
    for f in m["fixtures"]:
        if f["timestamp"] == args.timestamp:
            print(json.dumps(f, indent=2))
            return 0
    print(f"No fixture for timestamp {args.timestamp!r}.")
    return 2


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("rebuild", help="Scan logs and rewrite manifest.")
    p_list = sub.add_parser("list", help="List fixtures (filterable).")
    p_list.add_argument("--affinity", choices=list(ELEMENT_NAMES.values()),
                        help="Filter to one affinity.")
    p_list.add_argument("--with-poll", action="store_true",
                        help="Only fixtures with a poll log (replayable).")
    p_show = sub.add_parser("show", help="Print full metadata for one fixture.")
    p_show.add_argument("timestamp", help="YYYYMMDD_HHMMSS")
    args = ap.parse_args()
    return {"rebuild": cmd_rebuild, "list": cmd_list, "show": cmd_show}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
