"""The two-page evaluation report (Word and PDF) with the Adelaide University logo.

Both pages are always full: the layout is measured with the same fonts the documents use
(Carlito = Calibri metrics, Caladea = Cambria metrics, bundled in assets/fonts), optional
sections are added while they fit, and the charts grow to take up what is left. Without
charts the same space goes to plain-English summaries and tables.

The reviewed draft supplies the summary, findings and recommendations exactly as approved
(only presentation changes: plurals, thousands separators, bold numbers). The extra summaries
and tables are calculated directly from the survey data, like the charts.
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.reporting import charts as chart_lib

ASSETS = Path(__file__).resolve().parents[2] / 'assets'
LOGO = ASSETS / 'adelaide-university-logo.png'
FONTS = ASSETS / 'fonts'
NAVY, PLUM, LILAC_BG, GREEN_BG, AMBER_BG = '151054', '5B2EA6', 'F1EDFA', 'E8F3EC', 'FCF1DE'
GREY, INK, LILAC, LINE, GOOD, WARN = '6B6382', '1E1631', 'C9B8EE', 'E4DDF2', '2E7D5B', 'C27C0E'
DRAFT_MARK = 'DRAFT — REQUIRES HUMAN REVIEW'

CM = 28.3465                                  # points per centimetre
PAGE_W, PAGE_H = 21.0, 29.7                   # A4, cm
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 1.7, 2.45, 1.55
TEXT_W = PAGE_W - 2 * MARGIN_X                # 17.6 cm
FRAME_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM  # 25.7 cm
FILL = 0.975          # fill 97.5% of each page: full to the eye, never spills onto a third page in Word
CHART_MIN, CHART_PREFERRED, CHART_MAX = 5.4, 6.8, 9.2   # chart heights, cm
COL_W = TEXT_W / 2 - 0.3                      # chart width in a two-column row, cm

# type scale: (size, leading) in points; Word and the PDF use exactly these
BODY, SMALL, BULLET = (9.6, 12.8), (8.3, 10.8), (9.0, 11.8)
H1, H2, TITLE, KICK = (12.5, 15.5), (10.5, 13.0), (21.0, 24.0), (9.0, 11.5)
STAT, STAT_LABEL = (17.0, 19.0), (7.8, 9.5)
GAP_HEAD, GAP_PARA, GAP_BLOCK = 7.0, 3.0, 6.0   # points of space before headings / after paragraphs / after blocks


# ---- reading the reviewed text -------------------------------------------------------------------
def _sections(text):
    from src.review.claims import section_spans
    return {name: text[start:end].strip() for name, start, end in section_spans(text)}


def _bullets(body):
    return [line.strip()[2:].strip() for line in (body or '').splitlines() if line.strip().startswith('- ')]


def humanise(text):
    """Presentation-only tidying: plurals, thousands separators, no markdown or status banners."""
    text = text.replace('**', '').replace(DRAFT_MARK, '').strip()
    text = re.sub(r'\b1 (response|comment|learner)\(s\)', r'1 \1', text)
    text = re.sub(r'\b(\w+)\(s\)', r'\1s', text)
    text = re.sub(r'\b(\d{4,})(?= (?:responses?|comments?|learners?|answers?|matching|related|people)\b)',
                  lambda m: f'{int(m.group(1)):,}', text)
    text = text.replace(' — ', ': ').replace('—', ': ')
    return re.sub(r'\s{2,}', ' ', text).strip()


_NUMBER = re.compile(r'(\d[\d,]*(?:\.\d+)?\s?(?:%|/5)?)')


def emphasis_runs(text):
    """Split text into (part, bold) pairs: numbers, percentages and x/5 scores are bold."""
    parts, last = [], 0
    for match in _NUMBER.finditer(text):
        if match.start() > last:
            parts.append((text[last:match.start()], False))
        parts.append((match.group(0), True))
        last = match.end()
    if last < len(text):
        parts.append((text[last:], False))
    return parts


# ---- calculated plain-English summaries -----------------------------------------------------------
def _pct(part, whole):
    return part / whole * 100 if whole else 0


def _ratings_rows(frame):
    from src.analytics.quantitative import LABELS
    from src.config import RATING_COLUMNS
    rows = []
    for column in RATING_COLUMNS:
        if column not in frame:
            continue
        values = pd.to_numeric(frame[column], errors='coerce')
        values = values[values.between(1, 5)]
        if len(values):
            rows.append({'label': LABELS[column], 'mean': values.mean(), 'top': _pct((values >= 4).sum(), len(values)),
                         'low': _pct((values <= 2).sum(), len(values)), 'n': len(values),
                         'dist': [f'{_pct((values == k).sum(), len(values)):.0f}%' for k in range(1, 6)]})
    return rows


def ratings_text(rows):
    if not rows:
        return ''
    best, worst = max(rows, key=lambda r: r['mean']), min(rows, key=lambda r: r['mean'])
    others = [r for r in rows if r not in (best, worst)]
    text = (f"Learners rated {len(rows)} areas on a scale from 1 to 5. {best['label']} scored highest at "
            f"{best['mean']:.2f}, with {best['top']:.0f}% of learners giving it a 4 or 5.")
    if worst is not best:
        text += (f" {worst['label']} had the most room to improve at {worst['mean']:.2f}, where {worst['top']:.0f}% "
                 f"gave a 4 or 5.")
    if others:
        text += ' ' + ' and '.join(f"{r['label'].lower()} averaged {r['mean']:.2f}" for r in others).capitalize() + '.'
    low = max(rows, key=lambda r: r['low'])
    text += (f" Low scores were uncommon: at most {low['low']:.0f}% of learners rated any area 1 or 2."
             if low['low'] < 10 else f" {low['low']:.0f}% of learners rated {low['label'].lower()} 1 or 2, which is worth a closer look.")
    return text


def _group_split(frame):
    for column, label in (('DeliveryMode', 'delivery mode'), ('ClientType', 'client type'), ('CourseName', 'course')):
        if column in frame:
            counts = frame[column].fillna('').astype(str).str.strip()
            counts = counts[counts != ''].value_counts()
            counts = counts[counts >= chart_lib.MIN_GROUP]
            if len(counts) >= 2:
                return column, label, counts
    return None, None, None


def who_text(frame, m):
    text = (f"{m['response_count']:,} learners answered the survey, and {m['response_completeness']:.0f}% of all "
            f"answers were filled in.")
    column, label, counts = _group_split(frame)
    if counts is not None:
        total = counts.sum()
        parts = [f'{_pct(v, total):.0f}% {name}' for name, v in counts.head(4).items()]
        text += f" By {label}, " + ', '.join(parts[:-1]) + (' and ' if len(parts) > 1 else '') + parts[-1] + '.'
    if 'CourseName' in frame and column != 'CourseName':
        courses = frame['CourseName'].dropna().astype(str).nunique()
        if courses > 1:
            text += f' Responses came from {courses} courses.'
    dates = pd.to_datetime(frame['RecordedDate'], errors='coerce').dropna() if 'RecordedDate' in frame else pd.Series(dtype='datetime64[ns]')
    if len(dates):
        first, last = dates.min(), dates.max()
        text += (f' They were collected between {first:%B %Y} and {last:%B %Y}.' if (first.year, first.month) != (last.year, last.month)
                 else f' They were collected in {first:%B %Y}.')
    return text


def themes_text(context):
    themes = sorted(context.themes, key=lambda t: -t.frequency)
    if not themes:
        return 'No recurring topic in the comments met the threshold for reporting.'
    clean = lambda t: t.name.replace('Emerging: ', '').lower()
    positive = [t for t in themes if t.category == 'Positive'][:3]
    concerns = [t for t in themes if t.category == 'Improvement'][:2]
    text = ''
    if positive:
        listed = [f'{clean(t)} ({t.frequency:,} comments)' for t in positive]
        text += 'In their written comments, learners most often praised ' + ', '.join(listed[:-1]) + \
                (' and ' if len(listed) > 1 else '') + listed[-1] + '.'
    if concerns:
        listed = [f'{clean(t)} ({t.frequency:,})' for t in concerns]
        text += ' The most common suggestions for improvement were about ' + ' and '.join(listed) + '.'
    else:
        text += ' No improvement topic came up often enough to report on its own.'
    text += ' One comment can touch several topics, so these counts are comments, not people.'
    return text.strip()


def groups_text(frame):
    from src.review.clear import GROUP_LABELS
    values = pd.to_numeric(frame.get('OverallSatisfaction'), errors='coerce') if 'OverallSatisfaction' in frame else None
    if values is None:
        return '', []
    best = None
    for column, label in GROUP_LABELS.items():
        if column not in frame:
            continue
        data = pd.DataFrame({'g': frame[column].fillna('').astype(str).str.strip(), 'v': values}).dropna()
        data = data[data['g'] != '']
        stats = data.groupby('g')['v'].agg(['mean', 'count'])
        stats = stats[stats['count'] >= chart_lib.MIN_GROUP]
        if len(stats) < 2:
            continue
        spread = stats['mean'].max() - stats['mean'].min()
        if best is None or spread > best[0]:
            best = (spread, column, label, stats.sort_values('mean', ascending=False))
    if best is None:
        return '', []
    spread, column, label, stats = best
    top, bottom = stats.index[0], stats.index[-1]
    if spread < 0.15:
        text = (f'Satisfaction was much the same across each {label}, ranging only from {stats["mean"].min():.2f} '
                f'to {stats["mean"].max():.2f}.')
    else:
        text = (f'Satisfaction differed most by {label}: {top} learners rated it {stats.loc[top, "mean"]:.2f} and '
                f'{bottom} learners {stats.loc[bottom, "mean"]:.2f}, a gap of {spread:.2f} points. Groups with fewer '
                f'than {chart_lib.MIN_GROUP} responses are not shown.')
    rows = [(str(name), int(row['count']), float(row['mean'])) for name, row in stats.iterrows()][:8]
    return text, [label] + rows


# ---- everything the layout needs ------------------------------------------------------------------
def report_data(state, text=None):
    """Read a saved workspace state into the values the two pages show."""
    from src.workspace import reviewed_context, charts_of, charts_enabled
    text = text if text is not None else (state.get('approved_export') or state['content'])
    approved = state['workflow'].status == 'HUMAN REVIEWED' and '## Review record' in text
    record = ''
    if '## Review record' in text:
        text, record = text.split('## Review record', 1)
    sections = _sections(text)
    context = reviewed_context(state)
    m = context.metrics
    frame = state['frame']
    audience = state['report'].audience if state.get('report') else 'facilitator'
    quotes = re.findall(r'[“"](.+?)[”"]', sections.get('Evidence / Supporting Metrics', ''))
    for theme in sorted(context.themes, key=lambda t: -t.frequency):
        quotes += [q for q in theme.evidence if q not in quotes]
    notes = {}
    for line in _bullets(sections.get('Reviewer notes', '')):
        key, _, value = line.partition(':')
        notes[key.strip()] = value.strip()
    workflow = state['workflow']
    approved_event = next((e for e in reversed(workflow.events) if e.action == 'Approved'), None)
    rows = _ratings_rows(frame)
    group_sentence, group_rows = groups_text(frame)
    summary = humanise(sections.get('Executive Summary', ''))
    summary = re.sub(r'\s*These findings are descriptive and require human interpretation before use\.?', '', summary)
    feedback = humanise(sections.get('Learner Feedback Summary', ''))
    if 'Automated categories are indicators' in feedback or not feedback:
        feedback = ''
    return {
        'audience': audience,
        'kicker': 'Facilitator report' if audience == 'facilitator' else 'Client report',
        'title': context.course_name if context.course_name != 'All courses (aggregate)' else 'All courses',
        'source': state.get('loaded_file_label') or state.get('source', ''),
        'responses': m['response_count'], 'completeness': m['response_completeness'],
        'satisfaction': m['ratings']['OverallSatisfaction']['mean'], 'recommend': m.get('recommendation_percent'),
        'strongest': m['ratings'].get(m.get('strongest_area') or '', {}).get('label'),
        'lowest': m['ratings'].get(m.get('lowest_area') or '', {}).get('label'),
        'summary': summary,
        'working': [humanise(b) for b in _bullets(sections.get('What Worked Well', ''))],
        'improve': [humanise(b) for b in _bullets(sections.get('Areas for Improvement', ''))],
        'recommendations': [humanise(b) for b in _bullets(sections.get('Recommendations', ''))],
        'priority': next((v for k, v in notes.items() if k.startswith("Reviewer's priority")), ''),
        'priority_by': next((k[k.find('(') + 1:k.rfind(')')] for k in notes if k.startswith("Reviewer's priority")), ''),
        'caveats': [v for k, v in notes.items() if k in ('Caveat', 'Fairness note')],
        'feedback': feedback,
        'participation': humanise(sections.get('Participation Overview', '')),
        'method': humanise(sections.get('Analysis method', '')),
        'quotes': list(dict.fromkeys(humanise(q) for q in quotes))[:8] if audience == 'facilitator' else [],
        'record': [humanise(line.strip()[2:]) for line in record.splitlines() if line.strip().startswith('- ')],
        'approved': approved,
        'approver': workflow.approver if approved else '',
        'approved_at': approved_event.timestamp if approved and approved_event else '',
        'context': context, 'frame': frame,
        'charts_on': charts_enabled(state),
        'charts': charts_of(state) if charts_enabled(state) else [],
        'ratings_rows': rows, 'ratings_text': ratings_text(rows), 'who_text': who_text(frame, m),
        'themes_text': themes_text(context), 'groups_text': group_sentence, 'group_rows': group_rows,
        'theme_rows': [(t.name.replace('Emerging: ', 'New: '), t.category, t.frequency)
                       for t in sorted(context.themes, key=lambda t: -t.frequency)],
        'course_rows': _course_rows(frame), 'month_rows': _month_rows(frame),
        'distribution_rows': [(r['label'],) + tuple(r['dist']) for r in rows],
    }


def _course_rows(frame):
    from src.config import RATING_COLUMNS
    if 'CourseName' not in frame:
        return []
    names = frame['CourseName'].fillna('').astype(str).str.strip()
    counts = names[names != ''].value_counts()
    keep = [c for c in counts.index if counts[c] >= chart_lib.MIN_GROUP]
    if len(keep) < 2:
        return []
    out = []
    for course in keep[:10]:
        part = frame[names == course]
        means = []
        for column in RATING_COLUMNS:
            v = pd.to_numeric(part.get(column), errors='coerce') if column in part else pd.Series(dtype=float)
            v = v[v.between(1, 5)]
            means.append(f'{v.mean():.2f}' if len(v) else '–')
        out.append((course, f'{counts[course]:,}', *means))
    return out


def _month_rows(frame):
    if 'RecordedDate' not in frame or 'OverallSatisfaction' not in frame:
        return []
    dates = pd.to_datetime(frame['RecordedDate'], errors='coerce')
    values = pd.to_numeric(frame['OverallSatisfaction'], errors='coerce')
    data = pd.DataFrame({'m': dates.dt.to_period('M'), 'v': values.where(values.between(1, 5))}).dropna()
    monthly = data.groupby('m')['v'].agg(['count', 'mean'])
    monthly = monthly[monthly['count'] >= chart_lib.MIN_GROUP]
    if len(monthly) < 3:
        return []
    return [(f'{m.to_timestamp():%B %Y}', f'{int(r["count"]):,}', f'{r["mean"]:.2f}') for m, r in monthly.iterrows()]


def _date(iso=''):
    try:
        moment = datetime.fromisoformat(iso).astimezone() if iso else datetime.now().astimezone()
    except ValueError:
        moment = datetime.now().astimezone()
    return f'{moment.day} {moment:%B %Y}'


def status_line(data):
    if data['approved']:
        return f"Approved by {data['approver']} on {_date(data['approved_at'])}"
    return 'Draft for internal review: not yet approved'


def figures(data):
    """The key-figure strip: (value, label)."""
    items = [(f"{data['responses']:,}", 'responses analysed')]
    if data['satisfaction'] is not None:
        items.append((f"{data['satisfaction']:.2f}", 'average satisfaction out of 5'))
    if data['recommend'] is not None:
        items.append((f"{data['recommend']:.0f}%", 'would recommend the course'))
    items.append((f"{data['completeness']:.0f}%", 'answers complete'))
    return items[:4]


# ---- the blocks both documents are made of --------------------------------------------------------
class Block:
    """One piece of the page. `kind` decides how it is drawn; `data` holds what it shows."""

    def __init__(self, kind, **data):
        self.kind, self.data = kind, data

    def __repr__(self):
        return f'Block({self.kind})'


def _rich_list(items, limit):
    return [i for i in items if i][:limit]


def _page_one(data):
    head = [Block('kicker', text=data['kicker']), Block('title', text=data['title']),
            Block('meta', text=f"{data['responses']:,} survey responses  ·  {data['source']}  ·  {status_line(data)}"),
            Block('stats', items=figures(data)),
            Block('h1', text='At a glance'), Block('p', text=data['summary'] or 'No summary was written.')]
    highlights = []
    if data['strongest']:
        highlights.append(('Strongest area', data['strongest']))
    if data['lowest'] and data['lowest'] != data['strongest']:
        highlights.append(('Most room to improve', data['lowest']))
    if highlights:
        head.append(Block('highlights', items=highlights))
    boxes = Block('boxes', left=("What's working", _rich_list(data['working'], 5), 'No recurring strength stood out.'),
                  right=('What to improve', _rich_list(data['improve'], 5), 'No recurring concern stood out.'))
    options = []
    if data['ratings_text']:
        options.append(('after_head', [Block('h1', text='What the ratings show'), Block('p', text=data['ratings_text'])]))
    options.append(('end', [Block('h1', text='Who responded'), Block('p', text=data['who_text'])]))
    return head, boxes, options


def _page_two(data):
    recs = list(data['recommendations']) or ['No recommendation was kept.']
    callout = Block('callout', title='Recommended next steps', items=recs[:5], priority=data['priority'],
                    priority_by=data['priority_by'],
                    note='Recommendations are proposals for the team to discuss, not proven fixes.')
    learners = [Block('h1', text='What learners told us'), Block('p', text=data['themes_text'])]
    if data['feedback']:
        learners.append(Block('p', text=data['feedback']))
    about = [Block('h2', text='About this report')]
    for text in [data['participation'], data['method']] + [f'Reviewer caveat: {c}' for c in data['caveats']] + [
            'Ratings are learner perceptions, not measured learning outcomes. Theme counts are comments, not people, '
            'and a comment can touch several themes. Summaries and tables marked with figures are calculated directly '
            'from the survey data.']:
        if text:
            about.append(Block('small', text=text))
    record = [Block('h2', text='Review record' if data['approved'] else 'Review status')]
    if data['record']:
        rows = []
        for line in data['record'][:12]:
            label, sep, value = line.partition(':')
            if not sep:
                continue
            value = value.strip()
            if re.fullmatch(r'[0-9a-f]{64}.*', value):
                value = value[:16] + '…' + value[64:]
            rows.append((label.strip(), value))
        record.append(Block('record', rows=rows))
    else:
        record.append(Block('small', text='This draft has not been approved yet. A second person reviews it with the '
                                          'CLEAR questions before it is shared.'))
    return learners, callout, about, record


def _variable_options(data, page, has_chart):
    """Optional content that can grow a row or a quote at a time, to fill the last gap on a page."""
    sizes = {'quotes': len(data['quotes']), 'groups': max(len(data['group_rows']) - 1, 0),
             'themes': len(data['theme_rows']), 'courses': len(data['course_rows']),
             'months': len(data['month_rows']), 'distribution': len(data['distribution_rows']),
             'ratings': len(data['ratings_rows'])}
    if page == 1:
        order = ['ratings', 'distribution'] if has_chart else ['ratings', 'groups', 'distribution']
    else:
        order = ['quotes', 'groups', 'themes', 'courses', 'months', 'distribution', 'ratings']
    return [(kind, sizes[kind]) for kind in order if sizes[kind]]


def _variable_block(data, kind, n):
    if kind == 'quotes':
        return [Block('h2', text='In their words'), Block('quotes', items=data['quotes'][:n])]
    if kind == 'groups':
        label = data['group_rows'][0]
        return [Block('h2', text=f'Satisfaction by {label}'), Block('p', text=data['groups_text']),
                Block('table', head=(label.capitalize(), 'Responses', 'Satisfaction'),
                      rows=[(g, f'{c:,}', f'{v:.2f}') for g, c, v in data['group_rows'][1:1 + n]], widths=(0.6, 0.2, 0.2))]
    if kind == 'themes':
        return [Block('h2', text='Topics in the comments'),
                Block('table', head=('Topic', 'Type', 'Comments'),
                      rows=[(t, c, f'{f:,}') for t, c, f in data['theme_rows'][:n]], widths=(0.6, 0.2, 0.2))]
    if kind == 'courses':
        return [Block('h2', text='Results by course'),
                Block('table', head=('Course', 'Responses', 'Satisfaction', 'Content', 'Facilitator', 'Relevance'),
                      rows=data['course_rows'][:n], widths=(0.4, 0.12, 0.12, 0.12, 0.12, 0.12))]
    if kind == 'months':
        return [Block('h2', text='Satisfaction month by month'),
                Block('table', head=('Month', 'Responses', 'Average satisfaction'),
                      rows=data['month_rows'][:n], widths=(0.5, 0.2, 0.3))]
    if kind == 'distribution':
        return [Block('h2', text='How the ratings were spread'),
                Block('table', head=('Area', 'Rated 1', '2', '3', '4', 'Rated 5'),
                      rows=data['distribution_rows'][:n], widths=(0.4, 0.12, 0.12, 0.12, 0.12, 0.12))]
    if kind == 'ratings':
        return [Block('h2', text='Ratings at a glance'),
                Block('table', head=('Area', 'Average', 'Rated 4 or 5', 'Answers'),
                      rows=[(r['label'], f"{r['mean']:.2f}", f"{r['top']:.0f}%", f"{r['n']:,}") for r in data['ratings_rows']],
                      widths=(0.46, 0.18, 0.2, 0.16))]
    raise ValueError(kind)


# ---- measuring and drawing with reportlab --------------------------------------------------------------
_REGISTERED = None


def _fonts():
    """Register the bundled fonts once; fall back to the PDF base fonts if they are missing."""
    global _REGISTERED
    if _REGISTERED is None:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        try:
            for name, file in (('Body', 'Carlito-Regular.ttf'), ('Body-Bold', 'Carlito-Bold.ttf'),
                               ('Body-Italic', 'Carlito-Italic.ttf'), ('Head', 'Caladea-Bold.ttf')):
                pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))
            from reportlab.lib.fonts import addMapping
            addMapping('Body', 0, 0, 'Body'); addMapping('Body', 1, 0, 'Body-Bold')
            addMapping('Body', 0, 1, 'Body-Italic'); addMapping('Body', 1, 1, 'Body-Bold')
            _REGISTERED = {'body': 'Body', 'bold': 'Body-Bold', 'italic': 'Body-Italic', 'head': 'Head'}
        except Exception:
            _REGISTERED = {'body': 'Helvetica', 'bold': 'Helvetica-Bold', 'italic': 'Helvetica-Oblique',
                           'head': 'Times-Bold'}
    return _REGISTERED


def _styles():
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    f = _fonts()
    c = lambda h: colors.HexColor('#' + h)
    s = {
        'body': ParagraphStyle('body', fontName=f['body'], fontSize=BODY[0], leading=BODY[1], textColor=c(INK),
                               spaceAfter=GAP_PARA),
        'small': ParagraphStyle('small', fontName=f['body'], fontSize=SMALL[0], leading=SMALL[1], textColor=c(GREY),
                                spaceAfter=2),
        'bullet': ParagraphStyle('bullet', fontName=f['body'], fontSize=BULLET[0], leading=BULLET[1], textColor=c(INK),
                                 leftIndent=10, bulletIndent=0, spaceAfter=2),
        'h1': ParagraphStyle('h1', fontName=f['head'], fontSize=H1[0], leading=H1[1], textColor=c(NAVY),
                             spaceBefore=GAP_HEAD, spaceAfter=2),
        'h2': ParagraphStyle('h2', fontName=f['head'], fontSize=H2[0], leading=H2[1], textColor=c(NAVY),
                             spaceBefore=GAP_HEAD, spaceAfter=2),
        'title': ParagraphStyle('title', fontName=f['head'], fontSize=TITLE[0], leading=TITLE[1], textColor=c(NAVY),
                                spaceAfter=1),
        'kicker': ParagraphStyle('kicker', fontName=f['bold'], fontSize=KICK[0], leading=KICK[1], textColor=c(PLUM)),
        'meta': ParagraphStyle('meta', fontName=f['body'], fontSize=SMALL[0], leading=SMALL[1], textColor=c(GREY),
                               spaceAfter=GAP_BLOCK),
        'quote': ParagraphStyle('quote', fontName=f['italic'], fontSize=BODY[0], leading=BODY[1], textColor=c(INK)),
        'cell': ParagraphStyle('cell', fontName=f['body'], fontSize=SMALL[0], leading=SMALL[1], textColor=c(INK)),
        'cellhead': ParagraphStyle('cellhead', fontName=f['bold'], fontSize=SMALL[0], leading=SMALL[1], textColor=c(NAVY)),
        'white': ParagraphStyle('white', fontName=f['body'], fontSize=BODY[0], leading=BODY[1], textColor=colors.white,
                                leftIndent=14, bulletIndent=0, spaceAfter=GAP_PARA),
    }
    return s


def _markup(text, lead_bold=False, bold_font=None):
    from xml.sax.saxutils import escape
    head = ''
    if lead_bold and ':' in text[:60]:
        first, text = text.split(':', 1)
        head = f'<b>{escape(first)}:</b>'
    return head + ''.join(f'<b>{escape(p)}</b>' if b else escape(p) for p, b in emphasis_runs(text))


def _flowables(block, width, styles, images=None):
    """reportlab flowables for one block (used to measure the page and to draw the PDF)."""
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape
    c = lambda h: colors.HexColor('#' + h)
    k, d = block.kind, block.data
    if k in ('h1', 'h2') and d.get('extra'):
        return [Paragraph(escape(d['text']), styles[k].clone(k + 'x', spaceBefore=GAP_HEAD + d['extra']))]
    if k in ('h1', 'h2', 'title', 'kicker', 'meta'):
        return [Paragraph(escape(d['text']), styles[k])]
    if k == 'p':
        return [Paragraph(_markup(d['text']), styles['body'])]
    if k == 'small':
        return [Paragraph(_markup(d['text']), styles['small'])]
    if k == 'highlights':
        bits = [f"<font color='#{PLUM}'><b>{escape(a)}:</b></font> <b>{escape(b)}</b>" for a, b in d['items']]
        return [Paragraph('&nbsp;&nbsp;&nbsp;&nbsp;'.join(bits), styles['body'])]
    if k == 'stats':
        f = _fonts()
        from reportlab.lib.styles import ParagraphStyle
        cell = ParagraphStyle('s', fontName=f['body'], leading=STAT_LABEL[1], fontSize=STAT_LABEL[0], textColor=c(GREY))
        value = ParagraphStyle('v', fontName=f['head'], leading=STAT[1], fontSize=STAT[0], textColor=c(NAVY))
        row = [[Paragraph(v, value), Paragraph(escape(l), cell)] for v, l in d['items']]
        t = Table([row], colWidths=[width / len(row)] * len(row))
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), c(LILAC_BG)), ('LINEBEFORE', (0, 0), (-1, -1), 2, c(NAVY)),
                               ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                               ('LEFTPADDING', (0, 0), (-1, -1), 8), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        return [t, Spacer(1, GAP_BLOCK)]
    if k == 'boxes':
        cols = []
        for title, items, empty in (d['left'], d['right']):
            flow = [Paragraph(escape(title), styles['h2'].clone('bh', spaceBefore=0))]
            flow += [Paragraph(_markup(i, True), styles['bullet'], bulletText='•') for i in (items or [empty])]
            cols.append(flow)
        t = Table([cols], colWidths=[width / 2] * 2)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, 0), c(GREEN_BG)), ('BACKGROUND', (1, 0), (1, 0), c(AMBER_BG)),
                               ('LINEABOVE', (0, 0), (0, 0), 2, c(GOOD)), ('LINEABOVE', (1, 0), (1, 0), 2, c(WARN)),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 6),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('LEFTPADDING', (0, 0), (-1, -1), 8),
                               ('RIGHTPADDING', (0, 0), (-1, -1), 8)]))
        return [Spacer(1, GAP_BLOCK), t]
    if k == 'charts':
        cells = []
        for offset, spec in enumerate(d['specs']):
            png = images.get((spec['title'], d['height'])) if images is not None else None
            img = (Image(io.BytesIO(png), width=COL_W * cm, height=d['height'] * cm) if png
                   else Spacer(COL_W * cm, d['height'] * cm))
            caption = Paragraph(f'<font color="#{NAVY}"><b>Figure {d["start"] + offset}.</b></font> '
                                f'<i>{escape(spec["title"])}</i>', styles['small'])
            cells.append([img, caption])
        while len(cells) < 2:
            cells.append('')
        t = Table([cells], colWidths=[width / 2] * 2)
        t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 4),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
        return [t]
    if k == 'quotes':
        out = []
        for quote in d['items']:
            q = Table([[Paragraph(f'“{escape(quote)}”', styles['quote'])]], colWidths=[width])
            q.setStyle(TableStyle([('LINEBEFORE', (0, 0), (0, 0), 2, c(PLUM)), ('LEFTPADDING', (0, 0), (-1, -1), 8),
                                   ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
            out += [q, Spacer(1, 3)]
        return out
    if k == 'table':
        rows = [[Paragraph(escape(h), styles['cellhead']) for h in d['head']]]
        rows += [[Paragraph(escape(str(v)), styles['cell']) for v in r] for r in d['rows']]
        t = Table(rows, colWidths=[width * w for w in d['widths']])
        t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 1, c(NAVY)), ('LINEBELOW', (0, 1), (-1, -1), 0.4, c(LINE)),
                               ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                               ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        return [t, Spacer(1, GAP_BLOCK)]
    if k == 'record':
        rows = [[Paragraph(f'<b><font color="#{NAVY}">{escape(a)}</font></b>', styles['small']),
                 Paragraph(escape(b), styles['small'])] for a, b in d['rows']]
        if not rows:
            return []
        t = Table(rows, colWidths=[5.6 * cm, width - 5.6 * cm])
        t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                               ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
        return [t]
    if k == 'callout':
        f = _fonts()
        flow = [Paragraph(escape(d['title']), styles['h1'].clone('ch', textColor=colors.white, spaceBefore=0))]
        if d.get('priority'):
            flow.append(Paragraph(f'<font color="#{LILAC}"><b>Reviewer\'s priority'
                                  + (f' ({escape(d["priority_by"])})' if d.get('priority_by') else '') + ':</b></font> '
                                  + _markup(d['priority']), styles['white'].clone('wp', leftIndent=0)))
        flow += [Paragraph(_markup(item, True), styles['white'], bulletText=f'{n}.')
                 for n, item in enumerate(d['items'], 1)]
        flow.append(Paragraph(f'<i>{escape(d["note"])}</i>', styles['small'].clone('cn', textColor=c(LILAC), fontName=f['italic'])))
        t = Table([[flow]], colWidths=[width])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), c(NAVY)), ('TOPPADDING', (0, 0), (-1, -1), 9),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 8), ('LEFTPADDING', (0, 0), (-1, -1), 12),
                               ('RIGHTPADDING', (0, 0), (-1, -1), 12)]))
        return [Spacer(1, GAP_BLOCK), t, Spacer(1, 2)]
    raise ValueError(k)


def _height(blocks, styles):
    """Height in cm of a list of blocks laid out in the text column."""
    width = TEXT_W * CM
    total = 0.0
    for i, block in enumerate(blocks):
        for f in _flowables(block, width, styles):
            _, h = f.wrap(width, 10_000)
            before = f.getSpaceBefore() if (i or total) else 0
            total += h + before + f.getSpaceAfter()
    return total / CM


def _chart_row_height(height, styles):
    return _height([Block('charts', specs=[{'title': 'Sample'}], start=1, height=height)], styles)


def plan(data):
    """Decide what goes on each page so both are full. Returns (page1 blocks, page2 blocks)."""
    styles = _styles()
    target = FRAME_H * FILL
    specs = data['charts'][:chart_lib.MAX_CHARTS] if data['charts_on'] else []
    rows = [specs[i:i + 2] for i in range(0, len(specs), 2)]

    head, boxes, options1 = _page_one(data)
    learners, callout, about, record = _page_two(data)
    used_variable = set()

    def assemble(page, chosen, chart_height, extras):
        if page == 1:
            blocks = list(head)
            if 'after_head' in chosen:
                blocks += chosen['after_head']
            if rows:
                blocks.append(Block('charts', specs=rows[0], start=1, height=chart_height))
            blocks.append(boxes)
            if 'end' in chosen:
                blocks += chosen['end']
        else:
            blocks = []
            if len(rows) > 1:
                blocks.append(Block('charts', specs=rows[1], start=3, height=chart_height))
            blocks += learners
            for kind, n in extras:
                if kind == 'quotes':
                    blocks += _variable_block(data, kind, n)
            blocks.append(callout)
            for kind, n in extras:
                if kind != 'quotes':
                    blocks += _variable_block(data, kind, n)
            blocks += about + record
        if page == 1:
            for kind, n in extras:
                blocks += _variable_block(data, kind, n)
        return blocks

    def fill(page):
        has_chart = bool((page == 1 and rows) or (page == 2 and len(rows) > 1))
        chosen, extras = {}, []
        height = CHART_PREFERRED if has_chart else 0
        current = lambda: _height(assemble(page, chosen, height, extras), styles)
        if page == 1:
            for slot, blocks in options1:
                chosen[slot] = blocks
                if current() > target:
                    del chosen[slot]
        for kind, maximum in _variable_options(data, page, has_chart):
            if kind in used_variable:
                continue
            best = 0
            for n in range(1, maximum + 1):
                extras.append((kind, n))
                fits = current() <= target
                extras.pop()
                if not fits:
                    break
                best = n
            if best >= (1 if kind in ('quotes', 'ratings', 'distribution') else min(3, maximum)):
                extras.append((kind, best))
                used_variable.add(kind)
        if has_chart:
            height = CHART_MIN
            while current() > target and extras:      # charts must stay readable: drop extras first
                kind, n = extras.pop()
                used_variable.discard(kind)
            low, high = CHART_MIN, CHART_MAX
            for _ in range(16):                       # the tallest charts that still fit
                height = (low + high) / 2
                if current() <= target:
                    low = height
                else:
                    high = height
            height = low
            if height > CHART_MAX - 0.05:          # charts are as large as they should be: add tables instead
                for kind, maximum in _variable_options(data, page, has_chart):
                    if kind in used_variable:
                        continue
                    best = 0
                    for n in range(1, maximum + 1):
                        extras.append((kind, n)); fits = current() <= target; extras.pop()
                        if not fits:
                            break
                        best = n
                    if best >= (1 if kind in ('quotes', 'ratings', 'distribution') else min(3, maximum)):
                        extras.append((kind, best)); used_variable.add(kind)
        return assemble(page, chosen, height, extras)

    def settle(blocks):
        """Share any last gap as a little extra space above each heading, so the page ends flush."""
        heads = [b for i, b in enumerate(blocks) if b.kind in ('h1', 'h2') and i]
        gap = (target - _height(blocks, styles)) * CM
        if heads and gap > 0:
            for b in heads:
                b.data['extra'] = min(gap / len(heads), 16.0)
        return blocks

    return settle(fill(1)), settle(fill(2))


def _chart_images(data, pages):
    images = {}
    for block in pages[0] + pages[1]:
        if block.kind != 'charts':
            continue
        for spec in block.data['specs']:
            key = (spec['title'], block.data['height'])
            if key not in images:
                images[key] = chart_lib.render(spec, data['frame'], data['context'], COL_W / 2.54,
                                               block.data['height'] / 2.54)
    return images


# ---- PDF ---------------------------------------------------------------------------------------------
def build_pdf(data, logo=LOGO, pages=None):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import BaseDocTemplate, Frame, KeepInFrame, PageBreak, PageTemplate

    pages = pages or plan(data)
    images = _chart_images(data, pages)
    styles = _styles()
    f = _fonts()
    navy, grey = colors.HexColor('#' + NAVY), colors.HexColor('#' + GREY)
    width, height = A4

    def decorate(canvas, doc):
        canvas.saveState()
        if Path(logo).is_file():
            canvas.drawImage(str(logo), MARGIN_X * cm, height - 1.95 * cm, height=1.05 * cm,
                             width=1.05 * cm * 800 / 190, mask='auto')
        canvas.setFont(f['bold'], 8); canvas.setFillColor(navy)
        canvas.drawRightString(width - MARGIN_X * cm, height - 1.3 * cm, 'Learning Futures')
        canvas.setFont(f['body'], 8); canvas.setFillColor(grey)
        canvas.drawRightString(width - MARGIN_X * cm, height - 1.65 * cm, 'Course evaluation report')
        canvas.setStrokeColor(navy); canvas.setLineWidth(0.8)
        canvas.line(MARGIN_X * cm, height - 2.1 * cm, width - MARGIN_X * cm, height - 2.1 * cm)
        canvas.setFont(f['body'], 7.5); canvas.setFillColor(grey)
        canvas.drawString(MARGIN_X * cm, 0.9 * cm, f"{status_line(data)}  ·  Prepared {_date()}")
        canvas.drawRightString(width - MARGIN_X * cm, 0.9 * cm, f'Page {doc.page} of 2')
        canvas.restoreState()

    frame = Frame(MARGIN_X * cm, MARGIN_BOTTOM * cm, TEXT_W * cm, FRAME_H * cm, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    stream = io.BytesIO()
    doc = BaseDocTemplate(stream, pagesize=A4, title=f"{data['kicker']}: {data['title']}", author='Learning Futures')
    doc.addPageTemplates([PageTemplate('page', [frame], onPage=decorate)])
    story = []
    for number, blocks in enumerate(pages):
        flow = []
        for block in blocks:
            flow += _flowables(block, TEXT_W * cm, styles, images)
        story.append(KeepInFrame(TEXT_W * cm, FRAME_H * cm, flow, mode='shrink'))
        if number == 0:
            story.append(PageBreak())
    doc.build(story)
    return stream.getvalue()


# ---- Word --------------------------------------------------------------------------------------------
def build_docx(data, logo=LOGO, pages=None):
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    pages = pages or plan(data)
    images = _chart_images(data, pages)
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(PAGE_W), Cm(PAGE_H)
    section.left_margin = section.right_margin = Cm(MARGIN_X)
    section.top_margin, section.bottom_margin = Cm(MARGIN_TOP), Cm(MARGIN_BOTTOM)
    section.header_distance, section.footer_distance = Cm(0.8), Cm(0.6)

    base = doc.styles['Normal']
    base.font.name, base.font.size = 'Calibri', Pt(BODY[0])
    base.font.color.rgb = RGBColor.from_string(INK)
    base.element.rPr.rFonts.set(qn('w:eastAsia'), 'Calibri')
    base.paragraph_format.space_after = Pt(0)
    base.paragraph_format.space_before = Pt(0)

    def shade(cell, colour):
        tc = cell._tc.get_or_add_tcPr()
        fill = OxmlElement('w:shd')
        fill.set(qn('w:val'), 'clear'); fill.set(qn('w:color'), 'auto'); fill.set(qn('w:fill'), colour)
        tc.append(fill)

    def borders(cell, **sides):
        tc = cell._tc.get_or_add_tcPr()
        node = OxmlElement('w:tcBorders')
        for side in ('top', 'left', 'bottom', 'right'):
            spec = sides.get(side)
            el = OxmlElement(f'w:{side}')
            if spec:
                el.set(qn('w:val'), 'single'); el.set(qn('w:sz'), str(spec[0])); el.set(qn('w:color'), spec[1])
            else:
                el.set(qn('w:val'), 'nil')
            node.append(el)
        tc.append(node)

    def margins(cell, top=0, side=0, bottom=None):
        tc = cell._tc.get_or_add_tcPr()
        node = OxmlElement('w:tcMar')
        for edge, value in (('top', top), ('bottom', top if bottom is None else bottom), ('left', side), ('right', side)):
            el = OxmlElement(f'w:{edge}'); el.set(qn('w:w'), str(int(value * 20))); el.set(qn('w:type'), 'dxa')
            node.append(el)
        tc.append(node)

    def plain_table(table, widths_cm):
        props = table._tbl.tblPr
        node = OxmlElement('w:tblBorders')
        for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            el = OxmlElement(f'w:{side}'); el.set(qn('w:val'), 'nil'); node.append(el)
        props.append(node)
        cell_margin = OxmlElement('w:tblCellMar')
        for edge in ('left', 'right', 'top', 'bottom'):
            el = OxmlElement(f'w:{edge}'); el.set(qn('w:w'), '0'); el.set(qn('w:type'), 'dxa'); cell_margin.append(el)
        props.append(cell_margin)
        layout = OxmlElement('w:tblLayout'); layout.set(qn('w:type'), 'fixed'); props.append(layout)
        table.autofit = False
        for column, w in zip(table.columns, widths_cm):
            column.width = Cm(w)
        for row in table.rows:
            for cell, w in zip(row.cells, widths_cm):
                cell.width = Cm(w)

    def para(container, size_leading, before=0.0, after=0.0, align=None, indent=None, hanging=None, first=False):
        p = container.paragraphs[0] if first else container.add_paragraph()
        fmt = p.paragraph_format
        fmt.space_before, fmt.space_after = Pt(before), Pt(after)
        fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        fmt.line_spacing = Pt(size_leading[1])
        if align:
            p.alignment = align
        if indent is not None:
            fmt.left_indent = Pt(indent)
        if hanging is not None:
            fmt.first_line_indent = Pt(-hanging)
        return p

    def run(p, text, size, bold=False, colour=INK, italic=False, font=None):
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        r.font.size = Pt(size)
        r.font.color.rgb = RGBColor.from_string(colour)
        if font:
            r.font.name = font
            r._element.rPr.rFonts.set(qn('w:eastAsia'), font)
        return r

    def rich(p, text, size, colour=INK, lead_bold=False):
        if lead_bold and ':' in text[:60]:
            head, text = text.split(':', 1)
            run(p, head + ':', size, True, colour)
        for part, bold in emphasis_runs(text):
            run(p, part, size, bold, colour)

    def field(p, code):
        for kind in ('begin', 'instr', 'separate', 'text', 'end'):
            r = p.add_run()
            if kind == 'instr':
                el = OxmlElement('w:instrText'); el.set(qn('xml:space'), 'preserve'); el.text = f' {code} '; r._r.append(el)
            elif kind == 'text':
                r.text = '1'
            else:
                el = OxmlElement('w:fldChar'); el.set(qn('w:fldCharType'), kind); r._r.append(el)
            r.font.size, r.font.color.rgb = Pt(7.5), RGBColor.from_string(GREY)

    # header and footer
    header = section.header
    table = header.add_table(1, 2, Cm(TEXT_W))
    plain_table(table, (TEXT_W / 2, TEXT_W / 2))
    left, right = table.rows[0].cells
    if Path(logo).is_file():
        left.paragraphs[0].add_run().add_picture(str(logo), height=Cm(1.05))
    p = right.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run(p, 'Learning Futures', 8, True, NAVY)
    p = right.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run(p, 'Course evaluation report', 8, False, GREY)
    rule = header.paragraphs[0]
    rule.paragraph_format.space_after = Pt(0)
    pPr = rule._p.get_or_add_pPr()
    bdr = OxmlElement('w:pBdr'); bottom = OxmlElement('w:bottom')
    for key, value in (('val', 'single'), ('sz', '8'), ('space', '1'), ('color', NAVY)):
        bottom.set(qn(f'w:{key}'), value)
    bdr.append(bottom); pPr.append(bdr)
    header._element.append(rule._p)       # the rule sits under the logo row
    foot = section.footer.add_table(1, 2, Cm(TEXT_W))
    plain_table(foot, (TEXT_W - 4, 4))
    run(foot.rows[0].cells[0].paragraphs[0], f"{status_line(data)}  ·  Prepared {_date()}", 7.5, False, GREY)
    p = foot.rows[0].cells[1].paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run(p, 'Page ', 7.5, False, GREY); field(p, 'PAGE'); run(p, ' of ', 7.5, False, GREY); field(p, 'NUMPAGES')

    body = doc

    def new_para(size_leading, before=0.0, after=0.0, **kw):
        return para(body, size_leading, before, after, **kw)

    def heading(text, sl, top, extra=0.0):
        p = new_para(sl, 0 if top else GAP_HEAD + extra, 2)
        p.paragraph_format.keep_with_next = True
        run(p, text, sl[0], True, NAVY, font='Cambria')

    def add_table(rows, cols, widths):
        t = body.add_table(rows, cols)
        t.alignment = WD_TABLE_ALIGNMENT.LEFT
        plain_table(t, widths)
        return t

    def spacer(points):
        p = new_para((1, max(points, 1)))
        p.paragraph_format.line_spacing = Pt(max(points, 1))
        run(p, '', 1)

    for number, blocks in enumerate(pages):
        if number:
            p = body.add_paragraph()
            p.paragraph_format.space_after = p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
            p.paragraph_format.line_spacing = Pt(1)
            r = p.add_run(); r.font.size = Pt(1); r.add_break(WD_BREAK.PAGE)
        for index, block in enumerate(blocks):
            k, d = block.kind, block.data
            top = index == 0
            if k == 'kicker':
                run(new_para(KICK), d['text'], KICK[0], True, PLUM)
            elif k == 'title':
                run(new_para(TITLE, after=1), d['text'], TITLE[0], True, NAVY, font='Cambria')
            elif k == 'meta':
                run(new_para(SMALL, after=GAP_BLOCK), d['text'], SMALL[0], False, GREY)
            elif k in ('h1', 'h2'):
                heading(d['text'], H1 if k == 'h1' else H2, top, d.get('extra', 0.0))
            elif k == 'p':
                rich(new_para(BODY, after=GAP_PARA), d['text'], BODY[0])
            elif k == 'small':
                rich(new_para(SMALL, after=2), d['text'], SMALL[0], GREY)
            elif k == 'highlights':
                p = new_para(BODY, after=GAP_PARA)
                for i, (a, b) in enumerate(d['items']):
                    run(p, ('    ' if i else '') + a + ':', BODY[0], True, PLUM)
                    run(p, ' ' + b, BODY[0], True, INK)
            elif k == 'stats':
                items = d['items']
                t = add_table(1, len(items), [TEXT_W / len(items)] * len(items))
                for cell, (value, label) in zip(t.rows[0].cells, items):
                    shade(cell, LILAC_BG); margins(cell, 6, 8); borders(cell, left=(16, NAVY))
                    run(para(cell, STAT, first=True), value, STAT[0], True, NAVY, font='Cambria')
                    run(para(cell, STAT_LABEL), label, STAT_LABEL[0], False, GREY)
                spacer(GAP_BLOCK)
            elif k == 'boxes':
                spacer(GAP_BLOCK)
                t = add_table(1, 2, (TEXT_W / 2, TEXT_W / 2))
                for cell, (title, items, empty), fill_colour, accent in zip(
                        t.rows[0].cells, (d['left'], d['right']), (GREEN_BG, AMBER_BG), (GOOD, WARN)):
                    shade(cell, fill_colour); margins(cell, 6, 8); borders(cell, top=(16, accent))
                    p = para(cell, H2, after=2, first=True)
                    run(p, title, H2[0], True, NAVY, font='Cambria')
                    for item in items or [empty]:
                        p = para(cell, BULLET, after=2, indent=10, hanging=10)
                        run(p, '•\t', BULLET[0], False, INK)
                        p.paragraph_format.tab_stops.add_tab_stop(Pt(10))
                        rich(p, item, BULLET[0], INK, lead_bold=True)
            elif k == 'charts':
                t = add_table(1, 2, (TEXT_W / 2, TEXT_W / 2))
                for offset, cell in enumerate(t.rows[0].cells):
                    margins(cell, 0, 0)
                    cell.paragraphs[0].paragraph_format.space_before = Pt(4)
                    if offset >= len(d['specs']):
                        continue
                    spec = d['specs'][offset]
                    png = images[(spec['title'], d['height'])]
                    cell.paragraphs[0].add_run().add_picture(io.BytesIO(png), width=Cm(COL_W), height=Cm(d['height']))
                    p = para(cell, SMALL, after=2)
                    run(p, f"Figure {d['start'] + offset}. ", SMALL[0], True, NAVY)
                    run(p, spec['title'], SMALL[0], False, GREY, italic=True)
            elif k == 'quotes':
                for quote in d['items']:
                    p = new_para(BODY, after=3, indent=10)
                    pPr = p._p.get_or_add_pPr(); bdr = OxmlElement('w:pBdr'); left_b = OxmlElement('w:left')
                    for key, value in (('val', 'single'), ('sz', '16'), ('space', '6'), ('color', PLUM)):
                        left_b.set(qn(f'w:{key}'), value)
                    bdr.append(left_b); pPr.append(bdr)
                    run(p, f'“{quote}”', BODY[0], False, INK, italic=True)
            elif k == 'table':
                widths = [TEXT_W * w for w in d['widths']]
                t = add_table(1 + len(d['rows']), len(d['head']), widths)
                for col, text in enumerate(d['head']):
                    cell = t.rows[0].cells[col]
                    margins(cell, 2, 2); borders(cell, bottom=(8, NAVY))
                    run(para(cell, SMALL, first=True), text, SMALL[0], True, NAVY)
                for r, values in enumerate(d['rows'], 1):
                    for col, text in enumerate(values):
                        cell = t.rows[r].cells[col]
                        margins(cell, 2, 2); borders(cell, bottom=(3, LINE))
                        run(para(cell, SMALL, first=True), str(text), SMALL[0], False, INK)
                spacer(GAP_BLOCK)
            elif k == 'record':
                t = add_table(len(d['rows']), 2, (5.6, TEXT_W - 5.6))
                for r, (a, b) in enumerate(d['rows']):
                    cells = t.rows[r].cells
                    margins(cells[0], 0, 0, 1); margins(cells[1], 0, 0, 1)
                    run(para(cells[0], SMALL, first=True), a, SMALL[0], True, NAVY)
                    run(para(cells[1], SMALL, first=True), b, SMALL[0], False, INK)
            elif k == 'callout':
                spacer(GAP_BLOCK)
                t = add_table(1, 1, (TEXT_W,))
                cell = t.rows[0].cells[0]
                shade(cell, NAVY); margins(cell, 9, 12, 8)
                run(para(cell, H1, after=2, first=True), d['title'], H1[0], True, 'FFFFFF', font='Cambria')
                if d.get('priority'):
                    p = para(cell, BODY, after=GAP_PARA)
                    run(p, "Reviewer's priority" + (f" ({d['priority_by']})" if d.get('priority_by') else '') + ': ',
                        BODY[0], True, LILAC)
                    rich(p, d['priority'], BODY[0], 'FFFFFF')
                for n, item in enumerate(d['items'], 1):
                    p = para(cell, BODY, after=GAP_PARA, indent=14, hanging=14)
                    p.paragraph_format.tab_stops.add_tab_stop(Pt(14))
                    run(p, f'{n}.\t', BODY[0], True, LILAC)
                    rich(p, item, BODY[0], 'FFFFFF', lead_bold=True)
                run(para(cell, SMALL), d['note'], SMALL[0], False, LILAC, italic=True)
                spacer(2)
    end = body.add_paragraph()            # Word needs a paragraph after a final table; keep it 1 pt tall
    end.paragraph_format.space_after = end.paragraph_format.space_before = Pt(0)
    end.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    end.paragraph_format.line_spacing = Pt(1)
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


MEDIA = {'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
         'pdf': 'application/pdf', 'md': 'text/markdown; charset=utf-8'}


def export_bytes(state, text, fmt):
    """The designed two-page report (docx/pdf) or plain Markdown (md) for this text."""
    if fmt == 'md':
        from src.reporting.exporter import markdown_bytes
        return markdown_bytes(text)
    if fmt not in ('docx', 'pdf'):
        raise ValueError('Choose Word (.docx), PDF (.pdf) or Markdown (.md).')
    data = report_data(state, text)
    return build_docx(data) if fmt == 'docx' else build_pdf(data)
