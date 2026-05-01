"""Sell-rules bulk-sell pipeline.

Three concerns:
1. Fast read of the full artifact list for rule evaluation (sqlite-first
   so previews don't pay the mod's 8s pagination cost).
2. Cache invalidation after a sell so the next /api/state reflects the
   reduced vault.
3. The bulk-sell driver itself: chunk → /sell-artifacts → audit-log →
   invalidate cache. Returns {ok, sold, skipped} for the dashboard.

This is the canonical entry-point for any sell operation; the dashboard
HTTP handler is one consumer. The CLI below is the equivalent for
headless operation.

CLI usage:
    python3 tools/sell.py preview                  # show what rules would sell
    python3 tools/sell.py execute --confirm        # actually sell them
    python3 tools/sell.py history --limit 50       # tail data/sell_history.jsonl
"""
from __future__ import annotations

import datetime
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# 30s freshness window for the SQLite-derived artifact list. Rule
# evaluation does not need live freshness — a piece dropped between the
# last refresh and "now" simply isn't evaluated for sale.
SQLITE_ARTIFACT_TTL = 30.0

_SQLITE_ARTIFACT_CACHE: dict = {"ts": 0.0, "data": None}

_SLOT_MAP = {1: "Helmet", 2: "Chest", 3: "Gloves", 4: "Boots",
             5: "Weapon", 6: "Shield", 7: "Ring", 8: "Amulet", 9: "Banner"}
_STAT_MAP = {1: "HP", 2: "ATK", 3: "DEF", 4: "SPD",
             5: "RES", 6: "ACC", 7: "CR", 8: "CD"}


def artifacts_from_sqlite(db_path: Path) -> list[dict]:
    """Pull all artifacts + their substats from pyautoraid.db.

    Returns the list shape build_artifacts() produces (slot/primary_stat
    as strings, primary_flat bool, substats[]) so sell_rules.evaluate
    sees the same fields. Empty list if the db is missing.
    """
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        sets = {r[0]: r[1] for r in cur.execute(
            "SELECT set_id, name FROM ref_artifact_sets").fetchall()}
        art_rows = cur.execute(
            "SELECT id, kind, rank, rarity, level, set_id, hero_id, "
            "primary_stat, primary_value, primary_flat FROM artifacts"
        ).fetchall()
        sub_map: dict[int, list] = {}
        for r in cur.execute(
                "SELECT artifact_id, stat_id, value, is_flat, rolls "
                "FROM artifact_substats").fetchall():
            sub_map.setdefault(r[0], []).append({
                "stat": _STAT_MAP.get(r[1], ""),
                "value": r[2],
                "flat": bool(r[3]),
                "rolls": r[4],
            })
    finally:
        conn.close()
    out = []
    for r in art_rows:
        aid, kind, rank, rarity, level, sid, hid, pstat, pval, pflat = r
        out.append({
            "id": aid,
            "level": level or 0,
            "rank": rank or 0,
            "rarity": rarity or 0,
            "set_id": sid or 0,
            "set_name": sets.get(sid, ""),
            "slot": _SLOT_MAP.get(kind, ""),
            "slot_id": kind,
            "primary_stat": _STAT_MAP.get(pstat, ""),
            "primary_value": pval or 0,
            "primary_flat": bool(pflat),
            "substats": sub_map.get(aid, []),
            "sub_count": len(sub_map.get(aid, [])),
            "hero_id": hid,
            "equipped_on": {"hero_id": hid} if hid else None,
        })
    return out


