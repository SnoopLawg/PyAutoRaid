"""Build a glance-gate lookup: for every skill referenced by hero_profiles_game.json,
record which effect indices have `Relation.ActivateOnGlancingHit == False` AND a
stable per-effect SIGNATURE for each of those gated effects.

Output: data/static/glance_gates.json
  {
    "gates":           { "skill_id": [gated effect indices], ... },
    "gate_signatures": { "skill_id": [gated effect signatures], ... }
  }

Glance gates are the mechanism by which weak-affinity attacks "miss" secondary
effects (TM boosts, debuff placements, DoT applications). On a glance:
  - The damage roll still applies (at glance penalty, -30% per gameplay.json)
  - Effects with ActivateOnGlancingHit=false are SKIPPED for that cast

The per-effect SIGNATURE is what lets cb_sim gate the RIGHT effect instead of
collapsing to a skill-level boolean. cb_sim iterates PROFILED effects (sim
debuff/buff names), not raw skills_all Effects[] by index — so a bare index
can't be matched. The signature bridges the two namespaces:
  - ApplyDebuff/ApplyBuff -> the sim debuff/buff name from STATUS_EFFECT_MAP
    (e.g. TypeId 470 -> "hp_burn", 151 -> "def_down")
  - any other KindId      -> the KindId string itself (e.g. "IncreaseStamina",
    "ReduceStamina", "ForceStatusEffectTick", "ReduceCooldown")
cb_sim computes the SAME signature for each profiled effect (its params["debuff"]
sim name) and dampens ONLY when that signature is in the skill's gated set.

This fixes Geo A3 (48804): only effect 3 (IncreaseStamina, the TM-burst) is
gated. The old skill-level boolean wrongly dampened A3's HP-burn + Weaken
PLACEMENTS (effects 0/1, aog=true → NOT gated), gutting Geo's burn + downstream
deflect. The TM-burst itself stays gated (cb_sim handles it via self_tm_fill).

For MEN's Force-day failure: Ninja + Venomage (Magic) glance ~35% on the Force
boss. ALL their debuff placements are aog=false (def_down, hp_burn, poison,
dec_atk), so they STAY gated — Force survival is preserved.

Usage:
    python3 tools/build_glance_gates.py            # live mod (depth=8)
    python3 tools/build_glance_gates.py --offline  # from depth=8 snapshot
    # → data/static/glance_gates.json
"""
from __future__ import annotations
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from status_effect_map import STATUS_EFFECT_MAP
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from status_effect_map import STATUS_EFFECT_MAP

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = PROJECT_ROOT / "hero_profiles_game.json"
OUT_PATH = PROJECT_ROOT / "data" / "static" / "glance_gates.json"
SNAPSHOT_PATH = (PROJECT_ROOT / "data" / "static" / "snapshots"
                 / "all_skills_depth8.json")
MOD_BASE = "http://localhost:6790"


