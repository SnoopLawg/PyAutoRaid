"""M5 PHASE 5a — channel-aware heuristic fitness (works everywhere now).

The heuristic scores a comp from the M1 enriched tags + M3 boss constraints
WITHOUT a per-mode simulator, so it works for all 12 locations today. It is
deliberately TRANSPARENT: every term lands in the returned `breakdown` dict.

Model (game-truth from the 2026-06-29 research synthesis):

    fitness = (damage_score + control_score) * survival_multiplier
              - penalties

  damage_score — CHANNEL-AWARE multiplier stacking, never crossing channels:
    • hit channel    : (# hit/wm_gs/bring_it_down engines) × hit-amp multiplier
                       where the amp multiplier compounds Dec-DEF × Weaken ×
                       Inc-ATK × Inc-CR/CD. Credited ONLY if a hit engine is
                       present. A Weaken amp NEVER helps a poison engine.
    • poison channel : poison-stack count (toward the 10-cap) × Poison-Sens.
                       Credited ONLY if a poison engine is present.
    • hp_burn channel: flat value (cap 1 burn per M3) + dot_detonate bonus.
                       Amplified by neither Dec-DEF/Weaken nor Poison-Sens.

  survival_multiplier — survival/control FLOOR: a comp lacking any
    survival_currency is multiplicatively penalized, scaled by location
    lethality (CB hard, arena soft). A keystone that needs an enabler
    (keystone_needs_enabler) is rewarded when a compatible enabler is present
    and penalized when it is missing.

  control_score — value of CC/TM effects, ZEROED for any effect the boss
    no-ops (M3 is_effect_useful → Stun/TM on CB = 0, but high on arena).

  penalties — boss-script: DoT-vs-boss reactions (Ice Golem poison-immune →
    poison channel zeroed + penalty; HP-Burn +10% bonus), and ACC-floor
    shortfall when the caller supplies the team's ACC capability.
"""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import boss_constraints  # noqa: E402  (tools/ on path)

from . import synergy_data as sd

# --------------------------------------------------------------------------- #
# Per-location lethality (how much survival matters). 1.0 = a missed cover is
# a wipe (CB / clash bosses); low = a race where you rarely die (arena/FW).
# --------------------------------------------------------------------------- #
LETHALITY = {
    "clan_boss": 1.00,
    "hydra": 0.90,
    "chimera": 0.90,
    "nether_spider": 0.85,
    "magma_dragon": 0.80,
    "frost_spider": 0.80,
    "eternal_dragon": 0.80,
    "scarab_king": 0.80,
    "celestial_griffin": 0.80,
    "dark_fae": 0.80,
    "dragon": 0.60,
    "spider": 0.60,
    "fire_knight": 0.60,
    "ice_golem": 0.60,
    "faction_wars": 0.50,
    "arena": 0.40,
}
DEFAULT_LETHALITY = 0.60

# Tunables (transparent; every one shows up in the breakdown).
BASE_HIT_ENGINE = 1.00       # value per hit/wm_gs/bring_it_down engine hero
BASE_POISON_UNIT = 0.50      # value per poison stack (×Poison-Sens)
POISON_STACK_CAP = 10        # M3 slot cap
POISON_SENS_BONUS = 0.50     # +50% poison damage when Poison-Sensitivity present
BASE_HP_BURN = 1.50          # flat hp_burn value (cap 1 burn per target)
DOT_DETONATE_BONUS = 0.50    # bonus when a detonator is present for a DoT engine
CONTROL_PER_EFFECT = 0.50    # value per distinct USEFUL control effect
SURVIVAL_SATURATION = 1.00   # survival_value at which the floor is fully lifted
KEYSTONE_MATCH_BONUS = 1.15  # survival ×= this when keystone enabler satisfied
KEYSTONE_MISS_PENALTY = 0.75  # survival ×= this when keystone enabler missing
NO_SURVIVAL_FLOOR_MIN = 0.15  # survival_multiplier floor on a fully lethal loc


def _loc_lethality(loc_key: str | None, context: dict) -> float:
    if "lethality" in context:
        return float(context["lethality"])
    return LETHALITY.get(loc_key, DEFAULT_LETHALITY)


def _resolve_boss_key(location: str) -> str | None:
    """Map `location` onto a boss_constraints canonical key (or None)."""
    try:
        boss_constraints.get_constraints(location)
        # get_constraints resolves aliases internally; recover the canon key.
        key = str(location).strip().lower().replace("-", "_").replace(" ", "_")
        if key in boss_constraints.list_locations():
            return key
        for canon in boss_constraints.list_locations():
            rec = boss_constraints.get_constraints(canon)
            aliases = [a.lower() for a in (rec.get("aliases") or [])]
            if key == canon or key in aliases:
                return canon
        return key
    except KeyError:
        return None


