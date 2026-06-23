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


# Hand-coded baseline.
# AoE2 (skill 222802 etc): 2 separate effects (2*ATK + 1*ATK) both Count=1
#   to AllEnemies = 3*ATK per hero. Verified vs real T17 damage (40.34K sim
#   vs 42K real, within 4%).
CB_ATTACK_MULT.update({"aoe1": 1.0, "aoe2": 3.0})
_refresh_cb_attack_mult()
# AoE1 (skill 222603): Count=4 with TargetType=AllEnemies. The naive parser
# computes 1*ATK × Count=4 = 4×ATK per hero. WRONG. Real damage data
# (battle_logs_cb_20260615_203854) shows per-hero damage at AOE1 turns is
# ~1×ATK, not 4×ATK. The Count=4 likely means "4 hits distributed across
# targets" — with 5 player heroes and 4 hits, each hero takes ~0.8 hits avg
# = ~1×ATK. Override AFTER _refresh_cb_attack_mult so live-mod re-reads
# don't restore the wrong 4.0 value. Fixing 2026-06-16 brought Spirit-day
# MEN sim from +1.0% to +0.0% vs real T50/37.12M.
CB_ATTACK_MULT["aoe1"] = 1.0

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
# CB boss base speed by difficulty — community-canonical
# ============================================================================
# Verified 2026-06-16 by user (community canon):
#   UNM: 190 base, recommended champ SPD 191-209 (or 171-189 if behind)
#   NM:  170 base, 171-189
#   Brutal: 160 base, 161-169
#   Hard:   140 base, 141-149
#   Normal: 120 base, 121-129
#   Easy:    90 base,  91-99
# The static `data/static/alliance_bosses.json` UNM spd=170 value was
# misread (it's likely a pre-modifier base; the in-battle effective SPD
# is 190). Reverted 2026-06-16 from a brief cb_speed=170 experiment.

CB_SPEED_BY_DIFFICULTY: dict[str, float] = {
    # UNM kept at 191 per user (2026-06-23) — community canon may
    # reflect an unmodeled +20 SPD source (CB area aura?) that gives
    # heroes effective +20 SPD vs boss base 170. Cadence diff alone
    # can't distinguish (boss=170 no aura ≈ boss=190 +20 aura).
    # See task #14.
    "easy":             91,
    "normal":           121,
    "hard":             141,
    "brutal":           161,
    "nightmare":        171,
    "ultra-nightmare":  191,
    "ultranightmare":   191,
    "unm":              191,
    "nm":               171,
}


# ============================================================================
# CB boss crit chance / crit damage — STATIC (data/static/alliance_bosses.json)
# ============================================================================
# UNM Demon Lord base_stats: cr=15 (= 0.15), cd=50 (= 0.50 = +50% crit dmg).
# These come from the live mod's StaticData export; if Plarium retunes the
# boss CR/CD, refreshing alliance_bosses.json updates these automatically.
CB_CR_BY_DIFFICULTY: dict[str, float] = {}
CB_CD_BY_DIFFICULTY: dict[str, float] = {}
try:
    for _b in (_bosses.values() if "_bosses" in dir() else []):
        _bs = getattr(_b, "base_stats", None) or {}
        _diff = _b.difficulty.lower()
        # Stat-index field encodes percentages as integers — 15 -> 0.15.
        _cr_raw = _bs.get("cr") if isinstance(_bs, dict) else getattr(_bs, "cr", None)
        _cd_raw = _bs.get("cd") if isinstance(_bs, dict) else getattr(_bs, "cd", None)
        if _cr_raw is not None:
            CB_CR_BY_DIFFICULTY[_diff] = float(_cr_raw) / 100.0
        if _cd_raw is not None:
            CB_CD_BY_DIFFICULTY[_diff] = float(_cd_raw) / 100.0
    # Aliases
    if "ultranightmare" in CB_CR_BY_DIFFICULTY:
        CB_CR_BY_DIFFICULTY["unm"] = CB_CR_BY_DIFFICULTY["ultranightmare"]
        CB_CD_BY_DIFFICULTY["unm"] = CB_CD_BY_DIFFICULTY["ultranightmare"]
    if "nightmare" in CB_CR_BY_DIFFICULTY:
        CB_CR_BY_DIFFICULTY["nm"] = CB_CR_BY_DIFFICULTY["nightmare"]
        CB_CD_BY_DIFFICULTY["nm"] = CB_CD_BY_DIFFICULTY["nightmare"]
