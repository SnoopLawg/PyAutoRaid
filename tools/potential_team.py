#!/usr/bin/env python3
"""
PotentialTeam — Phase 1 of the CB-sim plan (docs/cb_sim_plan.md).

Per DWJ tune, resolves the concrete team from the matching calc variant,
checks blockers (hero ownership + gear feasibility), enumerates todos
(ascend / book / mastery / blessing), and — if blockers cleared —
materializes the team + preset spec ready for the sim re-driver.

This module is the single place tune-related questions get answered:
  - "Can I run this tune?"  → blockers list
  - "What do I need to do?"  → todos list
  - "What does the team look like?"  → potential_team
  - "What preset should I use?"  → preset (driven by calc_variant skill_configs)

Phase 1 ships blocker / todo detection + the structural shape with stub
gear/mastery/blessing fields. Phase 2 will replace stubs with real
optimizer output and game-truth mastery/blessing data.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

HEROES_ALL = PROJECT_ROOT / "heroes_all.json"
ARTIFACTS_ALL = PROJECT_ROOT / "all_artifacts.json"
DWJ_TUNES = PROJECT_ROOT / "data" / "dwj" / "parsed" / "tunes.json"
DWJ_CALC_TUNES = PROJECT_ROOT / "data" / "dwj" / "parsed" / "calc_tunes.json"
HH_CHAMPIONS = PROJECT_ROOT / "data" / "hh" / "parsed" / "champions.json"
SKILLS_DB = PROJECT_ROOT / "skills_db.json"


# Generic placeholder names that show up in DWJ data but don't pin a
# specific hero. When a tune's calc variant uses these, the slot is
# treated as a flex-DPS that any owned attacker can fill.
_GENERIC_HERO_TOKENS = {
    "dps", "1:1 dps", "4:3 dps", "1:1 dps 1", "1:1 dps 2",
    "block debuff", "block debuffs", "cleanser", "stun target",
    "counterattacker", "speed booster", "slowboi", "warboy",
    "fast maneater", "slow maneater", "maneater (fast)", "maneater (slow)",
    "dps / cleanser", "dps / block debuff",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _is_generic_hero_name(name: str) -> bool:
    if not name:
        return True
    return name.strip().lower() in _GENERIC_HERO_TOKENS


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_data() -> dict:
    """Pull every source the constructor needs into one dict so callers
    can pass it around without re-parsing files. Also makes testing
    easier (inject mocks for any field).
    """
    return {
        "tunes": _load_json(DWJ_TUNES) if DWJ_TUNES.exists() else [],
        "calc_variants": _load_json(DWJ_CALC_TUNES) if DWJ_CALC_TUNES.exists() else {},
        "heroes": _load_json(HEROES_ALL).get("heroes", []) if HEROES_ALL.exists() else [],
        "artifacts": _load_json(ARTIFACTS_ALL).get("artifacts", []) if ARTIFACTS_ALL.exists() else [],
        "hh_champions": _load_json(HH_CHAMPIONS) if HH_CHAMPIONS.exists() else [],
        "skills_db": _load_json(SKILLS_DB) if SKILLS_DB.exists() else {},
    }


def _index_roster(heroes: list[dict]) -> dict[str, dict]:
    """Return {norm_name: best_grade_hero}. Best = highest (grade, level, empower)."""
    out: dict[str, dict] = {}
    for h in heroes:
        nm = h.get("name") or ""
        key = _norm(nm)
        if not key:
            continue
        prev = out.get(key)
        rank = (h.get("grade", 0), h.get("level", 0), h.get("empower", 0))
        prev_rank = (prev.get("grade", 0), prev.get("level", 0), prev.get("empower", 0)) if prev else (-1, -1, -1)
        if rank > prev_rank:
            out[key] = h
    return out


def _index_hh(hh: list[dict]) -> dict[str, dict]:
    """{norm_name: hh_champion} for HH-recommended sets/stats/masteries/blessings."""
    return {_norm(c.get("name") or ""): c for c in hh if c.get("name")}


def pick_calc_variant(tune: dict, calc_variants: dict, today_affinity: str | None = None) -> Optional[dict]:
    """Pick the most relevant calc variant for a tune.

    Preference: variant whose boss affinity matches today's CB > Ultimate
    Nightmare > Nightmare > Brutal > first available.
    """
    links = tune.get("calculator_links") or []
    if not links:
        return None
    candidates = []
    for c in links:
        v = calc_variants.get(c.get("hash"))
        if v and v.get("champions"):
            candidates.append((c, v))
    if not candidates:
        return None

    def _rank(pair):
        c, v = pair
        nm = (c.get("name") or "").lower()
        aff = (v.get("clanboss") or {}).get("affinity") or ""
        # Lower number = better. Prefer affinity match, then UNM, NM, Brutal.
        if today_affinity and today_affinity.lower() == aff.lower():
            return (0, 0)
        if "ultra" in nm or "ultimate" in nm:
            return (1, 0)
        if "nightmare" in nm:
            return (1, 1)
        if "brutal" in nm:
            return (1, 2)
        return (1, 3)

    candidates.sort(key=_rank)
    return candidates[0][1]


def _resolve_team(tune: dict, calc_variant: dict) -> list[dict]:
    """Walk the calc variant's champions in order and produce the team.

    Each entry has {index, name, target_speed, is_generic}. is_generic=True
    means the slot is a DPS placeholder — the caller can fill from the
    owned roster, not gate as missing.
    """
    out = []
    for i, c in enumerate(calc_variant.get("champions") or [], 1):
        nm = c.get("name") or ""
        out.append({
            "index": i,
            "name": nm,
            "target_speed": c.get("total_speed"),
            "base_speed": c.get("base_speed"),
            "is_generic": _is_generic_hero_name(nm),
            "skill_configs": c.get("skillConfigs") or [],
            "has_lore_of_steel": c.get("has_lore_of_steel"),
        })
    return out


def _check_ownership(team: list[dict], roster: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Return (blockers, ownership_meta).

    blockers: missing_hero entries.
    ownership_meta: per-team-slot owned-hero record (None for generic / missing).
    """
    blockers = []
    meta = []
    for slot in team:
        if slot["is_generic"]:
            meta.append(None)
            continue
        owned = roster.get(_norm(slot["name"]))
        if owned is None:
            blockers.append({"kind": "missing_hero", "hero": slot["name"]})
            meta.append(None)
            continue
        meta.append(owned)
    return blockers, meta


