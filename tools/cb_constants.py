"""CB simulator constants — sourced from data/static when possible.

Each value is tagged with one of:

    STATIC      — derived at import from data/static/*.json (DRY).
                  Refreshing static data updates the value automatically.
    GAME-SPEC   — matches the game's design spec exactly. Hand-coded but
                  verified against the live game's skill/effect formulas.
                  Static would be a nice-to-have but the value is stable.
    CALIBRATED  — empirically fit from real battle logs. Do NOT flip
                  values from this file to the static-derived equivalent
                  without re-running CB sim calibration. See
                  CLAUDE.md "CB Sim Accuracy" and the project memory note
                  about "6 compensating wrongs that mask each other".

The point of this module is to let `cb_sim.py` import one named symbol
per concept and have the answer to "where does this number come from?"
in a single place.
"""
from __future__ import annotations

# ============================================================================
# CB boss attack multipliers — STATIC (verified against SkillData)
# ============================================================================
# Source: SkillData.SkillTypeById on CB skill 222603 ("Crash Through" / AOE1)
# and 222802 ("Belittle" / AOE2). Read at import; falls back to hand-coded
# values when the static data file is missing.

CB_ATTACK_MULT: dict[str, float] = {}
_CB_SKILL_IDS = {
    "aoe1": 222603,   # 4 hits × 1*ATK
    "aoe2": 222802,   # 2*ATK + 1*ATK
    "stun": 222601,   # 0.2*TRG_B_HP (HP-based, not ATK)
}


def _refresh_cb_attack_mult() -> None:
    """Re-read CB attack multipliers from /skill-data on the live mod.
    Best-effort: silently keeps prior values on failure."""
    import urllib.request
    import urllib.error
    import json as _json

    for label, skill_id in _CB_SKILL_IDS.items():
        try:
            url = (
                "http://localhost:6790/static-export?"
                f"path=SkillData.SkillTypeById.Item%5B{skill_id}%5D&depth=4&max=20"
            )
            with urllib.request.urlopen(url, timeout=5) as r:
                d = _json.loads(r.read().decode("utf-8"))
            total = 0.0
            for e in d.get("Effects", []):
                if e.get("KindId") != "Damage":
                    continue
                f = (e.get("MultiplierFormula") or "").strip()
                count = e.get("Count", 1) or 1
                # Parse simple "<float>*ATK" formulas. Stun uses *_B_HP and
                # is handled separately by the sim — skip it here.
                if "ATK" in f:
                    coeff_str = f.split("*")[0]
                    try:
                        total += float(coeff_str) * count
                    except ValueError:
                        pass
            if total > 0:
                CB_ATTACK_MULT[label] = total
        except Exception:
            continue


# Hand-coded baseline (verified 2026-04-23 against live game). Refreshed in
# place when the mod is reachable. AoE1 = 4 hits × 1*ATK = 4.0; AoE2 = 2+1.
CB_ATTACK_MULT.update({"aoe1": 4.0, "aoe2": 3.0})
_refresh_cb_attack_mult()

# Stun damage is *NOT* in CB_ATTACK_MULT — the sim handles it as
# 0.2 * TARGET_MAX_HP (HP-based, no ATK scaling). See cb_sim._cb_turn().
CB_STUN_HP_FRACTION: float = 0.2  # GAME-SPEC, skill 222601 effect 2226011


# ============================================================================
# Artifact-set proc constants — STATIC (verified against artifact_sets.json)
# ============================================================================
# Source: data/static/artifact_sets.json, set "LifeDrain" (id=9). The proc
# heals 30% of damage dealt (after damage land). Static gives the formula
# string "0.3*DEALT_DMG" — we extract the coefficient.

LIFESTEAL_RATE: float = 0.30  # GAME-SPEC fallback

try:
    try:
        from tools.static_data import default as _sd
    except ImportError:
        from static_data import default as _sd
    _ld = _sd().artifact_set("LifeDrain")
    for _e in _ld.effects:
        if _e.kind == "Heal" and "DEALT_DMG" in _e.formula:
            _coeff = _e.formula.split("*")[0]
            try:
                LIFESTEAL_RATE = float(_coeff)
            except ValueError:
                pass
            break
except Exception:
    pass


