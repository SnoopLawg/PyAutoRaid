"""Score DWJ tunes against the owned roster — surface viable CB teams.

Drives the dashboard's "Potential Teams" panel and the CLI here. The
scoring chain is:

1. comp_finder.evaluate_tune  (roster gap analysis per tune)
2. comp_finder.rank_tunes     (HellHades rating boost)
3. calc_parity_sim            (DWJ-parity scheduler — does the tune
                                 survive 50 boss turns?)
4. cb_calibrate.run_sim_for_team (real damage sim with user's gear)
5. _last_cb_team_names         (which tune is the user actually running?)

CLI usage:
    python3 tools/potential_teams.py --top 10
    python3 tools/potential_teams.py --json --top 5
    python3 tools/potential_teams.py --runnable
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# Damage floor estimates by tune "key capability" (1 Key UNM, 2 Key UNM, ...).
# Used when the real-damage sim isn't available (missing roster heroes etc.).
# ============================================================================

KEY_CAPABILITY_DAMAGE: dict[str, int] = {
    "1 Key UNM": 50_000_000,
    "2 Key UNM": 30_000_000,
    "3 Key UNM": 20_000_000,
    "4 Key UNM": 12_000_000,
    "5 Key UNM": 10_000_000,
}


def damage_floor_for_key(key_cap: str | None, affinity: str | None) -> int:
    base = KEY_CAPABILITY_DAMAGE.get(key_cap or "", 10_000_000)
    if affinity and "Void" in affinity and "Only" in affinity:
        return int(base * 0.95)
    return base


# Hero name to use when a tune slot is "generic" (e.g. "DPS" placeholder).
DEFAULT_DPS_HERO = "Ninja"


# ============================================================================
# Caches — module-level so build_potential_teams() called multiple times
# (dashboard polls every ~1s) doesn't redo expensive sim work.
# ============================================================================

_parity_survival_cache: dict[str | None, dict | None] = {}
_real_sim_damage_cache: dict[str, dict | None] = {}


# ============================================================================
# Helpers — read battle log for "today's element" + "last team"
# ============================================================================

def _ensure_path(root: Path) -> None:
    """Make sure root + tools/ are importable when run as a script."""
    for p in (str(root), str(root / "tools")):
        if p not in sys.path:
            sys.path.insert(0, p)


def last_cb_team_names(root: Path) -> list[str]:
    """Hero names from the most recent battle_logs_cb_latest.json player team.
    Empty list if no log or fewer than 5 players visible."""
    log_path = root / "battle_logs_cb_latest.json"
    if not log_path.exists():
        return []
    try:
        _ensure_path(root)
        from cb_history import hero_type_to_name
        d = json.loads(log_path.read_text())
        type_to_name = hero_type_to_name(root)
        for entry in (d.get("log") or [])[:30]:
            if isinstance(entry, dict) and entry.get("heroes"):
                names = []
                for h in entry["heroes"]:
                    if h.get("side") != "player":
                        continue
                    nm = h.get("name") or type_to_name.get(h.get("type_id"))
                    if nm:
                        names.append(nm)
                if len(names) == 5:
                    return names
        return []
    except Exception:
        return []


def tune_match_score(tune_slots: list[dict], actual_team: list[str]) -> float:
    """Score how well a DWJ tune's slot list matches the user's actual team.

    1.0 = every named slot matches a hero in actual_team and any generic
    "DPS" slot has at least one team hero left over to fill it. Lower
    scores indicate partial/missing matches.
    """
    if not tune_slots or not actual_team:
        return 0.0
    actual_norm = {n.lower(): n for n in actual_team}
    used = set()
    named_total = 0
    named_matched = 0
    generic_count = 0
    for s in tune_slots:
        hero = (s.get("hero") or "").strip()
        if not hero:
            continue
        if hero.upper() in ("DPS", "4:3 DPS", "ATTACKER", "BANNER LORD"):
            generic_count += 1
            continue
        named_total += 1
        nm_lower = hero.lower()
        if nm_lower in actual_norm and nm_lower not in used:
            named_matched += 1
            used.add(nm_lower)
            continue
        # Partial match — substring either way
        for cand_lower, cand in actual_norm.items():
            if cand_lower in used:
                continue
            if nm_lower in cand_lower or cand_lower in nm_lower:
                named_matched += 1
                used.add(cand_lower)
                break
    if named_total == 0:
        return 0.0
    score = named_matched / named_total
    # Bonus if generic DPS slots have available heroes left over
    if generic_count and (len(actual_team) - len(used)) >= generic_count:
        score = min(1.0, score + 0.05)
    return score


# ============================================================================
# Sim wrappers — cached calls into calc_parity_sim and cb_sim
# ============================================================================

def real_sim_damage(team_names: list[str], cb_element_str: str | None,
                    *, root: Path) -> dict | None:
    """Run cb_sim against a 5-hero team and return damage + boss_turns.
    cb_element_str is one of 'magic'/'force'/'spirit'/'void'; defaults to void.
    Returns None if any team member isn't 6-star (partial-team simmed)."""
    if not team_names or len(team_names) != 5:
        return None
    cb_el = (cb_element_str or "void").lower()
    cache_key = "|".join(team_names) + "::" + cb_el
    if cache_key in _real_sim_damage_cache:
        return _real_sim_damage_cache[cache_key]
    try:
        sys.path.insert(0, str(root / "tools"))
        from cb_calibrate import run_sim_for_team
        element_map = {"magic": 1, "force": 2, "spirit": 3, "void": 4}
        cb_el_int = element_map.get(cb_el, 4)
        result = run_sim_for_team(team_names, cb_element=cb_el_int,
                                  force_affinity=True, max_cb_turns=50,
                                  use_current_gear=True)
        if result.get("partial_team"):
            out = None
        else:
            out = {
                "total_damage": int(result.get("total", 0) or 0),
                "boss_turns": int(result.get("cb_turns", 0) or 0),
            }
    except Exception:
        out = None
    _real_sim_damage_cache[cache_key] = out
    return out


