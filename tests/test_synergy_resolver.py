"""M2 acceptance tests for tools/synergy_resolver.py.

Covers the spec's five acceptance criteria:
  1. Known DWJ CB tune (Maneater/Demytha/Ninja/Geomancer/Venomage):
     Maneater keystone enabler_ok; Ninja(hit) has a satisfied def_break edge;
     NO satisfied def_break edge credited to Venomage's poison engine.
  2. Mis-ordered comp (slowest + short-duration Dec-DEF provider) -> broken.
  3. Self-amplifier (Frozen Banshee) covers its own poison_synergy (reason "self").
  4. Keystone-enabler compat: Maneater+Pain Keeper -> enabler_ok; a revive
     keystone + buff_extension-only -> NOT satisfied.
  5. Two HP-burners -> 2nd flagged redundant (slot cap max_hp_burn=1).

Plus the headline channel rule: a pure-poison engine carrying needs:def_break
is NEVER credited a Weaken/Dec-DEF edge (the "won't credit Weaken->poison"
acceptance) -> it lands in notes, not satisfied/broken.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import synergy_resolver as sr  # noqa: E402


# --------------------------------------------------------------------- helpers
def _rec(name, **kw):
    """Build a synthetic enriched record with M1-complete safe defaults."""
    base = {
        "name": name,
        "element": "Void",
        "fraction": "Generic",
        "provides": [],
        "needs": [],
        "amplifier_channel": "none",
        "engine_channel": [],
        "survival_currency": None,
        "enabler": None,
        "keystone_needs_enabler": False,
        "debuffs_control_only": False,
    }
    base.update(kw)
    return base


MEN = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]


# ============================================================= acceptance #1
def test_known_dwj_tune_channels_and_keystone():
    res = sr.resolve(MEN, sr.ResolveContext(location="clan_boss"))

    # Maneater keystone (unkillable) is enabled (Demytha buff_extension /
    # Ninja+Geo cooldown_reduction are all unkillable-compatible).
    ks = res.keystone_for("Maneater")
    assert ks is not None, "Maneater should appear in keystones[]"
    assert ks["currency"] == "unkillable"
    assert ks["enabler_ok"] is True

    # Ninja is a hit engine -> has a satisfied def_break edge (self Dec-DEF).
    ninja_db = res.satisfied_edges(tag="def_break", consumer="Ninja")
    assert ninja_db, "Ninja (hit engine) should have a satisfied def_break edge"

    # Venomage is a poison engine -> NO satisfied def_break edge (channel
    # negative). Its needs carry poison_synergy, not def_break, so nothing is
    # credited; the assertion must hold regardless.
    assert res.satisfied_edges(tag="def_break", consumer="Venomage") == []
    assert not any(e.tag == "def_break" and e.consumer == "Venomage"
                   for e in res.broken)


def test_channel_negative_wont_credit_weaken_to_poison():
    """THE acceptance: a pure-poison engine carrying needs:def_break must NOT
    be credited a Weaken/Dec-DEF edge -> notes, not satisfied/broken."""
    weakener = _rec("Weakener", amplifier_channel="hit",
                    provides=["enemy_debuff:Weaken", "enemy_debuff:Decrease DEF"])
    poison_engine = _rec("PurePoison", amplifier_channel="none",
                         engine_channel=["poison"],
                         provides=["dot:Poison"],
                         needs=["def_break", "poison_synergy"])
    res = sr.resolve_records([weakener, poison_engine],
                             sr.ResolveContext(mode="generic"))

    assert res.satisfied_edges(tag="def_break") == []
    assert not any(e.tag == "def_break" for e in res.broken)
    # The mismatch is explained in notes, not silently dropped.
    assert any("def_break" in n and "channel mismatch" in n
               for n in res.notes)


# ============================================================= acceptance #2
def test_misordered_def_break_edge_is_broken():
    slow_provider = _rec("SlowFayne", amplifier_channel="hit",
                         provides=["enemy_debuff:Decrease DEF"])
    fast_nuker = _rec("FastNuker", engine_channel=["hit"],
                      needs=["def_break"])
    ctx = sr.ResolveContext(
        mode="generic",
        speeds={"SlowFayne": 100, "FastNuker": 220},  # provider is slowest
        durations={"SlowFayne": 1},                    # short debuff
        cooldowns={"FastNuker": 3},                    # needs longer coverage
    )
    res = sr.resolve_records([slow_provider, fast_nuker], ctx)

    assert res.satisfied_edges(tag="def_break") == []
    broken = [e for e in res.broken if e.tag == "def_break"]
    assert broken, "the late + short-duration Dec-DEF edge should be broken"
    assert broken[0].provider == "SlowFayne"
    assert broken[0].consumer == "FastNuker"
    assert "late_provider" in broken[0].ordering_reason


# ============================================================= acceptance #3
def test_self_amplifier_frozen_banshee():
    res = sr.resolve(["Frozen Banshee"], sr.ResolveContext(location="clan_boss"))
    ps = res.satisfied_edges(tag="poison_synergy", consumer="Frozen Banshee")
    assert ps, "Frozen Banshee should self-cover poison_synergy"
    edge = ps[0]
    assert edge.provider == edge.consumer == "Frozen Banshee"
    assert edge.ordering_reason == "self"
    assert edge.channel == "poison"


# ============================================================= acceptance #4
def test_keystone_enabler_compat_positive():
    res = sr.resolve(["Maneater", "Pain Keeper"],
                     sr.ResolveContext(location="clan_boss"))
    ks = res.keystone_for("Maneater")
    assert ks is not None and ks["enabler_ok"] is True
    # Pain Keeper supplies cooldown_reduction, which is unkillable-compatible.
    assert "cooldown_reduction" in ks["reason"] or ks["enabler"] == "Pain Keeper"


def test_keystone_enabler_compat_negative_revive_needs_cdr():
    revive = _rec("ReviveHero", survival_currency="revive_on_death",
                  keystone_needs_enabler=True)
    extender = _rec("Extender", enabler="buff_extension",
                    provides=["buff_extension"])
    res = sr.resolve_records([revive, extender], sr.ResolveContext())
    ks = res.keystone_for("ReviveHero")
    assert ks is not None
    # revive_on_death is compatible only with cooldown_reduction; a
    # buff_extension-only provider must NOT satisfy it.
    assert ks["enabler_ok"] is False


# ============================================================= acceptance #5
def test_two_hp_burners_second_redundant():
    b1 = _rec("Burner1", engine_channel=["hp_burn"], provides=["dot:HP Burn"])
    b2 = _rec("Burner2", engine_channel=["hp_burn"], provides=["dot:HP Burn"])
    res = sr.resolve_records([b1, b2], sr.ResolveContext(location="clan_boss"))
    assert any("redundant" in n and "Burner2" in n and "hp_burn" in n
               for n in res.notes), \
        "the 2nd HP burner should be flagged redundant (slot cap 1)"


# ------------------------------------------------------ supporting invariants
def test_cb_tm_control_is_noop_vs_boss():
    """tm_control is a no-op vs the CB boss -> notes, never satisfied."""
    res = sr.resolve(MEN, sr.ResolveContext(location="clan_boss"))
    assert res.satisfied_edges(tag="tm_control") == []
    assert any("tm_control" in n and "no-op" in n for n in res.notes)


def test_missing_m1_fields_tolerated():
    """A record lacking M1 fields resolves with safe defaults (no crash)."""
    bare = {"name": "LegacyHero", "provides": ["enemy_debuff:Decrease DEF"],
            "needs": ["def_break"]}
    res = sr.resolve_records([bare], sr.ResolveContext(mode="generic"))
    # No engine channel by default -> def_break is a category mismatch, noted.
    assert isinstance(res, sr.ResolveResult)
    assert res.satisfied_edges(tag="def_break") == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
