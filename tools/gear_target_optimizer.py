"""Generalized per-champion gear optimizer with stat targets (M6 #1).

HellHades-parity flagship: given a hero + per-stat targets (min / max /
importance), assign artifacts from the user's vault to a build that satisfies
the minimums, respects the maximums, and maximizes an importance-weighted
score — for ANY champion and ANY location, not just CB.

Distinct from `tools/gear_optimizer.py` (a CB-team, sim-scored optimizer with
hardcoded speed ranges). This one is location-agnostic, single-champion,
target-driven, and calibration-independent — it does NOT use the damage sim
(that's the separate "Damage mode" gap, M6 #2). It uses the canonical
`cb_optimizer.calc_stats` as the stat oracle so set bonuses, Lore-of-Steel,
masteries, blessings, and the game's column model stay consistent.

Modes (HH parity) set default importance weights when you don't specify:
    balanced     — ACC, SPD, survivability
    damage       — ATK, C.RATE, C.DMG, SPD
    survivability— HP, DEF, RES, SPD

CLI:
    python3 tools/gear_target_optimizer.py --hero Venomage --min "ACC=225,SPD=180" --weight "CD=3,ATK=2"
    python3 tools/gear_target_optimizer.py --hero Geomancer --mode damage --min "ACC=370"
    python3 tools/gear_target_optimizer.py --hero Demytha --mode survivability --min "SPD=170"
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from cb_optimizer import calc_stats, HP, ATK, DEF, SPD, RES, ACC, CR, CD  # noqa: E402
from gear_constants import ACCESSORY_SLOTS, SLOT_NAMES  # noqa: E402

STAT_NAME_TO_ID = {"HP": HP, "ATK": ATK, "DEF": DEF, "SPD": SPD,
                   "RES": RES, "ACC": ACC, "CR": CR, "CD": CD}
STAT_ID_TO_NAME = {v: k for k, v in STAT_NAME_TO_ID.items()}
# Per-stat scale to normalize importance-weighted contributions (≈ a strong total).
STAT_SCALE = {HP: 60000, ATK: 5000, DEF: 4000, SPD: 250, RES: 300,
              ACC: 400, CR: 100, CD: 300}

MODE_WEIGHTS = {
    "balanced":      {ACC: 2, SPD: 2, HP: 1, DEF: 1},
    "damage":        {ATK: 3, CR: 3, CD: 3, SPD: 2},
    "survivability": {HP: 3, DEF: 3, RES: 1, SPD: 2},
}


SET_STAT_NAME = {"Health": HP, "Attack": ATK, "Defence": DEF, "Speed": SPD,
                 "Resistance": RES, "Accuracy": ACC, "CriticalChance": CR,
                 "CriticalDamage": CD}


def _load(name):
    with (ROOT / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def load_set_stat_map():
    """set_id -> (stat_id, pieces_needed) for stat-bonus sets. Used to seed
    set-aware builds (single-slot hill-climb can't discover a 2/4-piece set
    threshold on its own — the bonus is non-linear)."""
    af = json.loads((ROOT / "data" / "static" / "artifact_sets.json").read_text(encoding="utf-8"))
    rows = next((v for k, v in af.items() if k != "_meta" and isinstance(v, list)), [])
    out = {}
    for r in rows:
        sb = r.get("stat_bonus") or {}
        sid = SET_STAT_NAME.get(sb.get("stat"))
        if sid is not None:
            out[r["id"]] = (sid, r.get("pieces", 2))
    return out


def load_data():
    arts = _load("all_artifacts.json")
    arts = arts.get("artifacts", arts) if isinstance(arts, dict) else arts
    heroes = _load("heroes_all.json")
    heroes = heroes.get("heroes", heroes) if isinstance(heroes, dict) else heroes
    account = _load("account_data.json")
    return arts, heroes, account


class Optimizer:
    def __init__(self, artifacts, heroes, account, min_rank=5):
        self.account = account
        self.set_stat = load_set_stat_map()
        self.heroes_by_name = {}
        for h in heroes:
            self.heroes_by_name.setdefault(h["name"].lower(), h)
        self.by_slot = {}
        for a in artifacts:
            if a.get("rank", 0) < min_rank:
                continue
            self.by_slot.setdefault(a["kind"], []).append(a)
        self._acc_faction = {}
        for h in heroes:
            frac = h.get("fraction", 0)
            for a in h.get("artifacts", []):
                if a.get("kind") in ACCESSORY_SLOTS and a.get("id"):
                    self._acc_faction[a["id"]] = frac

    def candidates(self, slot, hero_fraction, exclude_ids=None):
        arts = self.by_slot.get(slot, [])
        if exclude_ids:
            arts = [a for a in arts if a.get("id") not in exclude_ids]
        if slot in ACCESSORY_SLOTS:
            return [a for a in arts
                    if self._acc_faction.get(a["id"], hero_fraction) == hero_fraction]
        return arts

    def score(self, stats, targets):
        """Lexicographic-ish: unmet minimums dominate everything (huge penalty
        scaled by how far short), so the search always satisfies mins before
        chasing importance-weighted value. Maximums are a hard-ish penalty;
        importance is the soft objective once mins/maxes are satisfied."""
        s = 0.0
        met_all_mins = True
        for sid, t in targets.items():
            val = stats.get(sid, 0)
            imp = t.get("importance", 0) or 0
            mn, mx = t.get("min"), t.get("max")
            if mn is not None and val < mn:
                deficit = (mn - val) / max(1.0, STAT_SCALE[sid])
                # Dominant: must exceed any plausible importance reward so mins
                # are met first. (importance reward is O(100) per stat.)
                s -= (50000 + 5000 * imp) * deficit
                met_all_mins = False
            if mx is not None and val > mx:
                excess = (val - mx) / max(1.0, STAT_SCALE[sid])
                s -= 20000 * excess
            if imp:
                s += imp * (val / STAT_SCALE[sid]) * 100
        return s, met_all_mins

    def _stats_for(self, hero, assignment):
        arts = [a for a in assignment.values() if a is not None]
        # hypothetical=True: actually evaluate the PROPOSED gear. Without it
        # calc_stats returns the hero's CURRENT equipped stats for any input
        # (it copies the mod's artifact_bonus column), so the search is a no-op.
        return calc_stats(hero, arts, self.account, hypothetical=True)

    def _proxy(self, art, targets):
        score = 0.0
        for b in [art.get("primary")] + (art.get("substats") or []):
            if not b:
                continue
            sid, val = b.get("stat", 0), b.get("value", 0)
            t = targets.get(sid)
            if t:
                w = (t.get("importance", 0) or 0) + (2 if t.get("min") else 0)
                score += w * (val / max(1.0, STAT_SCALE.get(sid, 1)))
        return score

    def _set_bonus_reward(self, assignment, require_sets):
        if not require_sets:
            return 0.0
        counts = Counter(a["set"] for a in assignment.values() if a)
        reward = 0.0
        for set_id, need in require_sets.items():
            have = counts.get(set_id, 0)
            reward += min(have, need) / need * 300.0
            if have < need:
                reward -= (need - have) * 150.0
        return reward

    def optimize(self, hero_name, targets, require_sets=None, lock_slots=None,
                 anneal=8, slots=(1, 2, 3, 4, 5, 6, 7, 8, 9), seed=0,
                 exclude_ids=None, slot_primary=None):
        hero = self.heroes_by_name.get(hero_name.lower())
        if not hero:
            raise ValueError(f"hero '{hero_name}' not found")
        frac = hero.get("fraction", 0)
        rng = random.Random(seed)
        equipped = {a.get("kind"): a for a in hero.get("artifacts", [])}
        lock_slots = set(lock_slots or [])
        # exclude_ids = pieces claimed by OTHER heroes (team mode). A hero's own
        # locked/equipped pieces are never in its own exclude set, so locking
        # still works. The hero only sees free vault pieces for unlocked slots.
        cand = {s: self.candidates(s, frac, exclude_ids) for s in slots}
        # slot_primary = {slot_id: stat_id} — require that slot's main stat be a
        # specific primary (e.g. Ring=CD, Banner=ACC). Restricts candidates to
        # matching pieces; an empty result is honest (no such piece in vault)
        # and the slot falls back to the equipped piece below.
        slot_primary = slot_primary or {}
        for s, want in slot_primary.items():
            if s in lock_slots or s not in cand:
                continue
            cand[s] = [a for a in cand[s]
                       if (a.get("primary") or {}).get("stat") == want]

        assignment = {}
        for s in slots:
            if s in lock_slots and s in equipped:
                assignment[s] = equipped[s]
            elif cand[s]:
                assignment[s] = max(cand[s], key=lambda a: self._proxy(a, targets))
            else:
                assignment[s] = equipped.get(s)

        def total_score(assign):
            sc, _ = self.score(self._stats_for(hero, assign), targets)
            return sc + self._set_bonus_reward(assign, require_sets)

        def hill_climb(assign):
            score = total_score(assign)
            improved = True
            while improved:
                improved = False
                for s in slots:
                    if s in lock_slots or not cand[s]:
                        continue
                    cur, best_a, best_sc = assign.get(s), assign.get(s), score
                    for a in cand[s]:
                        if a is cur:
                            continue
                        assign[s] = a
                        sc = total_score(assign)
                        if sc > best_sc + 1e-9:
                            best_sc, best_a = sc, a
                    assign[s] = best_a
                    if best_a is not cur:
                        score, improved = best_sc, True
            return assign, score

        assignment, best = hill_climb(assignment)

        # Set-aware seeds: single-slot hill-climb can't discover a 2/4-piece
        # set threshold (the bonus is non-linear). For each set whose stat the
        # targets care about (min or importance), seed a build that force-fills
        # `pieces` slots with that set, fill the rest greedily, then hill-climb.
        wanted_stats = {sid for sid, t in targets.items()
                        if t.get("min") is not None or (t.get("importance") or 0) > 0}
        gear_slots = [s for s in slots if s not in ACCESSORY_SLOTS and s not in lock_slots]
        useful_sets = sorted({set_id for set_id, (st, _) in self.set_stat.items()
                              if st in wanted_stats})
        for set_id in useful_sets:
            st, need = self.set_stat[set_id]
            # Best piece of this set per gear slot, ranked by proxy value.
            slot_pieces = {}
            for s in gear_slots:
                pieces = [a for a in cand[s] if a.get("set") == set_id]
                if pieces:
                    # for the set's own stat, prefer the highest contributor
                    slot_pieces[s] = max(pieces, key=lambda a: self._proxy(a, targets))
            if len(slot_pieces) < need:
                continue
            ranked = sorted(slot_pieces, key=lambda s: self._proxy(slot_pieces[s], targets),
                            reverse=True)
            # 2-piece sets STACK (e.g. 6 Speed pieces = 3 Speed sets = +36%).
            # Seed at every multiple of `need` from the threshold up to the
            # max available, so the search sees both a light touch and a full
            # stack of the set. (Single-slot hill-climb can't build a stack on
            # its own.) Try maximal fill first.
            fill_levels = [n for n in range(len(ranked), need - 1, -need)] or [need]
            for k in fill_levels:
                seed = dict(assignment)
                for s in ranked[:k]:
                    seed[s] = slot_pieces[s]
                seed, sc = hill_climb(seed)
                if sc > best:
                    assignment, best = seed, sc

        for _ in range(anneal):
            trial = dict(assignment)
            for s in slots:
                if s in lock_slots or not cand[s]:
                    continue
                if rng.random() < 0.4:
                    trial[s] = rng.choice(cand[s])
            trial, sc = hill_climb(trial)
            if sc > best:
                assignment, best = trial, sc

        stats = self._stats_for(hero, assignment)
        _, met = self.score(stats, targets)
        return {"hero": hero["name"], "assignment": assignment, "stats": stats,
                "score": best, "targets": targets, "mins_met": met}


def parse_kv(s, cast=float):
    out = {}
    for part in (s or "").split(","):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        sid = STAT_NAME_TO_ID.get(k.strip().upper())
        if sid is not None:
            out[sid] = cast(v)
    return out


# Slot-name aliases accepted in --primary (in addition to numeric slot ids).
SLOT_ALIASES = {"HELMET": 1, "HELM": 1, "CHEST": 2, "GLOVES": 3, "BOOTS": 4,
                "WEAPON": 5, "SHIELD": 6, "RING": 7, "AMULET": 8, "CLOAK": 8,
                "BANNER": 9}


def parse_slot_primary(s):
    """'7=CD,9=ACC' or 'Ring=CD,Banner=ACC' -> {slot_id: stat_id}."""
    out = {}
    for part in (s or "").split(","):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip().upper()
        slot = int(k) if k.isdigit() else SLOT_ALIASES.get(k)
        sid = STAT_NAME_TO_ID.get(v.strip().upper())
        if slot is not None and sid is not None:
            out[slot] = sid
    return out


def build_targets(mins, maxs, weights, mode):
    targets = {}
    if mode and mode in MODE_WEIGHTS:
        for sid, w in MODE_WEIGHTS[mode].items():
            targets.setdefault(sid, {})["importance"] = w
    for sid, v in mins.items():
        targets.setdefault(sid, {})["min"] = v
    for sid, v in maxs.items():
        targets.setdefault(sid, {})["max"] = v
    for sid, v in weights.items():
        targets.setdefault(sid, {})["importance"] = v
    return targets


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hero", required=True)
    ap.add_argument("--min", default="", help="min stats, e.g. 'ACC=225,SPD=180'")
    ap.add_argument("--max", default="", help="max stats, e.g. 'SPD=250'")
    ap.add_argument("--weight", default="", help="importance, e.g. 'CD=3,ATK=2'")
    ap.add_argument("--mode", choices=list(MODE_WEIGHTS))
    ap.add_argument("--min-rank", type=int, default=5)
    ap.add_argument("--anneal", type=int, default=8)
    ap.add_argument("--lock", default="", help="slots to keep current piece, e.g. '7,8,9'")
    ap.add_argument("--primary", default="",
                    help="require slot primaries, e.g. 'Ring=CD,Banner=ACC' or '7=CD,9=ACC'")
    args = ap.parse_args()

    targets = build_targets(parse_kv(args.min), parse_kv(args.max),
                            parse_kv(args.weight), args.mode)
    if not targets:
        print("No targets. Use --min / --weight / --mode.")
        return
    lock = {int(x) for x in args.lock.split(",") if x.strip().isdigit()}
    slot_primary = parse_slot_primary(args.primary)

    arts, heroes, account = load_data()
    opt = Optimizer(arts, heroes, account, min_rank=args.min_rank)
    res = opt.optimize(args.hero, targets, lock_slots=lock, anneal=args.anneal,
                       slot_primary=slot_primary)

    print(f"=== Optimized build for {res['hero']} ===")
    print(f"  mode={args.mode or '(custom)'}  mins_met={res['mins_met']}  score={res['score']:.1f}\n")
    print("  Resulting stats:")
    st = res["stats"]
    for sid in (HP, ATK, DEF, SPD, RES, ACC, CR, CD):
        val = st.get(sid, 0)
        t = targets.get(sid, {})
        flags = []
        if t.get("min") is not None:
            flags.append("OK" if val >= t["min"] else f"MISS (need {t['min']:.0f})")
        if t.get("max") is not None and val > t["max"]:
            flags.append(f"OVER {t['max']:.0f}")
        fl = ("  [" + ", ".join(flags) + "]") if flags else ""
        print(f"    {STAT_ID_TO_NAME[sid]:4s} {val:8.1f}{fl}")
    print("\n  Build (slot -> set, primary):")
    setc = Counter()
    for s in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        a = res["assignment"].get(s)
        if not a:
            continue
        setc[a["set"]] += 1
        pn = STAT_ID_TO_NAME.get(a.get("primary", {}).get("stat"), "?")
        print(f"    {SLOT_NAMES.get(s, s):8s}: set#{a['set']:>3} primary={pn} (art {a['id']})")
    print(f"  Sets: {dict(setc)}")


if __name__ == "__main__":
    main()
