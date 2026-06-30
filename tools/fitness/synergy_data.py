"""Fitness substrate loader — reads M1 enriched per-hero records.

This is the read-only data layer for the M5 fitness package. It loads
`data/m5_synergy.jsonl` (M1 tags) into a name->record lookup and exposes a
handful of safe accessors + tag classifiers that the heuristic scorer uses.

The M1 record (see docs/organic_team_m2_m4_spec.md §0.1):
    name, base_id, element, rarity, fraction, game_role, synergy_role,
    provides[], needs[], debuffs_control_only,
    amplifier_channel ∈ {hit, poison, none},
    engine_channel: list ⊂ {hit, wm_gs, poison, hp_burn, bring_it_down},
    survival_currency ∈ {unkillable, block_damage, shield, revive_on_death,
                         ally_protect, heal_lifesteal, none/None},
    enabler ∈ {cooldown_reduction, buff_extension, none/None},
    keystone_needs_enabler: bool

All accessors tolerate records missing M1 fields (safe defaults) so a partial
record (or a synthetic one injected by a test/caller) still scores.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SYNERGY_PATH = ROOT / "data" / "m5_synergy.jsonl"

# --------------------------------------------------------------------------- #
# Channel / currency / enabler vocab (mirrors M1 + spec).
# --------------------------------------------------------------------------- #
HIT_ENGINE_CHANNELS = {"hit", "wm_gs", "bring_it_down"}
POISON_ENGINE_CHANNEL = "poison"
HP_BURN_ENGINE_CHANNEL = "hp_burn"

# Hit-channel amplifier TYPES (game-truth: these compound multiplicatively —
# Dec-DEF × Weaken × Inc-ATK × Inc-CR/CD all stack on a hit/wm_gs engine).
#   key -> (provides-tag predicate, multiplier weight)
HIT_AMPLIFIER_WEIGHTS = {
    "def_down": 0.50,   # enemy_debuff:Decrease DEF
    "weaken": 0.25,     # enemy_debuff:Weaken
    "inc_atk": 0.25,    # team_buff:Increase ATK
    "inc_crit": 0.35,   # team_buff:Increase C. RATE / C. DMG
}

# Survival-currency value weights (how much "stay-alive" each provides).
SURVIVAL_WEIGHTS = {
    "unkillable": 1.00,
    "block_damage": 0.85,
    "shield": 0.65,
    "revive_on_death": 0.60,
    "ally_protect": 0.55,
    "heal_lifesteal": 0.40,
}

# keystone_needs_enabler compatibility (spec M2 §edge-case 2).
KEYSTONE_ENABLER_COMPAT = {
    "unkillable": {"cooldown_reduction", "buff_extension"},
    "block_damage": {"cooldown_reduction", "buff_extension"},
    "shield": {"cooldown_reduction", "buff_extension"},
    "heal_lifesteal": {"cooldown_reduction", "buff_extension"},
    "revive_on_death": {"cooldown_reduction"},
    "ally_protect": {"cooldown_reduction"},
}

# provides-tag -> canonical control/effect tag (consumed by
# boss_constraints.is_effect_useful). Lets us zero-value control on bosses
# that no-op it (CB) while keeping it on PvP (arena).
CONTROL_PROVIDES_TO_TAG = {
    "tm_control": "turn_meter",
    "tm_drain": "turn_meter",
    "enemy_debuff:Stun": "stun",
    "enemy_debuff:Freeze": "freeze",
    "enemy_debuff:Sleep": "sleep",
    "enemy_debuff:Provoke": "provoke",
    "enemy_debuff:Fear": "fear",
    "enemy_debuff:True Fear": "fear",
    "enemy_debuff:Petrification": "petrification",
    "enemy_debuff:Sheep": "polymorph",
    "enemy_debuff:Decrease SPD": "dec_spd",
}

_cache: dict[str, dict] | None = None


def _load() -> dict[str, dict]:
    global _cache
    if _cache is None:
        recs: dict[str, dict] = {}
        with SYNERGY_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                recs[r["name"]] = r
        _cache = recs
    return _cache


def get_record(name: str, override: dict | None = None) -> dict | None:
    """Return the M1 record for `name`.

    `override` (caller/test-supplied) wins over the on-disk record and may
    fully synthesize a hero that isn't in m5_synergy.jsonl. Missing M1 fields
    are filled with safe defaults so the scorer never KeyErrors.
    """
    if override is not None and name in override:
        rec = dict(override[name])
    else:
        rec = _load().get(name)
        if rec is None:
            return None
        rec = dict(rec)
    return _normalize(rec)


def _normalize(rec: dict) -> dict:
    rec.setdefault("name", "?")
    rec.setdefault("provides", [])
    rec.setdefault("needs", [])
    # amplifier_channel: str or absent
    ac = rec.get("amplifier_channel")
    rec["amplifier_channel"] = (ac or "none").lower()
    # engine_channel: list (tolerate scalar / None)
    ec = rec.get("engine_channel")
    if ec is None:
        ec = []
    elif isinstance(ec, str):
        ec = [ec]
    rec["engine_channel"] = [str(e).lower() for e in ec]
    # survival_currency / enabler: None or "none" both mean absent
    sc = rec.get("survival_currency")
    rec["survival_currency"] = sc if (sc and str(sc).lower() != "none") else None
    en = rec.get("enabler")
    rec["enabler"] = en if (en and str(en).lower() != "none") else None
    rec["keystone_needs_enabler"] = bool(rec.get("keystone_needs_enabler"))
    return rec


# --------------------------------------------------------------------------- #
# Per-record classifiers
# --------------------------------------------------------------------------- #
def has_provide(rec: dict, tag: str) -> bool:
    return tag in rec.get("provides", [])


def hit_amplifier_types(rec: dict) -> set[str]:
    """Which hit-channel amplifier TYPES this hero supplies.

    Sourced from provides tags (Dec-DEF / Weaken / Inc-ATK / Inc-CR/CD). The
    M1 `amplifier_channel=="hit"` flag corroborates Dec-DEF/Weaken but the
    team-buff amps (Inc-ATK / Inc-CR/CD) live only in provides — per the spec
    'count from amplifier_channel=="hit" + team_buff tags'.
    """
    prov = set(rec.get("provides", []))
    types: set[str] = set()
    if "enemy_debuff:Decrease DEF" in prov:
        types.add("def_down")
    if "enemy_debuff:Weaken" in prov:
        types.add("weaken")
    if "team_buff:Increase ATK" in prov:
        types.add("inc_atk")
    if "team_buff:Increase C. RATE" in prov or "team_buff:Increase C. DMG" in prov:
        types.add("inc_crit")
    return types


def is_poison_sensitivity(rec: dict) -> bool:
    """Poison-channel amplifier (Poison Sensitivity)."""
    return rec.get("amplifier_channel") == "poison"


def poison_stack_contribution(rec: dict) -> int:
    """Rough poison-stacks this hero pushes toward the per-target cap.

    A dedicated poison applier (dot:Poison) contributes ~2 stacks; an
    `enables:poison` extender adds 1 more. Heuristic proxy only — the exact
    count is speed/turn dependent (resolved by M2, not here).
    """
    prov = set(rec.get("provides", []))
    n = 0
    if "dot:Poison" in prov:
        n += 2
    if "enables:poison" in prov:
        n += 1
    return n


def has_hp_burn_engine(rec: dict) -> bool:
    return HP_BURN_ENGINE_CHANNEL in rec.get("engine_channel", [])


def has_poison_engine(rec: dict) -> bool:
    return POISON_ENGINE_CHANNEL in rec.get("engine_channel", [])


def has_hit_engine(rec: dict) -> bool:
    return bool(HIT_ENGINE_CHANNELS & set(rec.get("engine_channel", [])))


def has_dot_detonate(rec: dict) -> bool:
    return has_provide(rec, "dot_detonate")


def control_tags(rec: dict) -> set[str]:
    """Canonical control/effect tags this hero supplies (for is_effect_useful)."""
    tags: set[str] = set()
    for prov in rec.get("provides", []):
        canon = CONTROL_PROVIDES_TO_TAG.get(prov)
        if canon:
            tags.add(canon)
    return tags


def survival_weight(rec: dict) -> float:
    sc = rec.get("survival_currency")
    return SURVIVAL_WEIGHTS.get(sc, 0.0) if sc else 0.0
