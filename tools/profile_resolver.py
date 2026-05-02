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


_STATIC_SKILLS_CACHE: dict | None = None
_HERO_TYPES_CACHE: dict | None = None


def _load_static_skills() -> dict:
    """Lazy-load skills_all.json indexed by skill ID."""
    global _STATIC_SKILLS_CACHE
    if _STATIC_SKILLS_CACHE is not None:
        return _STATIC_SKILLS_CACHE
    p = PROJECT_ROOT / "data" / "static" / "skills_all.json"
    if not p.exists():
        _STATIC_SKILLS_CACHE = {}
        return _STATIC_SKILLS_CACHE
    import json
    raw = json.loads(p.read_text(encoding="utf-8"))
    arr = raw.get("data") if isinstance(raw, dict) else raw
    _STATIC_SKILLS_CACHE = {s["Id"]: s for s in (arr or []) if isinstance(s, dict) and "Id" in s}
    return _STATIC_SKILLS_CACHE


def _load_hero_types() -> dict:
    """Lazy-load hero_types.json grouped by canonical hero name."""
    global _HERO_TYPES_CACHE
    if _HERO_TYPES_CACHE is not None:
        return _HERO_TYPES_CACHE
    p = PROJECT_ROOT / "data" / "static" / "hero_types.json"
    if not p.exists():
        _HERO_TYPES_CACHE = {}
        return _HERO_TYPES_CACHE
    import json
    raw = json.loads(p.read_text(encoding="utf-8"))
    rows = raw.get("hero_types") or raw.get("data") or []
    by_name: dict[str, dict] = {}
    for h in rows:
        name = h.get("name") or ""
        if not name:
            continue
        cur = by_name.get(name)
        if cur is None:
            by_name[name] = h
            continue
        # Prefer Legendary + max-ascended record so skill_ids reflect
        # the highest-rarity form (skill IDs are stable but shape may
        # differ for double-ascended heroes).
        cur_score = (cur.get("rarity") == "Legendary", cur.get("is_max_ascended", False))
        new_score = (h.get("rarity") == "Legendary", h.get("is_max_ascended", False))
        if new_score > cur_score:
            by_name[name] = h
    _HERO_TYPES_CACHE = by_name
    return _HERO_TYPES_CACHE


def _parse_damage_formula(formula: str) -> tuple[float, str]:
    """Extract (multiplier, scaling_stat) from a MultiplierFormula like
    '3.1*ATK', 'DEF*1.5', '0.2*HP'. Returns (0.0, 'ATK') if unparsed."""
    if not formula:
        return 0.0, "ATK"
    f = formula.strip()
    # Strip parens and condition suffixes that come after a closing brace.
    # Keep just the leading 'N*STAT' or 'STAT*N' form.
    m = re.match(r"^([\d.]+)\s*\*\s*(ATK|DEF|HP)\b", f)
    if m:
        return float(m.group(1)), m.group(2)
    m = re.match(r"^(ATK|DEF|HP)\s*\*\s*([\d.]+)", f)
    if m:
        return float(m.group(2)), m.group(1)
    m = re.match(r"^(ATK|DEF|HP)\b", f)
    if m:
        return 1.0, m.group(1)
    return 0.0, "ATK"


def _extract_static_skill_shape(skill: dict) -> dict:
    """Pull mult/stat/hits from a skills_all.json record's Effects[].

    Returns a dict with mult/stat/hits/cd/group fields. Missing fields
    default to ATK / 0 / 1 / cooldown=as-given. Multi-hit damage skills
    sum their per-effect multipliers (e.g. Ninja A2's 3 separate
    Damage effects each '2*ATK' = mult=6.0, hits=3).
    """
    eff_list = skill.get("Effects") or []
    cd = int(skill.get("Cooldown") or 0)
    group = skill.get("Group") or ""
    dmg_effects = [e for e in eff_list if e.get("KindId") == "Damage"]

    total_mult = 0.0
    primary_stat = "ATK"
    total_hits = 0
    for e in dmg_effects:
        m, s = _parse_damage_formula(e.get("MultiplierFormula") or "")
        cnt = int(e.get("Count") or 1)
        if m > 0:
            total_mult += m * cnt
            primary_stat = s
        total_hits += cnt
    if not dmg_effects:
        total_hits = 1  # placeholder for non-damage skills

    return {
        "mult": total_mult,
        "stat": primary_stat,
        "hits": max(1, total_hits),
        "cd": cd,
        "group": group,
        "raw": skill,  # keep full record for downstream parsers
    }


def _categorize_static_skills(skill_records: list[dict]) -> dict:
    """Split a hero's skill records into A1/A2/A3 labels.

    Mirrors load_game_profiles' categorization: A1 = first cooldown-0
    Active skill, A2/A3 = next two Actives sorted by cooldown.
    Passives are returned under '_passives' for the caller to handle.
    """
    actives = []
    passives = []
    for sk in skill_records:
        shape = _extract_static_skill_shape(sk)
        if shape["group"] == "Active":
            actives.append(shape)
        elif shape["group"] == "Passive":
            passives.append(shape)
    actives.sort(key=lambda s: (s["cd"], s["raw"].get("Id", 0)))
    out: dict = {"_passives": passives}
    if actives:
        # First Active with cooldown==0 is A1; otherwise just first Active.
        a1 = next((a for a in actives if a["cd"] == 0), actives[0])
        actives.remove(a1)
        out["A1"] = a1
    if actives:
        out["A2"] = actives[0]
    if len(actives) > 1:
        out["A3"] = actives[1]
    return out


