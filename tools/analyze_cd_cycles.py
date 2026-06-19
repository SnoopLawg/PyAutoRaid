"""Analyze skill cooldown cycles from a battle log to identify CD reductions
that the sim isn't modeling.

Tracks each hero's skill `rdy` (IsReady) transitions across polls. From this
we can compute:
  - effective cd between casts (in their own turn count)
  - effective cd between casts (in ticks)
  - vs sim's expected cd given the skill's base cd

When effective cd < base cd, something is reducing it: Cycle of Magic procs,
ReduceCooldown effects from other skills, etc. Counting these gives us a
direct measure of un-modeled mechanics.

Usage:
    python3 tools/analyze_cd_cycles.py battle_logs_cb_20260619_082925.json
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log_file")
    args = ap.parse_args()

    d = json.loads(Path(args.log_file).read_text(encoding="utf-8"))
    log = d.get("log") or []

    # Per-hero per-skill timeline:
    #   {hero_id: {skill_type_id: [(poll, turn_n, was_ready, became_ready_now,
    #                                cast_now)]}}
    # We track:
    #   - poll : poll counter
    #   - turn_n: hero's own turn counter at this poll
    #   - was_ready: rdy state at this poll
    #   - became_ready_now: rdy was False last poll, True now (CD wore off)
    #   - cast_now: rdy was True last poll, False now (skill cast)

    prev_states: dict[int, dict[int, bool]] = defaultdict(dict)
    prev_turn_n: dict[int, int] = defaultdict(int)

    # CD events: when did each skill come off cd, and when was it cast
    events: list[dict] = []

    for entry in log:
        if not isinstance(entry, dict):
            continue
        heroes = entry.get("heroes") or []
        poll = entry.get("poll", 0)
        for h in heroes:
            if h.get("side") not in ("player", "p"):
                continue
            hid = h.get("id")
            tn = h.get("turn_n", 0)
            sk_list = h.get("sk") or []
            for sk in sk_list:
                sid = sk.get("t")
                rdy = sk.get("rdy", True)
                prev_rdy = prev_states[hid].get(sid, True)
                if prev_rdy != rdy:
                    # Transition
                    event_type = "ready_now" if rdy else "cast_now"
                    events.append({
                        "poll": poll,
                        "hero_id": hid,
                        "tn": tn,
                        "skill_id": sid,
                        "transition": event_type,
                    })
                prev_states[hid][sid] = rdy
            prev_turn_n[hid] = tn

    # Per-hero per-skill: count cast events and ready events; compute deltas
    # between consecutive casts.
    casts_by_hs: dict[tuple, list[dict]] = defaultdict(list)
    readies_by_hs: dict[tuple, list[dict]] = defaultdict(list)
    for e in events:
        key = (e["hero_id"], e["skill_id"])
        if e["transition"] == "cast_now":
            casts_by_hs[key].append(e)
        else:
            readies_by_hs[key].append(e)

    # Hero name lookup (from skills_db / heroes_all)
    project_root = Path(__file__).resolve().parent.parent
    heroes_all = json.loads(
        (project_root / "heroes_all.json").read_text(encoding="utf-8"))
    skills_db = json.loads(
        (project_root / "skills_db.json").read_text(encoding="utf-8"))
    skill_to_name: dict[int, tuple[str, str, int]] = {}  # sid -> (hero, name, cd)
    for hero_name, sk_list in skills_db.items():
        if not isinstance(sk_list, list):
            continue
        for sk in sk_list:
            if isinstance(sk, dict):
                sid = sk.get("skill_type_id")
                if sid:
                    skill_to_name[sid] = (
                        hero_name, sk.get("name", "?"),
                        sk.get("cooldown", 0) or 0)

    print(f"Analyzed {len(events)} skill rdy-transitions")
    print()
    # Per skill: list cast intervals
    for key in sorted(casts_by_hs.keys()):
        hid, sid = key
        casts = casts_by_hs[key]
        if len(casts) < 2:
            continue
        hero, sname, base_cd = skill_to_name.get(sid, ("?", f"sid_{sid}", 0))
        # Deltas in turn_n (cast-to-cast)
        tn_deltas = [casts[i + 1]["tn"] - casts[i]["tn"]
                     for i in range(len(casts) - 1)]
        # Deltas in poll
        poll_deltas = [casts[i + 1]["poll"] - casts[i]["poll"]
                       for i in range(len(casts) - 1)]
        mean_tn = sum(tn_deltas) / len(tn_deltas)
        mean_poll = sum(poll_deltas) / len(poll_deltas)
        # Cast-to-cast turn delta IS the effective cooldown
        # (after casting, skill takes N turns to come back).
        effective_cd = mean_tn
        booked_cd = max(0, base_cd - 2)  # Assume fully booked
        delta = effective_cd - booked_cd
        ticks_per_turn = mean_poll / max(mean_tn, 1)
        print(f"  hero{hid} {hero:15s} {sname:25s} (sid={sid}, base_cd={base_cd}, booked={booked_cd}):")
        print(f"    casts: {len(casts)}  mean dturn_n: {mean_tn:.2f}  mean dpoll: {mean_poll:.1f}")
        print(f"    effective cycle: {effective_cd:.2f} hero-turns  ({ticks_per_turn:.2f} ticks/turn)  [{'+' if delta>0 else ''}{delta:.2f} vs booked]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
