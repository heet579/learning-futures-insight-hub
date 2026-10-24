"""Report workspace operations without any user interface.

The browser app (through the API server) uses these functions on the same saved snapshot
format as the desktop app, so a report can be continued in either. Every review gate is
enforced here exactly as in the desktop workflow.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from src.analytics.qualitative import collect_comments
from src.analytics.quantitative import calculate_metrics
from src.analytics.themes import extract_themes
from src.ingestion.validator import validate_dataframe
from src.models import AnalysisContext
from src.privacy.pii_masker import mask_dataframe
from src.review.claims import ClaimLedger, ai_text_retained, extract_claims, remove_claim
from src.review.themes import CATEGORIES, ThemeReview, matched_keywords
from src.workflow import ReviewWorkflow

ALL_COURSES = 'All courses (aggregate)'
EDITABLE = ('DRAFT', 'CHANGES REQUESTED')


def analyse(frame, name, scope=ALL_COURSES):
    validation = validate_dataframe(frame)
    if not validation.valid:
        raise ValueError('\n'.join(validation.errors))
    masked, count = mask_dataframe(frame)
    courses = sorted(masked['CourseName'].dropna().astype(str).unique()) if 'CourseName' in masked else []
    if scope != ALL_COURSES:
        masked = masked[masked['CourseName'].astype(str) == scope].copy()
    if masked.empty:
        raise ValueError('No responses in this course. Select another scope.')
    context = AnalysisContext(calculate_metrics(masked), extract_themes(collect_comments(masked)), name, scope,
                              validation.warnings)
    return masked, context, count, courses


def load_files(paths):
    """Read uploaded survey files (CSV/XLSX/XLS, canonical or Qualtrics) into one table."""
    from src.ingestion.qualtrics_loader import load_survey
    frames = []
    for path in paths:
        frame = load_survey(path).copy()
        frame['SourceFile'] = Path(path).name
        frames.append(frame)
    if not frames:
        raise ValueError('Choose at least one survey file.')
    return pd.concat(frames, ignore_index=True)


def new_state(raw, file_names):
    source = file_names[0] if len(file_names) == 1 else f'{len(file_names)} survey files'
    frame, context, count, _ = analyse(raw, source)
    label = Path(file_names[0]).stem.replace('_', ' ').replace('+', ' ')
    if len(file_names) > 1:
        label = f'{len(file_names)} survey files · {label} +{len(file_names) - 1} more'
    return {
        'raw': raw, 'frame': frame, 'context': context, 'source': source, 'loaded_file_label': label,
        'masked_count': count, 'report': None, 'workflow': ReviewWorkflow(), 'themes_changed_since_draft': False,
        'pending_revision': None, 'revision_history': [], 'revision_section_decisions': {},
        'revision_section_snapshots': {}, 'content': '', 'theme_decisions': {}, 'claim_decisions': {},
        'claim_history': [], 'revision_input': '', 'revision_method': 'Gemini', 'replacement_input': '',
        'revision_selection': [], 'audience': 'facilitator', 'approved_export': '',
        'charts': [], 'charts_enabled': True,
    }


# ---- charts in the designed report -----------------------------------------------------------
def _ai_or_none():
    from src.ai.selection import ai_provider
    try:
        return ai_provider()
    except ValueError:
        return None


def charts_enabled(state):
    return state.get('charts_enabled', True) is not False


def charts_of(state):
    """The report's charts. Reports saved before charts were chosen get the rule-based choice."""
    from src.reporting.charts import auto_choose, chart_list
    specs = state.get('charts')
    if specs:
        try:
            return chart_list(specs)
        except ValueError:
            pass
    return auto_choose(state['frame'], reviewed_context(state))


def choose_charts(state, provider=None):
    """Let the AI (or the rules, without one) pick the charts that suit this data."""
    from src.reporting.charts import auto_choose
    require_editable(state)
    state['charts'] = auto_choose(state['frame'], reviewed_context(state), provider if provider is not None else _ai_or_none())
    return state['charts']


def set_charts_enabled(state, enabled):
    require_editable(state)
    state['charts_enabled'] = bool(enabled)
    return 'The report will include charts.' if enabled else 'The report will be text only.'


def set_charts(state, specs):
    """Replace the report's charts (at most four, in order)."""
    from src.reporting.charts import MAX_CHARTS, chart_list
    require_editable(state)
    if not specs:
        raise ValueError('Keep at least one chart, or switch the report to text only.')
    if len(specs) > MAX_CHARTS:
        raise ValueError(f'The two-page report has room for {MAX_CHARTS} charts.')
    state['charts'] = chart_list(specs)
    return state['charts']


