"""M5 PHASE 5a — universal fitness function acceptance tests.

Run:  python -m pytest tests/test_fitness.py -q

Covers the five acceptance criteria from the milestone:
  1. CB heuristic RANK-correlates with cb_sim on strong↔weak comps.
  2. Channel rule: a Weaken amp credits a HIT engine, never a POISON engine.
  3. Boss-script: a Stun comp = ~0 control value on clan_boss, positive on arena.
  4. Survival floor: no survival_currency is penalized on a lethal location.
  5. Ice Golem: a poison engine is penalized vs a non-poison engine (poison-immune).
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
for p in (ROOT, TOOLS):
    if p not in sys.path:
        sys.path.insert(0, p)

from fitness import score  # noqa: E402


# --------------------------------------------------------------------------- #
# Synthetic M1 records — pure tag predicates, no real-roster dependency, so
# the channel/boss/survival rules are tested in isolation.
# --------------------------------------------------------------------------- #
def _rec(name, **kw):
    base = dict(name=name, provides=[], needs=[], amplifier_channel="none",
                engine_channel=[], survival_currency=None, enabler=None,
                keystone_needs_enabler=False)
    base.update(kw)
    return base


WEAKEN_AMP = _rec("WeakenGuy", provides=["enemy_debuff:Weaken"],
                  amplifier_channel="hit")
HIT_ENGINE = _rec("HitDPS", engine_channel=["hit"])
POISON_ENGINE = _rec("PoisonDPS", provides=["dot:Poison"],
                     engine_channel=["poison"])
HP_BURN_ENGINE = _rec("Burner", provides=["dot:HP Burn"],
                      engine_channel=["hp_burn"])
STUNNER = _rec("Stunner", provides=["enemy_debuff:Stun"])
TANK = _rec("Tank", survival_currency="unkillable")


def _ov(*recs):
    return {"records_override": {r["name"]: r for r in recs}}


# --------------------------------------------------------------------------- #
# 1. CB heuristic rank-correlates with cb_sim.
# --------------------------------------------------------------------------- #
def _spearman(a, b):
    def rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        rk = [0] * len(x)
        for pos, i in enumerate(order):
            rk[i] = pos
        return rk
    ra, rb = rank(a), rank(b)
    n = len(a)
    d2 = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1))


# Comps spanning strong (survival + amps + many engines) → weak (no survival /
# few engines). All heroes exist in the roster so cb_potential can gear them.
_CB_COMPS = {
    "MEN_full": ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"],
    "one_surv_dps": ["Demytha", "Ninja", "Geomancer", "Venomage", "Frozen Banshee"],
    "cardiel_men": ["Maneater", "Cardiel", "Ninja", "Geomancer", "Venomage"],
    "MEN_noVenom": ["Maneater", "Demytha", "Ninja", "Geomancer", "Pain Keeper"],
    "no_surv_all_dps": ["Ninja", "Geomancer", "Venomage", "Frozen Banshee", "Hyria"],
    "painkeeper_dps": ["Pain Keeper", "Ninja", "Geomancer", "Venomage", "Frozen Banshee"],
}


def test_cb_heuristic_rank_correlates_with_sim():
    try:
        import cb_potential
    except Exception as e:  # pragma: no cover
        pytest.skip(f"cb_potential unavailable: {e}")

    sim_vals, heur_vals, labels = [], [], []
    for label, team in _CB_COMPS.items():
        sim = cb_potential.simulate_team(team, cb_element=1)
        if sim.get("error"):
            pytest.skip(f"sim error on {label}: {sim['error']}")
        heur = score(team, "clan_boss", {"cb_element": 1})
        assert heur["kind"] == "heuristic"
        sim_vals.append(sim["total"])
        heur_vals.append(heur["fitness"])
        labels.append(label)

    rho = _spearman(sim_vals, heur_vals)
    assert rho >= 0.5, f"weak rank correlation rho={rho:.3f}\n" + \
        "\n".join(f"  {l}: sim={s:.0f} heur={h:.3f}"
                  for l, s, h in zip(labels, sim_vals, heur_vals))

    # Explicit sanity: full survival comp >> no-survival all-DPS comp.
    men = score(_CB_COMPS["MEN_full"], "clan_boss", {"cb_element": 1})["fitness"]
    allin = score(_CB_COMPS["no_surv_all_dps"], "clan_boss",
                  {"cb_element": 1})["fitness"]
    assert men > allin


# --------------------------------------------------------------------------- #
# 2. Channel rule: Weaken credits a hit engine, never a poison engine.
# --------------------------------------------------------------------------- #
def test_channel_weaken_credits_hit_not_poison():
    ov = _ov(WEAKEN_AMP, HIT_ENGINE, POISON_ENGINE, TANK)

    hit_no = score(["HitDPS", "Tank"], "clan_boss", ov)
    hit_yes = score(["HitDPS", "WeakenGuy", "Tank"], "clan_boss", ov)
    # Hit engine: Weaken raises the amplifier multiplier and the fitness.
    assert hit_yes["breakdown"]["channels"]["hit"]["amplifier_multiplier"] > \
        hit_no["breakdown"]["channels"]["hit"]["amplifier_multiplier"]
    assert hit_yes["fitness"] > hit_no["fitness"]

    poi_no = score(["PoisonDPS", "Tank"], "clan_boss", ov)
    poi_yes = score(["PoisonDPS", "WeakenGuy", "Tank"], "clan_boss", ov)
    # Poison engine: a hit-channel Weaken amp must give NO credit.
    assert poi_yes["breakdown"]["channels"]["poison"]["score"] == \
        poi_no["breakdown"]["channels"]["poison"]["score"]
    assert poi_yes["fitness"] == poi_no["fitness"]


# --------------------------------------------------------------------------- #
# 3. Boss-script: Stun control is zero-value on CB, positive on arena.
# --------------------------------------------------------------------------- #
def test_stun_control_zeroed_on_cb_but_useful_on_arena():
    ov = _ov(STUNNER, TANK)
    cb = score(["Stunner", "Tank"], "clan_boss", ov)["breakdown"]["control"]
    arena = score(["Stunner", "Tank"], "arena", ov)["breakdown"]["control"]

    assert cb["score"] == 0.0
    assert "stun" in cb["no_op_vs_boss"]
    assert arena["score"] > 0.0
    assert "stun" in arena["useful"]


# --------------------------------------------------------------------------- #
# 4. Survival floor: no survival_currency is penalized on a lethal location.
# --------------------------------------------------------------------------- #
def test_survival_floor_penalizes_no_survival_on_lethal_cb():
    ov = _ov(HIT_ENGINE, TANK)
    no_surv = score(["HitDPS", "HitDPS"], "clan_boss", ov)
    with_surv = score(["HitDPS", "Tank"], "clan_boss", ov)

    assert with_surv["fitness"] > no_surv["fitness"]
    # The penalty is the multiplicative survival floor on a lethal location.
    assert no_surv["breakdown"]["survival"]["multiplier"] < \
        with_surv["breakdown"]["survival"]["multiplier"]


# --------------------------------------------------------------------------- #
# 5. Ice Golem: a poison engine is penalized vs a non-poison engine.
# --------------------------------------------------------------------------- #
def test_ice_golem_penalizes_poison_engine():
    ov = _ov(POISON_ENGINE, HP_BURN_ENGINE, TANK)
    poison = score(["PoisonDPS", "Tank"], "ice_golem", ov)
    burn = score(["Burner", "Tank"], "ice_golem", ov)

    assert burn["fitness"] > poison["fitness"]
    pch = poison["breakdown"]["channels"]["poison"]
    assert pch["boss_poison_immune"] is True
    assert pch["score"] == 0.0  # poison damage zeroed vs an immune boss


# --------------------------------------------------------------------------- #
# CB adapter labels its kind correctly (heuristic vs simulated).
# --------------------------------------------------------------------------- #
def test_cb_adapter_labels_kind():
    team = _CB_COMPS["MEN_full"]
    heur = score(team, "clan_boss", {"cb_element": 1})
    assert heur["kind"] == "heuristic"

    try:
        import cb_potential  # noqa: F401
    except Exception as e:  # pragma: no cover
        pytest.skip(f"cb_potential unavailable: {e}")
    sim = score(team, "clan_boss", {"cb_element": 1, "sim": True})
    assert sim["kind"] == "cb_sim"
    assert sim["fitness"] > 0
    assert sim["breakdown"]["source"]
