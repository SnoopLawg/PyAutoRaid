"""Pick + equip the gear that best matches a target HH-team stat profile.

Greedy slot-by-slot picker:
  1. Pull /all-artifacts (full vault, no limit).
  2. Exclude CB-locked artifacts (heroes in `LOCKED_HEROES`).
  3. Pick the best piece per slot per hero, ordered by SPD primary first
     (boots), then SPD-substat-rich slots, then accessories.
  4. Score each candidate: weighted advance toward target stats with caps
     (ACC>=250 wasted, CR>=100 wasted).
  5. Equip via /swap-artifact (or /activate-artifact for vault pieces).
  6. Print before/after stats per hero.

Designed for the Teodor + Corvis Dragon Hard 10 build initially but the
TARGETS dict is parameterizable.
"""
from __future__ import annotations
import json, sys, time, urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MOD_BASE = "http://localhost:6790"

# Stat IDs (game-internal): 1=HP 2=ATK 3=DEF 4=SPD 5=RES 6=ACC 7=CR 8=CD
STAT = {1:'HP',2:'ATK',3:'DEF',4:'SPD',5:'RES',6:'ACC',7:'CR',8:'CD'}
SLOT = {1:'Helm',2:'Chest',3:'Glove',4:'Boots',5:'Weapon',6:'Shield',
        7:'Ring',8:'Amulet',9:'Banner'}

# CB team — gear on these heroes is OFF-LIMITS
LOCKED_HEROES = {
    # CB roster — gear tuned for boss UNM stall
    15120, 18607, 2643, 13615, 5692,  # Maneater, Demytha, Ninja, Geo, Venomage
    # Dragon roster (preset 5 DH3v3) — gear tuned for Hard 3 stall (HP/RES heavy)
    11615, 19723, 11506, 13250,        # Teodor, Mithrala, Artak, Cardiel
    # Spider preset (id=2 SpiderH10) — gear tuned for burst Spider Hard 10 attempt
    13076, 3890,                       # Sicia Flametongue, Coldheart
    # Spider/ITF flex — used by SpiderH9 (preset 7), keep existing gear
    12641,                             # Gnut
}

# Target stats for HH Iron Twins Force Stage 15 — 5-hero comp
# (team_id 795bbf13-..., 18-0 wr, 83-second / 36-turn avg).
# Mithrala + Gnut already in other presets — keep their gear; only
# gear the 3 "fresh" heroes (Alsgor, Rathalos, Ultimate Deathknight).
TARGETS = {
    'Alsgor Crimsonhorn':   dict(HP=85692, ATK=2612, DEF=4053, SPD=214,
                                  CR=45,   CD=137,  RES=194, ACC=329),
    'Rathalos Blademaster': dict(HP=48593, ATK=6235, DEF=3350, SPD=237,
                                  CR=80,   CD=284,  RES=214, ACC=322),
    'Ultimate Deathknight': dict(HP=55621, ATK=2907, DEF=5042, SPD=223,
                                  CR=101,  CD=222,  RES=347, ACC=247),
}

MASTERIES = {
    'Alsgor Crimsonhorn':   [500113, 500122, 500121, 500131, 500132, 500143,
                             500141, 500152, 500151, 500161, 500313, 500324,
                             500333, 500343, 500353],
    'Rathalos Blademaster': [500113, 500212, 500221, 500232, 500242, 500253,
                             500122, 500124, 500131, 500132, 500141, 500151,
                             500161, 500152, 500142],
    'Ultimate Deathknight': [500113, 500122, 500132, 500141, 500151, 500161,
                             500312, 500322, 500321, 500331, 500333, 500344,
                             500341, 500351, 500354],
}

SKIP_GEAR_HEROES = set()

# Balanced 5-hero DPS+tank weighting for Iron Twins Force Stage 15.
# CR boosted vs CD because crits are gating — high CD without crits = wasted.
WEIGHTS = {'SPD': 5.0, 'CR': 4.0, 'CD': 2.5, 'HP': 2.0, 'ATK': 1.8,
           'DEF': 1.5, 'ACC': 1.5, 'RES': 1.0}
