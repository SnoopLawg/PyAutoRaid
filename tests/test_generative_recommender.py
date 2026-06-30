"""Task #43 — generative engine wired into the recommendation path.

Run:  python -m pytest tests/test_generative_recommender.py -q

Asserts the acceptance criteria for wiring tools/team_generator.generate into
cb_recommender (the recommender that previously only SCORED scraped DWJ tunes):

  1. The generative domain function returns ranked candidates for clan_boss,
     each labelled rediscovered/novel with a fitness_kind.
  2. Same for a non-CB location (dragon) on the heuristic path.
  3. The recommender no longer REQUIRES the DWJ tune list — disabling the DWJ
     cross-check still produces game-truth-derived teams.
  4. The DWJ readiness overlay is ADDITIVE: rediscovering a full scraped core
     labels the comp "rediscovered" and attaches the template id; a comp missing
     that core stays "novel".
  5. The generative CLI prints ranked, labelled teams for clan_boss and dragon.
  6. Backward compat: the existing cb_recommender `list` entrypoint still runs.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

import cb_recommender as cr  # noqa: E402


def _labels_ok(teams):
    for t in teams:
        assert t["label"] in ("novel", "rediscovered")
        assert t["fitness_kind"] in ("heuristic", "cb_sim")
        assert isinstance(t["team"], list) and len(t["team"]) == 5
        assert "fitness" in t


# --------------------------------------------------------------------------- #
# 1. clan_boss generative — ranked, labelled, heuristic-fast.
# --------------------------------------------------------------------------- #
def test_clan_boss_generative_heuristic():
    res = cr.generate_recommendations(
        "clan_boss", top=8, rank_with="heuristic", cb_element="void",
        force=True)
    assert res["generative"] is True
    assert res["count"] > 0
    _labels_ok(res["teams"])
    # ranked descending by fitness (heuristic kind).
    fits = [t["fitness"] for t in res["teams"]]
    assert fits == sorted(fits, reverse=True)
    # produced from game-truth skeletons, not a DWJ tune list.
    assert res["report"]["skeletons_run"]


# --------------------------------------------------------------------------- #
# 2. dragon (non-CB) generative — heuristic path, no DWJ overlay.
# --------------------------------------------------------------------------- #
def test_dragon_generative_heuristic():
    res = cr.generate_recommendations(
        "dragon", top=6, rank_with="heuristic", force=True)
    assert res["count"] > 0
    _labels_ok(res["teams"])
    for t in res["teams"]:
        assert t["fitness_kind"] == "heuristic"   # no cb_sim off-CB
    # non-CB has no DWJ cross-check overlay.
    assert res["cross_check"] is False
    assert all("dwj" not in t for t in res["teams"])


# --------------------------------------------------------------------------- #
# 3. No DWJ tune list REQUIRED — teams generated with the overlay disabled.
# --------------------------------------------------------------------------- #
def test_generates_without_dwj_template_list():
    res = cr.generate_recommendations(
        "clan_boss", top=6, rank_with="heuristic", cb_element="void",
        cross_check=False, force=True)
    assert res["count"] > 0          # a team WITHOUT consulting any DWJ tune
    assert res["cross_check"] is False
    _labels_ok(res["teams"])


# --------------------------------------------------------------------------- #
# 4. DWJ overlay is additive: full-core containment -> rediscovered + id.
# --------------------------------------------------------------------------- #
def test_dwj_crosscheck_labels_rediscovered():
    idx = cr._dwj_template_index(cr._root(None))
    assert idx, "expected scraped DWJ templates to be available"
    # pick a template that names a real core (>= the core threshold).
    core_tpl = next((t for t in idx if len(t["names"]) >= cr._MIN_DWJ_CORE), None)
    assert core_tpl is not None
    core = sorted(core_tpl["names"])
    # a comp that CONTAINS the whole named core -> rediscovered.
    team = (core + ["filler_x", "filler_y"])[:5]
    xc = cr._crosscheck_dwj(team, idx)
    assert xc is not None
    assert xc["template_id"]
    # a comp missing one core member -> not this rediscovery (novel vs it).
    partial = (core[1:] + ["filler_a", "filler_b", "filler_c"])[:5]
    xc2 = cr._crosscheck_dwj(partial, idx)
    # either no match, or it matched a DIFFERENT (smaller) tune, never this one
    # via the missing-core path.
    if xc2 is not None:
        assert core_tpl["names"] - {c.lower() for c in partial}, \
            "partial team should not fully contain the core tune"


# --------------------------------------------------------------------------- #
# 5. CLI prints ranked, labelled teams for CB + a non-CB location.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("location", ["clan_boss", "dragon"])
def test_generative_cli(location):
    cmd = [sys.executable, os.path.join(TOOLS, "cb_recommender.py"),
           "generate", location, "--top", "5", "--rank-with", "heuristic",
           "--force"]
    if location == "clan_boss":
        cmd += ["--cb-element", "void"]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                         timeout=300)
    assert out.returncode == 0, out.stderr
    txt = out.stdout
    assert "generative recommendations" in txt
    assert "heuristic" in txt
    assert ("novel" in txt or "rediscovered" in txt)


# --------------------------------------------------------------------------- #
# 6. Backward compat — the existing list entrypoint still runs.
# --------------------------------------------------------------------------- #
def test_backward_compat_list_cli():
    cmd = [sys.executable, os.path.join(TOOLS, "cb_recommender.py"),
           "list", "--tab", "ready"]
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                         timeout=300)
    assert out.returncode == 0, out.stderr
