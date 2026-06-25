"""Artifact loadout snapshot / apply / restore.

The primitive that makes farm-cycle gear swapping safe:

- `snapshot(name, hero_ids)` — capture each hero's currently-equipped
  artifacts (by slot) into pyautoraid.db so we can put them back later.
- `apply(name, mapping)` — equip a target mapping {hero_id: [art_ids]}
  via the mod's `/bulk-equip` and record the result under `name`.
- `restore(name)` — re-equip the artifacts captured by the matching
  snapshot, so heroes return to their pre-apply state (e.g. CB tune).

Storage: a `loadouts` table in pyautoraid.db keyed by (name, hero_id,
slot). One snapshot per name; apply overwrites it. Restore reads it.

CLI:
    python3 tools/loadouts.py list
    python3 tools/loadouts.py show <name>
    python3 tools/loadouts.py snapshot <name> --heroes 15120,18607,2643
    python3 tools/loadouts.py restore <name>
    python3 tools/loadouts.py delete <name>

The orchestrator (tools/farm_cycle.py) calls snapshot() before swap
and restore() after the runs finish.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "pyautoraid.db"
MOD_BASE = "http://localhost:6790"

SLOT_NAMES = {1: "Helmet", 2: "Chest", 3: "Gloves", 4: "Boots",
              5: "Weapon", 6: "Shield", 7: "Ring", 8: "Amulet", 9: "Banner"}


SCHEMA = """
CREATE TABLE IF NOT EXISTS loadouts (
    name        TEXT NOT NULL,
    hero_id     INTEGER NOT NULL,
    slot        INTEGER NOT NULL,
    artifact_id INTEGER NOT NULL,
    captured_at TEXT NOT NULL,
    PRIMARY KEY (name, hero_id, slot)
);
CREATE INDEX IF NOT EXISTS idx_loadouts_name ON loadouts(name);
CREATE INDEX IF NOT EXISTS idx_loadouts_hero ON loadouts(name, hero_id);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(SCHEMA)
    return conn


def _get(path: str, timeout: int = 30) -> dict:
    with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def _fetch_heroes() -> dict[int, dict]:
    """Return {hero_id: hero_dict} from live /all-heroes."""
    data = _get("/all-heroes?limit=20000")
    heroes = data.get("heroes", data) if isinstance(data, dict) else data
    return {h["id"]: h for h in heroes if "id" in h}


def _equipped_by_slot(hero: dict) -> dict[int, int]:
    """{slot_id: artifact_id} for currently-equipped pieces on a hero."""
    out: dict[int, int] = {}
    for art in hero.get("artifacts", []) or []:
        slot = art.get("kind")
        aid = art.get("id")
        if slot and aid:
            out[slot] = aid
    return out


def snapshot(name: str, hero_ids: Iterable[int]) -> dict:
    """Capture the current equipped artifacts for hero_ids under `name`.

    Overwrites any prior snapshot with the same name. Returns
    {hero_id: {slot: artifact_id}}.
    """
    heroes = _fetch_heroes()
    captured_at = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")
    rows: list[tuple] = []
    result: dict[int, dict[int, int]] = {}
    missing: list[int] = []

    for hid in hero_ids:
        h = heroes.get(hid)
        if not h:
            missing.append(hid)
            continue
        by_slot = _equipped_by_slot(h)
        result[hid] = by_slot
        for slot, aid in by_slot.items():
            rows.append((name, hid, slot, aid, captured_at))

    conn = _conn()
    try:
        conn.execute("DELETE FROM loadouts WHERE name = ?", (name,))
        if rows:
            conn.executemany(
                "INSERT INTO loadouts(name, hero_id, slot, artifact_id, "
                "captured_at) VALUES (?, ?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()

    if missing:
        print(f"warning: snapshot '{name}' — {len(missing)} hero(s) not "
              f"found in /all-heroes: {missing}", file=sys.stderr)
    return result


def load(name: str) -> dict[int, dict[int, int]]:
    """Return {hero_id: {slot: artifact_id}} for a saved snapshot."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT hero_id, slot, artifact_id FROM loadouts "
            "WHERE name = ? ORDER BY hero_id, slot", (name,)).fetchall()
    finally:
        conn.close()
    out: dict[int, dict[int, int]] = {}
    for hid, slot, aid in rows:
        out.setdefault(hid, {})[slot] = aid
    return out


def list_names() -> list[tuple[str, int, str]]:
    """Return [(name, hero_count, captured_at)] for all snapshots."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT name, COUNT(DISTINCT hero_id), MIN(captured_at) "
            "FROM loadouts GROUP BY name ORDER BY name").fetchall()
    finally:
        conn.close()
    return rows


