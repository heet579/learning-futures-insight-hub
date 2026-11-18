"""The two-page designed report: text tidying, emphasis, Word and PDF output."""
from io import BytesIO
from pathlib import Path

import pytest

from src.config import DATA_DIR

pytest.importorskip('matplotlib')
pytest.importorskip('reportlab')

from src import workspace  # noqa: E402
from src.ai.local_provider import LocalAnalysisProvider  # noqa: E402
from src.reporting import charts, designed_report as d  # noqa: E402

SAMPLE = Path(DATA_DIR) / 'synthetic_qualtrics_evaluation.csv'


@pytest.fixture(scope='module')
def state():
    s = workspace.new_state(workspace.load_files([SAMPLE]), [SAMPLE.name])
    for theme in s['context'].themes:
        workspace.decide_theme(s, theme.name, 'confirmed')
    workspace.generate(s, 'facilitator', provider=LocalAnalysisProvider())
    return s


def test_humanise_and_emphasis():
    assert d.humanise('**DRAFT — REQUIRES HUMAN REVIEW** 1 response(s) and 2781 related comments') == \
        '1 response and 2,781 related comments'
    parts = d.emphasis_runs('Averaged 4.08/5 with 85% recommending')
    assert ('4.08/5', True) in parts and ('85%', True) in parts and ('Averaged ', False) in parts


def test_report_data_reads_the_reviewed_draft(state):
    data = d.report_data(state)
    assert data['responses'] > 0 and data['working'] and data['recommendations']
    assert not data['approved'] and 'not yet approved' in d.status_line(data)
    assert len(d.figures(data)) == 4


def test_word_and_pdf_are_built_with_the_logo(state):
    from docx import Document
    data = d.report_data(state)
    word = Document(BytesIO(d.build_docx(data)))
    assert word.sections[0].header.tables[0].rows[0].cells[0].paragraphs[0].runs  # logo picture
    text = '\n'.join(p.text for p in word.paragraphs)
    assert 'At a glance' in text and 'About this report' in text and '**' not in text
    import pypdf
    assert len(pypdf.PdfReader(BytesIO(d.build_pdf(data))).pages) == 2


def test_described_charts_and_limits(state):
    assert workspace.describe_chart(state, 'average relevance by course', replace=0).startswith('Figure 1 is now:')
    assert state['charts'][0]['kind'] == 'group_bar' and state['charts'][0]['group'] == 'CourseName'
    count = len(state['charts'])
    workspace.describe_chart(state, 'pie chart of who responded by delivery mode')   # full: replaces the last
    assert len(state['charts']) == min(count + 1, 4) and state['charts'][-1]['kind'] == 'share'
    with pytest.raises(ValueError):
        workspace.set_charts(state, [{'kind': 'ratings_bar'}] * 5)
    for i in range(len(state['charts'])):
        assert workspace.chart_png(state, i)[:4] == b'\x89PNG'
    for kind in ('ratings_violin', 'histogram', 'heatmap', 'scatter', 'group_stacked', 'trend'):
        spec = {'kind': kind, 'group': 'CourseName'}
        assert charts.render(spec, state['frame'], state['context'])[:4] == b'\x89PNG'


def test_any_chart_in_plain_english():
    cases = {'violin plot of ratings': 'ratings_violin', 'histogram of content quality': 'histogram',
             'heat map by course': 'heatmap', 'scatter of satisfaction against content quality': 'scatter',
             'pie chart of delivery mode': 'share', 'stacked relevance by course': 'group_stacked',
             'box plot of satisfaction per delivery mode': 'group_box', 'relevance over time': 'trend'}
    for text, kind in cases.items():
        assert charts.parse_request(text)[0]['kind'] == kind, text

    class FakeAI:
        def chart_request(self, text, catalogue):
            return {'possible': True, 'kind': 'heatmap', 'group': 'ClientType', 'title': 'Client types at a glance'}

    spec, message = charts.request_chart('something unusual with clients', FakeAI())
    assert spec['kind'] == 'heatmap' and spec['title'] == 'Client types at a glance'
    with pytest.raises(ValueError):
        charts.request_chart('something unusual')


def test_the_ai_picks_charts_and_rules_are_the_fallback(state):
    rules = charts.auto_choose(state['frame'], state['context'])
    assert 2 <= len(rules) <= 4 and all(r.get('reason') for r in rules)

    class FakeAI:
        def choose_charts(self, summary, options, count):
            return [{'id': len(options) - 1, 'reason': 'Shows who took part.'}, {'id': 0, 'reason': 'Overview.'}]

    picked = charts.auto_choose(state['frame'], state['context'], FakeAI())
    assert picked[0]['reason'] == 'Shows who took part.' and len(picked) == 2

    class BrokenAI:
        def choose_charts(self, *args):
            raise RuntimeError('quota')

    assert charts.auto_choose(state['frame'], state['context'], BrokenAI()) == rules


@pytest.mark.parametrize('audience,with_charts', [('facilitator', True), ('client', False)])
def test_both_pages_are_full_and_never_spill(audience, with_charts):
    s = workspace.new_state(workspace.load_files([SAMPLE]), [SAMPLE.name])
    for theme in s['context'].themes:
        workspace.decide_theme(s, theme.name, 'confirmed')
    workspace.generate(s, audience, provider=LocalAnalysisProvider(), charts=with_charts)
    data = d.report_data(s)
    pages = d.plan(data)
    styles = d._styles()
    for blocks in pages:
        height = d._height(blocks, styles)
        assert d.FRAME_H * 0.95 <= height <= d.FRAME_H * d.FILL + 0.01
    assert any(b.kind == 'charts' for b in pages[0]) is with_charts
    import pypdf
    assert len(pypdf.PdfReader(BytesIO(d.build_pdf(data, pages=pages))).pages) == 2
