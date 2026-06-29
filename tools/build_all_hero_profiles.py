"""Build hero_profiles_game.json covering EVERY hero in the game, not just
owned ones. Combines:

  - hero_types.json    — hero_id + name + skill_ids (the universe)
  - skills_db.json     — per-owned-hero skill details (book bonuses,
                         hero-specific cooldowns)
  - data/static/snapshots/all_skills_depth8.json — depth-8 effects per skill

Output: hero_profiles_game.json with one entry per unique hero name. Owned
heroes get their book-bonus data; un-owned heroes get base skill data from
static (cooldowns from the depth-8 snapshot, hits/mult parsed from
damage effects).

The downstream `load_game_profiles.load_profiles()` runs `_supplement_skill
_from_static` per labeled skill which fills in effects from the static
snapshot regardless of owned/un-owned. So this just needs to give it the
hero_name → [skill_ids] map plus skeleton skill metadata.

Usage:
    python3 tools/build_all_hero_profiles.py
    # → hero_profiles_game.json (full universe)
"""
from __future__ import annotations
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERO_TYPES = ROOT / "data" / "static" / "hero_types.json"
SKILLS_DB = ROOT / "skills_db.json"
SNAPSHOT = ROOT / "data" / "static" / "snapshots" / "all_skills_depth8.json"
OUT = ROOT / "hero_profiles_game.json"
OUT_BACKUP = ROOT / "hero_profiles_game.owned_only.json"


def _parse_mult_stat_from_static(effects: list[dict]) -> tuple[float, str, int]:
    """First Damage effect's MultiplierFormula → (mult, stat, hits).
    Walks all Damage effects to sum hits and pick the dominant mult/stat.
    """
    total_hits = 0
    total_mult = 0.0
    stat = "ATK"
    for eff in effects or []:
        if eff.get("KindId") != "Damage":
            continue
        f = (eff.get("MultiplierFormula") or "").strip()
        count = eff.get("Count", 1) or 1
        m = re.match(r"^([\d.]+)\*(ATK|DEF|HP)", f)
        if m:
            total_mult += float(m.group(1)) * count
            stat = m.group(2)
            total_hits += count
            continue
        m = re.match(r"^(ATK|DEF|HP)\*([\d.]+)", f)
        if m:
            stat = m.group(1)
            total_mult += float(m.group(2)) * count
            total_hits += count
            continue
        m = re.match(r"^(ATK|DEF|HP)$", f)
        if m:
            stat = m.group(1)
            total_mult += 1.0 * count
            total_hits += count
            continue
    return total_mult, stat, max(total_hits, 1)


def _legacy_effects_from_static(effects: list[dict]) -> list[dict]:
    """Translate depth-8 static effects into the legacy hero_profiles format.

    Output is a list of dicts shaped like load_game_profiles + cb_sim's
    `_supplement_skill_from_static` is happy to consume.
    """
    out = []
    for eff in effects or []:
        kind_str = eff.get("KindId") or ""
        # Map string KindId → numeric kind that cb_sim's legacy parser uses
        kind_num = _LEGACY_KIND.get(kind_str, 0)
        rec = {"kind": kind_num, "count": eff.get("Count", 1) or 1}
        mf = eff.get("MultiplierFormula") or ""
        if mf:
            rec["formula"] = mf
        ses = eff.get("StatusEffectInfos") or []
        if ses:
            rec["status_effects"] = [
                {"type": sei.get("TypeId"), "duration": sei.get("Duration") or 0}
                for sei in ses if isinstance(sei, dict)
            ]
        # Conditions / targeting
        if eff.get("TargetType"):
            rec["target"] = eff["TargetType"]
        cond = eff.get("Condition") or ""
        if isinstance(cond, str) and cond:
            rec["condition"] = cond
        # Use the original kind string as a tag so downstream callers can
        # special-case it cleanly (cb_sim does this for "damage" etc.).
        rec["tag"] = kind_str.lower() if kind_str else ""
        out.append(rec)
    return out