def remove_chart(state, index):
    require_editable(state)
    charts = charts_of(state)
    if not 0 <= index < len(charts):
        raise ValueError('That chart is not in the report.')
    if len(charts) == 1:
        raise ValueError('Keep at least one chart, or switch the report to text only.')
    charts.pop(index)
    state['charts'] = charts
    return 'Chart removed.'


def describe_chart(state, text, replace=None, provider=None):
    """Add (or replace chart number `replace`) from a plain-English description of any chart."""
    from src.reporting.charts import MAX_CHARTS, request_chart
    require_editable(state)
    spec, message = request_chart(text, provider if provider is not None else _ai_or_none())
    spec['reason'] = 'Requested: ' + text.strip()[:150]
    charts = charts_of(state)
    if replace is None and len(charts) >= MAX_CHARTS:
        replace = len(charts) - 1          # the report has room for four: the last one makes way
    if replace is not None:
        if not 0 <= replace < len(charts):
            raise ValueError('That chart is not in the report.')
        charts[replace] = spec
        message = message.replace('Added:', f'Figure {replace + 1} is now:')
    else:
        charts.append(spec)
    state['charts'] = charts
    state['charts_enabled'] = True
    return message


def chart_png(state, index):
    from src.reporting import charts
    specs = charts_of(state)
    if not 0 <= index < len(specs):
        raise ValueError('That chart is not in the report.')
    return charts.render(specs[index], state['frame'], reviewed_context(state), 3.55, 3.05)


# ---- reconstruct review objects from a snapshot ------------------------------------------
def themes_of(state):
    review = ThemeReview(state['context'].themes)
    review.decisions = state['theme_decisions']
    return review


def reviewed_context(state):
    return themes_of(state).reviewed_context(state['context'])


def ledger_of(state):
    ledger = ClaimLedger()
    ledger.decisions, ledger.history = state['claim_decisions'], state['claim_history']
    if state['report'] is not None and state['content'].strip():
        ledger.sync(extract_claims(state['content'], state['report'], reviewed_context(state)))
    state['claim_decisions'] = ledger.decisions
    return ledger


def require_editable(state):
    if state['workflow'].status not in EDITABLE:
        raise ValueError('This report is locked while it is with the reviewer or after approval.')


# ---- gate 1: themes ----------------------------------------------------------------------
def decide_theme(state, name, status, category=None):
    require_editable(state)
    review = themes_of(state)
    review.decide(name, status, category)
    state['theme_decisions'] = review.decisions
    if state['report'] is not None:
        state['themes_changed_since_draft'] = True


# ---- draft ---------------------------------------------------------------------------------
def generate(state, audience, provider=None, charts=True):
    """Create the draft. Returns a short notice when the draft had to use local wording.
    `charts` is the author's answer to "Include charts in the report?"; when yes, the AI picks them."""
    from src.ai.local_provider import LocalAnalysisProvider
    from src.reporting.report_generator import generate_report
    require_editable(state)
    review = themes_of(state)
    if not review.complete:
        raise ValueError(f'Review every theme first ({review.reviewed} of {review.total} done). '
                         'Only themes a person confirmed go into the report.')
    if audience not in ('facilitator', 'client'):
        raise ValueError('Choose a facilitator or client report.')
    context = review.reviewed_context(state['context'])
    notice = ''
    if provider is None:
        from src.ai.selection import ai_provider
        try:
            provider = ai_provider()
        except ValueError:
            provider, notice = LocalAnalysisProvider(), 'No AI service (Claude or Gemini) is set up, so this draft uses fixed local wording.'
    try:
        report = generate_report(context, audience, provider)
    except Exception:
        if isinstance(provider, LocalAnalysisProvider):
            raise
        report = generate_report(context, audience, LocalAnalysisProvider())
        notice = 'The AI service was unavailable, so this draft uses fixed local wording.'
    state.update(report=report, content=report.content, audience=audience, claim_decisions={}, claim_history=[],
                 themes_changed_since_draft=False, pending_revision=None, revision_history=[],
                 revision_section_decisions={}, revision_section_snapshots={}, charts_enabled=bool(charts))
    if charts:
        from src.reporting.charts import auto_choose
        state['charts'] = auto_choose(state['frame'], context,
                                      None if isinstance(provider, LocalAnalysisProvider) else provider)
    return notice


def set_content(state, content):
    require_editable(state)
    if state['report'] is None:
        raise ValueError('Create a draft first.')
    if len(content) > 200_000:
        raise ValueError('The draft is too long.')
    state['content'] = content
    state['pending_revision'] = None


