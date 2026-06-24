#!/usr/bin/env python3
"""sim_data_facade.py — single import-point for cb_sim's manifest-backed data.

Workstream 1.E + 2 + 3 completion: instead of cb_sim importing five
separate manifests + hand-coded constants, it imports ONE facade that
exposes a clean API over all of them. When the engine refactor is
complete, every `if name == ...` and every hardcoded `0.85` becomes
a facade call.

Wraps:
  - effect_dispatcher.EffectDispatcher          (effect manifest)
  - data/static/damage_pipeline.json            (damage formula constants)
  - data/static/tm_pipeline.json                (Stamina mechanics)
  - data/static/mastery_manifest.json           (mastery proc rules)
  - data/static/boss_skill_manifest.json        (boss skills + enrage)

Stable API designed so future manifest revisions don't break cb_sim.

Usage:
    from sim_data_facade import facade
    facade.effects.is_status_buff(2008)         # True
    facade.damage.hit_type_chance("crit")        # 0.15
    facade.damage.element_multiplier("Disadvantage")  # 0.8
    facade.tm.stamina_per_tick                   # 0.07
    facade.tm.stamina_to_turn                    # 100
    facade.mastery.warmaster_proc()              # dict
    facade.boss.turn_50_bypasses                 # ['BlockDamage', 'Unkillable']
    facade.boss.is_bypassed_at_turn_50("UK")     # True
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "data" / "static"


class _DamageFacade:
    def __init__(self, manifest: dict):
        self._m = manifest

    @property
    def hit_type_chances(self) -> dict:
        return self._m.get("hit_type_chances", {})

    def hit_type_chance(self, kind: str) -> float:
        chances = self.hit_type_chances
        m = {
            "crit": chances.get("base_crit_chance", 0.15),
            "crit_adv": chances.get("crit_advantage_bonus", 0.15),
            "crushing": chances.get("crushing_chance", 0.5),
            "glancing": chances.get("glancing_chance", 0.35),
        }
        return m.get(kind.lower(), 0.0)

    @property
    def hit_type_multipliers(self) -> dict:
        return self._m.get("hit_type_multipliers", {})

    def hit_type_multiplier(self, kind: str) -> float | str:
        return self.hit_type_multipliers.get(kind.capitalize(), 1.0)

    @property
    def normal_hit_base_factor(self) -> float:
        """Empirically captured 0.85 factor applied to Normal hits.
        See cb_constants.py NORMAL_HIT_BASE_FACTOR for derivation."""
        return self._m.get("normal_hit_base_factor", 0.85)

    def element_multiplier(self, relation: str) -> float:
        return self._m.get("element_advantage_multipliers", {}).get(relation, 1.0)

    def element_relation(self, attacker: str, defender: str) -> str:
        return self._m.get("element_matrix", {}).get(attacker, {}).get(defender, "Neutral")

    @property
    def pipeline_steps(self) -> list:
        return self._m.get("damage_pipeline_order", [])

    @property
    def mastery_damage_contributions(self) -> dict:
        return self._m.get("mastery_damage_contributions", {})


class _TMFacade:
    def __init__(self, manifest: dict):
        self._m = manifest

    @property
    def stamina_per_tick(self) -> float:
        return self._m.get("constants", {}).get("StaminaByTick", 0.07)

    @property
    def stamina_to_turn(self) -> int:
        return self._m.get("constants", {}).get("StaminaToTurn", 100)

    def tick_rate_for_threshold(self, tm_threshold: int) -> float:
        """Return per-tick TM gain factor for an arbitrary TM threshold.
        cb_sim uses threshold=1000 → 0.7; calc_parity_sim uses 100 → 0.07."""
        return self.stamina_per_tick * (tm_threshold / self.stamina_to_turn)

    @property
    def tiebreaker_order(self) -> list:
        return self._m.get("tick_scheduler", {}).get("tiebreaker_order", [])

    @property
    def cb_boss_immune_effects(self) -> list:
        return self._m.get("cb_boss_immune_effects", [])


class _MasteryFacade:
    def __init__(self, manifest: dict):
        self._m = manifest
        self._by_id: dict[int, dict] = {
            e["id"]: e for e in manifest.get("masteries", [])
        }

    def get(self, mastery_id: int) -> dict | None:
        return self._by_id.get(mastery_id)

    def warmaster_proc(self) -> dict:
        return (self.get(500161) or {}).get("conditional_proc") or {}

    def giant_slayer_proc(self) -> dict:
        return (self.get(500163) or {}).get("conditional_proc") or {}

    def helmsmasher_proc(self) -> dict:
        return (self.get(500162) or {}).get("conditional_proc") or {}

    def cycle_of_magic_proc(self) -> dict:
        return (self.get(500342) or {}).get("conditional_proc") or {}

    def lasting_gifts_proc(self) -> dict:
        return (self.get(500351) or {}).get("conditional_proc") or {}

    def master_hexer_proc(self) -> dict:
        return (self.get(500354) or {}).get("conditional_proc") or {}

    def proc_chance(self, mastery_id: int) -> float | None:
        m = self.get(mastery_id)
        if not m:
            return None
        proc = m.get("conditional_proc")
        if not proc:
            return None
        return proc.get("chance")


class _BossFacade:
    def __init__(self, manifest: dict):
        self._m = manifest

    @property
    def turn_50_trigger(self) -> int:
        return self._m.get("turn_50_enrage", {}).get("trigger_turn", 50)

    @property
    def turn_50_bypasses(self) -> list:
        return self._m.get("turn_50_enrage", {}).get("bypasses", [])

    @property
    def turn_50_non_bypassed(self) -> list:
        return self._m.get("turn_50_enrage", {}).get("non_bypassed_reductions", [])

    def is_bypassed_at_turn_50(self, effect_name: str) -> bool:
        """Check if a given effect (e.g. 'Unkillable', 'BlockDamage') is
        bypassed by the boss's turn-50 enrage skill."""
        lname = effect_name.lower().replace(" ", "")
        return any(
            lname == b.lower().replace(" ", "")
            for b in self.turn_50_bypasses
        )

    @property
    def damage_ramp_formula(self) -> str:
        return self._m.get("turn_50_enrage", {}).get("damage_ramp_formula", "")

    def get_skill(self, skill_id: int) -> dict | None:
        for s in self._m.get("boss_skills", []):
            if s.get("id") == skill_id:
                return s
        return None


