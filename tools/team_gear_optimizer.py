"""Team-wide multi-champion gear optimizer with cross-hero artifact locking (M6 #1b).

The single-champion `gear_target_optimizer.py` assigns the WHOLE vault to one
hero. In reality heroes on a team COMPETE for the same pieces — the SPD boot
that tunes Maneater is the same boot Demytha wants. This tool optimizes a whole
team at once under a shared-vault constraint: **each artifact goes to at most one
hero**, and the allocation maximizes total team value while honoring every
hero's hard minimums (HellHades-optimiser parity — its team optimizer does the
same contention resolution).

Algorithm — priority greedy + coordinate ascent:
  1. Order heroes by constraint tightness (most hard mins first) or a given
     `priority` list. Greedily assign each against the pool of still-free pieces.
  2. Re-optimization rounds: release one hero at a time, re-optimize it against
     the now-free pool, keep if its score improves. With the other heroes fixed,
     maximizing one hero's score maximizes the team total (coordinate ascent on
     sum-of-scores), so this provably converges to a local optimum and resolves
     contention — a piece ends up on whichever hero values it most.

Each hero's score already dominates-penalizes unmet minimums (see
`gear_target_optimizer.Optimizer.score`), so the allocator naturally prioritizes
satisfying everyone's hard floors before chasing importance-weighted value.

The vault includes pieces currently equipped on OTHER heroes, so the plan is a
set of cross-hero SWAPS (consistent with "equip-from-vault unreliable — swap
between heroes instead"). Locked slots keep a hero's current piece and reserve
it from the rest of the team.

Spec (`--spec team.json`):
  {
    "team": [
      {"hero": "Maneater", "mode": "survivability", "min": {"SPD": 288}, "lock": [7,8,9]},
      {"hero": "Demytha",  "min": {"SPD": 170, "ACC": 200}},
      {"hero": "Ninja",    "mode": "damage", "min": {"ACC": 225}},
      {"hero": "Geomancer","min": {"ACC": 250}},
      {"hero": "Venomage", "min": {"ACC": 200, "SPD": 180}}
    ],
    "priority": ["Maneater", "Geomancer", "Demytha", "Ninja", "Venomage"]
  }

Quick CLI (same mode for all, no per-hero mins):
  python3 tools/team_gear_optimizer.py --heroes "Maneater,Demytha,Ninja,Geomancer,Venomage" --mode balanced
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from gear_target_optimizer import (  # noqa: E402
    Optimizer, load_data, build_targets, parse_kv, MODE_WEIGHTS,
    STAT_NAME_TO_ID, STAT_ID_TO_NAME,
)
from cb_optimizer import HP, ATK, DEF, SPD, RES, ACC, CR, CD  # noqa: E402
from gear_constants import SLOT_NAMES  # noqa: E402


def _hard_min_count(targets):
    return sum(1 for t in targets.values() if t.get("min") is not None)


def _total_importance(targets):
    return sum((t.get("importance") or 0) for t in targets.values())


class TeamOptimizer:
    def __init__(self, opt: Optimizer):
        self.opt = opt

    def _assigned_ids(self, builds, exclude_hero=None):
        ids = set()
        for hero, res in builds.items():
            if hero == exclude_hero:
                continue
            for a in res["assignment"].values():
                if a:
                    ids.add(a["id"])
        return ids

    def optimize_team(self, specs, priority=None, anneal=25, rounds=3,
                      verbose=True):
        """specs: list of dicts {hero, targets, lock}. Returns
        {hero -> build_result} plus a 'team' summary."""
        by_name = {s["hero"]: s for s in specs}
        # Default priority: tightest constraints first (most hard mins, then
        # highest total importance). Honors an explicit priority list, with any
        # unlisted heroes appended by the default rule.
        default_order = sorted(
            specs,
            key=lambda s: (-_hard_min_count(s["targets"]),
                           -_total_importance(s["targets"]), s["hero"]),
        )
        order = []
        if priority:
            for name in priority:
                if name in by_name:
                    order.append(name)
        for s in default_order:
            if s["hero"] not in order:
                order.append(s["hero"])

        builds = {}
        # Phase 1 — greedy in priority order against the shrinking free pool.
        for name in order:
            spec = by_name[name]
            used = self._assigned_ids(builds)
            res = self.opt.optimize(name, spec["targets"], lock_slots=spec.get("lock"),
                                    anneal=anneal, exclude_ids=used)
            builds[name] = res
            if verbose:
                print(f"  [greedy] {name:14s} score={res['score']:8.1f} "
                      f"mins_met={res['mins_met']}")

        # Phase 2 — coordinate-ascent rounds. Releasing one hero and
        # re-optimizing against the rest maximizes total team score.
        for r in range(rounds):
            improved = False
            for name in order:
                spec = by_name[name]
                others = self._assigned_ids(builds, exclude_hero=name)
                res = self.opt.optimize(name, spec["targets"], lock_slots=spec.get("lock"),
                                        anneal=anneal, exclude_ids=others)
                if res["score"] > builds[name]["score"] + 1e-6:
                    builds[name] = res
                    improved = True
            if verbose:
                tot = sum(b["score"] for b in builds.values())
                met = sum(1 for b in builds.values() if b["mins_met"])
                print(f"  [round {r+1}] team_score={tot:8.1f}  mins_met={met}/{len(builds)}"
                      f"{'  (stable)' if not improved else ''}")
            if not improved:
                break

        # Sanity: with shared-vault, no artifact id should appear twice.
        all_ids = [a["id"] for b in builds.values()
                   for a in b["assignment"].values() if a]
        dupes = [i for i, c in Counter(all_ids).items() if c > 1]
        team = {
            "order": order,
            "total_score": sum(b["score"] for b in builds.values()),
            "mins_met": sum(1 for b in builds.values() if b["mins_met"]),
            "n_heroes": len(builds),
            "duplicate_artifact_ids": dupes,
        }
        return {"builds": builds, "team": team}


def specs_from_json(spec_path):
    data = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    out = []
    for row in data.get("team", []):
        mins = {STAT_NAME_TO_ID[k.upper()]: float(v)
                for k, v in (row.get("min") or {}).items()
                if k.upper() in STAT_NAME_TO_ID}
        maxs = {STAT_NAME_TO_ID[k.upper()]: float(v)
                for k, v in (row.get("max") or {}).items()
                if k.upper() in STAT_NAME_TO_ID}
        weights = {STAT_NAME_TO_ID[k.upper()]: float(v)
                   for k, v in (row.get("weight") or {}).items()
                   if k.upper() in STAT_NAME_TO_ID}
        targets = build_targets(mins, maxs, weights, row.get("mode"))
        out.append({"hero": row["hero"], "targets": targets,
                    "lock": set(row.get("lock") or [])})
    return out, data.get("priority")


def print_team(result):
    team = result["team"]
    print(f"\n=== Team gear plan ({team['n_heroes']} heroes) ===")
    print(f"  priority order : {' -> '.join(team['order'])}")
    print(f"  total score    : {team['total_score']:.1f}")
    print(f"  mins met       : {team['mins_met']}/{team['n_heroes']}")
    if team["duplicate_artifact_ids"]:
        print(f"  !! DUPLICATE artifact ids (bug): {team['duplicate_artifact_ids']}")
    else:
        print("  shared-vault   : OK (no artifact assigned to two heroes)")

    for hero, res in result["builds"].items():
        st = res["stats"]
        tgt = res["targets"]
        miss = []
        for sid, t in tgt.items():
            if t.get("min") is not None and st.get(sid, 0) < t["min"]:
                miss.append(f"{STAT_ID_TO_NAME[sid]}<{t['min']:.0f}")
        flag = "OK" if res["mins_met"] else "MISS: " + ",".join(miss)
        print(f"\n  --- {hero}  [{flag}] ---")
        line = "    "
        for sid in (HP, ATK, DEF, SPD, RES, ACC, CR, CD):
            line += f"{STAT_ID_TO_NAME[sid]}={st.get(sid,0):.0f}  "
        print(line)
        setc = Counter()
        pieces = []
        for s in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            a = res["assignment"].get(s)
            if not a:
                continue
            setc[a["set"]] += 1
            pieces.append(f"{SLOT_NAMES.get(s, s)}#{a['id']}")
        print(f"    sets={dict(setc)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", help="team spec JSON (per-hero min/max/weight/mode/lock)")
    ap.add_argument("--heroes", help="quick mode: comma-separated names (same --mode for all)")
    ap.add_argument("--mode", choices=list(MODE_WEIGHTS),
                    help="quick mode: importance preset applied to all --heroes")
    ap.add_argument("--min-rank", type=int, default=5)
    ap.add_argument("--anneal", type=int, default=25)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    if args.spec:
        specs, priority = specs_from_json(args.spec)
    elif args.heroes:
        priority = None
        mode = args.mode or "balanced"
        specs = [{"hero": h.strip(),
                  "targets": build_targets({}, {}, {}, mode),
                  "lock": set()}
                 for h in args.heroes.split(",") if h.strip()]
    else:
        ap.error("provide --spec or --heroes")

    arts, heroes, account = load_data()
    opt = Optimizer(arts, heroes, account, min_rank=args.min_rank)
    team_opt = TeamOptimizer(opt)
    result = team_opt.optimize_team(specs, priority=priority,
                                    anneal=args.anneal, rounds=args.rounds,
                                    verbose=not args.json)

    if args.json:
        out = {"team": result["team"], "builds": {}}
        for hero, res in result["builds"].items():
            out["builds"][hero] = {
                "mins_met": res["mins_met"],
                "score": res["score"],
                "stats": {STAT_ID_TO_NAME[k]: round(v, 1)
                          for k, v in res["stats"].items() if k in STAT_ID_TO_NAME},
                "assignment": {SLOT_NAMES.get(s, s): (a["id"] if a else None)
                               for s, a in res["assignment"].items()},
            }
        print(json.dumps(out, indent=2))
    else:
        print_team(result)


if __name__ == "__main__":
    main()
