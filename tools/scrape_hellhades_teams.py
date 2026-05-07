"""Scrape HellHades raidoptimiser.hellhades.com team-finder data.

The HH "Find Team" feature surfaces user-shared battle teams per
dungeon/stage/affinity, including hero rosters, speeds, and (per
variation) gear/skill orders. This tool harvests that data so we
can use it as ground-truth team recommendations for any location
without depending on HH being online.

Auth: requires a Bearer token from the user's HH session. Read it
from the env var HH_TOKEN, or pass --token on the command line.
The token lives in localStorage at https://raidoptimiser.hellhades.com
under the key `access_token` while the user is logged in.

Endpoints discovered (Angular SPA backend):
  GET  /api/Region                       — 65 regions, each with stages[]
  GET  /api/AccountMetadata              — user's heroes/artifacts (not needed for scrape)
  POST /api/TeamSuggestion/suggestions   — teams for one stage
  POST /api/TeamSuggestion/teams         — variations of one team
  POST /api/TeamSuggestion/details       — battle-level detail for one variation

Suggestions request body shape (verified 2026-05-03):
  {
    "stageId": <int>,                  # = floorId from /api/Region
    "minimumNumberOfBattles": 2,
    "winRate": 0.75,
    "typeIds": [<int>, ...],           # all known champion type IDs (filter)
    "minimumBossDamage": null,
    "teamSetupId": null,
    "autoOnly": false,
    "minimumNumberOfVictories": 0,
    "lastBossDamage": false,
    "giveUp": false,
    "requiredTypeIds": [],
    "soloTeams": false
  }

Output layout (under data/hh/teams/):
  data/hh/regions.json                  — full region+stages catalog
  data/hh/teams/<region>/<stage>/suggestions.json  — team summaries
  data/hh/teams/<region>/<stage>/teams_<group>.json — variations per group
  data/hh/teams/<region>/<stage>/details_<variant>.json — battles per variation

Usage:
  HH_TOKEN=<bearer> python3 tools/scrape_hellhades_teams.py regions
  HH_TOKEN=<bearer> python3 tools/scrape_hellhades_teams.py stage --region "Iron Twins Fortress" --difficulty Void --stage 15
  HH_TOKEN=<bearer> python3 tools/scrape_hellhades_teams.py all     # full harvest (slow, respectful pacing)
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "hh"
TEAMS_DIR = DATA_DIR / "teams"
REGIONS_PATH = DATA_DIR / "regions.json"

BASE = "https://raidoptimiser.hellhades.com"
USER_AGENT = "PyAutoRaid/scrape_hellhades_teams (research)"

# Pace requests so we don't hammer their server. HH's UI itself
# fires single requests on user clicks, so a 0.5s gap is comfortable.
DEFAULT_DELAY = 0.5


def _request(method: str, path: str, token: str, body: dict | None = None,
             timeout: float = 60.0, max_retries: int = 3) -> dict | list:
    """HTTP with backoff. On 429 we sleep 60s and retry. On 401 we surface the
    error so the caller can refresh the token. On 5xx we retry up to max_retries
    with exponential backoff."""
    url = f"{BASE}{path}"
    data = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode("utf-8")
            return json.loads(text) if text else {}
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 401:
                raise  # caller handles auth refresh
            if e.code == 429:
                time.sleep(60.0 + random.uniform(0, 10))
                continue
            if 500 <= e.code < 600:
                time.sleep((2 ** attempt) + random.uniform(0, 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            # Catch RemoteDisconnected, ConnectionResetError, BrokenPipeError —
            # all transient network issues that warrant retry, not abort.
            last_err = e
            time.sleep((2 ** attempt) + random.uniform(0, 1))
    if last_err:
        raise last_err
    raise RuntimeError("request failed without specific error")


def _jitter(base: float) -> float:
    """Add ±30% jitter so requests don't form a perfect 2 Hz rhythm."""
    return base * random.uniform(0.7, 1.3)


