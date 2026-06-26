"""Real CB battle replay — turn-by-turn from a captured battle log.

Segments a `battle_logs_cb_*.json` poll stream into per-action rows (one per
hero/boss turn) in the SAME shape the dashboard's turn-meter grid renders
(`tm_grid`): per-row actor + skill + damage + active effects, plus every unit's
turn meter for the hover tooltip.

Data sources:
- battle log polls: per-unit `turn_n` (segments turns), `tm`, `sk`, `eff`, and
  the boss's cumulative `dmg_taken` (damage is the delta attributed to the
  acting hero).
- effects: each `eff` entry's `t` is the canonical StatusEffectTypeId (emitted
  by the mod) which maps via effects.json to a KindId == our effect icon name +
  a StatusBuff/StatusDebuff category. Old logs without `t` simply show no
  effect icons (damage + turn order still work).

CLI: python3 tools/cb_replay.py <battle_logs_cb_*.json>
"""
from __future__ import annotations

import json
import re
from pathlib import Path

BOSS_NAME = "Demon Lord"
_PROTECTIVE = {"Unkillable", "BlockDamage", "Shield"}
_NICE = {
    "Unkillable": "Unkillable", "BlockDamage": "Block Damage", "Shield": "Shield",
    "ContinuousHeal": "Heal/turn", "ContinuousDamage": "Poison",
    "AoEContinuousDamage": "HP Burn", "IncreaseDamageTaken": "Weaken",
    "StatusReduceDefence": "Dec DEF", "StatusReduceAttack": "Dec ATK",
    "StatusReduceSpeed": "Dec SPD", "StatusReduceAccuracy": "Dec ACC",
    "StatusIncreaseAttack": "Inc ATK", "StatusIncreaseDefence": "Inc DEF",
    "StatusIncreaseSpeed": "Inc SPD", "StatusIncreaseCriticalDamage": "Inc C.DMG",
    "StatusIncreaseCriticalChance": "Inc C.RATE", "StatusIncreaseAccuracy": "Inc ACC",
    "BlockDebuff": "Block Debuffs", "BlockBuffs": "Block Buffs",
    "BlockHeal": "Heal Reduc.", "Stun": "Stun", "Freeze": "Freeze",
    "Sleep": "Sleep", "Provoke": "Provoke", "Taunt": "Taunt",
    "StatusCounterattack": "Counter", "ReflectDamage": "Reflect Dmg",
    "Shield2": "Shield", "ContinuousHeal2": "Heal/turn",
}


def _humanize(kind_id: str) -> str:
    if kind_id in _NICE:
        return _NICE[kind_id]
    return re.sub(r"(?<!^)(?=[A-Z])", " ", kind_id).replace("Status ", "")


def effect_meta(root: Path) -> dict:
    """EffectTypeId -> {icon, label, kind} from effects.json. kind is def
    (protective buff), buff, or debuff."""
    try:
        data = json.loads((root / "data" / "static" / "effects.json").read_text())["data"]
    except Exception:
        return {}
    out: dict = {}
    for r in data:
        if not isinstance(r, dict) or "Id" not in r:
            continue
        kid = r.get("KindId")
        if not kid:
            continue
        cat = r.get("Category")
        if kid in _PROTECTIVE:
            kind = "def"
        elif cat == "StatusDebuff":
            kind = "debuff"
        elif cat == "StatusBuff":
            kind = "buff"
        else:
            continue
        out[r["Id"]] = {"icon": kid, "label": _humanize(kid), "kind": kind}
    return out


def _decode_eff(eff, emeta) -> list:
    """Decode a unit's `eff` array into [{icon,label,kind,state,rem}] (deduped by
    effect type). Entries without the mod's `t` (old logs) are skipped."""
    out, seen = [], set()
    for ph in (eff or []):
        for e in (ph.get("e") or []):
            t = e.get("t")
            if t is None or t in seen:
                continue
            m = emeta.get(t)
            if not m:
                continue
            seen.add(t)
            out.append({"icon": m["icon"], "label": m["label"], "kind": m["kind"],
                        "state": "held", "rem": int(e.get("d") or 0)})
    return out


