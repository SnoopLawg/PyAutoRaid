"""Unified hero profile resolver.

Single answer to "what does this hero's kit look like for the sim?"
Sources, in priority order (highest wins):

1. **Hand-curated overrides** — `cb_profiles.PROFILES` (51 heroes,
   CB-tuned scoring data). Today these are CB-specific knobs
   (poisons_per_turn, hp_burn_uptime, breaks_speed_tune) — separate
   from the simulation skill data, so they augment rather than replace.

2. **Owned-hero structured data** — `hero_profiles_game.json` via
   `load_game_profiles.load_profiles()`. 317 heroes the user owns,
   with book-aware cooldowns + multipliers + status effects extracted
   from the live mod's /skill-data endpoint.

3. **Static-text auto-derived** — `desc_profiler.parse_all_descriptions()`
   parses skill localization (the 2560-entry static dump from Phase 2)
   into the same structured kit shape. Covers all 1121 heroes the game
   knows about. Less precise than #2 because base descriptions don't
   reflect book upgrades.

4. **Generic fallback** — `cb_sim.DEFAULT_SKILL_DATA` (A1×3.5 mult,
   A2 4.0/CD4, A3 unused). Final safety net for heroes still not
   resolved.

The resolver is consumed by `cb_sim.SKILL_DATA` lookup (and adjacent
SKILL_EFFECTS / PASSIVE_DATA). Owned heroes go through the full
load_profiles pipeline (with desc auto-correction and per-hero fixes);
unowned heroes get a desc-derived stub. Either way, cb_sim.py's
existing DEFAULT_SKILL_DATA fallback at line 1552 remains as the
ultimate floor.

This module is *additive* — it does not modify the existing
load_profiles output for owned heroes. Existing CB calibration is
preserved.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Status-effect-name → sim debuff/buff name. Matches the SE_TO_SIM
# table in load_game_profiles for consistency. Used to translate
# desc_profiler's debuff/buff types (already normalized) into entries
# the sim's buff/debuff bar understands.
_DESC_BUFF_KEEP = {
    "atk_up", "inc_def", "inc_spd", "inc_cr_30", "inc_cd_30",
    "counterattack", "block_damage", "block_debuffs", "ally_protect",
    "unkillable", "shield", "cont_heal_15", "perfect_veil", "veil",
    "reflect_damage", "revive_on_death", "strengthen", "inc_acc",
    "inc_res",
}

_DESC_DEBUFF_KEEP = {
    "poison_5pct", "hp_burn", "def_down", "dec_atk", "dec_spd",
    "dec_cr", "weaken", "leech", "heal_reduction",
    "poison_sensitivity", "block_buffs", "stun", "freeze", "sleep",
    "provoke", "fear", "true_fear", "hex", "block_revive", "bomb",
}


def derive_skill_data_from_desc(parsed_kit: dict) -> tuple[dict, dict]:
    """Convert a desc_profiler hero kit into (skill_data, skill_effects).

    Output shape matches `load_game_profiles.load_profiles()` so
    cb_sim's existing consumers don't need to change. Multipliers
    fall back to DEFAULT_SKILL_DATA values since static descriptions
    don't expose them — the auto-parsed profile is a partial kit, not
    a full damage spec.

    Returns:
        (hero_skill_data, hero_skill_effects) — both dicts keyed by
        skill label ("A1", "A2", "A3"). Empty dicts when nothing
        parseable.
    """
    sd: dict = {}
    eff: dict = {}
    if not parsed_kit:
        return sd, eff

    # Sensible defaults for skill-shape fields the desc parser doesn't
    # surface. cb_sim already has DEFAULT_SKILL_DATA with the same
    # values; mirroring them keeps the new entries identical to the
    # generic fallback for the unmodelable fields, while letting the
    # desc-derived debuffs/buffs show up.
    _DEFAULTS = {
        "A1": {"mult": 3.5, "stat": "ATK", "hits": 1, "cd": 0},
        "A2": {"mult": 4.0, "stat": "ATK", "hits": 1, "cd": 4},
        "A3": {"mult": 0.0, "stat": "ATK", "hits": 0, "cd": 5},
    }

    for label in ("A1", "A2", "A3"):
        p = parsed_kit.get(label)
        if not p:
            continue

        defaults = _DEFAULTS[label]
        sd_entry = {
            "mult": defaults["mult"],
            "stat": defaults["stat"],
            "hits": int(p.get("hits") or defaults["hits"]),
            "cd": defaults["cd"],
            "team_buffs": [],
            "team_tm_fill": float(p.get("tm_fill_team", 0) or 0),
            "self_tm_fill": float(p.get("tm_fill_self", 0) or 0),
            "grants_extra_turn": bool(p.get("extra_turn")),
        }
        ig = float(p.get("ignore_def_pct", 0) or 0)
        if ig > 0:
            sd_entry["ignore_def"] = ig

        # Team buffs from desc parser (non-self only).
        for buf in p.get("buffs") or []:
            if buf.get("target") == "self":
                continue
            t = buf.get("type")
            if t in _DESC_BUFF_KEEP:
                sd_entry["team_buffs"].append((t, int(buf.get("duration") or 2)))

        # Skill-effects list: debuff placements only (buff placements
        # live on sd_entry.team_buffs already).
        eff_list: list = []
        for db in p.get("debuffs") or []:
            if db.get("on_self"):
                continue
            t = db.get("type")
            if t not in _DESC_DEBUFF_KEEP:
                continue
            eff_list.append({
                "effect_type": "debuff",
                "params": {
                    "debuff": t,
                    "duration": int(db.get("duration") or 2),
                    "chance": float(db.get("chance") or 1.0),
                },
            })

        # Activate / extend / ally-attack flags map to effect_type strings
        # that cb_sim recognizes (per load_game_profiles _eff() helpers).
        if p.get("activate_burns"):
            eff_list.append({"effect_type": "activate_hp_burns", "params": {}})
        if p.get("activate_poisons"):
            eff_list.append({"effect_type": "activate_poisons",
                             "params": {"max_count": 2}})
        if p.get("activate_dots"):
            eff_list.append({"effect_type": "activate_dots", "params": {}})
        if p.get("ally_attack"):
            eff_list.append({"effect_type": "ally_attack",
                             "params": {"count": 4}})
        ext = p.get("extend_debuffs")
        if ext == "hp_burn":
            eff_list.append({"effect_type": "extend_debuffs_hp_burn",
                             "params": {"turns": 1, "per_hit": p.get("hits", 1) > 1}})
        elif ext == "poison_burn":
            eff_list.append({"effect_type": "extend_debuffs_poison_burn",
                             "params": {"turns": 1}})
        elif ext == "all":
            eff_list.append({"effect_type": "extend_debuffs",
                             "params": {"turns": 1, "per_hit": p.get("hits", 1) > 1}})

        sd[label] = sd_entry
        eff[label] = eff_list

    return sd, eff


def augment_with_unowned(skill_data: dict, skill_effects: dict, *,
                         passive_data: Optional[dict] = None) -> tuple[int, int]:
    """Mutate `skill_data` and `skill_effects` in place to add entries
    for heroes not already covered. Source: desc_profiler over the
    static-text dump (covers all 1121 heroes).

    Owned heroes (already keys in `skill_data`) are NOT touched —
    their book-aware structured profiles take precedence.

    Returns:
        (added, total_with_data) tuple — useful for one-line logging.
    """
    try:
        from desc_profiler import parse_all_descriptions
    except ImportError:
        return 0, len(skill_data)

    parsed = parse_all_descriptions()
    added = 0
    for hero_name, kit in parsed.items():
        if hero_name in skill_data:
            continue  # Owned + structured wins.
        sd_entry, eff_entry = derive_skill_data_from_desc(kit)
        if not sd_entry:
            continue
        skill_data[hero_name] = sd_entry
        skill_effects[hero_name] = eff_entry
        added += 1
    return added, len(skill_data)


if __name__ == "__main__":
    # Quick CLI to inspect what the resolver produces for a hero.
    import argparse
    import sys

    ap = argparse.ArgumentParser(
        description="Inspect the unified hero profile resolver output.")
    ap.add_argument("hero", help="Hero name (case-insensitive substring).")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from load_game_profiles import load_profiles
    except Exception as e:
        print(f"ERR loading owned profiles: {e}", file=sys.stderr)
        sys.exit(1)
    sd, se, pd = load_profiles()
    pre = len(sd)
    added, total = augment_with_unowned(sd, se, passive_data=pd)
    print(f"owned heroes: {pre}; +{added} desc-derived; total: {total}")

    matches = [n for n in sd if args.hero.lower() in n.lower()]
    if not matches:
        print(f"no hero matching {args.hero!r}", file=sys.stderr)
        sys.exit(1)
    matches.sort(key=lambda n: (args.hero.lower() != n.lower(), len(n)))
    name = matches[0]
    src = "desc-derived (unowned)" if name in se and not pd.get(name) else "owned (book-aware)"
    print(f"\n=== {name} ({src}) ===")
    for label in ("A1", "A2", "A3"):
        s = sd[name].get(label)
        if not s:
            continue
        print(f"  {label}: mult={s.get('mult','-')}x{s.get('stat','-')} "
              f"hits={s.get('hits','-')} cd={s.get('cd','-')}")
        for tb in s.get("team_buffs") or []:
            print(f"    team_buff: {tb}")
        if s.get("ignore_def"):
            print(f"    ignore_def: {s['ignore_def']*100:.0f}%")
        if s.get("grants_extra_turn"):
            print(f"    extra_turn")
        for e in se.get(name, {}).get(label, []) or []:
            params = e.get("params") or {}
            print(f"    effect: {e.get('effect_type')} {params}")
