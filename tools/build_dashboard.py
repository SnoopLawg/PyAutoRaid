#!/usr/bin/env python3
"""Build the dashboard: transpile gui/dashboard/*.jsx -> *.js (no in-browser Babel).

Ensures @babel/standalone is available (npm i --no-save) then runs the node
transpiler tools/build_dashboard.mjs. Run this after editing any dashboard .jsx;
the generated .js are committed so the server needs no build step at runtime.

    python3 tools/build_dashboard.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    # Install the transpiler (no-save: not a project dep, just a build tool).
    print("ensuring @babel/standalone is available…")
    r = subprocess.run(["npm", "install", "--no-save", "@babel/standalone"],
                       cwd=ROOT, capture_output=True, text=True, shell=(sys.platform == "win32"))
    if r.returncode != 0:
        print("npm install failed:\n" + (r.stderr or r.stdout)[-1000:])
        return 1
    print("transpiling JSX…")
    r = subprocess.run(["node", str(ROOT / "tools" / "build_dashboard.mjs")],
                       cwd=ROOT, capture_output=True, text=True, shell=(sys.platform == "win32"))
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
