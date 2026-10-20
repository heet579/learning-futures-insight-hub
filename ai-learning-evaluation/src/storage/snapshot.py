"""Versioned JSON workspace snapshots; no pickle or arbitrary class loading."""
import io
from dataclasses import fields, is_dataclass
import pandas as pd
from src.models import AnalysisContext, Theme, ReportDraft
from src.review.themes import ThemeDecision
from src.review.claims import DecisionEvent
from src.workflow import ReviewWorkflow, ReviewEvent
from src.reporting.revisions import RevisionProposal, BatchRevisionProposal

TYPES = {cls.__name__: cls for cls in (AnalysisContext, Theme, ReportDraft, ThemeDecision,
          DecisionEvent, ReviewWorkflow, ReviewEvent, RevisionProposal, BatchRevisionProposal)}


def encode(value):
    if is_dataclass(value):
        return {'type': type(value).__name__, 'fields': {f.name: encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, pd.DataFrame):
        return {'type': 'dataframe', 'json': value.to_json(orient='table', date_format='iso', index=False)}
    if isinstance(value, tuple):
        return {'type': 'tuple', 'items': [encode(v) for v in value]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {'type': 'dict', 'items': {k: encode(v) for k, v in value.items()}}
    return value


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    kind = value['type']
    if kind == 'dict':
        return {k: decode(v) for k, v in value['items'].items()}
    if kind == 'tuple':
        return tuple(decode(v) for v in value['items'])
    if kind == 'dataframe':
        return pd.read_json(io.StringIO(value['json']), orient='table')
    if kind not in TYPES:
        raise ValueError('Unsupported snapshot data type.')
    return TYPES[kind](**{k: decode(v) for k, v in value['fields'].items()})


def pack(state):
    return {'schema': 2, 'state': encode(state)}


def unpack(snapshot):
    if snapshot.get('schema') not in (1, 2):
        raise ValueError('This report uses an unsupported snapshot version.')
    state = decode(snapshot['state'])
    required = {'raw', 'frame', 'context', 'source', 'loaded_file_label', 'masked_count', 'report', 'workflow',
                'themes_changed_since_draft', 'pending_revision', 'revision_history', 'revision_section_decisions',
                'revision_section_snapshots', 'content', 'theme_decisions', 'claim_decisions', 'claim_history',
                'revision_input', 'revision_method', 'revision_selection'}
    if not isinstance(state, dict) or not required.issubset(state):
        raise ValueError('The saved workspace is incomplete.')
    if not isinstance(state['frame'], pd.DataFrame) or not isinstance(state['raw'], pd.DataFrame):
        raise ValueError('The saved dataset is invalid.')
    if not isinstance(state['workflow'], ReviewWorkflow):
        raise ValueError('The saved review state is invalid.')
    if (state['report'] is not None and not isinstance(state['report'], ReportDraft)) or not isinstance(state['context'], AnalysisContext):
        raise ValueError('Invalid report snapshot.')
    if state['workflow'].status not in ('DRAFT', 'CHANGES REQUESTED', 'AWAITING HUMAN REVIEW', 'HUMAN REVIEWED'):
        raise ValueError('Unknown report workflow status.')
    if state['workflow'].status in ('AWAITING HUMAN REVIEW', 'HUMAN REVIEWED') and state['report'] is None:
        raise ValueError('A submitted report must contain a draft.')
    return state