def _safe_name(s: str) -> str:
    """Filesystem-safe slug for region/stage names."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")


def fetch_regions(token: str) -> list[dict]:
    """Pull the full /api/Region catalog and cache to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching /api/Region...")
    regions = _request("GET", "/api/Region", token)
    REGIONS_PATH.write_text(json.dumps(regions, indent=2), encoding="utf-8")
    total_stages = sum(len(r.get("stages") or []) for r in regions)
    print(f"  saved {len(regions)} regions / {total_stages} stages -> {REGIONS_PATH}")
    return regions


def load_regions() -> list[dict]:
    if not REGIONS_PATH.exists():
        raise SystemExit("regions.json not found. Run: scrape_hellhades_teams.py regions")
    return json.loads(REGIONS_PATH.read_text(encoding="utf-8"))


def all_type_ids(regions: list[dict]) -> list[int]:
    """The /suggestions filter `typeIds` whitelists which champions can
    appear in returned teams — sending an incomplete list silently drops
    teams. Easiest comprehensive value: the full int range 1..30000 covers
    every champion ID we've ever seen (real IDs sit in the low thousands;
    e.g. Renegade=420, Mithrala=6740, Gnut=8010, Lord Champfort=910).

    For Iron Twins Void S15 verified 2026-05-03: 624 stage-typeIds → 591
    teams; range 1..30000 → 40,525 teams (including the 39s/100%/405-battle
    Renegade×2+Mithrala+Gnut×2 fastest).
    """
    return list(range(1, 30001))


def fetch_stage_suggestions(token: str, stage_id: int, type_ids: list[int],
                            min_battles: int = 2, win_rate: float = 0.75) -> list[dict]:
    body = {
        "stageId": stage_id,
        "minimumNumberOfBattles": min_battles,
        "winRate": win_rate,
        "typeIds": type_ids,
        "minimumBossDamage": None,
        "teamSetupId": None,
        "autoOnly": False,
        "minimumNumberOfVictories": 0,
        "lastBossDamage": False,
        "giveUp": False,
        "requiredTypeIds": [],
        "soloTeams": False,
    }
    return _request("POST", "/api/TeamSuggestion/suggestions", token, body=body)  # type: ignore[return-value]


def fetch_team_variations(token: str, stage_id: int, type_ids: list[int],
                          team_setup_id: str, min_battles: int = 2,
                          win_rate: float = 0.75) -> list[dict]:
    """List the variations within one team group. `team_setup_id` is the
    `id` returned by /suggestions for that team group. typeIds must be
    that team's 5 hero typeIds (in the order returned by /suggestions).
    Each variation includes per-hero `members[].stats.Speed` — the
    speed-tune the user explicitly cares about.
    """
    body = {
        "stageId": stage_id,
        "minimumNumberOfBattles": min_battles,
        "winRate": win_rate,
        "typeIds": type_ids,
        "minimumBossDamage": None,
        "teamSetupId": team_setup_id,
        "autoOnly": False,
        "minimumNumberOfVictories": 0,
        "lastBossDamage": False,
        "giveUp": False,
        "requiredTypeIds": [],
        "soloTeams": False,
    }
    return _request("POST", "/api/TeamSuggestion/teams", token, body=body)  # type: ignore[return-value]


def fetch_battle_details(token: str, variation_team_id: str) -> dict:
    """Full build for one variation — heroes with stats/masteries/artifacts/
    skillLevels/relics, plus team-level skillPriorities and
    skillPrioritiesByRound. `variation_team_id` is the `teamId` returned
    by /teams for that variation.
    """
    body = {"teamId": variation_team_id}
    return _request("POST", "/api/TeamSuggestion/details", token, body=body)  # type: ignore[return-value]


def stage_dir(region_name: str, stage: dict) -> Path:
    return TEAMS_DIR / _safe_name(region_name) / _safe_name(stage.get("name", "stage"))


def cmd_regions(args, token):
    fetch_regions(token)


