"""Derive useful views from the HH team-suggestion harvest.

`tools/scrape_hellhades_teams.py` pulls raw HH data per stage. This
tool turns that into actionable answers:

  - **runnable**      every hero in the team is in your owned set
  - **close_1**       exactly 1 hero is NOT yet in your owned set
                      (1 ascension/farm away from runnable)
  - **close_2**       exactly 2 heroes outside owned — longer-term target
  - **global**        absolute top by metric, ignoring ownership

Sort metric is automatic per region:
  - Damage-tier bosses (CB, Demon Lord, Hydra, Chimera) → max boss damage
  - Everything else → average duration (lower is better)

Usage:
    # Show top runnable teams for one stage
    python3 tools/hh_team_views.py show \
        --region "Iron Twins Fortress - Void" --stage "Stage 15" \
        --view runnable --top 10

    # All four views for one stage in one shot
    python3 tools/hh_team_views.py show \
        --region "Clan Boss" --stage "Ultra-Nightmare" --view all --top 5

    # Coverage stats — how much of the harvest is on disk
    python3 tools/hh_team_views.py summarize

    # Pre-generate every view as JSON to data/hh/views/
    python3 tools/hh_team_views.py export
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "hh"
TEAMS_DIR = DATA_DIR / "teams"
VIEWS_DIR = DATA_DIR / "views"
REGIONS_PATH = DATA_DIR / "regions.json"
OWNED_PATH = DATA_DIR / "owned_typeids.json"
OWNED_COUNTS_PATH = DATA_DIR / "owned_counts.json"
PINS_PATH = DATA_DIR / "hero_pins.json"
HERO_TYPES_PATH = PROJECT_ROOT / "data" / "static" / "hero_types.json"


def _base_typeid(tid: int) -> int:
    """Hero IDs are blocks of 7 sequential numbers per base hero (ascend 0-6).
    e.g. Gnut: 8010..8016. Base ID = floor(tid/10)*10."""
    return (int(tid) // 10) * 10

DAMAGE_REGION_RE = re.compile(r"clan\s+boss|demon\s+lord|hydra|chimera", re.I)


def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")


def _load_id_to_name() -> dict[int, str]:
    if not HERO_TYPES_PATH.exists():
        return {}
    raw = json.loads(HERO_TYPES_PATH.read_text(encoding="utf-8"))
    rows = raw.get("hero_types") if isinstance(raw, dict) else raw
    out = {}
    for h in (rows or []):
        if isinstance(h, dict) and h.get("id") is not None and h.get("name"):
            out[int(h["id"])] = h["name"]
    return out


def _load_regions() -> list[dict]:
    if not REGIONS_PATH.exists():
        raise SystemExit("regions.json not found. Run scrape_hellhades_teams.py regions first.")
    return json.loads(REGIONS_PATH.read_text(encoding="utf-8"))


def _load_owned() -> set[int]:
    if not OWNED_PATH.exists():
        return set()
    return set(int(x) for x in json.loads(OWNED_PATH.read_text(encoding="utf-8")))


def _load_owned_counts() -> dict[int, int]:
    """Map base typeId -> number of instances owned. Built from /all-heroes
    by tools/hh_team_views.py refresh-counts (or any caller)."""
    if not OWNED_COUNTS_PATH.exists():
        return {}
    raw = json.loads(OWNED_COUNTS_PATH.read_text(encoding="utf-8"))
    return {int(k): int(v) for k, v in raw.items()}


def _load_pins() -> dict[int, list[dict]]:
    """Map base typeId -> list of pins, each {"location": str, "count": int}.
    A hero with N owned instances can be pinned to N different locations
    (or one location with count=N). When computing runnable for location L,
    pins to OTHER locations subtract their counts from the available pool.

    Backward-compat: legacy format `{base_typeId: "<location>"}` is auto-
    upgraded to `{base_typeId: [{"location": ..., "count": 1}]}` on read.
    """
    if not PINS_PATH.exists():
        return {}
    try:
        raw = json.loads(PINS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[int, list[dict]] = {}
    for k, v in raw.items():
        base = int(k)
        if isinstance(v, str):
            out[base] = [{"location": v, "count": 1}]
        elif isinstance(v, list):
            out[base] = [{"location": str(p["location"]),
                          "count": int(p.get("count", 1))} for p in v if p]
        elif isinstance(v, dict):
            out[base] = [{"location": str(v["location"]),
                          "count": int(v.get("count", 1))}]
    return out


def _save_pins(pins: dict[int, list[dict]]):
    PINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PINS_PATH.write_text(
        json.dumps({str(k): v for k, v in pins.items()}, indent=2),
        encoding="utf-8")


def _resolve_hero_to_typeid(name_or_id: str, id_to_name: dict[int, str]) -> int | None:
    """Accept '#1234' (typeId) or hero name (resolves to base typeId).
    Returns base typeId on success, None if not found."""
    s = name_or_id.strip()
    if s.startswith("#"):
        try: return _base_typeid(int(s[1:]))
        except: return None
    if s.isdigit():
        return _base_typeid(int(s))
    # Match by name (case-insensitive substring); prefer exact match
    matches = [(tid, n) for tid, n in id_to_name.items() if n.lower() == s.lower()]
    if matches:
        return _base_typeid(matches[0][0])
    matches = [(tid, n) for tid, n in id_to_name.items() if s.lower() in n.lower()]
    if matches:
        # tied — pick lowest base typeId (deterministic)
        bases = sorted(set(_base_typeid(tid) for tid, _ in matches))
        return bases[0]
    return None


def _stage_dir(region_name: str, stage: dict) -> Path:
    return TEAMS_DIR / _safe_name(region_name) / _safe_name(stage.get("name", "stage"))


def _is_damage_region(region_name: str) -> bool:
    return bool(DAMAGE_REGION_RE.search(region_name or ""))


def _score_fn(metric: str):
    if metric == "dmg":
        return lambda t: -(t.get("maxBossDamage") or 0)
    return lambda t: (t.get("duration") or 1e9)


def _load_suggestions(stage_path: Path, prefer_dmg: bool) -> list[dict]:
    """Return the suggestions list for a stage. For damage-tier bosses
    we prefer suggestions_dmg.json (giveUp=true variant) since it has
    the high-damage stall comps."""
    if prefer_dmg:
        dmg = stage_path / "suggestions_dmg.json"
        if dmg.exists():
            try:
                return json.loads(dmg.read_text(encoding="utf-8"))
            except Exception:
                pass
    base = stage_path / "suggestions.json"
    if base.exists():
        try:
            return json.loads(base.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _dedupe_by_team(teams: list[dict]) -> list[dict]:
    """Multiple `id`s can have the same hero composition — keep the
    first per sorted-typeIds key."""
    seen, out = set(), []
    for t in teams:
        ids = t.get("typeIds") or []
        if not ids:
            continue
        key = tuple(sorted(ids))
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _classify(team: dict, owned: set[int],
              counts: dict[int, int] | None = None) -> tuple[str, list[int]]:
    """Return (view_name, missing_typeIds).

    Duplicate-aware: a team needing 5x Gnut is NOT runnable if the user
    owns only 2 Gnut instances. Counts are by base typeId (ignores
    ascension level). When counts is None, falls back to flat-set check
    (looser, may overcount runnability)."""
    ids = team.get("typeIds") or []
    if counts:
        # Group team by base, compare to owned counts
        from collections import Counter
        need = Counter(_base_typeid(i) for i in ids)
        missing: list[int] = []
        for base, n in need.items():
            have = counts.get(base, 0)
            if have < n:
                # Find the actual typeIds in this team's request to mark missing
                short = n - have
                bucket = [i for i in ids if _base_typeid(i) == base]
                missing.extend(bucket[:short])
    else:
        missing = [i for i in ids if i not in owned]
    if not missing:
        return "runnable", []
    if len(missing) == 1:
        return "close_1", missing
    if len(missing) == 2:
        return "close_2", missing
    return "global_only", missing


def build_view(stage_path: Path, owned: set[int], metric: str,
               min_battles: int = 5,
               counts: dict[int, int] | None = None,
               min_variations: int = 0) -> dict[str, list[dict]]:
    """Return {view_name -> sorted teams[]}."""
    sugg = _load_suggestions(stage_path, prefer_dmg=(metric == "dmg"))
    if not isinstance(sugg, list):
        return {"runnable": [], "close_1": [], "close_2": [], "global": []}
    teams = [t for t in sugg
             if (t.get("numberOfBattles") or 0) >= min_battles
             and (t.get("numberOfTeams") or 0) >= min_variations]
    teams = _dedupe_by_team(teams)
    teams.sort(key=_score_fn(metric))

    out: dict[str, list[dict]] = {"runnable": [], "close_1": [], "close_2": [], "global": []}
    for t in teams:
        view, missing = _classify(t, owned, counts)
        t = dict(t)
        t["_missing"] = missing
        if view in out:
            out[view].append(t)
        out["global"].append(t)
    return out


def _fmt_team_row(t: dict, id_to_name: dict[int, str], metric: str,
                  max_name_width: int = 90) -> str:
    names = []
    for i in (t.get("typeIds") or []):
        n = id_to_name.get(int(i), f"#{i}")
        if int(i) in (t.get("_missing") or []):
            n = f"*{n}*"  # flag missing
        names.append(n)
    team_str = ", ".join(names)
    if len(team_str) > max_name_width:
        team_str = team_str[:max_name_width - 1] + "..."
    # turns survived per battle (defeats end battles in CB; victories rare)
    turns = t.get("turns") or 0
    bat = t.get("numberOfBattles", 0) or 1
    if metric == "dmg":
        max_m = (t.get("maxBossDamage") or 0) / 1e6
        avg_m = (t.get("bossDamage") or 0) / 1e6
        max_str = "2.1B+" if max_m >= 2147 else f"{max_m:.1f}M"
        # damage / turn — measure of pure DPS (vs stall capability)
        per_turn = (avg_m * 1_000_000 / turns) if turns > 0 else 0
        return (f"{team_str:<{max_name_width}} {max_str:>6}  avg {avg_m:>5.1f}M  "
                f"turns {turns:>4.0f}  dmg/t {per_turn/1e3:>5.0f}k  "
                f"bat {t.get('numberOfBattles', 0):>4}  var {t.get('numberOfTeams', 0):>3}")
    else:
        dur = t.get("duration") or 0
        wr = (t.get("winRate") or 0) * 100
        return (f"{team_str:<{max_name_width}} {dur:>5.0f}s  "
                f"wr {wr:>4.1f}%  turns {turns:>4.0f}  "
                f"bat {t.get('numberOfBattles', 0):>4}  var {t.get('numberOfTeams', 0):>3}")


def _print_view(label: str, teams: list[dict], top: int,
                id_to_name: dict[int, str], metric: str):
    print(f"\n--- {label} (top {min(top, len(teams))} of {len(teams)}) ---")
    if not teams:
        print("  (none)")
        return
    for t in teams[:top]:
        print("  " + _fmt_team_row(t, id_to_name, metric))


def _label_for_stage(region_name: str, stage: dict) -> str:
    """Canonical short label for a region+stage; used as the location
    key in hero_pins.json. e.g. 'CB Ultra-Nightmare', 'IT Void S15'."""
    return f"{region_name} :: {stage.get('name','?')}"


def _apply_pins_to_counts(counts: dict[int, int],
                          pins: dict[int, list[dict]],
                          this_location: str) -> dict[int, int]:
    """Return a counts dict reduced by pins to OTHER locations.

    Counts-aware: if you own 2 Demythas and 1 is pinned to CB, this
    location still sees 1 Demytha available (not zero). Multiple pins
    to different non-current locations stack — they all subtract.
    """
    out = dict(counts)
    for base, plist in pins.items():
        consumed = sum(p.get("count", 1) for p in plist if p.get("location") != this_location)
        if consumed:
            out[base] = max(0, out.get(base, 0) - consumed)
    return out


def cmd_show(args):
    regions = _load_regions()
    region = next((r for r in regions
                   if args.region.lower() in (r.get("name") or "").lower()), None)
    if region is None:
        print(f"region not found: {args.region!r}", file=sys.stderr)
        return 2
    stages = region.get("stages") or []
    stage = next((s for s in stages if args.stage in (s.get("name") or "")), None)
    if stage is None:
        print(f"stage not found in {region['name']}: {args.stage!r}", file=sys.stderr)
        return 2

    owned = _load_owned()
    counts = _load_owned_counts()
    pins = _load_pins() if not args.ignore_pins else {}
    id_to_name = _load_id_to_name()
    metric = args.metric
    if metric == "auto":
        metric = "dmg" if _is_damage_region(region["name"]) else "time"

    sd = _stage_dir(region["name"], stage)
    if not sd.exists():
        print(f"no harvest data for {region['name']} :: {stage['name']}\n"
              f"(expected at {sd})", file=sys.stderr)
        return 2

    this_loc = _label_for_stage(region["name"], stage)
    effective_counts = _apply_pins_to_counts(counts, pins, this_loc)
    # Surface heroes that this location LOST capacity to (vs unpinned baseline)
    deltas: list[str] = []
    for base, plist in pins.items():
        consumed = sum(p.get("count", 1) for p in plist if p.get("location") != this_loc)
        if consumed > 0:
            owned_n = counts.get(base, 0)
            free = max(0, owned_n - consumed)
            nm = id_to_name.get(base, f"#{base}")
            note = f"{nm} {free}/{owned_n} avail"
            if free == 0:
                note += " (locked)"
            deltas.append(note)
    if deltas:
        more = "" if len(deltas) <= 8 else f" + {len(deltas) - 8} more"
        print(f"  pins reserve: {', '.join(deltas[:8])}{more}")

    views = build_view(sd, owned, metric, counts=effective_counts,
                       min_battles=args.min_battles)
    print(f"{region['name']} :: {stage['name']}  "
          f"(metric={metric}, owned={len(owned)} typeIds, top={args.top})")

    if args.view in ("all", "runnable"):
        _print_view("RUNNABLE (every hero owned)", views["runnable"],
                    args.top, id_to_name, metric)
    if args.view in ("all", "close_1"):
        _print_view("CLOSE_1 (1 hero away)", views["close_1"],
                    args.top, id_to_name, metric)
    if args.view in ("all", "close_2"):
        _print_view("CLOSE_2 (2 heroes away)", views["close_2"],
                    args.top, id_to_name, metric)
    if args.view in ("all", "global"):
        _print_view("GLOBAL (any heroes)", views["global"],
                    args.top, id_to_name, metric)
    return 0


def cmd_summarize(args):
    regions = _load_regions()
    rows = []
    grand_stages = grand_with = grand_drilled = 0
    for region in regions:
        rname = region.get("name", "?")
        n_stages = 0
        n_with_sugg = 0
        n_with_drill = 0
        for stage in (region.get("stages") or []):
            n_stages += 1
            sd = _stage_dir(rname, stage)
            if (sd / "suggestions.json").exists() or (sd / "suggestions_dmg.json").exists():
                n_with_sugg += 1
            if any(sd.glob("teams_*.json")):
                n_with_drill += 1
        rows.append((rname, n_stages, n_with_sugg, n_with_drill))
        grand_stages += n_stages
        grand_with += n_with_sugg
        grand_drilled += n_with_drill
    rows.sort(key=lambda r: -r[1])
    print(f"{'region':40}  stages  L1     L2/L3")
    print("-" * 70)
    for rname, total, sugg, drill in rows:
        print(f"{rname[:40]:40}  {total:>5}  {sugg:>5}  {drill:>6}")
    print("-" * 70)
    print(f"{'TOTAL':40}  {grand_stages:>5}  {grand_with:>5}  {grand_drilled:>6}")
    pct = 100 * grand_with / grand_stages if grand_stages else 0
    print(f"\nL1 coverage: {pct:.1f}%   L2/L3 coverage: "
          f"{100 * grand_drilled / grand_stages:.1f}%")
    return 0


def cmd_pin(args):
    """Reserve N instances of a hero for a specific location. With
    --count > 1, useful for teams that double up the same hero (e.g.,
    2× Renegade in Iron Twins). If the user owns more instances than
    pinned, the surplus stays available for other locations."""
    id_to_name = _load_id_to_name()
    counts = _load_owned_counts()
    base = _resolve_hero_to_typeid(args.hero, id_to_name)
    if base is None:
        print(f"hero not found: {args.hero!r}", file=sys.stderr)
        return 2
    name = id_to_name.get(base, f"#{base}")
    owned_n = counts.get(base, 0)
    if args.count > owned_n:
        print(f"WARN: pinning {args.count}× {name} but you only own {owned_n}",
              file=sys.stderr)

    pins = _load_pins()
    plist = pins.setdefault(base, [])
    # Merge: if same location already pinned, add to count; else append
    found = False
    for p in plist:
        if p["location"] == args.location:
            p["count"] = p.get("count", 1) + args.count
            found = True
            break
    if not found:
        plist.append({"location": args.location, "count": args.count})
    _save_pins(pins)
    total = sum(p.get("count", 1) for p in plist)
    free = max(0, owned_n - total)
    print(f"pinned {args.count}x {name} -> {args.location}  "
          f"(total reserved: {total}/{owned_n} owned, {free} free)")
    return 0


def cmd_unpin(args):
    id_to_name = _load_id_to_name()
    base = _resolve_hero_to_typeid(args.hero, id_to_name)
    if base is None:
        print(f"hero not found: {args.hero!r}", file=sys.stderr)
        return 2
    name = id_to_name.get(base, f"#{base}")
    pins = _load_pins()
    if base not in pins:
        print(f"{name} was not pinned")
        return 0
    if args.location:
        plist = pins[base]
        new = [p for p in plist if p["location"] != args.location]
        if len(new) == len(plist):
            print(f"{name} was not pinned to {args.location!r}")
        else:
            pins[base] = new
            if not new:
                pins.pop(base, None)
            print(f"unpinned {name} from {args.location}")
    else:
        n = len(pins.pop(base, []))
        print(f"unpinned {name} from all locations ({n} pins removed)")
    _save_pins(pins)
    return 0


def cmd_pins(args):
    id_to_name = _load_id_to_name()
    counts = _load_owned_counts()
    pins = _load_pins()
    if not pins:
        print("no pins set. use 'pin --hero <name> --location <label> [--count N]'")
        return 0
    by_loc: dict[str, list[tuple[str, int]]] = {}
    for base, plist in pins.items():
        nm = id_to_name.get(base, f"#{base}")
        for p in plist:
            by_loc.setdefault(p["location"], []).append((nm, p.get("count", 1)))
    for loc in sorted(by_loc):
        print(f"\n{loc}")
        for nm, n in sorted(by_loc[loc]):
            owned_n = counts.get(_resolve_hero_to_typeid(nm, id_to_name) or 0, 0)
            print(f"  - {nm}  x{n}" + (f"  (you own {owned_n})" if owned_n else ""))
    return 0


def cmd_plan(args):
    """Iterate locations in priority order. For each, find the best
    runnable team given heroes still available (after prior locations
    consumed theirs), then auto-pin those heroes to that location.

    Example:
      python3 tools/hh_team_views.py plan \\
          --priority "Clan Boss::Ultra-Nightmare" \\
          --priority "Iron Twins Fortress - Void::Stage 15" \\
          --priority "Dragon's Lair::Stage 25"
    """
    regions = _load_regions()
    owned = _load_owned()
    counts = _load_owned_counts()
    id_to_name = _load_id_to_name()
    pins: dict[int, str] = {} if args.no_carry else _load_pins().copy()

    print(f"Planning {len(args.priority)} locations in priority order "
          f"(starting pins: {len(pins)})")
    for spec in args.priority:
        if "::" not in spec:
            print(f"  ERROR: priority must be 'region::stage' not {spec!r}", file=sys.stderr)
            continue
        rstr, sstr = spec.split("::", 1)
        region = next((r for r in regions if rstr.lower() in (r.get("name") or "").lower()), None)
        if region is None:
            print(f"  region not found: {rstr!r}", file=sys.stderr); continue
        stage = next((s for s in (region.get("stages") or [])
                      if sstr in (s.get("name") or "")), None)
        if stage is None:
            print(f"  stage not found: {sstr!r} in {region['name']}", file=sys.stderr); continue

        sd = _stage_dir(region["name"], stage)
        if not sd.exists():
            print(f"\n{spec}: no harvest data yet ({sd}); skipping")
            continue

        loc_label = _label_for_stage(region["name"], stage)
        eff_counts = _apply_pins_to_counts(counts, pins, loc_label)
        metric = "dmg" if _is_damage_region(region["name"]) else "time"
        views = build_view(sd, owned, metric, counts=eff_counts)
        runnable = views.get("runnable") or []
        print(f"\n=== {loc_label}  (metric={metric}) ===")
        if not runnable:
            print("  no runnable team — falling back to close_1")
            runnable = views.get("close_1") or []
            if not runnable:
                print("  no close_1 team either; skipping pin step")
                continue
        top = runnable[0]
        names = [id_to_name.get(int(i), f"#{i}") for i in (top.get("typeIds") or [])]
        print(f"  pick: {', '.join(names)}")
        print(f"        " + (
            f"max {(top.get('maxBossDamage') or 0)/1e6:.1f}M  bat {top.get('numberOfBattles')}"
            if metric == "dmg" else
            f"avg {top.get('duration', 0):.0f}s wr {(top.get('winRate') or 0)*100:.0f}%  "
            f"bat {top.get('numberOfBattles')}"))
        # Count hero usage in the picked team (handles 2x same hero)
        from collections import Counter
        need = Counter(_base_typeid(int(i)) for i in (top.get("typeIds") or []))
        for base, n in need.items():
            plist = pins.setdefault(base, [])
            # Merge with existing pin to same location
            for p in plist:
                if p.get("location") == loc_label:
                    p["count"] = p.get("count", 1) + n
                    break
            else:
                plist.append({"location": loc_label, "count": n})

    if args.commit:
        _save_pins(pins)
        n_pins = sum(len(v) for v in pins.values())
        print(f"\ncommitted {n_pins} pins across {len(pins)} heroes to {PINS_PATH}")
    else:
        print("\n(dry run — pass --commit to save the resulting pin map)")
    return 0


def cmd_blockers(args):
    """Identify heroes that block the most stages for your roster.

    For each stage with harvest data, look at the top close_1 and close_2
    teams that meet the reliability bar. Each missing hero is a 'blocker' —
    acquiring that hero would unlock those teams. Aggregate across all
    stages and rank by how many runnable teams the hero would unlock.

    Result tells you which 2-3 heroes to prioritize from fusion / shards
    based on raw unlock value (not opinion / tierlist guesswork)."""
    from collections import defaultdict
    regions = _load_regions()
    owned = _load_owned()
    counts = _load_owned_counts()
    id_to_name = _load_id_to_name()

    # Aggregate: missing hero -> list of (region, stage, team, view_name)
    unlocks: dict[int, list[tuple[str, str, dict, str]]] = defaultdict(list)
    n_stages = 0
    for region in regions:
        rname = region.get("name", "?")
        is_dmg = _is_damage_region(rname)
        metric = "dmg" if is_dmg else "time"
        for stage in (region.get("stages") or []):
            sd = _stage_dir(rname, stage)
            if not sd.exists():
                continue
            n_stages += 1
            views = build_view(sd, owned, metric, counts=counts,
                               min_battles=args.min_battles)
            for vname in (["close_1"] if not args.include_close_2 else ["close_1", "close_2"]):
                for team in (views.get(vname) or [])[: args.top_per_stage]:
                    for mid in (team.get("_missing") or []):
                        base = _base_typeid(int(mid))
                        unlocks[base].append((rname, stage.get("name", "?"), team, vname))

    if not unlocks:
        print(f"no blockers found — checked {n_stages} stages with data; "
              f"either you have everything or harvest hasn't reached the right stages yet")
        return 0

    ranked = sorted(unlocks.items(), key=lambda kv: -len(kv[1]))
    print(f"Blocker analysis across {n_stages} harvested stages "
          f"(min_battles={args.min_battles}, top {args.top_per_stage} teams/stage)\n")
    print(f"{'hero':30}  unlocks  example stages")
    print("-" * 110)
    shown = ranked[: args.top]
    for base, entries in shown:
        name = id_to_name.get(base, f"#{base}")
        # Group examples by region for compactness
        ex_pairs = []
        for rname, sname, t, vn in entries[:5]:
            ex_pairs.append(f"{rname[:18]}::{sname[:8]}")
        ex = ", ".join(ex_pairs)
        if len(entries) > 5:
            ex += f" +{len(entries) - 5} more"
        print(f"  {name:30}  {len(entries):>5}    {ex}")

    if args.show_teams:
        print("\nTOP TEAM PER BLOCKER:")
        for base, entries in shown[:8]:
            name = id_to_name.get(base, f"#{base}")
            # Find best team per metric across this hero's blocks
            entries_sorted = sorted(entries, key=lambda e: -(e[2].get("maxBossDamage") or 0)
                                                          if (e[2].get("maxBossDamage") or 0) > 0
                                                          else (e[2].get("duration") or 1e9))
            top = entries_sorted[0]
            rname, sname, team, vn = top
            team_names = [id_to_name.get(int(i), f"#{i}") for i in (team.get("typeIds") or [])]
            for k in (team.get("_missing") or []):
                tn = id_to_name.get(_base_typeid(k), f"#{k}")
                team_names = [(f"*{n}*" if n == tn else n) for n in team_names]
            print(f"\n  Acquire {name} -> top team @ {rname} :: {sname}")
            print(f"    {', '.join(team_names)}")
    return 0


def cmd_export(args):
    """Pre-generate views as JSON for every stage."""
    regions = _load_regions()
    owned = _load_owned()
    counts = _load_owned_counts()
    id_to_name = _load_id_to_name()
    n_done = 0
    for region in regions:
        rname = region.get("name", "?")
        is_dmg = _is_damage_region(rname)
        for stage in (region.get("stages") or []):
            sd = _stage_dir(rname, stage)
            if not sd.exists():
                continue
            metric = "dmg" if is_dmg else "time"
            views = build_view(sd, owned, metric, counts=counts)
            out_dir = VIEWS_DIR / _safe_name(rname) / _safe_name(stage.get("name", ""))
            out_dir.mkdir(parents=True, exist_ok=True)
            for vname, teams in views.items():
                # Resolve names + add to top-N for compactness
                top = teams[: args.top]
                for t in top:
                    t["heroNames"] = [id_to_name.get(int(i), f"#{i}")
                                       for i in (t.get("typeIds") or [])]
                    if t.get("_missing"):
                        t["missingNames"] = [id_to_name.get(int(i), f"#{i}")
                                              for i in t["_missing"]]
                (out_dir / f"{vname}.json").write_text(
                    json.dumps(top, indent=2), encoding="utf-8")
            n_done += 1
    print(f"exported views for {n_done} stages -> {VIEWS_DIR}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("show", help="Print views for one stage")
    sp.add_argument("--region", required=True, help="Region name substring")
    sp.add_argument("--stage", required=True, help="Stage name substring")
    sp.add_argument("--view", choices=["runnable", "close_1", "close_2", "global", "all"],
                    default="runnable")
    sp.add_argument("--metric", choices=["auto", "time", "dmg"], default="auto")
    sp.add_argument("--top", type=int, default=10)
    sp.add_argument("--min-battles", type=int, default=5,
                    help="Reliability filter — drop teams with <N total battles (default 5)")
    sp.add_argument("--ignore-pins", action="store_true",
                    help="Show teams as if no heroes were pinned (raw view)")

    sub.add_parser("summarize", help="Show harvest coverage stats")

    sx = sub.add_parser("export", help="Write views as JSON for all stages")
    sx.add_argument("--top", type=int, default=15)

    bl = sub.add_parser("blockers",
        help="Find which heroes (not in your roster) would unlock the most stages")
    bl.add_argument("--min-battles", type=int, default=5,
                    help="Reliability filter (default 5)")
    bl.add_argument("--top-per-stage", type=int, default=5,
                    help="Look at top N close_1 teams per stage (default 5)")
    bl.add_argument("--top", type=int, default=20,
                    help="Show this many blocker heroes (default 20)")
    bl.add_argument("--include-close-2", action="store_true",
                    help="Also count heroes blocking close_2 teams (more aspirational)")
    bl.add_argument("--show-teams", action="store_true",
                    help="For top blockers, show the best team they'd unlock")

    pin_p = sub.add_parser("pin",
        help="Reserve N instances of a hero for a location. Surplus (owned but unpinned) "
             "stays available for other locations.")
    pin_p.add_argument("--hero", required=True, help="Hero name or '#<typeId>'")
    pin_p.add_argument("--location", required=True,
        help="Free-form label, e.g. 'Clan Boss :: Ultra-Nightmare'")
    pin_p.add_argument("--count", type=int, default=1,
        help="Instances to reserve (default 1; use 2 for teams that double up the same hero)")

    unpin_p = sub.add_parser("unpin", help="Remove a hero pin")
    unpin_p.add_argument("--hero", required=True, help="Hero name or '#<typeId>'")
    unpin_p.add_argument("--location", default=None,
        help="Remove only the pin to this location (default: remove all pins for this hero)")

    sub.add_parser("pins", help="List current pins by location")

    pl = sub.add_parser("plan",
        help="Iterate locations in priority order; pick top runnable per location, "
             "auto-pinning heroes so later locations get the next best team")
    pl.add_argument("--priority", action="append", required=True,
        help="Location specifier 'region_substring::stage_substring' (use multiple times)")
    pl.add_argument("--commit", action="store_true",
        help="Write resulting pin map to disk (default: dry run)")
    pl.add_argument("--no-carry", action="store_true",
        help="Ignore existing pins; plan from scratch")

    args = p.parse_args()
    handlers = {
        "show": cmd_show, "summarize": cmd_summarize, "export": cmd_export,
        "pin": cmd_pin, "unpin": cmd_unpin, "pins": cmd_pins, "plan": cmd_plan,
        "blockers": cmd_blockers,
    }
    return handlers[args.cmd](args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