def all_artifacts_for_rules(
    *, db_path: Path,
    in_memory_cache: dict,
    fallback_loader: Callable[[], list[dict] | None],
) -> list[dict]:
    """Return the full artifact list in the shape sell_rules.evaluate accepts.

    Speed-tier strategy:
      1. If the in-memory mod-paginated artifact cache is warm, use it.
      2. If the SQLite-derived cache is warm (< 30s), use it (~0ms).
      3. Otherwise read from the SQLite cache (~50-200ms) — populated by
         tools/refresh_data.py and good enough for rule evaluation.
      4. Fall back to fallback_loader() (paginates from the mod, several
         seconds) as a last resort.
    """
    if in_memory_cache.get("data"):
        return in_memory_cache["data"]
    now = time.time()
    cached = _SQLITE_ARTIFACT_CACHE.get("data")
    if cached and (now - _SQLITE_ARTIFACT_CACHE["ts"]) < SQLITE_ARTIFACT_TTL:
        return cached
    try:
        rows = artifacts_from_sqlite(db_path)
        if rows:
            _SQLITE_ARTIFACT_CACHE["ts"] = now
            _SQLITE_ARTIFACT_CACHE["data"] = rows
            return rows
    except Exception as e:
        logger.info("sqlite artifact read failed: %s", e)
    return fallback_loader() or []


def invalidate_artifact_cache(in_memory_cache: dict) -> None:
    """Bust the in-memory mod cache + the SQLite-derived cache. Call
    after a sell so the next preview reflects the post-sell vault."""
    in_memory_cache["ts"] = 0
    in_memory_cache["data"] = None
    _SQLITE_ARTIFACT_CACHE["ts"] = 0
    _SQLITE_ARTIFACT_CACHE["data"] = None


def append_sell_history(history_path: Path, entry: dict) -> None:
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.info("sell_history append failed: %s", e)


def run_bulk_sell(
    ids: list[int], source: str = "dashboard",
    *, mod_client, db_path: Path, history_path: Path,
    in_memory_cache: dict,
    fallback_loader: Callable[[], list[dict] | None],
) -> dict:
    """Sell a list of artifact IDs via the mod's /sell-artifacts endpoint.

    Returns {ok, sold: [int], skipped: [{id, reason}], error?}.

    Logs each successful sell to history_path (jsonl) for auditing.
    Forces an artifact-cache refresh on success so subsequent /api/state
    polls reflect the new vault state.
    """
    if not ids:
        return {"ok": True, "sold": [], "skipped": []}
    if not mod_client.available:
        return {"error": "mod not reachable"}
    # Look up metadata for the audit log BEFORE the sell removes it from
    # the cache. Use the fast sqlite/in-mem path — calling the fallback
    # loader here would re-paginate the mod (8s) and block the request.
    meta_by_id: dict[int, dict] = {}
    ids_set = set(ids)
    for a in all_artifacts_for_rules(
        db_path=db_path,
        in_memory_cache=in_memory_cache,
        fallback_loader=fallback_loader,
    ):
        if a.get("id") in ids_set:
            meta_by_id[a["id"]] = a
    sold: list[int] = []
    skipped: list[dict] = []
    err = None
    for i in range(0, len(ids), 50):
        chunk = ids[i:i+50]
        ids_param = ",".join(str(x) for x in chunk)
        r = mod_client._get("/sell-artifacts?ids=" + ids_param) or {}
        if "error" in r:
            err = r["error"]
            break
        sold.extend(r.get("sold") or [])
        skipped.extend(r.get("skipped") or [])
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    for aid in sold:
        m = meta_by_id.get(aid) or {}
        append_sell_history(history_path, {
            "ts": ts, "source": source, "id": aid,
            "slot": m.get("slot"), "set": m.get("set_name"),
            "rank": m.get("rank"), "rarity": m.get("rarity"),
            "level": m.get("level"), "primary": m.get("primary_stat"),
        })
    if sold:
        invalidate_artifact_cache(in_memory_cache)
    out = {"ok": err is None, "sold": sold, "skipped": skipped}
    if err:
        out["error"] = err
    return out


# ============================================================================
# CLI — headless equivalent of the dashboard's sell-rules panel.
# Both code paths funnel through run_bulk_sell() so behavior is identical.
# ============================================================================

# cli_util is in the same directory; add its dir to sys.path before importing
# so the script works whether run as `python3 tools/sell.py` or imported.
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from cli_util import project_root as _project_root, ensure_path as _ensure_path  # noqa: E402


