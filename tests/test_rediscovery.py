"""M6 rediscovery / coverage harness — structural tests.

These guard the role-signature abstraction, the engine-feasibility classifier,
and the end-to-end rediscovery metric in `tools/rediscovery_harness.py` after
the switch from the CB-only `cb_team_explorer` enumerator to the generative
`team_generator` pipeline (M2 resolve + M3 boss_constraints feasibility + M5
fitness).

The pure tests (signature algebra + classifier) run instantly. The end-to-end
test shells out to the CLI so it inherits the harness's PYTHONHASHSEED=0
re-exec and is therefore DETERMINISTIC (the in-process DWJ answer-key fill
iterates sets, so its signatures — and the rate — wobble with the hash seed;
the subprocess pins it).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

import rediscovery_harness as rh  # noqa: E402


# --------------------------------------------------------------------------
# Pure: role-signature algebra (name-agnostic, structural).
# --------------------------------------------------------------------------
def test_signature_is_name_agnostic():
    """Two role-equivalent teams (different champions, same emitted roles) must
    produce the SAME signature — the whole point of rediscovery."""
    roles = {
        "UK_A":   {"uk", "dps"},
        "Heal_A": {"heal", "dps"},
        "Amp_A":  {"def_down", "dps"},
        "Poi_A":  {"poisoner", "dps"},
        "DPS_A":  {"dps"},
        "UK_B":   {"uk", "dps"},
        "Amp_B":  {"weaken", "dps"},
        "Poi_B":  {"poisoner", "dps"},
        "DPS_B":  {"dps"},
    }
    sig_a = rh.team_signature(["UK_A", "Heal_A", "Amp_A", "Poi_A", "DPS_A"], roles)
    sig_a2 = rh.team_signature(["UK_B", "Heal_A", "Amp_B", "Poi_B", "DPS_B"], roles)
    assert sig_a == sig_a2
    assert sig_a.short() == sig_a2.short()


def test_signature_tolerates_duplicate_instance_suffix():
    """team_generator emits 'Maneater_2' for owned duplicates; the signature
    must base-strip the suffix so the dup contributes the same roles."""
    roles = {"Maneater": {"uk", "dps"}, "X": {"def_down", "dps"},
             "Y": {"poisoner", "dps"}, "Z": {"dps"}}
    s1 = rh.team_signature(["Maneater", "X", "Y", "Z"], roles)
    s2 = rh.team_signature(["Maneater_2", "X", "Y", "Z"], roles)
    assert s1 == s2


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
    assert sig.enabler is True
    assert sig.amp == frozenset({"hit"})
    assert sig.engine == frozenset({"hit", "poison", "hp_burn"})


def test_amp_channel_never_mismatched_to_dot():
    """Hit-channel amplifiers (def_down/weaken) must NOT register as a poison
    amplifier — the M1 channel-split invariant."""
    roles = {"A": {"weaken", "def_down", "dps"}, "B": {"poisoner", "dps"},
             "C": {"uk"}, "D": {"heal"}, "E": {"dps"}}
    sig = rh.team_signature(["A", "B", "C", "D", "E"], roles)
    assert "hit" in sig.amp
    assert "poison" not in sig.amp


# --------------------------------------------------------------------------
# Pure: engine-feasibility classifier (explains team_generator's misses).
# --------------------------------------------------------------------------
def test_generatable_by_engine_matches_channel_rule():
    """team_generator's channel_consistent rule: a comp with NO amplifier is
    only generatable if it carries an hp_burn engine (the one channel needing
    no amp). Amp-less pure-hit/WM-GS stalls are structurally excluded."""
    S = rh.RoleSignature
    # amp present -> always generatable
    assert rh.generatable_by_engine(
        S(frozenset({"shield"}), False, frozenset({"hit"}), frozenset({"hit"})))
    # amp-less but hp_burn engine -> generatable via the hp_burn skeleton
    assert rh.generatable_by_engine(
        S(frozenset({"shield", "unkillable"}), True, frozenset(),
          frozenset({"hit", "hp_burn"})))
    # amp-less pure-hit stall -> NOT generatable (needs a hit amplifier)
    assert not rh.generatable_by_engine(
        S(frozenset({"shield", "unkillable"}), False, frozenset(),
          frozenset({"hit"})))


# --------------------------------------------------------------------------
# Live-data: the generative engine fields shield-only stalls (the milestone's
# core claim — the old enumerator HARDCODED a UK-or-BD survival requirement and
# could not). This is robust to the hash seed, so it runs in-process.
# --------------------------------------------------------------------------
@pytest.mark.skipif(
    not (PROJECT_ROOT / "heroes_6star.json").exists(),
    reason="roster snapshot not present")
def test_engine_fields_shield_only_stall():
    import team_generator as tg
    roles_by_hero, eligible, owned, _ = rh.build_roles_and_roster(False)
    opts = tg.GenOpts(pool="owned", top=10**9, max_candidates=10**9,
                      rank_with="heuristic", bucket_cap=12, cores_per_anchor=12)
    res = tg.generate("clan_boss", None, opts)
    assert res, "generator produced nothing"
    sigs = {rh.team_signature(c.team, roles_by_hero) for c in res}
    # at least one comp survives on SHIELD alone (no unkillable / block_damage)
    shield_only = [s for s in sigs if s.survival == frozenset({"shield"})]
    assert shield_only, ("engine produced no shield-only-survival comp — the "
                         "UK/BD hardcode appears to have regressed")


# --------------------------------------------------------------------------
# End-to-end (deterministic via subprocess): CB rediscovery rate + the two
# shield-only signatures the POC structurally missed.
# --------------------------------------------------------------------------
@pytest.mark.skipif(
    not (PROJECT_ROOT / "heroes_6star.json").exists(),
    reason="roster snapshot not present")
def test_cb_rediscovery_end_to_end():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "redisc.json"
        # bucket-cap 12 keeps the subprocess ~15s; the harness re-execs with
        # PYTHONHASHSEED=0 so the rate is deterministic.
        cmd = [sys.executable, str(PROJECT_ROOT / "tools" / "rediscovery_harness.py"),
               "--bucket-cap", "12", "--cores", "12", "--json", str(out)]
        # Pin the seed in the env so the harness SKIPS its os.execv re-exec
        # (on Windows exec detaches the child, racing the JSON write); we still
        # get the deterministic seed-0 result.
        env = dict(os.environ); env["PYTHONHASHSEED"] = "0"
        r = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env,
                           capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, r.stderr[-2000:]
        result = json.loads(out.read_text(encoding="utf-8"))

    assert result["mode"] == "cb_rediscovery"
    assert result["dwj_distinct_signatures"] == 19         # deterministic @seed0
    # Engine re-derives a meaningful fraction (regression floor, not the target).
    assert result["rediscovery_rate_signatures"] >= 0.30, result

    # The UK/BD-hardcode fix: the amplified shield-only stall is rediscovered.
    by_sig = {s["sig"]: s for s in result["shield_only_status"]}
    amp_hit = [s for k, s in by_sig.items() if "surv[shield]" in k and "amp[hit]" in k]
    assert amp_hit and amp_hit[0]["rediscovered"], by_sig

    # The honest classification must flag the amp-less pure-hit stalls as
    # structurally excluded (not silently counted as search failures).
    assert result["missed_structural"], result
    for m in result["missed_structural"]:
        assert "amp[none]" in m["sig"] and "hp_burn" not in m["sig"]
