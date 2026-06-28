"""Per-COMMAND UK/BD coverage analysis (needs the fixed per-command buff reader).

Reads the newest tick_log_cb_*.json. The per-command unit snapshots now carry
"buffs":[{t,d,src}] (dynamic-offset reader). This measures, at each BOSS action
command, whether the fast caster (Maneater) actually has UK(320) or BD(60) up —
the precise game-truth coverage the empty AppliedEffects reader was blocking.

Usage: python tools/analyze_command_coverage.py [tick_log.json]
"""
import sys, json, glob, os

UK, BD, SHIELD = 320, 60, 280

def newest():
    fs = glob.glob("tick_log_cb_*.json")
    return max(fs, key=os.path.getmtime) if fs else None

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else newest()
    print(f"# tick log: {path}")
    d = json.load(open(path, encoding="utf-8"))
    ticks = d.get("ticks", [])
    # Defensive: keep only CB snapshots (exactly 1 enemy unit). A prior non-CB
    # battle (e.g. 4v4) can bleed into the tick log; those have >1 enemy and
    # different heroes/speeds -> phantom buffs. Filter them out.
    def n_enemy(t):
        return sum(1 for u in (t.get("units") or []) if u.get("s") == "e")
    before = len([t for t in ticks if t.get("units")])
    ticks = [t for t in ticks if not t.get("units") or n_enemy(t) == 1]
    after = len([t for t in ticks if t.get("units")])
    if after < before:
        print(f"# filtered {before - after} non-CB (multi-enemy) snapshots")
    # Does any unit now carry populated buffs?
    nb = sum(1 for t in ticks for u in (t.get("units") or []) if u.get("buffs"))
    print(f"# unit-snapshots with populated buffs: {nb}")
    if not nb:
        print("STILL EMPTY — buff reader fix did not populate. Stop."); return 1

    # Maneater = fastest player
    spd = {}
    for t in ticks:
        for u in t.get("units") or []:
            if u.get("s") == "p":
                spd[u["id"]] = max(spd.get(u["id"], 0), u.get("s_spd") or 0)
    mane = max(spd, key=spd.get)
    print(f"# Maneater id={mane} spd={spd[mane]}")

    # For each command snapshot, record boss tn + Maneater buff set
    def has(u, tid):
        return any(b.get("t") == tid and (b.get("d", 0) or 0) != 0 for b in (u.get("buffs") or []))

    rows = []
    for t in ticks:
        units = t.get("units") or []
        boss = next((u for u in units if u.get("s") == "e"), None)
        m = next((u for u in units if u.get("id") == mane), None)
        if not boss or not m:
            continue
        rows.append((t.get("tick"), boss.get("tn"),
                     has(m, UK), has(m, BD), has(m, SHIELD),
                     m.get("hp"), m.get("hp_max")))

    # Coverage by distinct boss turn: was Maneater UK-or-BD covered at ANY snapshot of that BT?
    by_bt = {}
    for tick, bt, uk, bd, sh, hp, hpmax in rows:
        if bt is None:
            continue
        r = by_bt.setdefault(bt, {"uk": False, "bd": False, "sh": False, "minhp": 1e9, "hpmax": hpmax})
        r["uk"] |= uk; r["bd"] |= bd; r["sh"] |= sh
        if hp is not None:
            r["minhp"] = min(r["minhp"], hp)
    covered = sum(1 for r in by_bt.values() if r["uk"] or r["bd"])
    print(f"\n## Maneater coverage: {covered}/{len(by_bt)} boss turns had UK or BD")
    bare = [bt for bt in sorted(by_bt) if not (by_bt[bt]["uk"] or by_bt[bt]["bd"])]
    print(f"## Bare boss turns (no UK/BD any snapshot): {bare}")
    print(f"\nBT | UK BD SH  minHP")
    for bt in sorted(by_bt):
        r = by_bt[bt]
        hp = r["minhp"] if r["minhp"] < 1e9 else 0
        pct = (hp / r["hpmax"] * 100) if r["hpmax"] else 0
        flag = "" if (r["uk"] or r["bd"]) else "  <-- BARE"
        print(f"{bt:>2} |  {int(r['uk'])}  {int(r['bd'])}  {int(r['sh'])}  {pct:5.0f}%{flag}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
