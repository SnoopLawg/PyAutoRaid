#!/usr/bin/env python3
"""
Analyze a battle-log JSON dump (from the RaidAutomation mod `/battle-log`).

Joins per-turn hero snapshots with skills_db.json to infer:
  - Team composition (hero names from type_id)
  - Per-turn damage dealt (hp_lost deltas)
  - Skills used per turn (rdy:true -> false transitions on active hero)
  - Debuff/buff uptime on boss
  - Dead-turn rate (turns with stun/freeze/sleep/provoke on your heroes)
  - Per-hero totals: turns taken, damage dealt, uptime of CC suffered

Usage:
    python3 tools/battle_log_analyze.py [path/to/battle_log.json]

Defaults to the most recent battle_logs_cb_*.json in the project root.
"""
import json
import sys
import glob
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent


def load_hero_db():
    """Build type_id -> name map by matching skill-ID prefixes in skills_db.json."""
    # skills_db is keyed by hero NAME; each entry is list of skills with skill_type_id.
    # skill_type_id starts with the hero type_id.
    db = json.load(open(ROOT / "skills_db.json"))
    type_to_name = {}
    skill_to_info = {}
    for name, skills in db.items():
        if not skills:
            continue
        # Infer hero type_id from first skill (prefix of skill_type_id is hero type_id)
        first_skill_id = skills[0].get("skill_type_id", 0)
        # Hero type_id is skill_type_id // 10 for most, but some skills have 5-digit
        # skill_type_ids where the last digit is the skill index (1..5).
        # So hero_type_id = skill_type_id // 10.
        hid = first_skill_id // 10
        type_to_name[hid] = name
        for sk in skills:
            stid = sk.get("skill_type_id", 0)
            skill_to_info[stid] = {
                "hero": name,
                "level": sk.get("level"),
                "cooldown": sk.get("cooldown"),
                "is_a1": sk.get("is_a1", False),
                "effects": sk.get("effects", []),
            }
    # Boss hero IDs aren't in skills_db (usually). Known CB boss = 22270.
    type_to_name.setdefault(22270, "CB Boss")
    return type_to_name, skill_to_info


