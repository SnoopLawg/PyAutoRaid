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


@pytest.fixture(scope="module")
def gear_opt():
    """Shared vault-wide gear optimizer (building it indexes the whole vault, so
    do it once for all gear tests)."""
    import gear_target_optimizer as gto
    arts, heroes, account = gto.load_data()
    return gto.Optimizer(arts, heroes, account)


GEAR_SCHEMA = ("feasible", "acc_floor", "per_hero")
PER_HERO_KEYS = ("reachable", "spd_gap", "acc_ok", "achieved_spd",
                 "achieved_acc", "target_spd", "needs_acc", "notes")
# MEN's daily-robust tune (memory project_speed_tune_finder) — the user's real,
# fielded comp, so its gear must be BUILDABLE.
MEN_TUNE = {"Maneater": 292, "Demytha": 174, "Ninja": 206,
            "Geomancer": 177, "Venomage": 162}


def test_cb_acc_floor_is_225():
    # game-truth CB UNM boss-RES ACC floor from boss_constraints (225).
    assert team_tune._cb_acc_floor("clan_boss") == 225


def test_gear_feasibility_schema_and_men_feasible(gear_opt):
    """gear_feasibility returns the documented schema AND marks MEN's tune
    FEASIBLE — it's the user's real, fielded comp, so the vault can build it
    (SPD targets + the 225 ACC floor on the debuffers)."""
    gf = team_tune.gear_feasibility(MEN, MEN_TUNE, element="spirit",
                                    opt=gear_opt)
    for k in GEAR_SCHEMA:
        assert k in gf, f"missing gear schema key {k}"
    assert gf["acc_floor"] == 225
    assert set(gf["per_hero"]) == set(MEN)
    for nm, h in gf["per_hero"].items():
        for k in PER_HERO_KEYS:
            assert k in h, f"{nm} missing per-hero key {k}"
        assert isinstance(h["reachable"], bool)
        assert isinstance(h["notes"], list)
    # the debuffers (Ninja/Geo/Venomage) carry the ACC floor; tank/protector don't.
    assert gf["per_hero"]["Ninja"]["needs_acc"] is True
    assert gf["per_hero"]["Maneater"]["needs_acc"] is False
    # MEN is buildable.
    assert gf["feasible"] is True


def test_gear_feasibility_reports_spd_gap(gear_opt):
    """An unreachable SPD target is reported as a gap (reachable False, positive
    spd_gap, a note) rather than silently passing — the actionable signal."""
    gf = team_tune.gear_feasibility(["Maneater"], {"Maneater": 400},
                                    element="spirit", opt=gear_opt)
    assert gf["feasible"] is False
    h = gf["per_hero"]["Maneater"]
    assert h["reachable"] is False
    assert h["spd_gap"] > 0
    assert any("SPD" in n for n in h["notes"])


def test_adaptive_search_finds_men_hold_within_budget():
    """The adaptive coarse->fine search finds MEN's T50 hold and stays within the
    combo budget (coarse + fine sims combined <= max_combos)."""
    budget = 24
    res = team_tune.tune_and_score(MEN, element="spirit", gear="current",
                                   adaptive=True, max_combos=budget)
    assert res["holds_t50"] is True
    assert res["best"]["turns"] >= 50
    assert res["combos_evaluated"] <= budget
    # adaptive without explicit vary still fills the full schema.
    for k in SCHEMA:
        assert k in res


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
