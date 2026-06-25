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

    # Stratified random sampling: shuffle each pair's combo list and
    # round-robin one team at a time, so the candidate pool gets even
    # representation across all (survivor, sustainer) anchor pairs.
    # Without this, alphabetically-first DPS heroes dominate the
    # output because itertools.combinations yields them first.
    import random as _rand
    for i, (surv, sust, combos) in enumerate(pair_combos):
        # Stable shuffle: each pair gets a deterministic but distinct
        # shuffle order based on its index, so re-runs are reproducible.
        rng = _rand.Random(0x5eed ^ hash((surv, sust)))
        shuffled = list(combos)
        rng.shuffle(shuffled)
        pair_combos[i] = (surv, sust, shuffled)

    max_iters = max(len(c[2]) for c in pair_combos) if pair_combos else 0
    for i in range(max_iters):
        for surv, sust, combos in pair_combos:
            if i >= len(combos):
                continue
            team = sorted({surv, sust, *combos[i]})
            if len(team) < 5:
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


def load_dwj_tunes() -> list[dict]:
    """Return every DWJ tune as `{name, slug, slots: [hero_names]}`.
    DWJ slots are dicts with a `hero` field (not `name`).
    """
    p = PROJECT_ROOT / "data" / "dwj" / "parsed" / "tunes.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    tunes = data if isinstance(data, list) else (data.get("tunes") or [])
    out: list[dict] = []
    for tune in tunes:
        if not isinstance(tune, dict):
            continue
        slots = tune.get("slots") or []
        names = []
        for s in slots:
            if isinstance(s, dict):
                n = s.get("hero") or s.get("name")
                if isinstance(n, str): names.append(n)
            elif isinstance(s, str):
                names.append(s)
        if 4 <= len(names) <= 6:
            out.append({
                "name":  tune.get("name") or tune.get("slug") or "?",
                "slug":  tune.get("slug") or "",
                "slots": names[:5],
            })
    return out


def predict_score(team: list[str],
                  roles_by_hero: dict[str, set[str]]) -> float:
    """Cheap heuristic for team strength — used to prune candidates
    before paying the full sim cost.

    Adds:
      - role-coverage points (UK/BD/heal/def_down/weaken/poisoner/burner)
      - synergy bonuses (poisoner + poison_sens, etc.)

    GAME-TRUTH ONLY: this is a pre-sim prune over our own game-derived role
    tags. No external tier list (HellHades/DWJ) feeds the score — the full
    sim (damage + survival) is the authoritative ranking. (M7 B2.)
    """
    team_roles: list[set[str]] = [roles_by_hero.get(h, set()) for h in team]
    flat: set[str] = set().union(*team_roles)
    score = 0.0
    # Role coverage
    if "uk" in flat:        score += 5
    if "bd" in flat:        score += 4
    if "heal" in flat or "shield" in flat or "heal_active" in flat: score += 3
    if "def_down" in flat:  score += 4
    if "weaken" in flat:    score += 3
    if "poisoner" in flat:  score += 2
    if "burner" in flat:    score += 2
    if "ally_protect" in flat: score += 1
    # DPS counts: more DPS = more output potential
    score += sum(1 for r in team_roles if "dps" in r) * 0.5
    # Synergy: poison + poison_sens
    if "poisoner" in flat and any("poison_sens" in r for r in team_roles):
        score += 2
    return score


# DWJ slot strings can be EITHER a literal hero name OR a role
# placeholder. Map common placeholders to the role tag set the
# explorer's role classifier produces.
DWJ_PLACEHOLDER_ROLES = {
    "DPS":                    {"dps"},
    "DPS/Cleanser":           {"dps", "heal_active"},
    "DPS (Extra Turn)":       {"dps", "extra_turn"},
    "Cleanser":               {"heal_active"},
    "Pain Keeper":            {"cd_reset"},
    "Painkeeper":             {"cd_reset"},
    "Slowboi":                {"dps"},   # low-SPD DPS — sub with any DPS
    "Stun Target":            {"dps"},
    "Stun Target - Any DPS":  {"dps"},
    "Stun Target (DPS)":      {"dps"},
    "Unkillable Champion (4 turn CD)": {"uk"},
    "Tower/Santa":            {"uk"},   # both are UK providers
    "Fast Maneater":          {"uk"},   # specific Maneater config
    "Slow Maneater":          {"uk"},
}

# Some DWJ slot strings are literal hero names with typos / extra
# whitespace. Map them to the canonical name.
DWJ_NAME_FIXUPS = {
    "Deacon ":           "Deacon Armstrong",
    "Deacon Armstron":   "Deacon Armstrong",
    "Maneater_2":        "Maneater",  # Budget UK uses two
}


