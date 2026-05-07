#!/usr/bin/env python3
"""Convert DWJ tunes into Raid preset `/update-preset` params for ANY tune.

Raid's Skill Instruction UI only accepts ONE opener (∞) per hero + priority
ranks (1st/2nd/3rd/Default/Don't Use). DWJ's per-skill "Delay N" is mapped
to "opener A1 + rank the delayed skill at position N."

This file provides:
  - role-based delay tables per tune (sourced from DWJ's calculator pages)
  - helpers that look up a user's hero_id and skill_type_ids from /all-heroes
    and /skill-data, then build the `/update-preset` URL
"""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://localhost:6790"
ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
# Per-tune role → per-skill delay map (derived from DWJ calc forms).
# Format: TUNE_ROLE_DELAYS[tune_id][role] = {skill_label: delay_turns}
# skill_label: 'A1' | 'A2' | 'A3' | 'A4'
# The conversion rule (see project memory `project_raid_preset_delays.md`):
#   delay=0 → priority 1 (fires ASAP)
#   delay=1 → priority 1 with A1 opener (fires turn 2)
#   delay=2 → priority 2 (fires turn 3, another skill takes priority 1)
# ============================================================================
TUNE_ROLE_DELAYS = {
    "myth_eater": {
        "fast_uk":      {"A1": 0, "A2": 0, "A3": 1},   # Maneater: A1 opener, A3 pri 1
        "block_damage": {"A1": 0, "A2": 0, "A3": 2},   # Demytha: A1 opener, A2 pri 1, A3 pri 2
        "dps_4to3":     {"A1": 0, "A2": 0, "A3": 1},   # Ninja: A1 opener, A3 pri 1
        "dps_1to1":     {"A1": 0, "A2": 0, "A3": 0},   # free-firing DPS
        "dps_slow":     {"A1": 0, "A2": 0, "A3": 0},
    },
    "budget_uk": {
        "fast_uk":      {"A1": 0, "A2": 0, "A3": 1},   # Maneater 1: A1 then A3
        "slow_uk":      {"A1": 0, "A2": 0, "A3": 1},   # Maneater 2: same
        "dps":          {"A1": 0, "A2": 0, "A3": 0},
        "stun":         {"A1": 0, "A2": 0, "A3": 0},   # slowest; just whatever
    },
    "batman_forever": {
        "fast_uk":            {"A1": 0, "A2": 0, "A3": 1},
        "seeker":             {"A1": 0, "A2": 0},                # Seeker has no A3 delay
        "dps_block_debuff":   {"A1": 0, "A2": 0, "A3": 0},
        "slow_uk":            {"A1": 0, "A2": 0, "A3": 1},
        "dps_cleanse":        {"A1": 0, "A2": 0, "A3": 0},
    },
    "budget_myth_heir": {
        "block_damage":  {"A1": 0, "A2": 0, "A3": 2},    # Demytha (same as Myth Eater)
        "buff_extend":   {"A1": 0, "A2": 1},             # Heiress opens with A2
        "dps":           {"A1": 0, "A2": 0, "A3": 0},
    },
    "myth_salad": {
        "block_damage":  {"A1": 0, "A2": 0, "A3": 2},
        "block_debuff":  {"A1": 0, "A2": 0},
        "seeker":        {"A1": 0, "A2": 0},
        "dps":           {"A1": 0, "A2": 0, "A3": 0},
    },
}


def _fetch_all_heroes():
    r = urllib.request.urlopen(f"{BASE}/all-heroes?page_size=600", timeout=30)
    return json.loads(r.read())["heroes"]


def _hero_by_name(heroes, query):
    aliases = {"me": "maneater", "demy": "demytha", "geo": "geomancer", "ven": "venomage"}
    q = aliases.get(query.lower(), query.lower())
    matches = [h for h in heroes if q in (h.get("name") or "").lower()]
    matches.sort(key=lambda h: (-h.get("grade", 0), -(h.get("level") or 0)))
    return matches[0] if matches else None


def _load_skills_db():
    p = ROOT / "skills_db.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def _skill_ids_for_hero(hero_name, skills_db):
    """Return {'A1': skill_type_id, 'A2': ..., 'A3': ...} for the given hero.

    Picks A1 as the is_a1 skill and A2/A3 as the two active skills sorted by
    cooldown ascending — matching load_game_profiles.py's slot assignment.
    """
    entries = skills_db.get(hero_name, [])
    # Dedupe by skill_type_id (skills_db may list duplicates for doubled heroes)
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
    out = {}
    if a1:
        out["A1"] = a1.get("skill_type_id") or a1.get("id")
    if len(actives) >= 1:
        out["A2"] = actives[0].get("skill_type_id") or actives[0].get("id")
    if len(actives) >= 2:
        out["A3"] = actives[1].get("skill_type_id") or actives[1].get("id")
    if len(actives) >= 3:
        out["A4"] = actives[2].get("skill_type_id") or actives[2].get("id")
    return out


