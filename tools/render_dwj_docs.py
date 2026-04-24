#!/usr/bin/env python3
"""Render scraped DWJ tunes into human-readable markdown under docs/dwj/tunes/.

Reads data/dwj/parsed/tunes.json (written by tools/scrape_dwj.py) and emits one
markdown file per tune plus an index. Replaces the hand-maintained
docs/deadwoodjedi_speed_tunes.md (moved to docs/dwj/legacy/).
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TUNES_JSON = PROJECT_ROOT / "data" / "dwj" / "parsed" / "tunes.json"
DOCS_TUNES = PROJECT_ROOT / "docs" / "dwj" / "tunes"
DOCS_INDEX = PROJECT_ROOT / "docs" / "dwj" / "tunes_index.md"


def strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p\s*>", "\n\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def render_tune_md(tune: dict) -> str:
    lines = []
    lines.append(f"# {tune['name']}")
    lines.append("")
    meta = []
    if tune.get("type"):
        meta.append(f"**Type**: {tune['type']}")
    if tune.get("difficulty"):
        meta.append(f"**Difficulty**: {tune['difficulty']}")
    if tune.get("key_capability"):
        meta.append(f"**Key**: {tune['key_capability']}")
    if tune.get("affinity"):
        meta.append(f"**Affinity**: {tune['affinity']}")
    if tune.get("created_by"):
        meta.append(f"**Author**: {tune['created_by']}")
    if meta:
        lines.append(" · ".join(meta))
        lines.append("")
    if tune.get("url"):
        lines.append(f"Source: {tune['url']}")
        lines.append("")

    if tune.get("description"):
        lines.append(strip_html(tune["description"]))
        lines.append("")

    # Slots table
    lines.append("## Slots")
    lines.append("")
    lines.append("| # | Hero | SPD min | SPD max | Mastery | Relentless | CoM | LG |")
    lines.append("|---|------|---------|---------|---------|------------|-----|-----|")
    for s in tune.get("slots", []):
        spd_min = s["min_spd"] if s.get("min_spd") is not None else "-"
        spd_max = s["max_spd"] if s.get("max_spd") is not None else "-"
        mast = s.get("mastery") or "-"
        rel = "Y" if s.get("relentless") else ("N" if s.get("relentless") is False else "-")
        com = "Y" if s.get("cycle_of_magic") else ("N" if s.get("cycle_of_magic") is False else "-")
        lg = "Y" if s.get("lasting_gifts") else ("N" if s.get("lasting_gifts") is False else "-")
        lines.append(
            f"| {s['index']} | {s.get('hero') or '-'} | {spd_min} | {spd_max} | {mast} | {rel} | {com} | {lg} |"
        )
    lines.append("")

    # Special rules per slot
    any_rules = any((s.get("special_rules_html") or "").strip() for s in tune.get("slots", []))
    if any_rules:
        lines.append("## Slot Rules")
        lines.append("")
        for s in tune.get("slots", []):
            rules = strip_html(s.get("special_rules_html") or "")
            if not rules:
                continue
            lines.append(f"### Slot {s['index']} · {s.get('hero') or '-'}")
            lines.append("")
            lines.append(rules)
            lines.append("")

    # Notes (post author's freeform text)
    notes = strip_html(tune.get("notes_html") or "")
    if notes:
        lines.append("## Notes")
        lines.append("")
        lines.append(notes)
        lines.append("")

    # Calculator links
    calc_links = tune.get("calculator_links") or []
    if calc_links:
        lines.append("## Calculator")
        lines.append("")
        for c in calc_links:
            label = c.get("name") or "link"
            lines.append(f"- [{label}]({c['url']}) — `{c['hash']}`")
        lines.append("")

    # Videos
    yt = tune.get("youtube_id")
    cvs = tune.get("community_videos") or []
    if yt or cvs:
        lines.append("## Videos")
        lines.append("")
        if yt:
            lines.append(f"- Author: https://youtu.be/{yt}")
        for v in cvs:
            lines.append(f"- Community: https://youtu.be/{v}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_index(tunes: list[dict]) -> str:
    lines = ["# DeadwoodJedi Speed Tunes — Index", "", f"Total: **{len(tunes)}** tunes. Source: `/wp-json/dwj-api/v1/tunes`.", ""]
    # Group by type
    by_type: dict[str, list[dict]] = {}
    for t in tunes:
        by_type.setdefault(t.get("type") or "Unknown", []).append(t)
    for typ in sorted(by_type):
        lines.append(f"## {typ}")
        lines.append("")
        lines.append("| Tune | Key | Difficulty | Affinity | Slots (SPDs) |")
        lines.append("|------|-----|------------|----------|---------------|")
        for t in sorted(by_type[typ], key=lambda x: x["name"]):
            slot_spds = " / ".join(
                f"{s.get('hero','?')}={s.get('min_spd') or '?'}-{s.get('max_spd') or '?'}"
                for s in t.get("slots", [])
            )
            slug = t.get("slug") or "-"
            key = t.get("key_capability") or "-"
            diff = t.get("difficulty") or "-"
            aff = t.get("affinity") or "-"
            lines.append(f"| [{t['name']}](tunes/{slug}.md) | {key} | {diff} | {aff} | {slot_spds} |")
        lines.append("")
    return "\n".join(lines)


def main():
    tunes = json.loads(TUNES_JSON.read_text(encoding="utf-8"))
    DOCS_TUNES.mkdir(parents=True, exist_ok=True)
    written = 0
    for t in tunes:
        slug = t.get("slug") or str(t.get("id") or "tune")
        (DOCS_TUNES / f"{slug}.md").write_text(render_tune_md(t), encoding="utf-8")
        written += 1
    DOCS_INDEX.write_text(render_index(tunes), encoding="utf-8")
    print(f"wrote {written} tune docs + index")


if __name__ == "__main__":
    main()
