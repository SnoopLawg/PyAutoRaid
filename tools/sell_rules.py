"""Sell-rule engine for artifacts.

Inspired by RSL Helper's filter chain. Rules are evaluated top-to-bottom.
First rule whose ALL conditions match → action = sell. No match → keep.

Persistence: data/sell_rules.json (auto-created with sensible defaults).

Each artifact dict expected to have at minimum:
  {id, kind (slot int 1-9), rank, rarity, set_id, set_name?, hero_id?,
   primary_stat (int 1-8), substats: [{stat, value, is_flat/flat}, ...]}

Conditions on a rule (all AND):
  enabled            — rule on/off
  min_rank/max_rank  — inclusive
  min_rarity/max_rarity — inclusive (1=Common, 6=Mythic)
  slots              — list of slot names ['Boots', 'Chest', ...]
  sets               — list of set names to match (case-insensitive)
  set_in_junk_list   — true → set must be in config.junk_sets
  primary_in         — list of primary stat names to require ['SPD', 'HP%', ...]
  primary_not_in     — list of primary stat names to exclude
  primary_not_in_slot_required — true → primary NOT in
                       config.slot_required_primary[slot]; if slot not in
                       the map, condition is false (skip the artifact)
  max_useful_subs    — integer, artifact must have <= this many useful subs
  min_useful_subs    — integer, artifact must have >= this many useful subs
  exclude_equipped   — true → only match unequipped (hero_id 0/null)

Slot id → name mapping mirrors raid_data SLOT_KIND_MAP.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = PROJECT_ROOT / "data" / "sell_rules.json"

SLOT_NAMES = {1: "Helmet", 2: "Chest", 3: "Gloves", 4: "Boots",
              5: "Weapon", 6: "Shield", 7: "Ring", 8: "Amulet", 9: "Banner"}
SLOT_NAME_TO_ID = {v: k for k, v in SLOT_NAMES.items()}

# Primary stat naming follows the user-facing convention:
# percent variants for HP/ATK/DEF, flat for SPD/RES/ACC/CR/CD.
STAT_INT_TO_NAME_PRIMARY = {
    1: "HP%", 2: "ATK%", 3: "DEF%", 4: "SPD",
    5: "RES", 6: "ACC", 7: "CR", 8: "CD",
}
STAT_INT_TO_NAME_FLAT = {
    1: "HP", 2: "ATK", 3: "DEF", 4: "SPD",
    5: "RES", 6: "ACC", 7: "CR", 8: "CD",
}

DEFAULT_USEFUL_SUBSTATS = ["SPD", "ACC", "CR", "CD", "HP%", "ATK%", "DEF%"]
DEFAULT_SLOT_REQUIRED = {
    "Boots":  ["SPD"],
    "Banner": ["ACC", "RES"],
    "Chest":  ["HP%", "ATK%", "DEF%"],
    "Gloves": ["CR", "CD"],
}
DEFAULT_JUNK_SETS = ["Avenge", "Frenzy", "CounterAttack", "Resilience", "Shield"]

DEFAULT_RULES = [
    {"id": "trash", "name": "Sell ranks 1-3 (trash drops)",
     "enabled": True, "max_rank": 3},
    {"id": "low_rare", "name": "Sell rank 4 below epic",
     "enabled": True, "max_rank": 4, "max_rarity": 3},
    {"id": "junk_set", "name": "Sell junk-set rank 5",
     "enabled": True, "max_rank": 5, "set_in_junk_list": True},
    {"id": "bad_primary_r5",
     "name": "Sell R5 with wrong primary on key slots",
     "enabled": True,
     "min_rank": 5, "max_rank": 5,
     "slots": ["Boots", "Banner", "Chest", "Gloves"],
     "primary_not_in_slot_required": True},
    {"id": "no_useful_subs_r5",
     "name": "Sell R5 with < 2 useful substats",
     "enabled": False,
     "min_rank": 5, "max_rank": 5,
     "max_useful_subs": 1},
]

DEFAULT_CONFIG = {
    "version": 1,
    "useful_substats": DEFAULT_USEFUL_SUBSTATS,
    "slot_required_primary": DEFAULT_SLOT_REQUIRED,
    "junk_sets": DEFAULT_JUNK_SETS,
    "rules": DEFAULT_RULES,
    "exclude_equipped": True,  # global safety: never auto-sell equipped pieces
}


def load_rules(path: Path = RULES_PATH) -> dict:
    """Load rules; create defaults if file is missing or malformed."""
    try:
        if path.exists():
            cfg = json.loads(path.read_text())
            return _migrate(cfg)
    except Exception:
        pass
    save_rules(DEFAULT_CONFIG, path)
    return json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy


def save_rules(cfg: dict, path: Path = RULES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))


def _migrate(cfg: dict) -> dict:
    """Fill in defaults for missing keys so older saves still work."""
    out = dict(DEFAULT_CONFIG)
    out.update(cfg)
    out["rules"] = list(cfg.get("rules") or DEFAULT_RULES)
    out["useful_substats"] = list(
        cfg.get("useful_substats") or DEFAULT_USEFUL_SUBSTATS)
    out["slot_required_primary"] = dict(
        cfg.get("slot_required_primary") or DEFAULT_SLOT_REQUIRED)
    out["junk_sets"] = list(cfg.get("junk_sets") or DEFAULT_JUNK_SETS)
    if "exclude_equipped" not in cfg:
        out["exclude_equipped"] = True
    return out


_PCT_STATS = {"HP", "ATK", "DEF"}


def _primary_name(art: dict) -> str:
    """Return user-facing primary stat name (e.g. 'SPD', 'HP%').

    Handles two input shapes:
      - mod /all-artifacts (build_artifacts output): primary_stat is a string
        like "HP", primary_flat is bool. HP/ATK/DEF on Helmet/Chest/Ring/etc.
        is "HP%" / "ATK%" / "DEF%" only when flat=False.
      - raw mod data: primary={'stat': 1, 'flat': False, ...}
    """
    pstat = art.get("primary_stat")
    pflat = art.get("primary_flat")
    if pstat is None:
        p = art.get("primary") or {}
        pstat = p.get("stat")
        pflat = p.get("flat") if pflat is None else pflat
    if pstat is None or pstat == "":
        return ""
    if isinstance(pstat, str):
        if pstat in _PCT_STATS and not pflat:
            return f"{pstat}%"
        return pstat
    if pflat or int(pstat) in (4, 5, 6, 7, 8):
        return STAT_INT_TO_NAME_FLAT.get(int(pstat), str(pstat))
    return STAT_INT_TO_NAME_PRIMARY.get(int(pstat), str(pstat))


def _sub_names(art: dict) -> list[str]:
    """Return list of substat names like ['SPD', 'CR', 'HP%']."""
    out = []
    for s in (art.get("substats") or []):
        sid = s.get("stat") or s.get("stat_id")
        flat = s.get("is_flat", s.get("flat", 0))
        if sid is None or sid == "":
            continue
        if isinstance(sid, str):
            if sid in _PCT_STATS and not flat:
                out.append(f"{sid}%")
            else:
                out.append(sid)
            continue
        if flat or int(sid) in (4, 5, 6, 7, 8):
            out.append(STAT_INT_TO_NAME_FLAT.get(int(sid), str(sid)))
        else:
            out.append(STAT_INT_TO_NAME_PRIMARY.get(int(sid), str(sid)))
    return out


def _slot_name(art: dict) -> str:
    """Return slot name. Handles string ("Boots") or int (1-9) input."""
    s = art.get("slot")
    if isinstance(s, str) and s:
        return s
    sid = art.get("kind") or art.get("slot_id") or s
    if isinstance(sid, str):
        return sid
    return SLOT_NAMES.get(int(sid or 0), "")


def _is_equipped(art: dict) -> bool:
    """build_artifacts shape uses `equipped_on` dict; raw shape uses `hero_id`."""
    if art.get("equipped_on"):
        return True
    return bool(art.get("hero_id"))


def _set_name(art: dict) -> str:
    return (art.get("set_name") or "").strip()


def evaluate(art: dict, cfg: dict) -> dict:
    """Evaluate one artifact against the rule chain.

    Returns: {"action": "sell"|"keep", "rule_id": str|None,
              "rule_name": str|None}
    """
    if cfg.get("exclude_equipped", True):
        if _is_equipped(art):
            return {"action": "keep", "rule_id": None, "rule_name": None}

    primary = _primary_name(art)
    subs = _sub_names(art)
    slot = _slot_name(art)
    set_n = _set_name(art)
    rank = int(art.get("rank") or 0)
    rarity = int(art.get("rarity") or 0)

    useful = set(cfg.get("useful_substats") or [])
    junk_sets = {s.lower() for s in (cfg.get("junk_sets") or [])}
    slot_req = cfg.get("slot_required_primary") or {}

    n_useful = sum(1 for s in subs if s in useful)

    for r in (cfg.get("rules") or []):
        if not r.get("enabled", True):
            continue
        if "min_rank" in r and rank < int(r["min_rank"]):
            continue
        if "max_rank" in r and rank > int(r["max_rank"]):
            continue
        if "min_rarity" in r and rarity < int(r["min_rarity"]):
            continue
        if "max_rarity" in r and rarity > int(r["max_rarity"]):
            continue
        if r.get("slots") and slot not in r["slots"]:
            continue
        if r.get("sets"):
            wanted = {s.lower() for s in r["sets"]}
            if set_n.lower() not in wanted:
                continue
        if r.get("set_in_junk_list"):
            if set_n.lower() not in junk_sets:
                continue
        if r.get("primary_in") and primary not in r["primary_in"]:
            continue
        if r.get("primary_not_in") and primary in r["primary_not_in"]:
            continue
        if r.get("primary_not_in_slot_required"):
            req = slot_req.get(slot)
            if not req or primary in req:
                continue  # this artifact's primary IS in required → keep
        if "max_useful_subs" in r and n_useful > int(r["max_useful_subs"]):
            continue
        if "min_useful_subs" in r and n_useful < int(r["min_useful_subs"]):
            continue
        return {"action": "sell", "rule_id": r.get("id"),
                "rule_name": r.get("name")}

    return {"action": "keep", "rule_id": None, "rule_name": None}


def evaluate_all(artifacts: list[dict], cfg: dict | None = None) -> dict:
    """Evaluate a list of artifacts. Returns counts + per-artifact decisions."""
    cfg = cfg or load_rules()
    sell, keep = [], []
    by_rule: dict[str, int] = {}
    for a in artifacts:
        d = evaluate(a, cfg)
        if d["action"] == "sell":
            sell.append({**d, "id": a.get("id"), "slot": _slot_name(a),
                         "set": _set_name(a), "rank": a.get("rank"),
                         "rarity": a.get("rarity"),
                         "primary": _primary_name(a)})
            by_rule[d["rule_id"] or "?"] = by_rule.get(d["rule_id"] or "?", 0) + 1
        else:
            keep.append(a.get("id"))
    return {
        "sell_count": len(sell),
        "keep_count": len(keep),
        "by_rule": by_rule,
        "sell": sell,
    }


if __name__ == "__main__":
    import sys
    cfg = load_rules()
    print(f"Rules file: {RULES_PATH}")
    print(f"Rules: {len(cfg['rules'])}")
    if "--evaluate" in sys.argv:
        # Load all artifacts from all_artifacts.json and report
        path = PROJECT_ROOT / "all_artifacts.json"
        if not path.exists():
            print("all_artifacts.json missing — run refresh_data.py first")
            sys.exit(1)
        data = json.loads(path.read_text())
        arts = data.get("artifacts", data) if isinstance(data, dict) else data
        result = evaluate_all(arts, cfg)
        print(f"\nSell: {result['sell_count']}  Keep: {result['keep_count']}")
        for rid, n in result['by_rule'].items():
            print(f"  {rid:25s}: {n}")