class _BlessingFacade:
    def __init__(self, manifest: dict):
        self._m = manifest
        self._by_id: dict[str, dict] = {
            e["id"]: e for e in manifest.get("blessings", [])
        }

    def get(self, blessing_id: str) -> dict | None:
        return self._by_id.get(blessing_id)

    def brimstone_proc(self) -> dict:
        return (self.get("Brimstone") or {}).get("conditional_proc") or {}

    def brimstone_chance_by_grade(self, grade: int) -> float:
        """Per-hit Smite-placement chance for a hero with Brimstone at
        the given grade. Returns 0.0 if Brimstone has no entry for that
        grade (or the manifest is missing the table).
        """
        proc = self.brimstone_proc()
        by_grade = proc.get("smite_chance_by_grade") or {}
        # JSON keys may be strings — coerce both
        if grade in by_grade:
            return float(by_grade[grade])
        if str(grade) in by_grade:
            return float(by_grade[str(grade)])
        return 0.0

    def cruelty_proc(self) -> dict:
        return (self.get("Cruelty") or {}).get("conditional_proc") or {}

    def phantom_touch_proc(self) -> dict:
        return (self.get("PhantomTouch") or {}).get("conditional_proc") or {}

    def is_cb_blessing(self, blessing_id: str) -> bool:
        proc = (self.get(blessing_id) or {}).get("conditional_proc") or {}
        return bool(proc.get("applies_to_cb"))


class SimDataFacade:
    """Unified facade. One instance for the whole sim run.

    All six manifests are loaded eagerly at __init__; raises if any
    are missing. Use `try_facade()` for a lazy-load variant that returns
    None on failure (legacy compat for cb_sim).
    """

    def __init__(self):
        self._effect_manifest = self._load("effect_manifest.json")
        self._damage = self._load("damage_pipeline.json")
        self._tm = self._load("tm_pipeline.json")
        self._mastery = self._load("mastery_manifest.json")
        self._boss = self._load("boss_skill_manifest.json")
        self._blessing = self._load("blessing_manifest.json")

        # Wrap EffectDispatcher
        from effect_dispatcher import EffectDispatcher  # noqa: lazy import
        self.effects = EffectDispatcher()

        self.damage = _DamageFacade(self._damage)
        self.tm = _TMFacade(self._tm)
        self.mastery = _MasteryFacade(self._mastery)
        self.boss = _BossFacade(self._boss)
        self.blessing = _BlessingFacade(self._blessing)

    @staticmethod
    def _load(name: str) -> dict:
        path = STATIC / name
        if not path.exists():
            raise FileNotFoundError(
                f"manifest {name} not found at {path}. "
                f"Run the corresponding extract_*.py script first."
            )
        return json.loads(path.read_text(encoding="utf-8"))


