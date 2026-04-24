#!/usr/bin/env python3
"""Unified CLI front for CB tooling built this session.

One entrypoint for the work that landed in:
- comp_finder.py        -> potential teams (DWJ tunes vs your roster)
- calc_parity_sim.py    -> DWJ-parity turn scheduler
- calc_parity_check.py  -> diff sim output vs live DWJ rendered text
- dwj_inspect.py        -> query the scraped DWJ dataset
- hh_vs_dwj.py          -> HellHades cross-reference / gap analysis

Examples:
    python3 tools/cb.py potential                          # all DWJ tunes ranked vs roster
    python3 tools/cb.py potential --runnable               # only fully owned at 6 star
    python3 tools/cb.py potential --missing 1              # 1-hero-away tunes
    python3 tools/cb.py potential --md docs/comps.md       # write markdown report

    python3 tools/cb.py sim --hash <variant_hash> --turns 25
    python3 tools/cb.py sim --slug myth-eater --variant "Ninja UNM"
    python3 tools/cb.py sim --slug myth-eater --trace      # per-action TM dump

    python3 tools/cb.py parity --hash <variant_hash> --text-file dwj_turns.txt

    python3 tools/cb.py inspect list                       # all tune slugs
    python3 tools/cb.py inspect search forever
    python3 tools/cb.py inspect tune myth-eater
    python3 tools/cb.py inspect variant <variant_hash>
    python3 tools/cb.py inspect champion Ninja

    python3 tools/cb.py gaps                               # full HH cross-reference
    python3 tools/cb.py gaps --roster-only
    python3 tools/cb.py gaps --missing-only
    python3 tools/cb.py gaps --posts-only
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

USAGE = (
    "usage: cb.py {potential|sim|parity|inspect|gaps} [args...]\n"
    "       cb.py --help          for full subcommand examples"
)


def _delegate(module_name: str, sub_argv: list[str]) -> None:
    """Run a sibling tool's main() with sub_argv as sys.argv[1:]."""
    mod = __import__(module_name)
    sys.argv = [f"{module_name}.py", *sub_argv]
    mod.main()


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return

    sub = argv[0]
    rest = argv[1:]

    if sub == "potential":
        _delegate("comp_finder", rest)
    elif sub == "sim":
        _delegate("calc_parity_sim", rest)
    elif sub == "parity":
        _delegate("calc_parity_check", rest)
    elif sub == "inspect":
        _delegate("dwj_inspect", rest)
    elif sub == "gaps":
        _delegate("hh_vs_dwj", rest)
    else:
        print(f"unknown subcommand: {sub}\n{USAGE}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
