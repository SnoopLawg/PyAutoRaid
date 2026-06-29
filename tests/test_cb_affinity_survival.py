"""GUARD: CB affinity survival pattern (the MEN team's real-game result).

WHY THIS EXISTS — read before touching the cb_sim turn-meter scheduler:
The user's speed-tuned MEN team (Maneater/Demytha/Ninja/Geomancer/Venomage)
survives the Clan Boss to turn 50 on MAGIC, SPIRIT, and VOID, but NEVER on
FORCE (Ninja is Magic-affinity, glances vs the Force boss, and his A1 turn-meter
burst — glance-gated — gets skipped, desyncing the speed tune). This is
GROUND TRUTH from the user (the player who built the tune) + the clean2 capture.

This pattern is the single hardest-won result of the CB calibration work and was
repeatedly LOST across sessions by re-deriving the turn-meter model wrong. The
correct model (tm_f-confirmed, clean2) is PICK-MAX-ONE + ZERO-RESET:
  tick all units by 0.07*SPD (discrete); when >=1 crosses, the single HIGHEST-TM
  unit acts and ZERO-resets (overshoot discarded; ties -> team beats boss).
This is cb_scheduler's DWJ/live-game model. The compensating wrongs that broke
it before: "drain-all crossed" processing and "hero TM-overflow preserve" — both
matched per-hero turn counts but drifted Maneater's [Unkillable] phase off the
boss aoe2 cycle, falsely wiping Magic/Void.

If this test fails, you (or a refactor) changed the scheduler and re-broke the
survival pattern. Do NOT just update the assertions — re-read
.claude/skills/cb-sim-truths and memory project_cb_sim_survival_baseline_20260627,
restore pick-max + zero-reset, and only adjust if you have NEW game-truth
(e.g. a fresh tm_f capture) proving the real model changed.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

_FX = os.path.join(os.path.dirname(__file__), "cb_fixtures")
_BUILD = os.path.join(_FX, "build_cb_clean2.json")
_PRESET = os.path.join(_FX, "presets_cb_clean2.json")

# Affinity ids: 1=Magic, 2=Force, 3=Spirit, 4=Void.
# Real-game result for THIS tune: survive on Magic/Spirit/Void, fail on Force.
_TEAM = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
_SURVIVE = {1: "Magic", 3: "Spirit", 4: "Void"}
_FAIL = {2: "Force"}


def _run(el):
    from cb_calibrate import run_sim_for_team
    return run_sim_for_team(
        _TEAM, cb_element=el, force_affinity=True, max_cb_turns=50,
        use_preset=True, preset_snapshot_path=_PRESET, build_snapshot_path=_BUILD,
    )


def _any_dead_by_t50(sim):
    pbt = sim.get("protection_by_turn") or {}
    for bt in range(1, 51):
        d = pbt.get(bt) or pbt.get(str(bt)) or {}
        for h in _TEAM:
            if ((d.get(h) or {}).get("hp_pct", 100)) <= 0:
                return True
    return False


class TestCBAffinitySurvivalPattern(unittest.TestCase):
    """Locks the MEN team's real-game affinity survival pattern.

    Deterministic: this is the point-estimate run. Magic/Spirit/Void must reach
    T50 with the full team alive; Force must wipe before T50.
    """

    def test_magic_spirit_void_survive_t50(self):
        for el, name in _SURVIVE.items():
            sim = _run(el)
            self.assertGreaterEqual(
                sim.get("cb_turns", 0), 50,
                f"{name}: sim ended at cb_turn {sim.get('cb_turns')} < 50 — "
                f"the team should reach T50. Scheduler regressed? "
                f"See tests/test_cb_affinity_survival.py docstring.",
            )
            self.assertFalse(
                _any_dead_by_t50(sim),
                f"{name}: a hero died before T50 but the real team survives. "
                f"Turn-meter scheduler likely regressed from pick-max+zero-reset. "
                f"See .claude/skills/cb-sim-truths.",
            )

    def test_force_wipes_before_t50(self):
        sim = _run(2)
        self.assertTrue(
            _any_dead_by_t50(sim),
            "Force: sim shows full-team survival to T50, but real-game Force "
            "NEVER lasts 50 (Ninja-Magic glances -> A1 TM burst skipped -> tune "
            "desync). If the sim survives Force, the glance/TM model regressed.",
        )


if __name__ == "__main__":
    unittest.main()