def _select_drill_targets(sugg: list[dict], top_teams: int,
                          owned: set[int] | None,
                          metric: str) -> list[dict]:
    """Pick which teams to drill. Returns deduped list combining:
    - top N globally (by metric)
    - top N runnable (every hero in owned set) — current potential
    - top N close-potential (≤1 hero outside owned set) — near-term build target

    metric='dmg' → sort by maxBossDamage desc (CB / Hydra / Chimera / Demon Lord)
    metric='time' → sort by duration asc (timed-clear stages)
    """
    if metric == "dmg":
        keyfn = lambda t: -(t.get("maxBossDamage") or 0)
    else:
        keyfn = lambda t: t.get("duration") or 1e9

    # Filter junk / duplicate hero compositions
    seen = set()
    unique = []
    for t in sugg:
        if (t.get("numberOfBattles") or 0) < 2:
            continue
        ids = t.get("typeIds") or []
        if not ids:
            continue
        key = tuple(sorted(ids))
        if key in seen:
            continue
        seen.add(key)
        unique.append(t)
    unique.sort(key=keyfn)

    picks: list[dict] = []
    picked_keys: set[tuple] = set()
    def take(pool: list[dict], n: int):
        for t in pool:
            k = tuple(sorted(t.get("typeIds") or []))
            if k in picked_keys:
                continue
            picks.append(t)
            picked_keys.add(k)
            if sum(1 for x in pool if tuple(sorted(x["typeIds"])) in picked_keys) >= n:
                break

    take(unique, top_teams)  # top-N global
    if owned:
        runnable = [t for t in unique if all(i in owned for i in t["typeIds"])]
        take(runnable, top_teams)  # top-N currently-runnable
        close_1 = [t for t in unique
                   if sum(1 for i in t["typeIds"] if i not in owned) == 1]
        take(close_1, top_teams)  # top-N one-hero-away
    return picks


def _drill_stage(token: str, stage_id: int, sugg: list[dict],
                 out_dir: Path, top_teams: int, top_variations: int,
                 delay: float, owned: set[int] | None = None,
                 metric: str = "time") -> tuple[int, int]:
    """For top-N teams in the suggestions list, fetch /teams, then for
    top-M variations of each team fetch /details. Saves under out_dir.
    Returns (teams_fetched, details_fetched)."""
    if not isinstance(sugg, list) or not sugg:
        return 0, 0
    targets = _select_drill_targets(sugg, top_teams, owned, metric)
    teams_n = 0
    details_n = 0
    for team in targets:
        team_id = team.get("id")
        if not team_id:
            continue
        var_path = out_dir / f"teams_{team_id}.json"
        if var_path.exists():
            try:
                var = json.loads(var_path.read_text(encoding="utf-8"))
            except Exception:
                var = None
        else:
            try:
                var = fetch_team_variations(token, stage_id, team["typeIds"], team_id)
            except urllib.error.HTTPError as e:
                # Common: HH returns 500 for some team groups (cause unclear).
                # Skip and move on so one bad team doesn't abort the whole harvest.
                print(f"    teams {team_id[:8]} ERROR {e.code}", file=sys.stderr)
                time.sleep(_jitter(delay))
                continue
            var_path.write_text(json.dumps(var, indent=2), encoding="utf-8")
            teams_n += 1
            time.sleep(_jitter(delay))
        if not isinstance(var, list):
            continue
        # Pick variations by metric
        v_sorted = sorted(var,
                          key=(lambda v: -(v.get("bossDamage") or 0)) if metric == "dmg"
                          else (lambda v: -(v.get("numberOfVictories") or 0)))
        for variation in v_sorted[:top_variations]:
            var_team_id = variation.get("teamId")
            if not var_team_id:
                continue
            det_path = out_dir / f"details_{var_team_id}.json"
            if det_path.exists():
                continue
            try:
                det = fetch_battle_details(token, var_team_id)
            except urllib.error.HTTPError as e:
                print(f"    details {var_team_id} ERROR {e.code}", file=sys.stderr)
                time.sleep(_jitter(delay))
                continue
            det_path.write_text(json.dumps(det, indent=2), encoding="utf-8")
            details_n += 1
            time.sleep(_jitter(delay))
    return teams_n, details_n