CAPS = {'CR': 100}


def get(path):
    with urllib.request.urlopen(f"{MOD_BASE}{path}", timeout=30) as r:
        return json.loads(r.read())


def cap(stat, value):
    return min(value, CAPS.get(stat, value))


def _resolve_value(stat_name: str, raw_value: float, flat: bool, base_stats: dict) -> float:
    """Convert a primary/substat value to its effective stat contribution.

    Mod data has a `flat` flag that's mostly correct (HP/ATK/DEF primaries on
    pct-roll slots like Gloves/Chest/Boots are flat=False meaning %-of-base).
    BUT for CR/CD/SPD/ACC/RES, the in-game additive behavior means the value
    is always an absolute count regardless of how the mod flags it (CR primary
    glove +60 means CR goes 15→75, NOT 15→24). Override flat=True for these
    stats so the score function doesn't multiply by base.
    """
    if stat_name in ('CR', 'CD', 'SPD', 'ACC', 'RES'):
        return raw_value  # always absolute
    if not flat:
        return base_stats.get(stat_name, 0) * raw_value / 100
    return raw_value


def score_artifact(art: dict, current_totals: dict, target: dict, base_stats: dict) -> float:
    """Score how much this artifact advances the hero toward target.

    Counts primary + each substat by weighted ratio of (gained_stat / remaining_gap).
    Returns 0 if the artifact provides no useful stats vs target."""
    score = 0.0
    p = art.get('primary') or {}
    if p.get('stat'):
        nm = STAT.get(p['stat'])
        if nm:
            v = _resolve_value(nm, p.get('value', 0), p.get('flat', True), base_stats)
            t = cap(nm, target.get(nm, 0))
            if t > 0:
                gap = max(1, t - current_totals.get(nm, 0))
                w = WEIGHTS.get(nm, 0.5)
                # gain capped at gap (no benefit beyond target)
                score += w * min(v, gap) / gap
    for s in (art.get('substats') or []):
        nm = STAT.get(s.get('stat'))
        if not nm: continue
        v = _resolve_value(nm, s.get('value', 0), s.get('flat', True), base_stats)
        t = cap(nm, target.get(nm, 0))
        if t > 0:
            gap = max(1, t - current_totals.get(nm, 0))
            w = WEIGHTS.get(nm, 0.5)
            score += w * min(v, gap) / gap
    return score


def apply_artifact_to_totals(art: dict, totals: dict, base: dict):
    """Add this artifact's stat contribution to running totals."""
    p = art.get('primary') or {}
    if p.get('stat'):
        nm = STAT.get(p['stat'])
        if nm:
            v = _resolve_value(nm, p.get('value', 0), p.get('flat', True), base)
            totals[nm] = totals.get(nm, 0) + v
    for s in (art.get('substats') or []):
        nm = STAT.get(s.get('stat'))
        if not nm: continue
        v = _resolve_value(nm, s.get('value', 0), s.get('flat', True), base)
        totals[nm] = totals.get(nm, 0) + v