except Exception:
    pass

# Fallback defaults if static load failed (UNM values verified 2026-06-15).
CB_CR_DEFAULT: float = CB_CR_BY_DIFFICULTY.get("unm", 0.15)
CB_CD_DEFAULT: float = CB_CD_BY_DIFFICULTY.get("unm", 0.50)


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

WM_PROC_RATE: float = 0.60   # Warmaster: 60% chance per skill (verified 2026-06-22 from in-game mastery description via mod /mastery-info?id=500161)
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

# Glancing hit chance on weak-affinity hits.
# Empirically derived 2026-06-18: Force-day captures (Magic Ninja vs Force boss
# = weak hit) showed Ninja A1's IncreaseStamina effect (+15% TM, gated by
# `Relation.ActivateOnGlancingHit: false`) fired only 73% of the time across
# 23 captures (192/264 casts). So ~27% of weak hits glance.
# Spirit (strong) and Magic (neutral, same-affinity) captures showed 98%+ and
# 100% fire rates — neither can glance.
# Used by `_apply_effects` in cb_sim.py to gate any effect whose static
# `Relation.ActivateOnGlancingHit` field is false (currently just Ninja A1's
# self_tm_fill, but extensible to any other AfterEffectProcessedOnTarget-keyed
# effect whose hero is weak vs boss).
WEAK_HIT_GLANCE_CHANCE: float = 0.35          # game-truth: gameplay.json GlancingHitChance=0.35
# Earlier value of 0.27 was empirical (192/264 weak-hit observations
# 2026-06-18). The static value is HIGHER. Difference likely came from
# multi-hit attacks where at least one hit landed non-glance and the boost
# applied once per cast. Default to the static truth.


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
# CB DoT-cap constants — STATIC (from boss passive skill bodies)
# ============================================================================
# Boss skill 200008 ("Clan Boss TRG_HP resistance") clamps incoming
# AoEContinuousDamage (HP Burn) ticks. Boss skill 200007 ("Clan Boss
# Cont damage resistance IV") clamps ContinuousDamage (Poison) ticks.
# Each skill's MultiplierFormula spells out the cap explicitly:
#
#   200008 -> -(DMG_MUL - (!detonated*75000 + detonated*75000*turns_left))
#             ...for HP Burn 5% (the standard CB UNM HP Burn cap = 75000)
#             plus 15000 and 50000 caps on lower-tier variants
#             plus a 250000 cap (big-AoE)
#   200007 -> -(DMG_MUL - (!detonated*25000 + ...))   [poison_2_5pct]
#             -(DMG_MUL - (!detonated*50000 + ...))   [poison_5pct]
#
# Reading this from static keeps the caps traceable. They were
# previously CALIBRATED constants in this file — now sourced from the
# skill data the boss itself carries.

_CB_DOT_CAPS_CACHE: dict[str, int] | None = None


def _load_cb_dot_caps() -> dict[str, int]:
    """Parse `data/static/skills_all.json` for skills 200008 and 200007
    and extract the integer cap values from their ChangeDamageMultiplier
    formulas.

    Formula shape: `-(DMG_MUL-(!relatedEffectWasDetonated*X+relatedEffectWasDetonated*X*...))`
    Extract X from `!relatedEffectWasDetonated*X+`.
    """
    global _CB_DOT_CAPS_CACHE
    if _CB_DOT_CAPS_CACHE is not None:
        return _CB_DOT_CAPS_CACHE
    import json as _json, re as _re
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parent.parent / "data" / "static" / "skills_all.json"
    out: dict[str, int] = {}
    if not p.exists():
        _CB_DOT_CAPS_CACHE = out
        return out
    try:
        sa = _json.loads(p.read_text(encoding="utf-8"))["data"]
    except Exception:
        _CB_DOT_CAPS_CACHE = out
        return out
    sk_idx = {s["Id"]: s for s in sa if isinstance(s, dict) and "Id" in s}

    def extract_caps(skill_id: int) -> list[int]:
        s = sk_idx.get(skill_id)
        if not s:
            return []
        caps = []
        for e in s.get("Effects", []) or []:
            if not isinstance(e, dict):
                continue
            mf = e.get("MultiplierFormula") or ""
            m = _re.search(r"!relatedEffectWasDetonated\*(\d+)", mf)
            if m:
                caps.append(int(m.group(1)))
            else:
                # fallback for the simple 250000 case "-(DMG_MUL-250000)"
                m2 = _re.search(r"-\(DMG_MUL-(\d+)\)", mf)
                if m2:
                    caps.append(int(m2.group(1)))
        return caps

    # Skill 200008: HP Burn cap (sorted; UNM = the largest at 75000)
    burn_caps = sorted(extract_caps(200008))
    if burn_caps:
        # 250000 is the big-AoE cap (last); the other three are
        # difficulty-tiered HP-Burn caps. UNM is the maximum non-AoE.
        burn_excl_aoe = [c for c in burn_caps if c <= 100_000]
        if burn_excl_aoe:
            out["hp_burn"] = max(burn_excl_aoe)
        out["big_aoe_cap"] = max(burn_caps)
    # Skill 200007: Poison caps
    poison_caps = sorted(extract_caps(200007))
    if poison_caps:
        out["poison_2_5pct"] = poison_caps[0] if len(poison_caps) >= 1 else 25_000
        out["poison_5pct"]   = poison_caps[-1]
    _CB_DOT_CAPS_CACHE = out
    return out