def cmd_stage(args, token):
    regions = load_regions()
    region = next((r for r in regions if args.region.lower() in (r.get("name") or "").lower()), None)
    if region is None:
        print(f"ERROR: region matching {args.region!r} not found", file=sys.stderr)
        return 2
    stages = region.get("stages") or []
    stage = next((s for s in stages if args.stage in (s.get("name") or "")), None)
    if stage is None:
        print(f"ERROR: stage {args.stage!r} not found in {region['name']}", file=sys.stderr)
        return 2
    print(f"{region['name']} :: {stage['name']} (floorId={stage.get('floorId')})")
    type_ids = all_type_ids(regions)
    stage_id = int(stage["floorId"])
    sugg = fetch_stage_suggestions(token, stage_id, type_ids)
    out = stage_dir(region["name"], stage)
    out.mkdir(parents=True, exist_ok=True)
    (out / "suggestions.json").write_text(json.dumps(sugg, indent=2), encoding="utf-8")
    n = len(sugg) if isinstance(sugg, list) else 0
    print(f"  saved {n} suggestions -> {out / 'suggestions.json'}")
    if args.drill and isinstance(sugg, list) and sugg:
        time.sleep(args.delay)
        teams_n, det_n = _drill_stage(token, stage_id, sugg, out,
                                       args.top_teams, args.top_variations, args.delay)
        print(f"  drilled top {teams_n} teams, fetched {det_n} variation details")
    return 0


def _is_damage_region(region_name: str) -> bool:
    """Damage-tier bosses (CB / Hydra / Chimera / Demon Lord) are scored on
    boss damage, not win rate. They also benefit from giveUp=true so we
    can capture stall comps that 'lose' but maximize damage."""
    n = (region_name or "").lower()
    return any(k in n for k in ("clan boss", "demon lord", "hydra", "chimera"))