def _evaluate(root: Path) -> dict:
    """Run the sell rules against the SQLite vault. Returns the dict produced
    by sell_rules.evaluate_all: {sell_count, keep_count, by_rule, sell:[...]}."""
    _ensure_path(root)
    from sell_rules import evaluate_all, load_rules, RULES_PATH
    cfg = load_rules(RULES_PATH)
    db_path = root / "pyautoraid.db"
    arts = artifacts_from_sqlite(db_path)
    return evaluate_all(arts, cfg)


def _cmd_preview(args) -> int:
    root = _project_root()
    result = _evaluate(root)
    sell = result.get("sell", [])
    keep = result.get("keep_count", 0)
    by_rule = result.get("by_rule", {})
    print(f"Vault: {len(sell) + keep} pieces. Would sell {len(sell)}, keep {keep}.\n")
    if by_rule:
        print("By rule:")
        for rid, n in sorted(by_rule.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>5}  rule={rid}")
        print()
    for m in sell[:args.limit]:
        equipped = " (equipped)" if m.get("hero_id") else ""
        print(f"  rule={m.get('rule_id','?'):20} | id={m.get('id','?'):>7} "
              f"{m.get('slot','?'):6} {m.get('set','?'):12} "
              f"R{m.get('rank','?')} L{m.get('level','?')} {m.get('primary','?')}{equipped}")
    if len(sell) > args.limit:
        print(f"  ... +{len(sell) - args.limit} more (use --limit N to see more)")
    return 0


def _cmd_execute(args) -> int:
    if not args.confirm:
        print("ERR: --confirm required for execute (this sells real artifacts)", file=__import__("sys").stderr)
        return 2
    root = _project_root()
    result = _evaluate(root)
    sell = result.get("sell", [])
    if not sell:
        print("Nothing to sell.")
        return 0
    print(f"Selling {len(sell)} pieces…")

    # Local-cli mod_client wrapper. Reuses the same Modules.mod_client used
    # by the dashboard so behavior is identical.
    _ensure_path(root)
    from Modules.mod_client import ModClient
    client = ModClient(args.mod_url)

    # No in-memory artifact cache outside the dashboard process; pass an
    # empty dict (so it can't short-circuit our reads) and the same fallback.
    in_mem: dict = {"ts": 0.0, "data": None}

    def _fallback() -> list[dict]:
        return artifacts_from_sqlite(root / "pyautoraid.db")

    ids = [m["id"] for m in sell if m.get("id") is not None]
    result = run_bulk_sell(
        ids, source="cli",
        mod_client=client,
        db_path=root / "pyautoraid.db",
        history_path=root / "data" / "sell_history.jsonl",
        in_memory_cache=in_mem,
        fallback_loader=_fallback,
    )
    if result.get("error"):
        print(f"ERR: {result['error']}", file=__import__("sys").stderr)
        return 3
    print(f"sold:    {len(result.get('sold', []))}")
    print(f"skipped: {len(result.get('skipped', []))}")
    return 0


def _cmd_history(args) -> int:
    root = _project_root()
    p = root / "data" / "sell_history.jsonl"
    if not p.exists():
        print("(no sell history yet)")
        return 0
    lines = p.read_text().splitlines()
    for line in lines[-args.limit:]:
        try:
            e = json.loads(line)
        except Exception:
            continue
        print(f"  {e.get('ts','')} src={e.get('source','?'):10} id={e.get('id','?'):>7} "
              f"{e.get('slot','?'):6} {e.get('set','?'):12} R{e.get('rank','?')} L{e.get('level','?')}")
    print(f"\n({len(lines)} entries total)")
    return 0


def _main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pv = sub.add_parser("preview", help="show what rules would sell")
    pv.add_argument("--limit", type=int, default=30)
    pv.set_defaults(func=_cmd_preview)

    ex = sub.add_parser("execute", help="actually sell pieces matching rules")
    ex.add_argument("--confirm", action="store_true", help="required for safety")
    ex.add_argument("--mod-url", default="http://localhost:6790")
    ex.set_defaults(func=_cmd_execute)

    hi = sub.add_parser("history", help="tail data/sell_history.jsonl")
    hi.add_argument("--limit", type=int, default=20)
    hi.set_defaults(func=_cmd_history)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_main())