def _check_gear_feasibility(team: list[dict], ownership: list[dict | None],
                             artifacts: list[dict]) -> list[dict]:
    """Phase 1 stub: returns no gear blockers. Real implementation will
    call gear_optimizer to test if each hero's target_speed is achievable
    from the current artifact pool.

    We surface a placeholder warning if SPD-primary boots count is fewer
    than the team has SPD-primary boot needs — the cheapest possible
    "your vault is too thin" check.
    """
    needs_spd_boots = sum(1 for slot, owned in zip(team, ownership)
                          if owned is not None and not slot["is_generic"]
                          and (slot.get("target_speed") or 0) >= 200)
    have_spd_boots = sum(1 for a in artifacts
                         if a.get("slot") == 4
                         and (a.get("rarity") or 0) >= 4
                         and ((a.get("primary") or {}).get("stat") == 4))
    if needs_spd_boots > have_spd_boots:
        # Warning, not blocker — gearing can sometimes substitute non-SPD-boots
        # via heavy substat rolls. Real optimizer in phase 2 confirms.
        return [{
            "kind": "thin_vault_warning",
            "detail": f"team needs {needs_spd_boots} SPD-primary epic+ boots, vault has {have_spd_boots}",
        }]
    return []


def _build_skill_max_lookup(skills_db: dict) -> dict[int, int]:
    """skill_type_id → max_level (1 + count of level_bonuses).

    Game-truth source: skills_db's `level_bonuses` list grows with each
    book applied. A skill at level 5 + 4 entries = max level 5 (no books
    available). A skill at 1 + 4 entries = max 5, current 1, needs 4 books.
    """
    out = {}
    for hero_skills in skills_db.values():
        if not isinstance(hero_skills, list):
            continue
        for sk in hero_skills:
            if not isinstance(sk, dict):
                continue
            sid = sk.get("type_id") or sk.get("skill_type_id")
            if sid is None:
                continue
            bonuses = sk.get("level_bonuses") or []
            # max_level = 1 + number of bonuses you can apply.
            out[sid] = 1 + len(bonuses)
    return out


