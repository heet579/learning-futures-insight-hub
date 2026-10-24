"""CLEAR: the review framework that replaces statement-by-statement checking.

    C  Check    the application verifies facts automatically and blocks on any failure
    L  Level    the application sets how much human judgement the report needs
    E  Examine  the reviewer answers 3 (standard) or 5 (high risk) questions only a person can
    A  Approve  a different signed-in person approves; "No" answers send the report back
    R  Record   answers, reasons and review time go to the audit chain and the review record

Every function here is pure: it reads a workspace state and returns plain data, so the
browser app, the desktop app and the server all apply exactly the same rules.
"""
from __future__ import annotations

import hashlib
import random
import re

import pandas as pd

MIN_GROUP = 5                 # groups smaller than this are never shown or compared
SMALL_SAMPLE = 30             # fewer responses than this makes a report high risk
LOW_SATISFACTION = 3.5        # an average below this makes the report critical, so high risk
CAUSAL = re.compile(r"\b(caused|causes|cause[sd]? by|proves?|proved|proven|resulted in|results in|led to|leads to|"
                    r"because of the (?:course|program|programme|workshop|facilitator))\b", re.I)
TEXT_COLUMNS = ('MostValuableAspect', 'WhatCouldImprove', 'AdditionalComments')
GROUP_LABELS = {'DeliveryMode': 'delivery mode', 'CourseName': 'course', 'ClientType': 'client type',
                'FacilitatorCode': 'facilitator'}

QUESTIONS = {
    'faithful': {
        'title': 'Faithful to learners',
        'prompt': 'Read these learner comments. The app picked them at random, not the AI. '
                  'Does the report reflect what these people said?',
        'choices': {'yes': 'Yes', 'partly': 'Partly', 'no': 'No'},
    },
    'balanced': {
        'title': 'Balanced',
        'prompt': "Here is the report's strongest claim next to the strongest evidence against it. "
                  'Keep the claim as it is, or add a caveat?',
        'choices': {'keep': 'Keep as it is', 'caveat': 'Add a caveat'},
    },
    'owned': {
        'title': 'Owned',
        'prompt': 'Which recommendation would you act on first? Write it in your own words. '
                  'It appears in the report under your name.',
    },
    'fair': {
        'title': 'Fair to people',
        'prompt': 'Could this report unfairly affect anyone, for example a facilitator judged on few '
                  'responses or a client team?',
        'choices': {'no': 'No', 'yes': 'Yes, add a fairness note'},
    },
    'fit': {
        'title': 'Fit for the audience',
        'prompt': 'Is the wording right for this audience, with nothing confidential in it?',
        'choices': {'yes': 'Yes', 'no': 'No'},
    },
}
STANDARD = ('faithful', 'balanced', 'owned')
HIGH = STANDARD + ('fair', 'fit')


# ---- C: Check ----------------------------------------------------------------------------------
def check(state, ledger, unsupported) -> dict:
    """The automatic checks. `ledger` is the synced ClaimLedger and `unsupported` the list of
    numbers or quotes that do not match the data (src/reporting/grounding.py)."""
    content = state.get('content') or ''
    named = [c for c in ledger.claims if c.possible_names and c.key not in ledger.decisions]
    causal = sorted({m.group(0).lower() for m in CAUSAL.finditer(content)})
    rules = [
        {'rule': 'Numbers match the survey data', 'ok': not unsupported, 'blocking': True,
         'detail': (f'{len(ledger.claims) - len(unsupported)} statements and figures checked automatically.'
                    if not unsupported else f'{len(unsupported)} number(s) or quote(s) do not match the data.')},
        {'rule': 'Quotes are real learner comments', 'ok': not any(c.kind == 'quote' and c.blocking for c in ledger.claims),
         'blocking': True, 'detail': 'Every quote is word for word from an analysed comment.'},
        {'rule': 'No personal names or contact details', 'ok': not named, 'blocking': True,
         'detail': (f"{state.get('masked_count', 0)} emails, phone numbers or links were removed from the data."
                    if not named else f'{len(named)} item(s) may contain a name. Confirm or remove each one.')},
        {'rule': f'Groups under {MIN_GROUP} responses are hidden', 'ok': True, 'blocking': True,
         'detail': 'Charts and comparisons never show a group small enough to identify someone.'},
        {'rule': 'Describes feelings, not causes', 'ok': not causal, 'blocking': False,
         'detail': ('Survey ratings show how learners felt, not what caused it.' if not causal else
                    'Consider rewording: ' + ', '.join(f'"{w}"' for w in causal) +
                    '. Survey data cannot prove cause and effect.')},
    ]
    return {'rules': rules, 'passed': all(r['ok'] for r in rules if r['blocking']),
            'auto_verified': len(ledger.verified), 'needs_person': len(ledger.pending)}