# ---- gates 2, 3, 5: claims -----------------------------------------------------------------
def decide_claim(state, key, decision):
    """Accept (or clear a quote), or reject (removing the text from the draft)."""
    require_editable(state)
    ledger = ledger_of(state)
    claim = ledger.get(key)
    if decision == 'accept':
        result = ledger.accept(key)
    elif decision == 'reject':
        state['content'] = remove_claim(state['content'], claim)
        result = ledger.reject(key)
    else:
        raise ValueError('Choose accept or reject.')
    state['claim_decisions'], state['claim_history'] = ledger.decisions, ledger.history
    ledger_of(state)
    return claim, result


# ---- revisions -----------------------------------------------------------------------------
def propose(state, sections, instruction, method='Gemini', replacement=''):
    from src.reporting.revisions import propose_revisions
    require_editable(state)
    if state['report'] is None:
        raise ValueError('Create a draft first.')
    provider = {'gemini': 'Gemini', 'offline': 'Offline edits', 'manual': 'Human / Copilot text'}.get(method.lower())
    if provider is None:
        raise ValueError('Choose Gemini, quick edits or your own wording.')
    if provider == 'Human / Copilot text':
        instruction = instruction or 'Replacement wording supplied by the reviewer.'
    batch = propose_revisions(state['report'], state['content'], reviewed_context(state), sections, instruction,
                              provider, replacement=replacement)
    state.update(pending_revision=batch, revision_input=instruction, revision_method=provider,
                 revision_selection=list(batch.sections), replacement_input=replacement)
    return batch


def apply_revision(state):
    from src.reporting.revisions import apply_batch_proposal
    require_editable(state)
    batch = state['pending_revision']
    if batch is None:
        raise ValueError('There is no suggested change to apply.')
    updated = apply_batch_proposal(state['report'], state['content'], batch)
    state['revision_history'].append(replace(state['report'], content=state['content']))
    state.update(report=updated, content=updated.content, pending_revision=None,
                 revision_section_decisions={s: 'applied' for s in batch.sections}, revision_section_snapshots={})
    return batch


def discard_revision(state):
    state['pending_revision'] = None


def undo_revision(state):
    require_editable(state)
    if not state['revision_history']:
        raise ValueError('There is no applied change to undo.')
    previous = state['revision_history'].pop()
    content = previous.content.replace('HUMAN REVIEWED', 'DRAFT — REQUIRES HUMAN REVIEW')
    state.update(report=replace(previous, content=content, status='DRAFT — REQUIRES HUMAN REVIEW'), content=content,
                 pending_revision=None, revision_section_decisions={}, revision_section_snapshots={})


# ---- readiness ------------------------------------------------------------------------------
def blockers(state):
    """What still stops the author from submitting (empty list when ready)."""
    from src.reporting.grounding import unsupported_claims
    items = []
    review = themes_of(state)
    if not review.complete:
        items.append(f'Review every theme ({review.reviewed} of {review.total} done).')
    if state['report'] is None:
        items.append('Create the draft.')
        return items
    if state['themes_changed_since_draft']:
        items.append('Themes changed after the draft was created: create the draft again.')
    ledger = ledger_of(state)
    if ledger.pending:
        items.append(f'Fix the {len(ledger.pending)} item(s) the automatic check flagged.')
    if unsupported_claims(state['content'], reviewed_context(state)):
        items.append('Fix numbers or quotes that do not match the data.')
    if state['pending_revision'] is not None:
        items.append('Apply or discard the suggested change.')
    return items


def review_summary(state):
    review, ledger = themes_of(state), ledger_of(state)
    return {'themes': review.counts(), 'claims': ledger.counts(), 'pace': ledger.pace(),
            'ai_retained': ai_text_retained(state['report'], state['content']),
            'returned': state['workflow'].times_returned()}


# ---- view model for the browser ---------------------------------------------------------------
def _theme_view(state, review):
    out = []
    for theme in state['context'].themes:
        decision = review.decisions.get(theme.name)
        out.append({
            'name': theme.name, 'category': theme.category, 'frequency': theme.frequency,
            'keywords': theme.keywords, 'status': review.status_of(theme.name),
            'decision': decision.status if decision else None,
            'decided_category': decision.category if decision else None,
            'evidence': [{'text': text, 'matched': matched_keywords(text, theme)} for text in theme.evidence],
        })
    return out


def _claim_view(ledger):
    claims = []
    for claim in ledger.claims:
        claims.append({
            'key': claim.key, 'section': claim.section, 'text': claim.text, 'kind': claim.kind,
            'origin': claim.origin, 'problems': claim.problems, 'possible_names': claim.possible_names,
            'evidence': claim.evidence, 'decision': ledger.status_of(claim.key),
            'verified': claim.verified, 'needs_person': claim.needs_person,
            'checks': [{'kind': c.kind, 'text': c.text, 'supported': c.supported} for c in claim.checks],
            'blocking': claim.blocking,
        })
    return claims


