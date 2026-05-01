"""tools — current Python tooling for PyAutoRaid.

Every module here is **mod-API-only** and **CLI-first** per
CLAUDE.md. New features ship as `tools/<feature>.py` with an
`if __name__ == "__main__":` entrypoint; the dashboard's `build_*`
functions become thin wrappers around the same domain code.

If you're tempted to add UI/screen automation, stop — that lives in
`Modules/` (legacy, see Modules/__init__.py) and is being phased out.
"""
