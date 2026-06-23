"""Milestone 5 — Per-location roster gap analysis.

The "what should I pull / build next" tool. For each location, compares the
synergy axes a good team NEEDS (from the recommender's location profiles)
against what the OWNED roster can cover, and lists the strongest UNOWNED
heroes that would fill each gap.

Pure analysis over game-truth data — no sim, no calibration risk:
    data/m5_synergy.jsonl      (provider/needs tags)
    tools/m5_recommender.py    (LOCATION_PROFILES — required axes)
    data/hh/parsed/tierlist.json (HH per-location rating, additive signal)
    heroes_all.json            (owned roster)

CLI:
    python3 tools/m5_roster_gaps.py                 # all locations summary
    python3 tools/m5_roster_gaps.py --location cb   # one location, with pull suggestions
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Reuse the recommender's data loaders + location profiles (single source).
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "m5_recommender", ROOT / "tools" / "m5_recommender.py")
_rec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rec)

OUT_DOC = ROOT / "docs" / "m5_roster_gaps.md"


def analyze(location: str) -> dict:
    prof = _rec.LOCATION_PROFILES[location]
    syn = _rec._load_synergy()
    hh = _rec._load_hh()
    axes = prof["axes"]
    hh_key = prof["hh_key"]

    owned = {h["name"] for h in _rec._load_owned() if h["name"] in syn}

    def hh_rating(name: str) -> float:
        row = hh.get(name.lower())
        v = row.get(hh_key) if row else None
        return float(v) if isinstance(v, (int, float)) else 0.0

    # For each axis: how many OWNED heroes provide it, and the best unowned ones.
    axis_report = {}
    for axis, weight in axes.items():
        owned_providers = [n for n in owned if axis in set(syn[n]["provides"])]
        unowned_providers = [
            n for n, r in syn.items()
            if n not in owned and axis in set(r["provides"])
        ]
        # Rank unowned by HH rating for this location.
        unowned_ranked = sorted(unowned_providers, key=lambda n: -hh_rating(n))
        axis_report[axis] = {
            "weight": weight,
            "owned_count": len(owned_providers),
            "owned_providers": sorted(owned_providers),
            "top_unowned": [(n, hh_rating(n)) for n in unowned_ranked[:5]],
        }

    # Gaps = axes with 0 owned providers, weighted.
    gaps = sorted(
        [(a, d) for a, d in axis_report.items() if d["owned_count"] == 0],
        key=lambda kv: -kv[1]["weight"],
    )
    thin = sorted(
        [(a, d) for a, d in axis_report.items() if d["owned_count"] == 1],
        key=lambda kv: -kv[1]["weight"],
    )

    # Best unowned UPGRADE for this location: the highest-HH unowned hero that
    # provides at least one required axis (a quality upgrade even when there's
    # no coverage gap). Surfaces "who's worth pulling" for deep rosters.
    best_owned_hh = max((hh_rating(n) for n in owned), default=0.0)
    upgrade_candidates = []
    req_axis_set = set(axes)
    for n, r in syn.items():
        if n in owned:
            continue
        if req_axis_set & set(r["provides"]):
            rt = hh_rating(n)
            if rt > best_owned_hh - 0.5:  # comparable to or better than current best
                upgrade_candidates.append((n, rt, sorted(req_axis_set & set(r["provides"]))))
    upgrade_candidates.sort(key=lambda x: -x[1])

    # Thinnest-covered axis (relative weak point even when >0).
    weakest = min(axis_report.items(),
                  key=lambda kv: (kv[1]["owned_count"], -kv[1]["weight"]),
                  default=(None, None))

    return {
        "location": location,
        "label": prof["label"],
        "axis_report": axis_report,
        "gaps": gaps,
        "thin": thin,
        "best_owned_hh": best_owned_hh,
        "upgrades": upgrade_candidates[:5],
        "weakest_axis": weakest,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--location")
    args = ap.parse_args()

    if args.location:
        if args.location not in _rec.LOCATION_PROFILES:
            print("Unknown location. Options:", ", ".join(_rec.LOCATION_PROFILES))
            return
        res = analyze(args.location)
        print(f"=== Roster gaps for {res['label']} ===\n")
        if not res["gaps"]:
            print("  No hard gaps — every required axis has at least one owned provider.")
        else:
            print("  HARD GAPS (no owned provider) — pull/build priority:")
            for axis, d in res["gaps"]:
                print(f"\n  [{d['weight']}] {axis}")
                for n, rt in d["top_unowned"]:
                    print(f"       pull: {n:24s} HH={rt:.1f}")
        if res["thin"]:
            print("\n  THIN (only 1 owned provider — single point of failure):")
            for axis, d in res["thin"]:
                print(f"    [{d['weight']}] {axis}: {d['owned_providers'][0]}")
        wa, wd = res["weakest_axis"]
        if wa:
            print(f"\n  Thinnest required axis: {wa} "
                  f"({wd['owned_count']} owned provider(s))")
        if res["upgrades"]:
            print(f"\n  Best unowned upgrades (HH-rated, your best owned = "
                  f"{res['best_owned_hh']:.1f}):")
            for n, rt, ax in res["upgrades"]:
                print(f"    pull: {n:24s} HH={rt:.1f}  provides: "
                      f"{', '.join(a.split(':')[-1] for a in ax)}")
        return

    # Summary across all locations -> doc.
    import datetime
    lines = [
        "# Per-location roster gap analysis",
        "",
        f"_Generated by `tools/m5_roster_gaps.py` on {datetime.date.today().isoformat()}_",
        "",
        "For each location: which required synergy axes the OWNED roster cannot cover",
        "(hard gaps) or covers with only one hero (thin). The recommender's location",
        "profiles define the required axes; provider data is game-truth synergy tags.",
        "",
        "| Location | hard gaps | thin axes |",
        "|---|---|---|",
    ]
    all_res = {}
    for loc in _rec.LOCATION_PROFILES:
        r = analyze(loc)
        all_res[loc] = r
        gap_s = ", ".join(a.split(":")[-1] for a, _ in r["gaps"]) or "—"
        thin_s = ", ".join(a.split(":")[-1] for a, _ in r["thin"]) or "—"
        lines.append(f"| {loc} | {gap_s} | {thin_s} |")
    lines.append("")
    for loc, r in all_res.items():
        lines.append(f"## {r['label']}")
        lines.append("")
        if r["gaps"]:
            lines.append("Pull/build priority (no owned provider):")
            for axis, d in r["gaps"]:
                tops = ", ".join(f"{n} (HH {rt:.1f})" for n, rt in d["top_unowned"][:3])
                lines.append(f"- **{axis}** (weight {d['weight']}): {tops or 'no provider in game'}")
        else:
            wa, wd = r["weakest_axis"]
            lines.append(f"No coverage gaps. Thinnest axis: `{wa}` "
                         f"({wd['owned_count']} owned provider(s)).")
        if r["upgrades"]:
            lines.append("")
            lines.append(f"Best unowned upgrades (your best owned HH = {r['best_owned_hh']:.1f}):")
            for n, rt, ax in r["upgrades"][:3]:
                lines.append(f"- {n} (HH {rt:.1f}) — provides "
                             f"{', '.join(a.split(':')[-1] for a in ax)}")
        lines.append("")

    OUT_DOC.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_DOC}")
    print()
    for loc, r in all_res.items():
        print(f"  {loc:12s} hard_gaps={len(r['gaps'])} thin={len(r['thin'])}")


if __name__ == "__main__":
    main()
