"""Extract per-DEF mitigation factors from `def_reduction` hook events.

The mod's BattleHook_DefReduction patches the game's
`DamageCalculator.DamageReductionByDefence(EffectContext, BattleHero, Fixed)`
postfix, capturing (target_def, returned_factor_raw) per call. The
returned value is a Fixed (32.32 raw long); divide by 2^32 to get the
0..1 multiplier the game multiplies into damage.

This tool reads any tick_log_*.json containing `def_reduction` events
and writes:
    data/derived/def_factor_lookup.json

The lookup is the literal game function output for every observed DEF
value. Sim consumers can either look up by DEF directly or use it as
a calibration/regression target for closed-form fits.

Usage:
    python3 tools/extract_def_factor.py tick_log_*.json [--output PATH]

Empirical observations (today's capture, 2026-05-02):
  - For each DEF, the *most-common* `out_raw` is the base formula value
    (other values come from skill-level IgnoreDef modifiers stacking
    on top of the base DEF before the formula runs).
  - Implied C in `factor = C/(C+DEF)` drifts:
        DEF= 608  factor=0.72135  → C=1574
        DEF=1520  factor=0.46487  → C=1320
        DEF=1941  factor=0.38295  → C=1205
        DEF=2974  factor=0.26702  → C=1083
    C decreasing systematically with DEF means the literal formula has
    additional terms beyond `C/(C+DEF)`. Likely candidates: attacker
    level, attacker rarity, or a non-trivial functional form.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXED_SCALE = 1 << 32  # Plarium's 32.32 fixed-point divisor


def load_def_events(path: Path) -> list[dict]:
    """Read def_reduction events from a tick log."""
    d = json.loads(path.read_text(encoding="utf-8"))
    ticks = d.get("ticks", [])
    return [t for t in ticks if isinstance(t, dict)
            and t.get("kind") == "def_reduction"
            and t.get("t_def") is not None
            and t.get("out_raw") is not None]


def build_lookup(events: list[dict]) -> dict:
    """Group events by t_def. For each DEF, the most-common out_raw is
    the BASE factor (no IgnoreDef applied). Other values are skill-
    modified variants — recorded but not selected as base.
    """
    by_def: dict[int, Counter] = defaultdict(Counter)
    for e in events:
        by_def[e["t_def"]][e["out_raw"]] += 1

    table: list[dict] = []
    for t_def in sorted(by_def):
        counts = by_def[t_def]
        base_raw, n_base = counts.most_common(1)[0]
        factor = base_raw / FIXED_SCALE
        # Implied C if the formula were factor = C/(C+DEF).
        c_implied = None
        if 0 < factor < 1:
            c_implied = round(factor * t_def / (1 - factor))
        variants = [
            {"out_raw": orw, "factor": orw / FIXED_SCALE, "n": n}
            for orw, n in counts.most_common()
            if orw != base_raw
        ]
        table.append({
            "t_def":          t_def,
            "base_factor":    factor,
            "base_out_raw":   base_raw,
            "n_base":         n_base,
            "n_total":        sum(counts.values()),
            "C_if_simple":    c_implied,
            "variants":       variants,  # IgnoreDef-modified hits
        })
    return {
        "row_count":   len(table),
        "by_def":      table,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tick_log", help="Path to a tick_log_*.json with "
                                       "def_reduction events.")
    ap.add_argument("--output", "-o",
                    default=str(PROJECT_ROOT / "data" / "derived"
                                / "def_factor_lookup.json"))
    args = ap.parse_args()

    src = Path(args.tick_log)
    if not src.exists():
        print(f"file not found: {src}", file=sys.stderr)
        return 1
    events = load_def_events(src)
    if not events:
        print(f"no def_reduction events in {src.name} — make sure the mod "
              "version with the DefReduction Harmony hook is deployed and "
              "you've captured a battle since.", file=sys.stderr)
        return 1

    lookup = build_lookup(events)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_tick_log": src.name,
        "event_count": len(events),
        **lookup,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Brief stdout report.
    print(f"# {len(events)} def_reduction events from {src.name}")
    print(f"# wrote {out_path}\n")
    print(f"{'t_def':>6} {'factor':>10} {'C_if_simple':>12} "
          f"{'n':>4}  variants")
    print("-" * 60)
    for row in lookup["by_def"]:
        c = row["C_if_simple"]
        c_s = "—" if c is None else str(c)
        v_s = (f" +{len(row['variants'])} ignore-def" if row["variants"] else "")
        print(f"{row['t_def']:>6} {row['base_factor']:>10.5f} "
              f"{c_s:>12} {row['n_base']:>4}{v_s}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
