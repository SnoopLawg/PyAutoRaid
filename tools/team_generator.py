"""Milestone 4 — Generative team-assembly engine.

Replaces the *template-matching* recommenders (`comp_finder` scores scraped
DWJ tunes against the roster; `m5_recommender` greedily covers M5 axes) with a
location-agnostic constraint-satisfaction generator that DERIVES teams from
game-truth champion tags.

The engine is driven by **archetype skeletons** that are ABSTRACT tag-predicate
slot constraints — *never* champion lineups. The canonical `unified` skeleton
(survival + enabler + amplifier + engine + flex) is instantiated once per
*engine channel present in the roster* (hit / wm_gs / poison / hp_burn /
bring_it_down). The proof it isn't replaying templates: the skeletons and the
search contain ZERO champion names, yet the generator rediscovers the known
meta comps from the M1 tags alone.

Pipeline (spec docs/organic_team_m2_m4_spec.md "M4"):
  1. M3 hard filters   (boss_constraints: faction_lock / affinity / CC-TM no-op)
  2. per-skeleton/channel bucketing of the roster by slot predicate
  3. slot-by-slot CSP search: MRV ordering + beam (width 200) + incremental
     team-rule pruning (branch-and-bound `can_add`) + cheap pre-score
     (cb_team_explorer.predict_score) ; dedup by frozenset(team)
  4. M2 resolve each comp; drop comps with unmet HARD edges (no survival /
     broken keystone-enabler / no channel-consistent amplifier->engine)
  5. rank by M5 fitness (cb_sim for CB via rank_with=auto, heuristic elsewhere)
  6. novelty flag vs scraped DWJ templates

Reuse anchors (cited functions):
  - cb_team_explorer.predict_score            cheap pre-sim prune score
  - cb_team_explorer.load_dwj_tunes           novelty cross-reference templates
  - cb_sim.DUPLICATE_INSTANCE_HEROES          '<hero>_2' duplicate convention
  - synergy_resolver.resolve / ResolveContext M2 dependency+ordering reasoning
  - synergy_resolver.KEYSTONE_ENABLER_COMPAT  keystone<-enabler compat table
  - boss_constraints.get_constraints/.acc_floor/.faction_lock/.is_effect_useful
  - fitness.score                             M5 universal fitness (heuristic/cb_sim)
  - fitness.synergy_data.get_record           normalized M1 per-hero record

CLI:
    python tools/team_generator.py clan_boss
    python tools/team_generator.py faction_wars --pool owned --top 15
    python tools/team_generator.py clan_boss --rank-with heuristic
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import boss_constraints  # noqa: E402
import synergy_resolver  # noqa: E402
from synergy_resolver import (  # noqa: E402
    KEYSTONE_ENABLER_COMPAT, ResolveContext, resolve as m2_resolve)
from fitness import score as fitness_score  # noqa: E402
from fitness import synergy_data as sd  # noqa: E402
import cb_team_explorer  # noqa: E402

SYNERGY = ROOT / "data" / "m5_synergy.jsonl"

# Engine channels the unified skeleton can be bound to (M1 vocab).
ENGINE_CHANNELS = ("hit", "wm_gs", "poison", "hp_burn", "bring_it_down")

# Which amplifier channel amplifies a given engine channel (game-truth,
# organic_team_milestones.md:32-36). Dec-DEF/Weaken (amp "hit") amplify
# hit/wm_gs/bring_it_down; Poison-Sens (amp "poison") amplifies poison;
# hp_burn is amplified by neither (detonation only).
AMP_FOR_ENGINE = {
    "hit": "hit",
    "wm_gs": "hit",
    "bring_it_down": "hit",
    "poison": "poison",
    "hp_burn": None,
}

# CB-family locations (cb_sim is the only true outcome simulator).
_CB_LOCATIONS = {"clan_boss", "cb", "demon_lord", "demon_lord_unm", "clanboss"}

# Survival currencies that COVER an unavoidable hit (the stall keystones).
# heal_lifesteal is sustain, not a cover, so it is not a stall keystone — the
# survival slot of the stall archetype requires one of these.
STRONG_KEYSTONES = ("unkillable", "block_damage", "shield",
                    "ally_protect", "revive_on_death")


# ============================================================ options / output
@dataclass
class GenOpts:
    size: int = 5
    pool: str = "owned"              # "owned" | "all"
    top: int = 30
    beam_width: int = 200
    max_candidates: int = 5000
    skeletons: Optional[list] = None  # explicit Skeleton list (else auto)
    cb_element: int = 4              # 1=Magic 2=Force 3=Spirit 4=Void
    # CB sim uses the FAST potential-gear sim by default (~0.3s/comp) so the
    # two-phase rank stays tractable; flip to True for the calibrated
    # current-gear sim (slower, owned heroes only).
    use_current_gear: bool = False
    rank_with: str = "auto"         # "auto" | "cb_sim" | "heuristic"
    # --- extra knobs (not in the bare spec; documented in the module note) ---
    sim_top: int = 90               # cores phase-1 sims (potential gear, fast)
    refine_cores: int = 20          # top cb_sim cores whose flex is fully simmed
    flex_cap: int = 16              # flex variants simmed per refined core
    pool_cap: int = 24              # per-slot bucket cap when pool=="all"
    bucket_cap: int = 8             # per-slot bucket cap when pool=="owned"
    cores_per_anchor: int = 6       # survival/enabler cores kept per anchor
    seed: int = 1234                # determinism for the (rare) tie shuffles


@dataclass
class CandidateComp:
    team: list                      # hero names in slot order (may hold Name_2)
    skeleton: str                   # skeleton name, e.g. "unified[hit]"
    resolve: object                 # synergy_resolver.ResolveResult
    fitness: float
    fitness_kind: str               # "cb_sim" | "heuristic"
    constraint_report: dict
    novelty: bool

    def as_dict(self) -> dict:
        return {
            "team": list(self.team),
            "skeleton": self.skeleton,
            "fitness": self.fitness,
            "fitness_kind": self.fitness_kind,
            "novelty": self.novelty,
            "constraint_report": self.constraint_report,
        }


# ================================================================= skeletons
@dataclass
class SlotConstraint:
    name: str
    require_any: list               # predicate keys (OR-ed)
    optional: bool = False


@dataclass
class Skeleton:
    name: str
    slots: list                     # list[SlotConstraint]
    channel: str                    # bound engine channel
    team_rules: tuple = (
        "survival_present", "enabler_if_keystone", "channel_consistent",
        "acc_floor_met", "boss_hard_filters")


def build_unified_skeleton(channel: str, size: int = 5) -> Skeleton:
    """The canonical `unified` skeleton bound to one engine `channel`.

    Slots are TAG PREDICATES only — no champion names anywhere. The amplifier
    slot is bound to the amplifier channel that actually helps this engine
    (AMP_FOR_ENGINE); for hp_burn (no amplifier exists) it becomes an optional
    detonator slot.
    """
    amp_ch = AMP_FOR_ENGINE[channel]
    slots = [
        SlotConstraint("survival", [f"survival:{k}" for k in STRONG_KEYSTONES],
                       optional=False),
        # enabler is conditionally required (team rule enabler_if_keystone);
        # modeled here as optional so the search still fills it when present.
        SlotConstraint("enabler", ["enabler:any"], optional=True),
    ]
    if amp_ch is not None:
        slots.append(SlotConstraint("amplifier",
                                    [f"amplifier:{amp_ch}"], optional=False))
    else:
        # hp_burn: no amplifier channel -> detonator is the multiplier proxy.
        slots.append(SlotConstraint("amplifier", ["dot_detonate"], optional=True))
    slots.append(SlotConstraint("engine", [f"engine:{channel}"], optional=False))
    flex_pred = [f"engine:{channel}", "dot_detonate", "cleanse", "heal"]
    if amp_ch is not None:
        flex_pred.insert(1, f"amplifier:{amp_ch}")
    slots.append(SlotConstraint("flex", flex_pred, optional=True))

    # Pad/trim to requested team size with extra flex slots.
    while len(slots) < size:
        slots.append(SlotConstraint(f"flex{len(slots)}", flex_pred, optional=True))
    slots = slots[:max(size, 4)]
    return Skeleton(name=f"unified[{channel}]", slots=slots, channel=channel)


def build_double_survival_skeleton(channel: str, size: int = 5) -> Skeleton:
    """A multi-keystone STALL skeleton bound to one engine `channel`: TWO
    distinct survival slots (+ optional enabler + engine + flex).

    Slots are TAG PREDICATES only — no champion names. The single-survival
    `unified` skeleton under-produces 2-/3-currency stalls (the Batman Forever /
    Budget-UK / Deacon / CatEater family) because two sustained keystones rarely
    co-occur in one beam; a dedicated second survival slot makes the
    multi-keystone stall systematic. No amplifier slot — these are the
    amp-less passive-damage stalls (the amplifier remains a SCORED preference via
    skeleton_prescore when one happens to fill a flex/engine slot).
    """
    keystone_preds = [f"survival:{k}" for k in STRONG_KEYSTONES]
    slots = [
        SlotConstraint("survival", list(keystone_preds), optional=False),
        SlotConstraint("survival2", list(keystone_preds), optional=False),
        # enabler conditionally required (team rule enabler_if_keystone);
        # modeled optional so the search fills it when a keystone needs it.
        SlotConstraint("enabler", ["enabler:any"], optional=True),
        SlotConstraint("engine", [f"engine:{channel}"], optional=False),
    ]
    flex_pred = [f"engine:{channel}", "dot_detonate", "cleanse", "heal"]
    slots.append(SlotConstraint("flex", flex_pred, optional=True))
    while len(slots) < size:
        slots.append(SlotConstraint(f"flex{len(slots)}", flex_pred,
                                    optional=True))
    slots = slots[:max(size, 4)]
    return Skeleton(name=f"double_survival[{channel}]", slots=slots,
                    channel=channel)


# Named presets are THIN wrappers over the unified skeleton (spec). The unified
# (primary) skeletons are emitted FIRST for every channel, then the
# double_survival (multi-keystone stall) variants — so a comp the canonical
# unified skeleton can build is attributed to it (the stall variant only claims
# the lean comps unified cannot produce, via the cross-skeleton team dedup).
def build_named_skeletons(channels_present: set, size: int = 5) -> list:
    present = [ch for ch in ENGINE_CHANNELS if ch in channels_present]
    out = [build_unified_skeleton(ch, size) for ch in present]
    out += [build_double_survival_skeleton(ch, size) for ch in present]
    return out


# ============================================================ record helpers
_catalog_names_cache: Optional[list] = None


def _all_catalog_names() -> list:
    global _catalog_names_cache
    if _catalog_names_cache is None:
        names = []
        with SYNERGY.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    names.append(json.loads(line)["name"])
        _catalog_names_cache = names
    return list(_catalog_names_cache)


def _base_name(name: str) -> str:
    """Strip a duplicate-instance suffix ('<hero>_2' -> '<hero>')."""
    if "_" in name:
        head, _, tail = name.rpartition("_")
        if tail.isdigit() and head:
            return head
    return name


def record_for(name: str) -> Optional[dict]:
    """Normalized M1 record for a (possibly Name_2-suffixed) hero name."""
    rec = sd.get_record(name)
    if rec is None:
        rec = sd.get_record(_base_name(name))
    if rec is None:
        return None
    rec = dict(rec)
    rec["name"] = name              # keep the caller's display/instance name
    return rec


def load_owned_roster() -> list:
    """The user's 6-star roster (reuses cb_team_explorer's data sources:
    heroes_6star.json for owned 6★, all_heroes.json for duplicate detection).

    Appends a 'Name_2' instance for any DUPLICATE_INSTANCE_HEROES the user owns
    two+ of (cb_sim dup convention).
    """
    hs6 = json.loads((ROOT / "heroes_6star.json").read_text(encoding="utf-8"))
    owned = [h["name"] for h in hs6.get("heroes", []) if h.get("name")]
    # Duplicate instances (data-driven, no champion names hardcoded here).
    try:
        from cb_sim import DUPLICATE_INSTANCE_HEROES
    except Exception:
        DUPLICATE_INSTANCE_HEROES = ()
    counts: dict = {}
    try:
        ah = json.loads((ROOT / "all_heroes.json").read_text(encoding="utf-8"))
        for h in ah.get("heroes", []):
            n = h.get("name")
            if n:
                counts[n] = counts.get(n, 0) + 1
    except Exception:
        pass
    extras = []
    for n in owned:
        if n in DUPLICATE_INSTANCE_HEROES and counts.get(n, 0) >= 2:
            extras.append(f"{n}_2")
    return owned + extras


# ============================================================ predicate eval
def slot_match(predicate_key: str, rec: dict) -> bool:
    """Evaluate ONE tag predicate against a normalized M1 record.

    Vocabulary (spec): survival:<currency>|any, enabler:<kind>|any,
    engine:<channel>, amplifier:<channel>, cleanse, heal, tm_control,
    dot_detonate, acc_capable.
    """
    prov = set(rec.get("provides", []))
    if predicate_key.startswith("survival:"):
        want = predicate_key.split(":", 1)[1]
        cur = rec.get("survival_currency")
        return bool(cur) if want == "any" else cur == want
    if predicate_key.startswith("enabler:"):
        want = predicate_key.split(":", 1)[1]
        en = rec.get("enabler")
        return bool(en) if want == "any" else en == want
    if predicate_key.startswith("engine:"):
        want = predicate_key.split(":", 1)[1]
        return want in (rec.get("engine_channel") or [])
    if predicate_key.startswith("amplifier:"):
        want = predicate_key.split(":", 1)[1]
        return rec.get("amplifier_channel") == want
    if predicate_key == "cleanse":
        return "cleanse" in prov
    if predicate_key == "heal":
        return ("heal" in prov or "team_buff:Continuous Heal" in prov
                or "team_buff:Shield" in prov)
    if predicate_key == "tm_control":
        return "tm_control" in prov
    if predicate_key == "dot_detonate":
        return "dot_detonate" in prov
    if predicate_key == "acc_capable":
        return any(p.startswith("enemy_debuff:") for p in prov)
    return False


def slot_accepts(slot: SlotConstraint, rec: dict) -> bool:
    return any(slot_match(pk, rec) for pk in slot.require_any)


# ============================================================ boss filtering
def _useful_vs_boss(rec: dict, location: str) -> bool:
    """A hero contributes NOTHING vs the boss iff its only output is control/TM
    the boss no-ops AND it has no survival / engine / amplifier / enabler / heal.

    This is the "exclude CC/TM-immune from value" hard filter (test #4).
    """
    if rec.get("survival_currency") or rec.get("enabler"):
        return True
    if rec.get("engine_channel"):
        return True
    if rec.get("amplifier_channel") and rec["amplifier_channel"] != "none":
        return True
    prov = rec.get("provides", [])
    # heal / cleanse are useful sustain.
    if any(p in ("heal", "cleanse", "team_buff:Continuous Heal",
                 "team_buff:Shield") for p in prov):
        return True
    # Any debuff/buff that the boss does NOT no-op is useful.
    for p in prov:
        if p.startswith("enemy_debuff:"):
            tag = sd.CONTROL_PROVIDES_TO_TAG.get(p)
            if tag is None:
                return True            # non-control debuff (DEF down etc.)
            try:
                if boss_constraints.is_effect_useful(location, tag):
                    return True
            except KeyError:
                return True
        elif p.startswith("team_buff:"):
            return True
    return False


def filter_roster(roster_names: list, location: str, cb_element: int,
                  is_cb: bool) -> tuple:
    """Apply per-hero hard filters; return (kept_records, dropped_report)."""
    kept, dropped = [], []
    for nm in roster_names:
        rec = record_for(nm)
        if rec is None:
            dropped.append({"hero": nm, "reason": "no M1 record"})
            continue
        if is_cb and not _useful_vs_boss(rec, location):
            dropped.append({"hero": nm,
                            "reason": "value only from CC/TM the boss no-ops"})
            continue
        kept.append(rec)
    return kept, dropped


# ============================================================ team-rule checks
def _channel_consistent(recs: list, channel: str) -> bool:
    """A comp is channel-consistent iff it fields a damage ENGINE of `channel`.

    RELAXED (task #45, 2026-06): the engine's channel-correct AMPLIFIER
    (Dec-DEF/Weaken for hit/wm_gs/bring_it_down; Poison-Sens for poison) used to
    be HARD-REQUIRED here, which structurally excluded the amp-less pure-hit /
    WM-GS stall tunes (BatManSaladEater, Bateater, Man Salad, Myth Heir Salad).
    Those stalls are VIABLE without an amplifier — damage accrues passively over
    the 50-turn stall (WM/GS procs + DoTs). The amplifier genuinely HELPS (e.g.
    our capture showed WM procced at calc_raw 93750 = 75000 x 1.25 Weaken), so
    it is now a strong SCORED preference (skeleton_prescore) instead of a gate:
    amp-less stalls are FEASIBLE but rank below their amp'd equivalents.

    Channel-CORRECTNESS for CREDITING is unchanged: M2 resolve never routes a
    hit amplifier to a poison engine, and skeleton_prescore only credits an
    amplifier whose channel matches AMP_FOR_ENGINE[channel].
    """
    return any(channel in (r.get("engine_channel") or []) for r in recs)


def team_rules_report(recs: list, skeleton: Skeleton, location: str,
                      is_cb: bool) -> tuple:
    """Evaluate all HARD team rules; return (all_pass, report)."""
    rep: dict = {"skeleton": skeleton.name, "channel": skeleton.channel}

    survivors = [r["name"] for r in recs if r.get("survival_currency")]
    survival_present = bool(survivors)

    enablers_present = {r["enabler"] for r in recs if r.get("enabler")}
    keystone_detail, keystone_ok = [], True
    for r in recs:
        if r.get("keystone_needs_enabler") and r.get("survival_currency"):
            compat = KEYSTONE_ENABLER_COMPAT.get(r["survival_currency"], set())
            matched = sorted(enablers_present & compat)
            keystone_detail.append({"keystone": r["name"],
                                    "currency": r["survival_currency"],
                                    "needs_any_of": sorted(compat),
                                    "matched_by": matched,
                                    "satisfied": bool(matched)})
            if not matched:
                keystone_ok = False

    channel_consistent = _channel_consistent(recs, skeleton.channel)

    # acc_floor_met: a debuff-reliant team must field acc-capable debuffers.
    acc_floor = None
    try:
        acc_floor = boss_constraints.acc_floor(location)
    except KeyError:
        acc_floor = None
    debuffers = [r["name"] for r in recs
                 if any(p.startswith("enemy_debuff:") for p in r.get("provides", []))]
    acc_ok = (acc_floor is None) or bool(debuffers)

    # boss_hard_filters: faction lock single-faction (FW); affinity advisory.
    faction_ok = True
    try:
        lock = boss_constraints.faction_lock(location)
    except KeyError:
        lock = False
    fractions = sorted({r.get("fraction") for r in recs if r.get("fraction")})
    if lock:
        faction_ok = len(fractions) <= 1

    rep.update({
        "survival_present": survival_present, "survivors": survivors,
        "keystones": keystone_detail, "keystone_ok": keystone_ok,
        "channel_consistent": channel_consistent,
        "acc_floor": acc_floor, "acc_floor_met": acc_ok, "debuffers": debuffers,
        "faction_lock": lock, "fractions": fractions, "faction_ok": faction_ok,
    })
    all_pass = (survival_present and keystone_ok and channel_consistent
                and acc_ok and faction_ok)
    rep["all_pass"] = all_pass
    return all_pass, rep


def can_add(partial_recs: list, rec: dict, location: str,
            faction_lock: bool) -> bool:
    """Incremental branch-and-bound prune (only HARD, monotone constraints).

    Currently: distinctness (handled by caller) + faction consistency for FW.
    Other team rules (survival/keystone/channel) are non-monotone — they can
    still be satisfied by later slots — so they are NOT pruned here, only
    checked once the comp is complete.
    """
    if faction_lock:
        fr = rec.get("fraction")
        existing = {r.get("fraction") for r in partial_recs if r.get("fraction")}
        if fr and existing and (existing != {fr}):
            return False
    return True


# ============================================================ pre-score
def _roles_from_rec(rec: dict) -> set:
    """Map an M1 record onto cb_team_explorer's role vocabulary so we can reuse
    cb_team_explorer.predict_score as the cheap pre-sim prune signal."""
    roles: set = set()
    sc = rec.get("survival_currency")
    if sc == "unkillable":
        roles.add("uk")
    elif sc == "block_damage":
        roles.add("bd")
    elif sc == "ally_protect":
        roles.add("ally_protect")
    prov = set(rec.get("provides", []))
    if "heal" in prov or "team_buff:Continuous Heal" in prov:
        roles.add("heal")
    if "team_buff:Shield" in prov:
        roles.add("shield")
    if "enemy_debuff:Decrease DEF" in prov:
        roles.add("def_down")
    if "enemy_debuff:Weaken" in prov:
        roles.add("weaken")
    if "dot:Poison" in prov:
        roles.add("poisoner")
    if "dot:HP Burn" in prov:
        roles.add("burner")
    if rec.get("engine_channel"):
        roles.add("dps")
    if rec.get("amplifier_channel") == "poison":
        roles.add("poison_sens")
    return roles


def _prescore(team_names: list, roles_by_hero: dict) -> float:
    """Cheap generic pre-score — reuses cb_team_explorer.predict_score over our
    game-truth role tags (no tier list). Used for diversity tie-breaks."""
    return cb_team_explorer.predict_score(team_names, roles_by_hero)


def skeleton_prescore(recs: list, skeleton: Skeleton,
                      roles_by_hero: dict | None = None) -> float:
    """CHANNEL-AWARE structural pre-score: how cleanly does this (partial) comp
    instantiate the archetype `skeleton`?  Rewards a strong survival keystone
    with a *satisfied* enabler + a channel amplifier + channel engines, so the
    beam retains canonical comps and the two-stage prune sims them.

    This adapts the spec's "reuse predict_score" pre-score: the bare M5
    heuristic / predict_score under-rate the known CB meta (survival-stall
    comps), so the cheap prune that decides WHICH comps reach cb_sim is made
    channel-structural instead.  predict_score is kept as a diversity tie-break.
    """
    ch = skeleton.channel
    amp_ch = AMP_FOR_ENGINE[ch]
    score = 0.0
    enablers_present = {r["enabler"] for r in recs if r.get("enabler")}

    # ---- multi-keystone STALL skeleton: score by SURVIVAL DEPTH, not damage. -
    # The double_survival archetype's value is COVERAGE — multiple distinct,
    # enabler-satisfied keystones holding the boss AoE/stun for 50 turns — and
    # its damage accrues passively. Scoring it with the damage-breadth/amplifier
    # terms below would let rich amp'd cores out-compete the lean multi-keystone
    # cores out of the per-anchor beam, which is exactly what under-produced the
    # amp-less multi-keystone stall signatures (Batman / Budget-UK / Deacon
    # tunes). So a stall core is ranked
    # by how many distinct keystone currencies it lands (each weighted by
    # enabler satisfaction), with only a light channel-engine presence nudge.
    if skeleton.name.startswith("double_survival"):
        per_currency: dict = {}
        for r in recs:
            cur = r.get("survival_currency")
            if not cur:
                continue
            w = sd.survival_weight(r)
            if r.get("keystone_needs_enabler"):
                compat = KEYSTONE_ENABLER_COMPAT.get(cur, set())
                w *= 1.0 if (enablers_present & compat) else 0.25
            per_currency[cur] = max(per_currency.get(cur, 0.0), w)
        # depth across DISTINCT currencies (so a 2nd/3rd cover is rewarded,
        # unlike the capped single-survival coverage term below).
        score += 3.0 * sum(per_currency.values())
        if any(ch in (r.get("engine_channel") or []) for r in recs):
            score += 1.0
        # detonation is the only damage lever a passive stall really wants.
        if any("dot_detonate" in r.get("provides", []) for r in recs):
            score += 0.3
        if roles_by_hero is not None:
            flat: set = set()
            for r in recs:
                flat |= roles_by_hero.get(r["name"], set())
            score += 0.05 * len(flat)
        return score

    # Survival COVERAGE — a stall needs the boss AoE/stun covered, but only ~2
    # *sustained* strong keystones; beyond that the extra survival slot is a
    # wasted damage slot (cb_sim does not reward a 3rd cover). So coverage is
    # CAPPED: 2 enabled keystones lifts survival fully; more adds nothing.
    coverage = 0.0
    for r in recs:
        cur = r.get("survival_currency")
        if not cur:
            continue
        w = sd.survival_weight(r)
        if r.get("keystone_needs_enabler"):
            compat = KEYSTONE_ENABLER_COMPAT.get(cur, set())
            w *= 1.0 if (enablers_present & compat) else 0.25
        coverage += w
    score += 3.0 * min(coverage, 1.85)           # cap ≈ unkillable + block_dmg
    # DAMAGE structure — a real engine + a channel amplifier that compounds.
    if amp_ch is not None and any(r.get("amplifier_channel") == amp_ch
                                  for r in recs):
        score += 2.0
    n_engines = sum(1 for r in recs if ch in (r.get("engine_channel") or []))
    score += 1.5 * min(n_engines, 3)
    # Hit-amplifier richness (Dec-DEF × Weaken compound) / detonator for DoTs.
    amp_types: set = set()
    for r in recs:
        amp_types |= sd.hit_amplifier_types(r)
    if ch in ("hit", "wm_gs", "bring_it_down"):
        score += 0.75 * len(amp_types)
    if any("dot_detonate" in r.get("provides", []) for r in recs):
        score += 0.5
    if roles_by_hero is not None:
        flat: set = set()
        for r in recs:
            flat |= roles_by_hero.get(r["name"], set())
        score += 0.05 * len(flat)
    return score


# ================================================================ CSP search
@dataclass
class _Partial:
    names: list                     # assigned hero names (slot order)
    recs: list                      # parallel records
    used: set


def _bucket(recs: list, slot: SlotConstraint) -> list:
    return [r for r in recs if slot_accepts(slot, r)]


def _flex_cat(rec: dict) -> str:
    """Coarse category of a flex filler, so the search keeps DIVERSE flex
    variants of a strong core (a poison/detonate flex like a Poison engine is
    retained alongside a hit-engine flex — cb_sim then decides which is best)."""
    ec = set(rec.get("engine_channel") or [])
    prov = set(rec.get("provides", []))
    if "poison" in ec:
        return "poison"
    if "hp_burn" in ec:
        return "hp_burn"
    if rec.get("amplifier_channel") in ("hit", "poison"):
        return "amp"
    if ec & {"hit", "wm_gs", "bring_it_down"}:
        return "hit"
    if "dot_detonate" in prov:
        return "detonate"
    if any(p in ("heal", "cleanse", "team_buff:Continuous Heal",
                 "team_buff:Shield") for p in prov):
        return "sustain"
    return "other"


def _core_key(team_names: list, flex_names: set) -> frozenset:
    """The 'core' of a comp = its non-flex members (survival/enabler/amp/engine).
    Used to group flex variants of the same archetype core for sim selection."""
    return frozenset(n for n in team_names if n not in flex_names)


def _slot_fit(rec: dict, slot: SlotConstraint, channel: str) -> float:
    """How well `rec` fills a SPECIFIC slot (used to cap each bucket to the
    strongest fillers per slot, so the target heroes — strongest at their
    role — survive the cap)."""
    nm = slot.name
    if nm == "survival":
        w = sd.survival_weight(rec)
        # A survival hero that also enables (e.g. block-damage + buff-extension)
        # is the premium keystone for a stall.
        if rec.get("enabler"):
            w += 0.3
        return w
    if nm == "enabler":
        f = 1.0
        if rec.get("survival_currency"):     # enabler that is ALSO a keystone
            f += sd.survival_weight(rec)
        return f
    if nm == "amplifier":
        return sum(sd.HIT_AMPLIFIER_WEIGHTS.get(t, 0.0)
                   for t in sd.hit_amplifier_types(rec)) + 0.1
    if nm == "engine":
        # A multi-channel engine (e.g. hp_burn + bring_it_down + hit) brings
        # more damage avenues; reward total engine breadth, not just the bound
        # channel, plus self-amp / detonation utility.
        breadth = len(rec.get("engine_channel") or [])
        amp = 0.3 if rec.get("amplifier_channel") in ("hit", "poison") else 0.0
        deto = 0.3 if "dot_detonate" in rec.get("provides", []) else 0.0
        ndeb = sum(1 for p in rec.get("provides", [])
                   if p.startswith("enemy_debuff:"))
        return breadth + amp + deto + 0.1 * ndeb
    return 0.0


def search_skeleton(skeleton: Skeleton, roster_recs: list, opts: GenOpts,
                    location: str, faction_lock: bool,
                    roles_by_hero: dict) -> tuple:
    """CSP search: MRV ordering + STRATIFIED beam + incremental prune.

    The two most-constrained REQUIRED slots (e.g. amplifier + engine for the
    hit channel) form an *anchor*; we enumerate every anchor (cartesian over
    those buckets) and beam-fill the remaining slots PER anchor, keeping the
    top `per_anchor` completions by the channel-aware structural pre-score.
    This stratification (the same idea as cb_team_explorer's round-robin
    diversity) guarantees every anchor retains its strongest completion, so a
    plain global beam can't starve a canonical comp out of the results.

    Returns (teams, gap_report). `teams` is a list of sorted name-lists.
    """
    # Bucket every slot, capped to the strongest fillers PER SLOT (slot-aware:
    # the survival slot keeps the heaviest keystones, the amplifier slot the
    # richest amps, etc.). This bounds the core space so cb_sim can rank it,
    # while keeping the best heroes (which are the ones meta comps use).
    cap = opts.pool_cap if opts.pool == "all" else opts.bucket_cap
    buckets = {}
    for slot in skeleton.slots:
        b = _bucket(roster_recs, slot)
        b.sort(key=lambda r: (-_slot_fit(r, slot, skeleton.channel),
                             -_prescore([r["name"]], roles_by_hero), r["name"]))
        # Cap the CONSTRAINED slots (survival/enabler/amp/engine) to bound the
        # core space; leave the flex slot wide (its diversity is wanted, and the
        # cb_sim refine pass sims every flex variant of the strong cores).
        if cap and not slot.name.startswith("flex"):
            b = b[:cap]
        buckets[slot.name] = b

    gap = []
    for slot in skeleton.slots:
        if not slot.optional and not buckets[slot.name]:
            gap.append({"skeleton": skeleton.name, "slot": slot.name,
                        "predicate": slot.require_any,
                        "reason": "no roster hero fills this required slot"})
    if gap:
        return [], gap

    # MRV order; required before optional.
    ordered = sorted(skeleton.slots, key=lambda s: (s.optional,
                                                    len(buckets[s.name])))
    required = [s for s in ordered if not s.optional]
    optional = [s for s in ordered if s.optional]
    # Anchor = the CHANNEL-DEFINING slots (engine + amplifier), enumerated
    # fully so every amplifier×engine pairing is tried; fall back to the most-
    # constrained remaining required slot if amplifier is optional (hp_burn).
    anchor_slots = [s for s in required if s.name in ("amplifier", "engine")]
    for s in required:
        if len(anchor_slots) >= 2:
            break
        if s not in anchor_slots:
            anchor_slots.append(s)
    anchor_slots = anchor_slots[:2]
    # Non-flex fill slots build the CORE (survival/enabler/extra required);
    # flex slots are filled afterward, one comp per flex CATEGORY per core.
    anchor_set = {s.name for s in anchor_slots}
    core_slots = [s for s in required if s.name not in anchor_set] + \
                 [s for s in optional if not s.name.startswith("flex")]
    flex_slots = [s for s in optional if s.name.startswith("flex")]
    core_keep = max(opts.cores_per_anchor * 4, 8)

    completion_pool = sorted(
        roster_recs, key=lambda r: -_prescore([r["name"]], roles_by_hero))
    anchor_buckets = [buckets[s.name] for s in anchor_slots]

    def _struct(recs):
        return (skeleton_prescore(recs, skeleton, roles_by_hero),
                _prescore([x["name"] for x in recs], roles_by_hero))

    teams, seen = [], set()
    for combo in product(*anchor_buckets):
        names0 = [r["name"] for r in combo]
        if len(set(names0)) != len(names0):
            continue
        if faction_lock:
            fr = {r.get("fraction") for r in combo if r.get("fraction")}
            if len(fr) > 1:
                continue

        # ---- Phase A: beam-fill the CORE slots (survival/enabler). -------- #
        core_beam = [list(combo)]
        for slot in core_slots:
            cands = buckets[slot.name]
            nb: list = []
            for recs in core_beam:
                used = {r["name"] for r in recs}
                cand = [r for r in cands if r["name"] not in used
                        and can_add(recs, r, location, faction_lock)]
                if not cand:
                    if slot.optional:
                        nb.append(recs)
                    continue
                for r in cand:
                    nb.append(recs + [r])
            nb.sort(key=lambda recs: (-_struct(recs)[0], -_struct(recs)[1]))
            core_beam = nb[:core_keep]
        core_beam = core_beam[:opts.cores_per_anchor]

        # ---- Phase B: per core, emit one comp per FLEX category. ---------- #
        for core_recs in core_beam:
            if not flex_slots:                   # core already == size
                comps = [list(core_recs)]
            else:
                fslot = flex_slots[0]
                used = {r["name"] for r in core_recs}
                fcands = [r for r in buckets[fslot.name]
                          if r["name"] not in used
                          and can_add(core_recs, r, location, faction_lock)]
                best_by_cat: dict = {}
                for r in fcands:
                    cat = _flex_cat(r)
                    cur = best_by_cat.get(cat)
                    if cur is None or _struct(core_recs + [r]) > _struct(cur):
                        best_by_cat[cat] = core_recs + [r]
                comps = list(best_by_cat.values()) or [list(core_recs)]

            for recs0 in comps:
                recs = list(recs0)
                names = [r["name"] for r in recs]
                used = set(names)
                core_names = {r["name"] for r in core_recs}
                if len(names) < opts.size:       # pad (rare; empty flex bucket)
                    for r in completion_pool:
                        if len(names) >= opts.size:
                            break
                        if r["name"] in used or not can_add(recs, r, location,
                                                            faction_lock):
                            continue
                        recs.append(r); names.append(r["name"])
                        used.add(r["name"])
                if len(names) != opts.size:
                    continue
                key = frozenset(names)
                if key in seen:
                    continue
                seen.add(key)
                flex_names = set(names) - core_names
                teams.append((sorted(names),
                              sorted(_core_key(names, flex_names))))
                if len(teams) >= opts.max_candidates:
                    return teams, gap
    return teams, gap


# ============================================================ hard-edge drop
def _value_edge_present(resolve_result, channel: str) -> bool:
    """Whether the comp carries a SATISFIED channel-consistent amplifier->engine
    edge (M2). hit-class engines look for a Dec-DEF/Weaken (ch="hit") edge;
    poison for a poison_synergy edge; hp_burn has no amplifier channel.

    This is now a PREFERENCE signal (see _channel_consistent / skeleton_prescore)
    rather than a hard gate — an amp-less stall has no such edge yet is still
    feasible. The channel CHECK stays channel-correct so a poison engine never
    treats a hit (def_break) edge as its multiplier.
    """
    sat = resolve_result.satisfied
    if channel in ("hit", "wm_gs", "bring_it_down"):
        return any(e.tag == "def_break" and e.channel == "hit" for e in sat)
    if channel == "poison":
        return any(e.tag == "poison_synergy" for e in sat)
    return False             # hp_burn (and anything else): no amplifier channel


def _hard_edges_ok(resolve_result, recs: list, channel: str) -> tuple:
    """Drop comps with unmet HARD edges (spec step 6). Returns (ok, reason).

    The HARD edges are: a survival currency, every keystone's enabler satisfied,
    and a channel-consistent damage ENGINE. The channel-correct AMPLIFIER is NO
    longer a hard edge (task #45) — amp-less stalls accrue damage passively, so
    the amplifier is a scored preference (skeleton_prescore), not a gate.
    """
    if not any(r.get("survival_currency") for r in recs):
        return False, "no survival currency"
    for k in resolve_result.keystones:
        if k.get("needs_enabler") and not k.get("enabler_ok"):
            return False, f"broken keystone-enabler ({k['keystone']})"
    if not _channel_consistent(recs, channel):
        return False, f"no channel-consistent {channel} engine"
    return True, "ok"


# ================================================================ novelty
_dwj_sigs_cache: Optional[set] = None


def _dwj_sigs() -> set:
    """frozenset signatures of scraped DWJ tunes (literal-hero slots only),
    via cb_team_explorer.load_dwj_tunes — the novelty cross-reference."""
    global _dwj_sigs_cache
    if _dwj_sigs_cache is None:
        sigs = set()
        for t in cb_team_explorer.load_dwj_tunes():
            slots = [s for s in t.get("slots", []) if isinstance(s, str)]
            if 4 <= len(slots) <= 6:
                sigs.add(frozenset(slots))
        _dwj_sigs_cache = sigs
    return _dwj_sigs_cache


def _is_novel(team: list) -> bool:
    base = frozenset(_base_name(n) for n in team)
    for sig in _dwj_sigs():
        if len(base & sig) >= max(4, len(sig) - 1):
            return False             # matches (≈) a known template
    return True


# ============================================================ fitness ranking
def _is_cb(location: str) -> bool:
    key = str(location).strip().lower().replace("-", "_").replace(" ", "_")
    return key in _CB_LOCATIONS


def _resolved_rank_with(rank_with: str, location: str) -> str:
    if rank_with != "auto":
        return rank_with
    return "cb_sim" if _is_cb(location) else "heuristic"


def _fitness_context(opts: GenOpts, sim: bool) -> dict:
    ctx = {"cb_element": opts.cb_element,
           "use_current_gear": opts.use_current_gear}
    if sim:
        ctx["sim"] = True
    return ctx


def _sim_value(team: list, opts: GenOpts, location: str,
               use_current_gear: bool):
    """One cb_sim call; returns (fitness, breakdown) or (0.0, {error})."""
    ctx = {"cb_element": opts.cb_element, "sim": True,
           "use_current_gear": use_current_gear}
    s = fitness_score(team, location, ctx)
    bd = s.get("breakdown", {})
    if bd.get("error") or s["fitness"] <= 0:
        return 0.0, bd
    return float(s["fitness"]), bd


def _cb_rank(scored: list, survivors: list, roster_recs: list,
             roles_by_hero: dict, opts: GenOpts, location: str,
             faction_lock: bool) -> tuple:
    """Two-phase cb_sim ranking (the bare M5/structural heuristics can't pin
    the gear-specific best comp, so cb_sim is the authoritative oracle):

      Phase 1 — group candidates by CORE (survival/enabler/amplifier/engine);
        sim the best representative of the top `sim_top` cores by structural
        pre-score with the FAST potential-gear sim, to find which cores survive
        and deal damage (cb_sim demotes the many structurally-strong cores that
        actually wipe).
      Phase 2 — take the top `refine_cores` cores by phase-1 sim; for each,
        enumerate EVERY flex completion from the roster, validate (M2 resolve +
        team rules) and sim with the requested gear (current gear by default —
        the user's real comp is best on their real gear). cb_sim then ranks the
        full simmed set; everything else stays heuristic.

    Returns (scored_rows, n_phase1_sims, n_phase2_sims).
    """
    pool_all = (opts.pool == "all")
    # Potential gear unless the caller asked for current gear (owned only).
    gear = (not pool_all) and opts.use_current_gear
    p1_gear = gear
    p2_gear = gear

    # ---- group rows by core; best-structural representative per core ------ #
    rep_by_core: dict = {}
    rows_by_core: dict = {}
    for row in scored:
        core = row[8]
        rows_by_core.setdefault(core, []).append(row)
        if core not in rep_by_core or row[7] > rep_by_core[core][7]:
            rep_by_core[core] = row
    cores_ranked = sorted(rep_by_core.values(), key=lambda r: -r[7])

    # ---- phase 1: sim the top cores' representatives ---------------------- #
    n1 = 0
    core_sim: dict = {}
    for row in cores_ranked[:opts.sim_top]:
        val, bd = _sim_value(row[0], opts, location, p1_gear)
        n1 += 1
        core_sim[row[8]] = val
        # annotate the representative row with its phase-1 sim value
        if val > 0:
            row[4], row[5], row[6] = val, "cb_sim", bd

    # ---- phase 2: refine flex of the best cores -------------------------- #
    n2 = 0
    refine = sorted(core_sim.items(), key=lambda kv: -kv[1])[:opts.refine_cores]
    rmode = "cb"
    rctx = ResolveContext(location=location, mode=rmode)
    rec_by_name = {r["name"]: r for r in roster_recs}
    extra_rows: list = []
    seen = {frozenset(r[0]) for r in scored}
    for core, _v in refine:
        rep = rep_by_core[core]
        sk = rep[1]
        core_names = list(core)
        used = set(core_names)
        # Flex candidates: roster heroes not in the core, ranked by pre-score
        # and capped (flex_cap) to bound the sim count. The full breadth of the
        # bucket is searched within that cap so the cb_sim-best flex surfaces.
        flex_cands = sorted(
            (r for r in roster_recs if r["name"] not in used),
            key=lambda r: -_prescore([r["name"]], roles_by_hero))[:opts.flex_cap]
        for r in flex_cands:
            if faction_lock:
                fr = {rec_by_name[n].get("fraction") for n in core_names}
                fr.discard(None)
                if r.get("fraction") and fr and fr != {r.get("fraction")}:
                    continue
            team = sorted(core_names + [r["name"]])
            key = frozenset(team)
            if key in seen:
                continue
            recs = [record_for(n) for n in team]
            recs = [x for x in recs if x is not None]
            rr = m2_resolve(team, rctx)
            ok, _ = _hard_edges_ok(rr, recs, sk.channel)
            if not ok:
                continue
            rules_ok, rule_rep = team_rules_report(recs, sk, location, True)
            if not rules_ok:
                continue
            seen.add(key)
            val, bd = _sim_value(team, opts, location, p2_gear)
            n2 += 1
            kind = "cb_sim" if val > 0 else "heuristic"
            h = (fitness_score(team, location, _fitness_context(opts, False))
                 if val <= 0 else {"fitness": val})
            extra_rows.append([team, sk, rr, rule_rep, h.get("fitness", val),
                               kind, bd, rep[7], core])

    # ---- re-sim the refine cores' representatives with phase-2 gear ------ #
    if p2_gear != p1_gear:
        for core, _v in refine:
            rep = rep_by_core[core]
            val, bd = _sim_value(rep[0], opts, location, p2_gear)
            n2 += 1
            if val > 0:
                rep[4], rep[5], rep[6] = val, "cb_sim", bd

    all_rows = scored + extra_rows
    # simmed comps (kind cb_sim) outrank heuristic ones; tie-break by value.
    all_rows.sort(key=lambda x: (0 if x[5] == "cb_sim" else 1, -x[4]))
    return all_rows, n1, n2


# ================================================================== generate
def generate(location: str, roster: list, opts: Optional[GenOpts] = None
             ) -> list:
    """Generate ranked CandidateComps for `location` from `roster` (names).

    See module docstring for the full pipeline. `roster` is a list of hero
    names; when None, the owned 6★ roster is loaded.
    """
    opts = opts or GenOpts()
    import random
    random.seed(opts.seed)

    if roster is None:
        roster = (load_owned_roster() if opts.pool == "owned"
                  else _all_catalog_names())
    elif opts.pool == "all" and roster == "all":
        roster = _all_catalog_names()

    is_cb = _is_cb(location)
    report: dict = {"location": location, "pool": opts.pool,
                    "roster_size": len(roster), "roster_gaps": [],
                    "dropped_heroes": [], "skeletons_run": [],
                    "skeletons_skipped": []}

    # ---- M3 per-hero hard filters --------------------------------------- #
    roster_recs, dropped = filter_roster(roster, location, opts.cb_element, is_cb)
    report["dropped_heroes"] = dropped

    # ---- engine channels present + skeletons ---------------------------- #
    channels_present = set()
    for r in roster_recs:
        channels_present |= set(r.get("engine_channel") or [])
    skeletons = opts.skeletons or build_named_skeletons(
        channels_present, size=opts.size)
    if not skeletons:
        report["error"] = ("no engine channel present in roster -> "
                           "nothing to generate")
        report["channels_present"] = sorted(channels_present)
        return _Result([], report)

    try:
        faction_lock = boss_constraints.faction_lock(location)
    except KeyError:
        faction_lock = False

    roles_by_hero = {r["name"]: _roles_from_rec(r) for r in roster_recs}

    # ---- per-skeleton CSP search ---------------------------------------- #
    raw_teams: list = []            # list[(team_names, skeleton, core)]
    seen_keys: set = set()
    for sk in skeletons:
        teams, gap = search_skeleton(sk, roster_recs, opts, location,
                                     faction_lock, roles_by_hero)
        if gap:
            report["roster_gaps"].extend(gap)
            report["skeletons_skipped"].append(sk.name)
            continue
        report["skeletons_run"].append(sk.name)
        for t, core in teams:
            key = frozenset(t)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            raw_teams.append((t, sk, frozenset(core)))
            if len(raw_teams) >= opts.max_candidates:
                break
        if len(raw_teams) >= opts.max_candidates:
            break

    # ---- M2 resolve + hard-edge drop ------------------------------------ #
    rmode = "cb" if is_cb else "generic"
    rctx = ResolveContext(location=location, mode=rmode)
    survivors: list = []            # (team, skeleton, resolve, rule_rep, core)
    for team, sk, core in raw_teams:
        recs = [record_for(n) for n in team]
        recs = [r for r in recs if r is not None]
        rr = m2_resolve(team, rctx)
        ok, reason = _hard_edges_ok(rr, recs, sk.channel)
        if not ok:
            continue
        # team rules (hard) re-checked on the assembled comp.
        rules_ok, rule_rep = team_rules_report(recs, sk, location, is_cb)
        if not rules_ok:
            continue
        survivors.append((team, sk, rr, rule_rep, core))

    # ---- rank by fitness ------------------------------------------------ #
    rank_with = _resolved_rank_with(opts.rank_with, location)
    # cheap heuristic + structural pre-score for everybody first.
    scored = []
    for team, sk, rr, rule_rep, core in survivors:
        recs = [r for r in (record_for(n) for n in team) if r is not None]
        h = fitness_score(team, location, _fitness_context(opts, sim=False))
        pre = skeleton_prescore(recs, sk, roles_by_hero)
        scored.append([team, sk, rr, rule_rep, h["fitness"], "heuristic",
                       h.get("breakdown", {}), pre, core])
    scored.sort(key=lambda x: -x[4])

    if rank_with == "cb_sim" and is_cb:
        scored, n_phase1, n_phase2 = _cb_rank(
            scored, survivors, roster_recs, roles_by_hero, opts, location,
            faction_lock)
        report["cb_sims_phase1"] = n_phase1
        report["cb_sims_phase2"] = n_phase2

    # ---- build CandidateComps ------------------------------------------ #
    out: list = []
    for team, sk, rr, rule_rep, fit, kind, bd, _pre, _core in scored[:opts.top]:
        rep = dict(rule_rep)
        rep["fitness_breakdown"] = bd
        out.append(CandidateComp(
            team=team, skeleton=sk.name, resolve=rr, fitness=fit,
            fitness_kind=kind, constraint_report=rep,
            novelty=_is_novel(team)))
    report["candidates_evaluated"] = len(survivors)
    report["candidates_returned"] = len(out)
    return _Result(out, report)


class _Result(list):
    """List of CandidateComp that also carries a `.report` diagnostics dict."""
    def __init__(self, items, report):
        super().__init__(items)
        self.report = report


# ===================================================================== CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("location", help="boss_constraints location key or alias")
    ap.add_argument("--pool", choices=["owned", "all"], default="owned")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--beam-width", type=int, default=200)
    ap.add_argument("--max-candidates", type=int, default=5000)
    ap.add_argument("--cb-element", default="void",
                    choices=["magic", "force", "spirit", "void"])
    ap.add_argument("--use-current-gear", action="store_true")
    ap.add_argument("--rank-with", choices=["auto", "cb_sim", "heuristic"],
                    default="auto")
    ap.add_argument("--sim-top", type=int, default=12)
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)

    elem = {"magic": 1, "force": 2, "spirit": 3, "void": 4}[args.cb_element]
    opts = GenOpts(pool=args.pool, top=args.top, beam_width=args.beam_width,
                   max_candidates=args.max_candidates, cb_element=elem,
                   use_current_gear=args.use_current_gear,
                   rank_with=args.rank_with, sim_top=args.sim_top)
    roster = None
    res = generate(args.location, roster, opts)

    if args.json:
        print(json.dumps({"report": res.report,
                          "candidates": [c.as_dict() for c in res]},
                         ensure_ascii=False, indent=2))
        return 0

    rep = res.report
    print(f"=== team_generator: {args.location} (pool={args.pool}) ===")
    print(f"roster={rep['roster_size']}  dropped={len(rep['dropped_heroes'])}  "
          f"skeletons_run={rep['skeletons_run']}  "
          f"skipped={rep['skeletons_skipped']}")
    if rep.get("error"):
        print("ERROR:", rep["error"])
        return 1
    print(f"candidates: {rep['candidates_returned']} returned "
          f"(of {rep['candidates_evaluated']} role-valid)\n")
    print(f"{'#':>3} {'fitness':>12} {'kind':>9} {'novel':>6}  skeleton / team")
    print("-" * 100)
    for i, c in enumerate(res, 1):
        fv = (f"{c.fitness/1e6:.2f}M" if c.fitness_kind == "cb_sim"
              else f"{c.fitness:.2f}")
        print(f"{i:>3} {fv:>12} {c.fitness_kind:>9} "
              f"{'yes' if c.novelty else 'no':>6}  {c.skeleton}  "
              f"{', '.join(c.team)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