# ============================================================================
# CB boss HP — STATIC (alliance_bosses.json, verified vs live battle log)
# ============================================================================
# UNM HP = 1,171,204,485 confirmed against battle_logs_cb_run1_20260501_105018
# (boss type_id 22260 hp_max field exactly matched).

CB_HP_BY_DIFFICULTY: dict[str, int] = {
    "easy": 19_021_215, "normal": 60_616_860, "hard": 194_130_180,
    "brutal": 361_551_030, "nightmare": 652_752_165, "ultranightmare": 1_171_204_485,
    "unm": 1_171_204_485, "nm": 652_752_165,
}
try:
    try:
        from tools.static_data import default as _sd2
    except ImportError:
        from static_data import default as _sd2
    _bosses = _sd2().alliance_bosses
    CB_HP_BY_DIFFICULTY = {
        b.difficulty.lower(): b.hp for b in _bosses.values()
    }
    # Aliases used by cb_sim's CB_SPEED_BY_DIFFICULTY map.
    CB_HP_BY_DIFFICULTY["unm"] = _bosses["UltraNightmare"].hp
    CB_HP_BY_DIFFICULTY["nm"] = _bosses["Nightmare"].hp
    CB_HP_BY_DIFFICULTY["ultranightmare"] = _bosses["UltraNightmare"].hp
except Exception:
    pass


# ============================================================================
# CB boss base speed by difficulty — CALIBRATED
# ============================================================================
# These are the in-battle effective speeds DWJ uses, NOT the
# HeroType.DefaultBaseStats values from static (which are pre-modifier and
# read 80/120/140/160/170/170 respectively). The 190 UNM speed has been
# verified against in-game observations of CB boss turn meter rate.
# Static-derived values would need per-stat verification before flipping.

CB_SPEED_BY_DIFFICULTY: dict[str, float] = {
    "easy":             80,
    "normal":           100,
    "hard":             120,
    "brutal":           160,
    "nightmare":        170,
    "ultra-nightmare":  190,
    "ultranightmare":   190,
    "unm":              190,
    "nm":               170,
}


# ============================================================================
# CB boss attack stat — CALIBRATED
# ============================================================================
# DO NOT flip this to alliance_bosses[].base_stats.atk (which reads 115).
# That is Plarium's stat-index, not a real ATK number. The 3950 here is
# back-solved from Beast Tier 1 AOE1 damage observations.
# See cb_sim.py:405 for the derivation.

# Game-truth boss ATK = 6993 (verified 2026-05-02 from captured
# `p_atk` in damage events; matches HellHades's screenshot exactly).
# Combined with Normal-hit base factor 0.85 (also derived from
# captured `calc_raw / p_atk` ratios), the per-hit pre-mitigation
# damage is: ATK × skill_mult × 0.85.
CB_ATK: int = 6993          # GAME-TRUTH (verified via /damage hooks 2026-05-02)

# Normal-hit base damage factor — derived empirically 2026-05-02.
# Every boss damage event with hit="Normal" shows calc_raw/p_atk ≈ 0.85
# (regardless of affinity, target, skill). Suggests the game applies
# a base 0.85 factor to all damage before crit/crush/glance modifiers.
# Sim was implicitly using 1.0, over-predicting damage by 18%.
NORMAL_HIT_BASE_FACTOR: float = 0.85   # GAME-EMPIRICAL


# ============================================================================
# CB boss DEF / RES — GAME-SPEC (verified 2026-05-01)
# ============================================================================
# Empirical capture from CB UNM Magic 2026-05-01 (1334 damage events):
# t_def = 1520 with no DEF Down, 608 with DEF Down 60% (1520*0.4 = 608 ✓).
# The previous 4878 was a back-fit. The new value lives here as the
# authoritative source; raid_data still imports for backward-compat.
UNM_DEF: int = 1520        # GAME-SPEC (verified via mod damage hook)
UNM_RES: int = 250         # CALIBRATED (no live capture yet)


# ============================================================================
# Mastery proc rates — GAME-SPEC (no static source for conditional masteries)
# ============================================================================
# Per project memory: stat-bonus masteries are in static; conditional ones
# (Warmaster, Giant Slayer, Crushing Rend) have no static form. These match
# the in-game tooltips.

WM_PROC_RATE: float = 0.60   # Warmaster: 60% chance per skill
GS_PROC_RATE: float = 0.30   # Giant Slayer: 30% per hit


