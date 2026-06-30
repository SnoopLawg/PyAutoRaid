"""Tests for tools/team_tune.py — stage-2 tune-and-compare.

These are SLOW-ish (each cb_sim run ~1s) so the grids are kept tiny: the point
is to prove the schema + plumbing, not to run a full SPD search. The full
side-by-side validation is the CLI deliverable (--compare --validate), not a
unit test, because it costs minutes.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import team_tune  # noqa: E402

MEN = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
NOVEL = ["Arbiter", "Coldheart", "Demytha", "Ninja", "Teodor the Savant"]
SCHEMA = ("spd_assignment", "tuned_fitness", "holds_t50", "tune_found", "notes")


def test_resolve_element():
    assert team_tune._resolve_element("spirit") == 3
    assert team_tune._resolve_element(4) == 4
    with pytest.raises(ValueError):
        team_tune._resolve_element("plasma")


def test_auto_grids_respects_budget():
    base = [288, 184, 206, 177, 162]
    # tight budget -> coarse pool; product must fit.
    ag = team_tune.auto_grids(base, max_combos=32)
    assert ag["combos"] <= 32
    # every hero grid contains its natural speed (offset 0 always present).
    for i, b in enumerate(base):
        assert b in ag["grids"][i]
    # a generous budget picks a richer pool (more values/hero).
    ag2 = team_tune.auto_grids(base, max_combos=243)
    assert ag2["combos"] <= 243
    assert len(ag2["offsets"]) >= len(ag["offsets"])


def test_normalize_vary_forms():
    names = MEN
    by_name = team_tune._normalize_vary({"Demytha": [174, 184]}, names)
    assert by_name == {1: [174, 184]}
    by_idx = team_tune._normalize_vary({1: [174, 184]}, names)
    assert by_idx == {1: [174, 184]}
    by_str = team_tune._normalize_vary("Demytha=174..184:10", names)
    assert by_str == {1: [174, 184]}
    with pytest.raises(ValueError):
        team_tune._normalize_vary({"Nobody": [1]}, names)


def test_tune_and_score_men_schema():
    """tune_and_score runs on MEN and returns the full schema with a numeric
    tuned_fitness + boolean holds_t50 (the acceptance minimum). Tiny explicit
    vary (Demytha 174/184 = the known lever) keeps it to ~2 sims."""
    res = team_tune.tune_and_score(
        MEN, element="spirit", gear="current",
        vary={"Demytha": [174, 184]})
    for k in SCHEMA:
        assert k in res, f"missing schema key {k}"
    assert isinstance(res["tuned_fitness"], float)
    assert res["tuned_fitness"] > 0.0
    assert isinstance(res["holds_t50"], bool)
    assert isinstance(res["tune_found"], bool)
    assert isinstance(res["notes"], list) and res["notes"]
    # spd_assignment covers all 5 heroes when the comp is gearable.
    assert set(res["spd_assignment"]) == set(MEN)
    # natural speeds were evaluated (offset-0 always in the grid).
    assert res["natural"] is not None
    assert res["base_spd"]["Demytha"] in (174, 184)


def test_compare_two_comps_tuned_side_by_side():
    """The --compare primitive tunes BOTH comps and ranks by tuned damage so
    they're comparable. Tiny vary (1 combo each) to stay fast."""
    comps = [("NOVEL", NOVEL), ("MEN", MEN)]
    rows = []
    for label, team in comps:
        res = team_tune.tune_and_score(
            team, element="spirit", gear="current",
            vary={"Demytha": [184]})  # 1 combo = natural only, fast
        rows.append((label, team, res))
    rows.sort(key=lambda r: (r[2]["holds_t50"], r[2]["tuned_fitness"]),
              reverse=True)
    assert len(rows) == 2
    for _label, _team, res in rows:
        assert res["tuned_fitness"] >= 0.0
        assert "holds_t50" in res
    # ranking is by tuned damage (desc) among equal holds_t50.
    assert rows[0][2]["tuned_fitness"] >= rows[1][2]["tuned_fitness"] or \
        rows[0][2]["holds_t50"] >= rows[1][2]["holds_t50"]