def _eff_is_damage(e: dict) -> bool:
    """True for a Damage effect in either format (legacy kind 6000 / static
    KindId / tagged)."""
    return (e.get("kind") == 6000 or e.get("KindId") == "Damage"
            or e.get("tag") == "damage")


def _filter_boss_damage_effects(effects: list[dict],
                                conditions: list[str] | None = None) -> list[dict]:
    """Keep only Damage effects that fire vs the CB boss; collapse
    mutually-exclusive cond/!cond Damage pairs to ONE. Non-Damage effects and
    genuine multi-hit Damage (unconditional, or distinct non-complementary
    conditions) pass through untouched.

    This is the durable root-fix for the skill-mult double-count (task #31):
    `skills_db.json` strips per-effect Condition, so the generator used to sum
    a skill's `!targetIsBoss` AllEnemies splash (Ninja A3 -> 6.95x/2) and its
    mutually-exclusive conditional Damage variants (Geo A2 -> 12x/2) into the
    boss multiplier. `conditions` is sourced from the index-aligned depth-8
    snapshot Effects (which DO carry Condition) so it works for owned effects
    too. CB-boss eligibility is delegated to load_game_profiles
    `_condition_fires_vs_cb_boss` (one source of truth).
    """
    from load_game_profiles import _condition_fires_vs_cb_boss
    conditions = conditions or []

    def cond_of(i: int, e: dict) -> str:
        if i < len(conditions) and conditions[i]:
            return conditions[i]
        return e.get("condition") or e.get("Condition") or ""

    dmg_conds = {cond_of(i, e) for i, e in enumerate(effects)
                 if _eff_is_damage(e)}
    out, collapsed_seen = [], set()
    for i, e in enumerate(effects):
        if not _eff_is_damage(e):
            out.append(e)
            continue
        cond = cond_of(i, e)
        if not _condition_fires_vs_cb_boss(cond):
            continue  # !targetIsBoss splash / kill-gated revenge damage
        comp = cond[1:] if cond.startswith("!") else "!" + cond
        if cond and comp in dmg_conds:            # complementary pair present
            key = cond.lstrip("!").strip()
            if key in collapsed_seen:
                continue
            collapsed_seen.add(key)
        out.append(e)
    return out


# Minimal KindId→legacy number map (matches what cb_sim has historically).
# Most are placeholder; downstream uses kind_id string via effect_engine.
_LEGACY_KIND = {
    "Damage": 6000,
    "Heal": 1000,
    "ApplyBuff": 4000,
    "ApplyDebuff": 5000,
    "ApplyOrProlongBuff": 4001,
    "ApplyOrProlongDebuff": 5001,
    "IncreaseStamina": 4001,
    "ReduceStamina": 5001,
    "ChangeDamageMultiplier": 7004,
    "PassiveChangeStats": 7005,
    "ExtraTurn": 4007,
    "ReduceCooldown": 4005,
    "IncreaseCooldown": 5005,
    "IncreaseBuffLifetime": 5008,
    "ReduceDebuffLifetime": 5009,
    "RemoveBuff": 5010,
    "RemoveDebuff": 4010,
    "Revive": 4012,
    "StealBuff": 5013,
    "DestroyHp": 7008,
    "ForceStatusEffectTick": 9002,
    "ActivateSkill": 4014,
    "ChangeDefenceModifier": 7001,
    "PassiveBlockDebuff": 4018,
    "PassiveBlockEffect": 4019,
    "Summon": 4020,
    "SetHeroCounter": 4021,
    "UpdateCombo": 4021,
    "PassiveReflectDamage": 7009,
}


