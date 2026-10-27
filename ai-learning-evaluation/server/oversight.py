"""The oversight panel: is the human review real, or a rubber stamp?

Built only from the audit chain, so every number traces back to a recorded, hash-chained event.
"""
from __future__ import annotations

import statistics
from datetime import datetime

QUICK_SECONDS = 120          # a review faster than this is "quick"
RUBBER_STAMP_MIN = 5         # flag a reviewer after this many reviews with no concern raised


def _when(event):
    try:
        return datetime.fromisoformat(event['timestamp'])
    except (KeyError, ValueError):
        return None


def summarise(events, names):
    decisions, people = [], {}
    for event in events:
        if event.get('action') not in ('Approved', 'Returned for changes'):
            continue
        d = event.get('details', {})
        decisions.append({
            'when': event.get('timestamp'), 'reviewer': event.get('actor', ''),
            'reviewer_name': names.get(event.get('actor', ''), event.get('actor', '')),
            'author': d.get('author', ''), 'author_name': names.get(d.get('author', ''), d.get('author', '')),
            'report_id': d.get('report_id', ''),
            'decision': 'Approved' if event['action'] == 'Approved' else 'Sent back',
            'seconds': d.get('seconds'), 'level': d.get('level', ''), 'concerns': d.get('concerns'),
            'clear': 'level' in d,
        })
    decisions.reverse()     # newest first
    for item in decisions:
        p = people.setdefault(item['reviewer'], {'reviewer': item['reviewer'], 'name': item['reviewer_name'],
                                                 'reviews': 0, 'approved': 0, 'returned': 0, 'times': [],
                                                 'with_concern': 0, 'clear_reviews': 0})
        p['reviews'] += 1
        p['approved' if item['decision'] == 'Approved' else 'returned'] += 1
        if item['seconds'] is not None:
            p['times'].append(float(item['seconds']))
        if item['clear']:
            p['clear_reviews'] += 1
            if (item['concerns'] or 0) > 0 or item['decision'] == 'Sent back':
                p['with_concern'] += 1
    rows = []
    for p in people.values():
        median = statistics.median(p['times']) if p['times'] else None
        concern_rate = (p['with_concern'] / p['clear_reviews'] * 100) if p['clear_reviews'] else None
        flags = []
        if p['clear_reviews'] >= RUBBER_STAMP_MIN and p['with_concern'] == 0:
            flags.append('Never raised a concern: possible rubber stamp')
        if median is not None and median < QUICK_SECONDS and len(p['times']) >= 3:
            flags.append(f'Median review under {QUICK_SECONDS // 60} minutes')
        rows.append({'reviewer': p['reviewer'], 'name': p['name'], 'reviews': p['reviews'], 'approved': p['approved'],
                     'returned': p['returned'], 'median_seconds': median, 'concern_rate': concern_rate,
                     'flags': flags})
    rows.sort(key=lambda r: (-len(r['flags']), -r['reviews']))
    times = [float(d['seconds']) for d in decisions if d['seconds'] is not None]
    clear = [d for d in decisions if d['clear']]
    return {
        'totals': {'reviews': len(decisions),
                   'median_seconds': statistics.median(times) if times else None,
                   'returned_percent': (sum(d['decision'] == 'Sent back' for d in decisions) / len(decisions) * 100)
                   if decisions else None,
                   'concern_percent': (sum(1 for d in clear if (d['concerns'] or 0) > 0 or d['decision'] == 'Sent back')
                                       / len(clear) * 100) if clear else None,
                   'quick': sum(1 for t in times if t < QUICK_SECONDS)},
        'reviewers': rows, 'recent': decisions[:30],
    }