# ---- L: Level ----------------------------------------------------------------------------------
def level(state, context) -> dict:
    m = context.metrics
    reasons = []
    audience = state['report'].audience if state.get('report') else state.get('audience', 'facilitator')
    if audience == 'client':
        reasons.append('It goes to a client.')
    if m['response_count'] < SMALL_SAMPLE:
        reasons.append(f"Only {m['response_count']} responses, so a few people can swing the results.")
    satisfaction = m['ratings'].get('OverallSatisfaction', {}).get('mean')
    if satisfaction is not None and satisfaction < LOW_SATISFACTION:
        reasons.append(f'Overall satisfaction is low ({satisfaction:.2f}/5), so the report is critical of someone.')
    high = bool(reasons)
    return {'level': 'high' if high else 'standard', 'label': 'High risk' if high else 'Standard',
            'reasons': reasons or ['Internal report with enough responses and no critical finding.'],
            'questions': list(HIGH if high else STANDARD),
            'approver': 'A Learning Futures lead must approve.' if audience == 'client' else 'Any administrator can approve.'}


# ---- E: Examine --------------------------------------------------------------------------------
def _seed(state) -> int:
    return int(hashlib.sha256((state.get('content') or '').encode('utf-8')).hexdigest()[:12], 16)


def sample_comments(frame: pd.DataFrame, seed: int, count: int = 5) -> list[dict]:
    """Random learner comments (already masked), chosen by the app rather than the AI."""
    pool = []
    for column in TEXT_COLUMNS:
        if column not in frame:
            continue
        for value in frame[column].dropna().astype(str):
            text = value.strip()
            if len(text) >= 20:
                pool.append({'text': text, 'question': {'MostValuableAspect': 'Most valuable',
                                                        'WhatCouldImprove': 'Could improve',
                                                        'AdditionalComments': 'Other comments'}[column]})
    unique = list({c['text']: c for c in pool}.values())
    return random.Random(seed).sample(unique, min(count, len(unique)))


def strongest_claim(context) -> dict:
    m = context.metrics
    if m.get('recommendation_percent') is not None:
        return {'text': f"{m['recommendation_percent']:.0f}% of learners would recommend the course.",
                'measure': 'OverallSatisfaction'}
    mean = m['ratings']['OverallSatisfaction']['mean']
    return {'text': f'Overall satisfaction averaged {mean:.2f} out of 5.', 'measure': 'OverallSatisfaction'}


def counter_evidence(frame: pd.DataFrame, context) -> dict:
    """The strongest data point against the headline result."""
    overall = context.metrics['ratings']['OverallSatisfaction']['mean']
    values = pd.to_numeric(frame.get('OverallSatisfaction'), errors='coerce') if 'OverallSatisfaction' in frame else None
    worst = None
    if values is not None and overall is not None:
        for column, label in GROUP_LABELS.items():
            if column not in frame:
                continue
            data = pd.DataFrame({'g': frame[column].astype(str), 'v': values}).dropna()
            for name, group in data.groupby('g'):
                if len(group) < MIN_GROUP or not name.strip() or name == 'nan':
                    continue
                gap = overall - group['v'].mean()
                if worst is None or gap > worst[0]:
                    worst = (gap, label, name, group['v'].mean(), len(group))
    if worst and worst[0] >= 0.15:
        gap, label, name, mean, n = worst
        return {'text': f'Learners in the {name} {label} group rated overall satisfaction {mean:.2f}/5 '
                        f'(n={n}), {gap:.2f} below the overall {overall:.2f}.',
                'caveat': f'Results were weaker for the {name} {label} group ({mean:.2f}/5, n={n}).'}
    if values is not None and values.notna().any():
        low = int((values <= 2).sum())
        share = low / int(values.notna().sum()) * 100
        return {'text': f'{share:.0f}% of learners ({low} people) rated overall satisfaction 1 or 2 out of 5.',
                'caveat': f'About {share:.0f}% of learners were dissatisfied, so the positive average does not '
                          'describe everyone.'}
    return {'text': 'No group differed noticeably from the overall result.',
            'caveat': 'Results were similar across groups.'}


def recommendations(content: str) -> list[str]:
    from src.review.claims import section_spans
    for name, start, end in section_spans(content or ''):
        if name == 'Recommendations':
            return [line.strip()[2:].replace('**', '').strip() for line in content[start:end].splitlines()
                    if line.strip().startswith('- ')]
    return []