# ============================================================================
# Affinity damage multipliers — GAME-SPEC (verified 2026-05-01)
# ============================================================================
# Verified via DamageCalculator.ElementAdvantageBonus IL2CPP invocation
# (the /damage-calc-probe endpoint):
#   Neutral      = 0     → 1.0× damage
#   Advantage    = 0     → 1.0× damage (NO flat damage bonus on strong hits)
#   Disadvantage = -0.2  → 0.8× damage (-20% on weak hits, NOT -30%)
#
# Strong-affinity heroes hit harder ONLY because of:
#   +15% crit chance (CriticalHitChanceAdvantage) → more crits = more damage
#   +50% crushing chance (CrushingHitChance vs the 35% glancing on weak)
#   crushing hit = +30% damage (CrushingHitCoef)
#
# So previous WEAK=0.7 and STRONG=1.3 were both wrong. Sim should roll the
# crit chance with the affinity bonus, not multiply final damage.

WEAK_HIT_DMG_MULT: float = 0.80               # GAME-SPEC (1.0 + ElementDisadvantageCoef -0.2)
WEAK_HIT_DEBUFF_FAIL: float = 0.35            # GAME-SPEC (Plarium official "35% chance")
STRONG_HIT_DMG_MULT: float = 1.0              # GAME-SPEC (advantage adds CRIT chance, not flat damage)


# ============================================================================
# Gathering Fury / enrage — GAME-SPEC (verified 2026-05-01)
# ============================================================================
# Skill 222904 effect MultiplierFormula:
#   T10-T19: DMG_MUL × 0.75 × (OWNERS_TURN_NUMBER - 9)
#   T20+:   DMG_MUL × 7.5 + DMG_MUL × (OWNERS_TURN_NUMBER - 19)
#   T50+:   AddIgnoredEffects (enrage — ignores Block Damage / UK)
# Verified directly from skills_all.json. The previous 0.85 was a back-fit
# to mask other damage gaps; flipping to 0.75 will reduce sim damage in
# T10-T19 specifically — Phase B survival fixes should compensate.

GATHERING_FURY_START_TURN: int = 10           # GAME-SPEC (skill 222904 cond)
GATHERING_FURY_RATE_PER_TURN: float = 0.75    # GAME-SPEC (skill 222904 formula)
GATHERING_FURY_CLIFF_TURN: int = 20           # GAME-SPEC (skill 222904 cond)
ENRAGE_TURN: int = 50                         # GAME-SPEC (skill 222904 cond)


# ============================================================================
# Buff effect rates — GAME-SPEC
# ============================================================================

CONT_HEAL_RATE: float = 0.075  # Continuous Heal: 7.5% max HP per tick


# ============================================================================
# Force Affinity damage caps — CALIBRATED
# ============================================================================
# Per-skill damage caps observed on live UNM Force-Affinity runs (clan has
# already beaten CB; he's in "infinite HP / capped-damage" endless mode).
# Round numbers in per-turn damage deltas suggest these are real game caps,
# not statistical artifacts. Caps are applied AFTER damage calc, before
# WM/GS/passive add-ons. Disable via CBSimulator(force_affinity=False).

FA_CAP_BIG:    int = 250_000   # big AoE / A3
FA_CAP_MEDIUM: int = 175_000   # large single-target
FA_CAP_SMALL:  int =  75_000   # A1 baseline
FA_CAP_DOT:    int =  75_000   # per-tick DoT cap (HP Burn / Poison tick)


# ============================================================================
# Lifesteal / Leech debuff — GAME-SPEC
# ============================================================================
# Leech debuff: attackers heal 10% of damage dealt. Skill-induced (Sicia,
# Cardiel A3) — distinct from the LifeDrain artifact set proc.
LEECH_HEAL_RATE: float = 0.10