def _hero_settings(skill_delays):
    """Convert {skill_label: delay} to (opener_skill_id, priority_dict).

    Rules (see project memory `project_raid_preset_delays.md`):
      - A1 becomes the Opener iff any skill has delay ≥ 1
      - priority rank = max(1, delay) for explicitly-delayed skills
      - delay-0 skills fill remaining priority slots (A3 preferred over A2)
    """
    needs_opener = any(d >= 1 for d in skill_delays.values())
    opener_label = "A1" if needs_opener else None

    # Build priority assignments. A1 stays Default (0). Rank other actives.
    targets = [(lbl, d) for lbl, d in skill_delays.items() if lbl != "A1"]
    label_order = {"A4": 4, "A3": 3, "A2": 2, "A1": 1}
    targets.sort(key=lambda t: (-t[1], -label_order.get(t[0], 0)))
    used = set()
    pri_by_label = {"A1": 0}
    for lbl, d in targets:
        rank = max(1, d) if d > 0 else 1
        while rank in used:
            rank += 1
        used.add(rank)
        pri_by_label[lbl] = rank
    return opener_label, pri_by_label


def build_update_preset_url(preset_id, team_names, tune_id):
    """Build /update-preset URL for the given tune applied to a team.

    team_names: list of hero names in slot order (5 heroes).
    tune_id: one of the TUNE_ROLE_DELAYS keys.
    Returns (url, breakdown) where breakdown lists per-hero opener+priorities.
    """
    from tune_library import get_tune
    tune = get_tune(tune_id)
    if not tune:
        raise ValueError(f"Unknown tune: {tune_id}")
    role_delays = TUNE_ROLE_DELAYS.get(tune_id)
    if not role_delays:
        raise ValueError(f"No delay map for tune: {tune_id}")

    heroes = _fetch_all_heroes()
    skills_db = _load_skills_db()

    prio_blocks = []
    starter_blocks = []
    breakdown = []
    for i, name in enumerate(team_names):
        hero = _hero_by_name(heroes, name)
        if not hero:
            continue
        hero_id = hero.get("id")
        slot = tune.slots[i] if i < len(tune.slots) else None
        role = slot.role if slot else "dps"
        delays = role_delays.get(role) or {"A1": 0, "A2": 0, "A3": 0}
        skill_ids = _skill_ids_for_hero(hero.get("name"), skills_db)
        if not skill_ids:
            continue
        opener_label, pri_by_label = _hero_settings(delays)
        pri_parts = []
        for lbl, rank in pri_by_label.items():
            sid = skill_ids.get(lbl)
            if sid:
                pri_parts.append(f"{sid}={rank}")
        prio_blocks.append(f"{hero_id}:{','.join(pri_parts)}")
        opener_sid = skill_ids.get(opener_label) if opener_label else None
        starter_blocks.append(f"{hero_id}:{opener_sid}" if opener_sid else f"{hero_id}:")
        breakdown.append({
            "slot": i + 1, "hero": hero.get("name"), "hero_id": hero_id,
            "role": role, "delays": delays, "opener": opener_label,
            "priorities_by_label": pri_by_label,
        })

    priorities_raw = ";".join(prio_blocks)
    starters_raw = ";".join(starter_blocks)
    url = (
        f"{BASE}/update-preset?id={preset_id}"
        f"&priorities={urllib.parse.quote(priorities_raw, safe='')}"
        f"&starters={urllib.parse.quote(starters_raw, safe='')}"
    )
    return url, breakdown


# Backward-compat: Myth Eater with specific hero IDs (our team)
MYTH_EATER_TUNE = {
    15120: {"A1": (10701, 0), "A2": (10702, 0), "A3": (10703, 1)},
    18607: {"A1": (65101, 0), "A2": (65102, 0), "A3": (65103, 2)},
    2643:  {"A1": (62001, 0), "A2": (62002, 0), "A3": (62003, 1)},
    13615: {"A1": (48801, 0), "A2": (48802, 0), "A3": (48804, 0)},
    5692:  {"A1": (62801, 0), "A2": (62802, 0), "A3": (62803, 0)},
}


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python tune_to_preset.py <preset_id> <tune_id> <hero1,hero2,...>")
        print("Available tunes:", ", ".join(TUNE_ROLE_DELAYS.keys()))
        sys.exit(1)
    pid = int(sys.argv[1])
    tune = sys.argv[2]
    team = [n.strip() for n in sys.argv[3].split(",")]
    url, breakdown = build_update_preset_url(pid, team, tune)
    print(json.dumps({"url": url[:200] + "...", "breakdown": breakdown}, indent=2))
    resp = urllib.request.urlopen(url, timeout=30).read().decode()
    print("Response:", resp[:300])