def examine(state, context) -> dict:
    """Everything the reviewer needs to answer the questions."""
    lv = level(state, context)
    claim = strongest_claim(context)
    return {
        'level': lv,
        'questions': [{'id': q, **{k: v for k, v in QUESTIONS[q].items()}} for q in lv['questions']],
        'comments': sample_comments(state['frame'], _seed(state)),
        'claim': claim['text'], 'counter': counter_evidence(state['frame'], context),
        'recommendations': recommendations(state.get('content')),
        'audience': state['report'].audience if state.get('report') else 'facilitator',
    }


# ---- A: Approve (validate answers) ---------------------------------------------------------------
def validate(state, context, answers: dict | None) -> dict:
    """Check the reviewer's answers. Returns {'outcome': 'approve'|'return', 'answers', 'notes'}."""
    if not isinstance(answers, dict):
        raise ValueError('Answer the review questions before approving.')
    lv = level(state, context)
    out, problems = {}, []

    def choice(name):
        value = str(answers.get(name, '')).strip().lower()
        if value not in QUESTIONS[name]['choices']:
            raise ValueError(f"Answer the question \"{QUESTIONS[name]['title']}\".")
        return value

    def text(name, minimum, message):
        value = re.sub(r'\s+', ' ', str(answers.get(name, '') or '')).strip()
        if len(value) < minimum:
            raise ValueError(message)
        return value[:600]

    out['faithful'] = choice('faithful')
    out['faithful_note'] = re.sub(r'\s+', ' ', str(answers.get('faithful_note', '') or '')).strip()[:600]
    if out['faithful'] != 'yes':
        problems.append('The report does not fully reflect what learners said'
                        + (f": {out['faithful_note']}" if out['faithful_note'] else '.'))
    out['balanced'] = choice('balanced')
    if out['balanced'] == 'caveat':
        out['caveat'] = text('caveat', 10, 'Write the caveat to add (at least 10 characters).')
    out['owned'] = text('owned', 15, 'Write the recommendation you would act on, in your own words (at least 15 characters).')
    if 'fair' in lv['questions']:
        out['fair'] = choice('fair')
        if out['fair'] == 'yes':
            out['fairness_note'] = text('fairness_note', 10, 'Write the fairness note to add (at least 10 characters).')
        out['fit'] = choice('fit')
        out['fit_note'] = re.sub(r'\s+', ' ', str(answers.get('fit_note', '') or '')).strip()[:600]
        if out['fit'] == 'no':
            if len(out['fit_note']) < 5:
                raise ValueError('Say what is wrong with the wording so the author can fix it.')
            problems.append(f"Wording is not right for the audience: {out['fit_note']}")
    try:
        out['seconds'] = max(0, min(int(float(answers.get('seconds') or 0)), 24 * 3600))
    except (TypeError, ValueError):
        out['seconds'] = 0
    out['level'] = lv['level']
    concerns = sum(1 for k in ('faithful', 'fit') if out.get(k) in ('partly', 'no')) \
        + (out['balanced'] == 'caveat') + (out.get('fair') == 'yes')
    out['concerns'] = concerns
    return {'outcome': 'return' if problems else 'approve', 'answers': out,
            'notes': ' '.join(problems)}


# ---- R: Record ---------------------------------------------------------------------------------
def reviewer_section(answers: dict, reviewer: str) -> str:
    """The "Reviewer notes" section added to the approved report."""
    lines = ['## Reviewer notes', '', f"- Reviewer's priority ({reviewer}): {answers['owned']}"]
    if answers.get('caveat'):
        lines.append(f"- Caveat: {answers['caveat']}")
    if answers.get('fairness_note'):
        lines.append(f"- Fairness note: {answers['fairness_note']}")
    return '\n'.join(lines)


def record_lines(answers: dict) -> list[str]:
    asked = 5 if answers.get('level') == 'high' else 3
    minutes = answers.get('seconds', 0) / 60
    timing = f', {minutes:.0f} min' if minutes >= 1 else (f", {answers['seconds']} s" if answers.get('seconds') else '')
    lines = [f"- CLEAR review: {'high risk' if answers.get('level') == 'high' else 'standard'} level, "
             f'{asked} questions answered{timing}',
             f"- Faithful to learner comments: {answers['faithful'].title()}"]
    lines.append('- Strongest claim: ' + ('caveat added' if answers.get('balanced') == 'caveat' else 'kept as written'))
    if 'fair' in answers:
        lines.append('- Fairness: ' + ('note added' if answers['fair'] == 'yes' else 'no concern raised'))
        lines.append(f"- Fit for the audience: {answers['fit'].title()}")
    return lines


def insert_before_record(text: str, section: str) -> str:
    marker = '\n## Review record'
    if marker in text:
        head, tail = text.split(marker, 1)
        return head.rstrip() + '\n\n' + section + '\n\n## Review record' + tail
    return text.rstrip() + '\n\n' + section
