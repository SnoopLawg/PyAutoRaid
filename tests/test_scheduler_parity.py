"""Scheduler-invariant regression locks — the safety net for unifying the
three turn-meter engines (cb_sim, calc_parity_sim, speed_tune) onto one core.

These lock the *turn order / cadence* specifically (not just total damage,
which test_cb_sim_regression already guards). A scheduler refactor MUST keep
these green: same cast sequence in, same cast sequence out.

  - CB-sim cadence: the MEN team's full action-for-action timeline signature +
    per-hero action counts + boss-turn count (deterministic, model_survival).
  - DWJ-parity: the cast order of 3 verified DWJ variants (myth-eater,
    batman-forever, endless-speed) — the calc_parity_sim scheduler, which is
    100%-action-for-action matched to DeadwoodJedi's calculator.

If a refactor intentionally changes scheduling, update the locked signature
AND add a comment explaining the delta (mirrors test_cb_sim_regression's
discipline). A silent signature drift is a cadence regression.
"""
import hashlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))


def _sig(tokens) -> str:
    """Stable 16-hex signature of an ordered token list."""
    return hashlib.sha256(json.dumps(tokens).encode()).hexdigest()[:16]


def _men_team():
    from cb_sim import build_champion_minimal
    return [
        build_champion_minimal(name="Maneater", position=1, speed=288,
                               hp=40000, defense=1500, element=4),
        build_champion_minimal(name="Demytha", position=2, speed=172,
                               hp=38000, defense=1500, element=4),
        build_champion_minimal(name="Ninja", position=3, speed=205,
                               hp=43000, defense=1500, element=1),
        build_champion_minimal(name="Geomancer", position=4, speed=177,
                               hp=58000, defense=1500, element=4),
        build_champion_minimal(name="Venomage", position=5, speed=162,
                               hp=48000, defense=1500, element=2),
    ]


def cb_sim_timeline_signature():
    """(timeline_len, signature, turns_taken_dict) for the locked MEN config.
    Exposed as a helper so a re-lock after an intentional change is one call."""
    from cb_sim import CBSimulator
    heroes = _men_team()
    sim = CBSimulator(heroes, cb_speed=190, cb_element=1,
                      deterministic=True, model_survival=True)
    res = sim.run(max_cb_turns=50)
    tl = res.get("timeline") or []
    # Token excludes `tick` (pure ordinal, arithmetic-sensitive); ORDER + actor
    # + skill is the scheduler invariant we care about.
    toks = [(e.get("kind"), e.get("hero") or e.get("boss_action"), e.get("skill"))
            for e in tl]
    turns = {h.name: h.turns_taken for h in heroes}
    return len(tl), _sig(toks), turns, res.get("cb_turns")


def dwj_cast_signature(slug):
    """(n_turns, boss_turns, signature) for a verified DWJ variant's cast order."""
    import calc_parity_sim as cps
    dwj = cps.load_all()
    tune = dwj.tunes.get(slug)
    if not tune or not tune.variants:
        return None
    v = tune.variants[0]
    turns = cps.simulate(v, max_boss_turns=25)
    toks = [(t.actor_name, getattr(t, "skill_alias", None) or getattr(t, "skill", None))
            for t in turns]
    return len(turns), cps.count_boss_turns(turns), _sig(toks)


class TestCbSimCadenceLock(unittest.TestCase):
    """Lock cb_sim's MEN turn order. Captured 2026-06-23 from the verified
    DWJ-parity cadence (commit da59b52, TM-reset-to-0)."""

    # 18 boss turns is current correct behavior (see test_cb_sim_regression
    # re-baseline note: 599297f Maneater-A3-self-hit + da59b52 cadence +
    # 95472fa debuff fixes). Per-hero action counts and the full cast-order
    # signature are the scheduler-cadence invariants.
    LOCKED_TIMELINE_LEN = 109
    LOCKED_TIMELINE_SIG = "a485d1cff0e269ec"
    LOCKED_TURNS = {"Maneater": 25, "Demytha": 15, "Ninja": 20,
                    "Geomancer": 17, "Venomage": 15}
    LOCKED_CB_TURNS = 18

    def test_men_cadence_signature(self):
        ln, sig, turns, cb_turns = cb_sim_timeline_signature()
        self.assertEqual(cb_turns, self.LOCKED_CB_TURNS, "boss-turn count drifted")
        self.assertEqual(turns, self.LOCKED_TURNS,
                         "per-hero action counts drifted (scheduler cadence changed)")
        self.assertEqual(ln, self.LOCKED_TIMELINE_LEN, "timeline length drifted")
        self.assertEqual(
            sig, self.LOCKED_TIMELINE_SIG,
            "MEN cast-order signature drifted — the scheduler produced a "
            "different turn sequence. If intentional, re-lock via "
            "tests.test_scheduler_parity.cb_sim_timeline_signature() and "
            "explain the delta.")


class TestDwjParityCastOrder(unittest.TestCase):
    """Lock the cast order of verified DWJ variants. calc_parity_sim is
    action-for-action matched to DeadwoodJedi's calculator; these guard that
    the scheduler stays in parity through the unification."""

    LOCKED = {
        "myth-eater":     (168, 25, "59f71c5fff4e53f5"),
        "batman-forever": (289, 25, "670178d002995fbb"),
        "endless-speed":  (209, 25, "174c5bdcf4300714"),
    }

    def test_verified_variants_cast_order(self):
        for slug, (n, boss, sig) in self.LOCKED.items():
            with self.subTest(slug=slug):
                got = dwj_cast_signature(slug)
                self.assertIsNotNone(got, f"{slug} variant not found")
                gn, gboss, gsig = got
                self.assertEqual(gboss, boss, f"{slug}: boss-turn count drifted")
                self.assertEqual(gn, n, f"{slug}: total-turn count drifted")
                self.assertEqual(
                    gsig, sig,
                    f"{slug}: cast-order signature drifted — calc_parity_sim "
                    f"fell out of DWJ parity. If intentional, re-lock + explain.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
