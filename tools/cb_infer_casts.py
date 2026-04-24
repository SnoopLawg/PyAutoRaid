#!/usr/bin/env python3
"""Infer per-hero skill cast sequence from /battle-log sk.rdy transitions.

Workaround for the ApplySkillCommand Harmony hook not firing: each poll
captures every hero's sk list with rdy state. When sk[X].rdy flips True→False
between two polls, hero just cast skill X. A1 has no CD (rdy stays True)
so A1 casts are inferred from turn_n increments WITHOUT a matching A2/A3
transition.

Usage:
    python3 tools/cb_infer_casts.py battle_logs_cb_*.json
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

NAME_BY_TYPE = {
    1070: "Maneater", 6510: "Demytha", 6200: "Ninja",
    4880: "Geomancer", 6280: "Venomage",
    22270: "Boss",
}

# Skill suffix: type_id = hero_type × 100 + slot (e.g. 10701 = Maneater A1)
def skill_slot(skill_type_id):
    """Return (hero_type_id, slot) where slot in {1,2,3,4}."""
    slot = skill_type_id % 10
    hero = skill_type_id // 100
    return hero, slot


def infer(log_path):
    data = json.loads(Path(log_path).read_text())
    entries = data.get("log", [])

    casts = []   # (bt, hero_name, slot, skill_id)

    prev_rdy = defaultdict(dict)   # hero_uid → {skill_type_id: bool}
    prev_tn = defaultdict(int)     # hero_uid → turn_n
    last_boss_tn = 0

    for e in entries:
        if not isinstance(e, dict):
            continue
        heroes = e.get("heroes") or []
        if not heroes:
            continue
        boss = next((h for h in heroes if h.get("side") == "enemy"), None)
        if boss:
            bt = boss.get("turn_n", 0) or 0
            if bt > last_boss_tn:
                last_boss_tn = bt

        for h in heroes:
            side = h.get("side")
            type_id = h.get("type_id", 0)
            if side == "player":
                uid = h.get("id") or type_id
            else:
                uid = h.get("id") or type_id
            name = NAME_BY_TYPE.get(type_id, f"type{type_id}")
            tn = h.get("turn_n", 0) or 0
            skills = h.get("sk") or []

            prev_rdy_for_hero = prev_rdy.get(uid, {})
            prev_tn_for_hero = prev_tn.get(uid, 0)

            # Detect CD-skill casts (rdy True→False)
            cd_cast_this_poll = None
            for s in skills:
                sid = s.get("t")
                rdy_now = s.get("rdy", True)
                rdy_before = prev_rdy_for_hero.get(sid)
                if rdy_before is True and rdy_now is False:
                    _, slot = skill_slot(sid)
                    cd_cast_this_poll = (sid, slot)

            # If turn_n incremented, a skill was cast
            if tn > prev_tn_for_hero:
                if cd_cast_this_poll:
                    sid, slot = cd_cast_this_poll
                else:
                    # No CD-skill transition → must be A1 (no CD)
                    a1_sid = next((s.get("t") for s in skills if s.get("t", 0) % 10 == 1), None)
                    slot = 1
                    sid = a1_sid
                casts.append((last_boss_tn, name, slot, sid))

            prev_tn[uid] = tn
            prev_rdy[uid] = {s.get("t"): s.get("rdy", True) for s in skills}

    return casts


def summarize(casts):
    print(f"Total casts detected: {len(casts)}")
    print()
    # Per-hero per-BT
    by_hero_bt = defaultdict(lambda: defaultdict(list))
    for bt, name, slot, sid in casts:
        by_hero_bt[name][bt].append(f"A{slot}")

    heroes = sorted(by_hero_bt)
    max_bt = max((bt for bt, _, _, _ in casts), default=0)
    print(f"{'BT':>3}  " + "  ".join(f"{h[:9]:<9}" for h in heroes))
    print("-" * (5 + 11 * len(heroes)))
    for bt in range(0, min(max_bt + 1, 25)):
        row = [f"{bt:>3}"]
        for h in heroes:
            cs = by_hero_bt[h].get(bt, [])
            cell = ",".join(cs) if cs else "-"
            row.append(f"{cell:<9}")
        print("  ".join(row))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("log")
    args = p.parse_args()
    casts = infer(args.log)
    summarize(casts)


if __name__ == "__main__":
    main()
