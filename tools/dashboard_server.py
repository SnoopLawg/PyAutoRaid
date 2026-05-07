"""
PyAutoRaid dashboard HTTP server.

Serves gui/dashboard/ static files and exposes /api/state, which aggregates
real data from the mod API, memory reader, DB, and psutil. Dashboard polls
/api/state every ~1s; missing slices fall back to the JS simulation.

Run:
    python tools/dashboard_server.py
    # then open http://localhost:8000/PyAutoRaid%20Dashboard.html

Phase 1 wired: layers (mod/memory/screen), account (level/power), vm (cpu/ram).
Everything else currently returns null and the dashboard keeps its sim values.
"""

import datetime
import http.server
import json
import logging
import os
import re
import socketserver
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from Modules.mod_client import ModClient  # noqa: E402
from tools.sell_rules import (  # noqa: E402
    DEFAULT_CONFIG as _SELL_DEFAULT,
    evaluate_all as _eval_sell,
    load_rules as _load_sell,
    save_rules as _save_sell,
)
from tools.champ_manager import (  # noqa: E402
    plan_skill_ups as _cm_plan_skill_ups,
    plan_rank_ups as _cm_plan_rank_ups,
    plan_multi_pass as _cm_plan_multi_pass,
    load_reserved as _cm_load_reserved,
    load_protected as _cm_load_protected,
    load_skills_db as _cm_load_skills_db,
)
from tools.rank_up_chain import (  # noqa: E402
    plan_session as _ruc_plan_session,
    plan_one_target as _ruc_plan_one_target,
    is_food_eligible as _ruc_is_food_eligible,
)

# Override to point proxy at a remote mod (e.g. PYAUTORAID_MOD_URL=http://mothership2:6790)
MOD_URL = os.environ.get("PYAUTORAID_MOD_URL", "http://localhost:6790")

# Display-name maps for Raid enums centralised in tools/raid_names.
from tools.raid_names import (  # noqa: E402
    RARITY_NAMES, FACTION_NAMES, FACTION_PRETTY as _FACTION_PRETTY,
    ROLE_NAMES as _HERO_ROLE_NAMES, ELEMENT_NAMES as _HERO_ELEMENT_NAMES,
)

# CB element/affinity + day-window math live in tools/cb_day.py
# (CLI: `python3 tools/cb_day.py` prints today's CB window + affinity).
from tools.cb_day import (  # noqa: E402
    CB_RESET_UTC_HOUR,
    ELEMENT_NAMES as _ELEMENT_NAMES,
    CB_TID_TO_ELEMENT as _CB_TID_TO_ELEMENT,
    cb_affinity_name as _cb_affinity_name,
    cb_day_for_timestamp as _cb_day_for_timestamp,
    cb_day_today as _cb_day_today,
)

