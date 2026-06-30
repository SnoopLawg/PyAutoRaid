"""M6 CB rediscovery harness — structural sanity tests (no CB sim).

These guard the role-signature abstraction and the rediscovery metric in
`tools/rediscovery_harness.py`. They run fast (pure data + role tags; the
expensive cb_sim path is NOT exercised here).

The thesis (docs/organic_team_milestones.md M6): the ORGANIC generator
re-derives the known DWJ CB meta from game-truth role tags alone. We assert:
  1. The role-signature abstraction is name-agnostic and stable.
  2. On the live roster, the generator rediscovers a meaningful fraction of
     the fieldable DWJ tune signatures (a regression floor, not a target).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import rediscovery_harness as rh  # noqa: E402


def test_signature_is_name_agnostic():
    """Two role-equivalent teams (different champions, same emitted roles)
    must produce the SAME signature — the whole point of rediscovery."""
    roles = {
        "UK_A":   {"uk", "dps"},
        "Heal_A": {"heal", "dps"},
        "Amp_A":  {"def_down", "dps"},
        "Poi_A":  {"poisoner", "dps"},
        "DPS_A":  {"dps"},
        # a totally different cast with the same functional roles
        "UK_B":   {"uk", "dps"},
        "Heal_B": {"shield", "dps"},   # shield is a distinct survival currency
        "Amp_B":  {"weaken", "dps"},   # weaken shares the 'hit' amp channel
        "Poi_B":  {"poisoner", "dps"},
        "DPS_B":  {"dps"},
    }
    sig_a = rh.team_signature(["UK_A", "Heal_A", "Amp_A", "Poi_A", "DPS_A"], roles)
    # Same survival currency on both -> use UK_A's heal twin (uk + heal)
    sig_a2 = rh.team_signature(["UK_B", "Heal_A", "Amp_B", "Poi_B", "DPS_B"], roles)
    assert sig_a == sig_a2
    assert sig_a.short() == sig_a2.short()


def test_signature_axes_capture_structure():
    roles = {
        "Mane": {"uk", "dps"},
        "PK":   {"cd_reset", "heal_active", "dps"},
        "Fayne": {"def_down", "weaken", "dps"},
        "Venom": {"poisoner", "dps"},
        "Geo":  {"burner", "dps"},
    }
    sig = rh.team_signature(["Mane", "PK", "Fayne", "Venom", "Geo"], roles)
    assert sig.survival == frozenset({"unkillable"})
    assert sig.enabler is True                 # Pain Keeper cd_reset
    assert sig.amp == frozenset({"hit"})       # def_down/weaken -> hit channel
    assert sig.engine == frozenset({"hit", "poison", "hp_burn"})


def test_amp_channel_never_mismatched_to_dot():
    """Hit-channel amplifiers (def_down/weaken) must NOT register as a poison
    amplifier — the M1 channel-split invariant."""
    roles = {"A": {"weaken", "def_down", "dps"}, "B": {"poisoner", "dps"},
             "C": {"uk"}, "D": {"heal"}, "E": {"dps"}}
    sig = rh.team_signature(["A", "B", "C", "D", "E"], roles)
    assert "hit" in sig.amp
    assert "poison" not in sig.amp             # no poison_sens provider present


@pytest.mark.skipif(
    not (PROJECT_ROOT / "heroes_6star.json").exists(),
    reason="roster snapshot not present")
def test_rediscovery_floor_on_live_roster():
    """End-to-end (structural only): generator must re-derive a meaningful
    fraction of fieldable DWJ signatures. Floor is conservative (regression
    guard, not the acceptance target)."""
    roles_by_hero, eligible, owned, has_2me = rh.build_roles_and_roster(False)
    assert len(eligible) >= 5

    import cb_team_explorer as cte
    dwj_tunes = cte.load_dwj_tunes()
    assert dwj_tunes, "DWJ tune answer-key missing"

    fieldable_sigs = set()
    for tune in dwj_tunes:
        filled = cte.fill_dwj_tune_with_owned(tune["slots"], set(eligible), roles_by_hero)
        if filled:
            fieldable_sigs.add(rh.team_signature(sorted(filled), roles_by_hero))
    assert fieldable_sigs, "no DWJ tune fieldable from roster"

    gen = cte.generate_candidate_teams(eligible, roles_by_hero,
                                       max_combos=4000, has_double_maneater=has_2me)
    assert gen, "generator produced nothing"
    gen_sigs = {rh.team_signature(t, roles_by_hero) for t in gen}

    matched = fieldable_sigs & gen_sigs
    rate = len(matched) / len(fieldable_sigs)
    # Observed ~0.81 on the current roster; floor well below to absorb data drift.
    assert rate >= 0.5, f"rediscovery rate regressed to {rate:.0%}"