def parity_survival(variant_hash: str | None, dwj_loader, *, root: Path) -> dict | None:
    """Run calc_parity_sim against `variant_hash` for 50 boss turns and
    return {boss_turns, actions, survived}, or None on missing/error."""
    if not variant_hash:
        return None
    if variant_hash in _parity_survival_cache:
        return _parity_survival_cache[variant_hash]
    try:
        sys.path.insert(0, str(root / "tools"))
        import calc_parity_sim as cps
        variant = dwj_loader().variants_by_hash.get(variant_hash)
        if variant is None:
            _parity_survival_cache[variant_hash] = None
            return None
        turns = cps.simulate(variant, max_boss_turns=50)
        boss_tn = cps.count_boss_turns(turns)
        result = {
            "boss_turns": boss_tn,
            "actions": len(turns),
            "survived": boss_tn >= 50,
        }
        _parity_survival_cache[variant_hash] = result
        return result
    except Exception:
        _parity_survival_cache[variant_hash] = None
        return None


# ============================================================================
# Main — score all tunes vs roster, return top N
# ============================================================================

def build(max_count: int = 12, *, root: Path | None = None) -> dict:
    """Score all DWJ tunes against user's owned roster and return the top.

    Returns {"potential_teams": [...]} or {"error": "..."} on failure.
    """
    if root is None:
        root = Path(__file__).resolve().parent.parent
    _ensure_path(root)

    try:
        import comp_finder as cf
        from dwj_tunes import load_all as load_dwj_all
    except Exception as e:
        return {"error": f"comp_finder import failed: {e}"}

    try:
        roster = cf.load_roster()
        tunes = cf.load_tunes()
        hh = cf.load_hh_ratings()
        calc_variants = cf.load_calc_variants()
        tunes = [cf.enrich_tune_slots_with_calc(t, calc_variants) for t in tunes]
    except Exception as e:
        return {"error": f"dwj/hh data load failed: {e}"}

    _dwj_cached: dict = {"d": None}

    def _dwj():
        if _dwj_cached["d"] is None:
            _dwj_cached["d"] = load_dwj_all()
        return _dwj_cached["d"]

    evaluated = [cf.evaluate_tune(t, roster) for t in tunes]
    ranked = cf.rank_tunes(evaluated, hh)

    # Today's CB affinity from the boss in the latest battle log
    from cb_day import today_cb_element_str
    today_element = today_cb_element_str(root / "battle_logs_cb_latest.json")
    last_team = last_cb_team_names(root)
    active_slug = None
    if last_team:
        best_score = 0.0
        for ev in ranked:
            score = tune_match_score(ev["tune"].get("slots") or [], last_team)
            if score > best_score and ev["missing"] == 0:
                best_score = score
                active_slug = ev["tune"].get("slug")
        if best_score < 0.6:
            active_slug = None

    if active_slug:
        active_idx = next((i for i, ev in enumerate(ranked)
                           if ev["tune"].get("slug") == active_slug), None)
        if active_idx is not None and active_idx > 0:
            ranked.insert(0, ranked.pop(active_idx))

    out: list[dict] = []
    for ev in ranked:
        t = ev["tune"]
        slots = ev["slots"]
        missing = ev["missing"]
        ascending = ev["ascending"]
        if t.get("slug") == active_slug:
            status = "active"
        elif missing == 0 and ascending == 0:
            status = "active" if (active_slug is None and len(out) == 0) else "candidate"
        elif missing <= 1:
            status = "candidate"
        else:
            status = "backup"
        conf = max(0.3, 1.0 - 0.15 * missing - 0.1 * ascending)
        heroes = [s.get("hero") or "?" for s in slots]
        floor = damage_floor_for_key(t.get("key_capability"), t.get("affinity"))
        est_damage = floor
        if missing:
            est_damage = int(est_damage * (0.85 ** missing))
        tags = []
        if t.get("type"):
            tags.append(t["type"].lower())
        if t.get("key_capability"):
            tags.append(t["key_capability"].replace(" ", "-").lower())
        if t.get("difficulty"):
            tags.append(t["difficulty"].lower())
        calc_links = []
        for c in t.get("calculator_links") or []:
            calc_links.append({
                "name": c.get("name") or "link",
                "hash": c.get("hash"),
                "url": c.get("url"),
            })
        unm_link = next((c for c in calc_links if "ultra" in (c.get("name") or "").lower() or "unm" in (c.get("name") or "").lower()), None)
        sim_hash = (unm_link or (calc_links[0] if calc_links else {})).get("hash")
        parity = parity_survival(sim_hash, _dwj, root=root) if missing == 0 else None
        real_sim = None
        if missing == 0:
            named_in_tune = {s.get("hero", "").lower(): True
                             for s in slots if s.get("status") != "generic"}
            dps_pool = [n for n in last_team if n.lower() not in named_in_tune]
            dps_iter = iter(dps_pool)
            team_names = []
            for s in slots:
                hn = s.get("hero")
                if not hn or s.get("status") == "generic":
                    team_names.append(next(dps_iter, DEFAULT_DPS_HERO))
                else:
                    team_names.append(hn)
            if len(team_names) == 5:
                el_str = today_element or t.get("affinity")
                real_sim = real_sim_damage(team_names, el_str, root=root)
        if parity:
            bt = parity.get("boss_turns") or 0
            if parity.get("survived"):
                conf = max(conf, 0.95)
            else:
                conf = min(conf, 0.3 + (bt / 50) * 0.5)
        if real_sim and real_sim.get("total_damage", 0) > 0:
            est_damage = real_sim["total_damage"]
        elif parity:
            bt = parity.get("boss_turns") or 0
            if bt > 0:
                surv_factor = min(1.0, bt / 50)
                actions = parity.get("actions") or 0
                import math
                action_factor = max(0.7, min(1.5, math.sqrt(actions / 250.0))) if actions else 1.0
                est_damage = int(est_damage * surv_factor * action_factor)
        note_bits = []
        if ev.get("missing_heroes"):
            note_bits.append("need " + ", ".join(ev["missing_heroes"]))
        if ev.get("ascending_heroes"):
            asc_txt = ", ".join(f"{h} ({g}★)" for h, g in ev["ascending_heroes"])
            note_bits.append("ascend " + asc_txt)
        if not note_bits and t.get("description"):
            note_bits.append(t["description"][:120] + ("…" if len(t["description"]) > 120 else ""))
        note = " · ".join(note_bits) or ""
        variant_speeds_by_index = {}
        if sim_hash:
            try:
                v = _dwj().variants_by_hash.get(sim_hash)
                if v:
                    for cs in (getattr(v, "slots", None) or []):
                        idx = getattr(cs, "index", None)
                        sp = getattr(cs, "total_speed", None) or getattr(cs, "base_speed", None)
                        if idx is not None and sp:
                            variant_speeds_by_index[idx] = int(sp)
            except Exception:
                pass
        slot_details = []
        for s in slots:
            min_s = s.get("min_spd")
            max_s = s.get("max_spd")
            if (min_s is None or max_s is None):
                vs = variant_speeds_by_index.get(s.get("index"))
                if vs is not None:
                    min_s = min_s if min_s is not None else vs
                    max_s = max_s if max_s is not None else vs
            slot_details.append({
                "index": s.get("index"),
                "hero": s.get("hero"),
                "status": s.get("status"),
                "min_spd": min_s,
                "max_spd": max_s,
                "roster_grade": s.get("roster_grade"),
            })
        out.append({
            "id": t.get("slug"),
            "name": t.get("name") or "Unnamed",
            "status": status,
            "est_damage": est_damage,
            "confidence": round(conf, 2),
            "tags": tags,
            "heroes": heroes,
            "note": note,
            "missing": missing,
            "ascending": ascending,
            "affinity": t.get("affinity"),
            "key_capability": t.get("key_capability"),
            "type": t.get("type"),
            "difficulty": t.get("difficulty"),
            "dwj_url": t.get("url"),
            "calculator_links": calc_links,
            "slots": slot_details,
            "parity_sim": parity,
            "real_sim": real_sim,
            "sim_hash": sim_hash,
        })
        if len(out) >= max_count:
            break
    return {"potential_teams": out}


# ============================================================================
# CLI — same data the dashboard's potential-teams panel renders.
# ============================================================================

def _main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=10, help="how many tunes to show")
    ap.add_argument("--runnable", action="store_true",
                    help="only show tunes with missing=0 (full roster fit)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    result = build(max_count=args.top * 4 if args.runnable else args.top)
    if "error" in result:
        print(f"ERR: {result['error']}", file=sys.stderr)
        return 2
    teams = result["potential_teams"]
    if args.runnable:
        teams = [t for t in teams if t.get("missing", 1) == 0][:args.top]
    if args.json:
        print(json.dumps({"potential_teams": teams}, indent=2))
        return 0

    print(f"{'#':>2}  {'status':9} {'name':30} {'dmg':>8} {'conf':>4} {'miss':>4}  team")
    for i, t in enumerate(teams, 1):
        team_str = ", ".join(h for h in t["heroes"][:5] if h)
        dmg_m = t["est_damage"] / 1e6
        print(f"{i:>2}  {t['status']:9} {t['name'][:30]:30} {dmg_m:>6.1f}M {t['confidence']:>4.2f} "
              f"{t['missing']:>4}  {team_str}")
        if t.get("note"):
            print(f"     -> {t['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
