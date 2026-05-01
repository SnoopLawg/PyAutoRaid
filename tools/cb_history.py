"""CB battle-log readers and per-key history aggregator.

Reads battle_logs_cb_*.json files saved by tools/cb_run.py / cb_daily.py
and turns them into structured summaries (per-day key history, last-run
team breakdown). Primary consumers are the dashboard's CB panels and
the CLI here.

CLI usage:
    python3 tools/cb_history.py history --days 7
    python3 tools/cb_history.py last-run
    python3 tools/cb_history.py last-run --json
"""
from __future__ import annotations

import datetime
import glob
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


# ============================================================================
# Battle log loaders
# ============================================================================

def most_recent_battle_log(root: Path) -> Path | None:
    """Pick the newest battle_logs_cb_*.json by mtime. Prefers timestamped
    files; falls back to battle_logs_cb_latest.json if that's all we have."""
    candidates = glob.glob(str(root / "battle_logs_cb_*.json"))
    if not candidates:
        return None
    def _key(p):
        name = Path(p).name
        return (name != "battle_logs_cb_latest.json", Path(p).stat().st_mtime)
    candidates.sort(key=_key)
    return Path(candidates[-1])


def load_battle_log(root: Path, *, cache: dict | None = None) -> dict | None:
    """Load the most-recent CB battle log JSON (parsed). Optional cache dict
    is keyed by (path, mtime) so repeated calls don't re-parse."""
    path = most_recent_battle_log(root)
    if path is None or not path.exists():
        return None
    mtime = path.stat().st_mtime
    cache_key = (str(path), mtime)
    if cache is not None and cache.get("key") == cache_key and cache.get("data"):
        return cache["data"]
    try:
        data = json.loads(path.read_text())
        if cache is not None:
            cache["key"] = cache_key
            cache["mtime"] = mtime
            cache["path"] = path
            cache["data"] = data
        return data
    except Exception as e:
        logger.info("battle log parse failed (%s): %s", path.name, e)
        return None


def hero_type_to_name(root: Path) -> dict[int, str]:
    """Best-effort hero type_id -> name map. Prefers skills_db.json, falls
    back to skill_descriptions.json. The result map is small enough to
    rebuild per call (a few hundred entries)."""
    out: dict[int, str] = {22270: "CB Boss"}
    skills_path = root / "skills_db.json"
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
    desc_path = root / "skill_descriptions.json"
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


# ============================================================================
# Per-key history (last N days of CB damage)
# ============================================================================

def per_key_history(root: Path, *, days: int = 7) -> list[dict]:
    """Aggregate per-run CB damage from saved battle_logs_cb_*.json files,
    grouped by CB window. Each key entry has damage, team, turn count,
    affinity, and file timestamp for hover tooltips."""
    from tools.cb_day import cb_day_for_timestamp, cb_day_today, cb_affinity_name

    name_map = hero_type_to_name(root)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for path in glob.glob(str(root / "battle_logs_cb_*.json")):
        name = Path(path).name
        if name == "battle_logs_cb_latest.json":
            continue
        try:
            mt = Path(path).stat().st_mtime
            cb_date = cb_day_for_timestamp(mt)
        except Exception:
            continue
        try:
            data = json.loads(Path(path).read_text())
            entries = data.get("log", []) if isinstance(data, dict) else []
            max_dmg = 0
            turns = 0
            team_types: list[int] = []
            boss_tid = None
            boss_element = None
            for e in entries:
                if not isinstance(e, dict):
                    continue
                for h in (e.get("heroes") or []):
                    if h.get("side") == "enemy":
                        max_dmg = max(max_dmg, int(h.get("dmg_taken", 0) or 0))
                        turns = max(turns, int(h.get("turn_n", 0) or 0))
                        if not boss_tid:
                            boss_tid = h.get("type_id")
                        if not boss_element:
                            boss_element = h.get("element")
                if not team_types and e.get("heroes"):
                    team_types = [
                        h.get("type_id") for h in e["heroes"]
                        if h.get("side") == "player"
                    ]
            if max_dmg <= 0:
                continue
            team_names = [name_map.get(tid, f"#{tid}") for tid in team_types if tid]
            local_dt = datetime.datetime.fromtimestamp(mt)
            affinity = cb_affinity_name(boss_element, boss_tid)
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
    today = cb_day_today()
    out: list[dict] = []
    for i in range(days - 1, -1, -1):
        d = today - datetime.timedelta(days=i)
        iso = d.isoformat()
        keys = sorted(by_day.get(iso, []), key=lambda k: -k["damage"])
        out.append({
            "date": iso,
            "day": iso[5:],
            "keys": keys,
            "total": sum(k["damage"] for k in keys),
        })
    return out