# Lazy global accessor — cb_sim imports `facade` once and reuses.
_facade_instance: SimDataFacade | None = None


def facade() -> SimDataFacade:
    """Get or create the singleton SimDataFacade.

    Lazy so importing this module doesn't crash cb_sim if manifests
    aren't built yet — caller catches the error on first call.
    """
    global _facade_instance
    if _facade_instance is None:
        _facade_instance = SimDataFacade()
    return _facade_instance


def try_facade() -> SimDataFacade | None:
    """Best-effort accessor; returns None on missing manifests."""
    try:
        return facade()
    except Exception:
        return None


# ------- self-test -------

def _selftest() -> int:
    """Smoke test against canonical CB values."""
    f = facade()
    asserts = []

    def check(name: str, actual, expected) -> None:
        ok = actual == expected
        asserts.append((name, ok, actual, expected))

    # Effects
    check("effects.is_status_buff(UK)", f.effects.is_status_buff(2008), True)
    check("effects.lifetime(UK)", f.effects.lifetime_update(2008), "OnEndTurn")
    check("effects.can_stack(ContDmg)", f.effects.can_stack(3007), True)
    # Damage
    check("damage.hit_type_chance crit", f.damage.hit_type_chance("crit"), 0.15)
    check("damage.hit_type_chance crushing", f.damage.hit_type_chance("crushing"), 0.5)
    check("damage.element_mult Disadvantage", f.damage.element_multiplier("Disadvantage"), 0.8)
    check("damage.element_mult Neutral", f.damage.element_multiplier("Neutral"), 1.0)
    check("damage.element_relation Magic→Spirit",
          f.damage.element_relation("Magic", "Spirit"), "Advantage")
    check("damage.element_relation Magic→Force",
          f.damage.element_relation("Magic", "Force"), "Disadvantage")
    # TM
    check("tm.stamina_per_tick", f.tm.stamina_per_tick, 0.07)
    check("tm.stamina_to_turn", f.tm.stamina_to_turn, 100)
    # Mastery
    wm = f.mastery.warmaster_proc()
    check("mastery.warmaster chance", wm.get("chance"), 0.60)
    # 67,626 game-truth cap (Plarium tuned WM/GS down post-2026-05-01; verified
    # via real per-event mod capture 2026-06-22, commit 4551388). HP Burn cap is
    # a distinct 75K. If the manifest is regenerated to a new value, update here.
    check("mastery.warmaster cap", wm.get("damage_cap"), 67_626)
    check("mastery.proc_chance(GS)", f.mastery.proc_chance(500163), 0.30)
    # Boss
    check("boss.turn_50_trigger", f.boss.turn_50_trigger, 50)
    check("boss.is_bypassed UK", f.boss.is_bypassed_at_turn_50("Unkillable"), True)
    check("boss.is_bypassed BD", f.boss.is_bypassed_at_turn_50("BlockDamage"), True)
    check("boss.is_bypassed Shield", f.boss.is_bypassed_at_turn_50("Shield"), False)
    # Blessings
    bs = f.blessing.brimstone_proc()
    check("blessing.brimstone applies_to_cb", bs.get("applies_to_cb"), True)
    cr = f.blessing.cruelty_proc()
    check("blessing.cruelty applies_to_cb", cr.get("applies_to_cb"), True)
    check("blessing.is_cb_blessing(Brimstone)",
          f.blessing.is_cb_blessing("Brimstone"), True)
    check("blessing.is_cb_blessing(LightOrbs)",
          f.blessing.is_cb_blessing("LightOrbs"), False)  # LightOrbs not in CB
    # Brimstone Smite chance by grade (game-truth tooltips)
    check("blessing.brimstone g1", f.blessing.brimstone_chance_by_grade(1), 0.15)
    check("blessing.brimstone g3", f.blessing.brimstone_chance_by_grade(3), 0.30)
    check("blessing.brimstone g6", f.blessing.brimstone_chance_by_grade(6), 1.0)
    check("blessing.brimstone g99 (oob)",
          f.blessing.brimstone_chance_by_grade(99), 0.0)

    passed = sum(1 for _, ok, _, _ in asserts if ok)
    failed = len(asserts) - passed
    print(f"sim_data_facade self-test: {passed}/{len(asserts)} passed")
    for name, ok, actual, expected in asserts:
        if not ok:
            print(f"  FAIL: {name}  actual={actual!r}  expected={expected!r}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(_selftest())