def _enumerate_todos(team: list[dict], ownership: list[dict | None],
                     hh_idx: dict[str, dict], skills_db: dict) -> list[dict]:
    """Per-hero todo list: ascend / book / mastery / blessing."""
    skill_max = _build_skill_max_lookup(skills_db)
    todos = []
    for slot, owned in zip(team, ownership):
        if owned is None:
            continue
        nm = slot["name"]
        # Ascend
        grade = owned.get("grade", 0) or 0
        if grade < 6:
            todos.append({
                "kind": "ascend", "hero": nm,
                "current_grade": grade, "target_grade": 6,
            })
        # Skills booked? Compare each owned skill's current level vs max.
        owned_skills = owned.get("skills") or []
        for sk in owned_skills:
            sid = sk.get("type_id") or sk.get("skill_type_id")
            cur = sk.get("level") or 1
            mx = skill_max.get(sid, 1)
            if cur < mx:
                todos.append({
                    "kind": "book", "hero": nm,
                    "skill_id": sid, "current_lvl": cur, "max_lvl": mx,
                    "books_needed": mx - cur,
                })
        # Mastery — flag if the hero has 0 masteries trained.
        # Real game data: count trained masteries per tree from /mastery-data.
        # Phase 1 just flags absence of the field.
        mtotal = owned.get("mastery_count") or 0
        if mtotal < 15:
            todos.append({
                "kind": "mastery", "hero": nm,
                "current_count": mtotal, "target_count": 15,
                "recommended": (hh_idx.get(_norm(nm)) or {}).get("masteries"),
            })
        # Blessing
        if not owned.get("blessing"):
            todos.append({
                "kind": "blessing", "hero": nm,
                "recommended": (hh_idx.get(_norm(nm)) or {}).get("blessings"),
            })
    return todos


def _build_preset_from_calc(team: list[dict]) -> dict:
    """Convert each team slot's calc skill_configs into a preset entry.

    DWJ skill_configs shape: [{"alias": "A1", "priority": 1, "delay": 0,
    "cooldown": 0, "id": "A1"}, ...].

    Output convention used elsewhere in this repo (memory
    project_raid_preset_delays): opener = "A1" (single-skill opener
    always); priorities ranked by priority field; delay carried through.
    """
    preset = {}
    for slot in team:
        if slot["is_generic"]:
            continue
        cfgs = slot.get("skill_configs") or []
        opener = "A1"
        priorities = []
        # Skip A1 in priorities (it's the default fallback opener);
        # take A2/A3/A4 sorted by priority.
        for cfg in sorted(cfgs, key=lambda x: x.get("priority", 99)):
            alias = cfg.get("alias") or cfg.get("id")
            if alias == "A1":
                continue
            priorities.append({
                "skill": alias,
                "delay": cfg.get("delay", 0),
                "cd_after_books": cfg.get("cooldown"),
            })
        preset[slot["name"]] = {"opener": opener, "priorities": priorities}
    return preset