# ============================================================================
# Last-run battle log decode (team + boss + per-turn timeline)
# ============================================================================
# Internal helper sets used by build_last_run.

DOT_DEBUFF_TYPES = {80, 81, 470, 310}  # Poison 5%/2.5%, HP Burn, legacy HPB


def build_last_run(
    root: Path,
    *,
    cache: dict | None = None,
    fetch_all_heroes: Callable[[], list[dict]] | None = None,
    status_id_to_name: dict[int, str] | None = None,
    compute_actual_stats: Callable[[dict], dict] | None = None,
) -> dict | None:
    """Parse the most recent CB battle log into a team breakdown + timeline.

    Dependency injection points:
    - fetch_all_heroes(): callable returning the mod's /all-heroes payload.
      Used to enrich each team slot with rarity/faction/level metadata.
      If None, those fields are blank.
    - status_id_to_name: {effect_id: pretty_name} for buff/debuff names.
      If None, raw "effect <id>" labels are used.
    - compute_actual_stats(hero_dict): returns gear-inclusive stats dict
      (HP/ATK/DEF/SPD/...). Defaults to tools.hero_stats.compute_hero_actual_stats.

    Returns the same shape the dashboard's build_cb_last_run did:
        {team: [...], boss: {...}, last_run: {...}}
    or None if there's no battle log to parse.
    """
    from tools.cb_day import cb_affinity_name
    from tools.raid_names import (
        FACTION_PRETTY, RARITY_NAMES, ROLE_NAMES, ELEMENT_NAMES, FACTION_NAMES,
    )

    if compute_actual_stats is None:
        from tools.hero_stats import compute_hero_actual_stats as compute_actual_stats  # type: ignore[assignment]

    if status_id_to_name is None:
        status_id_to_name = {}

    data = load_battle_log(root, cache=cache)
    if not data:
        return None
    log = data.get("log", []) if isinstance(data, dict) else data
    name_map = hero_type_to_name(root)

    # Pre-index mod's /all-heroes by NAME — battle log type_id is an internal
    # slot id that doesn't match /all-heroes's TypeId. Names are the bridge.
    heroes_by_name: dict[str, dict] = {}
    if fetch_all_heroes is not None:
        try:
            for h in (fetch_all_heroes() or []):
                n = h.get("name")
                if n and n not in heroes_by_name:
                    heroes_by_name[n] = h
        except Exception as e:
            logger.info("fetch_all_heroes failed: %s", e)

    team: dict = {}
    boss_prev_dmg = 0
    boss_max_hp = 0
    boss_tid = None
    boss_element = None
    dealt_attrib: dict = {}
    active_hero_id = None
    last_active_hero = None
    turn_has_hero_action = False
    current_boss_debuffs: list = []
    debuff_placement_sigs: set = set()
    debuff_counts_by_type: dict = {}
    debuff_by_src: dict = {}
    boss_status_seen: set = set()
    boss_uk_saves = 0
    timeline: list = []

    turn_log: dict = {}
    boss_prev_hp = None
    prev_buffs_by_slot: dict = {}
    prev_boss_mods: set = set()
    prev_boss_turn = 0
    prev_boss_uk_saved = False

    total_damage = 0
    turns_total = 0

    def hero_for(hid):
        slot = team.get(hid)
        if not slot:
            return f"#{hid}"
        return name_map.get(slot["type_id"], f"#{slot['type_id']}")

    def _ensure_turn(t):
        if t not in turn_log:
            turn_log[t] = {
                "boss_turn": t,
                "events": [],
                "damage": 0,
                "boss_hp_start": None,
                "boss_hp_end": None,
                "boss_action": ["AOE1", "AOE2", "STUN"][t % 3],
                "protection": {},
            }
        return turn_log[t]

    for entry in log:
        if not isinstance(entry, dict):
            continue
        if "active_hero" in entry:
            hid = entry.get("active_hero")
            active_hero_id = hid
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

                if boss_turn != prev_boss_turn:
                    if prev_boss_turn and prev_boss_turn in turn_log:
                        turn_log[prev_boss_turn]["boss_hp_end"] = h.get("hp_cur")
                    if boss_turn:
                        tl = _ensure_turn(boss_turn)
                        if tl["boss_hp_start"] is None:
                            tl["boss_hp_start"] = h.get("hp_cur")
                    prev_boss_turn = boss_turn
                    turn_has_hero_action = False

                current_boss_debuffs = list(h.get("debuffs") or [])

                if cur_dmg > boss_prev_dmg:
                    delta = cur_dmg - boss_prev_dmg
                    is_hero_phase = (
                        turn_has_hero_action
                        and active_hero_id is not None
                        and active_hero_id in team
                    )
                    if is_hero_phase:
                        dealt_attrib[active_hero_id] = dealt_attrib.get(active_hero_id, 0) + delta
                        by_name = hero_for(active_hero_id)
                    else:
                        dot_sources = [db.get("src") for db in current_boss_debuffs
                                       if db.get("t") in DOT_DEBUFF_TYPES and db.get("src") is not None]
                        if dot_sources:
                            share = delta / len(dot_sources)
                            for src in dot_sources:
                                dealt_attrib[src] = dealt_attrib.get(src, 0) + share
                            top_src = Counter(dot_sources).most_common(1)[0][0]
                            by_name = f"{hero_for(top_src)} (DoT)"
                        else:
                            if active_hero_id is not None:
                                dealt_attrib[active_hero_id] = dealt_attrib.get(active_hero_id, 0) + delta
                            by_name = hero_for(active_hero_id) if active_hero_id is not None else "?"
                    if boss_turn and boss_turn in turn_log:
                        turn_log[boss_turn]["damage"] += delta
                    if delta >= 500_000:
                        timeline.append({"t": boss_turn, "ev": f"{delta/1e6:.2f}M damage", "by": by_name})
                    boss_prev_dmg = cur_dmg

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
                    debuff_counts_by_type[t_id] = debuff_counts_by_type.get(t_id, 0) + 1
                    k_src = (t_id, src)
                    debuff_by_src[k_src] = debuff_by_src.get(k_src, 0) + 1
                    if boss_turn in turn_log:
                        name = status_id_to_name.get(t_id, f"effect {t_id}")
                        by_name = hero_for(src) if src is not None else (hero_for(active_hero_id) if active_hero_id is not None else "?")
                        turn_log[boss_turn]["events"].append({
                            "k": "debuff", "name": name, "by": by_name,
                        })

                for st in (h.get("st") or []):
                    boss_status_seen.add(st)

                cur_uk = h.get("uk_saved") is True
                if cur_uk and not prev_boss_uk_saved:
                    boss_uk_saves += 1
                prev_boss_uk_saved = cur_uk

                total_damage = cur_dmg
                turns_total = max(turns_total, boss_turn)
            elif side == "player":
                slot = team.setdefault(hid, {
                    "type_id": tid, "dmg_taken": 0, "absorbed": 0, "turns": 0,
                    "buffs_seen": set(), "status_seen": set(),
                    "counter_procs": 0, "uk_saves": 0,
                    "hp_max": h.get("hp_max", 0) or 0,
                })
                dt = h.get("dmg_taken") or h.get("hp_lost") or 0
                slot["dmg_taken"] = max(slot["dmg_taken"], dt)
                slot["turns"] = max(slot["turns"], h.get("turn_n", 0) or 0)
                abs_dict = h.get("abs") or {}
                try:
                    total_abs = sum(int(v) for v in abs_dict.values())
                except Exception:
                    total_abs = 0
                slot["absorbed"] = max(slot["absorbed"], total_abs)

                for st in (h.get("st") or []):
                    slot["status_seen"].add(st)

                if "buff_sources" not in slot:
                    slot["buff_sources"] = {}
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

                if prev_boss_turn and prev_boss_turn in turn_log:
                    turn_log[prev_boss_turn]["protection"][hid] = {
                        "uk": 320 in cur_buff_types,
                        "bd": 60 in cur_buff_types,
                        "sh": 280 in cur_buff_types,
                    }
                prev = prev_buffs_by_slot.get(hid, set())
                added = cur_buff_types - prev
                if added and prev_boss_turn:
                    hero_name = name_map.get(slot["type_id"], f"#{hid}")
                    for t_id in added:
                        name = status_id_to_name.get(t_id)
                        if not name:
                            continue
                        _ensure_turn(prev_boss_turn)["events"].append({
                            "k": "buff", "name": name, "on": hero_name,
                        })
                prev_buffs_by_slot[hid] = cur_buff_types

                ctr_dict = h.get("ctr") or {}
                try:
                    ctr_total = sum(int(v) for v in ctr_dict.values())
                except Exception:
                    ctr_total = 0
                if ctr_total > slot["counter_procs"]:
                    slot["counter_procs"] = ctr_total

    if not team:
        return None

    team_out = []
    for hid, slot in sorted(team.items()):
        tid = slot["type_id"]
        lookup_name = name_map.get(tid, f"#{tid}")
        meta = heroes_by_name.get(lookup_name) or {}
        rarity = RARITY_NAMES.get(meta.get("rarity") or 0, "")
        # /all-heroes can emit fraction as int or string; resolve both.
        f_val = meta.get("fraction")
        if isinstance(f_val, int):
            faction = FACTION_NAMES.get(f_val, "")
        elif isinstance(f_val, str):
            faction = FACTION_PRETTY.get(f_val, f_val)
        else:
            faction = ""
        buff_sources = slot.get("buff_sources") or {}
        buffs_named = []

        def _slot_name(slot_id):
            if slot_id == hid: return "self"
            other = team.get(slot_id)
            if other and other.get("type_id"):
                return name_map.get(other["type_id"], f"#{slot_id}")
            return f"#{slot_id}"

        for t_id in sorted(slot.get("buffs_seen") or set()):
            if t_id not in status_id_to_name:
                continue
            srcs = buff_sources.get(t_id, set())
            buffs_named.append({
                "name": status_id_to_name[t_id],
                "sources": sorted({_slot_name(s) for s in srcs}),
            })
        actual = compute_actual_stats(meta) if meta else {}
        team_out.append({
            "name": lookup_name,
            "preset_slot": hid + 1,
            "role": ROLE_NAMES.get(meta.get("role") or 0, ""),
            "rarity": rarity,
            "faction": faction,
            "stars": meta.get("grade") or 0,
            "element": ELEMENT_NAMES.get(meta.get("element") or 0, ""),
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

    debuffs_applied: dict = {}
    label_group = {
        "Poison 5%": "Poison", "Poison 2.5%": "Poison",
        "Block Heal 100": "Block Heal", "Block Heal 50": "Block Heal",
        "Weaken 15": "Weaken",
        "Dec Atk 25": "Dec ATK", "Dec Atk": "Dec ATK",
        "Dec Def 30": "Dec DEF", "Def Down": "Dec DEF",
        "Dec Spd 15": "Dec SPD", "Dec Spd": "Dec SPD",
        "Dec Cd 15": "Dec CD", "Dec Cd 25": "Dec CD",
        "Hp Burn": "HP Burn",
        "Dec Res 25": "Dec RES", "Dec Res 50": "Dec RES",
        "Block Revive": "Block Revive", "Leech": "Leech",
        "Fear": "Fear", "True Fear": "True Fear",
        "Poison Sensitivity": "Poison Sensitivity",
        "Poison Sensitivity 50": "Poison Sensitivity",
        "Stun": "Stun", "Freeze": "Freeze", "Sleep": "Sleep",
        "Provoke": "Provoke",
        "Dec Cr 15": "Dec CR", "Dec Cr": "Dec CR",
        "Cooldown": "Inc Cooldown",
    }
    for t_id, n in debuff_counts_by_type.items():
        name = status_id_to_name.get(t_id, f"effect {t_id}")
        canonical = label_group.get(name, name)
        debuffs_applied[canonical] = debuffs_applied.get(canonical, 0) + n

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

    boss_info = {
        "hp_max": boss_max_hp if boss_max_hp else None,
        "type_id": boss_tid,
        "element": boss_element,
        "affinity": cb_affinity_name(boss_element, boss_tid),
    }

    turn_log_out = []
    for t in sorted(turn_log.keys()):
        tl = turn_log[t]
        compact = []
        for ev in tl["events"]:
            if compact and compact[-1] == ev:
                continue
            compact.append(ev)
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


# ============================================================================
# CLI — headless equivalent of the dashboard's CB history panels.
# ============================================================================

def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_path(root: Path) -> None:
    import sys
    for p in (str(root), str(root / "tools")):
        if p not in sys.path:
            sys.path.insert(0, p)


def _fetch_all_heroes_default(mod_url: str = "http://localhost:6790"):
    """Live-pull /all-heroes; returns [] on any error."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{mod_url}/all-heroes", timeout=30) as r:
            return json.loads(r.read().decode("utf-8")).get("heroes", [])
    except Exception:
        return []


def _cmd_history(args) -> int:
    root = _project_root()
    _ensure_path(root)
    days = per_key_history(root, days=args.days)
    if args.json:
        print(json.dumps(days, indent=2))
        return 0
    for d in days:
        keys = d["keys"]
        total_m = d["total"] / 1e6
        print(f"{d['date']} ({d['day']}) - {total_m:6.2f}M total - {len(keys)} keys")
        for k in keys:
            team = ", ".join(k["team"][:5])
            print(f"  {k['time']:5s} {k['damage']/1e6:6.2f}M  T={k['turns']:>3}  "
                  f"{(k.get('affinity') or '?'):6}  {team}")
    return 0


def _cmd_last_run(args) -> int:
    root = _project_root()
    _ensure_path(root)
    fetcher = (lambda: _fetch_all_heroes_default(args.mod_url)) if not args.no_mod else None
    result = build_last_run(root, fetch_all_heroes=fetcher)
    if not result:
        print("(no battle log to parse)")
        return 1
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    boss = result["boss"]
    lr = result["last_run"]
    print(f"Last run: {lr['damage']/1e6:.2f}M dmg in {lr['turns_total']} boss turns")
    print(f"Boss: type_id={boss['type_id']} element={boss['element']} "
          f"affinity={boss['affinity']}")
    print(f"\nTeam:")
    print(f"  {'name':22s} {'role':9s} {'spd':>4} {'dmg dealt':>11} {'dmg taken':>10}")
    for t in result["team"]:
        print(f"  {t['name'][:22]:22s} {t['role']:9s} {t['spd']:>4} "
              f"{t['dmg_dealt']/1e6:>9.2f}M {t['dmg_taken']:>10}")
    print(f"\nDebuffs placed on boss:")
    for label, n in sorted(lr["debuffs_applied"].items(), key=lambda kv: -kv[1]):
        print(f"  {n:>4}  {label}")
    return 0


def _main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    hi = sub.add_parser("history", help="per-day CB damage history")
    hi.add_argument("--days", type=int, default=7)
    hi.add_argument("--json", action="store_true")
    hi.set_defaults(func=_cmd_history)

    lr = sub.add_parser("last-run", help="parse latest battle log into team summary")
    lr.add_argument("--mod-url", default="http://localhost:6790")
    lr.add_argument("--no-mod", action="store_true",
                    help="skip /all-heroes enrichment (raw log only)")
    lr.add_argument("--json", action="store_true")
    lr.set_defaults(func=_cmd_last_run)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(_main())