# ============================================================================
# DEF mitigation formula — GAME-TRUTH (extracted from GameAssembly.dll)
# ============================================================================
# Reverse-engineered 2026-05-02 by disassembling
# DamageCalculator.DamageReductionByDefence in the IL2CPP-compiled
# binary. The function body uses:
#   - Plarium.Common.Numerics.Fixed.Exp           (exponential)
#   - Fixed.op_Multiply / op_Subtraction / op_Addition / op_Division
#   - integer literals 0x3, 0x3e8 (=1000), 0xfffffffffffffffe (=-2)
#   - a double literal 0.85 at .rdata offset 0x3EB9B68
#   - reads target.Stats.Defence.RawValue
#
# The literal formula:
#   factor = ONE - 0.85 * (1 - exp((Defence - acc_mod)
#                                  * (K + defenceModifier)
#                                  * (-1/1500)))
#
# Where:
#   ONE  = static-field Fixed (1.0 in observed runs)
#   K    = static-field Fixed (1.0 in observed runs)
#   1500 = (3 * 1000) / 2  — integer literals → -2/3000 → -1/1500
#   acc_mod = sum of DEF-reduction effects iterated over AppliedEffects
#             at the start of the function (0 in typical events)
#   defenceModifier = the function's third arg (skill-level ignore-DEF
#                     accumulator; 0 unless caller passes a non-zero
#                     ignore-DEF amount).
#
# Simplified for the typical event (acc_mod=0, defenceModifier=0):
#   factor = 0.15 + 0.85 * exp(-DEF/1500)
#
# Verification: applied to 247 captured (t_def, factor) pairs from
# DamageReductionByDefence postfix hook, error < 0.7pp at every
# observed DEF (608, 1520, 1941, 2023, 2143, 2429, 2974), near-zero at
# DEF >= 1900. Replaces the previous back-solved C/(C+DEF) constants
# (2220 / 1100 / 850) which were always going to drift because
# `C/(C+DEF)` is not the function's actual shape.

DEF_FORMULA_FLOOR:    float = 0.15      # asymptotic factor as DEF -> infinity
DEF_FORMULA_SCALE:    float = 0.85      # 1 - floor; .rdata literal at 0x3EB9B68
DEF_FORMULA_DENOM:    float = 1500.0    # (3 * 1000) / 2 in the code

# Static-field constants resolved via dump.cs:
#   ONE  = Plarium.Common.Numerics.Fixed.One  (static-field offset 0x20)
#   K    = same (all three "1.0" usages dereference Fixed.One)
#   acc_mod is initialized to Plarium.Common.Numerics.Fixed.Zero (offset
#     0x28) and modified by an EnumerateAppliedEffects loop filtering
#     on EffectKindId.StatusIncreaseDefence (=2102).
#
# Captured live (mod hook on Fixed.op_Subtraction, 2026-05-02):
#   acc_mod is always 0 in observed events — the EnumerateAppliedEffects
#   loop runs but produces no contribution under normal play. The
#   "0.02 * Defence" pattern initially attributed to acc_mod actually
#   came from defenceModifier (the function's third arg) being -0.02
#   for hero attackers — a 2% base armor pierce applied by the caller
#   (CalculateDamage). Boss attackers pass 0. Skill-level ignore-DEF
#   modifiers push the value more negative (Ninja A3 = -1.0 full ignore).
#
# Sim-side defaults:
#   hero -> boss attacks: defence_modifier = HERO_BASE_ARMOR_PIERCE
#   boss -> hero attacks: defence_modifier = 0
HERO_BASE_ARMOR_PIERCE: float = -0.02   # GAME-TRUTH (captured Fixed=-0.02)

def def_mitigation_factor(defence: float,
                          acc_mod: float = 0.0,
                          defence_modifier: float = 0.0,
                          one: float = 1.0,
                          k: float = 1.0) -> float:
    """Game-truth DEF mitigation factor: damage *= factor.

    Mirrors DamageCalculator.DamageReductionByDefence exactly when
    ONE = K = 1 (the observed defaults) and acc_mod = 0 (empty loop).

    Args:
        defence: target.Stats.Defence value (post-DEF-Down/IncDEF).
        acc_mod: accumulator from the AppliedEffects loop filtering on
            StatusIncreaseDefence. Pass `defence * 0.02` for hero -> boss
            events to match observed live captures.
        defence_modifier: function's third arg (skill-level ignore-DEF
            multiplier; 0 for normal skills).
    """
    import math
    inner = (defence - acc_mod) * (k + defence_modifier) * (-1.0 / DEF_FORMULA_DENOM)
    return one - DEF_FORMULA_SCALE * (1.0 - math.exp(inner))