# --------------------------------------------------------------------------- #
# Channel scorers
# --------------------------------------------------------------------------- #
def _score_hit_channel(recs: list[dict]) -> dict:
    engines = [r["name"] for r in recs if sd.has_hit_engine(r)]
    amp_types: set[str] = set()
    amp_providers: dict[str, list[str]] = {}
    for r in recs:
        for t in sd.hit_amplifier_types(r):
            amp_types.add(t)
            amp_providers.setdefault(t, []).append(r["name"])

    multiplier = 1.0
    for t in amp_types:
        multiplier *= (1.0 + sd.HIT_AMPLIFIER_WEIGHTS[t])

    present = bool(engines)
    # Channel rule: amps ONLY pay out when a hit engine exists.
    score = (BASE_HIT_ENGINE * len(engines) * multiplier) if present else 0.0
    return {
        "present": present,
        "engines": engines,
        "amplifier_types": sorted(amp_types),
        "amplifier_providers": amp_providers,
        "amplifier_multiplier": round(multiplier, 4),
        "score": round(score, 4),
    }


def _score_poison_channel(recs: list[dict], poison_immune: bool) -> dict:
    engines = [r["name"] for r in recs if sd.has_poison_engine(r)]
    stacks = sum(sd.poison_stack_contribution(r) for r in recs)
    stacks_capped = min(stacks, POISON_STACK_CAP)
    sens_providers = [r["name"] for r in recs if sd.is_poison_sensitivity(r)]
    sens_mult = 1.0 + (POISON_SENS_BONUS if sens_providers else 0.0)
    detonators = [r["name"] for r in recs if sd.has_dot_detonate(r)]

    present = bool(engines)
    score = 0.0
    if present and not poison_immune:
        score = BASE_POISON_UNIT * stacks_capped * sens_mult
        if detonators:
            score *= (1.0 + DOT_DETONATE_BONUS)
    return {
        "present": present,
        "engines": engines,
        "stacks_raw": stacks,
        "stacks_capped": stacks_capped,
        "poison_sensitivity": sens_providers,
        "sensitivity_multiplier": round(sens_mult, 4),
        "detonators": detonators,
        "boss_poison_immune": poison_immune,
        "score": round(score, 4),
    }


def _score_hp_burn_channel(recs: list[dict], hp_burn_bonus_pct: float) -> dict:
    engines = [r["name"] for r in recs if sd.has_hp_burn_engine(r)]
    detonators = [r["name"] for r in recs if sd.has_dot_detonate(r)]
    present = bool(engines)
    score = 0.0
    if present:
        # Cap 1 HP Burn per target (M3): one burn's worth of value regardless
        # of how many burners are stacked.
        score = BASE_HP_BURN
        if detonators:
            score += DOT_DETONATE_BONUS
        if hp_burn_bonus_pct:
            score *= (1.0 + hp_burn_bonus_pct / 100.0)
    return {
        "present": present,
        "engines": engines,
        "detonators": detonators,
        "boss_bonus_pct": hp_burn_bonus_pct,
        "score": round(score, 4),
    }


# --------------------------------------------------------------------------- #
# Survival / control
# --------------------------------------------------------------------------- #
def _score_survival(recs: list[dict], lethality: float) -> dict:
    contributors = {r["name"]: sd.survival_weight(r)
                    for r in recs if r.get("survival_currency")}
    survival_value = sum(contributors.values())

    enablers_present = {r["enabler"] for r in recs if r.get("enabler")}
    keystones = []
    keystone_factor = 1.0
    for r in recs:
        if r.get("keystone_needs_enabler") and r.get("survival_currency"):
            compat = sd.KEYSTONE_ENABLER_COMPAT.get(r["survival_currency"], set())
            matched = sorted(enablers_present & compat)
            keystones.append({
                "hero": r["name"],
                "currency": r["survival_currency"],
                "needs_any_of": sorted(compat),
                "matched_by": matched,
                "satisfied": bool(matched),
            })
            keystone_factor *= (KEYSTONE_MATCH_BONUS if matched
                                else KEYSTONE_MISS_PENALTY)

    # Floor: on a fully lethal location, no survival → NO_SURVIVAL_FLOOR_MIN;
    # on a soft location the floor is much higher (survival barely matters).
    floor = 1.0 - (1.0 - NO_SURVIVAL_FLOOR_MIN) * lethality
    coverage = min(1.0, survival_value / SURVIVAL_SATURATION)
    multiplier = floor + (1.0 - floor) * coverage
    multiplier *= keystone_factor

    return {
        "contributors": contributors,
        "survival_value": round(survival_value, 4),
        "lethality": lethality,
        "floor": round(floor, 4),
        "coverage": round(coverage, 4),
        "keystones": keystones,
        "keystone_factor": round(keystone_factor, 4),
        "multiplier": round(multiplier, 4),
    }