def delete(name: str) -> int:
    """Delete the snapshot. Returns rows removed."""
    conn = _conn()
    try:
        cur = conn.execute("DELETE FROM loadouts WHERE name = ?", (name,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def _unequip(hero_id: int, artifact_id: int) -> dict:
    """Single unequip via /unequip — moves artifact from hero to vault."""
    return _get(f"/unequip?hero_id={hero_id}&artifact_id={artifact_id}")


def _release_to_vault(target_ids: set[int]) -> dict:
    """Unequip every artifact in `target_ids` from whatever hero
    currently owns it. Items already in vault are skipped. Returns
    {artifact_id: {ok, ...}}.

    Why: /bulk-equip enqueues swap commands async; when many heroes
    swap simultaneously the later swaps see stale state and drop. By
    putting all planned artifacts in vault first, the subsequent
    bulk-equip per hero only needs Activate (no hero-to-hero swap)."""
    arts_resp = _get("/all-artifacts?limit=20000")
    arts = arts_resp.get("artifacts", []) if isinstance(arts_resp, dict) else []
    owner_by_id: dict[int, int | None] = {
        int(a["id"]): a.get("hero_id") for a in arts
        if isinstance(a, dict) and "id" in a
    }
    results: dict[int, dict] = {}
    for aid in target_ids:
        owner = owner_by_id.get(aid)
        if not owner:
            results[aid] = {"ok": True, "skipped": "already in vault"}
            continue
        try:
            r = _unequip(owner, aid)
            results[aid] = {"ok": "error" not in (r or {}),
                            "from": owner, "raw": r}
        except Exception as e:
            results[aid] = {"ok": False, "error": str(e), "from": owner}
    return results


def _bulk_equip(hero_id: int, artifact_ids: list[int]) -> dict:
    """Returns the mod's bulk-equip response, normalized so callers can
    rely on `ok: bool`. The mod itself returns
        {bulk, hero_id, results: [{id, action, ...}, ...], equipped}
    with per-artifact `action` codes (already / swap / equip / error /
    failed). We translate to {ok, action_counts, results, equipped}."""
    ids_json = urllib.parse.quote(json.dumps(artifact_ids), safe="")
    raw = _get(f"/bulk-equip?hero_id={hero_id}&artifacts={ids_json}")
    if not isinstance(raw, dict):
        return {"ok": False, "raw": raw}
    if "error" in raw:
        return {"ok": False, **raw}
    results = raw.get("results") or []
    bad_actions = {"error", "failed"}
    counts: dict[str, int] = {}
    for r in results:
        counts[r.get("action", "?")] = counts.get(r.get("action", "?"), 0) + 1
    ok = bool(results) and not any(
        r.get("action") in bad_actions for r in results)
    return {"ok": ok, "action_counts": counts,
            "results": results, "equipped": raw.get("equipped")}


def _equip_mapping_once(mapping: dict[int, list[int]]) -> dict[int, dict]:
    """One pass of bulk-equip per hero. Pauses between heroes so the
    async CmdQueue can settle before the next hero's bulk-equip
    reads ownership state."""
    results: dict[int, dict] = {}
    hero_ids = list(mapping.keys())
    for i, hid in enumerate(hero_ids):
        art_ids = mapping[hid]
        if not art_ids:
            results[hid] = {"ok": True, "equipped": [], "skipped": "empty"}
            continue
        try:
            r = _bulk_equip(hid, list(art_ids))
            results[hid] = r if isinstance(r, dict) else {"ok": False, "raw": r}
        except Exception as e:
            results[hid] = {"ok": False, "error": str(e)}
        if i < len(hero_ids) - 1:
            time.sleep(0.5)
    return results


def _diff_mapping(mapping: dict[int, list[int]]) -> dict[int, list[int]]:
    """Heroes whose live equipped set != desired set. Re-fetches /all-heroes."""
    heroes = _fetch_heroes()
    out: dict[int, list[int]] = {}
    for hid, want in mapping.items():
        if not want:
            continue
        h = heroes.get(hid)
        if not h:
            out[hid] = list(want)
            continue
        have = {a["id"] for a in h.get("artifacts", []) or []}
        if set(want) != have:
            out[hid] = list(want)
    return out


def _release_set_for(mapping: dict[int, list[int]]) -> set[int]:
    """The set of artifacts to release to the vault for a contention-free,
    SWAP-FREE apply:

      (a) every target piece NOT already on its target hero, AND
      (b) every piece currently occupying a team hero's slot whose target
          piece is different (i.e. an "outgoing" piece being replaced).

    After releasing both, each team hero keeps ONLY its already-correct
    target pieces and every slot that needs a new piece is EMPTY — so the
    equip phase is PURE ACTIVATE (vault->empty-slot), with ZERO
    SwapArtifactCmd calls. That matters because:
      - no hero<->hero swap => no team hero can steal another's speed piece
        (contention), and
      - no swap-from-vault with a possibly-stale owner => avoids the
        Validate-failure that silently wedged hero 2643's command queue
        when its swap fired first in a burst (live 2026-06-24).
    Pieces already correct are left in place (no wasted moves)."""
    arts_resp = _get("/all-artifacts?limit=20000")
    arts = arts_resp.get("artifacts", []) if isinstance(arts_resp, dict) else []
    owner_by_id = {int(a["id"]): a.get("hero_id") for a in arts
                   if isinstance(a, dict) and "id" in a}
    heroes = _fetch_heroes()
    release: set[int] = set()
    for hid, ids in mapping.items():
        target = set(ids)
        # (a) target pieces not already on this hero (and currently equipped)
        for aid in target:
            if owner_by_id.get(aid) not in (hid, None) and owner_by_id.get(aid):
                release.add(aid)
        # (b) pieces currently on this hero that are NOT in its target set
        #     (free the slot so the incoming piece is an activate, not a swap)
        h = heroes.get(hid)
        if h:
            for slot, cur in _equipped_by_slot(h).items():
                if cur not in target:
                    release.add(cur)
    return release


def apply(name: str, mapping: dict[int, list[int]],
          snapshot_first: bool = True, max_passes: int = 4) -> dict:
    """Equip `mapping` on the live game, CONTENTION-FREE.

    A plan that re-gears several heroes from one shared pool will, if
    executed as hero<->hero swaps, let earlier-priority heroes STEAL
    speed pieces from later ones — the greedy bulk-equip + retry then
    oscillates and starves the tail (live-proven 2026-06-24: a full
    re-gear left Venomage at 122 SPD vs a 162 target).

    The fix: RELEASE-then-EQUIP. First unequip every piece that must move
    to the vault, then equip each hero's target set. Because every equip
    now pulls from the vault (vault->hero is reliable — verified live, the
    basis the old 'pre-release was counterproductive' note got wrong), no
    hero<->hero swap happens and contention is impossible. Converges in
    one equip pass; the multi-pass retry is just a safety net.

    If snapshot_first, capture the pre-apply state under `name` so a
    later restore() reverses to it.
    """
    if snapshot_first:
        snapshot(name, list(mapping.keys()))

    # RELEASE phase — move every piece that must change into the vault, so
    # the equip phase is pure activate (zero swaps). Then VERIFY the
    # releases actually landed in the vault before equipping: if an
    # unequip hasn't settled, the slot still looks occupied and bulk-equip
    # would fall back to a swap (the very thing we're avoiding).
    release = _release_set_for(mapping)
    release_results = _release_to_vault(release) if release else {}
    for _ in range(6):
        if not release:
            break
        time.sleep(1.0)
        arts_resp = _get("/all-artifacts?limit=20000")
        arts = arts_resp.get("artifacts", []) if isinstance(arts_resp, dict) else []
        owner_now = {int(a["id"]): a.get("hero_id") for a in arts
                     if isinstance(a, dict) and "id" in a}
        still_equipped = [a for a in release if owner_now.get(a)]
        if not still_equipped:
            break
        # Re-issue the stragglers' unequips.
        _release_to_vault(set(still_equipped))

    # EQUIP phase — every move is now vault->hero (no contention).
    results = _equip_mapping_once(mapping)
    for _ in range(max_passes - 1):
        time.sleep(1.5)  # let the prior pass's CmdQueue settle.
        outstanding = _diff_mapping(mapping)
        if not outstanding:
            break
        # Re-equip only the heroes whose loadout still doesn't match.
        retry_results = _equip_mapping_once(outstanding)
        for hid, r in retry_results.items():
            results[hid] = r
    results["_released"] = {"count": len(release),
                            "ok": sum(1 for r in release_results.values()
                                      if r.get("ok"))}
    return results


def restore(name: str, max_passes: int = 6) -> dict:
    """Re-equip the artifacts captured under `name`. Multi-pass since
    a single /bulk-equip may not resolve all hero-to-hero transfers
    in one go. Does NOT delete the snapshot.

    Unlike apply(), restore() does NOT pre-release to vault — the
    snapshotted gear typically stays mostly on the correct heroes,
    and dumping 45+ async unequips would cause more races than it
    solves."""
    saved = load(name)
    if not saved:
        return {"error": f"no snapshot named '{name}'"}

    mapping: dict[int, list[int]] = {
        hid: [aid for _slot, aid in sorted(by_slot.items())]
        for hid, by_slot in saved.items()
    }

    results = _equip_mapping_once(mapping)
    for _ in range(max_passes - 1):
        outstanding = _diff_mapping(mapping)
        if not outstanding:
            break
        retry = _equip_mapping_once(outstanding)
        for hid, r in retry.items():
            results[hid] = r
    return results


def verify(name: str) -> dict:
    """Compare a saved snapshot to current live equip state.
    Returns {hero_id: {slot: (expected_aid, current_aid)}} for diffs only."""
    saved = load(name)
    heroes = _fetch_heroes()
    diffs: dict[int, dict[int, tuple]] = {}
    for hid, by_slot in saved.items():
        h = heroes.get(hid)
        if not h:
            diffs[hid] = {"_": ("hero missing", None)}
            continue
        live = _equipped_by_slot(h)
        for slot, expected_aid in by_slot.items():
            current_aid = live.get(slot)
            if current_aid != expected_aid:
                diffs.setdefault(hid, {})[slot] = (expected_aid, current_aid)
    return diffs


def _hero_name(heroes: dict[int, dict], hid: int) -> str:
    h = heroes.get(hid)
    return h.get("name", f"#{hid}") if h else f"#{hid}"


def _cmd_list(_args) -> int:
    rows = list_names()
    if not rows:
        print("(no snapshots)")
        return 0
    print(f"{'NAME':<32} {'HEROES':>7}  CAPTURED")
    for name, n, captured in rows:
        print(f"{name:<32} {n:>7}  {captured}")
    return 0


def _cmd_show(args) -> int:
    saved = load(args.name)
    if not saved:
        print(f"no snapshot named '{args.name}'", file=sys.stderr)
        return 1
    try:
        heroes = _fetch_heroes()
    except Exception:
        heroes = {}
    for hid, by_slot in saved.items():
        print(f"\n{_hero_name(heroes, hid)} (id={hid})")
        for slot in sorted(by_slot):
            print(f"  {SLOT_NAMES.get(slot, slot):<8} {by_slot[slot]}")
    return 0


def _parse_hero_ids(spec: str) -> list[int]:
    ids: list[int] = []
    for tok in spec.split(","):
        tok = tok.strip()
        if tok.isdigit():
            ids.append(int(tok))
    return ids


def _cmd_snapshot(args) -> int:
    hero_ids = _parse_hero_ids(args.heroes)
    if not hero_ids:
        print("--heroes is required (comma-separated hero IDs)",
              file=sys.stderr)
        return 2
    result = snapshot(args.name, hero_ids)
    print(f"snapshotted '{args.name}': {len(result)} hero(s)")
    for hid, by_slot in result.items():
        print(f"  {hid}: {len(by_slot)} slot(s) equipped")
    return 0


def _cmd_restore(args) -> int:
    res = restore(args.name)
    if "error" in res:
        print(res["error"], file=sys.stderr)
        return 1
    ok = sum(1 for r in res.values() if r.get("ok"))
    fail = len(res) - ok
    print(f"restored '{args.name}': {ok} ok, {fail} failed")
    for hid, r in res.items():
        flag = "ok " if r.get("ok") else "ERR"
        msg = r.get("error") or r.get("equipped") or r.get("raw") or ""
        print(f"  [{flag}] {hid}: {msg}")
    return 0 if fail == 0 else 1


def _cmd_verify(args) -> int:
    diffs = verify(args.name)
    if not diffs:
        print(f"snapshot '{args.name}' matches live equip state")
        return 0
    print(f"snapshot '{args.name}' has {len(diffs)} hero(s) with diffs:")
    for hid, slots in diffs.items():
        print(f"  hero {hid}:")
        for slot, (exp, cur) in slots.items():
            sn = SLOT_NAMES.get(slot, slot)
            print(f"    {sn:<8} expected={exp} current={cur}")
    return 1


def _cmd_delete(args) -> int:
    n = delete(args.name)
    print(f"deleted '{args.name}' ({n} rows)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=_cmd_list)

    sp = sub.add_parser("show")
    sp.add_argument("name")
    sp.set_defaults(func=_cmd_show)

    sp = sub.add_parser("snapshot")
    sp.add_argument("name")
    sp.add_argument("--heroes", required=True,
                    help="comma-separated hero IDs")
    sp.set_defaults(func=_cmd_snapshot)

    sp = sub.add_parser("restore")
    sp.add_argument("name")
    sp.set_defaults(func=_cmd_restore)

    sp = sub.add_parser("verify")
    sp.add_argument("name")
    sp.set_defaults(func=_cmd_verify)

    sp = sub.add_parser("delete")
    sp.add_argument("name")
    sp.set_defaults(func=_cmd_delete)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
