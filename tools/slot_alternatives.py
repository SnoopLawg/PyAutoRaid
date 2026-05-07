"""Phase 8: enumerate alternatives for each generic DPS slot in a tune.

For each `is_generic` slot in a PotentialTeam, substitute every owned
6★ hero one at a time, re-run the sim, and surface the top-N by
damage. Lets the dashboard show "if you put Cardiel in slot 3 instead
of Ninja, this tune does X more damage."

Cached on disk so the same tune doesn't re-solve repeatedly. Cache is
invalidated by `vault_signature` (a hash of the user's owned 6★ hero
ids), so re-running a tune after acquiring a new 6★ refreshes the
candidate pool.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "slot_alternatives_cache.json"


def _owned_6star_signature() -> str:
    try:
        with open(ROOT / "heroes_6star.json") as f:
            data = json.load(f)
        ids = sorted(h.get("id", 0) for h in data.get("heroes", []))
        return hashlib.sha1(",".join(map(str, ids)).encode()).hexdigest()[:12]
    except Exception:
        return "no-roster"


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def compute_slot_alternatives(pt: dict, default_fillers: List[str],
                              cb_element: int = 4, top_n: int = 5,
                              cache_key: Optional[str] = None) -> dict:
    """For each generic slot in `pt`, find top-N owned 6★ heroes by sim damage.

    Args:
        pt: PotentialTeam dict from build_potential_team. Must have a
            non-blocked potential_team.
        default_fillers: hero names that fill generic slots when no
            substitution is being tested. Usually the user's last battle
            team in priority order.
        cb_element: 1=Magic 2=Force 3=Spirit 4=Void.
        top_n: how many alternatives to surface per generic slot.
        cache_key: when set, results are cached on disk under this key.

    Returns:
        {
          "slug": ...,
          "default_damage": int,         # sim with default fillers
          "default_fillers": [...],
          "slots": [
            {
              "index": 3,
              "label": "4:3 DPS",
              "alternatives": [
                {"hero": "Cardiel", "damage": 38123456, "delta": +500000},
                ...
              ]
            }
          ]
        }
    """
    sig = _owned_6star_signature()
    if cache_key:
        cache = _load_cache()
        cached = cache.get(cache_key)
        if cached and cached.get("vault_signature") == sig:
            return cached["data"]

    info = pt.get("potential_team") or {}
    team = info.get("team") or []
    if not team:
        return {"error": "no team — tune has blockers"}

    # Find generic slots (the substitution candidates).
    generic_indices = [i for i, s in enumerate(team) if s.get("is_generic")]
    if not generic_indices:
        return {
            "slug": pt.get("tune_slug"),
            "default_damage": None,
            "default_fillers": default_fillers,
            "slots": [],
            "note": "no generic slots — every slot is named in the tune",
        }

    from cb_sim import run_potential_team
    # Pool of owned 6★ heroes excluding those already named in the tune.
    with open(ROOT / "heroes_6star.json") as f:
        roster = json.load(f).get("heroes", [])
    named_in_tune = {(s.get("hero") or "").lower()
                     for s in team if not s.get("is_generic")}
    seen = set()
    candidates: List[str] = []
    for h in roster:
        nm = h.get("name", "")
        if not nm or nm.lower() in named_in_tune or nm in seen:
            continue
        seen.add(nm)
        candidates.append(nm)

    # Establish baseline damage with default fillers.
    base = run_potential_team(
        pt, cb_element=cb_element, force_affinity=True, max_cb_turns=50,
        generic_fillers=list(default_fillers), projection=True,
    )
    default_damage = int(base.get("total", 0) or 0) if not base.get("partial_team") else 0

    slots_out = []
    for slot_pos in generic_indices:
        slot_meta = team[slot_pos]
        # Build a candidate list — for slot_pos, swap each owned 6★ in.
        # The other generic slots stay filled by default_fillers (minus
        # any candidate we've placed in slot_pos).
        results: List[dict] = []
        for cand in candidates:
            # Build fillers for this run: candidate goes into slot_pos,
            # other generic slots get the default fillers (excluding cand
            # so we don't double up).
            fill_iter = [n for n in default_fillers if n != cand]
            fillers = []
            fi = iter(fill_iter)
            for j, s in enumerate(team):
                if not s.get("is_generic"):
                    continue
                if j == slot_pos:
                    fillers.append(cand)
                else:
                    fillers.append(next(fi, fill_iter[0] if fill_iter else "Ninja"))
            sim = run_potential_team(
                pt, cb_element=cb_element, force_affinity=True, max_cb_turns=50,
                generic_fillers=fillers, projection=True,
            )
            if sim.get("partial_team") or sim.get("error"):
                continue
            dmg = int(sim.get("total", 0) or 0)
            results.append({
                "hero": cand,
                "damage": dmg,
                "delta": dmg - default_damage,
            })
        results.sort(key=lambda r: -r["damage"])
        slots_out.append({
            "index": slot_meta.get("index"),
            "label": slot_meta.get("hero"),
            "target_speed": slot_meta.get("target_speed"),
            "alternatives": results[:top_n],
        })

    out = {
        "slug": pt.get("tune_slug"),
        "default_damage": default_damage,
        "default_fillers": default_fillers,
        "candidates_considered": len(candidates),
        "slots": slots_out,
    }
    if cache_key:
        cache = _load_cache()
        cache[cache_key] = {"vault_signature": sig, "data": out}
        _save_cache(cache)
    return out
