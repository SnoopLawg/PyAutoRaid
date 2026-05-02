"""Read saved game presets and produce per-hero opener + skill priority.

The mod's `/presets` endpoint exposes the user's saved preset slots
(15 max). Each preset has, per round, per hero:
  - StarterSkillIds (forced opener)
  - PriorityBySkillId (relative skill ordering)

These translate directly into `cb_sim.SimChampion.opening` and
`SimChampion.skill_priority`. Loading them lets the sim follow the
exact tune the user has saved in-game — no hardcoded if-hero branches.

Usage:
    from preset_loader import load_preset_for_team
    plan = load_preset_for_team(["Maneater","Demytha","Ninja","Geomancer","Venomage"])
    # plan = {"Demytha": {"opening": ["A1"], "priority": ["A2","A1","A3"]}, ...}

Falls back to (no opening, no priority) when no preset matches the team
or when the live mod isn't reachable. Supplemental, not required.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Preset `type` field values in Plarium's enum aren't strictly tied to
# location — type=1 holds the user's flagship CB team, type=7 holds an
# alternate "fast" preset, etc. Don't filter by type; match by hero set
# + prefer the preset with the most explicit priorities (i.e. an actual
# tune, not a default-everything slot).
CB_PRESET_TYPE = None  # kept for backwards-compat; ignored when None


def _fetch_presets(host: str = "localhost:6790",
                   timeout: float = 10.0) -> Optional[list[dict]]:
    """Fetch from live mod, fall back to local cache file."""
    try:
        with urllib.request.urlopen(
                f"http://{host}/presets", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data.get("presets") if isinstance(data, dict) else data
    except Exception:
        cache = PROJECT_ROOT / "presets.json"
        if cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
                return data.get("presets") if isinstance(data, dict) else data
            except Exception:
                return None
    return None


def _hero_id_to_name_map() -> dict[int, str]:
    """Build {hero_id: name} from heroes_all.json or heroes_6star.json."""
    for fname in ("heroes_all.json", "heroes_6star.json"):
        p = PROJECT_ROOT / fname
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            heroes = d.get("heroes", d) if isinstance(d, dict) else d
            return {h["id"]: h["name"] for h in heroes
                    if isinstance(h, dict) and "id" in h and "name" in h}
        except Exception:
            continue
    return {}


_SKILLS_DB_CACHE: Optional[dict[str, list]] = None


def _skills_db() -> dict[str, list]:
    """Load skills_db.json (per-hero skill metadata with is_a1, cooldown)."""
    global _SKILLS_DB_CACHE
    if _SKILLS_DB_CACHE is not None:
        return _SKILLS_DB_CACHE
    p = PROJECT_ROOT / "skills_db.json"
    if not p.exists():
        _SKILLS_DB_CACHE = {}
        return _SKILLS_DB_CACHE
    try:
        _SKILLS_DB_CACHE = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        _SKILLS_DB_CACHE = {}
    return _SKILLS_DB_CACHE


def _skill_label_for_hero(hero_name: str, skill_id: int) -> str:
    """Map a skill_type_id → "A1"/"A2"/"A3"/"Passive" via skills_db.json.

    skills_db.json keys are hero names; values are lists of skill dicts
    with `skill_type_id`, `is_a1`, `cooldown`. A1 is the always-on auto;
    actives are sorted by cooldown ascending (A2=lowest CD, A3=next).
    """
    db = _skills_db()
    skills = db.get(hero_name) or []
    a1_id = None
    actives: list[tuple[int, int]] = []
    passives: set[int] = set()
    seen_ids: set[int] = set()
    for s in skills:
        sid = s.get("skill_type_id") or s.get("id")
        if sid is None or sid in seen_ids:
            continue
        seen_ids.add(sid)
        if s.get("is_a1"):
            a1_id = sid
        elif s.get("cooldown") is not None:
            actives.append((sid, s.get("cooldown") or 99))
        else:
            passives.add(sid)
    if a1_id == skill_id:
        return "A1"
    if skill_id in passives:
        return "Passive"
    actives.sort(key=lambda x: x[1])
    for idx, (sid, _cd) in enumerate(actives):
        if sid == skill_id:
            return f"A{idx + 2}"
    return ""


def load_preset_for_team(team_names: list[str],
                         preset_id: Optional[int] = None,
                         preset_type: Optional[int] = None) -> dict[str, dict]:
    """Find a saved preset matching `team_names` and translate to per-hero plan.

    Returns a dict `{hero_name: {"opening": [labels], "priority": [labels],
                                  "delays": {label: int}}}`
    suitable to apply onto `SimChampion.opening` / `skill_priority` /
    `SimSkill.delay_turns`.

    Args:
        team_names: heroes in slot order (the leader is team_names[0]).
        preset_id: optionally pin to a specific preset id.
        preset_type: optional filter on preset type.

    Match precedence (when preset_id is None):
      1. Among presets whose hero set ⊇ team_names, prefer the one with
         the most non-zero priorities AND the most explicit starters
         (i.e. an actual tune, not a default-everything slot).
      2. Tie-break by lowest preset id (oldest user save wins).

    Heroes not present in the preset return an empty entry.
    """
    presets = _fetch_presets() or []
    id_to_name = _hero_id_to_name_map()
    name_set = set(team_names)

    def _signal(preset: dict) -> tuple[int, int, int]:
        """How 'tuned' is this preset — count non-zero prios + starters."""
        starters = 0
        prios_set = 0
        for h in preset.get("heroes") or []:
            for r in h.get("rounds") or []:
                if r.get("starter_ids"):
                    starters += 1
                for v in (r.get("priorities") or {}).values():
                    if isinstance(v, int) and v > 0:
                        prios_set += 1
        return (starters + prios_set, starters, prios_set)

    candidates: list[tuple[tuple[int, int, int], int, dict]] = []
    for p in presets:
        if p.get("empty"):
            continue
        if preset_id is not None and p.get("id") != preset_id:
            continue
        if preset_type is not None and p.get("type") != preset_type:
            continue
        preset_names = {id_to_name.get(h.get("hero_id"))
                        for h in p.get("heroes") or []}
        preset_names.discard(None)
        if not name_set.issubset(preset_names):
            continue
        candidates.append((_signal(p), p.get("id", 0), p))
    if not candidates:
        return {}
    # Pick highest tuned-signal, lowest id as tie-break.
    candidates.sort(key=lambda x: (-x[0][0], -x[0][1], -x[0][2], x[1]))
    chosen = candidates[0][2]

    plan: dict[str, dict] = {}
    for h_entry in chosen.get("heroes") or []:
        hid = h_entry.get("hero_id")
        name = id_to_name.get(hid)
        if not name or name not in name_set:
            continue
        rounds = h_entry.get("rounds") or []
        if not rounds:
            continue
        r0 = rounds[0]  # CB has 1 round
        starters = r0.get("starter_ids") or []
        prios = r0.get("priorities") or {}

        opening = []
        for sid in starters:
            label = _skill_label_for_hero(name, int(sid))
            if label:
                opening.append(label)

        # `priorities` is {skill_id_str: int}. The Plarium UI is
        # OPPOSITE to DWJ: in-game "1st priority" = LOWER NUMBER.
        # priority 0 = "default / unranked, falls through". Higher
        # numbers > 0 mean LOWER priority in the queue.
        # The DWJ "delay" mechanic is achieved IN-GAME via opener +
        # priority workaround: opener A1 + priority A2 = "fire A1
        # first (opener), then A2 (UI priority 1), naturally A3
        # last (UI priority 2 = lower in queue) — equivalent to
        # DWJ's `A3 d2` (A3 delayed to 3rd cast).
        prio_pairs: list[tuple[str, int, int]] = []  # (label, prio, default_idx)
        seen_labels: set[str] = set()
        for sid_str in prios.keys():
            try:
                sid_int = int(sid_str)
            except (TypeError, ValueError):
                continue
            label = _skill_label_for_hero(name, sid_int)
            if not label or label == "Passive":
                continue
            if label not in seen_labels:
                seen_labels.add(label)
                # Default-AI tiebreaker: A2 < A3 < A1 by ascending CD.
                # Used when priority ties (both 0 / both unranked).
                default_idx = (
                    0 if label == "A2"
                    else 1 if label == "A3"
                    else 2 if label == "A1"
                    else 3
                )
                prio_pairs.append((
                    label,
                    int(prios[sid_str]) if prios[sid_str] is not None else 0,
                    default_idx,
                ))
        # Sort: lowest priority number first (UI's "1st priority"),
        # then 2, 3 ... and unranked (priority 0) AFTER all explicit
        # rankings, by default_idx (A2 → A3 → A1 by ascending CD).
        # priority 0 sorts to the end since it means "no rank, default".
        BIG = 999
        prio_pairs.sort(key=lambda x: (x[1] if x[1] > 0 else BIG, x[2]))
        priority = [lbl for lbl, _p, _d in prio_pairs]

        plan[name] = {"opening": opening, "priority": priority}

    return plan


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--team", required=True,
                    help="Comma-separated hero names")
    ap.add_argument("--preset-id", type=int, default=None)
    ap.add_argument("--preset-type", type=int, default=CB_PRESET_TYPE)
    args = ap.parse_args()
    team = [n.strip() for n in args.team.split(",") if n.strip()]
    plan = load_preset_for_team(team, args.preset_id, args.preset_type)
    if not plan:
        print(f"no matching preset found (type={args.preset_type})")
        return 1
    for name in team:
        info = plan.get(name, {})
        print(f"  {name}: opening={info.get('opening', [])} "
              f"priority={info.get('priority', [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