def cb_dot_cap(effect: str, default: int = 75_000) -> int:
    """Per-tick DoT cap for the named effect on UNM CB.

    Effect keys:
        "hp_burn"        -> 75000 (skill 200008)
        "poison_5pct"    -> 50000 (skill 200007)
        "poison_2_5pct"  -> 25000 (skill 200007)
        "big_aoe_cap"    -> 250000 (skill 200008 last effect)
    """
    return _load_cb_dot_caps().get(effect, default)


# ============================================================================
# Lifesteal / Leech debuff — GAME-SPEC
# ============================================================================
# Leech debuff: attackers heal 10% of damage dealt. Skill-induced (Sicia,
# Cardiel A3) — distinct from the LifeDrain artifact set proc.
LEECH_HEAL_RATE: float = 0.10


# ============================================================================
# Hit-type bonus formula — GAME-TRUTH (extracted 2026-05-02)
# ============================================================================
# DamageCalculator.HitTypeBonus(BattleHero dealer, HitType hitType) at VA
# 0x182CE7880. Branches by hitType (enum: Normal=0 Crushing=1 Critical=2
# Glancing=3) and returns a Fixed bonus that the caller adds to 1.0 to
# scale base damage:
#
#   Normal   -> Fixed.Zero (0)                    => damage × 1.00
#   Crushing -> GameplayData.CrushingHitCoef      => damage × (1 + 0.30)
#   Critical -> dealer.Stats.CriticalDamage       => damage × (1 + CD)
#   Glancing -> GameplayData.GlancingHitCoef      => damage × (1 + -0.30)
#
# CrushingHitCoef and GlancingHitCoef are the same values exposed via
# `data/static/gameplay.json` (matching CrushingHitCoef=0.3,
# GlancingHitCoef=-0.3 above). Critical is per-hero — the game reads
# the dealer's CD stat from BattleStats[+0x48] directly.

# Game-truth values from data/static/gameplay.json (= CRUSHING_HIT_COEF
# / GLANCING_HIT_COEF that gameplay-data refresh produces, kept named
# explicitly here to mirror the Plarium field names).
CRUSHING_HIT_COEF: float = 0.3
GLANCING_HIT_COEF: float = -0.3


def hit_type_bonus(hit_type: str, dealer_cd_pct: float = 0.0) -> float:
    """Returns the +bonus the game adds to a hit's base damage multiplier.

    `hit_type` ∈ {"normal", "crushing", "critical", "glancing"}.
    `dealer_cd_pct` is the dealer's Critical Damage stat as a percent
    (e.g. 150 for 150% CD). Multiplier the caller applies:
        final = base × (1 + hit_type_bonus(...))
    """
    if hit_type == "crushing": return CRUSHING_HIT_COEF
    if hit_type == "glancing": return GLANCING_HIT_COEF
    if hit_type == "critical": return dealer_cd_pct / 100.0
    return 0.0  # Normal hit, or unknown


