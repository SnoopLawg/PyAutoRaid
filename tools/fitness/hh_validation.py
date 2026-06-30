"""M5 PHASE 5b — validate the 5a heuristic ranking against the HellHades tier
signal.

The 5a heuristic scores every location, but only `clan_boss` has a true
outcome simulator (cb_sim). For the other 11 locations there is no check that
the *ordering* the heuristic produces is sane. This module supplies that
sanity signal by correlating `fitness.score()` against the per-location
HellHades champion tier ratings.

    validate_against_hh(location, comps) -> {rho, n, agree_pct, notes, ...}

HellHades is an ADDITIVE reference (see CLAUDE.md): a *cross-check*, never
ground truth. A strong positive rank-correlation says "our heuristic ranks
comps the way a respected community profiler ranks their members" — a good
smell test. A weak/negative rho is a flag to investigate the heuristic for
that location, NOT proof the heuristic is wrong (HH rates heroes in a
vacuum; we score whole-comp synergy).

The HH signal for a comp is the mean (or sum) of its members' HH rating at
the location. Members HH doesn't rate are skipped (and noted).

Data: `data/hh/parsed/tierlist.json` — 1013 rows, each
`{name, clan_boss, hydra, chimera, dragon, fire_knight, ice_golem, spider,
  spider_hard, dragon_hard, ..., iron_twins, sand_devil, phantom_grove, ...}`.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

TIERLIST_PATH = ROOT / "data" / "hh" / "parsed" / "tierlist.json"

# Numeric per-location rating keys present in the HH tierlist rows. (Non-rating
# fields like id/hero_id/name/form/faction/url are excluded.)
HH_LOCATION_KEYS = {
    "overall_user", "clan_boss", "hydra", "chimera", "amius",
    "spider", "dragon", "fire_knight", "ice_golem",
    "spider_hard", "dragon_hard", "fire_knight_hard", "ice_golem_hard",
    "iron_twins", "sand_devil", "phantom_grove",
    "kuldath", "agreth", "borgoth", "sorath", "iragoth", "grythion",
}

# fitness/boss_constraints canonical location -> HH rating key. Locations HH
# does not track (arena, faction_wars, the DT affinity-keeps) map to None and
# yield a "no HH signal" note rather than an error.
FITNESS_TO_HH = {
    "clan_boss": "clan_boss",
    "hydra": "hydra",
    "chimera": "chimera",
    "dragon": "dragon",
    "spider": "spider",
    "fire_knight": "fire_knight",
    "ice_golem": "ice_golem",
    # Doom Tower clash bosses / PvP / FW: HH has no comparable per-hero column.
    "arena": None,
    "faction_wars": None,
    "magma_dragon": None,
    "eternal_dragon": None,
    "frost_spider": None,
    "nether_spider": None,
    "scarab_king": None,
    "celestial_griffin": None,
    "dark_fae": None,
}

_index: dict[str, dict] | None = None


def _load_index() -> dict[str, dict]:
    global _index
    if _index is None:
        rows = json.loads(TIERLIST_PATH.read_text(encoding="utf-8"))
        idx: dict[str, dict] = {}
        for row in rows:
            name = row.get("name")
            if name and name not in idx:  # first form wins (form==1)
                idx[name] = row
        _index = idx
    return _index


def _norm_loc(location: str) -> str:
    return str(location).strip().lower().replace("-", "_").replace(" ", "_")


def resolve_hh_location(location: str) -> str | None:
    """Map a fitness/boss_constraints location onto an HH rating key.

    Accepts an HH key directly ("spider_hard"), a fitness canonical key
    ("clan_boss"), or an alias resolvable via boss_constraints ("cb", "ig").
    Returns the HH key, or None if HH has no column for that location.
    """
    key = _norm_loc(location)
    if key in HH_LOCATION_KEYS:
        return key
    if key in FITNESS_TO_HH:
        return FITNESS_TO_HH[key]
    # Try boss_constraints alias resolution -> canonical -> HH key.
    try:
        import boss_constraints as bc
        for canon in bc.list_locations():
            rec = bc.get_constraints(canon)
            aliases = [a.lower() for a in (rec.get("aliases") or [])]
            if key == canon or key in aliases:
                return FITNESS_TO_HH.get(canon)
    except Exception:
        pass
    return None


def hh_rating(name: str, hh_key: str) -> float | None:
    """HH rating for `name` at `hh_key`, or None if hero/column absent."""
    row = _load_index().get(name)
    if row is None:
        # tolerate duplicate-instance suffix ("Maneater_2")
        if "_" in name:
            head = name.rpartition("_")[0]
            row = _load_index().get(head) if head else None
        if row is None:
            return None
    val = row.get(hh_key)
    return float(val) if isinstance(val, (int, float)) else None


def hh_team_signal(comp, hh_key: str, agg: str = "mean") -> float | None:
    """Aggregate HH rating across comp members rated at `hh_key`.

    Returns None when no member is rated (so the comp is excluded from the
    correlation rather than skewing it with a zero).
    """
    vals = [hh_rating(n, hh_key) for n in comp]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    if agg == "sum":
        return float(sum(vals))
    return float(sum(vals) / len(vals))


# --------------------------------------------------------------------------- #
# Rank-correlation (tie-aware Spearman = Pearson on average ranks).
# --------------------------------------------------------------------------- #
def _avg_ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0  # average rank for the tie group
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman_rho(a: list[float], b: list[float]) -> float | None:
    """Tie-aware Spearman rho, or None if undefined (n<2 or no variance)."""
    n = len(a)
    if n < 2 or len(b) != n:
        return None
    ra, rb = _avg_ranks(a), _avg_ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    va = sum((ra[i] - ma) ** 2 for i in range(n))
    vb = sum((rb[i] - mb) ** 2 for i in range(n))
    if va == 0 or vb == 0:
        return None
    rho = cov / math.sqrt(va * vb)
    return max(-1.0, min(1.0, rho))


def ordering_agreement(a: list[float], b: list[float]) -> float | None:
    """Pairwise concordance (Kendall-style): fraction of comp pairs that the
    two scores order the same way. Ties (in either series) are not counted.
    """
    n = len(a)
    if n < 2:
        return None
    concordant = comparable = 0
    for i in range(n):
        for j in range(i + 1, n):
            da, db = a[i] - a[j], b[i] - b[j]
            if da == 0 or db == 0:
                continue
            comparable += 1
            if (da > 0) == (db > 0):
                concordant += 1
    if comparable == 0:
        return None
    return concordant / comparable


# --------------------------------------------------------------------------- #
# Public entry
# --------------------------------------------------------------------------- #
def _as_comps(comps) -> list[list[str]]:
    """Accept a list of comps (list-of-lists) or a list of single hero names
    (each treated as a 1-hero comp). Returns a list of comps."""
    if not comps:
        return []
    first = comps[0]
    if isinstance(first, str):
        return [[c] for c in comps]
    return [list(c) for c in comps]


def validate_against_hh(location: str, comps, context: dict | None = None,
                        agg: str = "mean") -> dict:
    """Correlate `fitness.score()` against the HH tier signal at `location`.

    `comps`   a list of comps (each a list of hero names) OR a list of single
              hero names (each scored as a 1-hero comp).
    `agg`     how member HH ratings aggregate into a comp signal ("mean"/"sum").

    Returns:
        {
          location, hh_key, agg,
          n,                  # comps with both a fitness and an HH signal
          rho,                # Spearman rank-correlation (None if undefined)
          agree_pct,          # pairwise ordering agreement (None if undefined)
          paired,             # [{comp, fitness, hh_signal}, ...]
          skipped,            # comps dropped for lacking an HH signal
          notes,              # human-readable caveats
        }
    """
    from . import score  # public API only (no internals)

    context = dict(context or {})
    hh_key = resolve_hh_location(location)
    notes: list[str] = [
        "HellHades is an additive cross-check, not ground truth (CLAUDE.md): "
        "rho is a sanity signal on the heuristic's ordering."
    ]
    comps_n = _as_comps(comps)

    if hh_key is None:
        notes.append(f"no HH rating column for location '{location}' — "
                     "cannot validate (arena / faction_wars / DT clash bosses).")
        return {"location": location, "hh_key": None, "agg": agg, "n": 0,
                "rho": None, "agree_pct": None, "paired": [], "skipped": comps_n,
                "notes": notes}

    fit_vals: list[float] = []
    hh_vals: list[float] = []
    paired: list[dict] = []
    skipped: list[list[str]] = []
    for comp in comps_n:
        signal = hh_team_signal(comp, hh_key, agg=agg)
        if signal is None:
            skipped.append(comp)
            continue
        f = score(comp, location, context)
        fit_vals.append(f["fitness"])
        hh_vals.append(signal)
        paired.append({"comp": comp, "fitness": f["fitness"],
                       "hh_signal": round(signal, 4)})

    rho = spearman_rho(fit_vals, hh_vals)
    agree = ordering_agreement(fit_vals, hh_vals)
    n = len(paired)
    if n < 2:
        notes.append(f"only {n} comp(s) had an HH signal at '{hh_key}' — "
                     "need >=2 for a correlation.")
    if skipped:
        notes.append(f"{len(skipped)} comp(s) skipped (no HH-rated member).")

    return {"location": location, "hh_key": hh_key, "agg": agg, "n": n,
            "rho": rho, "agree_pct": agree, "paired": paired,
            "skipped": skipped, "notes": notes}


if __name__ == "__main__":  # pragma: no cover - manual smoke
    # run with: python -m tools.fitness.hh_validation
    strong = ["Maneater", "Demytha", "Ninja", "Geomancer", "Venomage"]
    mid = ["Apothecary", "High Khatun", "Ninja", "Venomage", "Frozen Banshee"]
    junk = ["Ranger", "Mystic Hand", "Militia", "Cataphract", "Crossbowman"]
    out = validate_against_hh("clan_boss", [strong, mid, junk], {"cb_element": 1})
    print(json.dumps(out, indent=2))