def _greedy_pick(target, hero_base, pool, force_speed_4pc):
    """Single pass — either with or without 4pc-Speed enforcement. Pure
    function: doesn't mutate the passed-in pool (returns picks list)."""
    from itertools import combinations
    local_pool = list(pool)
    totals = dict(hero_base)
    totals.setdefault('CR', 15)
    totals.setdefault('CD', 50)
    picks = []
    speed_slots: set[int] = set()

    if force_speed_4pc:
        speed_main = [a for a in local_pool if a.get('set') == 4 and a.get('kind') in (1,2,3,4,5,6)]
        best_speed_by_slot: dict[int, dict] = {}
        for slot_id in (1,2,3,4,5,6):
            cands = [a for a in speed_main if a.get('kind') == slot_id]
            if not cands: continue
            cands.sort(key=lambda a: -score_artifact(a, totals, target, hero_base))
            best_speed_by_slot[slot_id] = cands[0]
        if len(best_speed_by_slot) >= 4:
            best_combo, best_score = None, -1
            for combo in combinations(best_speed_by_slot.keys(), 4):
                sc = sum(score_artifact(best_speed_by_slot[s], totals, target, hero_base) for s in combo)
                if sc > best_score:
                    best_score = sc; best_combo = combo
            speed_picks = [best_speed_by_slot[s] for s in best_combo]
            for a in speed_picks:
                picks.append(a); local_pool.remove(a)
                apply_artifact_to_totals(a, totals, hero_base)
            totals['SPD'] = totals.get('SPD', 0) + hero_base.get('SPD', 0) * 0.30
            speed_slots = set(best_combo)

    remaining_main = [s for s in (1,2,3,4,5,6) if s not in speed_slots]
    for slot_id in remaining_main + [9, 7, 8]:
        cands = [a for a in local_pool if a.get('kind') == slot_id]
        if not cands: continue
        cands.sort(key=lambda a: -score_artifact(a, totals, target, hero_base))
        best = cands[0]
        picks.append(best); local_pool.remove(best)
        apply_artifact_to_totals(best, totals, hero_base)
    return totals, picks, speed_slots


def pick_loadout(hero_name: str, target: dict, hero_base: dict,
                 pool: list[dict]) -> tuple[dict, list[dict]]:
    """Try BOTH approaches (4pc Speed enforced vs no-enforce); keep
    whichever achieves higher SPD (most important stat for Dragon).

    Mutates pool to remove the chosen picks."""
    # Try with 4pc Speed enforced
    totals_a, picks_a, slots_a = _greedy_pick(target, hero_base, pool, force_speed_4pc=True)
    # Try without
    totals_b, picks_b, slots_b = _greedy_pick(target, hero_base, pool, force_speed_4pc=False)
    if totals_a.get('SPD', 0) >= totals_b.get('SPD', 0):
        chosen = "4pc-Speed"
        totals, picks = totals_a, picks_a
    else:
        chosen = "best-stats (no 4pc)"
        totals, picks = totals_b, picks_b
    print(f"  picker chose: {chosen}  (SPD with 4pc: {totals_a.get('SPD',0):.0f}, "
          f"without: {totals_b.get('SPD',0):.0f})")
    # Mutate pool to remove our final picks
    for a in picks:
        if a in pool: pool.remove(a)
    return totals, picks


