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

from Modules.mod_client import ModClient  # noqa: E402

# Override to point proxy at a remote mod (e.g. PYAUTORAID_MOD_URL=http://mothership2:6790)
MOD_URL = os.environ.get("PYAUTORAID_MOD_URL", "http://localhost:6790")

# Clan Boss resets on a daily cycle. The exact UTC hour varies by clan/region
# (common values: 6, 10). Override with PYAUTORAID_CB_RESET_UTC_HOUR=N.
# Observed default for this account: 10 UTC (matches "9h 20m remaining" at
# 18:50 local on 2026-04-22 = reset at ~04:10 local ≈ 10:10 UTC).
try:
    CB_RESET_UTC_HOUR = int(os.environ.get("PYAUTORAID_CB_RESET_UTC_HOUR", "10"))
except Exception:
    CB_RESET_UTC_HOUR = 10

RARITY_NAMES = {1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary", 6: "Mythical"}

# Element enum: 1=Magic, 2=Force, 3=Spirit, 4=Void (matches HeroType.Forms[0].Element)
_ELEMENT_NAMES = {1: "Magic", 2: "Force", 3: "Spirit", 4: "Void"}

# Fallback mapping when the mod's battle log predates the element capture patch.
# Populated from observed type_ids; extend as new affinities are seen.
_CB_TID_TO_ELEMENT = {
    # Confirmed via the mod's direct `element` field (2026-04-22 21:24 log):
    # 22270 is Force (not Void as an earlier inference suggested).
    22270: 2,  # Force
    # 22280 ran on 2026-04-21 — still unconfirmed until the new mod captures it.
}


def _cb_affinity_name(boss_element, boss_tid):
    """Return an affinity label ('Magic'/'Force'/'Spirit'/'Void') or None.

    Prefers the element field baked into the battle log by the mod; falls back
    to a hand-curated tid map for old logs that predate the capture.
    """
    if boss_element in _ELEMENT_NAMES:
        return _ELEMENT_NAMES[boss_element]
    if boss_tid in _CB_TID_TO_ELEMENT:
        return _ELEMENT_NAMES.get(_CB_TID_TO_ELEMENT[boss_tid])
    return None

# Gear-inclusive stat calc constants (mirrored from tools/gear_constants +
# tools/raid_data). Kept local to avoid a hard import dependency on those
# modules from the dashboard path.
_SET_BONUSES = {
    # set_id -> (pieces_per_bonus, {stat_id: bonus_value_pct_or_flat})
    # Basic 2-piece sets
    1: (2, {1: 15}), 2: (2, {2: 15}), 3: (2, {3: 15}), 4: (2, {4: 12}),
    5: (2, {7: 12}), 6: (2, {8: 20}), 7: (2, {6: 40}), 8: (2, {5: 40}),
    22: (2, {2: 15}),  # Cruel (ATK +15%)
    29: (2, {6: 40, 4: 5}), 38: (2, {6: 40, 4: 5}),  # Perception (+40 ACC, +5 SPD)
    35: (2, {5: 40, 1: 10}),  # Resilience
    # Divine 4-piece sets (Divine Speed = +30% SPD + bonus)
    24: (4, {4: 30, 7: 10}),   # Divine Speed (+30% SPD, +10% CR)
    25: (4, {7: 30, 2: 15}),   # Divine CritRate
    27: (4, {1: 30}),           # Divine Life (+30% HP)
    61: (4, {2: 30}),           # Divine Offense (+30% ATK)
    # Other SPD-adjacent sets
    28: (4, {}),                # Swift Parry — 25% counter on hit (no stat bonus)
    33: (4, {4: 15, 8: 15}),    # Reflex / Speed variant (+15% SPD, +15% CD)
}
_STAT_KEY = {1: "HP", 2: "ATK", 3: "DEF", 4: "SPD", 5: "RES", 6: "ACC", 7: "CR", 8: "CD"}
_LORE_OF_STEEL = 500343
# Empowerment stat bonuses per level: (hp_atk_def_pct, acc, res, spd, cd_pct, cr_pct)
_EMP_BONUSES = {
    "epic":      [(0,0,0,0,0,0), (10,10,10,0,0,0), (20,20,20,5,5,0),   (30,30,30,5,5,0),   (40,40,40,10,15,5)],
    "legendary": [(0,0,0,0,0,0), (10,15,15,0,0,0), (20,25,25,10,0,0),  (30,45,45,10,0,0),  (40,55,55,15,30,10)],
}


def compute_hero_actual_stats(hero):
    """Return gear-inclusive actual stats (SPD/HP/ATK/DEF/ACC/RES/CR/CD).

    Source: hero dict from /all-heroes (must have base_stats + artifacts +
    masteries + rarity + empower). Mirrors the game's Total Stats display
    (base + artifacts + sets + Lore of Steel + empowerment). Arena/blessing/
    Faction Guardians/relic bonuses are NOT included — those come from the
    mod's /hero-computed-stats endpoint if needed.
    """
    base = hero.get("base_stats") or {}
    flat = {k: float(base.get(k, 0) or 0) for k in ["HP", "ATK", "DEF", "SPD", "RES", "ACC", "CR", "CD"]}
    art_flat = dict.fromkeys(flat, 0.0)
    art_pct = dict.fromkeys(flat, 0.0)
    sets = {}
    for a in (hero.get("artifacts") or []):
        fb = a.get("flat_bonus") or {}
        pb = a.get("pct_bonus") or {}
        for k in flat:
            art_flat[k] += float(fb.get(k, 0) or 0)
            art_pct[k] += float(pb.get(k, 0) or 0)
        s = a.get("set", 0)
        if s:
            sets[s] = sets.get(s, 0) + 1
    has_los = _LORE_OF_STEEL in (hero.get("masteries") or [])
    # Base set bonus (no LoS), with the LoS amplifier tracked separately so we
    # can attribute it to the "Masteries" column like the in-game stat sheet.
    set_pct = dict.fromkeys(flat, 0.0)      # pct portion from sets, no LoS
    set_flat = dict.fromkeys(flat, 0.0)
    mastery_pct = dict.fromkeys(flat, 0.0)  # LoS delta (15% of base set pct)
    for set_id, count in sets.items():
        spec = _SET_BONUSES.get(set_id)
        if not spec:
            continue
        pieces_per, stats = spec
        apps = count // pieces_per
        for stat_id, val in stats.items():
            k = _STAT_KEY.get(stat_id)
            if not k:
                continue
            if k in ("ACC", "RES"):
                set_flat[k] += val * apps
            else:
                base_pct = (val / 100.0) * apps
                set_pct[k] += base_pct
                if has_los:
                    mastery_pct[k] += base_pct * 0.15
    emp_lvl = int(hero.get("empower", 0) or 0)
    rarity = hero.get("rarity", 4)
    emp_cat = "legendary" if rarity == 5 else "epic"
    emp_tbl = _EMP_BONUSES.get(emp_cat, _EMP_BONUSES["epic"])
    emp_flat = dict.fromkeys(flat, 0.0)
    emp_pct = dict.fromkeys(flat, 0.0)
    if 0 <= emp_lvl < len(emp_tbl):
        hp_atk_def, acc, res, spd, cd, cr = emp_tbl[emp_lvl]
        emp_flat.update({"SPD": spd, "ACC": acc, "RES": res})
        emp_pct.update({
            "HP": hp_atk_def / 100.0, "ATK": hp_atk_def / 100.0, "DEF": hp_atk_def / 100.0,
            "CD": cd / 100.0, "CR": cr / 100.0,
        })
    # Sum components the way the in-game "Total Stats" screen does: each
    # contribution is floored/rounded independently, then summed. Matches the
    # game's Basic + Artifacts + Masteries + Empowerment columns.
    out = {}
    breakdown = {}
    import math as _math
    for k in flat:
        base_val = flat[k]
        art_val = art_flat[k] + flat[k] * art_pct[k] + flat[k] * set_pct[k]  # flat + %substats + base set
        mast_val = flat[k] * mastery_pct[k]  # LoS delta only, attributed to masteries
        emp_val = emp_flat[k] + flat[k] * emp_pct[k]
        set_flat_val = set_flat[k]  # ACC/RES flat-set bonuses
        if k in ("HP", "ATK", "DEF", "SPD", "ACC", "RES"):
            # Game floors the per-column integer display
            components = [
                int(base_val),
                int(art_val + set_flat_val),   # artifacts column aggregates set-flats too
                round(mast_val),                # masteries column uses rounding (0.5 -> 1)
                int(emp_val),
            ]
            out[k] = sum(components)
            breakdown[k] = {"basic": components[0], "artifacts": components[1],
                            "masteries": components[2], "empower": components[3]}
        else:
            out[k] = round(base_val + art_val + mast_val + emp_val, 1)
    out["_breakdown"] = breakdown
    return out
FACTION_NAMES = {
    0: "Unknown", 1: "Banner Lords", 2: "High Elves", 3: "Sacred Order",
    4: "Coven of Magi", 5: "Ogryn Tribes", 6: "Lizardmen", 7: "Skinwalkers",
    8: "Orcs", 9: "Demonspawn", 10: "Undead Hordes", 11: "Dark Elves",
    12: "Knights Revenant", 13: "Barbarians", 14: "Sylvan Watchers",
    15: "Samurai", 16: "Dwarves", 17: "Olympians",
}

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
                }
                import math
                for out_k, src_k in keymap.items():
                    if src_k in allres:
                        # Floor fractional regenerating keys/tokens so the UI
                        # matches the in-game whole-key counter.
                        out["keys"][out_k] = int(math.floor(float(allres[src_k])))
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


