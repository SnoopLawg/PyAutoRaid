"""Summarize active GlobalEvents (tournaments + solo events) with our
current progress, time remaining, and next reward thresholds.

Reads `/events` from the live mod, which exposes the server's event
DataJson — a compact-key blob of all 12-14 active events including:

  - x/i:   prototype + instance ids
  - d.s/d.e: start/end timestamps (ms epoch)
  - q.q.n.d: human-readable name
  - q.q.ge.t: event type (1=Solo, 2=Tournament, 4=CvC, 7=CvC-Boss, ...)
  - q.q.ge.a: dict of per-category quest arrays. Each quest has
              `p` (current progress) and `c.s` (score per completion).
  - q.q.ge.b: tournament tier table (placement-based rewards).

Usage:
    python3 tools/events_status.py             # summary table
    python3 tools/events_status.py --json      # raw structured dump
"""
from __future__ import annotations
import json
import sys
import urllib.request
from datetime import datetime, timezone

MOD_BASE = "http://localhost:6790"

TYPE_NAMES = {
    None: 'Tournament',  # observed: TA Dragon, Sand Devil, Champion Chase, etc.
    0: 'Tournament',     # alias when JSON encodes the missing field as 0
    1: 'Solo',           # Get Artifacts, Hero Level Up, Fuse Warm Up
    2: 'Solo-alt',
    4: 'CvC',            # Community Weeks Titan
    7: 'CvC-Boss',       # Cooperation Event World Boss
}

# Resource id -> label mapping for tournament prize previews.
# Only the ones we've seen so far; others render as "id=N".
RESOURCE_NAMES = {
    1: 'Silver',         # observed values 75000+
    2: 'Silver',         # alt id depending on event
    4: 'Tokens',
    1112: 'TournamentPoints',
    4153: 'EventCurrency',
    1000034: 'Champion(Basalt)',
}


def get_events() -> dict:
    with urllib.request.urlopen(f"{MOD_BASE}/events", timeout=20) as r:
        return json.loads(r.read())


def fmt_remaining(end_ms: int) -> str:
    if not end_ms:
        return '-'
    end = datetime.fromtimestamp(end_ms/1000, tz=timezone.utc)
    delta = end - datetime.now(tz=timezone.utc)
    s = delta.total_seconds()
    if s < 0:
        return f"ENDED {abs(int(s/3600))}h ago"
    if s < 3600:
        return f"{int(s/60)}m"
    if s < 86400:
        return f"{int(s/3600)}h{int((s%3600)/60)}m"
    return f"{int(s/86400)}d{int((s%86400)/3600)}h"


def event_summary(e: dict) -> dict:
    """Extract our progress + reward-tier info from one event entry."""
    qq = (e.get('q') or {}).get('q') or {}
    nm_field = qq.get('n')
    name = nm_field.get('d') if isinstance(nm_field, dict) else (nm_field or '?')
    dates = e.get('d') or {}
    ge = qq.get('ge') or {}
    etype = ge.get('t')  # may be missing, 0, 1, 4, 7
    type_label = TYPE_NAMES.get(etype, f'type{etype}')

    quests_by_cat = ge.get('a') or {}
    total_p = 0
    quest_count = 0
    for cat, qlist in quests_by_cat.items():
        if not isinstance(qlist, list):
            continue
        for q in qlist:
            total_p += q.get('p', 0)
            quest_count += 1

    # Tournament: ge.b is the placement-tier table.
    # Solo: ge.b is empty; rewards are per-milestone in the quest dict itself.
    tiers = ge.get('b') or []
    tournament = bool(tiers)

    # For tournaments, sum the score-per-completion x completions.
    # For solo events, p IS the milestone progress (already summed).
    # We don't have absolute score for tournaments unless a separate
    # field tracks it. ge.x looked like 0 in samples but for some
    # events (Fuse Warm Up) it was 60 — possibly a server-side score?
    score = ge.get('x', 0)

    # Next reward threshold (tournaments only).
    next_threshold = None
    next_reward = None
    if tournament:
        # tiers[0].p is a list of (pts, reward) rungs sorted by pts asc.
        # Find the lowest pts that's > current_score.
        rungs = tiers[0].get('p') if tiers else []
        for rung in (rungs or []):
            pts = rung.get('p', 0)
            if pts > score:
                next_threshold = pts
                next_reward = rung.get('r', {}).get('r', {}).get('v', {})
                break

    return {
        'name': name,
        'type': type_label,
        'starts': dates.get('s', 0),
        'ends': dates.get('e', 0),
        'progress_p_sum': total_p,
        'quest_count': quest_count,
        'score': score,
        'is_tournament': tournament,
        'next_threshold': next_threshold,
        'next_reward': next_reward,
    }


def main():
    if '--json' in sys.argv:
        print(json.dumps(get_events(), indent=1))
        return 0

    payload = get_events()
    if 'error' in payload:
        print(f"ERROR: {payload['error']}", file=sys.stderr)
        return 1

    events = payload['data']['e']
    summaries = [event_summary(e) for e in events]
    # Sort: active events first (by ends ascending), then ended
    now_ms = datetime.now(tz=timezone.utc).timestamp() * 1000
    summaries.sort(key=lambda s: (s['ends'] < now_ms, s['ends']))

    print(f"{'#':>2} {'type':<12} {'remaining':>12} {'score':>6} {'quests':>6}  name + next reward")
    print('-' * 110)
    for i, s in enumerate(summaries):
        ended = s['ends'] < now_ms
        remaining = fmt_remaining(s['ends'])
        flag = '' if not ended else ' (ended)'
        # For solo events, score column shows aggregate quest progress
        score_str = f"{s['score']}" if s['is_tournament'] else f"{s['progress_p_sum']}"
        print(f"  {i:>2} {s['type']:<12} {remaining:>12} {score_str:>6} {s['quest_count']:>6}  {s['name'][:60]}{flag}")
        if s['is_tournament'] and s['next_threshold'] is not None and not ended:
            rew_str = ', '.join(f"{RESOURCE_NAMES.get(int(k), f'id={k}')}x{v}"
                                for k, v in (s['next_reward'] or {}).items())
            need = s['next_threshold'] - s['score']
            print(f"     next tier rung: {s['next_threshold']} pts ({need} to go)"
                  f" -> {rew_str or '(no resources, just rank prize)'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