def derive_skill_data_from_desc(parsed_kit: dict, hero_name: str | None = None) -> tuple[dict, dict]:
    """Convert a desc_profiler hero kit into (skill_data, skill_effects).

    Output shape matches `load_game_profiles.load_profiles()` so
    cb_sim's existing consumers don't need to change. Damage
    multipliers come from skills_all.json Effects[] when available
    (Phase 4 follow-up landed); buff/debuff modeling continues to
    flow from desc text.

    Args:
        parsed_kit: desc_profiler output for this hero (A1/A2/A3 dicts).
        hero_name: canonical hero name. When provided, the function
            looks up the hero in hero_types.json + skills_all.json to
            extract exact damage multipliers / hits / cooldowns. Falls
            back to DEFAULT_SKILL_DATA values when missing.

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

    # If we have the canonical hero name, overlay structured Effects[]
    # data from skills_all.json — exact damage multipliers / hits /
    # cooldowns for unowned heroes. Missing data falls through to
    # DEFAULT_SKILL_DATA values so the path stays safe even when
    # static data hasn't been refreshed.
    static_by_label: dict = {}
    if hero_name:
        ht = _load_hero_types().get(hero_name)
        if ht and ht.get("skill_ids"):
            sk_idx = _load_static_skills()
            sk_records = [sk_idx[sid] for sid in ht["skill_ids"] if sid in sk_idx]
            static_by_label = _categorize_static_skills(sk_records)

    for label in ("A1", "A2", "A3"):
        p = parsed_kit.get(label)
        if not p:
            continue

        defaults = _DEFAULTS[label]
        # Prefer static-derived values when present; fall back to defaults.
        st = static_by_label.get(label) if static_by_label else None
        if st:
            mult = st["mult"] if st["mult"] > 0 else defaults["mult"]
            stat = st["stat"]
            hits = int(p.get("hits") or st["hits"])
            cd = st["cd"]
        else:
            mult = defaults["mult"]
            stat = defaults["stat"]
            hits = int(p.get("hits") or defaults["hits"])
            cd = defaults["cd"]
        sd_entry = {
            "mult": mult,
            "stat": stat,
            "hits": hits,
            "cd": cd,
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


def derive_from_static_only(hero_name: str) -> tuple[dict, dict]:
    """Build a skill_data + skill_effects entry from `hero_types.json`
    × `skills_all.json` alone, without skill description text.

    Used for heroes the localization dump doesn't cover (e.g. recently
    added or unreleased). Effects[] gives us damage shape (mult, hits,
    cd, group) directly from game data — buff/debuff *placement chance
    and type* are NOT in the static dump (Chance / TargetParams come
    back as `<Nullable>` / `<TargetParams>` placeholders), so the entry
    only carries direct-damage shape. Sufficient for team-search /
    DPS scoring; debuff modeling for these heroes is best-effort.

    Returns ({}, {}) when the hero has no resolvable skill records.
    """
    ht = _load_hero_types().get(hero_name)
    if not ht or not ht.get("skill_ids"):
        return {}, {}
    sk_idx = _load_static_skills()
    sk_records = [sk_idx[sid] for sid in ht["skill_ids"] if sid in sk_idx]
    if not sk_records:
        return {}, {}
    by_label = _categorize_static_skills(sk_records)

    sd: dict = {}
    eff: dict = {}
    for label in ("A1", "A2", "A3"):
        st = by_label.get(label)
        if not st:
            continue
        sd[label] = {
            "mult": st["mult"],
            "stat": st["stat"],
            "hits": st["hits"],
            "cd": st["cd"],
            "team_buffs": [],
            "team_tm_fill": 0.0,
            "self_tm_fill": 0.0,
            "grants_extra_turn": False,
        }
        eff[label] = []
    return sd, eff


def augment_with_unowned(skill_data: dict, skill_effects: dict, *,
                         passive_data: Optional[dict] = None) -> tuple[int, int]:
    """Mutate `skill_data` and `skill_effects` in place to add entries
    for heroes not already covered.

    Two passes, lower-precision-first:
      1. desc-text derivation (mult/hits from Effects[] + buffs/debuffs
         from desc text) — covers heroes whose names appear in the
         static skill_descriptions dump.
      2. static-data-only fallback for heroes the desc dump misses —
         pulls damage shape from `hero_types.json` × `skills_all.json`
         Effects[] directly. Buff/debuff modeling is empty until the
         mod's static export grows to include Chance + TargetParams.

    Owned heroes (already keys in `skill_data`) are NOT touched —
    their book-aware structured profiles take precedence.

    Returns:
        (added, total_with_data) tuple — useful for one-line logging.
    """
    added = 0

    # Pass 1: desc-text derivation.
    try:
        from desc_profiler import parse_all_descriptions
        parsed = parse_all_descriptions()
        for hero_name, kit in parsed.items():
            if hero_name in skill_data:
                continue
            sd_entry, eff_entry = derive_skill_data_from_desc(kit, hero_name=hero_name)
            if not sd_entry:
                continue
            skill_data[hero_name] = sd_entry
            skill_effects[hero_name] = eff_entry
            added += 1
    except ImportError:
        pass

    # Pass 2: static-data-only fallback for heroes still uncovered.
    for hero_name in _load_hero_types():
        if hero_name in skill_data:
            continue
        sd_entry, eff_entry = derive_from_static_only(hero_name)
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