_HERO_ROLE_NAMES = {0: "Unknown", 1: "Attack", 2: "Defense", 3: "HP", 4: "Support"}
_HERO_ELEMENT_NAMES = {1: "Magic", 2: "Force", 3: "Spirit", 4: "Void"}


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


_FACTION_PRETTY = {
    "BannerLords": "Banner Lords", "HighElves": "High Elves", "SacredOrder": "Sacred Order",
    "CovenOfMagi": "Coven of Magi", "OgrynTribes": "Ogryn Tribes", "LizardMen": "Lizardmen",
    "UndeadHordes": "Undead Hordes", "DarkElves": "Dark Elves",
    "KnightsRevenant": "Knights Revenant", "SylvanWatchers": "Sylvan Watchers",
}


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
        sys.path.insert(0, str(ROOT / "tools"))
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


def _most_recent_battle_log():
    """Pick the newest battle_logs_cb_*.json by mtime. Prefers timestamped
    files; falls back to battle_logs_cb_latest.json if that's all we have."""
    import glob
    candidates = glob.glob(str(ROOT / "battle_logs_cb_*.json"))
    if not candidates:
        return None
    # Prefer timestamped files over 'latest' when ties; then newest mtime
    def key(p):
        name = Path(p).name
        return (name != "battle_logs_cb_latest.json", Path(p).stat().st_mtime)
    candidates.sort(key=key)
    return Path(candidates[-1])


def _load_battle_log():
    path = _most_recent_battle_log()
    if path is None or not path.exists():
        return None
    mtime = path.stat().st_mtime
    cache_key = (str(path), mtime)
    if _battle_log_cache.get("key") == cache_key and _battle_log_cache["data"]:
        return _battle_log_cache["data"]
    try:
        data = json.loads(path.read_text())
        _battle_log_cache["key"] = cache_key
        _battle_log_cache["mtime"] = mtime
        _battle_log_cache["path"] = path
        _battle_log_cache["data"] = data
        return data
    except Exception as e:
        logger.info("battle log parse failed (%s): %s", path.name, e)
        return None