def _load_owned_ids() -> set[int]:
    p = DATA_DIR / "owned_typeids.json"
    if not p.exists():
        return set()
    try:
        return set(int(x) for x in json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()


def cmd_all(args, token):
    regions = load_regions()
    type_ids = all_type_ids(regions)
    owned = _load_owned_ids()
    delay = args.delay
    total_stages = sum(len(r.get("stages") or []) for r in regions)
    print(f"Harvesting {total_stages} stages across {len(regions)} regions "
          f"(delay~{delay}s+/-30%; owned={len(owned)} typeIds)")
    done = 0
    for region in regions:
        rname = region.get("name", "?")
        is_damage = _is_damage_region(rname)
        metric = "dmg" if is_damage else "time"
        for stage in (region.get("stages") or []):
            sname = stage.get("name", "?")
            floor_id = stage.get("floorId")
            if floor_id is None:
                done += 1
                continue
            out = stage_dir(rname, stage)
            sugg_path = out / "suggestions.json"
            sugg = None
            if sugg_path.exists() and not args.force:
                try: sugg = json.loads(sugg_path.read_text(encoding="utf-8"))
                except Exception: sugg = None
            if sugg is None:
                try:
                    sugg = fetch_stage_suggestions(token, int(floor_id), type_ids)
                except urllib.error.HTTPError as e:
                    print(f"  [{done+1}/{total_stages}] {rname} :: {sname}  ERROR {e.code}",
                          file=sys.stderr)
                    done += 1
                    if e.code == 401:
                        print("  401 Unauthorized — token expired. Refresh and re-run.",
                              file=sys.stderr)
                        return 1
                    continue
                except Exception as e:
                    # Network blip, connection reset, etc — log + skip stage.
                    # The next run will retry it (file isn't created on error).
                    print(f"  [{done+1}/{total_stages}] {rname} :: {sname}  NET-ERR {type(e).__name__}: {e}",
                          file=sys.stderr)
                    done += 1
                    time.sleep(_jitter(delay) * 2)  # back off
                    continue
                out.mkdir(parents=True, exist_ok=True)
                sugg_path.write_text(json.dumps(sugg, indent=2), encoding="utf-8")
                time.sleep(_jitter(delay))

            # Damage-tier bosses: also pull giveUp=true variant
            if is_damage:
                dmg_path = out / "suggestions_dmg.json"
                if not dmg_path.exists() or args.force:
                    try:
                        body = {
                            "stageId": int(floor_id),
                            "minimumNumberOfBattles": 1, "winRate": 0,
                            "typeIds": type_ids,
                            "minimumBossDamage": None, "teamSetupId": None,
                            "autoOnly": False, "minimumNumberOfVictories": 0,
                            "lastBossDamage": False, "giveUp": True,
                            "requiredTypeIds": [], "soloTeams": False,
                        }
                        dmg = _request("POST", "/api/TeamSuggestion/suggestions", token, body=body)
                        out.mkdir(parents=True, exist_ok=True)
                        dmg_path.write_text(json.dumps(dmg, indent=2), encoding="utf-8")
                        # When drilling, prefer the damage-flavored list for boss stages
                        sugg = dmg
                    except urllib.error.HTTPError as e:
                        print(f"    [dmg variant] {rname} :: {sname}  ERROR {e.code}",
                              file=sys.stderr)
                    time.sleep(_jitter(delay))

            done += 1
            n = len(sugg) if isinstance(sugg, list) else 0
            extra = ""
            if args.drill and isinstance(sugg, list) and sugg:
                teams_n, det_n = _drill_stage(token, int(floor_id), sugg, out,
                                              args.top_teams, args.top_variations,
                                              delay, owned=owned, metric=metric)
                extra = f"  drilled +{teams_n}t/{det_n}d"
            print(f"  [{done}/{total_stages}] {rname} :: {sname}  -> {n} teams{extra}",
                  flush=True)
    print(f"done. results in {TEAMS_DIR}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--token", default=os.environ.get("HH_TOKEN"),
                   help="Bearer token (default: HH_TOKEN env var)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_r = sub.add_parser("regions", help="Fetch /api/Region catalog")

    def _add_drill(p):
        p.add_argument("--drill", action="store_true",
                       help="Also fetch /teams (variations) + /details (full builds) for top teams")
        p.add_argument("--top-teams", type=int, default=10,
                       help="When drilling, fetch variations for top N teams (default 10)")
        p.add_argument("--top-variations", type=int, default=3,
                       help="When drilling, fetch details for top N variations per team (default 3)")
        p.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                       help="Seconds to sleep between requests")

    sp_s = sub.add_parser("stage", help="Fetch suggestions for a single stage")
    sp_s.add_argument("--region", required=True, help="Region name substring (e.g. 'Iron Twins')")
    sp_s.add_argument("--stage", required=True, help="Stage name substring (e.g. 'Stage 15')")
    _add_drill(sp_s)

    sp_a = sub.add_parser("all", help="Harvest suggestions for every stage")
    sp_a.add_argument("--force", action="store_true",
                      help="Re-fetch even if file already exists")
    _add_drill(sp_a)

    args = p.parse_args()
    if not args.token:
        # Fallback: read from a local .hh_token file (gitignored).
        tok_path = PROJECT_ROOT / ".hh_token"
        if tok_path.exists():
            args.token = tok_path.read_text(encoding="utf-8").strip()
    if not args.token:
        print("ERROR: --token or HH_TOKEN env var required.\n"
              "Get it from https://raidoptimiser.hellhades.com after logging in:\n"
              "  open DevTools console -> localStorage.getItem('access_token')\n"
              "Or save the token to .hh_token at the project root.",
              file=sys.stderr)
        return 2

    handlers = {"regions": cmd_regions, "stage": cmd_stage, "all": cmd_all}
    return handlers[args.cmd](args, args.token) or 0


if __name__ == "__main__":
    raise SystemExit(main())