def build_potential_team(tune: dict, data: dict, today_affinity: str | None = None) -> dict:
    """Top-level constructor. See docs/cb_sim_plan.md for the output shape.

    `data` is the dict from load_data() — pass once, reuse across many tunes.
    """
    calc_variants = data["calc_variants"]
    roster = _index_roster(data["heroes"])
    artifacts = data["artifacts"]
    hh_idx = _index_hh(data["hh_champions"])
    skills_db = data["skills_db"]

    variant = pick_calc_variant(tune, calc_variants, today_affinity)
    if not variant:
        return {
            "tune_slug": tune.get("slug"),
            "tune_name": tune.get("name"),
            "calc_variant": None,
            "blockers": [{"kind": "no_calc_variant",
                          "detail": "tune has no scraped calc variant"}],
            "todos": [],
            "potential_team": None,
        }

    team = _resolve_team(tune, variant)
    blockers_own, ownership = _check_ownership(team, roster)
    blockers_gear = _check_gear_feasibility(team, ownership, artifacts)
    blockers = blockers_own + [b for b in blockers_gear if b["kind"] != "thin_vault_warning"]
    warnings = [b for b in blockers_gear if b["kind"] == "thin_vault_warning"]

    todos = _enumerate_todos(team, ownership, hh_idx, skills_db)

    out = {
        "tune_slug": tune.get("slug"),
        "tune_name": tune.get("name"),
        "calc_variant": variant.get("variant"),
        "calc_variant_hash": variant.get("hash"),
        "today_affinity": today_affinity,
        "blockers": blockers,
        "warnings": warnings,
        "todos": todos,
    }

    # Materialize the PotentialTeam only when blockers clear.
    if not blockers:
        # Use ownership for non-generic, leave generic slots flagged for
        # the dashboard / sim to pick a DPS from the user's roster.
        team_view = []
        for slot, owned in zip(team, ownership):
            entry = {
                "index": slot["index"],
                "hero": slot["name"],
                "is_generic": slot["is_generic"],
                "target_speed": slot["target_speed"],
                "base_speed": slot["base_speed"],
                "owned_grade": (owned or {}).get("grade") if owned else None,
                "owned_level": (owned or {}).get("level") if owned else None,
                "has_lore_of_steel": slot.get("has_lore_of_steel"),
            }
            team_view.append(entry)
        out["potential_team"] = {
            "team": team_view,
            "preset": _build_preset_from_calc(team),
            "gear_plan": None,         # phase 2: gear_optimizer output
            "masteries": None,         # phase 2: HH-recommended + game-truth
            "blessings": None,         # phase 2: same
        }
    else:
        out["potential_team"] = None

    return out


def main():
    """CLI: dump PotentialTeam summary for one or all tunes."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", help="One tune slug; default = all")
    ap.add_argument("--affinity", default=None, help="Today's CB affinity")
    ap.add_argument("--runnable-only", action="store_true",
                    help="Only show tunes with no blockers")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args()

    data = load_data()
    tunes = data["tunes"]
    if args.slug:
        tunes = [t for t in tunes if t.get("slug") == args.slug]
        if not tunes:
            print(f"No tune with slug={args.slug}")
            return 1

    results = [build_potential_team(t, data, args.affinity) for t in tunes]
    if args.runnable_only:
        results = [r for r in results if not r["blockers"]]

    if args.format == "json":
        print(json.dumps(results, indent=2, default=str))
        return 0

    # Text summary
    print(f"{'tune':<35} {'variant':<22} {'blockers':<8} {'todos':<5}")
    for r in results:
        nb = len(r["blockers"])
        nt = len(r["todos"])
        cv = (r["calc_variant"] or "—")[:22]
        flag = "OK" if not r["blockers"] else "  "
        print(f"  {flag} {r['tune_name'][:32]:<33} {cv:<22} {nb:<8} {nt:<5}")
        for b in r["blockers"][:3]:
            print(f"      - blocker: {b}")
        if len(r["blockers"]) > 3:
            print(f"      - ... +{len(r['blockers'])-3} more")


if __name__ == "__main__":
    sys.exit(main() or 0)