# ============================================================================
# StoneSkin / Petrification / NewbieDefence factors — GAME-SPEC
# ============================================================================
# DamageCalculator.StoneSkinDamageFactor(BattleHero, EffectKindId) at VA
# 0x182CE8520, PetrificationDamageFactor at 0x182CE8200, and
# NewbieDefenceDamageFactor at 0x182CE80C0. All three follow the same
# pattern:
#   1. Look up the effect descriptor on the target's BattleHero.
#   2. If no qualifying effect active, fall through to "no reduction".
#   3. Compare the incoming EffectKindId against 0xbc1 (= 3009 =
#      ContinuousDamage / Poison) — poisons bypass StoneSkin/Petrification.
#   4. Read the effect's Amount from the descriptor (offset +0x1a8 →
#      +0x18 for StoneSkin, +0x1b0 → +0x18 for Petrification).
#
# In CB, none of these three are active on the player team or boss in
# observed events:
#   - StoneSkin: hero buff, not present on CB targets
#   - Petrification: dungeon mechanic, never on CB
#   - NewbieDefence: low-level account protection, well past us
# Sim treats them as factor = 1.0 (no reduction). When the captures
# surface a non-trivial value, replace these with the actual function.

def stone_skin_damage_factor(*, has_stone_skin: bool = False,
                              effect_kind_id: int = 0,
                              stone_skin_amount: float = 0.0) -> float:
    if not has_stone_skin:
        return 1.0
    if effect_kind_id == 3009:  # poison bypasses StoneSkin
        return 1.0
    return 1.0 - stone_skin_amount  # e.g. 0.6 amount → 0.4 factor


def petrification_damage_factor(*, has_petrification: bool = False,
                                 effect_kind_id: int = 0,
                                 petrification_amount: float = 0.0) -> float:
    if not has_petrification:
        return 1.0
    if effect_kind_id == 3009:  # poison bypasses
        return 1.0
    return 1.0 - petrification_amount


def newbie_defence_damage_factor(level: int = 60) -> float:
    """Game's low-level damage reduction. Above level ~10 returns 1.0."""
    return 1.0  # We're always past it. Stub for future captures.


# ============================================================================
# Status-effect multipliers — STATIC (data/static/effects.json)
# ============================================================================
# Every status effect with a HasMultiplier=True entry carries its literal
# multiplier in `MultiplierFormula`. Examples (read live from static):
#   Id 350 IncreaseDamageTaken25 (Weaken) -> 1.25
#   Id 351 IncreaseDamageTaken15          -> 1.15
#   Id 430 Minotaur IDT                   -> 3
#   Id 431 HydraNeck IDT                  -> 3
# Sim's hand-coded `wk = 1.25 if has_weaken` is game-truth, but reading
# from static keeps it traceable AND auto-updates when Plarium tunes the
# value in a patch.

_STATIC_EFFECT_MULTIPLIERS_CACHE: dict[int, float] | None = None


def _load_status_effect_multipliers() -> dict[int, float]:
    """Lazy-load {effect_id -> MultiplierFormula} from effects.json.
    Skips effects whose formula isn't a plain number (some are computed
    expressions like '0.2*TRG_B_HP'). Caller can fall back to a hand-
    coded constant when an effect's formula is a string expression.
    """
    global _STATIC_EFFECT_MULTIPLIERS_CACHE
    if _STATIC_EFFECT_MULTIPLIERS_CACHE is not None:
        return _STATIC_EFFECT_MULTIPLIERS_CACHE
    import json as _json
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parent.parent / "data" / "static" / "effects.json"
    out: dict[int, float] = {}
    if p.exists():
        try:
            data = _json.loads(p.read_text(encoding="utf-8")).get("data", [])
            for e in data:
                eid = e.get("Id")
                mf = e.get("MultiplierFormula")
                if eid is None or mf is None:
                    continue
                try:
                    out[eid] = float(mf)
                except (TypeError, ValueError):
                    pass  # formula is an expression like "0.2*TRG_B_HP"
        except Exception:
            pass
    _STATIC_EFFECT_MULTIPLIERS_CACHE = out
    return out


def status_effect_multiplier(effect_id: int, default: float = 1.0) -> float:
    """Game-truth multiplier for any status effect by Id.

    Examples:
        status_effect_multiplier(350)  # 1.25 (Weaken)
        status_effect_multiplier(351)  # 1.15 (small Weaken variant)
        status_effect_multiplier(430)  # 3.0  (Minotaur IDT)
    Returns `default` when the effect isn't in static, or has a
    formula expression (not a plain number).
    """
    return _load_status_effect_multipliers().get(effect_id, default)