def skill_label(stid, skill_db, hero_type):
    """Produce a human label like 'A1', 'A2 (Unkillable+Block Debuffs)' for a skill ID."""
    if stid in skill_db:
        info = skill_db[stid]
        # Derive slot index from last digit of skill_type_id
        slot = stid - (stid // 10) * 10
        label = f"A{slot}"
        if info.get("is_a1"):
            label = "A1"
        effects = info.get("effects") or []
        # Collect status effect types for label
        se = []
        for e in effects:
            for s in e.get("status_effects", []):
                se.append(s.get("type"))
        if se:
            label += f" [se={se}]"
        return label
    # Fallback: slot from last digit
    slot = stid % 10
    return f"A{slot}(id={stid})"


DEBUFF_FLAGS = {
    "stun", "freeze", "sleep", "provoke", "banish", "grab", "entangle", "devour",
    "absent", "petrify", "nullifier", "enfeeble", "no_tm_tick", "block_heal",
}
BUFF_FLAGS = {
    "invincible", "block_debuff", "taunt", "rages", "invis", "xform", "ss", "ss_simple",
    "ss_reflect",
}


def analyze(log_path):
    d = json.load(open(log_path))
    logs = d["log"]
    type_to_name, skill_db = load_hero_db()

    turn_hooks = [e for e in logs if "active_hero" in e]
    hero_snaps = [e for e in logs if "heroes" in e]
    events = [e for e in logs if "event" in e]
    diags = [e for e in logs if "diag" in e]

    print(f"=== {log_path.name if isinstance(log_path, Path) else log_path} ===")
    print(f"active={d['active']}  turns_fired={d['turns']}  polls={d['polls']}  log_entries={d['count']}")
    print(f"  turn hooks: {len(turn_hooks)}   hero snapshots: {len(hero_snaps)}   events: {len(events)}   diags: {len(diags)}\n")

    if not hero_snaps:
        print("No hero snapshots — nothing to analyze.")
        return

    # Team composition (from first snapshot)
    first = hero_snaps[0]["heroes"]
    last = hero_snaps[-1]["heroes"]
    print("=== TEAM ===")
    print(f"  {'id':>2} {'side':6} {'name':<20} {'type_id':>7} {'HP_max':>10}")
    for h in first:
        name = type_to_name.get(h["type_id"], f"(type {h['type_id']})")
        print(f"  {h['id']:>2} {h['side']:6} {name:<20} {h['type_id']:>7} {h.get('hp_max',0):>10,}")
    print()

    # Index: id -> name
    id_to_name = {}
    for h in first:
        id_to_name[h["id"]] = type_to_name.get(h["type_id"], f"type{h['type_id']}")
    id_to_side = {h["id"]: h["side"] for h in first}

    # --- In-game turn counter (sum of all player turn_n values) vs mod turn counter
    # Raid's CB UI shows "Turn X" where X = sum of player BattleHero.TurnCount.
    last_snap = hero_snaps[-1]
    player_turn_total = sum(h.get("turn_n", 0) for h in last_snap["heroes"] if h.get("side") == "player")
    boss_turn = next((h.get("turn_n", 0) for h in last_snap["heroes"] if h.get("side") == "enemy"), 0)
    print(f"=== TURN COUNTERS ===")
    print(f"  mod _battleCommandCount : {d['turns']}   (fires every ProcessStartTurn)")
    print(f"  sum(player turn_n)      : {player_turn_total}   (== in-game 'Turn X' counter)")
    print(f"  boss turn_n             : {boss_turn}\n")

    # --- Authoritative damage + survival summary (the numbers you actually care about)
    last_boss = next((h for h in last_snap["heroes"] if h.get("side") == "enemy"), None)
    total_cb_damage = last_boss.get("dmg_taken", 0) if last_boss else 0
    deaths = []
    lowest_hp = {}  # hid -> (lowest hp_cur, hp_max)
    for snap in hero_snaps:
        for h in snap["heroes"]:
            if h.get("side") != "player":
                continue
            hp_cur = h.get("hp_cur", 0) or 0
            hp_max = h.get("hp_max", 0) or 0
            prev = lowest_hp.get(h["id"])
            if prev is None or hp_cur < prev[0]:
                lowest_hp[h["id"]] = (hp_cur, hp_max)
            if "dead" in h.get("st", []) and h["id"] not in {d_[0] for d_ in deaths}:
                deaths.append((h["id"], snap.get("turn", 0)))

    print("=== DAMAGE + SURVIVAL SUMMARY ===")
    print(f"  Total damage to CB       : {total_cb_damage:>14,}")
    print(f"  CB rounds survived       : {boss_turn}/50")
    print(f"  Player deaths            : {len(deaths)}/{len(lowest_hp)}")
    if deaths:
        for hid, t in deaths:
            print(f"    - {id_to_name.get(hid, f'id{hid}'):<15} died at mod turn {t}")
    print(f"  Lowest HP seen per hero (proves UK buff was saving them if low % while alive):")
    for hid, (low_hp, hp_max) in sorted(lowest_hp.items()):
        if id_to_side.get(hid) != "player":
            continue
        pct = (low_hp / hp_max * 100) if hp_max else 0
        survived = hid not in {d_[0] for d_ in deaths}
        print(f"    {id_to_name.get(hid, f'id{hid}'):<15} {low_hp:>6}/{hp_max:<6} ({pct:5.1f}%)  {'✓ survived' if survived else 'DIED'}")
    print()

    # --- Damage per turn + absorbed-by-UK delta
    # dmg_taken = cumulative real damage inflicted (incl. damage absorbed by UK/shields)
    # hp_lost   = cumulative HP actually lost
    # absorbed = dmg_taken - hp_lost per hero (saved by Unkillable/Block Damage/etc.)
    print("=== DAMAGE EVENTS (dmg_taken deltas per turn change) ===")
    prev_dmg = {h["id"]: h.get("dmg_taken", 0) for h in first}
    prev_hp_lost = {h["id"]: h.get("hp_lost", 0) for h in first}
    last_turn = -1
    damage_events = []
    for snap in hero_snaps:
        turn = snap.get("turn", 0)
        if turn == last_turn:
            continue
        last_turn = turn
        delta = {}
        for h in snap["heroes"]:
            cur_dmg = h.get("dmg_taken", 0)
            prev = prev_dmg.get(h["id"], 0)
            if cur_dmg != prev:
                delta[h["id"]] = {
                    "d_dmg": cur_dmg - prev,
                    "d_hp_lost": h.get("hp_lost", 0) - prev_hp_lost.get(h["id"], 0),
                }
                prev_dmg[h["id"]] = cur_dmg
                prev_hp_lost[h["id"]] = h.get("hp_lost", 0)
        if delta:
            damage_events.append((turn, delta))

    # Game mechanics reminder (for readers):
    #   Block Damage (BD)  = no damage taken at all (dmg_taken doesn't grow)
    #       -- wait, no: BD prevents HP loss. dmg_taken CAN still grow (incoming hit registers),
    #          but hp_lost stays 0.
    #   Unkillable (UK)    = damage registers AND HP drops, but hero can't fall below 1 HP.
    # So: if d_dmg > 0 AND d_hp_lost == 0  => Block Damage absorbed it.
    #     if d_dmg > 0 AND d_hp_lost > 0   => real damage landed (UK only saves the kill blow).
    shown = 0
    for turn, delta in damage_events:
        if shown >= 40:
            print(f"  ... ({len(damage_events) - shown} more turns)")
            break
        parts = []
        for hid, dd in sorted(delta.items()):
            n = id_to_name.get(hid, f"id{hid}")[:10]
            absorbed = dd["d_dmg"] - dd["d_hp_lost"]
            if absorbed > 0 and dd["d_hp_lost"] == 0:
                parts.append(f"{n} +{dd['d_dmg']:,}dmg (BD absorbed all)")
            elif absorbed > 0:
                parts.append(f"{n} +{dd['d_dmg']:,}dmg (hp-{dd['d_hp_lost']:,}, BD partial: {absorbed:,})")
            else:
                parts.append(f"{n} +{dd['d_dmg']:,}dmg (hp-{dd['d_hp_lost']:,})")
        print(f"  T{turn:3}: {'; '.join(parts)}")
        shown += 1
    print()

    # --- Totals per hero (BD absorbed vs HP lost)
    print("=== PER-HERO DAMAGE TOTALS (final) ===")
    print("  (BD = Block Damage absorbed, i.e. hits that registered but didn't reduce HP)")
    print(f"  {'name':<18} {'dmg_taken':>12} {'hp_lost':>10} {'BD_absorbed':>12} {'BD%':>6} {'turn_n':>7}")
    for h in last_snap["heroes"]:
        n = id_to_name.get(h["id"], f"id{h['id']}")[:18]
        dt = h.get("dmg_taken", 0)
        hl = h.get("hp_lost", 0)
        ab = dt - hl
        pct = (ab / dt * 100) if dt else 0
        print(f"  {n:<18} {dt:>12,} {hl:>10,} {ab:>12,} {pct:>5.1f}% {h.get('turn_n',0):>7}")
    print()

    # --- Detect moments BD dropped off (hp_lost starts growing mid-fight)
    # For each player hero, find the first turn where hp_lost became > 0.
    print("=== BLOCK DAMAGE COVERAGE (first turn each hero took real HP loss) ===")
    seen_hp_loss = {}  # hid -> first turn
    for snap in hero_snaps:
        for h in snap["heroes"]:
            if h.get("side") != "player": continue
            if h["id"] in seen_hp_loss: continue
            if h.get("hp_lost", 0) > 0:
                seen_hp_loss[h["id"]] = snap.get("turn", 0)
    for hid, name in id_to_name.items():
        if id_to_side.get(hid) != "player": continue
        first_loss = seen_hp_loss.get(hid)
        if first_loss is None:
            print(f"  {name:<18} BD held all fight (no HP loss through turn {d['turns']})")
        else:
            print(f"  {name:<18} BD failed at T{first_loss} — real HP damage landed")
    print()

    # --- Effect transitions: which buffs/debuffs appeared or disappeared each turn
    # For each hero, extract set of (effect_id) per snapshot. Diff consecutive snapshots.
    # eff entries look like: {"ph": N, "e": [{"id":X,"k":Y,"c":?,"s":?}, ...]}
    # --- Coverage-gap report: which heroes had NO damage-mitigating buff at each boss turn.
    # In Raid mechanics visible from HeroState:
    #   block_damage (IsInvincible) = Block Damage buff up (flag is flaky — often OFF when
    #                                 BD is absorbing a hit; trust survival outcomes, not flag)
    #   block_debuff (IsBlockDebuff) = blocks debuff application — does NOT prevent damage
    #   invis (IsInvisible) = gives dodge chance on single-target hits — partial protection
    #   uk_saved (IsUnkillable) = ONLY fires when hero is at 0 HP being prevented from dying
    # The Unkillable BUFF (not-yet-triggered) has no dedicated flag — can't detect directly.
    # NOTE: this report over-reports "WIPE RISK" in practice because UK buff coverage isn't
    # observable via a boolean. The authoritative survival signal is the "DEATHS" table below.
    print("=== COVERAGE GAPS PER BOSS TURN (flag-snapshot only — unreliable; see DEATHS below) ===")
    boss_turns = []  # list of (boss_turn_n, mod_turn, per_hero_coverage_dict)
    seen_boss_n = set()
    for snap in hero_snaps:
        boss = next((h for h in snap["heroes"] if h.get("side") == "enemy"), None)
        if not boss: continue
        btn = boss.get("turn_n", 0)
        if btn in seen_boss_n: continue
        seen_boss_n.add(btn)
        mt = snap.get("turn", 0)
        cov = {}
        for h in snap["heroes"]:
            if h.get("side") != "player": continue
            st = set(h.get("st", []))
            has_bd = "block_damage" in st or "invincible" in st  # support old logs with "invincible" label
            has_invis = "invis" in st
            is_dead = "dead" in st or "dying" in st
            cov[h["id"]] = {
                "bd": has_bd, "invis": has_invis, "dead": is_dead, "dmg": h.get("dmg_taken", 0),
            }
        boss_turns.append((btn, mt, cov))

    for btn, mt, cov in boss_turns:
        uncovered_names = []
        for hid, c in sorted(cov.items()):
            name = id_to_name.get(hid, f"id{hid}")
            if c["dead"]:
                uncovered_names.append(f"{name}(DEAD)")
            elif not c["bd"] and not c["invis"]:
                uncovered_names.append(name)
        tag = "  WIPE RISK" if len(uncovered_names) >= 2 else ("  GAP" if uncovered_names else "")
        if uncovered_names or btn >= 20:
            print(f"  B{btn:3} (mod T{mt:3}):  uncovered = {uncovered_names or '(none)'}{tag}")
    print()

    # --- Buff lifecycle (from boolean flag transitions, which DO change per turn)
    # PhaseEffects._effectsByPhaseIndex is static skill-phase data; boolean flags on
    # BattleHero are the real dynamic buff/debuff state. Track per-hero flag transitions
    # with attribution: which turn applied it, which hero consumed it when they took a turn.
    print("=== BUFF/DEBUFF LIFECYCLE (per-hero flag transitions) ===")
    # Assemble per-hero state tuple at each turn from: st list + uk field
    def hero_state(h):
        flags = set(h.get("st", []))
        if h.get("uk") is True: flags.add("uk")
        return flags

    # For each hero, find intervals where each flag was active: (start_turn, end_turn, turns_active)
    # And for each flag-loss event, record what "consumed" it (the hero's own turn, or timeout).
    by_hid = {}  # hid -> list of (turn, active_set)
    last_turn = -1
    for snap in hero_snaps:
        turn = snap.get("turn", 0)
        if turn == last_turn: continue
        last_turn = turn
        for h in snap["heroes"]:
            by_hid.setdefault(h["id"], []).append((turn, hero_state(h)))

    # Turn-hook ledger: turn -> active_hero
    turn_actor = {hk["turn"]: hk["active_hero"] for hk in turn_hooks}

    for hid in sorted(by_hid):
        side = id_to_side.get(hid)
        name = id_to_name.get(hid, f"id{hid}")
        history = by_hid[hid]
        # Scan for flag changes
        prev_flags = set()
        for (t, flags) in history:
            added = flags - prev_flags
            removed = prev_flags - flags
            for fg in added:
                actor = turn_actor.get(t, "?")
                actor_name = id_to_name.get(actor, f"id{actor}") if isinstance(actor, int) else "?"
                print(f"  T{t:3} {name:<10} +{fg:<14} (active hero: {actor_name})")
            for fg in removed:
                actor = turn_actor.get(t, "?")
                actor_name = id_to_name.get(actor, f"id{actor}") if isinstance(actor, int) else "?"
                cause = "(hero acted)" if actor == hid else f"(expired while {actor_name} acted)"
                print(f"  T{t:3} {name:<10} -{fg:<14} {cause}")
            prev_flags = flags
    print()

    # --- Per-buff uptime: % turns each flag was active per hero
    print("=== FLAG UPTIME (% of snapshots each flag was active per hero) ===")
    all_flags = set()
    flag_counts = {}  # (hid, flag) -> count
    snapshots_per_hero = {}
    for snap in hero_snaps:
        for h in snap["heroes"]:
            snapshots_per_hero[h["id"]] = snapshots_per_hero.get(h["id"], 0) + 1
            for f in hero_state(h):
                all_flags.add(f)
                flag_counts[(h["id"], f)] = flag_counts.get((h["id"], f), 0) + 1
    for hid in sorted(by_hid):
        name = id_to_name.get(hid, f"id{hid}")
        total = snapshots_per_hero.get(hid, 0)
        parts = []
        for f in sorted(all_flags):
            c = flag_counts.get((hid, f), 0)
            if c > 0:
                parts.append(f"{f}:{c/total*100:.0f}%")
        print(f"  {name:<12} {'  '.join(parts)}")
    print()

    # Baseline = all effects present at T0 (masteries, artifact sets, passives). We only care
    # about what gets added/removed DURING the fight vs that baseline.
    def collect_effs(heroes):
        result = {}  # hid -> {effect_id: (kind, phase)}
        for h in heroes:
            cur = {}
            for bucket in h.get("eff", []):
                ph = bucket["ph"]
                for e in bucket.get("e", []):
                    if not e: continue
                    cur[e["id"]] = (e.get("k"), ph)
            result[h["id"]] = cur
        return result

    baseline = collect_effs(hero_snaps[0]["heroes"]) if hero_snaps else {}

    print("=== EFFECT TRANSITIONS PER TURN (excl. baseline passives) ===")
    prev_effs = {hid: dict(effs) for hid, effs in baseline.items()}
    last_turn = -1
    for snap in hero_snaps:
        turn = snap.get("turn", 0)
        if turn == last_turn or turn == 0: continue
        last_turn = turn
        cur_all = collect_effs(snap["heroes"])
        added = {}
        removed = {}
        for hid, cur in cur_all.items():
            prev = prev_effs.get(hid, {})
            # Exclude baseline effect IDs from "added" (they're passives appearing first time)
            new_ids = (set(cur.keys()) - set(prev.keys())) - set(baseline.get(hid, {}).keys())
            gone_ids = set(prev.keys()) - set(cur.keys()) - set(baseline.get(hid, {}).keys())
            if new_ids:
                added[hid] = [(i, cur[i][0], cur[i][1]) for i in new_ids]
            if gone_ids:
                removed[hid] = [(i, prev[i][0], prev[i][1]) for i in gone_ids]
            prev_effs[hid] = cur
        for hid, entries in added.items():
            n = id_to_name.get(hid, f"id{hid}")[:14]
            ents = ", ".join(f"id{i}/k{k}@ph{p}" for (i, k, p) in entries[:8])
            if len(entries) > 8: ents += f" (+{len(entries)-8} more)"
            print(f"  T{turn:3} + {n:<14} {ents}")
        for hid, entries in removed.items():
            n = id_to_name.get(hid, f"id{hid}")[:14]
            ents = ", ".join(f"id{i}/k{k}" for (i, k, _) in entries[:8])
            if len(entries) > 8: ents += f" (+{len(entries)-8} more)"
            print(f"  T{turn:3} - {n:<14} {ents}")
    print()

    # --- AoE detection: a single turn where the same kind appears on 2+ heroes (excl. baseline)
    print("=== AoE APPLICATIONS (same kind placed on 2+ heroes in one turn) ===")
    prev_effs = {hid: dict(effs) for hid, effs in baseline.items()}
    last_turn = -1
    for snap in hero_snaps:
        turn = snap.get("turn", 0)
        if turn == last_turn or turn == 0: continue
        last_turn = turn
        cur_all = collect_effs(snap["heroes"])
        kind_to_heroes = {}
        for hid, cur in cur_all.items():
            new_ids = (set(cur.keys()) - set(prev_effs.get(hid, {}).keys())) - set(baseline.get(hid, {}).keys())
            for i in new_ids:
                k = cur[i][0]
                kind_to_heroes.setdefault(k, []).append(hid)
            prev_effs[hid] = cur
        for k, hids in kind_to_heroes.items():
            if len(hids) >= 2:
                targets = ", ".join(id_to_name.get(h, f"id{h}")[:10] for h in hids)
                print(f"  T{turn:3}  kind {k:>5} → {targets}  ({len(hids)} targets)")
    print()

    # --- Skills fired per turn: for each turn hook, compare sk[].rdy to previous snapshot
    # Use hero_snaps grouped by turn. For the hook at turn T, the active_hero used a
    # skill; we find which skill flipped rdy -> not-rdy.
    print("=== SKILLS USED (inferred from rdy transitions on active hero) ===")
    # Build: for each turn, hero states
    snap_by_turn = {}
    for snap in hero_snaps:
        snap_by_turn.setdefault(snap["turn"], []).append(snap)

    skills_fired = []  # (turn, caster_id, skill_ids)
    # For each turn hook, find rdy flips relative to the previous turn's last snapshot
    turns_in_order = sorted(set(snap_by_turn.keys()))
    prev_rdy_by_hero = {}  # {id: {skill_id: bool}}
    for h in first:
        prev_rdy_by_hero[h["id"]] = {s["t"]: s.get("rdy", True) for s in h.get("sk", [])}
    for hook in turn_hooks:
        turn = hook.get("turn", 0)
        active = hook.get("active_hero")
        # Find latest snapshot AT OR AFTER this turn with the full state
        matching = [s for s in hero_snaps if s["turn"] == turn]
        if not matching:
            continue
        snap = matching[-1]
        for h in snap["heroes"]:
            if h["id"] != active:
                continue
            new_rdy = {s["t"]: s.get("rdy", True) for s in h.get("sk", [])}
            prev = prev_rdy_by_hero.get(active, {})
            fired = [stid for stid, r in new_rdy.items() if prev.get(stid, True) and not r]
            if fired:
                skills_fired.append((turn, active, fired))
            prev_rdy_by_hero[active] = new_rdy

    shown = 0
    for turn, caster, fired in skills_fired:
        if shown >= 30:
            print(f"  ... ({len(skills_fired) - shown} more)")
            break
        caster_name = id_to_name.get(caster, f"id{caster}")
        labels = [skill_label(s, skill_db, caster) for s in fired]
        print(f"  T{turn:3}: {caster_name:<18} fired {', '.join(labels)}")
        shown += 1
    print()

    # --- Boss status flag uptime
    boss_id = next((h["id"] for h in first if h["side"] == "enemy"), None)
    if boss_id is not None:
        print("=== BOSS STATUS FLAG UPTIME (% of snapshots with each flag) ===")
        flag_count = defaultdict(int)
        total_boss_snaps = 0
        for snap in hero_snaps:
            for h in snap["heroes"]:
                if h["id"] == boss_id:
                    total_boss_snaps += 1
                    for flag in h.get("st", []):
                        flag_count[flag] += 1
                    break
        if total_boss_snaps:
            for flag, count in sorted(flag_count.items(), key=lambda x: -x[1]):
                pct = count / total_boss_snaps * 100
                print(f"  {flag:<18} {count:>4}/{total_boss_snaps} ({pct:5.1f}%)")
        print()

    # --- Dead-turn rate per player hero
    print("=== CC/DEAD-TURN SUFFERED PER PLAYER HERO (% of snapshots with CC/dead) ===")
    total_snaps = len(hero_snaps)
    for hid, name in id_to_name.items():
        if id_to_side.get(hid) != "player":
            continue
        cc_count = 0
        dead_count = 0
        for snap in hero_snaps:
            for h in snap["heroes"]:
                if h["id"] != hid:
                    continue
                st = set(h.get("st", []))
                if "dead" in st or "dying" in st:
                    dead_count += 1
                elif st & DEBUFF_FLAGS:
                    cc_count += 1
                break
        cc_pct = cc_count / total_snaps * 100 if total_snaps else 0
        dd_pct = dead_count / total_snaps * 100 if total_snaps else 0
        print(f"  {name:<18} cc={cc_pct:5.1f}%  dead={dd_pct:5.1f}%")
    print()

    # --- Per-hero damage dealt (approximation via turn hook attribution)
    # When a hero takes a turn, damage that appeared on enemies between this turn
    # and the previous turn is attributed to them. Crude but useful.
    print("=== DAMAGE DEALT TO BOSS BY CASTER (via turn-hook attribution) ===")
    boss_hp_by_turn = {}
    for snap in hero_snaps:
        for h in snap["heroes"]:
            if h["id"] == boss_id:
                boss_hp_by_turn[snap["turn"]] = h.get("hp_lost", 0)
                break
    caster_damage = defaultdict(int)
    prev_boss_hp_lost = boss_hp_by_turn.get(min(boss_hp_by_turn.keys(), default=0), 0)
    for hook in turn_hooks:
        turn = hook["turn"]
        active = hook.get("active_hero")
        cur_boss_hp_lost = boss_hp_by_turn.get(turn, prev_boss_hp_lost)
        damage = cur_boss_hp_lost - prev_boss_hp_lost
        if damage > 0 and active is not None:
            caster_damage[active] += damage
        prev_boss_hp_lost = cur_boss_hp_lost

    # Extrapolate to whole fight
    total_boss_damage = sum(caster_damage.values())
    for caster, dmg in sorted(caster_damage.items(), key=lambda x: -x[1]):
        name = id_to_name.get(caster, f"id{caster}")
        pct = dmg / total_boss_damage * 100 if total_boss_damage else 0
        print(f"  {name:<18} {dmg:>12,} ({pct:5.1f}%)")
    print(f"  {'TOTAL':<18} {total_boss_damage:>12,}")
    # Projection
    boss_max = first[-1].get("hp_max", 0) if first[-1]["side"] == "enemy" else next(
        (h["hp_max"] for h in last if h["side"] == "enemy"), 0)
    turns_done = turn_hooks[-1]["turn"] if turn_hooks else 0
    if boss_max and turns_done:
        per_turn = total_boss_damage / turns_done
        print(f"  boss hp_max={boss_max:,}  avg dmg/turn={per_turn:,.0f}  est key={per_turn*50:,.0f} (over 50t)")

    # --- Stat-mod effects ledger (from `mods` field added 2026-04-13)
    # Each mod entry: {"id":effect_id, "k":StatKindId, "v":signed value (Fixed >> 32)}
    # StatKindId: 1=HP, 2=ATK, 3=DEF, 4=SPD, 5=RES, 6=ACC, 7=CR, 8=CD (other = special)
    # Negative v = debuff (e.g., DEF Down id=151 k=3 v=-912 on boss).
    # Positive v on a player = buff (e.g., Stoneskin id=5002121 k=3 v=+75 DEF%).
    # Filter to DYNAMIC mods (exclude baseline mastery/passive mods present at T0).
    _SKID = {1: "HP", 2: "ATK", 3: "DEF", 4: "SPD", 5: "RES", 6: "ACC", 7: "CR", 8: "CD"}
    baseline_mod_ids = {}  # hid -> set of effect_ids present at T0
    if hero_snaps:
        for h in hero_snaps[0]["heroes"]:
            baseline_mod_ids[h["id"]] = {m["id"] for m in (h.get("mods") or []) if m}

    print("\n=== STAT-MOD EFFECTS (dynamic — baseline passives filtered out) ===")
    print("  k=1HP 2ATK 3DEF 4SPD 5RES 6ACC 7CR 8CD | v is signed (v<0 = debuff)")
    shown_dynamic = 0
    prev_seen = {hid: set() for hid in baseline_mod_ids}
    for snap in hero_snaps:
        turn = snap.get("turn", 0)
        if turn == 0:
            continue
        row_parts = []
        for h in snap["heroes"]:
            mods = h.get("mods") or []
            dynamic = [m for m in mods if m and m["id"] not in baseline_mod_ids.get(h["id"], set())]
            # Only show when new dynamic mod appears for this hero on this turn
            cur_ids = {m["id"] for m in dynamic}
            new_ids = cur_ids - prev_seen.get(h["id"], set())
            if new_ids:
                name = id_to_name.get(h["id"], f"id{h['id']}")[:10]
                newly = [m for m in dynamic if m["id"] in new_ids]
                parts = ", ".join(
                    f"id{m['id']}/{_SKID.get(m['k'], 'k'+str(m['k']))}{'+' if m['v'] >= 0 else ''}{m['v']}"
                    for m in newly
                )
                row_parts.append(f"{name}→[{parts}]")
            prev_seen[h["id"]] = cur_ids
        if row_parts:
            print(f"  T{turn:3}: {'; '.join(row_parts)}")
            shown_dynamic += 1
            if shown_dynamic >= 30:
                print(f"  ... (truncated, {len([1 for s in hero_snaps if s.get('turn',0) > turn])} more turns to scan)")
                break

    # --- Current-state mod summary at END of fight
    print("\n=== FINAL STAT-MOD SNAPSHOT (active mods at last turn) ===")
    if hero_snaps:
        for h in hero_snaps[-1]["heroes"]:
            mods = h.get("mods") or []
            dynamic = [m for m in mods if m and m["id"] not in baseline_mod_ids.get(h["id"], set())]
            if not dynamic:
                continue
            name = id_to_name.get(h["id"], type_to_name.get(h.get("type_id"), f"type{h.get('type_id')}"))
            parts = ", ".join(
                f"id{m['id']}/{_SKID.get(m['k'], 'k'+str(m['k']))}{'+' if m['v'] >= 0 else ''}{m['v']}"
                for m in dynamic
            )
            print(f"  {name:<12} ({h.get('side','?')}): {parts}")

    # --- AbsorbedDamageByEffectKindId — cumulative damage absorbed by each effect
    # Authoritative "which protection actually absorbed damage" signal. Effect kind IDs
    # we've observed: 2004 (continuous heal / shield family seems most common).
    print("\n=== ABSORBED DAMAGE BY EFFECT KIND (cumulative, final) ===")
    if hero_snaps:
        last_snapshot = hero_snaps[-1]
        for h in last_snapshot["heroes"]:
            abs_ = h.get("abs") or {}
            if not abs_:
                continue
            name = id_to_name.get(h["id"], type_to_name.get(h.get("type_id"), f"type{h.get('type_id')}"))
            parts = ", ".join(f"kind{k}:{v:,}" for k, v in sorted(abs_.items(), key=lambda kv: -int(kv[1])))
            print(f"  {name:<12} ({h.get('side','?')}): {parts}")
    print()

    print("\n=== FINAL STATE ===")
    for h in last:
        name = type_to_name.get(h["type_id"], f"type{h['type_id']}")[:20]
        cur = h.get("hp_max", 0) - h.get("hp_lost", 0)
        hp_max = h.get("hp_max", 0)
        pct = int(cur / hp_max * 100) if hp_max else 0
        st = ",".join(h.get("st", [])) or "-"
        ready = [s["t"] for s in h.get("sk", []) if s.get("rdy")]
        on_cd = [s["t"] for s in h.get("sk", []) if not s.get("rdy")]
        print(f"  {h['side']:6} {name:<20} HP {cur:>11,}/{hp_max:<11,} ({pct:3}%) TM {h.get('tm',0):3}  st={st}  rdy={ready}  cd={on_cd}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        # Most recent battle_logs_cb_*.json in ROOT
        candidates = sorted(glob.glob(str(ROOT / "battle_logs_cb_*.json")))
        if not candidates:
            print("Usage: battle_log_analyze.py <path>", file=sys.stderr)
            sys.exit(1)
        path = Path(candidates[-1])
    analyze(path)
