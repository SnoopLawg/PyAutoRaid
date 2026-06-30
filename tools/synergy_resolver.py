"""Milestone 2 — Provider->consumer dependency + ordering resolver.

The reasoning layer that did not exist before: given a comp (list of hero
names), build the channel-aware provider->consumer synergy graph and verify
each edge's *ordering* (provider acts earlier than its consumer, with buff/
debuff duration covering the consumer's turn).

This sits on top of:
  - M1 enriched substrate `data/m5_synergy.jsonl` (per-hero `provides[]`,
    `needs[]`, `amplifier_channel`, `engine_channel[]`, `survival_currency`,
    `enabler`, `keystone_needs_enabler`).  `engine_channel` is a LIST.
  - M3 boss filters `tools/boss_constraints.py`
    (`get_constraints`/`is_effect_useful`/`acc_floor`/`faction_lock`).

Ordering reuse (DO NOT re-derive — locked game-truth):
  - CB mode reuses the LOCKED PICK-MAX-ONE + ZERO-RESET scheduler in
    `tools/cb_scheduler.py` (`Actor`, `SkillConfig`, `pick_next_actor`,
    `effective_speed`) which itself drives `tools/turn_meter.TurnMeterEngine`.
    Boss SPD is 190 (memory project_cb_speed_compensating_wrong). We build
    a lightweight actor set + boss proxy and read the act order off one boss
    cycle — we do NOT re-implement the TM math.
  - Generic mode: SPD-rank + duration-vs-cooldown model.

Channel rule (game-truth, organic_team_milestones.md:32-36):
  Dec-DEF / Weaken (amplifier_channel=="hit") amplify hit / wm_gs /
  bring_it_down engines ONLY -- NOT DoTs.  Poison Sensitivity
  (amplifier_channel=="poison") amplifies the poison engine ONLY.  HP Burn is
  amplified by neither (`dot_detonate` only).  So a poison engine carrying
  `needs:def_break` (m5_synergy_graph adds def_break to all attackers) must
  NEVER be credited a Weaken/Dec-DEF edge -> it lands in `notes`, not
  `satisfied`/`broken`.  This "won't credit Weaken->poison" is THE acceptance.

API:
    resolve(comp: list[str], context: ResolveContext|None) -> ResolveResult
    resolve_records(records, context) -> ResolveResult   # pre-built records
    build_ordering_context(records, ctx) -> OrderingContext

CLI:
    python tools/synergy_resolver.py Maneater Demytha Ninja Geomancer Venomage
    python tools/synergy_resolver.py --location clan_boss <heroes...>
    python tools/synergy_resolver.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
SYNERGY = ROOT / "data" / "m5_synergy.jsonl"

# ---------------------------------------------------------------- M1 defaults
# Records predating M1 may lack these fields; accessor warns once and defaults.
_M1_DEFAULTS = {
    "amplifier_channel": "none",
    "engine_channel": [],
    "survival_currency": None,
    "enabler": None,
    "keystone_needs_enabler": False,
    "provides": [],
    "needs": [],
}
_warned: set[str] = set()


def _get(rec: dict, key: str, default=None):
    """Safe M1-field accessor: warn once if a record is missing the field."""
    if key in rec and rec[key] is not None:
        return rec[key]
    if key in _M1_DEFAULTS:
        if key not in rec:
            tag = f"{rec.get('name','?')}::{key}"
            if key not in _warned:
                print(f"[synergy_resolver] WARN: record(s) missing M1 field "
                      f"{key!r}; defaulting to {_M1_DEFAULTS[key]!r} "
                      f"(first seen on {rec.get('name','?')})", file=sys.stderr)
                _warned.add(key)
        return rec.get(key) if rec.get(key) is not None else (
            default if default is not None else _M1_DEFAULTS[key])
    return rec.get(key, default)


def _engine_set(rec: dict) -> set[str]:
    ec = _get(rec, "engine_channel", [])
    if isinstance(ec, str):
        ec = [ec] if ec and ec != "none" else []
    return {c for c in (ec or []) if c and c != "none"}


def _amp(rec: dict) -> str:
    return _get(rec, "amplifier_channel", "none") or "none"


def _provides(rec: dict) -> list[str]:
    return _get(rec, "provides", []) or []


def _needs(rec: dict) -> list[str]:
    return _get(rec, "needs", []) or []


def _survival(rec: dict):
    s = _get(rec, "survival_currency", None)
    return s if s and s != "none" else None


def _enabler(rec: dict):
    e = _get(rec, "enabler", None)
    return e if e and e != "none" else None


# ----------------------------------------------------- keystone enabler compat
# Which enabler kinds can sustain which survival keystone.  Revive / ally-protect
# are instantaneous on-trigger effects -> nothing to *extend*, only cooldown
# reduction helps re-arm them.  Buff-based keystones (unkillable/block/shield/
# lifesteal heal) accept either cooldown reduction OR buff extension.
KEYSTONE_ENABLER_COMPAT: dict[str, set[str]] = {
    "unkillable": {"cooldown_reduction", "buff_extension"},
    "block_damage": {"cooldown_reduction", "buff_extension"},
    "shield": {"cooldown_reduction", "buff_extension"},
    "heal_lifesteal": {"cooldown_reduction", "buff_extension"},
    "revive_on_death": {"cooldown_reduction"},
    "ally_protect": {"cooldown_reduction"},
}

# Defaults for the ordering model when per-hero data is unavailable.
DEFAULT_SPD = 150
BOSS_SPD = 190           # game-truth CB boss SPD (do NOT re-derive)
DEFAULT_DURATION = 2     # buff/debuff "for N turns" fallback
DEFAULT_COOLDOWN = 1     # consumer skill cooldown fallback

# A consumer need -> the boss-immunity tag M3 stores in `cc_immunities`. Only
# control/TM needs map; everything else is its own tag (and useful by default).
NEED_TO_BOSS_TAG = {"tm_control": "turn_meter"}

# Needs served by a *recurring* re-applier (fires every turn the provider acts)
# rather than a one-shot timed debuff -> ordering is "untimed_refresh", never a
# late-provider/short-duration break (cd-0 re-appliers, spec generic mode).
UNTIMED_NEEDS = {"tm_control", "buff_extension"}


# =========================================================== data structures
@dataclass
class SynergyEdge:
    provider: str
    consumer: str
    tag: str                 # the consumer need being served (e.g. "def_break")
    via: str                 # the provider effect that serves it
    channel: str             # the channel gate that applied ("hit"/"poison"/"-")
    ordering_ok: bool
    ordering_reason: str

    def __str__(self) -> str:
        arrow = "->" if self.provider != self.consumer else "(self)"
        return (f"{self.provider} {arrow} {self.consumer} [{self.tag} via "
                f"{self.via}, ch={self.channel}] "
                f"{'OK' if self.ordering_ok else 'BROKEN'}:{self.ordering_reason}")


@dataclass
class ResolveResult:
    satisfied: list[SynergyEdge] = field(default_factory=list)
    broken: list[SynergyEdge] = field(default_factory=list)
    unmet: list[dict] = field(default_factory=list)        # {consumer,tag,reason}
    order: list[str] = field(default_factory=list)         # act order (cycle)
    keystones: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def satisfied_edges(self, tag: str | None = None,
                        consumer: str | None = None) -> list[SynergyEdge]:
        out = self.satisfied
        if tag is not None:
            out = [e for e in out if e.tag == tag]
        if consumer is not None:
            out = [e for e in out if e.consumer == consumer]
        return out

    def keystone_for(self, name: str) -> dict | None:
        for k in self.keystones:
            if k["keystone"] == name:
                return k
        return None


@dataclass
class OrderingContext:
    """Act-order + duration/cooldown model used by `verify_ordering`.

    `order_index[name]` = position of the hero's first action in one boss
    cycle (lower acts earlier).  Built from the locked CB scheduler in CB mode
    or from SPD rank in generic mode.  `speeds`/`durations`/`cooldowns` may be
    supplied by the caller (tests, gear-aware callers) to override the defaults.
    """
    mode: str                       # "cb" | "generic"
    order_index: dict[str, int] = field(default_factory=dict)
    speeds: dict[str, float] = field(default_factory=dict)
    durations: dict[str, int] = field(default_factory=dict)   # by provider name
    cooldowns: dict[str, int] = field(default_factory=dict)   # by consumer name
    lenient: bool = True

    def duration(self, provider: str) -> int:
        return int(self.durations.get(provider, DEFAULT_DURATION))

    def cooldown(self, consumer: str) -> int:
        return int(self.cooldowns.get(consumer, DEFAULT_COOLDOWN))


@dataclass
class ResolveContext:
    location: str = "clan_boss"
    mode: Optional[str] = None      # auto: "cb" for clan_boss, else "generic"
    speeds: dict[str, float] = field(default_factory=dict)
    durations: dict[str, int] = field(default_factory=dict)
    cooldowns: dict[str, int] = field(default_factory=dict)
    boss_speed: int = BOSS_SPD
    lenient_ordering: bool = True
    # optional injected catalog override {name: record} for tests / pool=all
    catalog: Optional[dict] = None
    # optional cb_sim trace hook (full ordering) -> dict {name: order_index}
    cb_sim_hook: Optional[Callable[[list], dict]] = None

    def resolved_mode(self) -> str:
        if self.mode:
            return self.mode
        loc = (self.location or "").lower()
        if loc in ("clan_boss", "cb", "demon_lord", "clanboss",
                   "demon_lord_unm", "demon_lord_nm"):
            return "cb"
        # Ask M3 for the canonical key; CB aliases -> cb.
        try:
            rec = boss_get_constraints(self.location)
            disp = (rec.get("display_name", "") or "").lower()
            if "clan boss" in disp or "demon lord" in disp:
                return "cb"
        except Exception:
            pass
        return "generic"


# ------------------------------------------------------------- M3 thin imports
def boss_get_constraints(location: str) -> dict:
    from boss_constraints import get_constraints
    return get_constraints(location)


def _effect_useful(location: str, tag: str) -> bool:
    try:
        from boss_constraints import is_effect_useful
        return is_effect_useful(location, tag)
    except Exception:
        return True


def _slot_caps(location: str) -> dict:
    try:
        rec = boss_get_constraints(location)
        from boss_constraints import _field_value  # type: ignore
        caps = _field_value(rec, "slot_caps")
        return caps or {}
    except Exception:
        return {}


# ------------------------------------------------------------------- catalog
_catalog_cache: dict | None = None


def load_catalog() -> dict:
    """name -> enriched record from data/m5_synergy.jsonl (cached)."""
    global _catalog_cache
    if _catalog_cache is None:
        cat: dict[str, dict] = {}
        with SYNERGY.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                cat[rec["name"]] = rec
        _catalog_cache = cat
    return _catalog_cache


def _base_name(name: str) -> str:
    """Strip the duplicate-hero suffix convention (e.g. 'Maneater_2')."""
    if "_" in name:
        head, tail = name.rsplit("_", 1)
        if tail.isdigit():
            return head
    return name


def load_records(names: list[str], catalog: dict | None = None) -> list[dict]:
    """Resolve hero names -> records.  Honors the 'Name_2' duplicate convention
    and an injected catalog override.  Unknown names get a minimal stub."""
    cat = catalog or load_catalog()
    out = []
    for nm in names:
        base = _base_name(nm)
        rec = cat.get(nm) or cat.get(base)
        if rec is None:
            print(f"[synergy_resolver] WARN: unknown hero {nm!r}; "
                  f"using empty stub", file=sys.stderr)
            rec = {"name": base, **{k: (v.copy() if isinstance(v, list) else v)
                                    for k, v in _M1_DEFAULTS.items()}}
        else:
            rec = dict(rec)
        # Preserve the caller's display name (keeps Name_2 unique in output).
        rec = dict(rec)
        rec["name"] = nm
        out.append(rec)
    return out


# ============================================================ ordering model
def _cb_act_order(records: list[dict], speeds: dict[str, float],
                  boss_speed: int) -> dict[str, int]:
    """Reuse the LOCKED CB scheduler (cb_scheduler.pick_next_actor ->
    turn_meter.TurnMeterEngine, PICK-MAX-ONE + ZERO-RESET) to read the team's
    act order across one boss cycle.  We do NOT re-derive the TM math.

    Returns {hero_name: index_of_first_action}.  Boss excluded from the map.
    """
    try:
        from cb_scheduler import Actor, SkillConfig, pick_next_actor
    except Exception:
        return _spd_rank_order(records, speeds)

    actors: list[Actor] = []
    for rec in records:
        spd = float(speeds.get(rec["name"], DEFAULT_SPD))
        actors.append(Actor(
            name=rec["name"], is_boss=False,
            total_speed=spd, base_speed=spd, speed_bonus=0,
            has_lore_of_steel=False,
            skill_configs=[SkillConfig(alias="A1", id="1", priority=1,
                                       delay=0, cooldown=0)],
        ))
    boss = Actor(name="__boss__", is_boss=True,
                 total_speed=float(boss_speed), base_speed=float(boss_speed),
                 speed_bonus=0, has_lore_of_steel=False,
                 skill_configs=[SkillConfig(alias="A1", id="1", priority=1,
                                            delay=0, cooldown=0)])
    pool = actors + [boss]

    order: dict[str, int] = {}
    idx = 0
    boss_turns = 0
    # Run until every hero has acted once or the boss has cycled twice.
    for _ in range(200):
        act = pick_next_actor(pool, aura=0.0)
        act.turn_meter = 0.0          # ZERO-RESET (locked)
        if act.is_boss:
            boss_turns += 1
            if boss_turns >= 2:
                break
            continue
        if act.name not in order:
            order[act.name] = idx
            idx += 1
        if len(order) >= len(actors):
            break
    # Any hero that never acted (shouldn't happen) sorts last.
    for rec in records:
        order.setdefault(rec["name"], idx)
        idx += 1
    return order


def _spd_rank_order(records: list[dict], speeds: dict[str, float]) -> dict[str, int]:
    """Generic mode: rank by SPD desc, ties broken by input order."""
    ranked = sorted(
        enumerate(records),
        key=lambda t: (-float(speeds.get(t[1]["name"], DEFAULT_SPD)), t[0]))
    return {rec["name"]: i for i, (_, rec) in enumerate(ranked)}


def build_ordering_context(records: list[dict],
                           ctx: ResolveContext) -> OrderingContext:
    mode = ctx.resolved_mode()
    speeds = dict(ctx.speeds)
    if mode == "cb" and ctx.cb_sim_hook is not None:
        try:
            order = ctx.cb_sim_hook(records)
        except Exception as e:
            print(f"[synergy_resolver] cb_sim_hook failed ({e}); "
                  f"falling back to scheduler", file=sys.stderr)
            order = _cb_act_order(records, speeds, ctx.boss_speed)
    elif mode == "cb":
        order = _cb_act_order(records, speeds, ctx.boss_speed)
    else:
        order = _spd_rank_order(records, speeds)
    return OrderingContext(
        mode=mode, order_index=order, speeds=speeds,
        durations=dict(ctx.durations), cooldowns=dict(ctx.cooldowns),
        lenient=ctx.lenient_ordering)


def verify_ordering(provider: dict, consumer: dict, tag: str,
                    octx: OrderingContext, *, untimed: bool = False
                    ) -> tuple[bool, str]:
    """Edge ordering check.

    - self-amplifier (provider is consumer) -> ok, reason "self".
    - untimed re-appliers (cooldown_reduction enablers, cd-0 refreshers) ->
      ok, reason "untimed_refresh".
    - otherwise: ok iff provider acts earlier in the cycle AND the buff/debuff
      duration covers the consumer's turn (duration >= max(1, cooldown)).
    - missing data -> lenient pass (CLAUDE.md "tolerate missing fields").
    """
    pname, cname = provider["name"], consumer["name"]
    if pname == cname:
        return True, "self"
    if untimed:
        return True, "untimed_refresh"

    pi = octx.order_index.get(pname)
    ci = octx.order_index.get(cname)
    reason_base = "cb_schedule" if octx.mode == "cb" else "spd_rank+duration"
    if pi is None or ci is None:
        if octx.lenient:
            return True, f"{reason_base}:assumed"
        return False, f"{reason_base}:no_order_data"

    rank_ok = pi < ci
    dur = octx.duration(pname)
    cd = octx.cooldown(cname)
    dur_ok = dur >= max(1, cd)

    if rank_ok and dur_ok:
        return True, reason_base
    if not rank_ok and not dur_ok:
        return False, f"{reason_base}:late_provider+short_duration"
    if not rank_ok:
        return False, f"{reason_base}:late_provider"
    return False, f"{reason_base}:short_duration(dur={dur}<cd={cd})"


# ============================================================ channel routing
# Effect-family membership (channel-agnostic) for "raw provider exists" checks.
def _provides_def_break(rec: dict) -> bool:
    pv = _provides(rec)
    return any(p in ("enemy_debuff:Decrease DEF", "enemy_debuff:Weaken")
               for p in pv)


def _provides_poison_enable(rec: dict) -> bool:
    pv = _provides(rec)
    return ("enables:poison" in pv) or ("dot_detonate" in pv)


def _provides_detonate(rec: dict) -> bool:
    return "dot_detonate" in _provides(rec)


def _provides_tm_control(rec: dict) -> bool:
    return "tm_control" in _provides(rec)


def _provides_buff_extension(rec: dict) -> bool:
    return _enabler(rec) == "buff_extension" or "buff_extension" in _provides(rec)


def _via_def_break(rec: dict) -> str:
    pv = _provides(rec)
    if "enemy_debuff:Decrease DEF" in pv:
        return "enemy_debuff:Decrease DEF"
    return "enemy_debuff:Weaken"


def _via_poison(rec: dict) -> str:
    return "enables:poison" if "enables:poison" in _provides(rec) else "dot_detonate"


# Per-need routing spec: (raw_provider_pred, channel_gate, via_fn, channel_label)
# channel_gate(provider, consumer) -> bool
def _routing():
    return {
        "def_break": (
            _provides_def_break,
            lambda p, c: _amp(p) == "hit"
            and bool(_engine_set(c) & {"hit", "wm_gs", "bring_it_down"}),
            _via_def_break, "hit"),
        "poison_synergy": (
            _provides_poison_enable,
            lambda p, c: _amp(p) == "poison" and ("poison" in _engine_set(c)),
            _via_poison, "poison"),
        "burn_synergy": (
            _provides_detonate,
            lambda p, c: ("hp_burn" in _engine_set(c)),
            lambda p: "dot_detonate", "none"),
        "tm_control": (
            _provides_tm_control,
            lambda p, c: True,
            lambda p: "tm_control", "-"),
        "survival_support": (
            lambda r: _survival(r) is not None,
            lambda p, c: True,
            lambda p: f"survival:{_survival(p)}", "-"),
        "buff_extension": (
            _provides_buff_extension,
            lambda p, c: _survival(c) is not None,
            lambda p: "enabler:buff_extension", "-"),
    }


# ================================================================== resolve
def resolve(comp: list[str], context: ResolveContext | None = None
            ) -> ResolveResult:
    """Resolve a comp given by hero names against a context (default: CB)."""
    context = context or ResolveContext()
    records = load_records(comp, context.catalog)
    return resolve_records(records, context)


def resolve_records(records: list[dict],
                    context: ResolveContext | None = None) -> ResolveResult:
    """Resolve a comp given as pre-built enriched records.  Used by tests to
    inject synthetic heroes (e.g. a pure-poison engine carrying def_break)."""
    context = context or ResolveContext()
    res = ResolveResult()
    octx = build_ordering_context(records, context)
    mode = octx.mode
    loc = context.location
    routing = _routing()

    # Act order (informational).
    res.order = sorted((r["name"] for r in records),
                       key=lambda n: octx.order_index.get(n, 1 << 30))

    # ---- per-consumer need resolution ----
    for consumer in records:
        cname = consumer["name"]
        for tag in _needs(consumer):
            # 1) boss no-op (CB TM/CC immunities) -> note, never satisfied.
            boss_tag = NEED_TO_BOSS_TAG.get(tag, tag)
            if mode == "cb" and not _effect_useful(loc, boss_tag):
                res.notes.append(
                    f"{cname}: need {tag!r} is a no-op vs the {loc} boss "
                    f"(CC/TM immunity) -> ignored")
                continue

            spec = routing.get(tag)
            if spec is None:
                # Unknown need vocab -> treat as unmet (visible, not silent).
                res.unmet.append({"consumer": cname, "tag": tag,
                                  "reason": "no routing rule"})
                continue
            raw_pred, gate, via_fn, ch_label = spec

            raw_providers = [p for p in records if raw_pred(p)]
            # channel-valid candidates (self allowed)
            valid = [p for p in raw_providers if gate(p, consumer)]

            if not raw_providers:
                res.unmet.append({"consumer": cname, "tag": tag,
                                  "reason": "no provider in comp"})
                continue

            if not valid:
                # Providers exist but channel mismatched -> category mismatch.
                # THE "won't credit Weaken->poison" path.
                provs = ", ".join(sorted({p["name"] for p in raw_providers}))
                res.notes.append(
                    f"{cname}: {tag!r} NOT credited - channel mismatch "
                    f"(engine={sorted(_engine_set(consumer))}, "
                    f"available providers [{provs}] are wrong channel for "
                    f"this engine)")
                continue

            # Order valid candidates: prefer self, then earliest actor.
            def _pref(p):
                self_first = 0 if p["name"] == cname else 1
                return (self_first, octx.order_index.get(p["name"], 1 << 30))
            valid.sort(key=_pref)

            best = valid[0]
            untimed = (tag in UNTIMED_NEEDS)  # recurring re-appliers
            ok, reason = verify_ordering(best, consumer, tag, octx,
                                         untimed=untimed)
            edge = SynergyEdge(provider=best["name"], consumer=cname, tag=tag,
                               via=via_fn(best), channel=ch_label,
                               ordering_ok=ok, ordering_reason=reason)
            (res.satisfied if ok else res.broken).append(edge)

            # Surplus channel-valid providers -> redundant note (keep best edge).
            for extra in valid[1:]:
                res.notes.append(
                    f"redundant: {extra['name']} also serves {cname}'s {tag!r} "
                    f"(best edge kept from {best['name']})")

    # ---- keystone / enabler resolution ----
    _resolve_keystones(records, octx, res)

    # ---- engine slot-cap redundancy (e.g. 2nd HP burner) ----
    _flag_slot_cap_redundancy(records, loc, mode, res)

    return res


def _resolve_keystones(records: list[dict], octx: OrderingContext,
                       res: ResolveResult) -> None:
    for ks in records:
        cur = _survival(ks)
        if cur is None:
            continue
        needs_enabler = bool(_get(ks, "keystone_needs_enabler", False))
        entry = {"keystone": ks["name"], "currency": cur,
                 "needs_enabler": needs_enabler, "enabler_ok": True,
                 "enabler": None, "reason": "no enabler required"}
        if not needs_enabler:
            res.keystones.append(entry)
            continue

        compat = KEYSTONE_ENABLER_COMPAT.get(cur, set())
        entry["enabler_ok"] = False
        entry["reason"] = (f"no compatible enabler "
                           f"(needs one of {sorted(compat)})")
        # Candidate enablers: any hero (incl. self) whose enabler/provides match.
        for cand in records:
            kinds = set()
            ce = _enabler(cand)
            if ce:
                kinds.add(ce)
            if "cooldown_reduction" in _provides(cand):
                kinds.add("cooldown_reduction")
            if _provides_buff_extension(cand):
                kinds.add("buff_extension")
            usable = kinds & compat
            if not usable:
                continue
            # cooldown_reduction sustains untimed; buff_extension needs ordering.
            untimed = "cooldown_reduction" in usable
            ok, reason = verify_ordering(cand, ks, "enabler", octx,
                                         untimed=untimed)
            if ok:
                entry["enabler_ok"] = True
                entry["enabler"] = cand["name"]
                kind = "cooldown_reduction" if untimed else "buff_extension"
                entry["reason"] = (f"{cand['name']} provides {kind} "
                                   f"({reason})")
                break
        res.keystones.append(entry)


def _flag_slot_cap_redundancy(records: list[dict], loc: str, mode: str,
                              res: ResolveResult) -> None:
    caps = _slot_caps(loc) if mode == "cb" else {}
    # Engine channel -> slot-cap key in boss_constraints.slot_caps.
    cap_keys = {"hp_burn": "max_hp_burn", "poison": "max_poison_stacks"}
    for channel, cap_key in cap_keys.items():
        cap = caps.get(cap_key)
        if not isinstance(cap, int):
            continue
        contributors = [r["name"] for r in records if channel in _engine_set(r)]
        if len(contributors) > cap:
            for extra in contributors[cap:]:
                res.notes.append(
                    f"redundant: {extra} is engine#{contributors.index(extra)+1} "
                    f"for channel {channel!r} but slot cap is {cap} "
                    f"({cap_key}); surplus contributes no extra value")


# ===================================================================== CLI
def _format_result(res: ResolveResult) -> str:
    lines = []
    lines.append("ACT ORDER: " + " > ".join(res.order))
    lines.append(f"\nSATISFIED ({len(res.satisfied)}):")
    for e in res.satisfied:
        lines.append("  " + str(e))
    lines.append(f"\nBROKEN ({len(res.broken)}):")
    for e in res.broken:
        lines.append("  " + str(e))
    lines.append(f"\nUNMET ({len(res.unmet)}):")
    for u in res.unmet:
        lines.append(f"  {u['consumer']} needs {u['tag']} -- {u['reason']}")
    lines.append(f"\nKEYSTONES ({len(res.keystones)}):")
    for k in res.keystones:
        flag = "OK" if k["enabler_ok"] else "UNMET"
        lines.append(f"  {k['keystone']} [{k['currency']}] enabler={flag}"
                     f" :: {k['reason']}")
    lines.append(f"\nNOTES ({len(res.notes)}):")
    for n in res.notes:
        lines.append("  - " + n)
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("heroes", nargs="*", help="hero names in the comp")
    ap.add_argument("--location", default="clan_boss",
                    help="location/boss key (default clan_boss)")
    ap.add_argument("--mode", choices=["cb", "generic"], default=None)
    ap.add_argument("--self-test", action="store_true",
                    help="run a tiny smoke test")
    args = ap.parse_args(argv)

    if args.self_test:
        comp = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
        res = resolve(comp, ResolveContext(location="clan_boss"))
        print(_format_result(res))
        return 0

    if not args.heroes:
        ap.print_help()
        return 2

    res = resolve(args.heroes,
                  ResolveContext(location=args.location, mode=args.mode))
    print(_format_result(res))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