def _tick_overlay(root: Path, ts: str) -> dict | None:
    """From the matching tick_log_cb_<ts>.json, build each hero slot's ordered
    per-action damage to the boss (their own hit + their own DoT/effect damage
    accumulated since their last action) and the skill they cast. Damage is
    attributed by the event's `producer` — so a poison/burn tick is credited to
    the champion who applied it, never to whoever's turn it landed on."""
    p = root / f"tick_log_cb_{ts}.json"
    if not p.exists():
        return None
    try:
        ticks = json.loads(p.read_text()).get("ticks", [])
    except Exception:
        return None
    from collections import defaultdict
    BOSS_SLOT = 5
    # Key by NORMALISED type id (type_id // 10 drops the ascension digit), since
    # the battle log's hero order differs from the tick log's slot order.
    hit_by_tick: dict = defaultdict(lambda: defaultdict(int))
    dot_by_tick: dict = defaultdict(lambda: defaultdict(int))
    hit_ticks: dict = defaultdict(set)
    slot_to_nt: dict = {}
    max_tick = 0
    for e in ticks:
        if not isinstance(e, dict):
            continue
        tk = e.get("tick") or 0
        max_tick = max(max_tick, tk)
        if e.get("kind") == "damage" and e.get("target") == BOSS_SLOT:
            pr, d, pt = e.get("producer"), int(e.get("dealt") or 0), e.get("p_typeid")
            if pr is None or pr == BOSS_SLOT or pt is None:
                continue
            nt = int(pt) // 10
            slot_to_nt[pr] = nt
            if e.get("kind_id") == 6000:
                hit_by_tick[tk][nt] += d
                hit_ticks[nt].add(tk)
            else:
                dot_by_tick[tk][nt] += d
    casts: dict = defaultdict(list)
    for e in ticks:
        if isinstance(e, dict) and e.get("kind") == "cast":
            sl = e.get("producer_id")
            nt = slot_to_nt.get(sl)
            if nt is not None:
                casts[nt].append((e.get("tick"), e.get("skill_type_id")))

    out_dmg, out_skill = {}, {}
    for nt in set(list(casts) + list(hit_ticks)):
        # One entry per TURN (cast). Each turn absorbs ALL of this champion's
        # boss damage — multi-hits, counters AND DoT ticks — since their last
        # turn; the final turn also absorbs DoT that keeps ticking afterwards.
        cast_list = sorted(casts.get(nt, []), key=lambda x: x[0])
        if not cast_list:                       # damage but no cast (rare): one bucket
            cast_list = [(min(hit_ticks[nt]), None)]
        dmgs, sks, prev = [], [], -1
        for i, (T, st) in enumerate(cast_list):
            end = max_tick if i == len(cast_list) - 1 else T
            tot = sum(hit_by_tick[tk].get(nt, 0) + dot_by_tick[tk].get(nt, 0)
                      for tk in range(prev + 1, end + 1))
            dmgs.append(tot)
            sks.append("A" + str(int(st) % 10) if st else None)
            prev = T
        out_dmg[nt] = dmgs
        out_skill[nt] = sks
    return {"dmg": out_dmg, "skill": out_skill}


def _skill_alias(h, prev_sk, is_boss) -> str:
    if is_boss:
        bt = int(h.get("turn_n") or 0)
        return ["AOE1", "AOE2", "STUN"][(bt - 1) % 3] if bt > 0 else "AOE1"
    sk = h.get("sk") or []
    prev = {s.get("t"): s for s in (prev_sk or [])}
    used = None
    for s in sk:
        t = s.get("t")
        ps = prev.get(t)
        if ps is not None and ps.get("rdy") and not s.get("rdy"):
            used = t            # this cooldown skill just fired
    if used is not None:
        return "A" + str(int(used) % 10)
    return "A1"