# Convenience aliases for common effects sim references (so callers
# can write `WEAKEN_MULT` instead of remembering effect 350).
WEAKEN_MULT: float          = status_effect_multiplier(350, 1.25)  # IncreaseDamageTaken25
WEAKEN_15_MULT: float       = status_effect_multiplier(351, 1.15)  # IncreaseDamageTaken15


# ============================================================================
# Comprehensive buff/debuff registry — STATIC (data/static/effects.json)
# ============================================================================
# Every common CB-relevant buff/debuff is defined here as
# `name -> effect_id`. The literal multiplier ALWAYS comes from
# `data/static/effects.json` at lookup time — we never store the
# numeric value, only the effect Id. This means the registry can't
# drift from game data: if Plarium retunes a value in a patch,
# refreshing `effects.json` (run `tools/refresh_static_data.py`)
# auto-updates every callsite.
#
# Naming convention: `<effect>_<percentage>` matches the in-game
# tooltip number (e.g. `inc_spd_30` = "+30% Speed buff").
# Pair IDs are sorted by ascending magnitude — _15 / _30 / _50.
#
# Important: each effect's MultiplierFormula encodes the value in its
# own way, so callers must know what they're getting:
#   - StatusIncreaseSpeed/Defence/etc. -> "0.3*TRG_B_SPD"  ->  0.3
#     (the additive % of base stat — 0.3 means +30%)
#   - IncreaseCriticalChance/Damage    -> "0.3"            ->  0.3
#     (additive percentage points)
#   - IncreaseDamageTaken (Weaken)     -> "1.25"           ->  1.25
#     (final multiplier — caller does NOT add 1; multiplies directly)
#   - ReduceDamageTaken (Strengthen)   -> "0.85"           ->  0.85
#     (final factor — damage_taken *= 0.85 = -15%)
#   - ContinuousHeal                   -> "0.075*TRG_HP"   ->  0.075
#     (fraction of TRG_HP per tick)
#   - ReflectDamage                    -> "0.15*DEALT_DMG" ->  0.15
#     (fraction of damage reflected)
#   - PoisonSensitivity                -> "CALCULATED_DMG*0.25" -> 0.25
#     (we extract the trailing factor)

# name -> static effect Id
BUFF_REGISTRY: dict[str, int] = {
    # Speed (TRG_B_SPD-relative additive)
    "inc_spd_15":   160, "inc_spd_30":   161,
    "dec_spd_15":   170, "dec_spd_30":   171,
    # Attack
    "inc_atk_25":   120, "inc_atk_50":   121,
    "dec_atk_25":   130, "dec_atk_50":   131,
    # Defence
    "inc_def_30":   140, "inc_def_60":   141,
    "dec_def_30":   150, "dec_def_60":   151,
    # Crit Chance (additive percentage points)
    "inc_cr_15":    240, "inc_cr_30":    241,
    "dec_cr_15":    250, "dec_cr_30":    251,
    # Crit Damage
    "inc_cd_15":    260, "inc_cd_30":    261,
    # Accuracy / Resistance
    "inc_acc_25":   220, "inc_acc_50":   221,
    "dec_acc_25":   230, "dec_acc_50":   231,
    "inc_res_25":   710, "inc_res_50":   711,
    "dec_res_25":   720, "dec_res_50":   721,
    # IncreaseDamageTaken (Weaken family — final mult, e.g. 1.25)
    "weaken_25":    350, "weaken_15":    351,
    # ContinuousHeal (fraction of TRG_HP per tick)
    "cont_heal_75":  90, "cont_heal_15":  91,
    # ReflectDamage (fraction of DEALT_DMG)
    "reflect_15":   410, "reflect_30":   411,
    # ReduceDamageTaken (Strengthen — final factor, e.g. 0.85)
    "strengthen_15":510, "strengthen_25":511,
    # PoisonSensitivity (CALCULATED_DMG * X — trailing factor)
    "poison_sens":  500,

    # ----- DoT base rates (fraction of TRG_HP per tick) -----
    # These are the PRE-CAP percentages the game applies. CB UNM caps
    # them per cb_dot_cap() — but for non-CB content (dungeons, hydra),
    # the percentage is the active formula.
    "hp_burn":       470,     # 0.03 * TRG_HP
    "poison_5pct":    80,     # 0.05 * TRG_HP
    "poison_2_5pct":  81,     # 0.025 * TRG_HP

    # ----- Survival mechanics -----
    "revive_on_death": 300,   # 0.3 * TRG_HP (revives at 30% MAX HP)

    # ----- Damage-absorb shields -----
    "hit_counter_shield_80": 450,   # 0.8 * DEALT_DMG (Shemnath-style)
    "bone_shield_20":        730,   # 0.2 * DEALT_DMG (BoneShield base)
    "bone_shield_30":        731,   # 0.3 * DEALT_DMG (BoneShield bigger)

    # ----- Detonate-on-end damage -----
    "time_bomb":     330,     # 5 * ATK (Bomb deals 5x ATK on expire)
}