def equip_artifact(hero_id: int, art_id: int, owner_id: int = 0) -> dict:
    """Equip artifact `art_id` on `hero_id`. If currently on another hero,
    use SwapArtifactCmd. If unequipped, use ActivateArtifactCmd."""
    if owner_id and owner_id != hero_id:
        url = f"{MOD_BASE}/swap-artifact?hero_id={hero_id}&from_id=0&to_id={art_id}&owner_id={owner_id}"
    else:
        url = f"{MOD_BASE}/equip?hero_id={hero_id}&artifact_id={art_id}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def main():
    # 1. Pull full vault + heroes
    arts = get('/all-artifacts').get('artifacts', [])
    heroes = get('/all-heroes').get('heroes', [])
    name_to_inst = {}
    for h in heroes:
        nm = h.get('name')
        if not nm:
            continue
        # Prefer highest-grade-then-level instance (allows 5/50 fillers
        # when no 6/60 of that hero exists — needed for HH comps that
        # specify a hero we haven't yet ascended to 6/60).
        existing = name_to_inst.get(nm)
        rank = (h.get('grade', 0), h.get('level', 0))
        existing_rank = (existing.get('grade', 0), existing.get('level', 0)) if existing else (-1, -1)
        if rank > existing_rank:
            name_to_inst[nm] = h
    n6 = sum(1 for h in name_to_inst.values() if h.get('grade') == 6)
    print(f"vault: {len(arts)} artifacts;  heroes (best instance, 6*={n6}): {len(name_to_inst)}")

    # Hero base stats from /hero-computed-stats
    hcs = get('/hero-computed-stats').get('heroes', [])
    hcs_by_id = {int(h['id']): h for h in hcs}

    # 2. Available pool — exclude CB-locked
    pool = [a for a in arts if a.get('hero_id') not in LOCKED_HEROES]
    print(f"available pool (CB-locked excluded): {len(pool)}")

    # 3. Pick loadouts.
    # Order matters — greedy picker drains the best pieces from the
    # shared pool. Process DPS heroes (high target CR/CD) first so
    # they get priority on CR-primary gloves and CD-rich substats;
    # tanks consume the leftover stat-distributed pieces fine.
    def _dps_priority(target):
        # Higher target CR/CD/ATK = more "DPS-y" → process earlier
        return -(target.get('CR', 0) + target.get('CD', 0) / 2 + target.get('ATK', 0) / 50)
    target_order = sorted(TARGETS.items(), key=lambda kv: _dps_priority(kv[1]))
    plans = {}
    for hero_name, target in target_order:
        h = name_to_inst.get(hero_name)
        if not h:
            print(f"ERROR: {hero_name} not found at 6*", file=sys.stderr)
            continue
        # Get "starting point" stats — everything EXCEPT artifact contribution.
        # Base + mastery + blessing + arena + affinity + faction guardians +
        # area bonuses ARE in the hero before any artifacts are applied.
        # /hero-computed-stats provides each separately so we can sum non-artifact.
        h_full = hcs_by_id.get(int(h['id']), {})
        base = dict(h_full.get('base_computed', {}))
        for col in ['blessing_bonus','empower_bonus','classic_arena_bonus',
                    'affinity_bonus','mastery_bonus','faction_guardians_bonus','area_bonus']:
            b = h_full.get(col, {}) or {}
            for k in list(base.keys()):
                base[k] = base.get(k, 0) + b.get(k, 0)
        # Convert CR/CD from decimal -> percent (game stores as 0.15 / 0.50)
        if base.get('CR', 0) <= 1.5: base['CR'] = base.get('CR', 0) * 100
        if base.get('CD', 0) <= 5: base['CD'] = base.get('CD', 0) * 100

        totals, picks = pick_loadout(hero_name, target, base, pool)
        plans[hero_name] = (h['id'], totals, picks, base)

        print(f"\n=== {hero_name} (instance {h['id']}, base SPD {base.get('SPD',0):.0f}) ===")
        print(f"  achieved HP  {totals.get('HP',0):.0f}   / target {target['HP']}")
        print(f"  achieved DEF {totals.get('DEF',0):.0f}     / target {target['DEF']}")
        print(f"  achieved SPD {totals.get('SPD',0):.0f}    / target {target['SPD']}")
        print(f"  achieved ACC {totals.get('ACC',0):.0f}    / target {target['ACC']}")
        print(f"  achieved RES {totals.get('RES',0):.0f}    / target {target['RES']}")
        print(f"  achieved CR  {totals.get('CR',0):.0f}%    / target {target['CR']}%")
        print(f"  achieved CD  {totals.get('CD',0):.0f}%    / target {target['CD']}%")
        print(f"  picks (slot -> art_id):")
        for a in sorted(picks, key=lambda a: a.get('kind', 0)):
            slot = SLOT.get(a.get('kind'), '?')
            p = a.get('primary') or {}
            ps = STAT.get(p.get('stat'), '?')
            pv = p.get('value', 0)
            owner = a.get('hero_id', 0)
            print(f"    {slot:7}  art#{a.get('id'):>5}  rank{a.get('rank')}  "
                  f"set{a.get('set'):>3}  {ps}+{pv:.0f}  owner:{owner}")
    return plans


