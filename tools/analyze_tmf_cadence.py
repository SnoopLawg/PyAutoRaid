"""Analyze the new full-precision stamina (tm_f) + frame telemetry to settle the
1.52-vs-1.61 Maneater-cadence contradiction WITHOUT touching the locked speeds.

Reads the newest tick_log_cb_*.json (per-command snapshots with units[].tm_f).
For each consecutive pair of SIMULTANEOUS snapshots (same command captures ALL
units at once) it computes:
  - boss vs Maneater stamina GAIN ratio (= effective speed ratio)
  - boss turn (tn) spacing in commands AND frames (uniform 190 vs gapped/~176)
  - discrete TM fills on Maneater (tm_f jump NOT explained by speed accumulation)

Usage: python tools/analyze_tmf_cadence.py [path]
"""
import sys, json, glob, os

def newest_ticklog():
    files = glob.glob("tick_log_cb_*.json")
    return max(files, key=os.path.getmtime) if files else None

def load(path):
    d = json.load(open(path, encoding="utf-8"))
    ticks = d.get("ticks") or []
    # also support a flat list / {"log":[...]} of snapshots
    if not ticks and isinstance(d, dict) and "log" in d:
        ticks = [e for e in d["log"] if "units" in e or "heroes" in e]
    if not ticks and isinstance(d, list):
        ticks = d
    return ticks

def units_of(snap):
    return snap.get("units") or snap.get("heroes") or []

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else newest_ticklog()
    if not path:
        print("no tick log found"); return 1
    print(f"# tick log: {path}")
    ticks = load(path)
    snaps = [s for s in ticks if units_of(s) and any(("tm_f" in u) for u in units_of(s))]
    print(f"# snapshots with tm_f: {len(snaps)} / {len(ticks)} ticks")
    if not snaps:
        print("NO tm_f data — mod build may not have been live for this capture."); return 1

    # Identify Maneater (player, highest s_spd) and boss (enemy)
    def is_boss(u): return (u.get("s") == "e") or (u.get("side") == "enemy")
    spd_max = {}
    for s in snaps:
        for u in units_of(s):
            if not is_boss(u):
                spd_max[u.get("id")] = max(spd_max.get(u.get("id"), 0), u.get("s_spd") or 0)
    mane_id = max(spd_max, key=spd_max.get) if spd_max else None
    print(f"# Maneater id={mane_id} s_spd={spd_max.get(mane_id)}  (boss=enemy side)")

    def get(snap, pred):
        for u in units_of(snap):
            if pred(u): return u
        return None

    # 1) Speed ratio from consecutive simultaneous gains
    ratios = []
    fills = []
    prev = None
    boss_tn_at = []   # (command_tick, frame, boss_tn)
    mane_tn_at = []
    for s in snaps:
        b = get(s, is_boss)
        m = get(s, lambda u: u.get("id") == mane_id)
        tick = s.get("tick"); frame = s.get("frame")
        if b: boss_tn_at.append((tick, frame, b.get("tn")))
        if m: mane_tn_at.append((tick, frame, m.get("tn")))
        if prev and b and m:
            pb, pm = prev
            db = (b.get("tm_f") or 0) - (pb.get("tm_f") or 0)
            dm = (m.get("tm_f") or 0) - (pm.get("tm_f") or 0)
            # only count pure-accumulation windows (both rising, no reset/cast)
            if db > 0.5 and dm > 0.5:
                ratios.append(dm / db)
            # discrete fill: Maneater tm_f jumped UP across a window where boss barely moved
            if dm > 0 and db > 0 and (dm / db) > 2.2:  # >> the 288/190=1.52 baseline
                fills.append((tick, round(dm, 2), round(db, 2), round(dm/db, 2)))
        if b and m:
            prev = (b, m)

    if ratios:
        ratios.sort()
        import statistics
        print(f"\n## Maneater/boss stamina-gain ratio (= speed ratio)")
        print(f"   n={len(ratios)} median={statistics.median(ratios):.3f} "
              f"mean={statistics.mean(ratios):.3f}  (288/190={288/190:.3f})")
        print(f"   p10={ratios[len(ratios)//10]:.3f} p90={ratios[len(ratios)*9//10]:.3f}")

    # 2) Action ratio
    bt = max(t for _,_,t in boss_tn_at if t is not None)
    mt = max(t for _,_,t in mane_tn_at if t is not None)
    print(f"\n## Action counts: Maneater tn={mt}  boss tn={bt}  ratio={mt/bt:.3f}")

    # 3) Boss turn spacing (frames between boss tn increments) — uniform or gapped?
    print(f"\n## Boss turn spacing (frames between boss tn++):")
    last = None; gaps = []
    for tick, frame, tn in boss_tn_at:
        if tn is None or frame is None: continue
        if last is not None and tn == last[2] + 1:
            gaps.append(frame - last[1])
        if last is None or tn > last[2]:
            last = (tick, frame, tn)
    if gaps:
        import statistics
        print(f"   n={len(gaps)} frames/turn: median={statistics.median(gaps):.0f} "
              f"min={min(gaps)} max={max(gaps)} mean={statistics.mean(gaps):.1f}")
        print(f"   spacing samples: {gaps[:20]}")
        # If uniform -> boss is steady 190. If late gaps grow -> effective slowdown.

    # 4) Discrete fills on Maneater
    print(f"\n## Discrete TM-fill candidates on Maneater (gain ratio > 2.2):")
    if fills:
        for f in fills[:20]: print(f"   tick {f[0]}: Mane +{f[1]} vs boss +{f[2]} (ratio {f[3]})")
    else:
        print("   NONE — Maneater gains stamina purely by speed (no discrete fills).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
