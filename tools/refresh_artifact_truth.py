#!/usr/bin/env python3
"""
Refresh artifact rules from the live game via mod API. Writes the
authoritative tables to `data/static/artifact_rules.json`. Run after
any Raid patch that may have changed set bonuses, primary/substat
applicability, or rank/rarity stat curves.

What gets captured (game-truth, not handmade):
  - slot id → slot name (Helmet/Chest/Gloves/Boots/Weapon/Shield/Ring/Cloak/Banner)
  - primary stats applicable to each slot (with flat vs %)
  - substats applicable to each slot
  - set definitions: id, internal_name, pieces, stat_bonus, skill_bonus
  - set internal name → in-game UI name (curated alias map)
  - rank/rarity stat values per primary (for ascend forecast)
  - artifact stat enum ↔ stat name lookups

Endpoints used:
  /artifact-sets-truth                        (51 sets + 5 accessory sets)
  /static-export?path=ArtifactData            (slot rules, kind IDs)

The output JSON is consumed by tools/gear_constants.py at import time.
If the file is missing or stale, gear_constants.py falls back to its
embedded constants (less accurate but won't crash).

Usage:
    python3 tools/refresh_artifact_truth.py
    python3 tools/refresh_artifact_truth.py --diff   # show changes vs current
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "static" / "artifact_rules.json"
MOD_BASE = "http://localhost:6790"


def _get(path: str, timeout: int = 30) -> dict:
    try:
        with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as ex:
        return {"error": str(ex)}


# Plarium's internal ArtifactSetKindId → the name shown in the in-game UI.
# Mod's /artifact-sets-truth returns the internal name; we curate the
# display alias here. This is manual but rarely changes (only when
# Plarium adds new sets, which happens every few months).
SET_DISPLAY_NAMES = {
    "Hp":                                       "Life",
    "AttackPower":                              "Offense",
    "Defense":                                  "Defense",
    "AttackSpeed":                              "Speed",
    "CriticalChance":                           "Critical Rate",
    "CriticalDamage":                           "Critical Damage",
    "Accuracy":                                 "Accuracy",
    "Resistance":                               "Resistance",
    "CriticalHealMultiplier":                   "Divine Critical Heal",
    "LifeDrain":                                "Lifesteal",
    "DamageIncreaseOnHpDecrease":               "Avenging",
    "SleepChance":                              "Daze",
    "BlockHealChance":                          "Bloodthirst",
    "FreezeRateOnDamageReceived":               "Frostbite",
    "Stamina":                                  "Immortal",
    "Heal":                                     "Regeneration",
    "BlockDebuff":                              "Immunity",
    "Shield":                                   "Shield",
    "GetExtraTurn":                             "Relentless",
    "IgnoreDefense":                            "Cruel",
    "DecreaseMaxHp":                            "Cursed",
    "StunChance":                               "Stun",
    "DotRate":                                  "Toxic",
    "ProvokeChance":                            "Taunting",
    "Counterattack":                            "Retaliation (2-pc)",
    "CounterattackOnCrit":                      "Retaliation",
    "AoeDamageDecrease":                        "Guardian",
    "CooldownReductionChance":                  "Reflex",
    "AttackPowerAndIgnoreDefense":              "Frenzied",
    "HpAndHeal":                                "Curing",
    "ShieldAndAttackPower":                     "Untouchable",
    "ShieldAndCriticalChance":                  "Deflection",
    "ShieldAndHp":                              "Fortitude",
    "ShieldAndSpeed":                           "Resilience",
    "UnkillableAndSpdAndCrDmg":                 "Immortal Speed (Mythical)",
    "BlockReflectDebuffAndHpAndDef":            "Bastion (Mythical)",
    "HpAndDefence":                             "Protection",
    "AccuracyAndSpeed":                         "Perception",
    "CritDmgAndTransformWeekIntoCritHit":       "Merciless",
    "ResistanceAndBlockDebuff":                 "Steadfast",
    "AttackAndCritRate":                        "Annihilation",
    "FreezeResistAndRate":                      "Frosthold",
    "CritRateAndLifeDrain":                     "Bloodgorge",
    "PassiveShareDamageAndHeal":                "Survival",
    "ResistAndDef":                             "Resilient Will",
    "CritRateAndIgnoreDefMultiplier":           "Hellfire",
    "BuffChanceResHpSpd":                       "Banner Lord",
    "StoneSkinHpResDef":                        "Stoneskin",
    "CritDamageAndSpeed":                       "Relic Hunter",
    "SpeedAndIgnoreDefMultiplier":              "Stalwart",
    "ShieldAndHp2":                             "Aegis",
    "DefAndAoeDamageReduce":                    "Sheltering",
    "SpeedAndCdReductionChance":                "Swiftness",
    "CritDmgAndDmgIncreaseOnHpIncrease":        "Wrath",
    "IncreaseStaminaAndSpdAndAcc":              "Furious",
    "CritDmgAndIgnoreDefAndCdReductionChance":  "Devastation",
    # Mythical accessory-related sets (0-piece display, special slot rules):
    "IncreaseStaminaAndResHpSpd":               "Mythical Stamina",
    "IgnoreDefMultAndAtkSpdCritDmg":            "Mythical Ignore-Def",
    "IncreaseStaminaIgnoreDefMultiplierDmgAndSpd": "Mythical Speed",
    "IncreaseAccuracyAndSpeedWithSkillEffects": "Mythical Skill ACC+SPD",
    "IncreaseAccuracyAndSpeedWithInterceptBuff":"Mythical Intercept",
    "IgnoreDefMultiplierIncreaseAtkAndCritDmgAndSpd": "Mythical IgnoreDef ATK+CD",
    "ReviveSkillDecreaseCooldownIncreaseResAndSpd": "Mythical Revive",
    "HpResSpdChronoBuffScalingWithStacks":      "Mythical Chrono",
    "HpResSpdOnGuardBuffScalingWithStacks":     "Mythical Guard",
    # 1-piece accessory sets
    "IgnoreCooldown":                           "Cleansing Aura",
    "RemoveDebuff":                             "Cleansing Touch",
    "ShieldAccessory":                          "Protection (Acc)",
    "ChangeHitType":                            "Hit Rate (Acc)",
    "CounterattackAccessory":                   "Retaliation (Acc)",
}


def fetch_sets() -> list[dict]:
    r = _get("/artifact-sets-truth", timeout=30)
    if r.get("error"):
        raise RuntimeError(f"/artifact-sets-truth failed: {r['error']}")
    return r.get("sets") or r if isinstance(r, dict) else r


def _static_get(path: str) -> list | dict:
    """`/static-export` returns a list when the path resolves to a list
    (e.g. ArtifactData.PrimaryBonusInfos). Wrap so callers don't need
    to special-case the `.get('error')` check on non-dict returns."""
    r = _get(path)
    if isinstance(r, dict) and r.get("error"):
        raise RuntimeError(f"{path} failed: {r['error']}")
    return r


def fetch_primary_rules() -> list[dict]:
    """Each entry: {stat, is_flat, slots: [...]} for primary stats."""
    r = _static_get("/static-export?path=ArtifactData.PrimaryBonusInfos&depth=4&max=400")
    out = []
    for item in r if isinstance(r, list) else []:
        sk = item.get("StatKey") or {}
        out.append({
            "stat": sk.get("KindId"),
            "is_flat": bool(sk.get("IsAbsolute")),
            "slots": list(item.get("ApplicableKindIds") or []),
        })
    return out


def fetch_substat_rules() -> list[dict]:
    r = _static_get("/static-export?path=ArtifactData.SecBonusInfos&depth=3&max=300")
    out = []
    for item in r if isinstance(r, list) else []:
        sk = item.get("StatKey") or {}
        out.append({
            "stat": sk.get("KindId"),
            "is_flat": bool(sk.get("IsAbsolute")),
            "slots": list(item.get("ApplicableKindIds") or []),
        })
    return out


def build_rules() -> dict:
    sets_raw = fetch_sets()
    primary_rules = fetch_primary_rules()
    substat_rules = fetch_substat_rules()

    # Slot-name set (derived from the rules — should be 9 entries).
    slot_set = set()
    for r in primary_rules + substat_rules:
        slot_set.update(r["slots"])
    all_slots = sorted(slot_set)

    # Sets table — keep id, internal name, display name, pieces, bonuses.
    sets_out = []
    for s in sets_raw:
        internal = s.get("set")
        sets_out.append({
            "id": s.get("id"),
            "internal_name": internal,
            "display_name": SET_DISPLAY_NAMES.get(internal, internal or "?"),
            "pieces": s.get("pieces"),
            "max_pieces": s.get("max_pieces"),
            "stat_bonus": s.get("stat_bonus"),       # primary (first) — back-compat
            # Full list (IL2CPP ArtifactSetInfo.StatBonuses). Several sets grant
            # TWO stats (Perception ACC+SPD, Lethal ATK+CR, ...); the singular
            # field above drops the 2nd. Keep the complete list so SET_BONUSES
            # is game-truth without re-reading artifact_sets.json.
            "stat_bonuses": s.get("stat_bonuses") or (
                [s.get("stat_bonus")] if s.get("stat_bonus") else []),
            "skill_bonus": s.get("skill_bonus"),
        })

    return {
        "schema_version": 1,
        "slots": all_slots,
        "primary_rules": primary_rules,
        "substat_rules": substat_rules,
        "sets": sets_out,
    }


def diff_vs_existing(new_rules: dict) -> list[str]:
    if not OUT_PATH.exists():
        return ["(no existing file — fresh write)"]
    try:
        old = json.loads(OUT_PATH.read_text())
    except Exception as e:
        return [f"(couldn't load existing: {e})"]
    changes = []
    if old.get("schema_version") != new_rules["schema_version"]:
        changes.append(f"schema_version: {old.get('schema_version')} → {new_rules['schema_version']}")
    old_set_ids = {s["id"] for s in (old.get("sets") or [])}
    new_set_ids = {s["id"] for s in new_rules["sets"]}
    added = new_set_ids - old_set_ids
    removed = old_set_ids - new_set_ids
    if added:
        changes.append(f"added sets: {sorted(added)}")
    if removed:
        changes.append(f"removed sets: {sorted(removed)}")
    return changes or ["(no changes detected)"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--diff", action="store_true",
                    help="show what would change vs the current file, don't write")
    args = ap.parse_args()

    rules = build_rules()
    print(f"Built rules: {len(rules['sets'])} sets, "
          f"{len(rules['primary_rules'])} primary rules, "
          f"{len(rules['substat_rules'])} substat rules, "
          f"{len(rules['slots'])} slots ({', '.join(rules['slots'])})")

    print("\nDiff vs existing:")
    for line in diff_vs_existing(rules):
        print(f"  {line}")

    if args.diff:
        print("(--diff only; not writing)")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(rules, indent=2, ensure_ascii=False))
    print(f"\nWrote {OUT_PATH.relative_to(ROOT)} ({OUT_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