def equip_via_mod(hero_id: int, art_id: int) -> dict:
    """The mod's /equip endpoint handles both cases (vault->hero, hero->hero swap)
    via Activate or Swap command internally. Idempotent — returns ok:true if
    already equipped.
    """
    url = f"{MOD_BASE}/equip?hero_id={hero_id}&artifact_id={art_id}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def reset_masteries(hero_id: int) -> dict:
    """Wipes all masteries on a hero (refunds scrolls). Required before
    re-applying a fresh tree from HH spec."""
    try:
        with urllib.request.urlopen(f"{MOD_BASE}/reset-masteries?hero_id={hero_id}", timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def open_mastery(hero_id: int, mastery_id: int) -> dict:
    """Unlock a single mastery node. The mod resolves prerequisites
    automatically (clicks tree-up if needed). Costs scrolls."""
    try:
        with urllib.request.urlopen(
            f"{MOD_BASE}/open-mastery?hero_id={hero_id}&mastery_id={mastery_id}",
            timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def apply_masteries_for_hero(hero_id: int, hero_name: str, target_mids: list[int]):
    """Reset + apply HH's exact 15-mastery list. Returns (n_ok, n_err)."""
    print(f"\n  reset masteries on {hero_name}…")
    r = reset_masteries(hero_id)
    if r.get('error'):
        print(f"    reset ERR: {r.get('error')}")
        return 0, 1
    print(f"    reset ok")
    time.sleep(0.5)
    n_ok = n_err = 0
    for mid in target_mids:
        r = open_mastery(hero_id, mid)
        if r.get('ok') or r.get('opened'):
            n_ok += 1
        else:
            err = r.get('error', str(r))[:120]
            print(f"    mastery {mid}: ERR {err}")
            n_err += 1
        time.sleep(0.3)
    print(f"    masteries: {n_ok}/{len(target_mids)} applied, {n_err} errors")
    return n_ok, n_err


def apply_plans(plans: dict, preset_name: str | None = None,
                hero_names_for_preset: list[str] | None = None,
                apply_masteries: bool = True):
    """Equip picked pieces, apply HH masteries, then create preset."""
    n_ok = 0
    n_err = 0
    print("\n=== APPLYING GEAR ===")
    for hero_name, (h_id, totals, picks, base) in plans.items():
        print(f"\n{hero_name} (instance {h_id}):")
        for a in sorted(picks, key=lambda a: a.get('kind', 0)):
            slot = SLOT.get(a.get('kind'), '?')
            r = equip_via_mod(h_id, a['id'])
            if r.get('ok'):
                msg = r.get('msg') or 'equipped'
                print(f"  {slot:7}  art#{a['id']:>5}  -> {msg}")
                n_ok += 1
            else:
                err = r.get('error', str(r))[:80]
                print(f"  {slot:7}  art#{a['id']:>5}  ERROR: {err}")
                n_err += 1
            time.sleep(0.2)
    print(f"\nequip results: {n_ok} ok, {n_err} errors")

    if apply_masteries:
        print("\n=== APPLYING MASTERIES ===")
        for hero_name, (h_id, _t, _p, _b) in plans.items():
            mids = MASTERIES.get(hero_name)
            if not mids:
                print(f"\n  {hero_name}: no mastery target defined, skipping")
                continue
            apply_masteries_for_hero(h_id, hero_name, mids)

    if preset_name and hero_names_for_preset:
        heroes_csv = ",".join(hero_names_for_preset)
        import subprocess
        print(f"\n=== CREATING PRESET '{preset_name}' ===")
        result = subprocess.run(
            ["python3", str(PROJECT_ROOT / "tools" / "preset_manage.py"),
             "create", "--name", preset_name, "--heroes", heroes_csv, "--type", "1"],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"preset creation FAILED: {result.stderr}", file=sys.stderr)


if __name__ == "__main__":
    plans = main()
    if "--apply" in sys.argv:
        skip_preset = "--no-preset" in sys.argv
        skip_masteries = "--no-masteries" in sys.argv
        apply_plans(
            plans,
            preset_name=None if skip_preset else "ITForce15",
            hero_names_for_preset=None if skip_preset else
                # Full 5-hero list; TARGETS only re-gears 3 heroes,
                # but the preset includes Mithrala + Gnut as-is.
                ['Alsgor Crimsonhorn', 'Rathalos Blademaster',
                 'Mithrala Lifebane', 'Gnut', 'Ultimate Deathknight'],
            apply_masteries=not skip_masteries,
        )
    else:
        print("\n(dry run — call with --apply to equip + masteries + preset)")
