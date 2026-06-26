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


def _apply_state(e) -> tuple[bool, bool]:
    """(landed, failed) for an apply_status event, trusting the game's own
    ApplyContext (ApplyResult / IsGuaranteedBlocked / IsEvaded) over the coarse
    `fail` flag. failed => render the icon X'd (blocked/evaded/resisted)."""
    args = e.get("args") or []
    a0 = args[0] if args and isinstance(args[0], dict) else {}
    ac = a0.get("ApplyContext") or {}
    landed = bool(ac.get("ApplyResult")) if "ApplyResult" in ac else not e.get("fail")
    blocked = bool(ac.get("IsGuaranteedBlocked")) or bool(a0.get("IsEvaded"))
    return (landed and not blocked), (not landed) or blocked


def _tick_overlay(root: Path, ts: str, emeta: dict | None = None) -> dict | None:
    """From the matching tick_log_cb_<ts>.json, build each hero slot's ordered
    per-action damage to the boss (their own hit + their own DoT/effect damage
    accumulated since their last action) and the skill they cast. Damage is
    attributed by the event's `producer` — so a poison/burn tick is credited to
    the champion who applied it, never to whoever's turn it landed on.

    Also overlays the buffs/debuffs each champion PLACES on their action
    (DWJ-style "green on the caster's turn") from the `apply_status` stream,
    keyed the same way (normalised producer type id -> per-action list)."""
    emeta = emeta or {}
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
    received: dict = defaultdict(int)        # damage each hero took from the boss
    max_tick = 0
    for e in ticks:
        if not isinstance(e, dict):
            continue
        tk = e.get("tick") or 0
        max_tick = max(max_tick, tk)
        if e.get("kind") != "damage":
            continue
        d = int(e.get("dealt") or 0)
        if e.get("target") == BOSS_SLOT:     # damage TO the boss (hero -> boss)
            pr, pt = e.get("producer"), e.get("p_typeid")
            if pr is None or pr == BOSS_SLOT or pt is None:
                continue
            nt = int(pt) // 10
            slot_to_nt[pr] = nt
            if e.get("kind_id") == 6000:
                hit_by_tick[tk][nt] += d
                hit_ticks[nt].add(tk)
            else:
                dot_by_tick[tk][nt] += d
        elif e.get("producer") == BOSS_SLOT:  # damage FROM the boss (boss -> hero)
            tt = e.get("t_typeid")
            if tt is not None:
                received[int(tt) // 10] += d
    casts: dict = defaultdict(list)
    for e in ticks:
        if isinstance(e, dict) and e.get("kind") == "cast":
            sl = e.get("producer_id")
            nt = slot_to_nt.get(sl)
            if nt is not None:
                casts[nt].append((e.get("tick"), e.get("skill_type_id")))

    # Buffs/debuffs a champion PLACES, bucketed by tick under the producer's
    # normalised type id. The slot->nt map is learned from boss-damage events, so
    # also seed it from cast producers (a pure-support turn deals no boss damage).
    for e in ticks:
        if isinstance(e, dict) and e.get("kind") == "cast":
            sl, pt = e.get("producer_id"), e.get("p_typeid") or e.get("producer_type")
            if sl is not None and sl != BOSS_SLOT and pt and sl not in slot_to_nt:
                slot_to_nt[sl] = int(pt) // 10
    eff_by_tick: dict = defaultdict(lambda: defaultdict(list))   # nt -> tick -> [eff]
    for e in ticks:
        if not isinstance(e, dict) or e.get("kind") != "apply_status":
            continue
        pr, pt = e.get("prod"), e.get("prodT")
        if pr is None or pr == BOSS_SLOT or not pt:
            continue
        m = emeta.get(e.get("setype"))
        if not m:
            continue
        landed, failed = _apply_state(e)
        eff_by_tick[int(pt) // 10][e.get("tick") or 0].append({
            "icon": m["icon"], "label": m["label"], "kind": m["kind"],
            "state": "new", "rem": 0, "failed": failed,
            "on_boss": e.get("tgt") == BOSS_SLOT,
        })

    out_dmg, out_skill, out_eff = {}, {}, {}
    for nt in set(list(casts) + list(hit_ticks) + list(eff_by_tick)):
        # One entry per TURN (cast). Each turn absorbs ALL of this champion's
        # boss damage — multi-hits, counters AND DoT ticks — since their last
        # turn; the final turn also absorbs DoT that keeps ticking afterwards.
        cast_list = sorted(casts.get(nt, []), key=lambda x: x[0])
        if not cast_list:                       # damage/effects but no cast (rare)
            anchor = hit_ticks.get(nt) or set(eff_by_tick.get(nt, {}))
            cast_list = [(min(anchor), None)] if anchor else []
        dmgs, sks, effs, prev = [], [], [], -1
        for i, (T, st) in enumerate(cast_list):
            end = max_tick if i == len(cast_list) - 1 else T
            tot = sum(hit_by_tick[tk].get(nt, 0) + dot_by_tick[tk].get(nt, 0)
                      for tk in range(prev + 1, end + 1))
            dmgs.append(tot)
            sks.append("A" + str(int(st) % 10) if st else None)
            # Effects this champion placed during THIS action (up to its cast
            # tick — trailing DoT ticks aren't fresh placements). Dedupe by icon,
            # preferring a landed copy when the same effect hit multiple targets.
            by_icon: dict = {}
            for tk in range(prev + 1, T + 1):
                for fx in eff_by_tick.get(nt, {}).get(tk, []):
                    cur = by_icon.get(fx["icon"])
                    if cur is None or (cur["failed"] and not fx["failed"]):
                        by_icon[fx["icon"]] = fx
            effs.append(list(by_icon.values()))
            prev = T
        out_dmg[nt] = dmgs
        out_skill[nt] = sks
        out_eff[nt] = effs

    # Boss stun targeting. Landed stuns are apply_status setype=10 (tgtT=target,
    # fail=0). To also catch RESISTED stuns we learn the boss's stun skill id
    # from the casts nearest the landed applies, then flag any cast of that
    # skill with no matching landed apply as resisted. boss_turn from snapshots.
    STUN = 10
    boss_tn_at: dict = {}
    for e in ticks:
        if isinstance(e, dict) and "units" in e:
            b = next((u for u in e["units"] if u.get("s") == "e"), None)
            if b is not None:
                boss_tn_at[e.get("tick") or 0] = b.get("tn")

    def boss_turn_at(tk):
        if tk in boss_tn_at:
            return boss_tn_at[tk]
        cands = [t for t in boss_tn_at if t <= tk]
        return boss_tn_at[max(cands)] if cands else None

    applies = [e for e in ticks if isinstance(e, dict) and e.get("kind") == "apply_status" and e.get("setype") == STUN]
    casts_all = [e for e in ticks if isinstance(e, dict) and e.get("kind") == "cast" and e.get("producer_id") == BOSS_SLOT]
    # learn the stun skill id (boss cast within 2 ticks of a landed stun apply)
    from collections import Counter
    skill_votes = Counter()
    for a in applies:
        near = [c for c in casts_all if abs((c.get("tick") or 0) - (a.get("tick") or 0)) <= 2]
        for c in near:
            skill_votes[c.get("skill_type_id")] += 1
    stun_skill = skill_votes.most_common(1)[0][0] if skill_votes else None
    # Did a stun actually COST the target a turn? A landed stun roughly doubles
    # the gap straddling its tick in that champion's cast cadence. This is the
    # truthful "landed" signal: the game logs many stuns as applied (ApplyResult
    # true, not blocked) yet the hero acts on schedule — the debuff was shaken
    # off before their turn, so it cost nothing.
    import statistics

    def cost_a_turn(nt, tk):
        cts = sorted(t for t, _ in casts.get(nt, []))
        if len(cts) < 4:
            return None
        gaps = [b - a for a, b in zip(cts, cts[1:])]
        med = statistics.median(gaps) or 0
        before = [t for t in cts if t <= tk]
        after = [t for t in cts if t > tk]
        if not before or not after or med <= 0:
            return None
        return (after[0] - before[-1]) > 1.6 * med

    stuns = []
    seen_casts = set()
    for c in casts_all:
        if stun_skill is not None and c.get("skill_type_id") != stun_skill:
            continue
        tk = c.get("tick") or 0
        if tk in seen_casts:
            continue
        seen_casts.add(tk)
        tslot = c.get("target_id")
        ap = next((a for a in applies if abs((a.get("tick") or 0) - tk) <= 2
                   and a.get("tgt") == tslot), None)
        if ap is not None:
            tnt = int(ap.get("tgtT") or 0) // 10
            _, blocked = _apply_state(ap)
        else:
            tnt = slot_to_nt.get(tslot)
            blocked = True
        if not tnt:
            continue
        skipped = cost_a_turn(tnt, tk)
        # Landed only if it both applied (not blocked) AND cost a turn. When the
        # cadence is too short to tell, fall back to the apply verdict.
        landed = (not blocked) if skipped is None else (skipped and not blocked)
        stuns.append({"boss_turn": boss_turn_at(tk), "target_nt": tnt,
                      "landed": bool(landed), "blocked": bool(blocked)})

    return {"dmg": out_dmg, "skill": out_skill, "eff": out_eff,
            "received": dict(received), "stuns": stuns}


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
    overlay = _tick_overlay(root, m.group(1), emeta) if m else None
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
                overlay_eff = None
                if is_boss:
                    skill = _skill_alias(h, None, True)
                else:
                    skill = pending.pop(uid, None) or "A1"
                    # Prefer the tick log's exact per-action damage + skill +
                    # placed effects, matched by normalised type id (slot orders
                    # differ between the battle log and the tick log).
                    nt = int(h.get("type_id") or 0) // 10
                    if overlay and nt in overlay["dmg"]:
                        k = action_idx.get(nt, 0)
                        action_idx[nt] = k + 1
                        if k < len(overlay["dmg"][nt]):
                            dmg = overlay["dmg"][nt][k]
                        if k < len(overlay["skill"][nt]) and overlay["skill"][nt][k]:
                            skill = overlay["skill"][nt][k]
                        if k < len(overlay["eff"][nt]):
                            overlay_eff = overlay["eff"][nt][k]
                eff_dec = overlay_eff if overlay_eff is not None \
                    else _decode_eff(h.get("eff"), emeta)
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

    # Boss stun: mark the victim's first turn at/after the stun with the Stun
    # icon (X'd if the boss's stun was resisted — shows who was targeted either
    # way). The turns right after a boss STUN are where this lands.
    for s in (overlay or {}).get("stuns", []):
        tnt, bt = s.get("target_nt"), s.get("boss_turn")
        for r in rows:
            if r["is_boss_turn"]:
                continue
            tid = type_ids.get(r["actor"])
            if tid is None or (tid // 10) != tnt:
                continue
            if bt is not None and r["boss_turn"] < bt:
                continue
            if any(e.get("icon") == "Stun" for c in r["cells"] if c["acting"]
                   for e in c.get("effects", [])):
                continue   # already marked
            ac = next((c for c in r["cells"] if c["acting"]), None)
            if ac is not None:
                if s.get("landed"):
                    lbl = "Stunned (lost a turn)"
                elif s.get("blocked"):
                    lbl = "Stun blocked (Block Debuffs)"
                else:
                    lbl = "Stun shaken off (no turn lost)"
                ac["effects"] = (ac.get("effects") or []) + [{
                    "icon": "Stun", "kind": "debuff", "state": "new", "rem": 0,
                    "label": lbl, "failed": not s.get("landed")}]
            break

    # Team summary: per hero, damage dealt to boss + damage received from boss.
    from collections import defaultdict as _dd
    dealt_by = _dd(int)
    for r in rows:
        if not r["is_boss_turn"]:
            dealt_by[r["actor"]] += r["damage"]
    recv = (overlay or {}).get("received", {})
    team = []
    for col in columns:
        if col == BOSS_NAME:
            continue
        tid = type_ids.get(col)
        team.append({"name": col, "type_id": tid,
                     "dealt": dealt_by.get(col, 0),
                     "received": int(recv.get((tid or 0) // 10, 0))})

    return {
        "columns": columns,
        "column_type_ids": {c: (None if c == BOSS_NAME else type_ids.get(c)) for c in columns},
        "rows": rows,
        "team": team,
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
