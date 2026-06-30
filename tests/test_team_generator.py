"""Acceptance tests for M4 — tools/team_generator.py (generative assembly).

Maps 1:1 onto the spec's acceptance list (docs/organic_team_m2_m4_spec.md "M4"):

  1. Reproduce the user's known CB comp in top-K from the *unified* skeleton,
     AND prove the skeletons/search contain ONLY tag predicates (no champion
     names) — the organic proof.
  2. Every emitted CandidateComp independently passes its skeleton team rules.
  3. Faction Wars -> every comp is single-faction.
  4. Clan Boss -> no comp's value derives from a CC/TM effect.
  5. Channel consistency -> a poison-engine comp never credits a Weaken/Dec-DEF
     amplifier as its damage multiplier (asserted via M2 resolve).
  6. Tractability -> pool="all" completes under a wall-clock budget, respects
     max_candidates, and a fixed seed is deterministic.

Test 1 runs the real cb_sim (rank_with="auto") and is the slow one (~1-2 min);
the rest use the fast heuristic ranker.  Everything reads the live repo data
(heroes_6star.json + data/m5_synergy.jsonl + boss_constraints), exactly like
cb_team_explorer, so no fixtures are needed.
"""
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
for p in (str(ROOT), str(TOOLS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import team_generator as tg          # noqa: E402
import synergy_resolver as sr        # noqa: E402

# The user's known-good CB comp (used ONLY by the test as the rediscovery
# target — it appears nowhere in team_generator's skeletons/search).
TARGET = frozenset({"Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"})
CHAMPION_NAMES = sorted(TARGET) + ["Ma'Shalled", "Skullcrusher", "Arbiter",
                                   "Cardiel", "Fayne", "Teodor the Savant"]

# Allowed slot-predicate vocabulary (spec §M4 "Predicate keys").
_PRED_RE = re.compile(
    r"^(survival:[a-z_]+|enabler:[a-z_]+|engine:[a-z_]+|amplifier:[a-z_]+|"
    r"cleanse|heal|tm_control|dot_detonate|acc_capable)$")


# --------------------------------------------------------------------------- #
# shared fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def owned():
    return tg.load_owned_roster()


def _base_set(comp):
    return frozenset(tg._base_name(n) for n in comp.team)


# --------------------------------------------------------------------------- #
# 1. Reproduce the user's comp + organic proof
# --------------------------------------------------------------------------- #
def test_skeletons_and_search_are_tag_predicates_only():
    """Organic proof: the skeletons/search reference ONLY abstract tag
    predicates — zero champion names anywhere in the assembly logic."""
    # (a) every predicate in every channel skeleton parses to the vocabulary
    #     and contains no champion name.
    for ch in tg.ENGINE_CHANNELS:
        sk = tg.build_unified_skeleton(ch)
        assert sk.name.startswith("unified")
        for slot in sk.slots:
            assert slot.require_any, slot
            for pred in slot.require_any:
                assert _PRED_RE.match(pred), f"non-vocab predicate {pred!r}"
                for champ in CHAMPION_NAMES:
                    assert champ.lower() not in pred.lower()

    # (b) the module source itself contains no champion-name string literals
    #     (the strongest form of the proof).
    src = (TOOLS / "team_generator.py").read_text(encoding="utf-8")
    for champ in CHAMPION_NAMES:
        assert champ not in src, f"champion name {champ!r} leaked into source"


def test_reproduce_user_cb_comp_from_unified_skeleton(owned):
    """generate(clan_boss, owned, rank_with='auto') rediscovers the user's
    Maneater/Demytha/Ninja/Geomancer/Venomage comp in the top-K output,
    instantiated from the unified skeleton — with no champion-name templates."""
    res = tg.generate("clan_boss", owned, tg.GenOpts(rank_with="auto", top=40))

    hit = [(i, c) for i, c in enumerate(res, 1) if _base_set(c) == TARGET]
    assert hit, ("user's known CB comp was not rediscovered in the top-K; "
                 f"top teams: {[sorted(c.team) for c in res[:5]]}")
    rank, comp = hit[0]
    # rediscovered organically from the unified skeleton:
    assert comp.skeleton.startswith("unified"), comp.skeleton
    # it was actually evaluated by the CB simulator (auto -> cb_sim on CB):
    assert comp.fitness_kind == "cb_sim"
    assert comp.fitness > 0
    # and it is role-valid (resolve has no broken keystone-enabler edge):
    for k in comp.resolve.keystones:
        if k.get("needs_enabler"):
            assert k.get("enabler_ok"), k


# --------------------------------------------------------------------------- #
# 2. Every emitted comp passes its skeleton's team rules
# --------------------------------------------------------------------------- #
def test_every_emitted_comp_passes_team_rules(owned):
    res = tg.generate("clan_boss", owned, tg.GenOpts(rank_with="heuristic",
                                                     top=40))
    assert len(res) > 0
    for c in res:
        ch = c.skeleton[c.skeleton.index("[") + 1:c.skeleton.rindex("]")]
        sk = tg.build_unified_skeleton(ch)
        recs = [r for r in (tg.record_for(n) for n in c.team) if r is not None]
        ok, rep = tg.team_rules_report(recs, sk, "clan_boss", is_cb=True)
        assert ok, (sorted(c.team), rep)
        # spelled-out rules from the spec:
        assert rep["survival_present"]
        assert rep["keystone_ok"]               # enabler_if_keystone
        assert rep["channel_consistent"]
        assert rep["acc_floor_met"]


# --------------------------------------------------------------------------- #
# 3. Faction Wars -> single faction
# --------------------------------------------------------------------------- #
def test_faction_wars_comps_are_single_faction():
    # pool="all" so factions have enough heroes to field the archetype.
    res = tg.generate("faction_wars", None,
                      tg.GenOpts(pool="all", rank_with="heuristic", top=20,
                                 max_candidates=1500))
    assert len(res) > 0, "no FW comps generated"
    for c in res:
        fr = {tg.record_for(n).get("fraction") for n in c.team}
        fr.discard(None)
        assert len(fr) == 1, (sorted(c.team), fr)
        assert c.constraint_report["faction_ok"]


# --------------------------------------------------------------------------- #
# 4. Clan Boss -> no value from CC/TM
# --------------------------------------------------------------------------- #
def test_cb_no_value_from_cc_or_tm(owned):
    res = tg.generate("clan_boss", owned, tg.GenOpts(rank_with="heuristic",
                                                     top=40))
    assert len(res) > 0
    for c in res:
        # (a) M2 resolve never credits a TM/CC need as satisfied on CB.
        for e in c.resolve.satisfied:
            assert e.tag != "tm_control", (sorted(c.team), str(e))
        # (b) the heuristic fitness breakdown counts ZERO useful control value
        #     (the CB boss no-ops every control/TM effect).
        bd = c.constraint_report.get("fitness_breakdown", {})
        control = bd.get("control", {})
        assert control.get("useful", []) == [], (sorted(c.team), control)
        assert control.get("score", 0) == 0


# --------------------------------------------------------------------------- #
# 5. Channel consistency — poison engine never credits a Weaken amplifier
# --------------------------------------------------------------------------- #
def test_poison_engine_does_not_credit_weaken_amplifier(owned):
    """A poison engine carrying needs:def_break (m5_synergy_graph adds it to all
    attackers) must NOT be credited a Dec-DEF/Weaken edge — that amplifier is a
    HIT-channel multiplier, not a poison one.  Asserted via M2 resolve."""
    res = tg.generate("clan_boss", owned,
                      tg.GenOpts(rank_with="heuristic", top=60))
    poison_comps = [c for c in res if c.skeleton == "unified[poison]"]
    assert poison_comps, "no poison-engine comps generated"

    checked = 0
    for c in poison_comps:
        recs = {r["name"]: r for r in
                (tg.record_for(n) for n in c.team) if r is not None}
        poison_engines = {n for n, r in recs.items()
                          if "poison" in (r.get("engine_channel") or [])
                          and not (set(r.get("engine_channel") or [])
                                   & {"hit", "wm_gs", "bring_it_down"})}
        if not poison_engines:
            continue
        checked += 1
        # No satisfied def_break (hit-channel) edge may target a pure-poison
        # engine — the channel gate must have rejected it.
        for e in c.resolve.satisfied:
            if e.tag == "def_break":
                assert e.consumer not in poison_engines, (
                    sorted(c.team), str(e),
                    "Weaken/Dec-DEF wrongly credited to a poison engine")
                assert e.channel == "hit"
    assert checked > 0, "no pure-poison engine appeared to verify the gate"


def test_resolve_channel_gate_rejects_weaken_to_poison_directly():
    """Direct M2 check (no search): a hand-built comp with a hit amplifier and
    a pure-poison engine must route def_break to the hit engine, never the
    poison engine."""
    comp = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
    rr = sr.resolve(comp, sr.ResolveContext(location="clan_boss"))
    # Venomage is the pure-poison engine; it must not be a def_break consumer.
    for e in rr.satisfied:
        if e.tag == "def_break":
            assert e.consumer != "Venomage", str(e)
    # and the channel-mismatch shows up as a note, not satisfied/broken.
    assert any("Venomage" in n and "poison_synergy" in n
               and "channel mismatch" in n for n in rr.notes), rr.notes


# --------------------------------------------------------------------------- #
# 6. Tractability — pool=all under budget, max_candidates respected, deterministic
# --------------------------------------------------------------------------- #
def test_pool_all_tractable_and_deterministic():
    opts = lambda: tg.GenOpts(pool="all", rank_with="heuristic", top=20,
                              max_candidates=800, seed=1234)
    t0 = time.time()
    r1 = tg.generate("clan_boss", None, opts())
    elapsed = time.time() - t0
    assert elapsed < 60, f"pool=all heuristic took {elapsed:.1f}s (budget 60s)"
    assert len(r1) > 0
    # max_candidates respected.
    assert r1.report["candidates_evaluated"] <= 800

    # fixed seed -> deterministic ordering.
    r2 = tg.generate("clan_boss", None, opts())
    assert [c.team for c in r1] == [c.team for c in r2]


def test_no_engine_channel_reports_and_emits_nothing():
    """A roster with no damage engine emits nothing and says why (edge case)."""
    res = tg.generate("clan_boss", ["Demytha"],   # block-damage only, no engine
                      tg.GenOpts(rank_with="heuristic"))
    assert len(res) == 0
    assert "error" in res.report