def _parse_multiplier_formula(mf: str | None) -> float | None:
    """Extract the numeric coefficient from a MultiplierFormula.
    Handles "0.3*TRG_B_SPD" / "0.85" / "CALCULATED_DMG*0.25" /
    "0.075*TRG_HP". Returns None when the formula is non-numeric.
    """
    if mf is None:
        return None
    import re
    s = str(mf).strip()
    # Leading numeric: "0.3", "0.3*X", "1.25"
    m = re.match(r'^(-?[\d.]+)', s)
    if m:
        try: return float(m.group(1))
        except ValueError: pass
    # Trailing numeric: "X*0.25"
    m = re.search(r'\*(-?[\d.]+)\s*$', s)
    if m:
        try: return float(m.group(1))
        except ValueError: pass
    return None


def buff_mult(name: str, default: float = 0.0) -> float:
    """Look up a buff/debuff's literal multiplier.

    Reads from `data/static/effects.json` MultiplierFormula via the
    BUFF_REGISTRY mapping. Returns the parsed numeric value of the
    formula. Caller is responsible for knowing whether that value is
    additive (+30% SPD = 0.30 added to base) or a final factor
    (Weaken = 1.25 multiplied directly).

    Examples:
        buff_mult("inc_spd_30")    # 0.30  (additive on base SPD)
        buff_mult("weaken_25")     # 1.25  (final mult on damage taken)
        buff_mult("cont_heal_75")  # 0.075 (fraction of MAX_HP)
        buff_mult("strengthen_15") # 0.85  (final factor: damage * 0.85)
    """
    eid = BUFF_REGISTRY.get(name)
    if eid is None:
        return default
    val = status_effect_multiplier(eid, default=None)  # type: ignore[arg-type]
    if val is None or val == 0.0:
        # status_effect_multiplier may return 0.0 when formula didn't
        # parse — try our richer parser.
        import json as _json
        from pathlib import Path as _Path
        p = _Path(__file__).resolve().parent.parent / "data" / "static" / "effects.json"
        if p.exists():
            data = _json.loads(p.read_text(encoding="utf-8")).get("data", [])
            for e in data:
                if e.get("Id") == eid:
                    parsed = _parse_multiplier_formula(e.get("MultiplierFormula"))
                    if parsed is not None:
                        return parsed
                    break
        return default
    return val


def buff_effect_id(name: str) -> int | None:
    """The static effect Id behind a registry entry."""
    return BUFF_REGISTRY.get(name)


# ============================================================================
# Top-level gameplay tunables — STATIC (data/static/gameplay.json)
# ============================================================================
# These are global Plarium constants exposed via StaticGameplayData.
# Loaded once on import; refresh by re-running tools/refresh_static_data.py.

_GAMEPLAY_CACHE: dict | None = None


def _load_gameplay() -> dict:
    global _GAMEPLAY_CACHE
    if _GAMEPLAY_CACHE is not None:
        return _GAMEPLAY_CACHE
    import json as _json
    from pathlib import Path as _Path
    p = _Path(__file__).resolve().parent.parent / "data" / "static" / "gameplay.json"
    out: dict = {}
    if p.exists():
        try:
            out = _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    _GAMEPLAY_CACHE = out
    return out


def gameplay_const(name: str, default: float = 0.0) -> float:
    """Read a top-level constant from gameplay.json.

    Examples:
        gameplay_const("CounterattackModifier")    # -0.25
        gameplay_const("ShieldCapValue")           # 1000000
        gameplay_const("HpDestructionFromDamagePercent")  # 0.4
        gameplay_const("CrushingHitCoef")          # 0.3 (also exposed as CRUSHING_HIT_COEF)
    """
    val = _load_gameplay().get(name, default)
    if isinstance(val, (int, float, bool)):
        return float(val)
    return default


