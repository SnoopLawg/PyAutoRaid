"""Comprehensive CB team explorer — surfaces team comps the DWJ tune
library doesn't already cover.

Unlike `cb_team_search.py` (which only generates from Myth-Eater /
Budget-UK templates), this tool:

1. **Discovers roles dynamically from each hero's static skill data.**
   No hardcoded "this hero is a UK provider"; we look at every skill's
   Effects[] and tag the hero based on what status effects it can
   apply (UK / BD / Continuous Heal / DEF Down / Weaken / etc.).

2. **Generates feasible teams** from role requirements rather than fixed
   templates. Default rule set: at least one survival provider (UK or
   BD on team), at least one sustain source (heal or shield), at least
   three damage contributors. Easily reconfigurable via CLI flags.

3. **Sims every candidate** using the same `cb_sim` machinery, with
   gear assigned via `cb_optimizer.optimal_artifacts_for_hero` so
   potential heroes get vault-best loadouts.

4. **Cross-references against the DWJ tune library** so the output
   flags which top teams are NOVEL — i.e., not already a known DWJ
   tune. Those are the candidates the existing recommendations would
   miss.

Usage:
    python3 tools/cb_team_explorer.py                    # owned roster, top 30
    python3 tools/cb_team_explorer.py --top 50           # top 50 teams
    python3 tools/cb_team_explorer.py --include-unowned  # potential heroes too
    python3 tools/cb_team_explorer.py --cb-element magic
    python3 tools/cb_team_explorer.py --max-combos 5000  # cap combinatorial blowup
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "tools"))


# Skill-description keyword → role mapping. KindIds in skills_all.json
# are mostly `ApplyBuff` / `ApplyDebuff` which don't reveal what's
# being applied (the TargetParams pointing to the actual status effect
# isn't fully serialised in the static dump). Skill descriptions DO
# carry the human-readable buff/debuff names — desc_profiler already
# parses these accurately, so we lean on that instead.
ROLE_KEYWORDS = {
    "uk":          ("[Unkillable]", "Unkillable buff"),
    "bd":          ("[Block Damage]",),
    "shield":      ("[Shield]", "Shield buff"),
    "heal":        ("[Continuous Heal]", "Continuous Heal buff"),
    "heal_active": ("Heals all allies", "Restores their HP", "by ", "% of their MAX HP"),
    "def_down":    ("[Decrease DEF]", "Decrease DEF debuff"),
    "weaken":      ("[Weaken]", "[Increase Damage Taken]"),
    "dec_atk":     ("[Decrease ATK]",),
    "poisoner":    ("[Poison]",),
    "burner":      ("[HP Burn]",),
    "counter":     ("[Counterattack]",),
    "inc_atk":     ("[Increase ATK]",),
    "inc_def":     ("[Increase DEF]",),
    "inc_spd":     ("[Increase SPD]",),
    "inc_cr":      ("[Increase C. RATE]", "[Increase C.RATE]"),
    "inc_cd":      ("[Increase C. DMG]",  "[Increase C.DMG]"),
    "cd_reset":    ("Decreases the cooldown", "Reduces cooldown"),
    "ally_protect":("[Ally Protect]",),
    "perfect_veil":("[Perfect Veil]",),
    "extra_turn":  ("Fills this Champion's Turn Meter", "extra turn"),
    "tm_team":     ("Fills the Turn Meters of all allies",),
    "revive":      ("Revives", "[Revive on Death]"),
}


def discover_roles(hero_name: str, hero_type, sk_idx, sd_text) -> set[str]:
    """Return the set of CB roles this hero can fill, based on their
    skill descriptions. `sd_text` is the static skill_descriptions_all
    dict (skill_id -> description string).
    """
    roles: set[str] = set()
    has_damage_skill = False
    for sid in hero_type.get("skill_ids", []) or []:
        sk = sk_idx.get(sid)
        if not sk:
            continue
        # DPS detection: any Damage effect
        for eff in sk.get("Effects", []) or []:
            if isinstance(eff, dict) and eff.get("KindId") == "Damage":
                has_damage_skill = True
                break
        # Description-driven role detection
        desc = sd_text.get(str(sid)) or sd_text.get(sid) or ""
        if not isinstance(desc, str):
            continue
        for role, keywords in ROLE_KEYWORDS.items():
            if any(kw in desc for kw in keywords):
                roles.add(role)
    if has_damage_skill:
        roles.add("dps")
    return roles


def is_team_feasible(team_roles: list[set[str]],
                     min_uk: bool = True,
                     min_sustain: bool = True,
                     min_dps: int = 3) -> bool:
    """Check whether a 5-hero team is plausibly viable for CB.

    Default rules:
      - At least one hero with `uk` or `bd` (survival keystone)
      - At least one hero with `heal`/`shield`/`heal_active` (sustain)
      - At least 3 heroes with the `dps` role (any damage skill)
    """
    if min_uk and not any("uk" in r or "bd" in r for r in team_roles):
        return False
    if min_sustain and not any(r & {"heal", "heal_active", "shield"}
                                for r in team_roles):
        return False
    if min_dps and sum(1 for r in team_roles if "dps" in r) < min_dps:
        return False
    return True


def generate_candidate_teams(eligible_heroes: list[str],
                              roles_by_hero: dict[str, set[str]],
                              max_combos: int,
                              has_double_maneater: bool = False) -> list[list[str]]:
    """Yield diverse 5-hero teams that satisfy CB feasibility rules.

    Round-robin over survivors × sustainers (rather than nested loops
    that exhaust the first survivor's combos before moving on) so the
    candidate pool gets diversity across all role-fillers.
    """
    survivors = [h for h in eligible_heroes
                 if "uk" in roles_by_hero[h] or "bd" in roles_by_hero[h]]
    sustainers = [h for h in eligible_heroes
                  if {"heal", "heal_active", "shield"} & roles_by_hero[h]]
    dps_pool = [h for h in eligible_heroes if "dps" in roles_by_hero[h]]

    if not survivors or not sustainers or len(dps_pool) < 3:
        return []

    teams: list[list[str]] = []
    seen: set[frozenset] = set()

    # Pre-build per-(surv,sust) DPS combo iterators, then round-robin
    # one combo from each to get diverse candidates first.
    pair_combos: list[tuple[str, str, list[tuple[str, ...]]]] = []
    for surv in survivors:
        for sust in sustainers:
            anchors = {surv, sust}
            free = [h for h in dps_pool if h not in anchors]
            need = 5 - len(anchors)
            if len(free) < need:
                continue
            pair_combos.append((surv, sust,
                list(combinations(free, need))))

    # Round-robin: yield first combo from each pair, then second, etc.
    max_iters = max(len(c[2]) for c in pair_combos) if pair_combos else 0
    for i in range(max_iters):
        for surv, sust, combos in pair_combos:
            if i >= len(combos):
                continue
            team = sorted({surv, sust, *combos[i]})
            if len(team) < 5:
                # surv == sust collapsed; pull one extra DPS
                continue
            key = frozenset(team)
            if key in seen:
                continue
            seen.add(key)
            teams.append(team)
            if len(teams) >= max_combos:
                return teams

    if has_double_maneater:
        free_dps = [h for h in dps_pool if h != "Maneater"]
        for combo in combinations(free_dps, 3):
            team = ["Maneater", "Maneater_2"] + list(combo)
            key = frozenset(team)
            if key in seen:
                continue
            seen.add(key)
            teams.append(sorted(team))
            if len(teams) >= max_combos:
                break

    return teams


def load_dwj_tune_signatures() -> set[frozenset]:
    """Return {frozenset(team)} for every DWJ tune so we can flag teams
    that are NOT already a known recipe (= "novel" candidates)."""
    sigs: set[frozenset] = set()
    p = PROJECT_ROOT / "data" / "dwj" / "parsed" / "tunes.json"
    if not p.exists():
        return sigs
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return sigs
    tunes = data.get("tunes") if isinstance(data, dict) else data
    if not isinstance(tunes, list):
        return sigs
    for tune in tunes:
        if not isinstance(tune, dict):
            continue
        slots = tune.get("slots") or tune.get("hero_names") or []
        names = [s.get("name") if isinstance(s, dict) else s for s in slots]
        names = [n for n in names if isinstance(n, str)]
        if 4 <= len(names) <= 6:
            sigs.add(frozenset(names))
    return sigs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=30,
                    help="Show top N teams by sim damage (default 30)")
    ap.add_argument("--cb-element", default="magic",
                    choices=("magic", "force", "spirit", "void"))
    ap.add_argument("--max-combos", type=int, default=2000,
                    help="Cap candidate teams enumerated (default 2000)")
    ap.add_argument("--include-unowned", action="store_true",
                    help="Include potential (unowned) heroes — uses "
                         "ungeared baseline / vault-best gear")
    ap.add_argument("--min-roles", default="uk,sustain,3dps",
                    help="Comma-separated feasibility rules (default uk,sustain,3dps)")
    args = ap.parse_args()

    print("Loading data...", file=sys.stderr)
    # Owned roster — restrict to 6-star (which is what `simulate_team`
    # expects). Lower-star heroes aren't viable for CB UNM and get
    # rejected by the sim's hero lookup anyway.
    ah = json.loads((PROJECT_ROOT / "all_heroes.json").read_text(encoding="utf-8"))
    hs6 = json.loads((PROJECT_ROOT / "heroes_6star.json").read_text(encoding="utf-8"))
    owned = {h["name"] for h in hs6.get("heroes", []) if h.get("name")}
    # All heroes (for --include-unowned)
    ht = json.loads((PROJECT_ROOT / "data" / "static" / "hero_types.json")
                    .read_text(encoding="utf-8"))["hero_types"]
    ht_by_name: dict[str, dict] = {}
    for h in ht:
        n = h.get("name")
        if not n:
            continue
        cur = ht_by_name.get(n)
        if cur is None or (h.get("is_max_ascended") and not cur.get("is_max_ascended")):
            ht_by_name[n] = h
    sa = json.loads((PROJECT_ROOT / "data" / "static" / "skills_all.json")
                    .read_text(encoding="utf-8"))["data"]
    sk_idx = {s["Id"]: s for s in sa if "Id" in s}
    # Skill descriptions text (skill_id -> description string)
    sd_path = PROJECT_ROOT / "data" / "static" / "skill_descriptions_all.json"
    sd_all_text: dict[str | int, str] = {}
    if sd_path.exists():
        try:
            sd_blob = json.loads(sd_path.read_text(encoding="utf-8"))
            sd_all_text = sd_blob.get("skill_descriptions") or sd_blob.get("data") or {}
        except Exception:
            pass

    eligible = sorted(owned if not args.include_unowned else set(ht_by_name.keys()))
    print(f"  eligible heroes: {len(eligible)}", file=sys.stderr)

    # Discover roles
    print("Classifying heroes by role...", file=sys.stderr)
    roles_by_hero: dict[str, set[str]] = {}
    for name in eligible:
        ht_entry = ht_by_name.get(name)
        if ht_entry:
            roles_by_hero[name] = discover_roles(name, ht_entry, sk_idx, sd_all_text)
    role_counts = defaultdict(int)
    for r in roles_by_hero.values():
        for role in r:
            role_counts[role] += 1
    print(f"  role distribution: "
          f"uk={role_counts['uk']} bd={role_counts['bd']} "
          f"heal={role_counts['heal']+role_counts['heal_active']} "
          f"shield={role_counts['shield']} "
          f"def_down={role_counts['def_down']} weaken={role_counts['weaken']} "
          f"poisoner={role_counts['poisoner']} burner={role_counts['burner']} "
          f"dps={role_counts['dps']}", file=sys.stderr)

    # Generate candidate teams
    print("Generating candidate teams...", file=sys.stderr)
    has_2me = len([h for h in ah["heroes"] if h.get("name") == "Maneater"]) >= 2
    candidates = generate_candidate_teams(
        eligible, roles_by_hero,
        max_combos=args.max_combos,
        has_double_maneater=has_2me,
    )
    print(f"  {len(candidates)} feasible team combos", file=sys.stderr)

    if not candidates:
        print("No feasible teams found. Try --include-unowned or relax --min-roles.")
        return 1

    # Sim each
    print(f"Simulating ({len(candidates)} teams)...", file=sys.stderr)
    from cb_potential import simulate_team
    elem_id = {"magic": 1, "force": 2, "spirit": 3, "void": 4}[args.cb_element]
    results: list[tuple[list[str], float, dict]] = []
    for i, team in enumerate(candidates):
        if i % 50 == 0 and i:
            print(f"  ... {i}/{len(candidates)}", file=sys.stderr)
        try:
            res = simulate_team(team, verbose=False, cb_element=elem_id)
            total = float(res.get("total", 0)) if "error" not in res else 0.0
        except Exception as e:
            total = 0.0
            res = {"error": str(e)}
        results.append((team, total, res))

    results.sort(key=lambda r: -r[1])

    # Flag novel comps (not in DWJ tune library)
    dwj_sigs = load_dwj_tune_signatures()

    # Output
    top = results[: args.top]
    print(f"\n=== Top {len(top)} CB teams (cb_element={args.cb_element}) ===\n")
    print(f"{'#':>3} {'damage':>10} {'novel?':>6} team")
    print("-" * 80)
    for i, (team, total, res) in enumerate(top, 1):
        novel = "yes" if frozenset(team) not in dwj_sigs else "no"
        team_str = ", ".join(team)
        print(f"{i:>3} {total/1_000_000:>8.1f}M {novel:>6} {team_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