def _score_control(recs: list[dict], location: str, boss_key: str | None) -> dict:
    effects: set[str] = set()
    for r in recs:
        effects |= sd.control_tags(r)
    useful, no_op = [], []
    for eff in sorted(effects):
        usable = True
        if boss_key is not None:
            try:
                usable = boss_constraints.is_effect_useful(location, eff)
            except KeyError:
                usable = True
        (useful if usable else no_op).append(eff)
    score = CONTROL_PER_EFFECT * len(useful)
    return {
        "effects_present": sorted(effects),
        "useful": useful,
        "no_op_vs_boss": no_op,
        "score": round(score, 4),
    }


# --------------------------------------------------------------------------- #
# Public entry
# --------------------------------------------------------------------------- #
def heuristic_score(recs: list[dict], location: str, context: dict) -> dict:
    """Score a comp (list of normalized M1 records) at `location`.

    Returns {fitness, kind:"heuristic", breakdown:{...}}.
    """
    context = context or {}
    boss_key = _resolve_boss_key(location)
    lethality = _loc_lethality(boss_key, context)

    # M3 DoT-vs-boss reactions.
    poison_immune = False
    hp_burn_bonus_pct = 0.0
    dot_rx = {}
    if boss_key is not None:
        try:
            dot_rx = boss_constraints.dot_reactions(location) or {}
        except KeyError:
            dot_rx = {}
        poison_immune = bool(dot_rx.get("poison_immune")) or \
            ("immun" in str(dot_rx.get("poison", "")).lower())
        hp_burn_bonus_pct = float(dot_rx.get("hp_burn_bonus_pct") or 0.0)

    hit = _score_hit_channel(recs)
    poison = _score_poison_channel(recs, poison_immune)
    hp_burn = _score_hp_burn_channel(recs, hp_burn_bonus_pct)
    damage_score = hit["score"] + poison["score"] + hp_burn["score"]

    survival = _score_survival(recs, lethality)
    control = _score_control(recs, location, boss_key)

    # --- penalties --------------------------------------------------------- #
    penalties: dict[str, float] = {}
    if poison_immune and poison["present"]:
        # Bringing a poison engine to a poison-immune boss is a wasted slot.
        penalties["poison_immune_boss"] = round(
            BASE_POISON_UNIT * poison["stacks_capped"], 4)

    acc_floor = None
    if boss_key is not None:
        try:
            acc_floor = boss_constraints.acc_floor(location)
        except KeyError:
            acc_floor = None
    acc_note = None
    team_acc = context.get("team_acc")  # caller-supplied ACC capability
    if acc_floor and team_acc is not None:
        # Number of debuff-reliant heroes that must actually land.
        debuffers = [r["name"] for r in recs
                     if any(p.startswith("enemy_debuff:") for p in r.get("provides", []))]
        if team_acc < acc_floor and debuffers:
            shortfall = (acc_floor - team_acc) / 100.0
            penalties["acc_floor_shortfall"] = round(
                shortfall * len(debuffers), 4)
    elif acc_floor and context.get("team_acc") is None:
        acc_note = (f"acc_floor={acc_floor} but team ACC capability unknown "
                    f"(pass context['team_acc']) — no ACC penalty applied")

    penalty_total = sum(penalties.values())

    fitness = (damage_score + control["score"]) * survival["multiplier"] \
        - penalty_total

    breakdown = {
        "location": location,
        "boss_key": boss_key,
        "lethality": lethality,
        "channels": {"hit": hit, "poison": poison, "hp_burn": hp_burn},
        "damage_score": round(damage_score, 4),
        "survival": survival,
        "control": control,
        "penalties": penalties,
        "penalty_total": round(penalty_total, 4),
        "dot_reactions": dot_rx,
        "acc_floor": acc_floor,
        "notes": [n for n in (acc_note,) if n],
        "missing_records": context.get("_missing_records", []),
    }
    return {"fitness": round(fitness, 4), "kind": "heuristic",
            "breakdown": breakdown}