# Common aliases sim references — sourced from gameplay.json.
COUNTERATTACK_MODIFIER: float = gameplay_const("CounterattackModifier", -0.25)
SHIELD_CAP_VALUE:       int   = int(gameplay_const("ShieldCapValue",   1_000_000))
HP_DESTRUCTION_PCT:     float = gameplay_const("HpDestructionFromDamagePercent", 0.4)
MAX_APPLIED_BUFF_EFFECTS:   int = int(gameplay_const("MaxAppliedBuffEffects",   10))
MAX_APPLIED_DEBUFF_EFFECTS: int = int(gameplay_const("MaxAppliedDebuffEffects", 10))


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


# ============================================================================
# Manifest cross-check — Workstream 1.E / 2 / 3 integration safety net
# ============================================================================
# At import time, optionally validate that this module's constants match
# the manifest-backed values exposed by sim_data_facade. Any drift surfaces
# immediately rather than silently after a future manifest refresh.
#
# Best-effort: if the facade can't load (manifests missing), this is a
# no-op. Set CB_CONSTANTS_STRICT=1 in env to make drift a hard error.
def _validate_against_manifest() -> None:
    import os
    strict = os.environ.get("CB_CONSTANTS_STRICT") == "1"
    try:
        # Late import to avoid circular issues
        import sys
        from pathlib import Path
        tools_dir = Path(__file__).resolve().parent
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        from sim_data_facade import try_facade
        f = try_facade()
        if f is None:
            return
        drift = []
        # Normal-hit base factor
        try:
            manifest_nhf = f.damage.normal_hit_base_factor
            if abs(manifest_nhf - NORMAL_HIT_BASE_FACTOR) > 0.0001:
                drift.append(
                    f"NORMAL_HIT_BASE_FACTOR: constants={NORMAL_HIT_BASE_FACTOR} "
                    f"manifest={manifest_nhf}"
                )
        except Exception:
            pass
        # Element disadvantage
        try:
            manifest_disadv = f.damage.element_multiplier("Disadvantage")
            if abs(manifest_disadv - WEAK_HIT_DMG_MULT) > 0.0001:
                drift.append(
                    f"WEAK_HIT_DMG_MULT: constants={WEAK_HIT_DMG_MULT} "
                    f"manifest_Disadvantage={manifest_disadv}"
                )
        except Exception:
            pass
        # Warmaster proc rate
        try:
            manifest_wm = f.mastery.warmaster_proc().get("chance")
            if manifest_wm is not None and abs(manifest_wm - WM_PROC_RATE) > 0.0001:
                drift.append(
                    f"WM_PROC_RATE: constants={WM_PROC_RATE} "
                    f"manifest={manifest_wm}"
                )
        except Exception:
            pass
        # Giant Slayer proc rate
        try:
            manifest_gs = f.mastery.giant_slayer_proc().get("chance")
            if manifest_gs is not None and abs(manifest_gs - GS_PROC_RATE) > 0.0001:
                drift.append(
                    f"GS_PROC_RATE: constants={GS_PROC_RATE} "
                    f"manifest={manifest_gs}"
                )
        except Exception:
            pass
        # Boss turn-50 enrage trigger
        try:
            manifest_enrage = f.boss.turn_50_trigger
            if manifest_enrage and manifest_enrage != ENRAGE_TURN:
                drift.append(
                    f"ENRAGE_TURN: constants={ENRAGE_TURN} "
                    f"manifest={manifest_enrage}"
                )
        except Exception:
            pass
        # UNM boss base crit chance / damage (from alliance_bosses.json)
        # These don't have a manifest equivalent yet (facade.boss covers
        # skills, not stats) but we self-validate the static load.
        try:
            if not (0.0 <= CB_CR_DEFAULT <= 1.0):
                drift.append(
                    f"CB_CR_DEFAULT out of [0,1]: {CB_CR_DEFAULT}"
                )
            if not (0.0 <= CB_CD_DEFAULT <= 5.0):
                drift.append(
                    f"CB_CD_DEFAULT out of expected range: {CB_CD_DEFAULT}"
                )
        except Exception:
            pass
        if drift and strict:
            raise RuntimeError(
                "cb_constants ↔ manifest drift detected:\n  "
                + "\n  ".join(drift)
            )
        elif drift:
            import warnings
            warnings.warn(
                "cb_constants ↔ manifest drift:\n  "
                + "\n  ".join(drift)
                + "\n  (set CB_CONSTANTS_STRICT=1 to fail-loud)"
            )
    except Exception:
        # Non-fatal: facade missing or other issue
        pass


_validate_against_manifest()