def view(state, *, can_edit, can_review):
    from src.ai.insights import local_insights
    context = state['context']
    review = themes_of(state)
    ledger = ledger_of(state)
    workflow = state['workflow']
    batch = state['pending_revision']
    m = context.metrics
    return {
        'source': state['source'], 'file_label': state['loaded_file_label'], 'masked_count': state['masked_count'],
        'course': context.course_name, 'warnings': context.warnings,
        'metrics': {
            'responses': m['response_count'], 'completeness': m['response_completeness'],
            'satisfaction_mean': m['ratings']['OverallSatisfaction']['mean'],
            'satisfaction_percent': m['satisfaction_percent'], 'recommend_percent': m['recommendation_percent'],
            'ratings': [{'key': k, **v} for k, v in m['ratings'].items()],
            'strongest': m['strongest_area'], 'lowest': m['lowest_area'],
        },
        'insights': local_insights(context),
        'themes': _theme_view(state, review), 'categories': list(CATEGORIES),
        'themes_progress': {'reviewed': review.reviewed, 'total': review.total},
        'themes_changed_since_draft': state['themes_changed_since_draft'],
        'audience': state.get('audience') or (state['report'].audience if state['report'] else 'facilitator'),
        'report': None if state['report'] is None else {
            'audience': state['report'].audience, 'written_by': state['report'].source_mode, 'mode': state['report'].mode},
        'content': state['content'],
        'claims': _claim_view(ledger),
        'revision': None if batch is None else {
            'sections': list(batch.sections), 'provider': batch.provider, 'feedback': batch.feedback,
            'changes': [{'section': p.section, 'before': _section(p.original, p.section),
                         'after': _section(p.revised, p.section), 'note': p.note} for p in batch.proposals]},
        'can_undo_revision': bool(state['revision_history']),
        'workflow': {
            'status': workflow.status, 'author': workflow.reviewer, 'approver': workflow.approver,
            'approver_role': workflow.approver_role,
            'events': [{'action': e.action, 'actor': e.actor, 'notes': e.notes, 'at': e.timestamp} for e in workflow.events],
        },
        'blockers': blockers(state) if workflow.status in EDITABLE else [],
        'summary': review_summary(state) if state['report'] is not None else None,
        'approved': bool(state.get('approved_export')),
        'charts': charts_of(state), 'chart_kinds': _chart_catalogue(), 'charts_enabled': charts_enabled(state),
        'clear': _clear_view(state, ledger, can_review),
        'can_edit': can_edit, 'can_review': can_review,
    }


def _clear_view(state, ledger, can_review):
    from src.reporting.grounding import unsupported_claims
    from src.review import clear
    if state['report'] is None:
        return None
    context = reviewed_context(state)
    out = {'check': clear.check(state, ledger, unsupported_claims(state['content'], context)),
           'level': clear.level(state, context), 'answers': state.get('clear')}
    if can_review:
        out['examine'] = clear.examine(state, context)
    return out


def _chart_catalogue():
    from src.reporting.charts import GROUPS, KINDS, MAX_CHARTS
    from src.reporting.charts import LABELS, RATING_COLUMNS
    return {'kinds': KINDS, 'groups': GROUPS, 'measures': {c: LABELS[c] for c in RATING_COLUMNS}, 'max': MAX_CHARTS}


def _section(content, section):
    from src.reporting.revisions import section_text
    try:
        return section_text(content, section)
    except ValueError:
        return ''


def survey_rows(state, search='', offset=0, limit=50):
    """Masked survey responses for the data table (never the unmasked source)."""
    frame = state['frame']
    columns = [c for c in ('ResponseID', 'RecordedDate', 'CourseName', 'OverallSatisfaction', 'WouldRecommend',
                           'MostValuableAspect', 'WhatCouldImprove', 'AdditionalComments') if c in frame]
    rows = frame[columns]
    if search.strip():
        needle = search.strip().lower()
        mask = rows.astype(str).apply(lambda col: col.str.lower().str.contains(needle, regex=False)).any(axis=1)
        rows = rows[mask]
    total = len(rows)
    page = rows.iloc[offset:offset + limit].astype(object).where(rows.iloc[offset:offset + limit].notna(), None)
    return {'columns': columns, 'total': total, 'rows': [[None if v is None else str(v) for v in r]
                                                          for r in page.itertuples(index=False)]}