# compute_hero_actual_stats — domain logic lives in tools/hero_stats.py
# (with its own CLI: `python3 tools/hero_stats.py "<name>"`). The dashboard
# is one consumer; CLI is another. Same code path either way.
from tools.hero_stats import compute_hero_actual_stats  # noqa: E402, F401
logger = logging.getLogger("dashboard_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DASHBOARD_DIR = ROOT / "gui" / "dashboard"
DB_PATH = ROOT / "pyautoraid.db"
BATTLE_LOG_PATH = ROOT / "battle_logs_cb_latest.json"
HISTORY_PATH = ROOT / "data" / "dashboard_history.jsonl"
PORT = 8000

# Cache heavy parses; invalidate by mtime
_battle_log_cache = {"mtime": None, "data": None}
_heroes_cache = {"mtime": None, "data": None}

# ---------- lazy singletons ----------

_mod_client = None
_memory_reader = None
_memory_attach_last = 0.0
_screen_state = None
MEMORY_RETRY_COOLDOWN = 30.0  # seconds between attach attempts if not yet attached

# Heroes are expensive to read (~471 * 4 memory reads), cache for 60s
_heroes_mem_cache = {"ts": 0.0, "data": None}
HEROES_CACHE_TTL = 60.0

# Artifacts are fetched via paginated mod API; cache for 60s.
_artifacts_cache = {"ts": 0.0, "data": None}
ARTIFACTS_CACHE_TTL = 60.0

# Full /all-heroes payload (shared between build_heroes and build_artifacts for
# equipped-artifact cross-referencing). Refetched every 60s.
_all_heroes_cache = {"ts": 0.0, "data": None}
ALL_HEROES_CACHE_TTL = 60.0

ARTIFACT_SLOTS = {
    1: "Helmet", 2: "Chest", 3: "Gloves", 4: "Boots",
    5: "Weapon", 6: "Shield", 7: "Ring", 8: "Amulet", 9: "Banner",
}
ARTIFACT_STATS = {1: "HP", 2: "ATK", 3: "DEF", 4: "SPD", 5: "RES", 6: "ACC", 7: "CR", 8: "CD"}


def mod_client():
    global _mod_client
    if _mod_client is None:
        _mod_client = ModClient(base_url=MOD_URL)
    return _mod_client


def memory_reader():
    """Return MemoryReader if attached, else None. Retries every 30s if not yet attached."""
    global _memory_reader, _memory_attach_last
    if _memory_reader and _memory_reader.is_attached:
        return _memory_reader
    now = time.time()
    if now - _memory_attach_last < MEMORY_RETRY_COOLDOWN:
        return None
    _memory_attach_last = now
    try:
        from Modules.memory_reader import MemoryReader
        reader = _memory_reader or MemoryReader()
        if reader.attach():
            _memory_reader = reader
            logger.info("MemoryReader attached")
            return reader
        else:
            logger.info("MemoryReader could not attach (game may still be loading)")
    except Exception as e:
        logger.info("MemoryReader import/attach failed: %s", e)
    return None


# ---------- slice builders ----------

def probe_mod():
    start = time.perf_counter()
    client = mod_client()
    try:
        status = client.get_status()
        latency_ms = int((time.perf_counter() - start) * 1000)
        scene = status.get("scene") if isinstance(status, dict) else None
        return {"up": True, "latency": latency_ms, "label": "BepInEx mod", "port": 6790,
                "detail": f"scene={scene}" if scene else "online"}
    except Exception as e:
        return {"up": False, "latency": None, "label": "BepInEx mod", "port": 6790,
                "detail": f"offline: {type(e).__name__}"}


def probe_memory():
    reader = memory_reader()
    if reader is None:
        return {"up": False, "latency": None, "label": "IL2CPP memory", "port": None,
                "detail": "not attached"}
    start = time.perf_counter()
    try:
        _ = reader.is_attached
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {"up": True, "latency": latency_ms, "label": "IL2CPP memory", "port": None,
                "detail": "pymem attached"}
    except Exception as e:
        return {"up": False, "latency": None, "label": "IL2CPP memory", "port": None,
                "detail": f"error: {type(e).__name__}"}


def probe_screen():
    return {"up": False, "latency": None, "label": "Screen automation", "port": None,
            "detail": "not initialized"}


def build_account():
    """Live from memory reader; falls back to DB if memory unavailable."""
    reader = memory_reader()
    if reader is not None:
        try:
            return {
                "level": reader.get_account_level(),
                "power": int(reader.get_total_power() or 0),
                "name": None,
                "vault_rank": None,
            }
        except Exception as e:
            logger.info("build_account (memory) failed: %s", e)
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM account LIMIT 1").fetchone()
        power = conn.execute(
            "SELECT COALESCE(SUM(power), 0) AS total FROM hero_computed_stats"
        ).fetchone()
        conn.close()
        if not row:
            return None
        cols = row.keys()
        return {
            "level": row["account_level"] if "account_level" in cols else None,
            "power": (power["total"] if power else None),
            "name": row["name"] if "name" in cols else None,
            "vault_rank": row["vault_rank"] if "vault_rank" in cols else None,
        }
    except Exception as e:
        logger.info("build_account failed: %s", e)
        return None


def build_vm():
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {
            "host": "local",
            "ip": None,
            "cpu": psutil.cpu_percent(interval=None),
            "ram": round(vm.used / (1024**3), 2),
            "ramMax": round(vm.total / (1024**3), 2),
        }
    except Exception as e:
        logger.info("build_vm failed: %s", e)
        return None


def build_resources():
    """Prefer mod /resources (stateless, reliable). Fall back to memory reader
    only if mod is offline. A cached MemoryReader can go stale when the game
    rebuilds singletons (Raid restart, specific scene transitions) and silently
    return all zeros; the mod endpoint doesn't have this failure mode."""
    global _memory_reader, _memory_attach_last
    client = mod_client()
    if client.available:
        try:
            r = client._get("/resources") or {}
            # Whole-key resources regenerate fractionally; /resources rounds so
            # 1.64 -> 2. Prefer the float values from /all-resources and floor.
            out = {
                "energy": int(r.get("energy", 0)),
                "silver": int(r.get("silver", 0)),
                "gems": int(r.get("gems", 0)),
                "arena_tokens": float(r.get("arena_tokens", 0)),
                "cb_keys": int(r.get("cb_keys", 0)),
                "mystery_shards": None, "ancient_shards": None,
                "void_shards": None, "sacred_shards": None, "primal_shards": None,
                "keys": {},
            }
            # Pre-floor cb_keys from the fractional source if available
            try:
                allres0 = client._get("/all-resources") or {}
                import math
                if "AllianceBossKey" in allres0:
                    out["cb_keys"] = int(math.floor(allres0["AllianceBossKey"]))
                if "Tokens" in allres0:
                    out["arena_tokens"] = float(allres0["Tokens"])
            except Exception:
                pass
            # Full resources dump for all the key/token types (Hydra, Chimera,
            # Fortress, Doom Tower, etc.). Single call gets ~88 named resources.
            try:
                allres = client._get("/all-resources") or {}
                keymap = {
                    "classic_arena_tokens": "Tokens",
                    "tag_arena_tokens":     "Arena3X3Tokens",
                    "live_arena_tokens":    "LiveArenaTokens",
                    "demon_lord_keys":      "AllianceBossKey",
                    "hydra_keys":           "AllianceHydraKeys",
                    "chimera_keys":         "AllianceChimeraKeys",
                    "fortress_keys":        "FortressKeys",
                    "cursed_city_keys":     "CursedCityKeys",
                    "doom_tower_gold_keys": "DoomTowerGoldKeys",
                    "doom_tower_silver_keys": "DoomTowerSilverKeys",
                    "auto_tickets":         "AutoBattleTickets",
                    "faction_keys":         "FortressKeys",  # Faction Wars uses the same keys
                }
                import math
                for out_k, src_k in keymap.items():
                    if src_k in allres:
                        # Floor fractional regenerating keys/tokens so the UI
                        # matches the in-game whole-key counter.
                        out["keys"][out_k] = int(math.floor(float(allres[src_k])))
                # Include the full raw map so the dashboard can render every
                # resource type the game exposes (crafting mats, soul coins,
                # foggy forest tokens, etc.) — UI displays them as a flat
                # grid with empty frame for icons we haven't extracted.
                out["all_raw"] = {k: float(v) for k, v in allres.items()}
            except Exception as e:
                logger.info("mod /all-resources failed: %s", e)
            # Shards come from a separate endpoint (/shards) since they live on
            # UserWrapper.Shards.ShardData.Shards, not in Resources.
            try:
                s = client._get("/shards") or {}
                shards = s.get("shards") or {}
                if shards:
                    out["mystery_shards"] = shards.get("mystery")
                    out["ancient_shards"] = shards.get("ancient")
                    out["void_shards"] = shards.get("void")
                    out["sacred_shards"] = shards.get("sacred")
                    out["primal_shards"] = shards.get("primal")
            except Exception as e:
                logger.info("mod /shards failed: %s", e)
            return out
        except Exception as e:
            logger.info("mod /resources failed: %s", e)
    reader = memory_reader()
    if reader is None:
        return None
    try:
        r = reader.get_resources()
        result = {
            "energy": int(r.get("energy", 0)),
            "silver": int(r.get("silver", 0)),
            "gems": int(r.get("gems", 0)),
            "arena_tokens": float(r.get("arena_tokens", 0)),
            "cb_keys": int(r.get("cb_keys", 0)),
        }
        # Stale-pointer detection: if everything is zero but the game is running
        # and logged in, force a re-attach on the next call.
        if client.available and all(v == 0 for v in result.values()):
            logger.info("memory reader returning zeros - forcing re-attach")
            try: reader.detach()
            except Exception: pass
            _memory_reader = None
            _memory_attach_last = 0.0
        return result
    except Exception as e:
        logger.info("build_resources (memory) failed: %s", e)
        return None


def build_arena_opponents():
    reader = memory_reader()
    if reader is None:
        return None
    try:
        opps = reader.get_arena_opponents() or []
        player_power = reader.get_total_power() if hasattr(reader, "get_total_power") else 0
        out = []
        weakest_idx = None
        weakest_pow = float("inf")
        for i, o in enumerate(opps[:5]):
            name = o.get("name") or "?"
            power = int(o.get("power") or 0)
            available = bool(o.get("available", True))
            if player_power and power:
                ratio = power / player_power
                if ratio < 0.85: status = "weak"
                elif ratio < 1.15: status = "fair"
                else: status = "strong"
            else:
                status = "fair"
            tier = f"{int(o.get('points',0))} pts"
            out.append({"name": name, "power": power, "tier": tier,
                        "status": status, "pick": False})
            if available and status == "weak" and power < weakest_pow:
                weakest_pow = power
                weakest_idx = i
        if weakest_idx is not None:
            out[weakest_idx]["pick"] = True
        return out
    except Exception as e:
        logger.info("build_arena_opponents failed: %s", e)
        return None


# _HERO_ROLE_NAMES, _HERO_ELEMENT_NAMES — re-exported from tools/raid_names


def _fetch_all_heroes():
    """Shared paginated /all-heroes fetch. Returns list of raw hero dicts."""
    client = mod_client()
    if not client.available:
        return None
    now = time.time()
    if _all_heroes_cache["data"] and (now - _all_heroes_cache["ts"]) < ALL_HEROES_CACHE_TTL:
        return _all_heroes_cache["data"]
    try:
        out, offset, page_size = [], 0, 100
        for _ in range(20):  # hard cap 2000 heroes
            r = client._get(f"/all-heroes?offset={offset}&limit={page_size}") or {}
            hs = r.get("heroes") or []
            if not hs:
                break
            out.extend(hs)
            if len(hs) < page_size:
                break
            offset += page_size
        _all_heroes_cache["ts"] = now
        _all_heroes_cache["data"] = out
        return out
    except Exception as e:
        logger.info("_fetch_all_heroes failed: %s", e)
        return None


def build_heroes():
    """Prefer mod /all-heroes (has empower, skills, equipped artifacts). Fall
    back to memory reader, then DB."""
    all_heroes = _fetch_all_heroes()
    if all_heroes is not None:
        out = []
        for h in all_heroes:
            rarity = RARITY_NAMES.get(h.get("rarity") or 0, "Unknown")
            faction = FACTION_NAMES.get(h.get("fraction") or 0, "Unknown")
            bs = h.get("base_stats") or {}
            skill_levels = [sk.get("level", 0) for sk in (h.get("skills") or [])]
            equipped = h.get("artifacts") or []
            # Masteries are 6-digit IDs shaped 500XYZ: X=tree (1=Offense,2=Defense,3=Support)
            masteries = h.get("masteries") or []
            tree_counts = [0, 0, 0]
            for mid in masteries:
                tree = (mid // 100) % 10  # extract X from 500XYZ
                if 1 <= tree <= 3:
                    tree_counts[tree - 1] += 1
            # Blessing: DoubleAscendData.Grade / BlessingId (if present)
            dbl = h.get("_dbl_ascend_debug") or {}
            ascend_grade = 0
            try:
                ascend_grade = int(dbl.get("grade") or 0)
            except Exception:
                pass
            blessing_id = h.get("blessing_id") or 0
            out.append({
                "id": h.get("id"),
                "type_id": h.get("type_id"),
                "name": h.get("name") or f"#{h.get('type_id')}",
                "faction": _FACTION_PRETTY.get(faction, faction),
                "rarity": rarity,
                "stars": h.get("grade") or 0,
                "level": h.get("level") or 0,
                "empower": h.get("empower") or 0,
                "role": _HERO_ROLE_NAMES.get(h.get("role") or 0, "?"),
                "element": _HERO_ELEMENT_NAMES.get(h.get("element") or 0, "?"),
                "skills": skill_levels,
                "equipped_count": len(equipped),
                "equipped_ids": [a.get("id") for a in equipped],
                "mastery_count": h.get("mastery_count") or len(masteries),
                "mastery_trees": tree_counts,  # [offense, defense, support]
                "ascend_grade": ascend_grade,  # Double-ascension stars (0-3)
                "blessing_id": blessing_id,
                "locked": bool(h.get("locked", False)),
                "in_storage": bool(h.get("in_storage", False)),
                "power": int(sum((bs.get(k) or 0) for k in ("HP","ATK","DEF","SPD"))),
            })
        out.sort(key=lambda x: (x["rarity"] != "Legendary", -(x["stars"] * 100 + x["level"])))
        return out

    reader = memory_reader()
    now = time.time()
    if reader is not None:
        if _heroes_mem_cache["data"] and (now - _heroes_mem_cache["ts"]) < HEROES_CACHE_TTL:
            return _heroes_mem_cache["data"]
        try:
            raw = reader.get_heroes(with_names=True)
            out = []
            for h in raw:
                rarity = h.get("rarity") or "Unknown"
                faction = h.get("faction") or "Unknown"
                out.append({
                    "name": h.get("name") or f"#{h.get('type_id')}",
                    "faction": _FACTION_PRETTY.get(faction, faction),
                    "rarity": rarity,
                    "stars": h.get("grade") or 0,
                    "level": h.get("level") or 0,
                    "empower": 0, "role": "?", "element": "?",
                    "skills": [], "equipped_count": 0, "equipped_ids": [],
                    "power": 0,
                })
            out.sort(key=lambda x: (x["rarity"] != "Legendary", -(x["stars"] * 100 + x["level"])))
            _heroes_mem_cache["ts"] = now
            _heroes_mem_cache["data"] = out
            return out
        except Exception as e:
            logger.info("build_heroes (memory) failed: %s", e)

    if not DB_PATH.exists():
        return None
    try:
        mtime = DB_PATH.stat().st_mtime
        if _heroes_cache["mtime"] == mtime and _heroes_cache["data"]:
            return _heroes_cache["data"]
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT h.name, h.grade, h.level, h.rarity, h.fraction,
                   h.base_hp, h.base_atk, h.base_def, h.base_spd,
                   h.base_res, h.base_acc, h.base_cr, h.base_cd
              FROM heroes h
        """).fetchall()
        conn.close()
        out = []
        for r in rows:
            d = dict(r)
            stats = [d.get(c) or 0 for c in ("base_hp","base_atk","base_def","base_spd","base_res","base_acc","base_cr","base_cd")]
            out.append({
                "name": d["name"],
                "faction": FACTION_NAMES.get(d["fraction"] or 0, "Unknown"),
                "rarity": RARITY_NAMES.get(d["rarity"] or 0, "Unknown"),
                "stars": d["grade"] or 0,
                "level": d["level"] or 0,
                "power": int(sum(stats)),
            })
        out.sort(key=lambda h: (h["rarity"] != "Legendary", -h["power"]))
        _heroes_cache["mtime"] = mtime
        _heroes_cache["data"] = out
        return out
    except Exception as e:
        logger.info("build_heroes failed: %s", e)
        return None


def build_artifacts():
    """Fetch artifact inventory via paginated mod /all-artifacts. Returns a
    compact list suitable for the dashboard table. Cached 60s — pages can be
    large (2k+ artifacts) so we don't refetch on every poll."""
    client = mod_client()
    if not client.available:
        return None
    now = time.time()
    if _artifacts_cache["data"] and (now - _artifacts_cache["ts"]) < ARTIFACTS_CACHE_TTL:
        return _artifacts_cache["data"]
    # Try to import set-name lookup from tools/gear_constants.py
    set_names = {}
    try:
        from gear_constants import SET_NAMES
        set_names = SET_NAMES
    except Exception:
        pass
    # Build equipped-artifact index from /all-heroes so every artifact can be
    # annotated with the hero it's currently on (if any).
    equipped_idx = {}  # artifact_id -> {hero_id, hero_name}
    try:
        for h in (_fetch_all_heroes() or []):
            for a in (h.get("artifacts") or []):
                aid = a.get("id")
                if aid:
                    equipped_idx[aid] = {"hero_id": h.get("id"), "hero_name": h.get("name")}
    except Exception:
        pass
    try:
        out = []
        offset, page_size, hard_cap = 0, 500, 5000
        while offset < hard_cap:
            r = client._get(f"/all-artifacts?offset={offset}&limit={page_size}") or {}
            arts = r.get("artifacts") or []
            if not arts:
                break
            for a in arts:
                kind = a.get("kind") or 0
                pr = a.get("primary") or {}
                subs = []
                sub_stats = set()
                for sb in (a.get("substats") or []):
                    stat = ARTIFACT_STATS.get(sb.get("stat"), "")
                    sub_stats.add(stat)
                    subs.append({
                        "stat": stat,
                        "value": sb.get("value", 0),
                        "flat": bool(sb.get("flat", False)),
                        "rolls": sb.get("rolls", 0),
                        "glyph": sb.get("glyph", 0),
                    })
                equipped = equipped_idx.get(a.get("id"))
                out.append({
                    "id": a.get("id"),
                    "level": a.get("level", 0),
                    "rank": a.get("rank", 0),
                    "rarity": a.get("rarity", 0),
                    "set_id": a.get("set", 0),
                    "set_name": set_names.get(a.get("set", 0), f"set {a.get('set', 0)}"),
                    "slot": ARTIFACT_SLOTS.get(kind, f"slot {kind}"),
                    "slot_id": kind,
                    "primary_stat": ARTIFACT_STATS.get(pr.get("stat"), ""),
                    "primary_value": pr.get("value", 0),
                    "primary_flat": bool(pr.get("flat", False)),
                    "substats": subs,
                    "sub_count": len(subs),
                    "sub_stat_set": sorted(sub_stats),
                    "equipped_on": equipped,
                })
            last_id = r.get("last_id") or 0
            if len(arts) < page_size or last_id == 0:
                break
            offset += page_size
        out.sort(key=lambda x: (-x["rank"], -x["rarity"], -x["level"]))
        _artifacts_cache["ts"] = now
        _artifacts_cache["data"] = out
        return out
    except Exception as e:
        logger.info("build_artifacts failed: %s", e)
        return None


# Sell-rules pipeline lives in tools/sell.py — same module backs the CLI
# (`python3 tools/sell.py preview|execute|history`). The dashboard wraps
# the pure functions to inject its module-level state (artifact cache,
# DB path, mod client, history file).
from tools import sell as _sell  # noqa: E402

_SELL_HISTORY_PATH = ROOT / "data" / "sell_history.jsonl"


def _all_artifacts_for_rules():
    return _sell.all_artifacts_for_rules(
        db_path=DB_PATH,
        in_memory_cache=_artifacts_cache,
        fallback_loader=build_artifacts,
    )


def _invalidate_artifact_cache():
    _sell.invalidate_artifact_cache(_artifacts_cache)


def _artifacts_from_sqlite():
    return _sell.artifacts_from_sqlite(DB_PATH)


def _append_sell_history(entry: dict) -> None:
    _sell.append_sell_history(_SELL_HISTORY_PATH, entry)


def _run_bulk_sell(ids: list[int], source: str = "dashboard") -> dict:
    return _sell.run_bulk_sell(
        ids, source,
        mod_client=mod_client(),
        db_path=DB_PATH,
        history_path=_SELL_HISTORY_PATH,
        in_memory_cache=_artifacts_cache,
        fallback_loader=build_artifacts,
    )


def build_events():
    """Live from memory reader."""
    reader = memory_reader()
    if reader is None:
        return None
    try:
        active = reader.get_active_events() or {}
        solo = active.get("solo_events") or []
        tourns = active.get("tournaments") or []
        out = []
        for e in solo:
            out.append({
                "name": e.get("name") or "Event",
                "type": "solo",
                "progress": float(e.get("progress") or 0),
                "reward": e.get("reward") or "",
                "ends_in": e.get("ends_in") or "",
            })
        for e in tourns:
            out.append({
                "name": e.get("name") or "Tournament",
                "type": "tournament",
                "progress": float(e.get("progress") or 0),
                "reward": e.get("reward") or "",
                "ends_in": e.get("ends_in") or "",
            })
        return out
    except Exception as e:
        logger.info("build_events failed: %s", e)
        return None


# Battle-log loaders + per-key history live in tools/cb_history.py
# (CLI: `python3 tools/cb_history.py history|last-run`). The dashboard
# uses thin wrappers that share its in-memory _battle_log_cache so
# repeated polls don't re-parse the JSON.
from tools import cb_history as _cb_history  # noqa: E402


def _most_recent_battle_log():
    return _cb_history.most_recent_battle_log(ROOT)


def _load_battle_log():
    return _cb_history.load_battle_log(ROOT, cache=_battle_log_cache)


def _hero_type_to_name():
    return _cb_history.hero_type_to_name(ROOT)


_STATUS_ID_TO_NAME = {}
try:
    from status_effect_map import STATUS_EFFECT_MAP as _SEM
    # Pretty-print the name: "dec_atk" -> "Dec ATK"
    def _pretty(s):
        return s.replace("_", " ").replace("pct", "%").title().replace("Pct", "%").replace("Cd", "CD").replace("Cr", "CR").replace("Atk", "ATK").replace("Def", "DEF").replace("Spd", "SPD").replace("Acc", "ACC").replace("Res", "RES")
    for tid, (name, is_debuff, is_buff) in _SEM.items():
        _STATUS_ID_TO_NAME[tid] = _pretty(name)
except Exception:
    pass
# Extensions for StatusEffectTypeIds not yet in tools/status_effect_map.py.
# These are game IDs observed in real battle logs that need friendly names.
_STATUS_ID_TO_NAME.update({
    230: "Dec CR 15",
    231: "Dec CR",
    730: "Dec RES",      # observed; companion to inc_res
    740: "Cooldown",     # placeholder — seen on CB, needs confirmation
    741: "Cooldown",
})


# Common debuff effect IDs (from Modules/status_effect_map.py). The battle log's
# `eff[].e[].id` is a SkillEffectKindId enum value; these are the ones we see
# commonly on CB runs.
_CB_DEBUFF_EFFECTS = {
    80:  "Poison",
    131: "Dec ATK",
    151: "Dec DEF",
    160: "Dec SPD",
    170: "Dec CR",
    240: "Stun",
    260: "Sleep",
    270: "Freeze",
    280: "Fear",
    290: "True Fear",
    310: "HP Burn",          # legacy id
    350: "Weaken",
    360: "Hex",
    370: "Block Buffs",
    380: "Block Debuffs",
    390: "Block Revive",
    400: "Block Cooldown",
    410: "Heal Reduction",
    440: "Provoke",
    450: "Debuff Spread",
    460: "Leech",
    470: "HP Burn",
    500: "Poison Sensitivity",
    510: "Bomb",
}


def build_cb_per_key_history(days=7):
    """Aggregate per-run CB damage from saved battle_logs_cb_*.json files,
    grouped by CB window. Domain logic is in tools/cb_history.py."""
    return _cb_history.per_key_history(ROOT, days=days)


def build_cb_last_run():
    """Parse latest CB battle log into team breakdown + timeline.
    Domain logic is in tools/cb_history.py (CLI: `python3 tools/cb_history.py last-run`).
    """
    return _cb_history.build_last_run(
        ROOT,
        cache=_battle_log_cache,
        fetch_all_heroes=_fetch_all_heroes,
        status_id_to_name=_STATUS_ID_TO_NAME,
        compute_actual_stats=compute_hero_actual_stats,
    )




# ---------- Simulator bridge ------------------------------------------------
# Runs cb_sim on the same team + SPDs as the last battle log so the dashboard
# can show "Predicted" alongside "Actual" per boss turn. Deliberately cached
# by team fingerprint so repeated polls don't re-run the sim unnecessarily.
_sim_cache = {"fingerprint": None, "data": None}


def build_sim_last_run():
    """Return {"timeline": [...], "protection_by_turn": {...}} from cb_sim
    using the same team shape as the most recent saved battle log. Matches
    the format the UI renders for the real run so the two can be diffed."""
    real = build_cb_last_run()
    if not real:
        return {"error": "no battle log available"}
    team_rows = real.get("team") or []
    boss = real.get("boss") or {}
    cb_element = boss.get("element") or 4

    # Team fingerprint for cache invalidation (name + SPD + element)
    fp = tuple((h.get("name"), h.get("spd"), cb_element) for h in team_rows)
    if _sim_cache["fingerprint"] == fp and _sim_cache["data"] is not None:
        return _sim_cache["data"]

    # Lazy import to keep server startup cheap when sim isn't needed
    try:
        from cb_sim import CBSimulator, build_champion_minimal  # build_champion_minimal added below
    except Exception as e:
        return {"error": f"cb_sim import failed: {e}"}

    # Prefer hp_max from the saved battle log — that's the actual in-battle HP
    # including all gear + mastery + blessing contributions. The team_rows' hp
    # field is from compute_hero_actual_stats which underestimates because it
    # doesn't yet include arena/blessing/FG/relic contributions.
    hp_by_name = {}
    try:
        log_data = _load_battle_log() or {}
        for e in (log_data.get("log") or [])[:40]:
            if not isinstance(e, dict) or not e.get("heroes"):
                continue
            for h in e["heroes"]:
                if h.get("side") != "player":
                    continue
                nm = _hero_type_to_name().get(h.get("type_id"), f"#{h.get('id')}")
                hp_by_name[nm] = max(hp_by_name.get(nm, 0), int(h.get("hp_max") or 0))
    except Exception:
        pass

    # Detect team-wide speed aura from the lead hero's leader_skills. Same
    # mechanic DWJ exposes as a global "Speed aura" input — in-game it comes
    # from the leader slot's leader skill (stat=4=SPD, area 0 or 4 covers CB).
    speed_aura_pct = 0.0
    try:
        all_heroes = _fetch_all_heroes() or []
        heroes_by_name = {h.get("name"): h for h in all_heroes if h.get("name")}
        if team_rows:
            leader = heroes_by_name.get(team_rows[0].get("name")) or {}
            for ls in (leader.get("leader_skills") or []):
                if ls.get("stat") == 4 and ls.get("area") in (0, 4) and not ls.get("absolute"):
                    speed_aura_pct = max(speed_aura_pct, float(ls.get("amount") or 0))
    except Exception:
        pass

    try:
        champs = []
        for i, h in enumerate(team_rows, start=1):
            nm = h.get("name")
            real_hp = hp_by_name.get(nm) or (h.get("hp") or 30000)
            champs.append(build_champion_minimal(
                name=nm,
                position=i,
                speed=h.get("spd") or h.get("spd_base") or 100,
                hp=real_hp,
                defense=h.get("def") or 1000,
            ))
        # model_survival=True so the sim tracks HP; without it, the sim
        # interprets any UK/BD gap as an instakill which truncates the timeline.
        sim = CBSimulator(champs, cb_speed=190, cb_element=cb_element,
                          deterministic=True, model_survival=True,
                          cb_difficulty="ultra-nightmare",
                          speed_aura_pct=speed_aura_pct)
        # Unlimited — sim stops naturally when all heroes die (or when it
        # hits its 100K-tick safety net). No artificial cap, so the
        # prediction goes as far as the tune can actually sustain.
        result = sim.run(max_cb_turns=0)
        out = {
            "timeline": result.get("timeline", []),
            "protection_by_turn": result.get("protection_by_turn", {}),
            "cb_turns": result.get("cb_turns"),
            "team": [h.get("name") for h in team_rows],
        }
        _sim_cache["fingerprint"] = fp
        _sim_cache["data"] = out
        return out
    except Exception as e:
        return {"error": f"sim run failed: {e}"}


# Potential-teams scoring lives in tools/potential_teams.py with its own CLI:
#   python3 tools/potential_teams.py --top 10 [--runnable] [--json]
from tools import potential_teams as _potential_teams  # noqa: E402
from tools.cb_day import today_cb_element_str as _today_cb_element_str_impl  # noqa: E402


def build_potential_teams(max_count: int = 12):
    """Score all DWJ tunes against user's owned roster and return the top.
    Domain logic in tools/potential_teams.py."""
    return _potential_teams.build(max_count=max_count, root=ROOT)


# Back-compat wrappers — older build_X helpers still call these names.
def _today_cb_element_str() -> str | None:
    return _today_cb_element_str_impl(ROOT / "battle_logs_cb_latest.json")


def _last_cb_team_names() -> list[str]:
    return _potential_teams.last_cb_team_names(ROOT)




def build_cb_parity_sim(hash_: str | None = None, max_boss_turns: int = 25):
    """Run calc_parity_sim against a specific DWJ calc variant (by hash)
    or — if no hash is given — against the top-ranked runnable tune for
    the user's roster. Returns a cast timeline + summary suitable for the
    dashboard sim panel.
    """
    try:
        import calc_parity_sim as cps
        from dwj_tunes import load_all
    except Exception as e:
        return {"error": f"calc_parity_sim import failed: {e}"}

    dwj = load_all()
    variant = None
    if hash_:
        variant = dwj.variants_by_hash.get(hash_)
    if variant is None:
        # Fall back: pick top-ranked runnable tune's Ultra-Nightmare variant
        pt = build_potential_teams(max_count=1)
        if "potential_teams" in pt and pt["potential_teams"]:
            top = pt["potential_teams"][0]
            for link in top.get("calculator_links") or []:
                if "ultra" in (link.get("name") or "").lower():
                    variant = dwj.variants_by_hash.get(link.get("hash"))
                    break
            if variant is None and top.get("calculator_links"):
                variant = dwj.variants_by_hash.get(top["calculator_links"][0].get("hash"))
    if variant is None:
        return {"error": "no calc variant to simulate"}

    try:
        turns = cps.simulate(variant, max_boss_turns=max_boss_turns)
    except Exception as e:
        return {"error": f"sim run failed: {e}"}

    # Summarize cast counts per hero
    from collections import Counter
    cast_counts = Counter((t.actor_name, t.skill_alias) for t in turns)
    cast_summary = [
        {"actor": k[0], "skill": k[1], "count": n}
        for k, n in cast_counts.most_common()
    ]
    timeline = [{
        "turn": t.turn_number,
        "boss_turn": t.boss_turn_number,
        "actor": t.actor_name,
        "skill": t.skill_alias,
    } for t in turns]
    return {
        "variant": {
            "hash": variant.hash,
            "name": variant.name,
            "slug": variant.slug,
            "boss_speed": variant.boss_speed,
            "boss_difficulty": variant.boss_difficulty,
            "boss_affinity": variant.boss_affinity,
            "speed_aura": variant.speed_aura,
            "slots": [{
                "index": s.index,
                "name": s.name,
                "total_speed": s.total_speed,
                "base_speed": s.base_speed,
                "skill_configs": [{"alias": c.alias, "priority": c.priority,
                                    "delay": c.delay, "cooldown": c.cooldown}
                                  for c in s.skill_configs],
            } for s in variant.slots],
        },
        "turn_count": len(turns),
        "boss_turn_count": cps.count_boss_turns(turns),
        "cast_summary": cast_summary,
        "timeline": timeline,
    }


def build_tune_library():
    """Return all tunes from tools/tune_library.py in a UI-friendly shape."""
    try:
        from tune_library import TUNES
    except Exception as e:
        return {"error": f"tune_library import failed: {e}"}
    out = []
    for tune_id, t in TUNES.items():
        slots = []
        for s in t.slots:
            slots.append({
                "role": s.role,
                "speed_range": list(s.speed_range),
                "required_hero": s.required_hero,
                "opening": list(s.opening or []),
                "skill_priority": list(s.skill_priority or []),
                "needs_acc": s.needs_acc,
                "notes": s.notes,
            })
        out.append({
            "id": tune_id,
            "name": t.name,
            "type": t.tune_type,
            "difficulty": t.difficulty,
            "performance": t.performance,
            "affinities": t.affinities,
            "notes": t.notes,
            "slots": slots,
        })
    return {"tunes": out}


def build_tune_compliance(tune_id):
    """Compare current team SPDs vs the tune's bands. Returns a per-hero diff."""
    try:
        from tune_library import get_tune
    except Exception as e:
        return {"error": f"tune_library: {e}"}
    tune = get_tune(tune_id)
    if not tune:
        return {"error": f"tune not found: {tune_id}"}

    real = build_cb_last_run()
    team_rows = (real or {}).get("team") or []
    if not team_rows:
        # Fall back to /all-heroes default team mapping
        heroes = _fetch_all_heroes() or []
        wanted = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
        by_name = {h.get("name"): h for h in heroes}
        team_rows = []
        for nm in wanted:
            h = by_name.get(nm)
            if h:
                actual = compute_hero_actual_stats(h)
                team_rows.append({"name": nm, "spd": int(actual.get("SPD") or 0)})

    # Simple assignment: pair tune slots with team in slot order
    out = []
    for i, slot in enumerate(tune.slots):
        row = team_rows[i] if i < len(team_rows) else None
        hero = row.get("name") if row else "—"
        spd = row.get("spd") if row else 0
        lo, hi = slot.speed_range
        status = "on_target" if lo <= spd <= hi else ("too_fast" if spd > hi else "too_slow")
        delta = spd - ((lo + hi) // 2)
        out.append({
            "slot": i + 1,
            "role": slot.role,
            "hero": hero,
            "actual_spd": spd,
            "target_low": lo,
            "target_high": hi,
            "status": status,
            "delta": delta,
            "required_hero": slot.required_hero,
        })
    return {
        "tune": tune_id,
        "tune_name": tune.name,
        "slots": out,
    }


def build_sim_affinity_matrix():
    """Run cb_sim on all 4 CB affinities; report outcome per affinity.

    Uses run_tune (real preset + real gear) so the sim cycles UK/BD on the
    right cadence. Falls back to build_champion_minimal if a tune match
    can't be inferred (rare — usually only when the team isn't a known
    DWJ/library tune).
    """
    real = build_cb_last_run()
    if not real:
        return {"error": "no battle log available"}
    team_rows = real.get("team") or []
    try:
        from cb_sim import run_tune
    except Exception as e:
        return {"error": f"cb_sim import: {e}"}

    hero_names = [h.get("name") for h in team_rows]
    # Pick the tune to simulate. Default to myth_eater (the team the user
    # actually runs day-to-day); future enhancement: detect from preset.
    tune_id = "myth_eater"

    out = {}
    for elem_name, elem_id in [("Magic", 1), ("Force", 2), ("Spirit", 3), ("Void", 4)]:
        try:
            r = run_tune(tune_id, hero_names, cb_element=elem_id,
                         force_affinity=False, use_current_gear=True,
                         verbose=False)
            gaps = 0
            first_death = None
            for bt in sorted(r.get("protection_by_turn", {}), key=int):
                p = r["protection_by_turn"][bt]
                alive = [n for n, v in p.items() if v.get("alive")]
                if not alive and first_death is None:
                    first_death = int(bt)
                if alive and not all(p[n].get("uk") or p[n].get("bd") for n in alive):
                    gaps += 1
            out[elem_name.lower()] = {
                "affinity": elem_name,
                "cb_turns": r.get("cb_turns"),
                "total_damage": r.get("total") or r.get("total_damage"),
                "gaps": gaps,
                "first_death_bt": first_death,
            }
        except Exception as ex:
            out[elem_name.lower()] = {"affinity": elem_name, "error": str(ex)}
    return {"results": out}


def build_sim_sweep(hero_name, lo, hi):
    """Run sim with one hero's SPD varied across [lo, hi] in steps of 2.

    Reports (spd, cb_turns, damage, gaps) for each SPD value — finds the
    'sweet spot' SPD band where the tune holds.
    """
    real = build_cb_last_run()
    if not real:
        return {"error": "no battle log"}
    team_rows = real.get("team") or []
    try:
        from cb_sim import CBSimulator, build_champion_minimal
    except Exception as e:
        return {"error": f"cb_sim: {e}"}

    boss = real.get("boss") or {}
    cb_element = boss.get("element") or 4

    log = _load_battle_log() or {}
    hp_by_name = {}
    for e in (log.get("log") or [])[:40]:
        if not isinstance(e, dict) or not e.get("heroes"):
            continue
        for h in e["heroes"]:
            if h.get("side") != "player":
                continue
            nm = _hero_type_to_name().get(h.get("type_id"), f"#{h.get('id')}")
            hp_by_name[nm] = max(hp_by_name.get(nm, 0), int(h.get("hp_max") or 0))

    results = []
    for spd_try in range(lo, hi + 1, 2):
        champs = []
        for i, h in enumerate(team_rows, start=1):
            nm = h.get("name")
            use_spd = spd_try if nm == hero_name else (h.get("spd") or 100)
            champs.append(build_champion_minimal(
                name=nm, position=i,
                speed=use_spd,
                hp=hp_by_name.get(nm) or (h.get("hp") or 30000),
                defense=h.get("def") or 1000,
            ))
        sim = CBSimulator(champs, cb_speed=190, cb_element=cb_element,
                          deterministic=True, model_survival=True,
                          cb_difficulty="ultra-nightmare")
        r = sim.run(max_cb_turns=0)
        gaps = sum(1 for bt, p in r.get("protection_by_turn", {}).items()
                   if (alive := [n for n, v in p.items() if v.get("alive")])
                   and not all(p[n].get("uk") or p[n].get("bd") for n in alive))
        results.append({
            "spd": spd_try,
            "cb_turns": r.get("cb_turns"),
            "damage": r.get("total"),
            "gaps": gaps,
        })
    return {"hero": hero_name, "sweep": results}


def build_tune_recommend():
    """Run cb_sim against every tune for today's CB affinity and rank by damage.

    Uses the last-run battle log to source team composition. Today's CB
    affinity comes from the saved log's boss.element. Each tune is simulated
    independently; we don't re-assign team heroes between tunes because the
    user's actual roster is fixed — we just run the current team through
    each tune's role-based priority/opener pattern.
    """
    real = build_cb_last_run()
    if not real:
        return {"error": "no battle log available"}
    team_rows = real.get("team") or []
    boss = real.get("boss") or {}
    cb_element = boss.get("element") or 4
    try:
        from tune_library import TUNES
        from cb_sim import CBSimulator, build_champion_minimal
    except Exception as e:
        return {"error": f"import failed: {e}"}

    # Hero HPs from battle log, element from /all-heroes
    log = _load_battle_log() or {}
    hp_by_name = {}
    for e in (log.get("log") or [])[:40]:
        if not isinstance(e, dict) or not e.get("heroes"):
            continue
        for h in e["heroes"]:
            if h.get("side") != "player":
                continue
            nm = _hero_type_to_name().get(h.get("type_id"), f"#{h.get('id')}")
            hp_by_name[nm] = max(hp_by_name.get(nm, 0), int(h.get("hp_max") or 0))
    all_h = _fetch_all_heroes() or []
    elem_by_name = {h.get("name"): (h.get("element") or 4) for h in all_h}

    team_names_set = {(h.get("name") or "").lower() for h in team_rows}
    results = []
    for tune_id, tune in TUNES.items():
        # Compatibility check: any slot's required_hero not in our team => skip
        missing = []
        for slot in tune.slots:
            if slot.required_hero and slot.required_hero.lower() not in team_names_set:
                missing.append(slot.required_hero)
        if missing:
            results.append({
                "tune": tune_id, "name": tune.name,
                "difficulty": tune.difficulty, "performance": tune.performance,
                "incompatible": True, "missing_heroes": missing,
            })
            continue
        try:
            champs = []
            for i, h in enumerate(team_rows, start=1):
                nm = h.get("name")
                c = build_champion_minimal(
                    name=nm, position=i,
                    speed=h.get("spd") or 100,
                    hp=hp_by_name.get(nm) or (h.get("hp") or 30000),
                    defense=h.get("def") or 1000,
                    element=elem_by_name.get(nm, 4),
                )
                # Apply tune slot's opener + priority so the sim actually
                # differentiates this tune from others.
                slot = tune.slots[i-1] if i-1 < len(tune.slots) else None
                if slot:
                    if slot.opening:
                        c.opening = list(slot.opening)
                    if slot.skill_priority:
                        c.skill_priority = list(slot.skill_priority)
                champs.append(c)
            sim = CBSimulator(champs, cb_speed=190, cb_element=cb_element,
                              deterministic=True, model_survival=True,
                              cb_difficulty="ultra-nightmare", speed_aura_pct=0.0)
            r = sim.run(max_cb_turns=0)
            gaps = sum(1 for bt, p in r.get("protection_by_turn", {}).items()
                       if (alive := [n for n, v in p.items() if v.get("alive")])
                       and not all(p[n].get("uk") or p[n].get("bd") for n in alive))
            results.append({
                "tune": tune_id,
                "name": tune.name,
                "difficulty": tune.difficulty,
                "performance": tune.performance,
                "cb_turns": r.get("cb_turns"),
                "damage": r.get("total"),
                "gaps": gaps,
            })
        except Exception as ex:
            results.append({"tune": tune_id, "error": str(ex)})
    # Sort: compatible tunes by damage desc, then incompatibles by name
    results.sort(key=lambda x: (
        1 if x.get("incompatible") else 0,
        -(x.get("damage") or 0),
    ))
    return {
        "affinity": ["?", "Magic", "Force", "Spirit", "Void"][cb_element] if 0 <= cb_element <= 4 else "?",
        "results": results,
    }


# CB reset countdown + autorun live in dedicated CLI modules:
#   python3 tools/cb_day.py              — print today's window + next reset
#   python3 tools/cb_autorun.py status   — current autorun state
#   python3 tools/cb_autorun.py start    — enable + block, print fires
from tools.cb_day import reset_info as build_cb_reset_info  # noqa: E402, F401
from tools import cb_autorun as _autorun  # noqa: E402


# Back-compat shim — older /api/autorun handler reads _autorun_state.
class _AutorunStateProxy:
    def get(self, k, default=None):
        return _autorun.state().get(k, default)

    def __getitem__(self, k):
        return _autorun.state().get(k)


_autorun_state = _AutorunStateProxy()


def _autorun_worker():
    """Compat wrapper — older code paths called this directly to start the
    background thread. The new module exposes ensure_thread()."""
    _autorun.ensure_thread(MOD_URL, ROOT)


def build_cb_history_with_attribution():
    """Per-CB-key damage history with gear-change attribution.

    Walks all battle_logs_cb_*.json files in chronological order. For each
    team+run combo, fingerprints the team's equipped artifact IDs at the
    time of the run. When the fingerprint changes between runs, emits a
    `gear_change` marker along with the damage delta.

    Useful for answering "did the gear swap help?" — compares median damage
    before/after each gear change.
    """
    import glob
    runs = []
    for path in sorted(glob.glob(str(ROOT / "battle_logs_cb_*.json"))):
        name = Path(path).name
        if name == "battle_logs_cb_latest.json":
            continue
        try:
            mt = Path(path).stat().st_mtime
            cb_date = _cb_day_for_timestamp(mt).isoformat()
            data = json.loads(Path(path).read_text())
            entries = data.get("log", []) if isinstance(data, dict) else []
            # Per-run fingerprint = sorted artifact ids across all player heroes
            # in the first snapshot that includes them. Battle logs don't include
            # artifact lists directly, so we approximate with (team_type_ids,
            # hp_max per hero, dmg_taken per hero) which shifts on gear changes.
            max_dmg = 0
            team_key = None
            hp_per_hero = {}
            for e in entries:
                if not isinstance(e, dict) or not e.get("heroes"):
                    continue
                boss = next((h for h in e["heroes"] if h.get("side") == "enemy"), None)
                if boss:
                    max_dmg = max(max_dmg, int(boss.get("dmg_taken", 0) or 0))
                for h in e["heroes"]:
                    if h.get("side") == "player":
                        tid = h.get("type_id")
                        if tid:
                            hp_per_hero[tid] = max(hp_per_hero.get(tid, 0),
                                                    int(h.get("hp_max") or 0))
                if not team_key and e.get("heroes"):
                    ids = sorted(h.get("type_id") for h in e["heroes"]
                                  if h.get("side") == "player" and h.get("type_id"))
                    if ids:
                        team_key = tuple(ids)
            # Fingerprint = team members + rounded HP buckets (so a minor substat
            # tweak doesn't count as a gear change; a real set swap does)
            if team_key:
                hp_bucket = tuple(sorted((t, (hp_per_hero.get(t, 0) // 1000) * 1000)
                                          for t in team_key))
                fingerprint = str(hash((team_key, hp_bucket)) & 0xffffffff)
            else:
                fingerprint = None
            runs.append({
                "file": name,
                "cb_date": cb_date,
                "mtime": mt,
                "damage": max_dmg,
                "team": list(team_key) if team_key else [],
                "fingerprint": fingerprint,
            })
        except Exception:
            continue

    # Detect gear changes (fingerprint transitions) + attribute damage deltas
    gear_changes = []
    prev_fp = None
    prev_dmg_window = []  # rolling: last 3 runs' damage
    for i, r in enumerate(runs):
        fp = r.get("fingerprint")
        if prev_fp is not None and fp and fp != prev_fp:
            # Gear changed — compute median damage before/after
            before = prev_dmg_window[-3:] if prev_dmg_window else []
            after_idx = i
            after = []
            for j in range(i, min(i + 3, len(runs))):
                if runs[j].get("fingerprint") == fp:
                    after.append(runs[j].get("damage", 0))
            if before and after:
                med_before = sorted(before)[len(before) // 2]
                med_after = sorted(after)[len(after) // 2]
                gear_changes.append({
                    "run_index": i,
                    "cb_date": r["cb_date"],
                    "median_before": med_before,
                    "median_after": med_after,
                    "delta": med_after - med_before,
                    "pct_change": ((med_after - med_before) / max(1, med_before)) * 100,
                })
        prev_fp = fp or prev_fp
        prev_dmg_window.append(r.get("damage", 0))

    return {
        "runs": runs,
        "gear_changes": gear_changes,
    }


def build_tune_lab(slug: str | None = None, runnable_only: bool = False,
                   include_sim: bool = True, affinity: str | None = None,
                   projection: bool = True):
    """Per-tune blocker/todo/team output from tools/potential_team.

    Today's CB affinity is auto-detected from the latest battle log so
    Spirit-day tunes prefer the Spirit calc variant, etc. Pass an
    explicit `affinity` to override (used by the per-affinity drilldown
    in the dashboard modal).

    When include_sim is True (default), runs cb_sim.run_potential_team
    against each runnable tune to attach a real damage projection.
    Generic DPS slots fill from the user's most recent battle team so
    sim numbers reflect actual play.

    `projection` (default True, Phase 6): runs the sim with every
    stat-bonus mastery treated as taken, regardless of the user's actual
    mastery picks. Set to False for "what does this do with my current
    progression today" mode.
    """
    try:
        from potential_team import build_potential_team, load_data
        if include_sim:
            from cb_sim import run_potential_team
    except Exception as e:
        return {"error": f"potential_team import failed: {e}"}
    try:
        data = load_data()
        if affinity is None:
            affinity = _today_cb_element_str()
        tunes = data["tunes"]
        if slug:
            tunes = [t for t in tunes if t.get("slug") == slug]
        results = [build_potential_team(t, data, affinity) for t in tunes]
        if runnable_only:
            results = [r for r in results if not r["blockers"]]
        results.sort(key=lambda r: (len(r["blockers"]), len(r["todos"])))

        if include_sim:
            element_map = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
            cb_el = element_map.get((affinity or "void").lower(), 4)
            generic_fillers = _last_cb_team_names() or ["Ninja"]
            for r in results:
                if r["blockers"]:
                    r["sim"] = None
                    continue
                try:
                    sim_res = run_potential_team(
                        r, cb_element=cb_el, force_affinity=True,
                        max_cb_turns=50, generic_fillers=generic_fillers,
                        projection=projection,
                    )
                    if sim_res.get("partial_team"):
                        r["sim"] = {
                            "partial": True,
                            "missing_at_6star": sim_res.get("missing_at_6star"),
                        }
                    else:
                        r["sim"] = {
                            "total_damage": int(sim_res.get("total", 0) or 0),
                            "boss_turns": int(sim_res.get("cb_turns", 0) or 0),
                            "team_names": sim_res.get("potential_team_meta", {}).get("team_names"),
                            "warnings": len(sim_res.get("errors", [])),
                            "projection": sim_res.get("projection_meta") or {},
                        }
                except Exception as ex:
                    r["sim"] = {"error": str(ex)}

        return {
            "today_affinity": affinity,
            "total": len(tunes),
            "runnable": sum(1 for r in results if not r["blockers"]),
            "tunes": results,
        }
    except Exception as e:
        return {"error": f"tune-lab build failed: {e}"}


def build_tune_slot_alternatives(query: str):
    """Lazy-loaded generic-slot alternatives for one tune. For each
    is_generic slot in the tune, returns the top-N owned 6★ heroes by
    sim damage when substituted into that slot.
    """
    try:
        import urllib.parse as _u
        q = _u.parse_qs(query)
        slug = (q.get("slug") or [None])[0]
        affinity = (q.get("affinity") or [None])[0]
        top_n = int((q.get("top") or [5])[0])
        if not slug:
            return {"error": "missing slug"}
        from potential_team import build_potential_team, load_data
        from slot_alternatives import compute_slot_alternatives
        data = load_data()
        if affinity is None:
            affinity = _today_cb_element_str()
        tune = next((t for t in data["tunes"] if t.get("slug") == slug), None)
        if not tune:
            return {"error": f"tune {slug!r} not found"}
        pt = build_potential_team(tune, data, affinity)
        if pt.get("blockers"):
            return {"error": "tune has blockers", "blockers": pt["blockers"]}
        element_map = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
        cb_el = element_map.get((affinity or "void").lower(), 4)
        default_fillers = _last_cb_team_names() or ["Ninja"]
        out = compute_slot_alternatives(
            pt, default_fillers, cb_element=cb_el,
            top_n=top_n, cache_key=f"{slug}|{affinity}",
        )
        return out
    except Exception as e:
        return {"error": f"slot alternatives failed: {e}"}


def build_tune_gear_plan(query: str):
    """Lazy-loaded gear plan for one tune. Wraps potential_gear.compute_gear_plan_for_tune
    so the modal can fetch on demand without blocking the tune list.

    Cached results from data/gear_plans_cache.json return immediately
    when the user's vault hash matches.
    """
    try:
        import urllib.parse as _u
        q = _u.parse_qs(query)
        slug = (q.get("slug") or [None])[0]
        sa_iter = int((q.get("sa") or [500])[0])
        if not slug:
            return {"error": "missing slug"}
        from potential_team import build_potential_team, load_data
        from potential_gear import compute_gear_plan_for_tune
        data = load_data()
        affinity = _today_cb_element_str()
        tune = next((t for t in data["tunes"] if t.get("slug") == slug), None)
        if not tune:
            return {"error": f"tune {slug!r} not found"}
        pt = build_potential_team(tune, data, affinity)
        if pt.get("blockers"):
            return {"error": "tune has blockers", "blockers": pt["blockers"]}
        team = (pt.get("potential_team") or {}).get("team") or []
        # Resolve generic-DPS slots from the user's last battle team.
        named_in_tune = {(s.get("hero") or "").lower()
                         for s in team if not s.get("is_generic")}
        fillers = [n for n in (_last_cb_team_names() or ["Ninja"])
                   if n.lower() not in named_in_tune]
        f_iter = iter(fillers)
        resolved = []
        for s in team:
            if s.get("is_generic"):
                resolved.append({**s, "hero": next(f_iter, "Ninja")})
            else:
                resolved.append(s)
        element_map = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
        cb_el = element_map.get((affinity or "void").lower(), 4)
        plan = compute_gear_plan_for_tune(slug, resolved,
                                          sa_iterations=sa_iter, cb_element=cb_el)
        return {"slug": slug, "team": [s["hero"] for s in resolved], "plan": plan}
    except Exception as e:
        return {"error": f"gear plan failed: {e}"}


def build_sim_per_tune_accuracy():
    """Group data/sim_calibration_history.jsonl rows by tune_slug and
    surface mean / stddev / count per tune. Phase 4 of the plan: lets
    the dashboard detect per-tune drift instead of just an aggregate
    calibration error.
    """
    path = ROOT / "data" / "sim_calibration_history.jsonl"
    if not path.exists():
        return {"tunes": {}, "total_rows": 0}
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        return {"tunes": {}, "total_rows": 0}
    by_tune: dict[str, list[dict]] = {}
    for r in rows:
        slug = r.get("tune_slug") or "unknown"
        by_tune.setdefault(slug, []).append(r)
    out = {}
    import statistics
    for slug, rs in by_tune.items():
        # Only count "tuned" runs (>=30 boss turns) for accuracy stats —
        # wipes (low boss turns) just say sim>>real because the team
        # died early. Keep the wipe rows around in `all_rows` for context.
        tuned = [r for r in rs if (r.get("real_turns") or 0) >= 30]
        errs = [r["error_pct"] for r in tuned if isinstance(r.get("error_pct"), (int, float))]
        out[slug] = {
            "count": len(rs),
            "tuned_count": len(tuned),
            "mean_error_pct": round(statistics.mean(errs), 2) if errs else None,
            "median_error_pct": round(statistics.median(errs), 2) if errs else None,
            "stdev_error_pct": round(statistics.stdev(errs), 2) if len(errs) >= 2 else None,
            "drift_flag": (
                bool(errs) and abs(statistics.mean(errs)) > 10.0 and len(errs) >= 3
            ),
            "latest": rs[-1],
        }
    return {
        "tunes": out,
        "total_rows": len(rows),
        "drift_count": sum(1 for s in out.values() if s["drift_flag"]),
    }


def build_sim_calibration(limit: int = 30):
    """Read data/sim_calibration_history.jsonl and return the recent N rows
    plus a rolling summary (mean/median error_pct, count, latest delta).
    Used by the dashboard to surface sim drift over time.
    """
    path = ROOT / "data" / "sim_calibration_history.jsonl"
    if not path.exists():
        return {"rows": [], "count": 0, "mean_error_pct": None,
                "median_error_pct": None, "latest": None}
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        return {"rows": [], "count": 0, "mean_error_pct": None,
                "median_error_pct": None, "latest": None}
    rows.sort(key=lambda r: r.get("ts") or "")
    recent = rows[-limit:]
    errs = [r.get("error_pct") for r in rows if isinstance(r.get("error_pct"), (int, float))]
    mean_err = sum(errs) / len(errs) if errs else None
    median_err = (sorted(errs)[len(errs)//2] if errs else None)
    return {
        "rows": recent,
        "count": len(rows),
        "mean_error_pct": round(mean_err, 2) if mean_err is not None else None,
        "median_error_pct": round(median_err, 2) if median_err is not None else None,
        "latest": rows[-1] if rows else None,
    }


def build_gear_gaps(threshold: float = 4.0, min_rarity: int = 4, min_rank: int = 4,
                    top: int = 15, areas=None):
    """Run the artifact gap analysis and return a JSON-shape report.

    Wraps tools/gear_gap_analysis.build_gap_report so the dashboard can render
    the same data the CLI prints. Cheap (no I/O beyond JSON files), safe to
    call on demand.
    """
    try:
        import gear_gap_analysis as gga
    except Exception as e:
        return {"error": f"gear_gap_analysis import failed: {e}"}
    try:
        return gga.build_gap_report(
            threshold=threshold,
            min_rarity=min_rarity,
            min_rank=min_rank,
            areas=areas or gga.ALL_AREAS,
            top=top,
        )
    except Exception as e:
        return {"error": f"gear gap analysis failed: {e}"}


def _fetch_presets() -> dict | None:
    """Fetch /presets via the mod client and repair stray "{," sequences the
    mod sometimes emits. Used by build_preset_view + apply_tune_to_preset."""
    client = mod_client()
    if not client.available:
        return None
    try:
        raw = urllib.request.urlopen(f"{client.base_url}/presets", timeout=15).read().decode()
        return json.loads(re.sub(r"\{,", "{", raw))
    except Exception as e:
        logger.info("_fetch_presets failed: %s", e)
        return None


def build_preset_view(preset_id):
    """Return the preset with skill_type_id→label lookups attached so the
    dashboard can render opener + priority dropdowns cleanly."""
    data = _fetch_presets()
    if data is None:
        return {"error": "fetch presets failed"}
    presets = data.get("presets", [])
    heroes_meta = _fetch_all_heroes() or []
    hid_to_meta = {h.get("id"): h for h in heroes_meta}

    # Load skills_db for skill labels
    sdb_path = ROOT / "skills_db.json"
    skills_db = {}
    if sdb_path.exists():
        try:
            skills_db = json.loads(sdb_path.read_text())
        except Exception:
            pass

    def _skill_labels(hero_name):
        entries = skills_db.get(hero_name, [])
        seen = set()
        dedup = []
        for s in entries:
            sid = s.get("skill_type_id") or s.get("id", 0)
            if sid in seen:
                continue
            seen.add(sid)
            dedup.append(s)
        a1 = next((s for s in dedup if s.get("is_a1")), None)
        actives = sorted([s for s in dedup if not s.get("is_a1") and s.get("cooldown", 0)],
                         key=lambda s: s.get("cooldown", 99))
        labels = {}
        if a1:
            labels[a1.get("skill_type_id")] = {"label": "A1", "name": a1.get("name", ""), "cd": 0}
        for i, s in enumerate(actives[:3]):
            labels[s.get("skill_type_id")] = {
                "label": f"A{i+2}", "name": s.get("name", ""),
                "cd": s.get("cooldown", 0),
            }
        return labels

    target = next((p for p in presets if p.get("id") == preset_id), None)
    if not target:
        return {"error": f"preset {preset_id} not found"}

    out_heroes = []
    for h in target.get("heroes") or []:
        hid = h.get("hero_id")
        meta = hid_to_meta.get(hid) or {}
        name = meta.get("name", f"#{hid}")
        labels = _skill_labels(name)
        r1 = (h.get("rounds") or [{}])[0]
        out_heroes.append({
            "hero_id": hid,
            "name": name,
            "rarity": RARITY_NAMES.get(meta.get("rarity") or 0, ""),
            "starter_ids": r1.get("starter_ids") or [],
            "priorities": {str(k): v for k, v in (r1.get("priorities") or {}).items()},
            "skill_labels": {str(sid): lbl for sid, lbl in labels.items()},
        })
    return {
        "id": target.get("id"),
        "name": target.get("name"),
        "type": target.get("type"),
        "heroes": out_heroes,
    }


def edit_preset_raw(preset_id, heroes):
    """Push opener + priorities to /update-preset. Same logic as tune_to_preset
    but takes raw inputs instead of deriving from a tune."""
    prio_blocks = []
    starter_blocks = []
    for h in heroes:
        hid = h.get("hero_id")
        if not hid:
            continue
        pri_parts = []
        for sid, rank in (h.get("priorities") or {}).items():
            pri_parts.append(f"{sid}={rank}")
        prio_blocks.append(f"{hid}:{','.join(pri_parts)}")
        opener = h.get("opener")
        starter_blocks.append(f"{hid}:{opener}" if opener else f"{hid}:")
    priorities_raw = ";".join(prio_blocks)
    starters_raw = ";".join(starter_blocks)
    url = (
        f"{MOD_URL}/update-preset?id={preset_id}"
        f"&priorities={urllib.parse.quote(priorities_raw, safe='')}"
        f"&starters={urllib.parse.quote(starters_raw, safe='')}"
    )
    try:
        resp = urllib.request.urlopen(url, timeout=30).read().decode()
        return {"ok": True, "mod_response": json.loads(resp)}
    except Exception as e:
        return {"error": str(e)}


def apply_tune_to_preset(tune_id, preset_id):
    """Push a tune's opener + priority params to the in-game preset.

    Auto-derives per-hero skill IDs + opener + priority ranks from the
    tune's role→delays map and the user's current team in that preset.
    Supports all 5 tunes in tune_library via role-based delay lookup.
    """
    try:
        from tune_to_preset import build_update_preset_url as _build_url, TUNE_ROLE_DELAYS
    except Exception as e:
        return {"error": f"tune_to_preset import: {e}"}
    if tune_id not in TUNE_ROLE_DELAYS:
        return {"error": f"No delay map for tune '{tune_id}'. Available: {list(TUNE_ROLE_DELAYS.keys())}"}

    # Fetch current team names from the preset for ordered slot assignment
    team_names = []
    presets_data = _fetch_presets()
    if presets_data is not None:
        heroes_meta = _fetch_all_heroes() or []
        hid_to_name = {h.get("id"): h.get("name") for h in heroes_meta}
        for p in presets_data.get("presets", []):
            if p.get("id") != preset_id:
                continue
            for h in p.get("heroes", []):
                nm = hid_to_name.get(h.get("hero_id"))
                if nm:
                    team_names.append(nm)
            break

    if len(team_names) != 5:
        return {"error": f"Expected 5 heroes in preset #{preset_id}, found {len(team_names)}: {team_names}"}

    try:
        url, breakdown = _build_url(preset_id=preset_id, team_names=team_names, tune_id=tune_id)
        resp = urllib.request.urlopen(url, timeout=30).read().decode()
        return {
            "ok": True,
            "preset_id": preset_id,
            "tune": tune_id,
            "team": team_names,
            "breakdown": breakdown,
            "mod_response": json.loads(resp),
        }
    except Exception as e:
        return {"error": f"apply failed: {e}"}


def _ensure_today_snapshot(cb_damage):
    """Append today's snapshot to HISTORY_PATH if we don't already have one.
    Skips writing when resources are all zero (stale memory reader, mod down,
    or user on a loading screen) so we don't pollute the 14-day chart.

    CB damage is only attributed to today if battle_logs_cb_latest.json was
    modified today - otherwise today's cb_dmg_m is 0 (we can't claim damage
    from yesterday's log as today's output)."""
    # Staleness gate: use the most recent timestamped battle log's mtime.
    today_date = datetime.date.today()
    try:
        path = _most_recent_battle_log()
        if path is not None and path.exists():
            log_date = datetime.date.fromtimestamp(path.stat().st_mtime)
            if log_date != today_date:
                cb_damage = 0
        else:
            cb_damage = 0
    except Exception:
        cb_damage = 0

    res = {}
    client = mod_client()
    if client.available:
        try:
            res = client._get("/resources") or {}
        except Exception:
            res = {}
    if not res:
        reader = memory_reader()
        if reader is None:
            return
        try:
            res = reader.get_resources() or {}
        except Exception:
            return
    # Sanity gate: don't snapshot zeros
    if not any((res.get(k) or 0) > 0 for k in ("gems", "silver", "energy")):
        logger.info("skipping history snapshot - resources all zero")
        return
    today = datetime.date.today().isoformat()
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing_today_idx = None
    existing_today = None
    lines = []
    if HISTORY_PATH.exists():
        for i, line in enumerate(HISTORY_PATH.read_text().splitlines()):
            lines.append(line)
            try:
                e = json.loads(line)
                if e.get("date") == today:
                    existing_today_idx = i
                    existing_today = e
            except Exception:
                pass
    # Upgrade today's entry when new live data is available:
    if existing_today is not None:
        needs_shards = not existing_today.get("shards")
        needs_cb = (existing_today.get("cb_dmg_m") or 0) == 0 and (cb_damage or 0) > 0
        needs_tokens = "arena_tokens" not in existing_today
        if not needs_shards and not needs_cb and not needs_tokens:
            return
    # Capture current shard counts for per-shard history drilldown
    shards_today = {}
    try:
        sh = (client._get("/shards") or {}).get("shards") or {} if client.available else {}
        for k in ("mystery", "ancient", "void", "sacred", "primal"):
            if k in sh:
                shards_today[k] = int(sh[k])
    except Exception:
        pass
    entry = {
        "date": today,
        "day": today[5:],
        "gems": int(res.get("gems", 0)),
        "silver_m": round((res.get("silver") or 0) / 1e6, 2),
        "energy": int(res.get("energy", 0)),
        "arena_tokens": int(res.get("arena_tokens") or 0),
        "cb_keys": int(res.get("cb_keys") or 0),
        "battles": 0,
        "cb_dmg_m": round((cb_damage or 0) / 1e6, 2),
        "shards": shards_today,
    }
    if existing_today_idx is not None:
        # Replace today's line in-place (upgrade stale entry with shard data)
        lines[existing_today_idx] = json.dumps(entry)
        HISTORY_PATH.write_text("\n".join(lines) + "\n")
        logger.info("Upgraded today's snapshot with shards")
    else:
        with HISTORY_PATH.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info("Snapshotted %s", entry)


def build_history(cb_damage):
    """Return last 14 days of persisted snapshots. None if fewer than 1 exists."""
    _ensure_today_snapshot(cb_damage)
    if not HISTORY_PATH.exists():
        return None
    entries = []
    for line in HISTORY_PATH.read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    if not entries:
        return None
    return entries[-14:]


def _hero_summary(h):
    """Compact dict for dashboard transport — strips fields the UI doesn't need."""
    return {
        "id": h.get("id"),
        "type_id": h.get("type_id"),
        "name": h.get("name"),
        "rarity": h.get("rarity"),
        "grade": h.get("grade"),
        "level": h.get("level"),
        "element": h.get("element"),
        "faction": h.get("faction"),
    }


def build_champ_manager():
    """Skill-up + rank-up plan, computed from /all-heroes + reserved + protected.
    Single source of truth: tools/champ_manager.py."""
    heroes = _fetch_all_heroes() or []
    reserved = _cm_load_reserved()
    protected = _cm_load_protected()
    skills_db = _cm_load_skills_db()

    skill_plans, skill_consumed = _cm_plan_skill_ups(
        heroes, reserved, protected, skills_db)
    rank_plans, bottlenecked = _cm_plan_rank_ups(
        heroes, reserved, protected, pre_consumed=skill_consumed)
    multi = _cm_plan_multi_pass(heroes, reserved, protected, skills_db)

    return {
        "roster_total": len(heroes),
        "reserved_count": len(reserved),
        "multi_pass": multi,
        "protected": {
            "exclude_all_legendaries": protected.get("exclude_all_legendaries", True),
            "exclude_all_epics": protected.get("exclude_all_epics", False),
            "fusion_targets": protected.get("fusion_targets", []),
            "protected_names": protected.get("protected_names", []),
        },
        "skill_plans": [
            {
                "primary": _hero_summary(p["primary"]),
                "feeds": [_hero_summary(f) for f in p["feeds"]],
                "skill_levels": p["skill_levels"],
                "total_remaining": p["total_remaining"],
            }
            for p in skill_plans
        ],
        "rank_plans": [
            {
                "target": _hero_summary(p["target"]),
                "food": [_hero_summary(f) for f in p["food"]],
            }
            for p in rank_plans
        ],
        "bottlenecked": [
            {
                "target": _hero_summary(b["target"]),
                "needed": b["needed"], "available": b["available"],
                "missing": b["missing"],
            }
            for b in bottlenecked
        ],
        "skill_consumed_count": len(skill_consumed),
        "rank_consumed_count": sum(len(p["food"]) for p in rank_plans),
    }


def build_rank_up_chain(body: dict):
    """Recursive rank-up chain plan for a session of selected target heroes.
    Body: {"target_ids": [int], "to_grade": int}.
    Returns the same shape as rank_up_chain.plan_session.

    NOTE: 'rank-up' is the 1*->6* progression. NOT to be confused with
    'Ascension' (Sacred Ascend) which is a separate post-6* mechanic."""
    target_ids = body.get("target_ids") or []
    to_grade = int(body.get("to_grade") or 6)
    if not isinstance(target_ids, list) or not target_ids:
        return ({"error": "target_ids: non-empty list required"}, 400)
    try:
        target_ids = [int(x) for x in target_ids]
    except Exception:
        return ({"error": "target_ids must be integers"}, 400)

    heroes = _fetch_all_heroes() or []
    by_id = {h.get("id"): h for h in heroes}
    targets = [by_id[i] for i in target_ids if i in by_id]
    if not targets:
        return ({"error": "no matching heroes in roster"}, 400)
    reserved = _cm_load_reserved()
    protected = _cm_load_protected()

    result = _ruc_plan_session(heroes, targets, to_grade, reserved, protected)
    # consumed_ids is a set — convert for JSON.
    for p in result["plans"]:
        if isinstance(p.get("consumed_ids"), set):
            p["consumed_ids"] = sorted(p["consumed_ids"])
    return result


# --- Champion training (long-running six_star.py) -------------------
# Tracks one detached background subprocess. The dashboard exposes
# start/status/stop for the user to drive the rank-up cascade loop
# without keeping a Claude session open.
_six_star_state = {
    "pid": None,
    "target_id": None,
    "target_name": None,
    "started_at": None,
    "log_file": None,
}


def _six_star_log_path(target_name: str) -> Path:
    return Path(__file__).resolve().parent.parent / f"farm_{target_name}.log"


def _six_star_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        # Windows: tasklist /FI "PID eq N" returns the process line if alive
        rc = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return f" {pid} " in (rc.stdout or "") or f"\t{pid}\t" in (rc.stdout or "")
    except Exception:
        return False


def _super_raid_proxy(action: str):
    """Thin proxy to the mod's /super-raid endpoint. Lets the dashboard
    UI read state and toggle without exposing :6790 to the browser."""
    if action not in ("status", "toggle", "on", "off"):
        return ({"error": "action must be status|toggle|on|off"}, 400)
    try:
        with urllib.request.urlopen(f"{MOD_URL}/super-raid?action={action}", timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return ({"error": str(e)}, 502)


def six_star_plan(query: dict):
    """Return the cascade plan for a single target. Body/query: target_id=N&to_grade=6.
    Re-uses rank_up_chain.plan_one_target — same output as the existing
    /api/rank-up-chain endpoint but for one target with carry/stage hints."""
    try:
        tid = int(_q(query, "target_id") or 0)
    except Exception:
        return ({"error": "target_id (int) required"}, 400)
    if not tid:
        return ({"error": "target_id (int) required"}, 400)
    to_grade = int(_q(query, "to_grade", 6) or 6)

    heroes = _fetch_all_heroes() or []
    target = next((h for h in heroes if h.get("id") == tid), None)
    if not target:
        return ({"error": f"hero id {tid} not in roster"}, 404)
    reserved = _cm_load_reserved()
    protected = _cm_load_protected()
    plan = _ruc_plan_one_target(heroes, target, to_grade, reserved, protected)
    if isinstance(plan.get("consumed_ids"), set):
        plan["consumed_ids"] = sorted(plan["consumed_ids"])

    # Augment with food-eligible counts per grade so UI can show "what
    # commons/uncommons/rares we'll cascade through".
    counts = {g: 0 for g in range(1, 7)}
    eligible_samples_by_grade: dict[int, list] = {g: [] for g in range(1, 7)}
    for h in heroes:
        if not _ruc_is_food_eligible(h, reserved, protected):
            continue
        g = h.get("grade") or 0
        if 1 <= g <= 6:
            counts[g] = counts.get(g, 0) + 1
            if len(eligible_samples_by_grade[g]) < 12:
                eligible_samples_by_grade[g].append({
                    "id": h.get("id"), "name": h.get("name"),
                    "type_id": h.get("type_id"),
                    "rarity": h.get("rarity"),
                    "level": h.get("level"),
                })
    plan["pool_counts"] = counts
    plan["pool_samples"] = eligible_samples_by_grade
    plan["target"] = {
        "id": target.get("id"), "name": target.get("name"),
        "type_id": target.get("type_id"),
        "rarity": target.get("rarity"), "grade": target.get("grade"),
        "level": target.get("level"), "to_grade": to_grade,
        "element": target.get("element"),
    }
    plan["protections"] = {
        "exclude_legendaries": protected.get("exclude_all_legendaries", True),
        "exclude_epics": protected.get("exclude_all_epics", False),
        "protected_names": protected.get("protected_names", []),
        "fusion_targets": protected.get("fusion_targets", []),
    }
    return plan


def six_star_start(body: dict):
    """Spawn six_star.py as a detached subprocess; track PID for status/stop.
    Body: {target_id: N, target_name?: str, carry_id?: int, stage_name?: str}."""
    if _six_star_state["pid"] and _six_star_alive(_six_star_state["pid"]):
        return ({"error": "training already running",
                 "pid": _six_star_state["pid"],
                 "target": _six_star_state.get("target_name")}, 409)
    body = body or {}
    tid = int(body.get("target_id") or 0)
    if not tid:
        return ({"error": "target_id required"}, 400)
    heroes = _fetch_all_heroes() or []
    target = next((h for h in heroes if h.get("id") == tid), None)
    if not target:
        return ({"error": "target hero not in roster"}, 404)
    name = target.get("name")

    project_root = Path(__file__).resolve().parent.parent
    log_path = _six_star_log_path(name)
    # Open log file; subprocess inherits the FD so output streams live.
    log_fd = open(log_path, "a", buffering=1, encoding="utf-8")
    log_fd.write(f"\n\n=== six_star {name} started @ {datetime.datetime.utcnow().isoformat()}Z ===\n")
    log_fd.flush()

    args = [sys.executable, "-u", str(project_root / "tools" / "six_star.py"), name]
    if body.get("carry_id"):
        args += ["--carry", str(int(body["carry_id"]))]
    if body.get("stage_name"):
        args += ["--stage-name", str(body["stage_name"])]
    if body.get("to_grade"):
        args += ["--to-grade", str(int(body["to_grade"]))]

    # Detach via CREATE_NEW_PROCESS_GROUP + CREATE_BREAKAWAY_FROM_JOB so the
    # child survives this dashboard process exiting.
    creationflags = 0
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        creationflags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        args, cwd=str(project_root),
        stdout=log_fd, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    _six_star_state.update({
        "pid": proc.pid,
        "target_id": tid,
        "target_name": name,
        "started_at": datetime.datetime.utcnow().isoformat() + "Z",
        "log_file": str(log_path),
    })
    return {"ok": True, "pid": proc.pid, "target": name, "log": str(log_path)}


def six_star_status():
    """Live state of the running training task — pid + log tail + cascade snapshot."""
    pid = _six_star_state.get("pid")
    alive = bool(pid and _six_star_alive(pid))
    out = {
        "running": alive,
        "pid": pid,
        "target_id": _six_star_state.get("target_id"),
        "target_name": _six_star_state.get("target_name"),
        "started_at": _six_star_state.get("started_at"),
        "log_file": _six_star_state.get("log_file"),
    }
    # Log tail (last 60 lines)
    log_path = _six_star_state.get("log_file")
    if log_path and Path(log_path).exists():
        try:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-60:]
            out["log_tail"] = "".join(lines)
        except Exception:
            out["log_tail"] = ""

    # Live cascade snapshot
    heroes = _fetch_all_heroes() or []
    reserved = _cm_load_reserved()
    protected = _cm_load_protected()
    counts = {g: 0 for g in range(1, 7)}
    for h in heroes:
        if _ruc_is_food_eligible(h, reserved, protected):
            g = h.get("grade") or 0
            if 1 <= g <= 6:
                counts[g] = counts.get(g, 0) + 1
    out["fodder_counts"] = counts
    if _six_star_state.get("target_id"):
        cur = next((h for h in heroes if h.get("id") == _six_star_state["target_id"]), None)
        if cur:
            out["target_state"] = {
                "grade": cur.get("grade"), "level": cur.get("level"),
                "rarity": cur.get("rarity"),
            }
    return out


def six_star_stop():
    """Terminate the running training task, if any."""
    pid = _six_star_state.get("pid")
    if not pid:
        return {"ok": True, "note": "nothing running"}
    if not _six_star_alive(pid):
        _six_star_state.update({"pid": None})
        return {"ok": True, "note": "process already exited"}
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, timeout=10)
        else:
            os.kill(pid, 15)
        _six_star_state.update({"pid": None})
        return {"ok": True, "stopped_pid": pid}
    except Exception as ex:
        return ({"error": str(ex)}, 500)


def build_mod_info():
    """Aggregate live mod state for the Mod & offsets dashboard tab.
    Pulls /status, /hook-diag, plugin DLL hash + game version."""
    out: dict = {"mod_url": MOD_URL}
    try:
        with urllib.request.urlopen(f"{MOD_URL}/status", timeout=5) as r:
            out["status"] = json.loads(r.read())
    except Exception as e:
        out["status_error"] = str(e)
    try:
        with urllib.request.urlopen(f"{MOD_URL}/hook-diag", timeout=5) as r:
            out["hook_diag"] = json.loads(r.read())
    except Exception as e:
        out["hook_diag_error"] = str(e)
    plugin = (Path(os.environ.get("LOCALAPPDATA", "")) / "PlariumPlay" / "StandAloneApps"
              / "raid" / "build" / "BepInEx" / "plugins" / "RaidAutomationPlugin.dll")
    if plugin.exists():
        try:
            stat = plugin.stat()
            import hashlib
            with open(plugin, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()[:16]
            out["plugin_dll"] = {
                "path": str(plugin),
                "size": stat.st_size,
                "modified": int(stat.st_mtime),
                "sha256_short": h,
            }
        except Exception as e:
            out["plugin_dll_error"] = str(e)
    return out


def build_events_from_mod():
    """Pull live events from the mod's /events endpoint, extract the
    minimal fields the dashboard's PageEvents needs (name, dates,
    progress hint). Returns {events: [{...}, ...]}."""
    try:
        with urllib.request.urlopen(f"{MOD_URL}/events", timeout=10) as r:
            raw = json.loads(r.read())
    except Exception as e:
        return {"events": [], "error": str(e)}
    events = ((raw or {}).get("data") or {}).get("e") or []
    now_ms = int(time.time() * 1000)
    out = []
    for ev in events:
        d = ev.get("d") or {}
        s = d.get("s")  # start ms
        end = d.get("e")  # end ms
        if not end:
            continue
        # Skip already-finished events older than 1d
        if end < now_ms - 86_400_000:
            continue
        q = ((ev.get("q") or {}).get("q") or {})
        n = (q.get("n") or {}).get("d") or f"Event #{ev.get('i','?')}"
        ge = q.get("ge") or {}
        goal = ge.get("g") or 0
        # Format ends_in
        diff_ms = end - now_ms
        if diff_ms < 0:
            ends_in = "ended"
        else:
            mins = diff_ms // 60000
            if mins < 60:    ends_in = f"{mins}m"
            elif mins < 1440: ends_in = f"{mins//60}h{(mins%60):02d}m"
            else:           ends_in = f"{mins//1440}d{(mins%1440)//60}h"
        upcoming = (s or 0) > now_ms
        # Type heuristic
        kind = "tournament" if "Tournament" in n else "event"
        # progress: we don't have user-progress in this dump, default to 0
        out.append({
            "name": n[:80],
            "type": kind,
            "ends_in": ends_in,
            "progress": 0.0,
            "reward": f"goal {goal}" if goal else "—",
            "upcoming": upcoming,
            "starts_at": s,
            "ends_at": end,
        })
    out.sort(key=lambda e: (e["upcoming"], e["ends_at"]))
    return {"events": out}


def build_mod_log(query: dict | None = None):
    """Tail BepInEx LogOutput.log + recent activity into a unified
    real-time feed. Returns {entries: [{t, level, tag, text}, ...]} where
    `t` is unix-seconds and entries are newest-first.

    Sources merged:
      * BepInEx LogOutput.log (last N lines)
      * /api/six-star/status log_tail (if running)
    Truncates to `n` most-recent entries (default 60)."""
    n = int(_q(query, "n", 60) or 60)
    out = []
    # 1) BepInEx mod log
    bep = Path(os.environ.get("LOCALAPPDATA", "")) / "PlariumPlay" / "StandAloneApps" \
          / "raid" / "build" / "BepInEx" / "LogOutput.log"
    if bep.exists():
        try:
            with open(bep, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 16384))
                blob = f.read().decode("utf-8", errors="replace")
            lines = blob.splitlines()[-n:]
            mtime = bep.stat().st_mtime
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                # Format: [Info   :TagName] message body
                level, tag, text = "info", "mod", line
                if line.startswith("["):
                    end = line.find("]")
                    if end > 0:
                        head = line[1:end]
                        text = line[end+1:].strip()
                        if ":" in head:
                            lvl_part, tag_part = head.split(":", 1)
                            level = lvl_part.strip().lower()
                            tag = tag_part.strip()
                # Synthesize timestamps spread over the recent past so the
                # UI can sort them — file doesn't include per-line timestamps.
                t = (mtime - (len(lines) - i - 1) * 1.0) * 1000  # ms
                out.append({
                    "t": int(t),
                    "level": level if level in ("info","warn","warning","error","debug") else "info",
                    "tag": tag.lower()[:12] if tag else "mod",
                    "text": text[:400],
                })
        except Exception as e:
            out.append({"t": int(time.time()*1000), "level":"warn", "tag":"sys",
                       "text": f"mod-log read failed: {e}"})
    # 2) Six-star training tail
    sx_log = _six_star_state.get("log_file")
    if sx_log and Path(sx_log).exists():
        try:
            with open(sx_log, encoding="utf-8", errors="replace") as f:
                tail = f.readlines()[-20:]
            mtime = Path(sx_log).stat().st_mtime
            for i, line in enumerate(tail):
                if not line.strip():
                    continue
                t = (mtime - (len(tail) - i - 1) * 0.5) * 1000
                out.append({
                    "t": int(t), "level":"info", "tag":"6star",
                    "text": line.rstrip()[:400],
                })
        except Exception:
            pass
    out.sort(key=lambda e: -e["t"])
    return {"entries": out[:n]}


def list_rank_up_targets():
    """Return heroes that could be rank-up targets (grade < 6, not reserved/locked).
    Used by the dashboard's target picker."""
    heroes = _fetch_all_heroes() or []
    reserved = _cm_load_reserved()
    out = []
    for h in heroes:
        if h.get("locked") or h.get("in_storage"):
            continue
        if h.get("id") in reserved:
            continue
        if (h.get("grade") or 0) >= 6:
            continue
        out.append({
            "id": h.get("id"), "name": h.get("name"),
            "type_id": h.get("type_id"),
            "rarity": h.get("rarity"), "grade": h.get("grade"),
            "level": h.get("level"),
            "level_ready": (h.get("level") or 0) >= (h.get("grade") or 0) * 10,
        })
    out.sort(key=lambda h: (-(h.get("rarity") or 0),
                             -(h.get("grade") or 0),
                             -(h.get("level") or 0),
                             h.get("name") or ""))
    return {"heroes": out}


def execute_champ_manager(body: dict):
    """Run the planned skill-ups + rank-ups against the live mod.
    Body: {"phase": "skill"|"rank"|"both", "max_skill_ups": N, "max_rank_ups": N}.
    Returns per-call results so the UI can show what succeeded/failed."""
    phase = (body or {}).get("phase", "both")
    if phase not in ("skill", "rank", "both"):
        return ({"error": "phase must be skill | rank | both"}, 400)
    max_skill = int((body or {}).get("max_skill_ups") or 0)
    max_rank = int((body or {}).get("max_rank_ups") or 0)

    heroes = _fetch_all_heroes() or []
    reserved = _cm_load_reserved()
    protected = _cm_load_protected()
    skills_db = _cm_load_skills_db()

    client = mod_client()
    if not client.available:
        return ({"error": "mod offline"}, 503)

    skill_plans, skill_consumed = _cm_plan_skill_ups(
        heroes, reserved, protected, skills_db)
    rank_plans, _bot = _cm_plan_rank_ups(
        heroes, reserved, protected, pre_consumed=skill_consumed)

    skill_results = []
    if phase in ("skill", "both"):
        n_to_run = max_skill if max_skill > 0 else len(skill_plans)
        for p in skill_plans[:n_to_run]:
            pri = p["primary"]
            food_csv = ",".join(str(f["id"]) for f in p["feeds"])
            try:
                r = client._get(f"/skill-up?hero_id={pri['id']}&food={food_csv}") or {}
            except Exception as ex:
                skill_results.append({"primary": _hero_summary(pri), "ok": False,
                                      "error": str(ex)})
                continue
            skill_results.append({"primary": _hero_summary(pri),
                                  "ok": bool(r.get("ok")),
                                  "error": r.get("error"),
                                  "fed": len(p["feeds"])})

    rank_results = []
    if phase in ("rank", "both"):
        n_to_run = max_rank if max_rank > 0 else len(rank_plans)
        for p in rank_plans[:n_to_run]:
            t = p["target"]
            food_csv = ",".join(str(f["id"]) for f in p["food"])
            try:
                r = client._get(f"/rank-up?hero_id={t['id']}&food={food_csv}") or {}
            except Exception as ex:
                rank_results.append({"target": _hero_summary(t), "ok": False,
                                     "error": str(ex)})
                continue
            rank_results.append({"target": _hero_summary(t),
                                 "ok": bool(r.get("ok")),
                                 "error": r.get("error"),
                                 "consumed": len(p["food"])})

    # Bust the all-heroes cache so the next /api/champ-manager hit reflects
    # the post-execution state.
    _all_heroes_cache["data"] = None
    _all_heroes_cache["ts"] = 0

    return {
        "phase": phase,
        "skill_results": skill_results,
        "rank_results": rank_results,
        "skill_succeeded": sum(1 for x in skill_results if x.get("ok")),
        "rank_succeeded": sum(1 for x in rank_results if x.get("ok")),
    }


def build_state():
    cb = build_cb_last_run()
    cb_damage = ((cb or {}).get("last_run") or {}).get("damage", 0)
    # Today's damage is the sum of all CB runs in the current CB window
    # (06:00 UTC reset boundary). The boss respawns at reset so damage from a
    # previous window shouldn't roll forward.
    today_dmg = 0
    per_key = build_cb_per_key_history(days=7)
    if per_key:
        today_iso = _cb_day_today().isoformat()
        for row in per_key:
            if row.get("date") == today_iso:
                today_dmg = int(row.get("total") or 0)
                break
    # Build 7-day CB history from the dashboard history snapshots
    cb_history = []
    if HISTORY_PATH.exists():
        try:
            for line in HISTORY_PATH.read_text().splitlines()[-7:]:
                try:
                    e = json.loads(line)
                    cb_history.append({"day": e.get("day"),
                                        "dmg": int((e.get("cb_dmg_m") or 0) * 1e6)})
                except Exception:
                    pass
        except Exception:
            pass
    if cb is not None:
        cb["damage_today"] = today_dmg
        cb["history"] = cb_history
        cb["per_key_history"] = per_key
        # DWJ-sourced potential teams (ranks owned roster vs 103 DWJ tunes).
        try:
            pt = build_potential_teams(max_count=8)
            if "potential_teams" in pt:
                cb["potential_teams"] = pt["potential_teams"]
        except Exception:
            pass
        # Calc-parity sim of the top-runnable tune — gives the dashboard a real
        # cast timeline driven by DWJ's scheduler rather than a static fallback.
        try:
            parity = build_cb_parity_sim(max_boss_turns=20)
            if "error" not in parity:
                cb["calc_parity_sim"] = parity
        except Exception:
            pass
    return {
        "ts": int(time.time() * 1000),
        "layers": {
            "mod": probe_mod(),
            "memory": probe_memory(),
            "screen": probe_screen(),
        },
        "account": build_account(),
        "vm": build_vm(),
        "resources": build_resources(),
        "arena_opponents": build_arena_opponents(),
        "heroes": build_heroes(),
        "artifacts": build_artifacts(),
        "events": build_events(),
        "history": build_history(cb_damage),
        "cb": cb,
    }


## ---------- Live task runner (generic state machine in tools/task_runner) ----------
# The dashboard adds a "connect" task that probes the memory reader + mod;
# everything else (cb, etc.) lives in the shared registry.

from tools import task_runner as _tr  # noqa: E402


def _task_connect(tid):
    reader = memory_reader()
    if reader is None:
        _tr.rlog(tid, "memory reader not attached")
        return False
    _tr.rlog(tid, "attached to Raid.exe via pymem")
    client = mod_client()
    if client.available:
        try:
            status = client.get_status() or {}
            _tr.rlog(tid, f"mod online — scene={status.get('scene')} logged_in={status.get('logged_in')}")
        except Exception as e:
            _tr.rlog(tid, f"mod probe err: {e}")
    else:
        _tr.rlog(tid, "mod API offline (memory-only mode)")
    return True


# Dashboard task registry = shared CLI registry + dashboard-only "connect"
# probe. Any new tools/<x>_daily.py task should be added to
# tools/task_runner.DEFAULT_REGISTRY so both sides stay in sync.
TASK_IMPL = dict(_tr.DEFAULT_REGISTRY)
TASK_IMPL["connect"] = _task_connect


def start_run(task_ids):
    return _tr.start_run([str(x) for x in task_ids], TASK_IMPL)


def stop_run():
    return _tr.stop_run()


# Back-compat shims — older code paths import these from dashboard_server.
def _rlog(tid, msg):
    _tr.rlog(tid, msg)


def run_state():
    """Snapshot of the current task chain state. The HTTP /api/run handler
    serializes this dict as JSON."""
    return _tr.state()


# ---------- Dungeon loop runner (mod-API only) ----------
# Stateful threading + state machine moved into tools/dungeon_run.py
# (LoopController). Dashboard wires the same controller other consumers
# (CLI / future cron) can drive.
from tools.dungeon_run import default_controller as _dungeon_controller, DUNGEONS as DUNGEON_VALID  # noqa: E402, F401


def start_dungeon_run(dungeon, stage, stop_condition):
    return _dungeon_controller().start(dungeon, stage, stop_condition)


def stop_dungeon_run():
    return _dungeon_controller().stop()


def dungeon_run_state():
    return _dungeon_controller().snapshot()


# ---------- Windows Task Scheduler CRUD ----------
# Extracted to tools/windows_tasks.py for separation of concerns.
from tools.windows_tasks import (  # noqa: E402
    TASK_FOLDER, TASK_NAME_RE, TIME_RE,
    list_scheduled_tasks, create_scheduled_task,
    delete_scheduled_task, set_scheduled_task_enabled,
)


# ---------- HTTP handler ----------

# =============================================================================
# Route tables
# =============================================================================
# Each handler returns either a dict (200 OK) or a (dict, status) tuple.
# Splitting GET / POST / DELETE keeps the handler signatures small —
# GET handlers only see the parsed query, POST only see the JSON body.
# Adding a new endpoint = adding one entry to the appropriate dict.
# Pattern routes (path-with-id like /api/schedule/<name>/toggle) live in
# the *_PATTERNS lists with their compiled regex.
# =============================================================================

def _q(query: dict, key: str, default=None):
    """parse_qs returns lists; this fetches the first value (or default)."""
    return (query.get(key) or [default])[0]


def _gear_gaps(query: dict):
    try:
        return build_gear_gaps(
            float(_q(query, "threshold", 4.0)),
            int(_q(query, "min_rarity", 4)),
            int(_q(query, "min_rank", 4)),
            int(_q(query, "top", 15)),
            query.get("area"),  # list or None
        )
    except Exception as e:
        return ({"error": str(e)}, 400)


def _sim_sweep(query: dict):
    try:
        return build_sim_sweep(
            _q(query, "hero", ""),
            int(_q(query, "lo", 0)),
            int(_q(query, "hi", 0)),
        )
    except Exception as e:
        return ({"error": str(e)}, 400)


def _sell_rules_summary(query: dict):
    cfg = _load_sell()
    preview = _eval_sell(_all_artifacts_for_rules(), cfg)
    return {
        "config": cfg,
        "summary": {
            "sell_count": preview["sell_count"],
            "keep_count": preview["keep_count"],
            "by_rule": preview["by_rule"],
        },
    }


# GET handlers: query-only inputs.
GET_ROUTES = {
    "/api/state":                  lambda q: build_state(),
    "/api/schedule":               lambda q: {"tasks": list_scheduled_tasks()},
    "/api/run":                    lambda q: run_state(),
    "/api/sim-last-run":           lambda q: build_sim_last_run(),
    "/api/tune-library":           lambda q: build_tune_library(),
    "/api/sim-affinity-matrix":    lambda q: build_sim_affinity_matrix(),
    "/api/tune-compliance":        lambda q: build_tune_compliance(_q(q, "tune", "myth_eater")),
    "/api/tune-recommend":         lambda q: build_tune_recommend(),
    "/api/potential-teams":        lambda q: build_potential_teams(max_count=int(_q(q, "n", 12))),
    "/api/calc-parity-sim":        lambda q: build_cb_parity_sim(
        hash_=_q(q, "hash"), max_boss_turns=int(_q(q, "turns", 25))),
    "/api/preset":                 lambda q: build_preset_view(int(_q(q, "id", 1))),
    "/api/cb-history":             lambda q: build_cb_history_with_attribution(),
    "/api/autorun/status":         lambda q: {
        "enabled": _autorun_state.get("enabled", False),
        "last_fired": _autorun_state.get("last_fired"),
        "last_result": _autorun_state.get("last_result"),
    },
    "/api/cb-reset-info":          lambda q: build_cb_reset_info(),
    "/api/dungeons/state":         lambda q: dungeon_run_state(),
    "/api/sim-calibration":        lambda q: build_sim_calibration(),
    "/api/sim-per-tune-accuracy":  lambda q: build_sim_per_tune_accuracy(),
    "/api/tune-lab":               lambda q: build_tune_lab(
        slug=_q(q, "slug"),
        runnable_only=_q(q, "runnable_only", "0") == "1",
        affinity=_q(q, "affinity"),
        # projection=0 → current-progression mode (skip Phase 6 mastery/
        # blessing projection). Defaults to projection=True.
        projection=_q(q, "projection", "1") != "0",
    ),
    "/api/gear-gaps":              _gear_gaps,
    "/api/sim-sweep":              _sim_sweep,
    "/api/sell-rules":             lambda q: _sell_rules_summary(q),
    "/api/sell-rules/preview":     lambda q: _eval_sell(_all_artifacts_for_rules(), _load_sell()),
    "/api/champ-manager":          lambda q: build_champ_manager(),
    "/api/rank-up-targets":        lambda q: list_rank_up_targets(),
    "/api/six-star/plan":          lambda q: six_star_plan(q),
    "/api/six-star/status":        lambda q: six_star_status(),
    "/api/super-raid":             lambda q: _super_raid_proxy(_q(q, "action", "status")),
    "/api/mod-log":                lambda q: build_mod_log(q),
    "/api/events":                 lambda q: build_events_from_mod(),
    "/api/mod-info":               lambda q: build_mod_info(),
}

# A couple GET handlers want the raw `parsed.query` string instead of the
# parse_qs dict (legacy contract; both internal helpers split the string
# themselves). Kept separate from GET_ROUTES so the lambda shape stays clean.
GET_ROUTES_RAW_QUERY = {
    "/api/tune-gear-plan":          build_tune_gear_plan,
    "/api/tune-slot-alternatives":  build_tune_slot_alternatives,
}


# POST handlers: take the parsed JSON body.
def _post_schedule(body: dict):
    ok, msg = create_scheduled_task(body.get("name", ""), body.get("time", ""),
                                    body.get("command", ""))
    return ({"ok": ok, "message": msg}, 200 if ok else 400)


def _post_run(body: dict):
    ids = body.get("task_ids") or []
    if not isinstance(ids, list):
        return ({"error": "task_ids must be a list"}, 400)
    ok, msg = start_run(ids)
    return ({"ok": ok, "message": msg}, 200 if ok else 409)


def _post_apply_tune(body: dict):
    return apply_tune_to_preset(body.get("tune") or "", int(body.get("preset_id") or 1))


def _post_autorun_enable(body: dict):
    enabled = bool(body.get("enabled", True))
    if enabled:
        _autorun.enable()
        _autorun.ensure_thread(MOD_URL, ROOT)
    else:
        _autorun.disable()
    return {"ok": True, "enabled": enabled}


def _post_dungeons_start(body: dict):
    ok, msg = start_dungeon_run(
        body.get("dungeon"), body.get("stage"),
        body.get("stop_condition") or {},
    )
    return ({"ok": ok, "message": msg}, 200 if ok else 400)


def _post_sell_rules(body: dict):
    """Replace the entire sell-rules config. Caller must send the full schema."""
    cfg = body if isinstance(body, dict) else {}
    try:
        merged = {**_SELL_DEFAULT, **cfg}
        merged["rules"] = list(cfg.get("rules") or _SELL_DEFAULT["rules"])
        _save_sell(merged)
        return {"ok": True, "config": _load_sell()}
    except Exception as e:
        return ({"error": str(e)}, 400)


def _post_bulk_sell(body: dict):
    ids = body.get("ids") if isinstance(body, dict) else None
    if not isinstance(ids, list) or not ids:
        return ({"error": "ids: list of artifact IDs required"}, 400)
    try:
        ids_int = [int(x) for x in ids]
    except Exception:
        return ({"error": "ids must be integers"}, 400)
    return _run_bulk_sell(ids_int)


def _post_preset_edit(body: dict):
    """Raw priority+opener push for a single preset. Accepts:
    {"preset_id":1, "heroes":[{"hero_id":X, "opener":<sid|null>,
                                "priorities":{sid: rank, ...}}, ...]}"""
    return edit_preset_raw(int(body.get("preset_id") or 1), body.get("heroes") or [])


POST_ROUTES = {
    "/api/schedule":              _post_schedule,
    "/api/run":                   _post_run,
    "/api/apply-tune":            _post_apply_tune,
    "/api/autorun/enable":        _post_autorun_enable,
    "/api/dungeons/start":        _post_dungeons_start,
    "/api/sell-rules":            _post_sell_rules,
    "/api/sell-rules/bulk-sell":  _post_bulk_sell,
    "/api/preset/edit":           _post_preset_edit,
    "/api/champ-manager/execute": execute_champ_manager,
    "/api/rank-up-chain":         build_rank_up_chain,
    "/api/six-star/start":        six_star_start,
    "/api/six-star/stop":         lambda body: six_star_stop(),
}

# POST handlers matched by regex — the captured group is appended to the body args.
POST_PATTERNS = [
    (re.compile(r"^/api/schedule/([A-Za-z0-9_\-]+)/toggle$"),
     lambda body, name: (
         (lambda ok, msg: ({"ok": ok, "message": msg}, 200 if ok else 400))(
             *set_scheduled_task_enabled(name, bool(body.get("enabled", True))))
     )),
]

# DELETE handlers: take only the path (no body).
def _delete_run(_):
    ok, msg = stop_run()
    return ({"ok": ok, "message": msg}, 200 if ok else 400)


def _delete_dungeons_run(_):
    ok, msg = stop_dungeon_run()
    return ({"ok": ok, "message": msg}, 200 if ok else 400)


DELETE_ROUTES = {
    "/api/run":           _delete_run,
    "/api/dungeons/run":  _delete_dungeons_run,
}

DELETE_PATTERNS = [
    (re.compile(r"^/api/schedule/([A-Za-z0-9_\-]+)$"),
     lambda name: (
         (lambda ok, msg: ({"ok": ok, "message": msg}, 200 if ok else 400))(
             *delete_scheduled_task(name))
     )),
]


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DASHBOARD_DIR), **kw)

    def log_message(self, fmt, *args):
        logger.info("%s - %s", self.address_string(), fmt % args)

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _unwrap(result):
        """Handler return value → (data, status). Bare dict means 200 OK."""
        if isinstance(result, tuple) and len(result) == 2:
            return result
        return (result, 200)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ---- method dispatch ------------------------------------------------

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        handler = GET_ROUTES.get(parsed.path)
        if handler is not None:
            data, status = self._unwrap(handler(urllib.parse.parse_qs(parsed.query)))
            return self._send_json(data, status)
        raw_handler = GET_ROUTES_RAW_QUERY.get(parsed.path)
        if raw_handler is not None:
            data, status = self._unwrap(raw_handler(parsed.query))
            return self._send_json(data, status)
        # Static file fallthrough (gui/dashboard/*).
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid json"}, status=400)
        handler = POST_ROUTES.get(parsed.path)
        if handler is not None:
            data, status = self._unwrap(handler(body))
            return self._send_json(data, status)
        for pattern, fn in POST_PATTERNS:
            m = pattern.match(parsed.path)
            if m:
                data, status = self._unwrap(fn(body, *m.groups()))
                return self._send_json(data, status)
        self._send_json({"error": "not found"}, status=404)

    def do_PUT(self):
        # PUT routes through POST — historically the sell-rules save came
        # in as PUT. Endpoints that want to distinguish can guard on
        # self.command in the handler.
        return self.do_POST()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        handler = DELETE_ROUTES.get(parsed.path)
        if handler is not None:
            data, status = self._unwrap(handler(parsed.path))
            return self._send_json(data, status)
        for pattern, fn in DELETE_PATTERNS:
            m = pattern.match(parsed.path)
            if m:
                data, status = self._unwrap(fn(*m.groups()))
                return self._send_json(data, status)
        self._send_json({"error": "not found"}, status=404)


class ReusableServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    logger.info("Serving %s on http://localhost:%d", DASHBOARD_DIR, PORT)
    logger.info("Mod API target: %s", MOD_URL)
    logger.info("CB reset hour: %02d:00 UTC (PYAUTORAID_CB_RESET_UTC_HOUR to override)", CB_RESET_UTC_HOUR)
    logger.info("Dashboard: http://localhost:%d/PyAutoRaid%%20Dashboard.html", PORT)
    # Start autorun worker (disabled by default; opt-in via /api/autorun/enable).
    # _autorun_state is a read-only proxy now; the worker module owns the
    # 'thread_started' flag internally via ensure_thread().
    _autorun_worker()
    # Pre-warm the SQLite-derived artifact cache so the first sell-rules
    # preview hit is instant. Done in a background thread so it doesn't
    # block the server from binding the port.
    def _prewarm():
        try:
            n = len(_all_artifacts_for_rules())
            logger.info("artifact cache pre-warmed: %d pieces", n)
        except Exception as e:
            logger.info("artifact cache pre-warm failed: %s", e)
    threading.Thread(target=_prewarm, daemon=True, name="art-prewarm").start()
    with ReusableServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("shutting down")


if __name__ == "__main__":
    main()