def _is_a1(skill: dict) -> bool:
    """Heuristic: A1 = first active skill with cd=0 or marked Default."""
    if (skill.get("Cooldown") or 0) == 0:
        if skill.get("Group") == "Active":
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-backup", action="store_true",
                    help="Don't write the owned-only backup file")
    args = ap.parse_args()

    ht = json.loads(HERO_TYPES.read_text(encoding="utf-8"))
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    skills_static = snap.get("skills") or {}
    skills_db = json.loads(SKILLS_DB.read_text(encoding="utf-8"))

    # 1. Back up the existing owned-only profile if present and not already done
    existing = ROOT / "hero_profiles_game.json"
    if existing.exists() and not args.no_backup and not OUT_BACKUP.exists():
        OUT_BACKUP.write_bytes(existing.read_bytes())
        print(f"Backed up existing -> {OUT_BACKUP.name}")

    # 2. Build owned-name → skills_db data for book bonuses etc.
    owned_skills_by_name: dict[str, list[dict]] = {}
    for hero_name, sk_list in skills_db.items():
        if isinstance(sk_list, list):
            owned_skills_by_name[hero_name] = sk_list

    # 3. Walk hero_types — one entry per unique name (collapse forms / ascend grades)
    # Use the highest-ascend-grade entry per base_id as canonical
    rows = ht.get("hero_types") or []
    by_name: dict[str, dict] = {}
    for h in rows:
        name = h.get("name") or ""
        if not name or h.get("is_boss"):
            continue
        ascend = h.get("ascend_level", 0) or 0
        if name in by_name and ascend <= (by_name[name].get("ascend_level") or 0):
            continue
        by_name[name] = h
    print(f"Unique hero names: {len(by_name)}")

    # 4. Emit profile per hero
    profiles = {}
    owned_count = 0
    skipped_no_skills = 0
    for name, h in by_name.items():
        skill_ids = h.get("skill_ids") or []
        if not skill_ids:
            skipped_no_skills += 1
            continue
        profile_skills = []
        owned_entries = owned_skills_by_name.get(name) or []
        owned_sid_map = {sk.get("skill_type_id"): sk for sk in owned_entries
                          if isinstance(sk, dict)}
        # Dedup skill IDs
        seen = set()
        for sid in skill_ids:
            if sid in seen:
                continue
            seen.add(sid)
            static = skills_static.get(str(sid))
            if not static:
                continue
            # Conditions for THIS skill's effects come from the index-aligned
            # depth-8 snapshot (skills_db strips Condition). Used to drop
            # !targetIsBoss / kill-gated Damage + collapse cond/!cond pairs.
            static_conds = [(e.get("Condition") or "")
                            for e in (static.get("Effects") or [])]
            owned = owned_sid_map.get(sid)
            if owned:
                # Use owned data — it has book-applied cooldowns + correct
                # effects from the legacy parser
                from build_hero_profiles import _parse_mult_stat, _skill_type
                owned_effects = _filter_boss_damage_effects(
                    owned.get("effects") or [], static_conds)
                mult, stat, hits = _parse_mult_stat(owned_effects)
                profile_skills.append({
                    "id": sid,
                    "type": _skill_type(owned),
                    "cooldown": owned.get("cooldown", 0) or 0,
                    "hits": hits,
                    "mult": mult,
                    "stat": stat,
                    "effects": owned_effects,
                })
            else:
                # Derive from static depth-8 snapshot
                effects_static = _filter_boss_damage_effects(
                    static.get("Effects") or [], static_conds)
                mult, stat, hits = _parse_mult_stat_from_static(effects_static)
                group = static.get("Group", "")
                # Skill type heuristic
                cd = static.get("Cooldown") or 0
                if group == "Passive":
                    skill_type = "passive"
                elif _is_a1(static):
                    skill_type = "A1"
                elif group == "Active":
                    skill_type = "active"
                else:
                    skill_type = group.lower() or "active"
                profile_skills.append({
                    "id": sid,
                    "type": skill_type,
                    "cooldown": cd,
                    "hits": hits,
                    "mult": mult,
                    "stat": stat,
                    "effects": _legacy_effects_from_static(effects_static),
                })
        if profile_skills:
            profiles[name] = {"skills": profile_skills}
            if owned_entries:
                owned_count += 1

    OUT.write_text(json.dumps(profiles, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"Wrote {len(profiles)} hero profiles to {OUT.name}")
    print(f"  owned: {owned_count}")
    print(f"  un-owned: {len(profiles) - owned_count}")
    print(f"  skipped (no skills): {skipped_no_skills}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
