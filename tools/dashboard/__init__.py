"""Dashboard server submodules.

The HTTP server (`tools/dashboard_server.py`) historically held everything
in one 4000-LOC module. This package isolates the self-contained pieces:

- stat_calc       — gear-inclusive hero stat calculator
- cb_affinity     — CB element/affinity resolution helpers
"""
