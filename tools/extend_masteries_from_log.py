"""Extend `data/masteries_truth.json` with stat-bonus values mined from
a real battle tick log.

The mod's `/masteries-truth` endpoint walks `MasteryBonusById` which only
captures 13 of the actual stat-bonus masteries — missing entries like
500324 (ACC +20), 500333 (ACC +4), and others that DO show as `mods` on
each `BattleHero` at battle start. This script reads the first snapshot
of a tick log, takes every `mods[]` entry per player hero, and emits any
mastery_id we can ground-truth that's not already in masteries_truth.json.

Usage:
    python3 tools/extend_masteries_from_log.py --log battle_logs_cb_latest.json [--write]

Without --write, prints the additions that would be made. With --write,
updates `data/masteries_truth.json` in place.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Stat id (mod's `k` field) → human stat name used in masteries_truth.json
STAT_NAME_BY_K = {
    1: "Health",
    2: "Attack",
    3: "Defence",
    4: "Speed",
    5: "Resistance",
    6: "Accuracy",
    7: "CriticalChance",
    8: "CriticalDamage",
}


def mod_id_to_mastery_id(mod_id: int) -> int | None:
    """Mods on heroes have IDs like 5001121 — that's mastery 500112 with a
    suffix `1` (the bonus index within the mastery). Strip the trailing
    digit to get the mastery id when it's in the 500xxx range.

    Example: 5001121 → 500112 (mastery), 5003131 → 500313 (mastery).
    """
    if 5000000 <= mod_id < 5100000:
        return mod_id // 10
    return None


def extract_mods_from_log(log_path: Path) -> dict[int, list[dict]]:
    """Read first snapshot, return {mastery_id: [{stat_k, value}...]}.

    Heroes with the same mastery selected emit the same numeric bonus,
    so duplicates collapse. Different heroes may have different
    masteries → broader coverage.
    """
    with open(log_path) as f:
        data = json.load(f)
    log = data.get("log", [])
    sample = next(
        (e for e in log if isinstance(e, dict) and "heroes" in e and e.get("turn", -1) >= 2),
        None,
    )
    if not sample:
        return {}
    by_mastery: dict[int, list[dict]] = {}
    for h in sample["heroes"]:
        if h.get("side") != "player":
            continue
        for m in h.get("mods", []):
            mid_full = m.get("id", 0)
            mid = mod_id_to_mastery_id(mid_full)
            if mid is None:
                continue
            k = m.get("k")
            v = m.get("v", 0)
            if k is None or k == 0:
                continue
            stat = STAT_NAME_BY_K.get(k)
            if not stat:
                continue
            entry = {"stat": stat, "value": v, "absolute": True}
            existing = by_mastery.setdefault(mid, [])
            if entry not in existing:
                existing.append(entry)
    return by_mastery


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log", default="battle_logs_cb_latest.json")
    p.add_argument("--write", action="store_true",
                   help="Update masteries_truth.json with the additions")
    args = p.parse_args()

    truth_path = ROOT / "data" / "masteries_truth.json"
    truth = json.loads(truth_path.read_text())
    by_id = {m["id"]: m for m in truth.get("masteries", [])}

    additions = extract_mods_from_log(ROOT / args.log)
    new_entries = []
    for mid, bonuses in additions.items():
        existing = by_id.get(mid, {})
        if existing.get("stat_bonus"):
            continue  # already known
        # Only add masteries with non-zero v values (the v=0 ones are
        # percentage masteries whose bonus is in the BattleStats but
        # not the mods-list value).
        nonzero = [b for b in bonuses if b.get("value", 0) > 0]
        if not nonzero:
            continue
        # If multiple stat bonuses on one mastery, keep the first — the
        # rest are likely set bonuses or other artifacts of the mod.
        new_entries.append({"id": mid, "stat_bonus": nonzero[0]})

    if not new_entries:
        print("No new mastery stat-bonus values found in log.")
        return

    print(f"Found {len(new_entries)} masteries with stat bonuses missing from truth file:")
    for e in new_entries:
        print(f"  {e['id']}: {e['stat_bonus']}")

    if args.write:
        for e in new_entries:
            mid = e["id"]
            if mid in by_id:
                by_id[mid]["stat_bonus"] = e["stat_bonus"]
            else:
                truth["masteries"].append({"id": mid, **e})
        truth_path.write_text(json.dumps(truth, indent=2))
        print(f"\nUpdated {truth_path}")


if __name__ == "__main__":
    main()
