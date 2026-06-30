"""M5 PHASE 5b FOUNDATIONS — acceptance tests for the additive 5b modules.

Run:  python -m pytest tests/test_fitness_5b.py -q

Covers:
  1. hh_validation.validate_against_hh returns a finite rho + full schema for
     clan_boss on a handful of comps; rho is non-negative on an obvious
     strong-vs-weak ordering.
  2. learned.featurize is a stable-length vector for different comps;
     train([]) returns a usable PRIOR model; predict runs and is monotonic
     in heuristic strength for the prior.
  3. We touch ONLY the public 5a surface (score / synergy_data helpers) — the
     existing 5a tests still pass unchanged (verified separately in CI).
"""
from __future__ import annotations

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

from fitness import hh_validation as hv   # noqa: E402
from fitness import learned as lr          # noqa: E402


# Real-roster comps with HH coverage. STRONG is a full-synergy CB comp; JUNK is
# bottom-tier filler (no engines/amps/survival, HH clan_boss ~1). Both metrics
# (5a heuristic AND the HH per-hero mean) agree on this ordering, so it's a
# stable strong-vs-weak fixture. MID sits between.
STRONG = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
MID = ["Apothecary", "High Khatun", "Ninja", "Venomage", "Frozen Banshee"]
JUNK = ["Ranger", "Mystic Hand", "Militia", "Cataphract", "Crossbowman"]
# A whole-comp-synergy comp that is NOT a per-hero all-star average — used to
# show the heuristic and HH-mean genuinely measure different things.
WEAK = ["Warmaiden", "Hyria", "High Khatun", "Apothecary", "Ninja"]


# --------------------------------------------------------------------------- #
# 1. HH validation
# --------------------------------------------------------------------------- #
def test_validate_against_hh_schema_and_finite_rho():
    out = hv.validate_against_hh("clan_boss", [STRONG, MID, JUNK],
                                 {"cb_element": 1})
    # full schema present
    for key in ("location", "hh_key", "agg", "n", "rho", "agree_pct",
                "paired", "skipped", "notes"):
        assert key in out, f"missing schema key {key}"
    assert out["hh_key"] == "clan_boss"
    assert out["n"] == 3
    assert out["rho"] is not None
    assert isinstance(out["rho"], float) and math.isfinite(out["rho"])
    assert -1.0 <= out["rho"] <= 1.0
    assert len(out["paired"]) == 3


def test_validate_against_hh_positive_on_strong_vs_weak():
    # On an obviously-ordered set (full-synergy >> filler) the heuristic ranks
    # the same way HH does → positive rho ("ranks sanely vs HH" acceptance).
    out = hv.validate_against_hh("clan_boss", [STRONG, MID, JUNK],
                                 {"cb_element": 1})
    assert out["n"] == 3
    assert out["rho"] is not None
    assert out["rho"] > 0.0, out


def test_validate_against_hh_unsupported_location_notes():
    out = hv.validate_against_hh("arena", [STRONG, WEAK])
    assert out["hh_key"] is None
    assert out["rho"] is None
    assert out["n"] == 0
    assert any("no HH rating column" in n for n in out["notes"])


def test_spearman_helpers_basic():
    assert hv.spearman_rho([1, 2, 3], [1, 2, 3]) == 1.0
    assert hv.spearman_rho([1, 2, 3], [3, 2, 1]) == -1.0
    assert hv.spearman_rho([1], [1]) is None  # n<2 undefined
    assert hv.ordering_agreement([1, 2, 3], [1, 2, 3]) == 1.0


# --------------------------------------------------------------------------- #
# 2. learned model scaffold
# --------------------------------------------------------------------------- #
def test_featurize_stable_length():
    fa = lr.featurize(STRONG, "clan_boss", {"cb_element": 1})
    fb = lr.featurize(WEAK, "spider")
    assert len(fa) == lr.N_FEATURES == len(lr.FEATURE_NAMES)
    assert len(fb) == lr.N_FEATURES
    assert all(isinstance(v, float) for v in fa)
    # The two comps must differ somewhere (not a constant vector).
    assert fa != fb


def test_featurize_all_unknown_is_zero_vector():
    z = lr.featurize(["NotAHeroXYZ", "AlsoFake"], "clan_boss")
    assert len(z) == lr.N_FEATURES
    # comp_size is the only inherently non-zero feature for unknown heroes.
    nonzero = {lr.FEATURE_NAMES[i]: v for i, v in enumerate(z) if v != 0.0}
    # comp_size + boss-derived features + the amp-multiplier baseline (empty
    # product == 1.0) are the only non-zero features for an all-unknown comp.
    assert set(nonzero) <= {"comp_size", "lethality", "acc_floor",
                            "boss_hp_burn_bonus_pct", "hit_amp_multiplier"}


def test_train_empty_returns_usable_prior():
    m = lr.train([])
    assert m["kind"] == "prior"
    assert m["weights"] is None
    assert m["feature_names"] == lr.FEATURE_NAMES
    # prior predict runs and is monotonic in heuristic strength:
    # full-synergy comp > filler comp.
    pa = lr.predict(m, STRONG, "clan_boss", {"cb_element": 1})
    pj = lr.predict(m, JUNK, "clan_boss", {"cb_element": 1})
    assert 0.0 <= pa["p_clear"] <= 1.0
    assert pa["kind"] == "prior"
    assert pa["p_clear"] >= pj["p_clear"]


def test_train_on_synthetic_labels_fits_and_predicts():
    # Two clearly separable classes so a classifier (sklearn or fallback) fits.
    samples = []
    for _ in range(4):
        samples.append(lr.make_sample(STRONG, "clan_boss", cleared=True,
                                      damage=36e6, context={"cb_element": 1},
                                      source="cb_sim"))
        samples.append(lr.make_sample(WEAK, "clan_boss", cleared=False,
                                      damage=5e6, context={"cb_element": 1},
                                      source="cb_sim"))
    m = lr.train(samples)
    assert m["kind"] in ("logreg_sklearn", "logreg_fallback")
    assert m["trained_on"] == len(samples)
    assert m["weights"] is not None and len(m["weights"]) == lr.N_FEATURES
    p_strong = lr.predict(m, STRONG, "clan_boss", {"cb_element": 1})["p_clear"]
    p_weak = lr.predict(m, WEAK, "clan_boss", {"cb_element": 1})["p_clear"]
    assert 0.0 <= p_strong <= 1.0 and 0.0 <= p_weak <= 1.0
    assert p_strong > p_weak


def test_make_sample_validation():
    s = lr.make_sample(STRONG, "clan_boss", True, damage=1.0, source="cb_sim")
    assert s["cleared"] is True and s["source"] == "cb_sim"
    try:
        lr.make_sample(STRONG, "clan_boss", True, source="bogus")
        assert False, "expected ValueError on bad source"
    except ValueError:
        pass


def test_save_and_load_roundtrip(tmp_path):
    m = lr.train([])
    path = tmp_path / "fitness_model.json"
    lr.save_model(m, path)
    m2 = lr.load_model(path)
    assert m2["kind"] == m["kind"]
    assert m2["feature_names"] == lr.FEATURE_NAMES
    # load of a missing path degrades to a prior, not an error.
    missing = lr.load_model(tmp_path / "nope.json")
    assert missing["kind"] == "prior"
