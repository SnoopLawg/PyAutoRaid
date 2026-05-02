"""Generic effect translator — data-driven, no per-skill conditionals.

Goal: replace the ~10 `if skill_id == X` / `if name == "Y"` branches
in load_game_profiles.py with handlers keyed on EffectKindId + Condition
that read parameters from static data.

Pattern:
    raw_effect (skills_all.json)  →  GenericEffect (this module)  →  cb_sim handler

Each `GenericEffect` carries the same shape regardless of which hero
or skill it came from. Adding a new hero = no code change, just
re-run `tools/refresh_static_data.py`.

Authoritative data sources (per `feedback_sim_ground_truth_not_back_fit`):
- `data/static/skills_all.json` — Effect.KindId, Count, MultiplierFormula,
  Condition, Chance, ApplyStatusEffectParams, ChangeEffectLifetimeParams
- `data/static/effects.json` — effect prototypes (Family, StackCount)
- `data/static/effect_kind_id.json` — KindId enum value mapping

Extracted-on-import: `EFFECT_KIND_BY_NAME` etc. so consumers can
reference effect kinds by name without re-parsing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# =============================================================================
# Enum mappings — loaded once at import.
# =============================================================================

def _load_enum(name: str) -> dict[int, str]:
    """Load an enum dump from data/static and return {value: name}."""
    p = PROJECT_ROOT / "data" / "static" / f"{name}.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[int, str] = {}
    for entry in raw.get("values", []):
        out[entry["value"]] = entry["name"]
    return out


EFFECT_KIND_BY_VAL: dict[int, str] = _load_enum("effect_kind_id")
EFFECT_KIND_BY_NAME: dict[str, int] = {v: k for k, v in EFFECT_KIND_BY_VAL.items()}
STATUS_EFFECT_BY_VAL: dict[int, str] = _load_enum("status_effect_type_id")
STATUS_EFFECT_BY_NAME: dict[str, int] = {v: k for k, v in STATUS_EFFECT_BY_VAL.items()}


# =============================================================================
# GenericEffect — the shape every sim consumer sees, regardless of source.
# =============================================================================

@dataclass
class GenericEffect:
    """Game-data-derived effect descriptor for the sim.

    Hero-agnostic: built purely from `skills_all.json` static data plus
    a small set of parsed condition tags. The cb_sim dispatcher routes
    on `kind_id` (e.g. ApplyDebuff, Damage, ForceStatusEffectTick).
    """
    skill_id: int
    effect_index: int      # position within the skill's Effects[] array
    kind_id: str           # "Damage", "ApplyDebuff", "ForceStatusEffectTick", ...
    count: int = 1         # how many times this effect fires per skill use
    chance: float = 1.0    # 0..1 — read from Effect.Chance.value (or default 1.0)
    multiplier_formula: str = ""    # raw formula string, e.g. "0.04*TRG_HP"
    condition: str = ""    # raw condition string for routing
    target_type: str = ""  # "Target", "AllAllies", "AllEnemies", ...

    # Status-effect placement (when KindId == ApplyDebuff / ApplyBuff /
    # ApplyOrProlongDebuff). Each entry: (StatusEffectTypeId, duration).
    applied_status_effects: list[tuple[int, int]] = field(default_factory=list)

    # ChangeEffectLifetimeParams (IncreaseBuffLifetime,
    # IncreaseDebuffLifetime, ReduceDebuffLifetime, etc.)
    lifetime_change_count: int = 0       # +N or -N turns
    lifetime_change_type: str = ""       # "Buff" / "Debuff"
    lifetime_change_effect_kinds: list[str] = field(default_factory=list)
    lifetime_change_turns_formula: str = ""

    # ForceStatusEffectTickParams (kind=ForceStatusEffectTick / 9002).
    # `EffectTypeIds` is the list of in-game effect type names this skill
    # activates ("Burn" = HP Burn, "ContinuousDamage025p" = 2.5% Poison,
    # "ContinuousDamage5p" = 5% Poison). `Ticks` = activations per fire.
    # `EffectCount` = -1 for unbounded ("all"), or a positive cap.
    force_tick_effect_type_ids: list[str] = field(default_factory=list)
    force_tick_count: int = -1   # -1 means "all matching"
    force_ticks: int = 1

    # DamageParams (kind=Damage). `def_modifier` is the IgnoreDefense
    # multiplier (e.g. -0.5 = "ignore 50% of target DEF"). 0.0 means
    # no DEF modification on this damage effect. `is_fixed_damage`
    # signals "ignores DEF entirely" (rare, e.g. Demytha A3 fixed dmg).
    damage_def_modifier: float = 0.0
    damage_is_fixed: bool = False

    # Parsed convenience fields derived from condition + kind_id, not
    # raw. Empty string if not applicable.
    activates_dot_kind: str = ""    # "Burn" / "Poison" / "All" — for kind=9002


# =============================================================================
# Static data loaders — cached once at import.
# =============================================================================

_SKILLS_BY_ID_CACHE: Optional[dict[int, dict]] = None


def skills_by_id() -> dict[int, dict]:
    """Lazy-load skills static data keyed by skill ID.

    Prefers per-skill depth=4 entries from `skills_d4.json` (populated by
    `tools/refresh_skills_d4.py` for sim-relevant heroes) since the inner
    parameter blocks (ForceTickParams, ChangeEffectLifetimeParams,
    ApplyStatusEffectParams) are only fully expanded at depth>=4. Falls
    back to the depth=3 bulk dump (`skills_all.json`) for skills not in
    the d4 cache.
    """
    global _SKILLS_BY_ID_CACHE
    if _SKILLS_BY_ID_CACHE is not None:
        return _SKILLS_BY_ID_CACHE
    cache: dict[int, dict] = {}
    # Depth=3 bulk first — covers all ~5400 skills shallowly.
    p3 = PROJECT_ROOT / "data" / "static" / "skills_all.json"
    if p3.exists():
        raw = json.loads(p3.read_text(encoding="utf-8"))
        arr = raw.get("data") if isinstance(raw, dict) else raw
        for s in arr or []:
            if isinstance(s, dict) and "Id" in s:
                cache[s["Id"]] = s
    # Depth=4 supplement overrides — sim-relevant heroes only.
    p4 = PROJECT_ROOT / "data" / "static" / "skills_d4.json"
    if p4.exists():
        d4 = json.loads(p4.read_text(encoding="utf-8"))
        for sid_str, s in d4.items():
            if isinstance(s, dict) and "Id" in s:
                try:
                    cache[int(sid_str)] = s
                except (TypeError, ValueError):
                    continue
    _SKILLS_BY_ID_CACHE = cache
    return _SKILLS_BY_ID_CACHE


# =============================================================================
# Condition-string parsing — turns game expression into routing tags.
# =============================================================================

# Matches "RelationTargetHasEffectOfKind(<EffectKindId>_KindId)" or
# "RelationTargetHasEffectOfKindPlacedByProducer(<EffectKindId>_KindId)" —
# tells us which DoT family the effect activates.
_RE_HAS_EFFECT_OF_KIND = re.compile(
    r"RelationTargetHasEffectOfKind(?:PlacedByProducer)?\(([A-Za-z]+)_KindId\)"
)


def parse_dot_activation_target(condition: str) -> str:
    """For ForceStatusEffectTick (kind=9002) effects, the Condition tells
    us which DoT to activate. Returns one of:
      "Burn"  — AoEContinuousDamage (HP Burn)
      "Poison" — ContinuousDamage
      "All"   — both (when condition has || operator)
      ""      — unconditional or unrecognized

    Example conditions:
      "RelationTargetHasEffectOfKind(ContinuousDamage_KindId)" → Poison
      "RelationTargetHasEffectOfKind(AoEContinuousDamage_KindId)" → Burn
      "ContinuousDamage_KindId)||RelationTargetHasEffectOfKind(AoEContinuousDamage_KindId)" → All
    """
    if not condition:
        return ""
    matches = _RE_HAS_EFFECT_OF_KIND.findall(condition)
    if not matches:
        return ""
    kinds = set(m for m in matches)
    has_burn = "AoEContinuousDamage" in kinds
    has_poison = "ContinuousDamage" in kinds
    if has_burn and has_poison:
        return "All"
    if has_burn:
        return "Burn"
    if has_poison:
        return "Poison"
    return ""


# =============================================================================
# Effect normalization — game data → GenericEffect
# =============================================================================

def _read_chance(effect_dict: dict) -> float:
    """Extract Effect.Chance.value as a 0..1 float, or 1.0 if no chance.

    Game stores chance as a Nullable<Fixed>:
      {"hasValue": false, ...}        → 1.0 (unconditional)
      {"hasValue": true, "value": 0.469} → 0.469
      {"hasValue": true, "value": 469.195} → 0.469 (per-mille; divide by 1000)

    Some skills' chance values are scaled to per-mille (469.195 = 46.9%).
    Detect by magnitude: if >1.0, assume per-mille and divide.
    """
    chance = effect_dict.get("Chance")
    if chance is None:
        return 1.0
    if isinstance(chance, str):
        # Placeholder string like "<Nullable>" from shallow export
        return 1.0
    if isinstance(chance, dict):
        if not (chance.get("hasValue") or chance.get("HasValue")):
            return 1.0
        v = chance.get("value")
        if v is None:
            v = chance.get("Value")
        if v is None:
            return 1.0
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 1.0
        # Per-mille detection — game stores some chances as 0..1000
        if v > 1.0:
            return v / 1000.0
        return v
    # Direct numeric (shouldn't happen but be defensive)
    try:
        v = float(chance)
        return v / 1000.0 if v > 1.0 else v
    except (TypeError, ValueError):
        return 1.0


def _read_target_type(effect_dict: dict) -> str:
    """Extract TargetType — string at top level OR nested in TargetParams."""
    tt = effect_dict.get("TargetType")
    if isinstance(tt, str):
        return tt
    tp = effect_dict.get("TargetParams")
    if isinstance(tp, dict):
        return tp.get("TargetType", "")
    return ""


def _read_applied_status_effects(effect_dict: dict) -> list[tuple[int, int]]:
    """Extract ApplyStatusEffectParams.StatusEffectInfos[].(TypeId, Duration)."""
    out: list[tuple[int, int]] = []
    asep = effect_dict.get("ApplyStatusEffectParams")
    if not isinstance(asep, dict):
        return out
    sei = asep.get("StatusEffectInfos")
    if not isinstance(sei, list):
        return out
    for entry in sei:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("TypeId")
        dur = entry.get("Duration")
        if tid is None:
            continue
        try:
            tid_int = int(tid)
            dur_int = int(dur) if dur is not None else 0
            out.append((tid_int, dur_int))
        except (TypeError, ValueError):
            continue
    return out


def _read_lifetime_change(effect_dict: dict) -> tuple[int, str, list[str], str]:
    """Extract ChangeEffectLifetimeParams.

    Returns (count, type, effect_kinds, turns_formula). `count` is the
    multiplier on `turns_formula` — sometimes -1 means "all matching".
    `effect_kinds` lists which effect type names this affects ("Burn",
    "ContinuousDamage025p", etc.); empty list = all debuffs/buffs of the
    declared `type`.
    """
    p = effect_dict.get("ChangeEffectLifetimeParams")
    if not isinstance(p, dict):
        return 0, "", [], ""
    try:
        count = int(p.get("Count", 0) or 0)
    except (TypeError, ValueError):
        count = 0
    type_ = str(p.get("Type", "") or "")
    eids = p.get("EffectTypeIds") or []
    if not isinstance(eids, list):
        eids = []
    eids = [str(x) for x in eids if isinstance(x, (str, int))]
    turns_formula = str(p.get("TurnsFormula", "") or "")
    return count, type_, eids, turns_formula


def _read_damage_params(effect_dict: dict) -> tuple[float, bool]:
    """Extract DamageParams.{DefenceModifier, IsFixed}.

    Returns (def_modifier, is_fixed). `def_modifier` is negative for
    "ignore X% of target DEF" — e.g. -0.5 for Ninja A3 vs Boss.
    """
    p = effect_dict.get("DamageParams")
    if not isinstance(p, dict):
        # Sometimes appears under the SharedModel-prefixed alias only
        p = effect_dict.get("SharedModel.Battle.AI.IAiEffect.DamageParams")
        if not isinstance(p, dict):
            return 0.0, False
    try:
        dm = float(p.get("DefenceModifier", 0) or 0)
    except (TypeError, ValueError):
        dm = 0.0
    return dm, bool(p.get("IsFixed", False))


def _read_force_tick_params(effect_dict: dict) -> tuple[list[str], int, int]:
    """Extract ForceStatusEffectTickParams.

    Returns (effect_type_ids, effect_count, ticks). EffectCount = -1
    means "activate all matching DoTs"; positive = cap (e.g. Venomage A1
    has EffectCount=2, "up to 2 poisons").
    """
    p = effect_dict.get("ForceTickParams")
    if not isinstance(p, dict):
        return [], -1, 1
    eids = p.get("EffectTypeIds") or []
    if not isinstance(eids, list):
        eids = []
    eids = [str(x) for x in eids if isinstance(x, (str, int))]
    try:
        cnt = int(p.get("EffectCount", -1))
    except (TypeError, ValueError):
        cnt = -1
    try:
        ticks = int(p.get("Ticks", 1))
    except (TypeError, ValueError):
        ticks = 1
    return eids, cnt, ticks


def classify_dot_family(effect_type_ids: list[str]) -> str:
    """Map a list of in-game effect type names → simulator DoT family.

    "Burn"/"AoEContinuousDamage*" → Burn family
    "ContinuousDamage*" → Poison family
    Both present → All
    """
    if not effect_type_ids:
        return ""
    has_burn = any(s == "Burn" or s.startswith("AoEContinuousDamage")
                   for s in effect_type_ids)
    has_poison = any(s.startswith("ContinuousDamage") for s in effect_type_ids)
    if has_burn and has_poison:
        return "All"
    if has_burn:
        return "Burn"
    if has_poison:
        return "Poison"
    return ""


def normalize_skill_effects(skill_id: int) -> list[GenericEffect]:
    """Return all effects of `skill_id` as GenericEffect objects.

    No per-skill conditionals — pure data extraction. Returns an empty
    list if the skill is not in the static export.
    """
    skill = skills_by_id().get(skill_id)
    if not skill:
        return []
    out: list[GenericEffect] = []
    for idx, eff in enumerate(skill.get("Effects") or []):
        if not isinstance(eff, dict):
            continue
        cond = eff.get("Condition") or ""
        kind = eff.get("KindId") or ""
        ge = GenericEffect(
            skill_id=skill_id,
            effect_index=idx,
            kind_id=kind,
            count=int(eff.get("Count") or 1),
            chance=_read_chance(eff),
            multiplier_formula=eff.get("MultiplierFormula") or "",
            condition=cond,
            target_type=_read_target_type(eff),
            applied_status_effects=_read_applied_status_effects(eff),
        )
        ltc, ltt, lt_kinds, lt_formula = _read_lifetime_change(eff)
        ge.lifetime_change_count = ltc
        ge.lifetime_change_type = ltt
        ge.lifetime_change_effect_kinds = lt_kinds
        ge.lifetime_change_turns_formula = lt_formula
        ft_ids, ft_cnt, ft_ticks = _read_force_tick_params(eff)
        ge.force_tick_effect_type_ids = ft_ids
        ge.force_tick_count = ft_cnt
        ge.force_ticks = ft_ticks
        dp_dm, dp_fixed = _read_damage_params(eff)
        ge.damage_def_modifier = dp_dm
        ge.damage_is_fixed = dp_fixed
        if kind == "ForceStatusEffectTick":
            # Prefer ForceTickParams.EffectTypeIds (depth=4 truth) over
            # the Condition string (which is only a gate, not the target).
            if ft_ids:
                ge.activates_dot_kind = classify_dot_family(ft_ids)
            else:
                ge.activates_dot_kind = parse_dot_activation_target(cond)
        out.append(ge)
    return out


# =============================================================================
# Sim-level dispatch helpers — turn GenericEffects into sim effect dicts
# without per-skill-id conditionals.
# =============================================================================

# These are the dotnet KindId enum *names* used by the static export
# (matching `data/static/effect_kind_id.json`). Keeping them as strings
# avoids the consumer needing the enum file.
KIND_FORCE_TICK = "ForceStatusEffectTick"
KIND_INCREASE_DEBUFF_LIFETIME = "IncreaseDebuffLifetime"
KIND_REDUCE_DEBUFF_LIFETIME = "ReduceDebuffLifetime"
KIND_INCREASE_BUFF_LIFETIME = "IncreaseBuffLifetime"
KIND_REDUCE_BUFF_LIFETIME = "ReduceBuffLifetime"


def classify_extend_debuff(eff: GenericEffect) -> dict | None:
    """For an IncreaseDebuffLifetime effect, return a sim-friendly dict.

    Routes by `lifetime_change_effect_kinds` — no skill_id branching.
        ['Burn']                        → extend_debuffs_hp_burn
        ['ContinuousDamage025p', '5p']  → extend_debuffs_poison
        ['Burn', 'Continuous*']         → extend_debuffs_poison_burn
        []  (unrestricted)              → extend_debuffs (all)

    Returns None if the effect isn't a debuff lifetime extension.
    """
    if eff.kind_id != KIND_INCREASE_DEBUFF_LIFETIME:
        return None
    family = classify_dot_family(eff.lifetime_change_effect_kinds)
    if family == "Burn":
        sim_type = "extend_debuffs_hp_burn"
    elif family == "Poison":
        sim_type = "extend_debuffs_poison"
    elif family == "All":
        sim_type = "extend_debuffs_poison_burn"
    else:
        sim_type = "extend_debuffs"
    return {
        "sim_type": sim_type,
        "turns": int(eff.lifetime_change_turns_formula or "1") or 1,
        "effect_kinds": list(eff.lifetime_change_effect_kinds),
    }


def classify_activate_dots(eff: GenericEffect) -> dict | None:
    """For a ForceStatusEffectTick effect, return a sim-friendly dict.

    Routes purely by `force_tick_effect_type_ids`:
        ['Burn']                  → activate_hp_burns
        ['ContinuousDamage*']     → activate_poisons (max_count from ForceTickParams.EffectCount)
        ['Burn','Continuous*']    → activate_dots (all)

    Returns None if not a ForceStatusEffectTick.
    """
    if eff.kind_id != KIND_FORCE_TICK:
        return None
    family = classify_dot_family(eff.force_tick_effect_type_ids)
    if family == "Burn":
        sim_type = "activate_hp_burns"
    elif family == "Poison":
        sim_type = "activate_poisons"
    elif family == "All":
        sim_type = "activate_dots"
    else:
        # Couldn't classify — fall back to condition-based parse
        cf = parse_dot_activation_target(eff.condition)
        if cf == "Burn":
            sim_type = "activate_hp_burns"
        elif cf == "Poison":
            sim_type = "activate_poisons"
        elif cf == "All":
            sim_type = "activate_dots"
        else:
            return None
    out: dict[str, Any] = {"sim_type": sim_type, "ticks": eff.force_ticks}
    # `EffectCount=-1` means "all matching"; positive = cap (e.g. Venomage A1: 2)
    if eff.force_tick_count > 0:
        out["max_count"] = eff.force_tick_count
    return out


def classify_extend_buffs(eff: GenericEffect) -> dict | None:
    """For an IncreaseBuffLifetime effect, return a sim-friendly dict.

    Reads turns_formula and effect_kinds. Some compound skills (Demytha A2)
    co-locate Heal alongside this — those need a separate Heal effect
    classifier in the consumer.
    """
    if eff.kind_id != KIND_INCREASE_BUFF_LIFETIME:
        return None
    return {
        "sim_type": "extend_buffs",
        "turns": int(eff.lifetime_change_turns_formula or "1") or 1,
        "effect_kinds": list(eff.lifetime_change_effect_kinds),
    }


# =============================================================================
# CLI for debugging
# =============================================================================

def main() -> int:
    """Inspect a skill's normalized effects."""
    import argparse
    import sys
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill_id", type=int)
    args = ap.parse_args()
    effs = normalize_skill_effects(args.skill_id)
    if not effs:
        print(f"no effects found for skill {args.skill_id}", file=sys.stderr)
        return 1
    print(f"=== Skill {args.skill_id} ({len(effs)} effects) ===")
    for e in effs:
        print(f"  [{e.effect_index}] {e.kind_id}")
        print(f"      count={e.count} chance={e.chance:.3f} target={e.target_type}")
        if e.multiplier_formula:
            print(f"      formula: {e.multiplier_formula}")
        if e.applied_status_effects:
            ses = ", ".join(f"{STATUS_EFFECT_BY_VAL.get(t, str(t))}({t}, {d}T)"
                            for t, d in e.applied_status_effects)
            print(f"      places: {ses}")
        if e.lifetime_change_count or e.lifetime_change_effect_kinds:
            line = (f"      lifetime: count={e.lifetime_change_count} "
                    f"type={e.lifetime_change_type}"
                    f" turns={e.lifetime_change_turns_formula!r}")
            if e.lifetime_change_effect_kinds:
                line += f" kinds={e.lifetime_change_effect_kinds}"
            print(line)
        if e.force_tick_effect_type_ids:
            print(f"      force_tick: ticks={e.force_ticks} "
                  f"count={e.force_tick_count} "
                  f"kinds={e.force_tick_effect_type_ids}")
        if e.condition:
            print(f"      cond: {e.condition[:120]}")
        if e.activates_dot_kind:
            print(f"      -> activates DoT: {e.activates_dot_kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