def fill_dwj_tune_with_owned(slots: list[str], owned: set[str],
                              roles_by_hero: dict[str, set[str]]) -> list[str] | None:
    """Resolve a DWJ tune's slot list to a concrete owned-hero team.

    Each slot is either:
      - A literal hero name (resolve directly).
      - A name with typo/whitespace (canonicalize via DWJ_NAME_FIXUPS).
      - A role placeholder (find the highest-rated owned hero with
        the placeholder's role tags).

    Returns None when any slot can't be filled OR the resulting team
    has fewer than 5 distinct members.
    """
    team: list[str] = []
    used: set[str] = set()
    for raw_slot in slots:
        # Normalize: strip whitespace, apply name fixups
        slot = DWJ_NAME_FIXUPS.get(raw_slot, raw_slot.strip())
        # Direct hero match
        if slot in owned and slot not in used:
            team.append(slot)
            used.add(slot)
            continue
        # Same hero allowed twice (2x Maneater pattern) — Budget-UK
        if slot in owned:
            # Already used, but DWJ tune lists it again
            team.append(slot)
            continue
        # Role placeholder
        target_roles = DWJ_PLACEHOLDER_ROLES.get(slot)
        if target_roles is None:
            target_roles = roles_by_hero.get(slot, set())
        if not target_roles:
            return None
        # Find best owned hero for this role
        candidates = [h for h in owned
                      if (target_roles & roles_by_hero.get(h, set()))
                      and h not in used]
        if not candidates:
            return None
        # Pick the hero with the most-overlapping role set
        candidates.sort(key=lambda h: -len(target_roles & roles_by_hero.get(h, set())))
        chosen = candidates[0]
        team.append(chosen)
        used.add(chosen)
    if len(set(team)) < 4:  # CB tunes can have a 2x-Maneater duplicate
        return None
    return team[:5]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=30,
                    help="Show top N teams by sim damage (default 30)")
    ap.add_argument("--cb-element", default="magic",
                    choices=("magic", "force", "spirit", "void"))
    ap.add_argument("--candidate-pool", type=int, default=5000,
                    help="Total feasible teams to enumerate (default 5000)")
    ap.add_argument("--sample", type=int, default=2000,
                    help="Randomly sample this many from the candidate "
                         "pool to prune-score (default 2000)")
    ap.add_argument("--sim-top", type=int, default=200,
                    help="Number of pre-scored teams to actually sim "
                         "(default 200). Score-based prune to keep "
                         "runtime tractable.")
    ap.add_argument("--include-unowned", action="store_true",
                    help="Include potential (unowned) heroes — uses "
                         "ungeared baseline / vault-best gear")
    ap.add_argument("--include-dwj", action="store_true", default=True,
                    help="Also sim every DWJ tune populated with the "
                         "user's roster (substitute missing slots with "
                         "same-role owned heroes). Default on.")
    ap.add_argument("--no-dwj", action="store_false", dest="include_dwj",
                    help="Skip the DWJ-tune coverage")
    ap.add_argument("--novel-margin", type=float, default=0.10,
                    help="Mark a team `novel` only when its damage "
                         "exceeds the closest matching DWJ tune by at "
                         "least this fraction (default 0.10 = 10%%)")
    ap.add_argument("--use-current-gear", action="store_true",
                    help="Skip the artifact optimizer; sim with each "
                         "hero's CURRENTLY equipped artifacts. "
                         "Damage values then match your calibrated "
                         "sim (~36M for the active CB team) instead "
                         "of the potential-projection baseline.")
    ap.add_argument("--explore-speed", action="store_true",
                    help="Drop the UK_ME_SPD_RANGE cap on UK heroes "
                         "during gear optimization so the optimizer "
                         "can find non-standard speed tunes.")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    import random
    random.seed(args.seed)

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

    # Discover roles for EVERY hero in the static catalog (not just
    # eligible) — we need unowned-hero role data so DWJ-tune fill can
    # find substitutes for slots the user doesn't own.
    print("Classifying heroes by role...", file=sys.stderr)
    roles_by_hero: dict[str, set[str]] = {}
    for name, ht_entry in ht_by_name.items():
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
        max_combos=args.candidate_pool,
        has_double_maneater=has_2me,
    )
    # Random sample to break alphabetical bias from the round-robin
    if len(candidates) > args.sample:
        candidates = random.sample(candidates, args.sample)
    print(f"  {len(candidates)} candidate team combos (after sampling)",
          file=sys.stderr)

    # Source DWJ tunes — populate with user's roster where slots are
    # role placeholders. dwj_sigs holds the FILLED team frozensets so
    # the novelty check below can look them up by hero name.
    dwj_tunes = load_dwj_tunes()
    dwj_sigs: set[frozenset] = set()
    dwj_tune_teams: list[tuple[list[str], dict]] = []  # (team, tune_meta)
    for tune in dwj_tunes:
        if args.include_dwj:
            filled = fill_dwj_tune_with_owned(tune["slots"],
                                                set(eligible),
                                                roles_by_hero)
            if filled:
                team_sorted = sorted(filled)
                dwj_tune_teams.append((team_sorted, tune))
                dwj_sigs.add(frozenset(team_sorted))
    print(f"  DWJ tunes: {len(dwj_tunes)} known, "
          f"{len(dwj_tune_teams)} fillable from owned roster",
          file=sys.stderr)

    # Score-based prune: rank candidates by predict_score, keep top
    # `sim-top` for full sim. DWJ-tune teams always get simmed (they're
    # the baseline we compare novel candidates against).
    print("Pre-scoring candidates (game-truth role coverage; no tier list)...",
          file=sys.stderr)
    scored: list[tuple[float, list[str]]] = []
    for team in candidates:
        s = predict_score(team, roles_by_hero)
        scored.append((s, team))
    scored.sort(key=lambda x: -x[0])
    sim_pool = [t for _, t in scored[:args.sim_top]]
    # Add DWJ teams (de-dup against pool)
    sim_keys = {frozenset(t) for t in sim_pool}
    for team, _ in dwj_tune_teams:
        if frozenset(team) not in sim_keys:
            sim_pool.append(team)
            sim_keys.add(frozenset(team))
    print(f"  pruned to {len(sim_pool)} teams "
          f"({len(scored[:args.sim_top])} top-scored + "
          f"{len(sim_pool) - len(scored[:args.sim_top])} DWJ)",
          file=sys.stderr)

    if not candidates:
        print("No feasible teams found. Try --include-unowned or relax --min-roles.")
        return 1

    # Sim each
    print(f"Simulating ({len(sim_pool)} teams)...", file=sys.stderr)
    elem_id = {"magic": 1, "force": 2, "spirit": 3, "void": 4}[args.cb_element]
    if args.use_current_gear:
        # Calibrated path: real gear + Maneater A3-opener (cb_sim main
        # convention). Closer to in-game damage but still ~50% below
        # calibrated sim until /presets are applied per hero.
        from cb_sim import evaluate_team_calibrated as _sim_fn
        def _run(team):
            return _sim_fn(team, cb_element=elem_id,
                            use_current_gear=True,
                            force_affinity=True)
    else:
        # Default: potential gear via cb_potential.simulate_team.
        from cb_potential import simulate_team as _sim_fn
        def _run(team):
            return _sim_fn(team, cb_element=elem_id,
                            explore_speed=args.explore_speed)

    results: list[tuple[list[str], float, dict]] = []
    for i, team in enumerate(sim_pool):
        if i % 50 == 0 and i:
            print(f"  ... {i}/{len(sim_pool)}", file=sys.stderr)
        try:
            res = _run(team)
            total = float(res.get("total", 0)) if "error" not in res else 0.0
        except Exception:
            total = 0.0
            res = {"error": "sim failed"}
        results.append((team, total, res))

    results.sort(key=lambda r: -r[1])

    # Build "closest DWJ damage" lookup so we can flag novel teams
    # (those that BEAT their closest DWJ tune by --novel-margin).
    # Closest DWJ for a team = the DWJ tune with the most overlapping
    # heroes. If no overlap, novel margin is meaningless → mark "yes".
    dwj_team_dmgs: dict[frozenset, float] = {}
    for team, dmg, _ in results:
        if frozenset(team) in dwj_sigs:
            dwj_team_dmgs[frozenset(team)] = dmg

    def closest_dwj_damage(team: list[str]) -> float:
        team_set = frozenset(team)
        best_overlap = 0
        best_dmg = 0.0
        for dwj_sig, dwj_dmg in dwj_team_dmgs.items():
            overlap = len(team_set & dwj_sig)
            if overlap > best_overlap:
                best_overlap = overlap
                best_dmg = dwj_dmg
        return best_dmg

    # Output
    top = results[: args.top]
    print(f"\n=== Top {len(top)} CB teams (cb_element={args.cb_element}) ===\n")
    print(f"{'#':>3} {'damage':>10} {'novel':>7} {'vs_dwj':>10}  team")
    print("-" * 110)
    for i, (team, total, res) in enumerate(top, 1):
        sig = frozenset(team)
        is_dwj_match = sig in dwj_sigs
        if is_dwj_match:
            novel_flag = "DWJ"
            vs = "—"
        else:
            ref = closest_dwj_damage(team)
            if ref > 0:
                margin = (total - ref) / ref
                if margin >= args.novel_margin:
                    novel_flag = f"+{margin*100:.0f}%"
                else:
                    novel_flag = "no"
                vs = f"{ref/1_000_000:.1f}M"
            else:
                novel_flag = "yes"
                vs = "n/a"
        team_str = ", ".join(team)
        print(f"{i:>3} {total/1_000_000:>8.1f}M {novel_flag:>7} {vs:>10}  {team_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
