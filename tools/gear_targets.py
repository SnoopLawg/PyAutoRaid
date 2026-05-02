"""Per-location gear target presets — Phase 6 schema + loader.

A target preset is a JSON file at `data/targets/<slug>.json` that
describes what gear *shape* a hero needs to fight a specific location.
The optimizer reads these to score artifact assignments / suggest
swaps from the vault.

Schema (see `data/targets/cb_unm.json` for a worked example):

    {
      "slug": "cb-unm",                    # matches BossProfile slug family
      "label": "Clan Boss UNM",
      "role_targets": {                    # one entry per role flavor
        "debuffer": {
          "stat_floors": {                 # absolute minimums
            "ACC": 230,
            "SPD": 170,
            "HP_pct_of_base": 1.5
          },
          "stat_caps": {                   # absolute maximums (rarely set)
            "SPD": 250
          },
          "preferred_sets": ["Lifesteal", "Accuracy", "Toxic"],
          "primary_by_slot": {             # main-stat preference per slot
            "weapon": "ATK",
            "helmet": "HP",
            "chest": "HP",
            "gauntlets": "HP",
            "boots": "SPD",
            "ring": "ATK",
            "amulet": "ACC",
            "banner": "ACC"
          },
          "substats_priority": [           # weighted scoring order
            "ACC", "SPD", "HP", "RES"
          ],
          "notes": "ACC>=230 floor (UNM RES=250 minus desc bonus); SPD band 170-189 for Budget UK tunes"
        },
        "stunner": { ... },
        "unkillable": { ... }
      },
      "global": {                          # fallback / shared knobs
        "set_bonus_value_per_pct": 100,    # how much 1% set bonus is worth
        "min_artifact_rank": 5
      }
    }

The role_targets keys are free-form strings — `gear_solve.py` accepts
`--role <name>` to pick which set of stat floors to apply. Default is
the first role in the file.

Loaders:
    list_targets() -> list[str]
    load_target(slug) -> dict (raises KeyError on miss)
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGETS_DIR = PROJECT_ROOT / "data" / "targets"


def list_targets() -> list[str]:
    """Return all available target slugs (filename minus .json)."""
    if not TARGETS_DIR.exists():
        return []
    return sorted(p.stem for p in TARGETS_DIR.glob("*.json"))


def load_target(slug: str) -> dict:
    """Load a target preset by slug. Raises KeyError if not found."""
    p = TARGETS_DIR / f"{slug}.json"
    if not p.exists():
        raise KeyError(f"unknown target {slug!r} — try list_targets()")
    return json.loads(p.read_text(encoding="utf-8"))


def get_role(target: dict, role: str | None = None) -> dict:
    """Pick the role config from a target preset.

    If role is None, returns the first role in role_targets (insertion
    order is preserved in JSON-loaded dicts on Python 3.7+).
    """
    roles = target.get("role_targets") or {}
    if not roles:
        return {}
    if role is None:
        return next(iter(roles.values()))
    if role in roles:
        return roles[role]
    raise KeyError(f"role {role!r} not in target {target.get('slug')!r}; "
                   f"available: {list(roles.keys())}")


def evaluate_gear(stats: dict, target: dict, role: str | None = None) -> dict:
    """Check a hero's current stats against a target's floors / caps.

    Returns a verdict dict:
        {
            "role": "debuffer",
            "passes": bool,
            "violations": [{"stat": "ACC", "have": 200, "need_floor": 230, "delta": -30}, ...],
            "headroom": [{"stat": "SPD", "have": 245, "cap": 250, "delta": +5}, ...]
        }

    Stats input expects keys "HP", "ATK", "DEF", "SPD", "RES", "ACC",
    "CR", "CD" — the shape produced by `tools/hero_stats.py`.
    `HP_pct_of_base` is a synthetic floor: e.g. 1.5 means "HP must be
    >= 1.5× base HP".
    """
    role_cfg = get_role(target, role)
    floors = role_cfg.get("stat_floors") or {}
    caps = role_cfg.get("stat_caps") or {}

    violations: list[dict] = []
    headroom: list[dict] = []

    _BASE_PCT_SUFFIX = "_pct_of_base"
    for stat, need in floors.items():
        # Synthetic floor: "<STAT>_pct_of_base" → require total stat
        # >= need × base value. Useful when "high HP" should scale with
        # the hero's base rather than be an absolute number.
        if stat.endswith(_BASE_PCT_SUFFIX):
            base_stat = stat[: -len(_BASE_PCT_SUFFIX)]
            base_val = stats.get(f"base_{base_stat}") or 0
            if base_val <= 0:
                continue
            have = stats.get(base_stat, 0)
            need_abs = need * base_val
            if have < need_abs:
                violations.append({
                    "stat": base_stat,
                    "have": have,
                    "need_floor": int(need_abs),
                    "rule": f"{stat}={need}× (base={base_val})",
                    "delta": int(have - need_abs),
                })
            continue
        have = stats.get(stat, 0)
        if have < need:
            violations.append({
                "stat": stat,
                "have": have,
                "need_floor": need,
                "delta": have - need,
            })

    for stat, cap in caps.items():
        have = stats.get(stat, 0)
        if have > cap:
            headroom.append({
                "stat": stat,
                "have": have,
                "cap": cap,
                "delta": have - cap,
            })

    return {
        "role": role or (next(iter((target.get("role_targets") or {}).keys()), None)),
        "passes": not violations,
        "violations": violations,
        "headroom": headroom,
    }