def build_replay(root: Path, log_path: Path, name_map: dict | None = None,
                 max_rows: int = 600) -> dict:
    """Parse one battle log into a tm_grid-shaped replay."""
    name_map = name_map or {}
    try:
        d = json.loads(Path(log_path).read_text())
    except Exception as e:
        return {"error": f"cannot read {log_path}: {e}"}
    log = d.get("log", []) if isinstance(d, dict) else []
    if not log:
        return {"error": "empty battle log (no polls)"}
    emeta = effect_meta(root)

    # Columns = player heroes in slot order (from the first heroes poll) + boss.
    columns, type_ids, id_to_name = [], {}, {}
    for entry in log:
        players = [h for h in (entry.get("heroes") or []) if h.get("side") == "player"]
        if players:
            for h in players:
                nm = name_map.get(h.get("type_id"), f"#{h.get('type_id')}")
                if nm not in columns:
                    columns.append(nm)
                type_ids[nm] = h.get("type_id")
                id_to_name[h.get("id")] = nm
            break
    columns.append(BOSS_NAME)

    # Accurate per-hero damage from the matching tick log (attributed by the
    # damage event's producer). Falls back to boss-HP deltas if absent.
    m = re.search(r"battle_logs_cb_(\d{8}_\d{6})", Path(log_path).name)
    overlay = _tick_overlay(root, m.group(1)) if m else None
    action_idx: dict = {}

    last_tn, last_rdy, pending = {}, {}, {}
    boss_prev_dmg = 0
    cur_boss_turn = 0
    rows: list = []

    for entry in log:
        hs = entry.get("heroes")
        if not hs:
            continue
        boss = next((h for h in hs if h.get("side") == "enemy"), None)
        if boss:
            cur_boss_turn = int(boss.get("turn_n") or cur_boss_turn)
        boss_dmg = int((boss.get("dmg_taken") if boss else 0) or boss_prev_dmg)

        for h in hs:
            uid = h.get("id")
            tn = int(h.get("turn_n") or 0)
            if uid is None:
                continue
            # A cooldown skill flipping ready->not-ready means it was just cast;
            # this is captured a poll BEFORE turn_n increments, so stash it and
            # attribute it to the next action by this unit (A1 has no cooldown).
            # At first sight, a cooldown skill already on cooldown = the opener.
            cur_rdy = {int(s.get("t")): bool(s.get("rdy")) for s in (h.get("sk") or []) if s.get("t") is not None}
            prev_rdy = last_rdy.get(uid)
            first_seen = prev_rdy is None
            for t, rdy in cur_rdy.items():
                if (int(t) % 10) == 1:
                    continue
                if first_seen and not rdy:
                    pending[uid] = "A" + str(int(t) % 10)
                elif prev_rdy and prev_rdy.get(t) and not rdy:
                    pending[uid] = "A" + str(int(t) % 10)
            last_rdy[uid] = cur_rdy

            # Units begin the fight at turn 0; using 0 (not None) as the implicit
            # previous turn catches each unit's FIRST/opener action even when the
            # first poll already shows it at turn_n >= 1 (the fast champions).
            prev = last_tn.get(uid, 0)
            if tn > prev and len(rows) < max_rows:
                is_boss = h.get("side") == "enemy"
                actor = BOSS_NAME if is_boss else id_to_name.get(
                    uid, name_map.get(h.get("type_id"), f"#{uid}"))
                dmg = max(0, boss_dmg - boss_prev_dmg)
                boss_prev_dmg = boss_dmg
                # The boss doesn't damage itself — the delta during a boss turn
                # is DoT ticks; consume it but don't credit the boss row.
                if is_boss:
                    dmg = 0
                if is_boss:
                    skill = _skill_alias(h, None, True)
                else:
                    skill = pending.pop(uid, None) or "A1"
                    # Prefer the tick log's exact per-action damage + skill,
                    # matched by normalised type id (slot orders differ).
                    nt = int(h.get("type_id") or 0) // 10
                    if overlay and nt in overlay["dmg"]:
                        k = action_idx.get(nt, 0)
                        action_idx[nt] = k + 1
                        if k < len(overlay["dmg"][nt]):
                            dmg = overlay["dmg"][nt][k]
                        if k < len(overlay["skill"][nt]) and overlay["skill"][nt][k]:
                            skill = overlay["skill"][nt][k]
                eff_dec = _decode_eff(h.get("eff"), emeta)
                cells = []
                for col in columns:
                    if col == BOSS_NAME:
                        u = boss
                    else:
                        u = next((x for x in hs if x.get("side") == "player"
                                  and id_to_name.get(x.get("id")) == col), None)
                    tm = int(round((u.get("tm") if u else 0) or 0))
                    acting = (col == actor)
                    cells.append({
                        "tm": 100 if acting else max(0, min(100, tm)),
                        "raw_tm": tm, "acting": acting,
                        "skill": skill if acting else None,
                        "effects": eff_dec if acting else [],
                    })
                rows.append({
                    "turn": len(rows) + 1, "boss_turn": cur_boss_turn, "actor": actor,
                    "is_boss_turn": is_boss, "damage": dmg, "danger": False, "cells": cells,
                })
            last_tn[uid] = tn

    return {
        "columns": columns,
        "column_type_ids": {c: (None if c == BOSS_NAME else type_ids.get(c)) for c in columns},
        "rows": rows,
        "protection_gaps": 0,
        "replay": True,
        "meta": {"damage": boss_prev_dmg, "boss_turns": cur_boss_turn,
                 "file": Path(log_path).name},
    }


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parent.parent
    if len(sys.argv) < 2:
        print("usage: python3 tools/cb_replay.py <battle_logs_cb_*.json>")
        sys.exit(1)
    try:
        from tools.cb_history import hero_type_to_name
        nm = hero_type_to_name(root)
    except Exception:
        nm = {}
    r = build_replay(root, Path(sys.argv[1]), nm)
    if "error" in r:
        print("ERROR:", r["error"]); sys.exit(1)
    print(f"file={r['meta']['file']} cols={r['columns']} rows={len(r['rows'])} "
          f"dmg={r['meta']['damage']} boss_turns={r['meta']['boss_turns']}")
    for row in r["rows"][:12]:
        ac = next((c for c in row["cells"] if c["acting"]), {})
        fx = "+".join(e["icon"][:5] for e in ac.get("effects", []))
        print(f"  T{row['turn']:<3} bt{row['boss_turn']:<2} {row['actor']:<12} "
              f"{ac.get('skill','?'):<5} dmg={row['damage']:<9} {fx}")
