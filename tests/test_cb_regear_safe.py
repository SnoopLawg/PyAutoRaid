"""GUARD: the SAFE re-gear gate (tools/cb_regear_for_damage.py, Task #51).

WHY THIS EXISTS — a live re-gear of the MEN dealers WIPED at boss turn 24 (17.2M
vs 36M/T50 baseline). Root cause: a survivor SPD source (Maneater's speed piece)
leaked into a dealer's assignment, slowing the UK provider 1.65->1.25 turns/boss,
and dealer SPDs drifted ~1pt off the tune. MEN holds by buff-cadence sync, so SPD
must stay EXACTLY on tune. The gate must:

  1. NEVER let a dealer assignment reuse a survivor's equipped artifact.
  2. Read REAL computed SPD (not None) so the verify step has ground truth.
  3. Re-sim with the ACTUAL post-equip SPDs and, if the tune breaks (survivor SPD
     changed, drops below T50, or damage doesn't rise), RESTORE the baseline
     BEFORE any key is spent.

Offline tests always run (parsing + the exclusion assert). The live gate test
runs only when RUN_LIVE_REGEAR=1 and the mod is up at localhost:6790, because it
mutates gear on the live game (it always restores, but we don't do that on a
normal test run).
"""
import io
import json
import os
import sys
import unittest
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import cb_regear_for_damage as m  # noqa: E402
from cb_sim import SPD, CR, CD, ACC, ATK  # noqa: E402

MEN_IDS = [15120, 18607, 2643, 13615, 5692]  # Maneater/Demytha/Ninja/Geo/Venom


def _mod_up():
    try:
        with urllib.request.urlopen(f"{m.MOD_BASE}/status", timeout=3) as r:
            return json.loads(r.read()).get("logged_in") is not None
    except Exception:
        return False


class TestSurvivorExclusionAssert(unittest.TestCase):
    """The airtight guard: dealer assignment must share ZERO ids with survivors."""

    def _solves(self, ninja_ids):
        # minimal shape _assignment_ids / _assert_no_survivor_overlap read.
        return {"Ninja": {"assignment": {i + 1: {"id": a}
                                         for i, a in enumerate(ninja_ids)}}}

    def test_disjoint_passes(self):
        solves = self._solves([101, 102, 103])
        survivor_ids = {201, 202}
        got = m._assert_no_survivor_overlap(solves, survivor_ids)
        self.assertEqual(got, {101, 102, 103})

    def test_overlap_raises(self):
        solves = self._solves([101, 202, 103])   # 202 is a survivor piece
        survivor_ids = {201, 202}
        with self.assertRaises(AssertionError):
            m._assert_no_survivor_overlap(solves, survivor_ids)


class TestComputedStatsParse(unittest.TestCase):
    """read_computed_stats must SUM the columns and convert CR/CD fraction->%."""

    _FAKE = {
        "heroes": [{
            "id": 2643,
            "base_computed": {"SPD": 100.0, "CR": 0.15, "CD": 0.63,
                              "ACC": 10.0, "ATK": 1509.0},
            "artifact_bonus": {"SPD": 102.0, "CR": 0.80, "CD": 0.97,
                               "ACC": 205.0, "ATK": 1852.0},
            "mastery_bonus": {"SPD": 4.0, "CR": 0.05, "CD": 0.10,
                              "ACC": 16.0, "ATK": 0.0},
            "faction_guardians_bonus": {"SPD": None, "CR": None},  # tolerate None
        }],
    }

    def setUp(self):
        self._orig = urllib.request.urlopen
        fake = self._FAKE

        class _Resp(io.BytesIO):
            def __enter__(self_):
                return self_

            def __exit__(self_, *a):
                return False

        def _fake_urlopen(url, timeout=30):
            return _Resp(json.dumps(fake).encode())

        urllib.request.urlopen = _fake_urlopen

    def tearDown(self):
        urllib.request.urlopen = self._orig

    def test_sum_and_convert(self):
        stats = m.read_computed_stats([2643])[2643]
        self.assertEqual(round(stats[SPD]), 206)           # 100+102+4
        self.assertAlmostEqual(stats[CR], 100.0, places=3)  # (0.15+0.80+0.05)*100
        self.assertAlmostEqual(stats[CD], 170.0, places=3)  # (0.63+0.97+0.10)*100
        self.assertEqual(round(stats[ACC]), 231)            # 10+205+16
        self.assertEqual(round(stats[ATK]), 3361)           # 1509+1852

    def test_spd_only_helper(self):
        self.assertEqual(m.read_computed_spd([2643]), {2643: 206})

    def test_missing_hero_is_none(self):
        self.assertIsNone(m.read_computed_stats([999999])[999999])
        self.assertIsNone(m.read_computed_spd([999999])[999999])


@unittest.skipUnless(os.environ.get("RUN_LIVE_REGEAR") == "1" and _mod_up(),
                     "live gate (mutates gear) — set RUN_LIVE_REGEAR=1 with mod up")
class TestLiveGate(unittest.TestCase):
    """End-to-end on the live game: the loose (spd_tol=2) solve DRIFTS the tune,
    so the gate must FAIL and RESTORE. Always leaves gear restored."""

    def test_real_computed_spd_not_none(self):
        spd = m.read_computed_spd(MEN_IDS)
        for hid in MEN_IDS:
            self.assertIsNotNone(spd[hid], f"SPD None for {hid}")

    def test_loose_regear_desyncs_and_restores(self):
        R = m.safe_regear(element="spirit", dry_run=True, anneal=6, spd_tol=2,
                          snapshot_name="men_safe_regear_test")
        # survivor exclusion held (assert would have raised otherwise).
        self.assertEqual(set(R["assigned_ids"]) & set(R["survivor_excluded"]),
                         set())
        # survivors' SPD never changed (airtight exclusion).
        for n, v in R["survivor_spd_check"].items():
            self.assertTrue(v["ok"], f"{n} SPD drifted {v}")
        # loose solve drifts the tune -> gate FAILS -> gear restored.
        self.assertFalse(R["passed"])
        self.assertTrue(R["restored"])
        # gear is back to the tune on all 5.
        import loadouts
        heroes = loadouts._fetch_heroes()
        ids = m._resolve_ids()
        for n in m.MEN:
            self.assertEqual(len(loadouts._equipped_by_slot(heroes[ids[n]])), 9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
