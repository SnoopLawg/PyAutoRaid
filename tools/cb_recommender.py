"""CB Team Recommender — tried-and-true templates split by what you can run.

Phase 1: ownership + cheap gear-feasibility, no per-team sim (that's Phase 2).
Builds on `potential_teams.build(quick=True)` (DWJ tunes scored against the
owned roster — gives ownership, per-slot target speeds, capability tags) and
adds, per template:
  - tab: "ready" (own every hero) vs "need_heroes" (don't yet)
  - mechanic: the archetype chip (Unkillable / Speed / ...)
  - status traffic-light: ready / lacking-gear / need-heroes
  - gear gaps: per-hero SPD shortfall vs the tune, AS CURRENTLY GEARED — the
    cheap Tier-1 signal. Whether a *regear* could reach the tune (and the simmed
    damage once it does) is Phase 2 (gear solver + cb_sim).

Results are cached to data/cb_recommendations.json keyed by a roster/vault hash
so the dashboard reads instantly; pass force=True (or `build --force`) to rebuild.

CLI:
  python3 tools/cb_recommender.py build [--force]
  python3 tools/cb_recommender.py list [--tab ready|need]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

CACHE_NAME = "cb_recommendations.json"
_SPD_TOL = 2          # treat "within 2 SPD" of target as on-tune

# Demon Lord UNM reward chests by total damage (game-truth thresholds).
_CHESTS = [(70_280_000, "Transcendent"), (46_850_000, "Celestial"),
           (23_430_000, "Divine"), (17_570_000, "Mythical")]


def _chest(dmg: int) -> str | None:
    for floor, name in _CHESTS:
        if dmg >= floor:
            return name
    return None

# DWJ tune `type` -> friendly mechanic chip. The DWJ taxonomy is speed-tune
# centric (Unkillable chain vs Traditional); richer archetypes (Infinity Shield,
# Counterattack) come from a synergy-tag enrichment pass in a later phase.
_MECHANIC = {
    "Unkillable": "Unkillable",
    "Traditional": "Speed",
}


def _root(root: Path | None) -> Path:
    return root or Path(__file__).resolve().parent.parent


def _hero_spd_map(root: Path) -> dict:
    """name -> current Total SPD (base_computed + every column bonus), max over
    duplicate copies. The cheap readiness oracle for Phase 1."""
    out: dict = {}
    try:
        comp = {h["id"]: h for h in
                json.loads((root / "hero_computed_stats.json").read_text()).get("heroes", [])
                if isinstance(h, dict) and "id" in h}
        roster = json.loads((root / "heroes_all.json").read_text())
        roster = roster if isinstance(roster, list) else roster.get("heroes", [])
        for h in roster:
            nm, hid = h.get("name"), h.get("id")
            if not nm or hid not in comp:
                continue
            row = comp[hid]
            spd = sum(float(v.get("SPD", 0) or 0) for k, v in row.items()
                      if isinstance(v, dict) and (k.endswith("_bonus") or k == "base_computed"))
            out[nm] = max(out.get(nm, 0), int(round(spd)))
    except Exception:
        pass
    return out


def _feasibility(team: dict, spd_map: dict) -> tuple[bool, list]:
    """(feasible, gaps) by comparing each NAMED slot's current SPD to the tune
    target. Generic DPS slots and unowned/unknown heroes are skipped. Feasible
    when no named hero is short of its target speed (as currently geared)."""
    gaps = []
    for s in team.get("slots", []):
        hero, want = s.get("hero"), s.get("min_spd")
        if not hero or s.get("status") == "generic" or not want:
            continue
        have = spd_map.get(hero)
        if have is None:
            continue
        if have < want - _SPD_TOL:
            gaps.append({"hero": hero, "have": have, "want": int(want),
                         "short": int(want) - have})
    gaps.sort(key=lambda g: -g["short"])
    return (len(gaps) == 0), gaps


def _key_sort(cap: str | None) -> int:
    """Fewer keys = stronger team -> sorts first. '1 Key UNM' -> 1."""
    if not cap:
        return 9
    for tok in cap.split():
        if tok.isdigit():
            return int(tok)
    return 9


def _roster_hash(root: Path) -> str:
    h = hashlib.sha1()
    for f in ("heroes_all.json", "all_artifacts.json", "hero_computed_stats.json"):
        p = root / f
        try:
            h.update(f.encode())
            h.update(str(p.stat().st_mtime_ns).encode())
        except OSError:
            h.update(b"-")
    return h.hexdigest()[:16]


def _team_names(rec: dict, last_team: list, default_dps: str) -> list | None:
    """The 5 hero names for a template, filling generic DPS slots from the user's
    last CB team (the heroes they actually run in flex slots)."""
    named = [s.get("hero") for s in rec.get("slots", [])
             if s.get("hero") and s.get("status") != "generic"]
    named_l = {n.lower() for n in named}
    pool = iter([n for n in last_team if n.lower() not in named_l])
    names = []
    for s in rec.get("slots", []):
        if s.get("hero") and s.get("status") != "generic":
            names.append(s["hero"])
        else:
            names.append(next(pool, default_dps))
    return names if len(names) == 5 else None


def build(root: Path | None = None, force: bool = False,
          with_sim: bool = False) -> dict:
    """Assemble the recommendation lists, using the cache when the roster/vault
    is unchanged. Returns {generated_at, hash, ready:[...], need_heroes:[...]}.

    with_sim=True runs cb_sim (current gear) ONLY on the templates whose gear
    already fits the tune (status 'ready') — a small set — to attach projected
    damage, chest tier and T50 survival, and ranks ready teams by damage. The
    heavy 'regear to hit the tune' fit stays an on-demand action, not a batch."""
    root = _root(root)
    cache = root / "data" / CACHE_NAME
    cur_hash = _roster_hash(root)
    if not force and cache.exists():
        try:
            cached = json.loads(cache.read_text())
            if cached.get("hash") == cur_hash and (cached.get("has_sim") or not with_sim):
                return cached
        except Exception:
            pass

    if str(root / "tools") not in sys.path:
        sys.path.insert(0, str(root / "tools"))
    import potential_teams as pt
    pteams = pt.build(max_count=300, root=root, quick=True)
    if "error" in pteams:
        return {"error": pteams["error"], "ready": [], "need_heroes": []}

    spd_map = _hero_spd_map(root)
    ready, need = [], []
    for t in pteams.get("potential_teams", []):
        mech = _MECHANIC.get(t.get("type"), t.get("type") or "Other")
        rec = {
            "id": t.get("id"),
            "name": t.get("name"),
            "mechanic": mech,
            "key_capability": t.get("key_capability"),
            "key_count": _key_sort(t.get("key_capability")),
            "heroes": t.get("heroes"),
            "slots": t.get("slots"),
            "affinity": t.get("affinity"),
            "dwj_url": t.get("dwj_url"),
            "sim_hash": t.get("sim_hash"),
            "est_damage": t.get("est_damage"),     # rough floor; real sim in Phase 2
            "note": t.get("note"),
        }
        if t.get("missing", 0) == 0:
            feasible, gaps = _feasibility(t, spd_map)
            rec["status"] = "ready" if feasible else "lacking-gear"
            rec["gear_gaps"] = gaps
            ready.append(rec)
        else:
            rec["status"] = "need-heroes"
            rec["missing"] = t.get("missing")
            rec["missing_heroes"] = t.get("missing_heroes") or []
            need.append(rec)

    # Phase 2: projected damage for the gear-fits-the-tune ("ready") templates
    # only — run the calibrated cb_sim on current gear (a handful of teams), and
    # attach chest tier + T50 survival. Lacking-gear teams stay un-simmed (their
    # number needs a regear first — the on-demand Solve-gear path).
    has_sim = False
    today_el = None
    if with_sim:
        try:
            from cb_day import today_cb_element_str
            today_el = today_cb_element_str(root / "battle_logs_cb_latest.json")
        except Exception:
            today_el = None
        last_team = pt.last_cb_team_names(root)
        default_dps = getattr(pt, "DEFAULT_DPS_HERO", "Cardiel")
        # DWJ-parity scheduler (100%-matching port) is the RELIABLE survival
        # signal — cb_sim under-survives some tunes, so it drives the badge.
        _dwj_box = {"d": None}

        def _dwj():
            if _dwj_box["d"] is None:
                from dwj_tunes import load_all as _load
                _dwj_box["d"] = _load()
            return _dwj_box["d"]

        for r in ready:
            if r["status"] != "ready":
                continue
            par = None
            try:
                par = pt.parity_survival(r.get("sim_hash"), _dwj, root=root)
            except Exception:
                par = None
            if par:
                r["holds_t50"] = bool(par.get("survived"))
                r["dwj_boss_turns"] = int(par.get("boss_turns") or 0)
                has_sim = True
            names = _team_names(r, last_team, default_dps)
            if names:
                sim = pt.real_sim_damage(names, today_el or r.get("affinity"), root=root)
                if sim and sim.get("total_damage"):
                    # cb_sim absolute is calibration-limited (under-survives) —
                    # shown as a labelled "sim est", NOT used for chest tier.
                    r["sim_damage"] = int(sim["total_damage"])
                    r["sim_boss_turns"] = int(sim.get("boss_turns") or 0)
                    r["sim_team"] = names
                    has_sim = True

    # Ready first (gear fits), ranked by: holds-T50 (DWJ, reliable) -> fewest
    # keys -> sim-damage tiebreak. Lacking-gear teams sink below, by fewest keys.
    def _ready_key(r):
        ready_now = 0 if r["status"] == "ready" else 1
        holds = 0 if r.get("holds_t50") else 1
        return (ready_now, holds, r["key_count"], -(r.get("sim_damage") or 0),
                r["name"] or "")
    ready.sort(key=_ready_key)
    need.sort(key=lambda r: (r.get("missing", 9), r["key_count"], r["name"] or ""))

    result = {
        "generated_at": None,        # stamped by the caller / CLI (no clock in lib)
        "hash": cur_hash,
        "has_sim": has_sim,
        "today_element": today_el,
        "ready": ready,
        "need_heroes": need,
        "counts": {"ready": len(ready), "need_heroes": len(need)},
    }
    return result


def _write_cache(root: Path, result: dict) -> Path:
    result = dict(result)
    result["generated_at"] = int(time.time())
    cache = root / "data" / CACHE_NAME
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(result, indent=2))
    return cache


def _main() -> int:
    ap = argparse.ArgumentParser(description="CB team recommender")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="(re)build the recommendation cache")
    b.add_argument("--force", action="store_true", help="ignore the cache")
    li = sub.add_parser("list", help="print recommendations")
    li.add_argument("--tab", choices=["ready", "need"], default="ready")
    args = ap.parse_args()
    root = _root(None)

    if args.cmd == "build" or args.cmd is None:
        res = build(root, force=True, with_sim=not getattr(args, "no_sim", False))
        if "error" in res:
            print("ERROR:", res["error"]); return 1
        p = _write_cache(root, res)
        print(f"built: {res['counts']['ready']} ready, "
              f"{res['counts']['need_heroes']} need-heroes "
              f"(sim={'yes' if res.get('has_sim') else 'no'}) -> {p}")
        return 0
    if args.cmd == "list":
        res = build(root)
        rows = res["ready"] if args.tab == "ready" else res["need_heroes"]
        for r in rows:
            if args.tab == "ready":
                if r["status"] == "ready":
                    surv = "holds T50" if r.get("holds_t50") else (
                        f"DWJ T{r['dwj_boss_turns']}" if r.get("dwj_boss_turns") else "")
                    dm = f"~{r['sim_damage']/1e6:.1f}M sim" if r.get("sim_damage") else ""
                    extra = f"READY {surv} {dm}".strip()
                else:
                    extra = "lacking gear: " + ", ".join(f"{g['hero']} -{g['short']} SPD" for g in r["gear_gaps"][:3])
            else:
                extra = f"need {', '.join(r['missing_heroes'])}"
            print(f"  [{r['mechanic']:<10}] {r['name'][:22]:<22} {r['key_capability'] or '':<10} {extra}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