def _hero_type_to_name():
    """Best-effort hero type_id -> name map. Prefers skills_db.json, falls back
    to skill_descriptions.json (different shape)."""
    out = {22270: "CB Boss"}
    skills_path = ROOT / "skills_db.json"
    if skills_path.exists():
        try:
            db = json.loads(skills_path.read_text())
            for name, skills in db.items():
                if not skills:
                    continue
                first = skills[0].get("skill_type_id", 0)
                if first:
                    out[first // 10] = name
            return out
        except Exception:
            pass
    desc_path = ROOT / "skill_descriptions.json"
    if desc_path.exists():
        try:
            db = json.loads(desc_path.read_text())
            for name, skills in db.items():
                if not isinstance(skills, dict):
                    continue
                for sk in skills.values():
                    if isinstance(sk, dict) and sk.get("skill_type_id"):
                        out[sk["skill_type_id"] // 10] = name
                        break
        except Exception:
            pass
    return out


_STATUS_ID_TO_NAME = {}
try:
    sys.path.insert(0, str(ROOT / "tools"))
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


def _cb_day_for_timestamp(ts):
    """Which CB window does a unix timestamp belong to? CB resets at
    CB_RESET_UTC_HOUR daily; anything before that UTC hour counts toward the
    prior day's CB instance (same boss, continuing damage)."""
    dt_utc = datetime.datetime.utcfromtimestamp(ts)
    return (dt_utc - datetime.timedelta(hours=CB_RESET_UTC_HOUR)).date()


def _cb_day_today():
    return _cb_day_for_timestamp(time.time())


def build_cb_per_key_history(days=7):
    """Aggregate per-run CB damage from saved battle_logs_cb_*.json files,
    grouped by CB window. Each key entry includes damage, team composition,
    turn count, and file timestamp for rich hover tooltips."""
    import glob
    from collections import defaultdict
    name_map = _hero_type_to_name()
    by_day = defaultdict(list)  # iso_date -> list of key dicts
    for path in glob.glob(str(ROOT / "battle_logs_cb_*.json")):
        name = Path(path).name
        if name == "battle_logs_cb_latest.json":
            continue
        try:
            mt = Path(path).stat().st_mtime
            cb_date = _cb_day_for_timestamp(mt)
        except Exception:
            continue
        try:
            data = json.loads(Path(path).read_text())
            entries = data.get("log", []) if isinstance(data, dict) else []
            max_dmg = 0
            turns = 0
            team_types = []
            boss_tid = None
            boss_element = None
            for e in entries:
                if not isinstance(e, dict):
                    continue
                for h in (e.get("heroes") or []):
                    if h.get("side") == "enemy":
                        max_dmg = max(max_dmg, int(h.get("dmg_taken", 0) or 0))
                        turns = max(turns, int(h.get("turn_n", 0) or 0))
                        # Prefer first non-zero element / type_id seen on boss
                        if not boss_tid:
                            boss_tid = h.get("type_id")
                        if not boss_element:
                            boss_element = h.get("element")
                    elif h.get("side") == "player" and not team_types:
                        # capture team on first poll
                        pass
                if not team_types and e.get("heroes"):
                    team_types = [h.get("type_id") for h in e["heroes"] if h.get("side") == "player"]
            if max_dmg <= 0:
                continue
            team_names = [name_map.get(tid, f"#{tid}") for tid in team_types if tid]
            local_dt = datetime.datetime.fromtimestamp(mt)
            affinity = _cb_affinity_name(boss_element, boss_tid)
            by_day[cb_date.isoformat()].append({
                "damage": max_dmg,
                "turns": turns,
                "team": team_names,
                "boss_tid": boss_tid,
                "boss_element": boss_element,
                "affinity": affinity,
                "time": local_dt.strftime("%H:%M"),
                "iso_time": local_dt.isoformat(timespec="minutes"),
                "file": name,
            })
        except Exception:
            continue
    today = _cb_day_today()
    out = []
    for i in range(days - 1, -1, -1):
        d = today - datetime.timedelta(days=i)
        iso = d.isoformat()
        # Sort each day's keys by damage descending (display order)
        keys = sorted(by_day.get(iso, []), key=lambda k: -k["damage"])
        out.append({
            "date": iso,
            "day": iso[5:],
            "keys": keys,
            "total": sum(k["damage"] for k in keys),
        })
    return out


def build_cb_last_run():
    """Parse latest CB battle log into team breakdown + timeline."""
    data = _load_battle_log()
    if not data:
        return None
    log = data.get("log", []) if isinstance(data, dict) else data
    name_map = _hero_type_to_name()

    # Pre-index mod's /all-heroes by NAME — the battle log's type_id is an
    # internal slot id that doesn't match /all-heroes's TypeId. Names are the
    # reliable bridge (both sources agree on "Maneater", "Ninja", etc.).
    heroes_by_name = {}
    for h in (_fetch_all_heroes() or []):
        n = h.get("name")
        if n and n not in heroes_by_name:
            heroes_by_name[n] = h

    team = {}            # slot -> {type_id, dmg_taken, absorbed, turns, buffs_seen, status_seen, counter_procs, uk_saves}
    boss_prev_dmg = 0
    boss_max_hp = 0
    boss_tid = None
    boss_element = None
    dealt_attrib = {}    # slot -> cumulative dmg dealt
    active_hero_id = None
    last_active_hero = None  # remembers who just took their turn
    # DoT tick attribution: at each new boss turn, debuff damage ticks BEFORE
    # any hero takes an action. We detect that window and split the HP delta
    # among sources of Poison / HP Burn debuffs currently on the boss.
    DOT_DEBUFF_TYPES = {80, 81, 470, 310}  # Poison 5%, Poison 2.5%, HP Burn, legacy HPB
    turn_has_hero_action = False
    current_boss_debuffs = []   # list of {t, src} — refreshed each boss snapshot
    # Debuffs applied to the boss via the clean `debuffs[]` field. Each entry
    # is {t: StatusEffectTypeId, d: duration_remaining, src: slot_id}.
    # We dedupe by (turn, type_id, src) so a 2-turn debuff isn't counted twice.
    debuff_placement_sigs = set()
    debuff_counts_by_type = {}  # type_id -> total placements
    debuff_by_src = {}          # (type_id, src_slot_id) -> placements (attribution)
    boss_status_seen = set()
    boss_uk_saves = 0
    timeline = []        # [{t: turn, ev: text, by: hero_name}]

    # Per-turn log buckets (key = boss turn_n)
    turn_log = {}        # turn -> {boss_turn, hero_moves, debuffs_applied, buffs_gained, boss_damage}
    boss_prev_hp = None
    prev_buffs_by_slot = {}  # slot -> set((type_id, duration)) of buffs last seen
    prev_boss_mods = set()   # set of (mod.id)
    prev_boss_turn = 0
    prev_boss_uk_saved = False

    total_damage = 0
    turns_total = 0

    def hero_for(hid):
        slot = team.get(hid)
        if not slot:
            return f"#{hid}"
        return name_map.get(slot["type_id"], f"#{slot['type_id']}")

    # Stat kind names for mod decoding (matches ARTIFACT_STATS order)
    stat_label = {1:"HP", 2:"ATK", 3:"DEF", 4:"SPD", 5:"RES", 6:"ACC", 7:"CR", 8:"CD"}

    def _ensure_turn(t):
        if t not in turn_log:
            turn_log[t] = {
                "boss_turn": t,
                "events": [],
                "damage": 0,
                "boss_hp_start": None,
                "boss_hp_end": None,
                # CB boss skill cycle: AOE1 -> AOE2 -> STUN repeating every 3
                # turns (per DWJ tune simulator convention). Turn 0 = AOE1
                # opener.
                "boss_action": ["AOE1", "AOE2", "STUN"][t % 3],
                # Per-hero protection at the moment of boss action (captured
                # from the poll snapshot just BEFORE the HP drop that starts
                # this boss turn's damage event).
                "protection": {},   # slot_id -> {"uk": bool, "bd": bool, "sh": bool}
            }
        return turn_log[t]

    for entry in log:
        if not isinstance(entry, dict):
            continue
        if "active_hero" in entry:
            hid = entry.get("active_hero")
            active_hero_id = hid
            # Record hero turn in the current boss turn's log (if side=player)
            if hid is not None and hid in team and team[hid].get("type_id"):
                t = prev_boss_turn or 0
                if t:
                    tlog = _ensure_turn(t)
                    tlog["events"].append({
                        "k": "hero_turn",
                        "by": name_map.get(team[hid]["type_id"], f"#{hid}"),
                    })
                turn_has_hero_action = True
            last_active_hero = hid
            continue
        if "heroes" not in entry:
            continue

        for h in entry["heroes"]:
            side = h.get("side")
            hid = h.get("id")
            tid = h.get("type_id")
            if hid is None:
                continue

            if side == "enemy":
                cur_dmg = h.get("dmg_taken", 0) or 0
                hp_max = h.get("hp_max", 0) or 0
                boss_turn = h.get("turn_n", 0) or 0
                if hp_max > boss_max_hp:
                    boss_max_hp = hp_max
                if boss_tid is None:
                    boss_tid = h.get("type_id")
                if boss_element is None and h.get("element") is not None:
                    boss_element = h.get("element")

                # New boss turn boundary: capture HP start + emit prior HP end.
                # Also reset the "has any hero acted this turn?" flag so DoT
                # tick damage at the top of the next boss turn is distinguished.
                if boss_turn != prev_boss_turn:
                    if prev_boss_turn and prev_boss_turn in turn_log:
                        turn_log[prev_boss_turn]["boss_hp_end"] = h.get("hp_cur")
                    if boss_turn:
                        tl = _ensure_turn(boss_turn)
                        if tl["boss_hp_start"] is None:
                            tl["boss_hp_start"] = h.get("hp_cur")
                    prev_boss_turn = boss_turn
                    turn_has_hero_action = False

                # Capture current boss debuffs for DoT-tick attribution fallback
                current_boss_debuffs = list(h.get("debuffs") or [])

                if cur_dmg > boss_prev_dmg:
                    delta = cur_dmg - boss_prev_dmg
                    # Active-hero phase: a hero has acted this boss turn AND
                    # active_hero_id currently points to a player slot -> direct
                    # attribution. Otherwise this is DoT tick / boss-phase
                    # damage -> split among debuff sources.
                    is_hero_phase = (
                        turn_has_hero_action
                        and active_hero_id is not None
                        and active_hero_id in team
                    )
                    if is_hero_phase:
                        dealt_attrib[active_hero_id] = dealt_attrib.get(active_hero_id, 0) + delta
                        by_name = hero_for(active_hero_id)
                    else:
                        # Find active DoT sources (Poison + HP Burn). Share
                        # the delta by stack count -> each stack's `src` slot.
                        dot_sources = [db.get("src") for db in current_boss_debuffs
                                       if db.get("t") in DOT_DEBUFF_TYPES and db.get("src") is not None]
                        if dot_sources:
                            share = delta / len(dot_sources)
                            for src in dot_sources:
                                dealt_attrib[src] = dealt_attrib.get(src, 0) + share
                            # Credit the timeline to the biggest contributor
                            from collections import Counter
                            top_src = Counter(dot_sources).most_common(1)[0][0]
                            by_name = f"{hero_for(top_src)} (DoT)"
                        else:
                            # No debuff data (mid-log gap) — fall back to the
                            # last active hero rather than dropping the delta.
                            if active_hero_id is not None:
                                dealt_attrib[active_hero_id] = dealt_attrib.get(active_hero_id, 0) + delta
                            by_name = hero_for(active_hero_id) if active_hero_id is not None else "?"
                    if boss_turn and boss_turn in turn_log:
                        turn_log[boss_turn]["damage"] += delta
                    if delta >= 500_000:
                        timeline.append({"t": boss_turn, "ev": f"{delta/1e6:.2f}M damage", "by": by_name})
                    boss_prev_dmg = cur_dmg

                # Boss debuffs via the clean `debuffs[]` field. Each placement
                # is (type_id, src, duration). A given placement is the same as
                # long as duration is decreasing; when duration RESETS or the
                # pair (type, src) disappears and reappears, count as new.
                # We dedupe by "did this (turn, type, src, remaining-duration)
                # arrive this turn for the first time?" — in practice, we count
                # once per (boss_turn, type_id, src_slot) first-seen.
                cur_debuff_keys = set()
                for db in (h.get("debuffs") or []):
                    t_id = db.get("t")
                    src = db.get("src")
                    if t_id is None:
                        continue
                    key = (boss_turn, t_id, src)
                    cur_debuff_keys.add((t_id, src))
                    if key in debuff_placement_sigs:
                        continue
                    debuff_placement_sigs.add(key)
                    # Only count when the debuff JUST APPEARED this boss turn
                    # (not present the previous turn). Without prev-turn state
                    # this naturally fires on first appearance per turn which
                    # is what we want.
                    debuff_counts_by_type[t_id] = debuff_counts_by_type.get(t_id, 0) + 1
                    k_src = (t_id, src)
                    debuff_by_src[k_src] = debuff_by_src.get(k_src, 0) + 1
                    # Log a turn event for the first new debuff of each type
                    if boss_turn in turn_log:
                        name = _STATUS_ID_TO_NAME.get(t_id, f"effect {t_id}")
                        by_name = hero_for(src) if src is not None else (hero_for(active_hero_id) if active_hero_id is not None else "?")
                        turn_log[boss_turn]["events"].append({
                            "k": "debuff", "name": name, "by": by_name,
                        })

                # Boss status flags observed this poll
                for st in (h.get("st") or []):
                    boss_status_seen.add(st)

                # Boss Unkillable-like save count — only count False->True transitions
                cur_uk = h.get("uk_saved") is True
                if cur_uk and not prev_boss_uk_saved:
                    boss_uk_saves += 1
                prev_boss_uk_saved = cur_uk

                total_damage = cur_dmg
                turns_total = max(turns_total, boss_turn)
            elif side == "player":
                slot = team.setdefault(hid, {
                    "type_id": tid,
                    "dmg_taken": 0,
                    "absorbed": 0,
                    "turns": 0,
                    "buffs_seen": set(),
                    "status_seen": set(),
                    "counter_procs": 0,
                    "uk_saves": 0,
                    "hp_max": h.get("hp_max", 0) or 0,
                })
                dt = h.get("dmg_taken") or h.get("hp_lost") or 0
                slot["dmg_taken"] = max(slot["dmg_taken"], dt)
                slot["turns"] = max(slot["turns"], h.get("turn_n", 0) or 0)
                # Absorbed damage (block damage + unkillable shields). `abs` is
                # a dict { effect_id: amount }.
                abs_dict = h.get("abs") or {}
                total_abs = 0
                try:
                    total_abs = sum(int(v) for v in abs_dict.values())
                except Exception:
                    total_abs = 0
                slot["absorbed"] = max(slot["absorbed"], total_abs)

                # Status flags
                for st in (h.get("st") or []):
                    slot["status_seen"].add(st)

                # Active buffs from `buffs` list: {t: type_id, d: duration, src: slot_id}
                # Track source per buff so the UI can show "Unkillable (from Demytha)"
                if "buff_sources" not in slot:
                    slot["buff_sources"] = {}  # type_id -> set of source slot ids
                cur_buff_types = set()
                for b in (h.get("buffs") or []):
                    t_id = b.get("t")
                    src = b.get("src")
                    if t_id is None:
                        continue
                    cur_buff_types.add(t_id)
                    slot["buffs_seen"].add(t_id)
                    if src is not None:
                        slot["buff_sources"].setdefault(t_id, set()).add(src)

                # Protection snapshot for THIS boss turn's action. The last
                # snapshot we see before the turn transitions is the "state at
                # boss hit" — overwrite on every poll of this boss_turn so the
                # final overwrite is the most-recent-before-transition.
                if prev_boss_turn and prev_boss_turn in turn_log:
                    turn_log[prev_boss_turn]["protection"][hid] = {
                        "uk": 320 in cur_buff_types,
                        "bd": 60 in cur_buff_types,
                        "sh": 280 in cur_buff_types,
                    }
                # Detect buff transitions (new buff this poll vs last poll)
                prev = prev_buffs_by_slot.get(hid, set())
                added = cur_buff_types - prev
                if added and prev_boss_turn:
                    hero_name = name_map.get(slot["type_id"], f"#{hid}")
                    for t_id in added:
                        name = _STATUS_ID_TO_NAME.get(t_id)
                        if not name:
                            continue
                        _ensure_turn(prev_boss_turn)["events"].append({
                            "k": "buff", "name": name, "on": hero_name,
                        })
                prev_buffs_by_slot[hid] = cur_buff_types

                # Counter counter dict
                ctr_dict = h.get("ctr") or {}
                try:
                    ctr_total = sum(int(v) for v in ctr_dict.values())
                except Exception:
                    ctr_total = 0
                if ctr_total > slot["counter_procs"]:
                    slot["counter_procs"] = ctr_total

                # Unkillable save: hero was about to die (hp_cur stuck at 1) and uk_saved true would be on mod.
                if h.get("hp_cur") == 1 and (h.get("st") or []):
                    if "unkillable" in (h.get("st") or []) or 320 in cur_buff_types:
                        pass  # active; don't count

    if not team:
        return None

    # Enrich team rows with metadata from /all-heroes — match by hero NAME
    team_out = []
    for hid, slot in sorted(team.items()):
        tid = slot["type_id"]
        lookup_name = name_map.get(tid, f"#{tid}")
        meta = heroes_by_name.get(lookup_name) or {}
        rarity = RARITY_NAMES.get(meta.get("rarity") or 0, "")
        faction = FACTION_NAMES.get(meta.get("fraction") or 0, "")
        # Build structured buff entries with source attribution
        buff_sources = slot.get("buff_sources") or {}
        buffs_named = []
        # Map slot_id -> hero name lookup helper. If a buff's src is the hero
        # themselves, mark self-cast; otherwise show the teammate's name.
        def _slot_name(slot_id):
            if slot_id == hid: return "self"
            other = team.get(slot_id)
            if other and other.get("type_id"):
                return name_map.get(other["type_id"], f"#{slot_id}")
            return f"#{slot_id}"
        for t_id in sorted(slot.get("buffs_seen") or set()):
            if t_id not in _STATUS_ID_TO_NAME:
                continue
            srcs = buff_sources.get(t_id, set())
            buffs_named.append({
                "name": _STATUS_ID_TO_NAME[t_id],
                "sources": sorted({_slot_name(s) for s in srcs}),
            })
        # Actual gear-inclusive stats (base + artifacts + sets + LoS + empower).
        # Falls back to base_stats if meta is missing (e.g. unmatched name).
        actual = compute_hero_actual_stats(meta) if meta else {}
        team_out.append({
            "name": lookup_name,
            "preset_slot": hid + 1,  # battle log slot id 0-4 => in-team position 1-5
            "role": _HERO_ROLE_NAMES.get(meta.get("role") or 0, ""),
            "rarity": rarity,
            "faction": _FACTION_PRETTY.get(faction, faction),
            "stars": meta.get("grade") or 0,
            "element": _HERO_ELEMENT_NAMES.get(meta.get("element") or 0, ""),
            "level": meta.get("level") or 0,
            "hp": int(actual.get("HP") or (meta.get("base_stats") or {}).get("HP") or 0),
            "def": int(actual.get("DEF") or (meta.get("base_stats") or {}).get("DEF") or 0),
            "spd": int(actual.get("SPD") or (meta.get("base_stats") or {}).get("SPD") or 0),
            "spd_base": int((meta.get("base_stats") or {}).get("SPD") or 0),
            "dmg_dealt": int(dealt_attrib.get(hid, 0)),
            "dmg_taken": int(slot["dmg_taken"]),
            "absorbed": int(slot.get("absorbed", 0)),
            "counters": int(slot.get("counter_procs", 0)),
            "turns": int(slot["turns"]),
            "buffs": buffs_named,
            "status_flags": sorted(list(slot.get("status_seen") or [])),
        })

    # Aggregate boss debuffs under friendly names. Multiple ID variants can map
    # to the same label (e.g. Poison 5% and Poison 2.5% both appear as "Poison").
    debuffs_applied = {}
    label_group = {
        # Collapse variants under a single user-facing name.
        "Poison 5%":           "Poison",
        "Poison 2.5%":         "Poison",
        "Block Heal 100":      "Block Heal",
        "Block Heal 50":       "Block Heal",
        "Weaken 15":           "Weaken",
        "Dec Atk 25":          "Dec ATK",
        "Dec Atk":             "Dec ATK",
        "Dec Def 30":          "Dec DEF",
        "Def Down":            "Dec DEF",
        "Dec Spd 15":          "Dec SPD",
        "Dec Spd":             "Dec SPD",
        "Dec Cd 15":           "Dec CD",
        "Dec Cd 25":           "Dec CD",
        "Hp Burn":             "HP Burn",
        "Dec Res 25":          "Dec RES",
        "Dec Res 50":          "Dec RES",
        "Block Revive":        "Block Revive",
        "Leech":               "Leech",
        "Fear":                "Fear",
        "True Fear":           "True Fear",
        "Poison Sensitivity":  "Poison Sensitivity",
        "Poison Sensitivity 50": "Poison Sensitivity",
        "Stun":                "Stun",
        "Freeze":              "Freeze",
        "Sleep":               "Sleep",
        "Provoke":             "Provoke",
        "Dec Cr 15":           "Dec CR",
        "Dec Cr":              "Dec CR",
        "Cooldown":            "Inc Cooldown",
    }
    for t_id, n in debuff_counts_by_type.items():
        name = _STATUS_ID_TO_NAME.get(t_id, f"effect {t_id}")
        canonical = label_group.get(name, name)
        debuffs_applied[canonical] = debuffs_applied.get(canonical, 0) + n

    # Final event on timeline
    if turns_total:
        timeline.append({"t": turns_total, "ev": f"Run end - {total_damage/1e6:.2f}M", "by": "result"})
    timeline.sort(key=lambda x: x.get("t") or 0)
    seen = set(); dedup = []
    for ev in timeline:
        key = (ev.get("t"), ev.get("ev"), ev.get("by"))
        if key in seen:
            continue
        seen.add(key); dedup.append(ev)
    timeline = dedup[:20]

    # Boss metadata
    boss_info = {
        "hp_max": boss_max_hp if boss_max_hp else None,
        "type_id": boss_tid,
        "element": boss_element,
        "affinity": _cb_affinity_name(boss_element, boss_tid),
    }

    # Sort turn log by boss turn + compact each
    turn_log_out = []
    for t in sorted(turn_log.keys()):
        tl = turn_log[t]
        # Collapse consecutive duplicate hero_turn events
        compact = []
        for ev in tl["events"]:
            if compact and compact[-1] == ev:
                continue
            compact.append(ev)
        # Convert per-slot protection dict to hero-name keyed dict for UI
        prot = {}
        for slot_id, p in (tl.get("protection") or {}).items():
            s = team.get(slot_id) or {}
            nm = name_map.get(s.get("type_id"), f"#{slot_id}")
            prot[nm] = p
        turn_log_out.append({
            "boss_turn": tl["boss_turn"],
            "boss_action": tl.get("boss_action"),
            "damage": int(tl["damage"]),
            "boss_hp_start": tl.get("boss_hp_start"),
            "boss_hp_end": tl.get("boss_hp_end"),
            "protection": prot,
            "events": compact,
        })

    return {
        "team": team_out,
        "boss": boss_info,
        "last_run": {
            "duration_s": None,
            "turns_total": int(turns_total),
            "damage": int(total_damage),
            "damage_taken": int(sum(t["dmg_taken"] for t in team_out)),
            "damage_absorbed": int(sum(t.get("absorbed", 0) for t in team_out)),
            "unkillable_triggers": int(boss_uk_saves),
            "counters_total": int(sum(t.get("counters", 0) for t in team_out)),
            "debuffs_applied": debuffs_applied,
            "timeline": timeline,
            "turn_log": turn_log_out,
        },
    }


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
        sys.path.insert(0, str(ROOT / "tools"))
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


# Expected damage per key-capability tier (used to rank potential teams).
# Roughly based on community consensus / HH/DWJ baselines.
_KEY_CAPABILITY_DAMAGE = {
    "1 Key UNM": 50_000_000,
    "2 Key UNM": 30_000_000,
    "3 Key UNM": 20_000_000,
    "4 Key UNM": 12_000_000,
    "5 Key UNM": 10_000_000,
}


def _damage_floor_for_key(key_cap: str | None, affinity: str | None) -> int:
    base = _KEY_CAPABILITY_DAMAGE.get(key_cap or "", 10_000_000)
    # Force-weak Magic units take -30%; DWJ tune flagged "not_force" means teams
    # drop damage on Force days. Default affinity factor 1.0.
    if affinity and "Void" in affinity and "Only" in affinity:
        return int(base * 0.95)  # slight penalty for affinity-restricted
    return base


# Cache calc-parity sim results by variant hash so build_potential_teams
# doesn't re-run the scheduler 8 times per dashboard poll.
_parity_survival_cache: dict[str, dict] = {}


def _parity_survival(variant_hash: str | None, dwj_loader) -> dict | None:
    """Run calc_parity_sim against `variant_hash` for the full 50 boss turns
    and return {"boss_turns": int, "actions": int, "survived": bool}, or None
    if the variant or sim is unavailable. Cached.
    """
    if not variant_hash:
        return None
    if variant_hash in _parity_survival_cache:
        return _parity_survival_cache[variant_hash]
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import calc_parity_sim as cps
        variant = dwj_loader().variants_by_hash.get(variant_hash)
        if variant is None:
            _parity_survival_cache[variant_hash] = None
            return None
        turns = cps.simulate(variant, max_boss_turns=50)
        boss_tn = cps.count_boss_turns(turns)
        result = {
            "boss_turns": boss_tn,
            "actions": len(turns),
            "survived": boss_tn >= 50,
        }
        _parity_survival_cache[variant_hash] = result
        return result
    except Exception:
        _parity_survival_cache[variant_hash] = None
        return None


def build_potential_teams(max_count: int = 12):
    """Score all DWJ tunes against user's owned roster and return the top.

    Uses tools/comp_finder.py's logic (roster from heroes_all.json, tunes from
    data/dwj/parsed/tunes.json) and runs calc_parity_sim per tune to surface
    sim-backed survival as a confidence signal (100%-match against DWJ calc).
    """
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import comp_finder as cf
        from dwj_tunes import load_all as load_dwj_all
    except Exception as e:
        return {"error": f"comp_finder import failed: {e}"}

    try:
        roster = cf.load_roster()
        tunes = cf.load_tunes()
        hh = cf.load_hh_ratings()
    except Exception as e:
        return {"error": f"dwj/hh data load failed: {e}"}

    # Cache the DWJ dataset across all tunes in this call.
    _dwj_cached = {"d": None}
    def _dwj():
        if _dwj_cached["d"] is None:
            _dwj_cached["d"] = load_dwj_all()
        return _dwj_cached["d"]

    evaluated = [cf.evaluate_tune(t, roster) for t in tunes]
    ranked = cf.rank_tunes(evaluated, hh)

    out = []
    for ev in ranked:
        t = ev["tune"]
        slots = ev["slots"]
        missing = ev["missing"]
        ascending = ev["ascending"]
        # Status mapping
        if missing == 0 and ascending == 0:
            status = "active" if len(out) == 0 else "candidate"
        elif missing <= 1:
            status = "candidate"
        else:
            status = "backup"
        # Confidence: full-fill + no ascending = 1.0; penalize per gap
        conf = max(0.3, 1.0 - 0.15 * missing - 0.1 * ascending)
        heroes = [s.get("hero") or "?" for s in slots]
        est_damage = _damage_floor_for_key(t.get("key_capability"), t.get("affinity"))
        if missing:
            est_damage = int(est_damage * (0.85 ** missing))  # softer estimate w/ gaps
        # Tags
        tags = []
        if t.get("type"):
            tags.append(t["type"].lower())
        if t.get("key_capability"):
            tags.append(t["key_capability"].replace(" ", "-").lower())
        if t.get("difficulty"):
            tags.append(t["difficulty"].lower())
        # Calculator links
        calc_links = []
        for c in t.get("calculator_links") or []:
            calc_links.append({
                "name": c.get("name") or "link",
                "hash": c.get("hash"),
                "url": c.get("url"),
            })
        # Pick the UNM variant hash (preferred) or first variant for parity sim.
        unm_link = next((c for c in calc_links if "ultra" in (c.get("name") or "").lower() or "unm" in (c.get("name") or "").lower()), None)
        sim_hash = (unm_link or (calc_links[0] if calc_links else {})).get("hash")
        parity = _parity_survival(sim_hash, _dwj) if missing == 0 else None
        # Fold sim survival into confidence: a roster-fit comp that the parity
        # sim says dies before turn 50 should NOT read as high-confidence.
        if parity:
            if parity.get("survived"):
                conf = max(conf, 0.95)         # sim-validated 50T survival
            else:
                # Scale by how far it got
                bt = parity.get("boss_turns") or 0
                conf = min(conf, 0.3 + (bt / 50) * 0.5)
        note_bits = []
        if ev.get("missing_heroes"):
            note_bits.append("need " + ", ".join(ev["missing_heroes"]))
        if ev.get("ascending_heroes"):
            asc_txt = ", ".join(f"{h} ({g}★)" for h, g in ev["ascending_heroes"])
            note_bits.append("ascend " + asc_txt)
        if not note_bits and t.get("description"):
            # Use a trimmed description when there are no gaps
            note_bits.append(t["description"][:120] + ("…" if len(t["description"]) > 120 else ""))
        note = " · ".join(note_bits) or ""
        # Slot details for drill-down panels
        slot_details = []
        for s in slots:
            slot_details.append({
                "index": s.get("index"),
                "hero": s.get("hero"),
                "status": s.get("status"),
                "min_spd": s.get("min_spd"),
                "max_spd": s.get("max_spd"),
                "roster_grade": s.get("roster_grade"),
            })
        out.append({
            "id": t.get("slug"),
            "name": t.get("name") or "Unnamed",
            "status": status,
            "est_damage": est_damage,
            "confidence": round(conf, 2),
            "tags": tags,
            "heroes": heroes,
            "note": note,
            "missing": missing,
            "ascending": ascending,
            "affinity": t.get("affinity"),
            "key_capability": t.get("key_capability"),
            "type": t.get("type"),
            "difficulty": t.get("difficulty"),
            "dwj_url": t.get("url"),
            "calculator_links": calc_links,
            "slots": slot_details,
            "parity_sim": parity,            # {boss_turns, actions, survived} or None
            "sim_hash": sim_hash,            # variant hash the parity sim ran against
        })
        if len(out) >= max_count:
            break
    return {"potential_teams": out}


def build_cb_parity_sim(hash_: str | None = None, max_boss_turns: int = 25):
    """Run calc_parity_sim against a specific DWJ calc variant (by hash)
    or — if no hash is given — against the top-ranked runnable tune for
    the user's roster. Returns a cast timeline + summary suitable for the
    dashboard sim panel.
    """
    try:
        sys.path.insert(0, str(ROOT / "tools"))
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
        sys.path.insert(0, str(ROOT / "tools"))
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
        sys.path.insert(0, str(ROOT / "tools"))
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
        sys.path.insert(0, str(ROOT / "tools"))
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
        sys.path.insert(0, str(ROOT / "tools"))
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


def build_cb_reset_info():
    """Return seconds until next CB reset + reset-window-aware "today" key."""
    import datetime as _dt
    now_utc = _dt.datetime.now(_dt.timezone.utc)
    next_utc = now_utc.replace(hour=CB_RESET_UTC_HOUR, minute=0, second=0, microsecond=0)
    if next_utc <= now_utc:
        next_utc += _dt.timedelta(days=1)
    return {
        "now_utc": now_utc.isoformat(timespec="seconds"),
        "next_reset_utc": next_utc.isoformat(timespec="seconds"),
        "seconds_until_reset": int((next_utc - now_utc).total_seconds()),
        "reset_hour_utc": CB_RESET_UTC_HOUR,
    }


_autorun_state = {
    "enabled": False,
    "last_fired": None,
    "last_result": None,
    "thread_started": False,
}


def _autorun_worker():
    """Background thread: checks CB key count every 60s; fires cb_run.py if
    enabled and keys are available. Opt-in via `/api/autorun/enable`.

    Runs in a daemon thread so we don't block shutdown. Uses subprocess with
    a timeout so a stuck battle can't hang the autorunner.
    """
    import subprocess
    import time as _t
    while True:
        _t.sleep(60)
        if not _autorun_state.get("enabled"):
            continue
        try:
            import urllib.request
            raw = urllib.request.urlopen(f"{MOD_URL}/all-resources", timeout=10).read().decode()
            data = json.loads(raw)
            keys = int((data.get("cb_keys") or 0) if isinstance(data, dict) else 0)
        except Exception:
            continue
        if keys <= 0:
            continue
        # Avoid rapid refiring: require at least 60s since last fire
        last = _autorun_state.get("last_fired") or 0
        if time.time() - last < 60:
            continue
        _autorun_state["last_fired"] = time.time()
        try:
            result = subprocess.run(
                ["python", str(ROOT / "tools" / "cb_run.py")],
                cwd=str(ROOT), timeout=420,
                capture_output=True, text=True,
            )
            _autorun_state["last_result"] = {
                "ok": result.returncode == 0,
                "stdout_tail": result.stdout[-500:] if result.stdout else "",
                "stderr_tail": result.stderr[-500:] if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            _autorun_state["last_result"] = {"ok": False, "error": "timed out (>7min)"}
        except Exception as e:
            _autorun_state["last_result"] = {"ok": False, "error": str(e)}


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


def build_preset_view(preset_id):
    """Return the preset with skill_type_id→label lookups attached so the
    dashboard can render opener + priority dropdowns cleanly."""
    try:
        raw = urllib.request.urlopen(f"{MOD_URL}/presets", timeout=15).read().decode()
        fixed = re.sub(r"\{,", "{", raw)
        presets = json.loads(fixed).get("presets", [])
    except Exception as e:
        return {"error": f"fetch presets: {e}"}
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
        sys.path.insert(0, str(ROOT / "tools"))
        from tune_to_preset import build_update_preset_url as _build_url, TUNE_ROLE_DELAYS
    except Exception as e:
        return {"error": f"tune_to_preset import: {e}"}
    if tune_id not in TUNE_ROLE_DELAYS:
        return {"error": f"No delay map for tune '{tune_id}'. Available: {list(TUNE_ROLE_DELAYS.keys())}"}

    # Fetch current team names from the preset for ordered slot assignment
    team_names = []
    try:
        raw = urllib.request.urlopen(f"{MOD_URL}/presets", timeout=15).read().decode()
        # /presets may return malformed JSON — repair stray "{," sequences
        fixed = re.sub(r"\{,", "{", raw)
        presets_data = json.loads(fixed)
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
    except Exception as e:
        return {"error": f"fetching preset team failed: {e}"}

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


# ---------- Live task runner ----------

_run_state = {
    "running": False,
    "started_at": None,
    "current_task_id": None,
    "tasks": {},  # task_id -> {status, log:[], started_at, finished_at}
}
_run_lock = threading.Lock()


def _rlog(tid, msg):
    with _run_lock:
        t = _run_state["tasks"].setdefault(tid, {"log": []})
        t.setdefault("log", []).append({"ts": time.time(), "msg": str(msg)[:400]})
        if len(t["log"]) > 80:
            t["log"] = t["log"][-80:]
    logger.info("[run:%s] %s", tid, msg)


def _task_connect(tid):
    reader = memory_reader()
    if reader is None:
        _rlog(tid, "memory reader not attached")
        return False
    _rlog(tid, "attached to Raid.exe via pymem")
    client = mod_client()
    if client.available:
        try:
            status = client.get_status() or {}
            _rlog(tid, f"mod online — scene={status.get('scene')} logged_in={status.get('logged_in')}")
        except Exception as e:
            _rlog(tid, f"mod probe err: {e}")
    else:
        _rlog(tid, "mod API offline (memory-only mode)")
    return True


def _task_subprocess(tid, args, cwd=None):
    """Run a Python tool, streaming stdout into the task log."""
    _rlog(tid, f"exec: {' '.join(args)}")
    try:
        p = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd or ROOT),
            text=True,
            bufsize=1,
        )
        if p.stdout:
            for line in iter(p.stdout.readline, ''):
                line = line.rstrip()
                if line:
                    _rlog(tid, line)
        p.wait(timeout=600)
        _rlog(tid, f"exit code {p.returncode}")
        return p.returncode == 0
    except Exception as e:
        _rlog(tid, f"subprocess err: {e}")
        return False


# ---- Task impls — CLI tools only (mod API, no pyautogui per CLAUDE.md) ----

def _task_cb(tid):
    return _task_subprocess(tid, [sys.executable, str(ROOT / "tools" / "cb_daily.py"), "--wait"])


# Task ID -> impl. Only tasks with a mod-API CLI tool defined in CLAUDE.md
# are wired. Anything else reports "not implemented" — we never fall back to
# pyautogui / screen automation.
TASK_IMPL = {
    "connect": _task_connect,
    "cb":      _task_cb,
    # shop, inbox, quests_reg, quests_adv, clan, gem_mine, timed, arena,
    # dungeon, window — no pure mod-API CLI exists; reported as not-implemented
    # until someone adds tools/{shop,inbox,...}_daily.py equivalents.
}


def _runner_thread(task_ids):
    with _run_lock:
        _run_state["running"] = True
        _run_state["started_at"] = time.time()
        _run_state["tasks"] = {
            tid: {"status": "pending", "log": [], "started_at": None, "finished_at": None}
            for tid in task_ids
        }
    for tid in task_ids:
        if not _run_state["running"]:
            break  # stop requested
        with _run_lock:
            _run_state["current_task_id"] = tid
            _run_state["tasks"][tid]["status"] = "running"
            _run_state["tasks"][tid]["started_at"] = time.time()
        impl = TASK_IMPL.get(tid)
        if impl is None:
            _rlog(tid, "not implemented for this task id")
            status = "skipped"
        else:
            try:
                status = "done" if impl(tid) else "error"
            except Exception as e:
                _rlog(tid, f"unhandled exception: {e}")
                status = "error"
        with _run_lock:
            _run_state["tasks"][tid]["status"] = status
            _run_state["tasks"][tid]["finished_at"] = time.time()
    with _run_lock:
        _run_state["current_task_id"] = None
        _run_state["running"] = False


def start_run(task_ids):
    if _run_state["running"]:
        return False, "a run is already in progress"
    ids = [str(x) for x in task_ids if str(x) in TASK_IMPL or True]
    if not ids:
        return False, "no task_ids"
    threading.Thread(target=_runner_thread, args=(ids,), daemon=True).start()
    return True, f"started {len(ids)} task(s)"


def stop_run():
    with _run_lock:
        if not _run_state["running"]:
            return False, "not running"
        _run_state["running"] = False  # current task finishes, loop exits
    return True, "stop requested (current task will finish)"


# ---------- Windows Task Scheduler CRUD (scoped to \PyAutoRaid\) ----------

TASK_FOLDER = r"\PyAutoRaid"
TASK_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")


def _run_cmd(args, timeout=20):
    """Run a command list and return (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError as e:
        return 127, "", str(e)


def list_scheduled_tasks():
    """Return list of dicts for every task under \\PyAutoRaid\\."""
    ps = r"""
$out = @()
foreach ($t in (Get-ScheduledTask -TaskPath '\PyAutoRaid\*' -ErrorAction SilentlyContinue)) {
    $info = $t | Get-ScheduledTaskInfo
    $a = if ($t.Actions.Count -gt 0) { $t.Actions[0] } else { $null }
    $tr = if ($t.Triggers.Count -gt 0) { $t.Triggers[0] } else { $null }
    $out += [PSCustomObject]@{
        name = $t.TaskName
        enabled = ($t.State -ne 'Disabled')
        state = $t.State.ToString()
        execute = if ($a) { $a.Execute } else { '' }
        arguments = if ($a) { $a.Arguments } else { '' }
        workingDir = if ($a) { $a.WorkingDirectory } else { '' }
        startBoundary = if ($tr) { [string]$tr.StartBoundary } else { '' }
        lastRun = [string]$info.LastRunTime
        nextRun = [string]$info.NextRunTime
        lastResult = $info.LastTaskResult
    }
}
if ($out.Count -eq 0) { Write-Output '[]' }
elseif ($out.Count -eq 1) { Write-Output ('[' + ($out[0] | ConvertTo-Json -Depth 3 -Compress) + ']') }
else { $out | ConvertTo-Json -Depth 3 -Compress }
""".strip()
    rc, out, err = _run_cmd([
        "powershell", "-NoProfile", "-NonInteractive", "-Command", ps
    ], timeout=15)
    if rc != 0:
        logger.info("list_scheduled_tasks rc=%s err=%s", rc, err[:200])
        return []
    if not out:
        return []
    try:
        data = json.loads(out)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError as e:
        logger.info("list_scheduled_tasks parse err: %s", e)
        return []


def create_scheduled_task(name, time_hhmm, command):
    if not TASK_NAME_RE.match(name or ""):
        return False, "invalid name (A-Z, 0-9, underscore, dash only)"
    if not TIME_RE.match(time_hhmm or ""):
        return False, "time must be HH:MM"
    if not command or not command.strip():
        return False, "command required"
    tn = f"{TASK_FOLDER}\\{name}"
    rc, out, err = _run_cmd([
        "schtasks", "/Create", "/SC", "DAILY",
        "/TN", tn, "/TR", command, "/ST", time_hhmm, "/F"
    ])
    if rc == 0:
        return True, "created"
    return False, (err or out or f"exit {rc}")[:300]


def delete_scheduled_task(name):
    if not TASK_NAME_RE.match(name or ""):
        return False, "invalid name"
    tn = f"{TASK_FOLDER}\\{name}"
    rc, out, err = _run_cmd(["schtasks", "/Delete", "/TN", tn, "/F"])
    if rc == 0:
        return True, "deleted"
    return False, (err or out or f"exit {rc}")[:300]


def set_scheduled_task_enabled(name, enabled):
    if not TASK_NAME_RE.match(name or ""):
        return False, "invalid name"
    tn = f"{TASK_FOLDER}\\{name}"
    flag = "/ENABLE" if enabled else "/DISABLE"
    rc, out, err = _run_cmd(["schtasks", "/Change", "/TN", tn, flag])
    if rc == 0:
        return True, "toggled"
    return False, (err or out or f"exit {rc}")[:300]


# ---------- HTTP handler ----------

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DASHBOARD_DIR), **kw)

    def log_message(self, fmt, *args):
        logger.info("%s - %s", self.address_string(), fmt % args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/state":
            self._send_json(build_state())
            return
        if parsed.path == "/api/schedule":
            self._send_json({"tasks": list_scheduled_tasks()})
            return
        if parsed.path == "/api/run":
            self._send_json(_run_state)
            return
        if parsed.path == "/api/sim-last-run":
            self._send_json(build_sim_last_run())
            return
        if parsed.path == "/api/tune-library":
            self._send_json(build_tune_library())
            return
        if parsed.path == "/api/sim-affinity-matrix":
            self._send_json(build_sim_affinity_matrix())
            return
        if parsed.path == "/api/tune-compliance":
            q = urllib.parse.parse_qs(parsed.query)
            self._send_json(build_tune_compliance(q.get("tune", ["myth_eater"])[0]))
            return
        if parsed.path == "/api/tune-recommend":
            self._send_json(build_tune_recommend())
            return
        if parsed.path == "/api/potential-teams":
            q = urllib.parse.parse_qs(parsed.query)
            n = int((q.get("n") or [12])[0])
            self._send_json(build_potential_teams(max_count=n))
            return
        if parsed.path == "/api/calc-parity-sim":
            q = urllib.parse.parse_qs(parsed.query)
            h = (q.get("hash") or [None])[0]
            turns = int((q.get("turns") or [25])[0])
            self._send_json(build_cb_parity_sim(hash_=h, max_boss_turns=turns))
            return
        if parsed.path == "/api/preset":
            q = urllib.parse.parse_qs(parsed.query)
            pid = int(q.get("id", ["1"])[0])
            self._send_json(build_preset_view(pid))
            return
        if parsed.path == "/api/cb-history":
            self._send_json(build_cb_history_with_attribution())
            return
        if parsed.path == "/api/autorun/status":
            self._send_json({"enabled": _autorun_state.get("enabled", False),
                             "last_fired": _autorun_state.get("last_fired"),
                             "last_result": _autorun_state.get("last_result")})
            return
        if parsed.path == "/api/cb-reset-info":
            self._send_json(build_cb_reset_info())
            return
        if parsed.path == "/api/sim-sweep":
            q = urllib.parse.parse_qs(parsed.query)
            try:
                hero = q.get("hero", [""])[0]
                lo = int(q.get("lo", ["0"])[0])
                hi = int(q.get("hi", ["0"])[0])
                self._send_json(build_sim_sweep(hero, lo, hi))
            except Exception as e:
                self._send_json({"error": str(e)}, status=400)
            return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get('Content-Length') or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send_json({"error": "invalid json"}, status=400)

        if parsed.path == "/api/schedule":
            ok, msg = create_scheduled_task(
                body.get("name", ""), body.get("time", ""), body.get("command", "")
            )
            return self._send_json({"ok": ok, "message": msg}, status=200 if ok else 400)

        if parsed.path == "/api/run":
            ids = body.get("task_ids") or []
            if not isinstance(ids, list):
                return self._send_json({"error": "task_ids must be a list"}, status=400)
            ok, msg = start_run(ids)
            return self._send_json({"ok": ok, "message": msg}, status=200 if ok else 409)

        if parsed.path == "/api/apply-tune":
            tune = body.get("tune") or ""
            preset_id = int(body.get("preset_id") or 1)
            return self._send_json(apply_tune_to_preset(tune, preset_id))

        if parsed.path == "/api/autorun/enable":
            _autorun_state["enabled"] = bool(body.get("enabled", True))
            return self._send_json({"ok": True, "enabled": _autorun_state["enabled"]})

        if parsed.path == "/api/preset/edit":
            # Raw priority+opener push for a single preset. Accepts:
            #   {"preset_id":1, "heroes":[{"hero_id":X, "opener":<sid|null>,
            #                              "priorities":{sid: rank, ...}}, ...]}
            pid = int(body.get("preset_id") or 1)
            heroes = body.get("heroes") or []
            return self._send_json(edit_preset_raw(pid, heroes))

        m = re.match(r"^/api/schedule/([A-Za-z0-9_\-]+)/toggle$", parsed.path)
        if m:
            ok, msg = set_scheduled_task_enabled(m.group(1), bool(body.get("enabled", True)))
            return self._send_json({"ok": ok, "message": msg}, status=200 if ok else 400)

        self._send_json({"error": "not found"}, status=404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/run":
            ok, msg = stop_run()
            return self._send_json({"ok": ok, "message": msg}, status=200 if ok else 400)
        m = re.match(r"^/api/schedule/([A-Za-z0-9_\-]+)$", parsed.path)
        if not m:
            return self._send_json({"error": "not found"}, status=404)
        ok, msg = delete_scheduled_task(m.group(1))
        self._send_json({"ok": ok, "message": msg}, status=200 if ok else 400)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class ReusableServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    logger.info("Serving %s on http://localhost:%d", DASHBOARD_DIR, PORT)
    logger.info("Mod API target: %s", MOD_URL)
    logger.info("CB reset hour: %02d:00 UTC (PYAUTORAID_CB_RESET_UTC_HOUR to override)", CB_RESET_UTC_HOUR)
    logger.info("Dashboard: http://localhost:%d/PyAutoRaid%%20Dashboard.html", PORT)
    # Start autorun worker (disabled by default; opt-in via /api/autorun/enable)
    if not _autorun_state.get("thread_started"):
        _autorun_state["thread_started"] = True
        t = threading.Thread(target=_autorun_worker, daemon=True, name="cb-autorun")
        t.start()
    with ReusableServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("shutting down")


if __name__ == "__main__":
    main()
