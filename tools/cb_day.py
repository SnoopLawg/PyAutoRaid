"""CB element / affinity / day-window resolution helpers.

Element enum follows HeroType.Forms[0].Element: 1=Magic, 2=Force,
3=Spirit, 4=Void. CB resets daily at CB_RESET_UTC_HOUR; anything before
that UTC hour belongs to the previous day's CB instance.
"""
from __future__ import annotations

import datetime
import os
import time

# Element enum: 1=Magic, 2=Force, 3=Spirit, 4=Void (matches HeroType.Forms[0].Element)
ELEMENT_NAMES: dict[int, str] = {1: "Magic", 2: "Force", 3: "Spirit", 4: "Void"}

# Fallback mapping when the mod's battle log predates the element capture patch.
# Populated from observed type_ids; extend as new affinities are seen.
CB_TID_TO_ELEMENT: dict[int, int] = {
    # Confirmed via the mod's direct `element` field (2026-04-22 21:24 log):
    # 22270 is Force (not Void as an earlier inference suggested).
    22270: 2,  # Force
    # 22280 ran on 2026-04-21 — still unconfirmed until the new mod captures it.
}

# Clan Boss resets on a daily cycle. The exact UTC hour varies by clan/region
# (common values: 6, 10). Override with PYAUTORAID_CB_RESET_UTC_HOUR=N.
# Observed default for this account: 10 UTC.
try:
    CB_RESET_UTC_HOUR = int(os.environ.get("PYAUTORAID_CB_RESET_UTC_HOUR", "10"))
except Exception:
    CB_RESET_UTC_HOUR = 10


def cb_affinity_name(boss_element, boss_tid) -> str | None:
    """Return an affinity label ('Magic'/'Force'/'Spirit'/'Void') or None.

    Prefers the element field baked into the battle log by the mod; falls back
    to a hand-curated tid map for old logs that predate the capture.
    """
    if boss_element in ELEMENT_NAMES:
        return ELEMENT_NAMES[boss_element]
    if boss_tid in CB_TID_TO_ELEMENT:
        return ELEMENT_NAMES.get(CB_TID_TO_ELEMENT[boss_tid])
    return None


def cb_day_for_timestamp(ts: float) -> datetime.date:
    """Which CB window does a unix timestamp belong to? CB resets at
    CB_RESET_UTC_HOUR daily; anything before that UTC hour counts toward the
    prior day's CB instance (same boss, continuing damage)."""
    dt_utc = datetime.datetime.utcfromtimestamp(ts)
    return (dt_utc - datetime.timedelta(hours=CB_RESET_UTC_HOUR)).date()


def cb_day_today() -> datetime.date:
    return cb_day_for_timestamp(time.time())


def reset_info() -> dict:
    """Return seconds until next CB reset + the next-reset UTC timestamp.
    Used by the dashboard's CB countdown panel and any CLI / cron script
    that needs to know how long until the next CB instance opens."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    next_utc = now_utc.replace(hour=CB_RESET_UTC_HOUR, minute=0,
                                second=0, microsecond=0)
    if next_utc <= now_utc:
        next_utc += datetime.timedelta(days=1)
    return {
        "now_utc": now_utc.isoformat(timespec="seconds"),
        "next_reset_utc": next_utc.isoformat(timespec="seconds"),
        "seconds_until_reset": int((next_utc - now_utc).total_seconds()),
        "reset_hour_utc": CB_RESET_UTC_HOUR,
    }


def _newest_cb_log(directory) -> "str | None":
    """Newest battle_logs_cb_<YYYYMMDD>_<HHMMSS>.json in `directory`, by the
    timestamp in the filename (NOT the `battle_logs_cb_latest.json` alias, which
    can be stale). Returns the path or None."""
    import glob
    import re
    from pathlib import Path
    best = None
    for f in glob.glob(str(Path(directory) / "battle_logs_cb_*.json")):
        m = re.search(r"battle_logs_cb_(\d{8}_\d{6})", Path(f).name)
        if m and (best is None or m.group(1) > best[0]):
            best = (m.group(1), f)
    return best[1] if best else None


def _element_from_log(path) -> "str | None":
    import json
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
        for entry in (d.get("log") or []):
            if not isinstance(entry, dict):
                continue
            for h in entry.get("heroes") or []:
                if h.get("side") == "enemy" and h.get("element"):
                    return {1: "magic", 2: "force", 3: "spirit",
                            4: "void"}.get(int(h["element"]))
        return None
    except Exception:
        return None


def today_cb_element_str(battle_log_path) -> str | None:
    """Read the current CB affinity from the NEWEST real battle log.
    Returns one of 'magic'/'force'/'spirit'/'void' or None if unknown.

    `battle_log_path` is treated as a hint for the directory to scan — the actual
    read is the newest battle_logs_cb_<ts>.json there, because the conventional
    `battle_logs_cb_latest.json` alias is frequently stale (months old)."""
    from pathlib import Path
    p = Path(battle_log_path)
    directory = p.parent if str(p.parent) not in ("", ".") else Path(".")
    newest = _newest_cb_log(directory)
    el = _element_from_log(newest) if newest else None
    if el:
        return el
    # Fall back to the literal path if scanning found nothing usable.
    return _element_from_log(p) if p.exists() else None


def _main() -> int:
    """CLI: print today's CB window + most-recent affinity if a battle log exists."""
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser(description="CB day window + element resolution")
    ap.add_argument("--battle-log",
                    default=str(Path(__file__).resolve().parent.parent / "battle_logs_cb_latest.json"),
                    help="path to battle_logs_cb_latest.json")
    ap.add_argument("--at", type=float, default=None,
                    help="unix timestamp to resolve CB day for (default: now)")
    args = ap.parse_args()

    ts = args.at if args.at is not None else time.time()
    day = cb_day_for_timestamp(ts)
    print(f"CB reset hour (UTC):  {CB_RESET_UTC_HOUR}")
    print(f"CB day window:        {day.isoformat()}")
    info = reset_info()
    secs = info["seconds_until_reset"]
    h, rem = divmod(secs, 3600)
    m = rem // 60
    print(f"Next reset:           {info['next_reset_utc']} ({h}h {m}m from now)")
    elem = today_cb_element_str(args.battle_log)
    print(f"Most-recent affinity: {elem or '(no log / no element field)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