def fetch_skill(skill_id: int, retries: int = 2):
    """Fetch a single skill at depth=8 from the live mod."""
    url = (f"{MOD_BASE}/static-export?path=SkillData.SkillTypeById."
           f"Item%5B{skill_id}%5D&depth=8")
    last_err = None
    for _ in range(retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            time.sleep(1.0)
    raise RuntimeError(f"fetch skill_id={skill_id} failed: {last_err}")


def gated_indices(skill: dict) -> list[int]:
    """Return effect indices where Relation.ActivateOnGlancingHit is False."""
    indices = []
    for i, eff in enumerate(skill.get("Effects") or []):
        rel = eff.get("Relation") or {}
        if rel.get("ActivateOnGlancingHit") is False:
            indices.append(i)
    return indices


def effect_signatures(eff: dict) -> list[str]:
    """Stable signature(s) for one effect, in cb_sim's namespace.

    ApplyDebuff/ApplyBuff -> the sim debuff/buff name(s) (STATUS_EFFECT_MAP),
    one per StatusEffectInfos entry; falls back to "type_<id>" for unmapped
    type ids, or the KindId if there are no status-effect infos. Any other
    KindId -> the KindId string itself. cb_sim matches profiled debuff effects
    by their sim name, so ApplyDebuff signatures line up with params["debuff"].
    """
    kind = eff.get("KindId") or ""
    if kind in ("ApplyDebuff", "ApplyBuff"):
        asep = eff.get("ApplyStatusEffectParams") or {}
        seis = asep.get("StatusEffectInfos") or []
        sigs: list[str] = []
        for sei in seis:
            tid = sei.get("TypeId")
            info = STATUS_EFFECT_MAP.get(tid)
            if info:
                sigs.append(info[0])
            elif tid is not None:
                sigs.append(f"type_{tid}")
        if sigs:
            return sigs
        return [kind]
    return [kind]


def gated_signatures(skill: dict, indices: list[int]) -> list[str]:
    """Union of effect_signatures() over the gated effect indices."""
    effs = skill.get("Effects") or []
    sigs: set[str] = set()
    for i in indices:
        if 0 <= i < len(effs):
            sigs.update(effect_signatures(effs[i]))
    return sorted(sigs)


def build_offline(skill_ids: set[int]):
    """Compute (gates, gate_signatures) from the depth=8 snapshot — no mod."""
    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    skills = snap.get("skills") or {}
    gates: dict[str, list[int]] = {}
    sigs: dict[str, list[str]] = {}
    missing: list[int] = []
    for sid in sorted(skill_ids):
        skill = skills.get(str(sid))
        if not skill:
            missing.append(sid)
            continue
        gi = gated_indices(skill)
        if gi:
            gates[str(sid)] = gi
            sigs[str(sid)] = gated_signatures(skill, gi)
    return gates, sigs, missing


def main() -> int:
    if not PROFILES_PATH.exists():
        print(f"missing {PROFILES_PATH} — run build_hero_profiles.py first")
        return 1
    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))

    # Collect every (hero, skill_id) pair we care about.
    skill_ids: set[int] = set()
    for hero, prof in profiles.items():
        for sk in prof.get("skills") or []:
            sid = sk.get("id")
            if isinstance(sid, int):
                skill_ids.add(sid)

    print(f"profiles cover {len(profiles)} heroes, {len(skill_ids)} unique skills")

    offline = "--offline" in sys.argv
    # Auto-fall back to the snapshot if the mod isn't up but we have one.
    if not offline:
        try:
            with urllib.request.urlopen(f"{MOD_BASE}/status", timeout=5) as r:
                json.loads(r.read())
        except Exception as e:
            if SNAPSHOT_PATH.exists():
                print(f"mod not reachable ({e}); using depth=8 snapshot")
                offline = True
            else:
                print(f"mod not reachable at {MOD_BASE}: {e}")
                return 2

    failures: list[tuple[int, str]] = []
    sigs: dict[str, list[str]] = {}

    if offline:
        gates, sigs, missing = build_offline(skill_ids)
        source = f"depth=8 snapshot ({SNAPSHOT_PATH.name})"
    else:
        gates = {}
        missing = []
        progress_every = 50
        for i, sid in enumerate(sorted(skill_ids), 1):
            try:
                skill = fetch_skill(sid)
            except Exception as e:
                failures.append((sid, str(e)))
                continue
            if not skill or skill.get("Id") != sid:
                missing.append(sid)
                continue
            gi = gated_indices(skill)
            if gi:
                gates[str(sid)] = gi
                sigs[str(sid)] = gated_signatures(skill, gi)
            if i % progress_every == 0:
                print(f"  {i}/{len(skill_ids)} fetched; {len(gates)} gated so far")
        source = "live mod /static-export at depth=8"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "source": source,
            "skills_scanned": len(skill_ids),
            "skills_with_gates": len(gates),
            "skills_missing": len(missing),
            "fetch_failures": len(failures),
        },
        "gates": gates,
        "gate_signatures": sigs,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    print(f"scanned: {len(skill_ids)} skills")
    print(f"with glance gates: {len(gates)}")
    print(f"with signatures: {len(sigs)}")
    print(f"missing from static: {len(missing)}")
    print(f"fetch failures: {len(failures)}")
    print(f"wrote: {OUT_PATH}")
    if failures[:5]:
        print("first failures:")
        for sid, err in failures[:5]:
            print(f"  {sid}: {err[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
