"""Report charts: a small catalogue of chart types, a plain-English request parser, and
matplotlib rendering in the Adelaide University palette.

A chart is a small dict ("spec") saved with the report, e.g.
    {"kind": "group_box", "measure": "OverallSatisfaction", "group": "DeliveryMode"}
so the same charts appear in the browser preview, the Word document and the PDF.
Charts only ever show aggregated survey numbers; groups with fewer than MIN_GROUP
responses are left out so nobody can be singled out.
"""
from __future__ import annotations

import io
import re

import pandas as pd

from src.analytics.quantitative import LABELS
from src.config import RATING_COLUMNS

NAVY, PLUM, LILAC, MIST = '#151054', '#5B2EA6', '#C9B8EE', '#EEE9F8'
GOOD, WARN, NEUTRAL, INK, MUTED = '#2E7D5B', '#C27C0E', '#8E86A3', '#1E1631', '#6B6382'
SCALE = ['#B4234B', '#E28B6B', '#D9D3E6', '#8F77D2', '#151054']   # ratings 1..5
MIN_GROUP = 5
MAX_CHARTS = 4

GROUPS = {'CourseName': 'course', 'DeliveryMode': 'delivery mode', 'FacilitatorCode': 'facilitator',
          'ClientType': 'client type'}
KINDS = {
    'ratings_bar': 'Average rating for each area',
    'ratings_stacked': 'How learners rated each area (1 to 5)',
    'ratings_box': 'Spread of ratings (box plot)',
    'themes': 'What learners talked about (themes)',
    'recommend': 'Would recommend the course',
    'group_bar': 'Average rating compared by group',
    'group_box': 'Spread of ratings compared by group (box plot)',
    'trend': 'Average rating over time (by month)',
}
DEFAULT_CHARTS = [{'kind': 'ratings_stacked'}, {'kind': 'ratings_box'}, {'kind': 'themes'}, {'kind': 'recommend'}]


# ---- specs ---------------------------------------------------------------------------------
def clean_spec(spec):
    """Validate a chart spec from a person or a request; raises ValueError when unusable."""
    if not isinstance(spec, dict) or spec.get('kind') not in KINDS:
        raise ValueError('Choose one of the available chart types.')
    out = {'kind': spec['kind']}
    if out['kind'] in ('group_bar', 'group_box', 'trend'):
        measure = spec.get('measure') or 'OverallSatisfaction'
        if measure not in RATING_COLUMNS:
            raise ValueError('Choose a rating to chart.')
        out['measure'] = measure
    if out['kind'] in ('group_bar', 'group_box'):
        if spec.get('group') not in GROUPS:
            raise ValueError('Choose what to compare by: course, delivery mode, facilitator or client type.')
        out['group'] = spec['group']
    title = str(spec.get('title') or '').strip()
    out['title'] = title[:90] or default_title(out)
    return out


def default_title(spec):
    kind = spec['kind']
    if kind in ('group_bar', 'group_box'):
        measure = LABELS[spec['measure']].lower()
        verb = 'Average' if kind == 'group_bar' else 'Spread of'
        return f"{verb} {measure} by {GROUPS[spec['group']]}"
    if kind == 'trend':
        return f"{LABELS[spec['measure']]} over time"
    return KINDS[kind]


def chart_list(specs):
    cleaned = []
    for spec in (specs or [])[:MAX_CHARTS]:
        cleaned.append(clean_spec(spec))
    return cleaned


_MEASURES = [('effectiveness', 'FacilitatorEffectiveness'), ('teaching', 'FacilitatorEffectiveness'),
             ('content', 'ContentQuality'), ('material', 'ContentQuality'), ('quality', 'ContentQuality'),
             ('relevan', 'CourseRelevance'), ('useful', 'CourseRelevance'),
             ('satisf', 'OverallSatisfaction'), ('overall', 'OverallSatisfaction')]
_GROUP_WORDS = [('delivery', 'DeliveryMode'), ('online', 'DeliveryMode'), ('in person', 'DeliveryMode'),
                ('mode', 'DeliveryMode'), ('client', 'ClientType'), ('organisation', 'ClientType'),
                ('organization', 'ClientType'), ('course', 'CourseName'), ('program', 'CourseName'),
                ('facilitator', 'FacilitatorCode'), ('presenter', 'FacilitatorCode'), ('trainer', 'FacilitatorCode')]


def parse_request(text):
    """Turn a plain-English description into a chart spec. Returns (spec, explanation)."""
    t = ' ' + re.sub(r'\s+', ' ', (text or '').lower()) + ' '
    if not t.strip():
        raise ValueError('Describe the chart you want, for example "box plot of satisfaction by delivery mode".')
    group = None
    match = (re.search(r'\b(?:by|per|each|across|between|for every)\b(.*)', t)
             or re.search(r'\b(?:compare[ds]?|comparing)\b(.*)', t))
    tail = match.group(1) if match else ''
    for word, column in _GROUP_WORDS:
        if word in tail:
            group = column
            break
    measure = next((column for word, column in _MEASURES if word in t), None)
    if 'facilitator effectiveness' in t:
        measure = 'FacilitatorEffectiveness'
    box = bool(re.search(r'box|spread|range|variation|distribution of score', t))
    if re.search(r'theme|topic|talk(ed)? about|comment', t):
        spec = {'kind': 'themes'}
    elif re.search(r'recommend', t):
        spec = {'kind': 'recommend'}
    elif re.search(r'over time|trend|month|timeline|change over', t):
        spec = {'kind': 'trend', 'measure': measure or 'OverallSatisfaction'}
    elif group:
        spec = {'kind': 'group_box' if box else 'group_bar', 'measure': measure or 'OverallSatisfaction', 'group': group}
    elif box:
        spec = {'kind': 'ratings_box'}
    elif re.search(r'stack|likert|1 to 5|how (people|learners) rated|breakdown|split', t):
        spec = {'kind': 'ratings_stacked'}
    elif re.search(r'average|mean|rating|score|bar', t):
        spec = {'kind': 'ratings_bar'}
    else:
        raise ValueError('I could not match that to a chart. Try "average ratings", "box plot by course", '
                         '"themes", "would recommend" or "satisfaction over time".')
    spec = clean_spec(spec)
    return spec, f"Added: {spec['title']}."


def _horizontal():
    import matplotlib
    major, minor = (int(x) for x in matplotlib.__version__.split('.')[:2])
    return {'orientation': 'horizontal'} if (major, minor) >= (3, 10) else {'vert': False}



# ---- rendering -------------------------------------------------------------------------------
_FONT = None


def _font():
    """The first installed font from a list that matches the Word document (Calibri on Windows)."""
    global _FONT
    if _FONT is None:
        import logging
        from matplotlib import font_manager
        logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
        installed = {f.name for f in font_manager.fontManager.ttflist}
        _FONT = next((name for name in ('Calibri', 'Segoe UI', 'Carlito', 'Helvetica', 'Arial', 'Liberation Sans')
                      if name in installed), 'DejaVu Sans')
    return _FONT


def _figure(width, height):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        'font.family': [_font()], 'font.size': 8.5,
        'axes.edgecolor': '#CFC8DD', 'axes.labelcolor': MUTED, 'xtick.color': MUTED, 'ytick.color': INK,
        'axes.titlesize': 10, 'axes.titleweight': 'bold', 'axes.titlecolor': NAVY, 'axes.titlelocation': 'left',
        'axes.titlepad': 8, 'figure.dpi': 200, 'savefig.dpi': 200,
    })
    fig, ax = plt.subplots(figsize=(width, height))
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    return plt, fig, ax


def _ratings(frame, column):
    values = pd.to_numeric(frame[column], errors='coerce') if column in frame else pd.Series(dtype=float)
    return values.where(values.between(1, 5)).dropna()


def _groups(frame, spec):
    group = frame[spec['group']].fillna('Not recorded').astype(str).str.strip().replace('', 'Not recorded')
    values = pd.to_numeric(frame[spec['measure']], errors='coerce')
    data = pd.DataFrame({'group': group, 'value': values.where(values.between(1, 5))}).dropna()
    counts = data['group'].value_counts()
    keep = [name for name in counts.index if counts[name] >= MIN_GROUP][:8]
    return data[data['group'].isin(keep)], counts


def _short(label, size=28):
    label = str(label)
    return label if len(label) <= size else label[:size - 1].rstrip() + '…'


def render(spec, frame, context, width=3.6, height=2.5):
    """Return PNG bytes for one chart spec."""
    spec = clean_spec(spec)
    plt, fig, ax = _figure(width, height)
    kind = spec['kind']
    try:
        if kind == 'ratings_bar':
            labels, means = [], []
            for column in RATING_COLUMNS:
                values = _ratings(frame, column)
                if len(values):
                    labels.append(LABELS[column]); means.append(values.mean())
            bars = ax.barh(labels[::-1], means[::-1], color=PLUM, height=0.55)
            ax.set_xlim(1, 5); ax.set_xlabel('Average rating (1 to 5)')
            for bar, mean in zip(bars, means[::-1]):
                ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2, f'{mean:.2f}',
                        va='center', fontsize=8, color=INK, fontweight='bold')
            ax.grid(axis='x', color=MIST); ax.set_axisbelow(True)
        elif kind == 'ratings_stacked':
            labels, shares = [], []
            for column in RATING_COLUMNS:
                values = _ratings(frame, column)
                if len(values):
                    labels.append(LABELS[column])
                    shares.append([(values == score).mean() * 100 for score in range(1, 6)])
            left = [0.0] * len(labels)
            for score in range(5):
                widths = [row[score] for row in shares][::-1]
                ax.barh(labels[::-1], widths, left=left, color=SCALE[score], height=0.6, label=str(score + 1))
                for i, w in enumerate(widths):
                    if w >= 9:
                        ax.text(left[i] + w / 2, i, f'{w:.0f}%', ha='center', va='center', fontsize=7,
                                color='white' if score in (0, 3, 4) else INK)
                left = [l + w for l, w in zip(left, widths)]
            ax.set_xlim(0, 100); ax.set_xlabel('Share of answers (%)')
            ax.legend(title='Rating', ncol=5, fontsize=7, title_fontsize=7, frameon=False,
                      loc='upper center', bbox_to_anchor=(0.45, -0.28))
        elif kind == 'ratings_box':
            data, labels = [], []
            for column in RATING_COLUMNS:
                values = _ratings(frame, column)
                if len(values):
                    data.append(values.values); labels.append(LABELS[column].replace(' ', '\n', 1))
            box = ax.boxplot(data, patch_artist=True, widths=0.5, showmeans=True,
                             medianprops={'color': NAVY, 'linewidth': 1.6},
                             meanprops={'marker': 'D', 'markerfacecolor': 'white', 'markeredgecolor': NAVY, 'markersize': 4},
                             whiskerprops={'color': NEUTRAL}, capprops={'color': NEUTRAL},
                             flierprops={'marker': 'o', 'markersize': 2.5, 'markerfacecolor': NEUTRAL, 'markeredgecolor': NEUTRAL, 'alpha': 0.5})
            for patch in box['boxes']:
                patch.set_facecolor(LILAC); patch.set_edgecolor(PLUM)
            ax.set_xticks(range(1, len(labels) + 1), labels, fontsize=7.5)
            ax.set_ylim(0.6, 5.4); ax.set_ylabel('Rating (1 to 5)')
            ax.grid(axis='y', color=MIST); ax.set_axisbelow(True)
        elif kind == 'themes':
            themes = sorted(context.themes, key=lambda t: t.frequency)[-8:]
            if not themes:
                raise ValueError('No themes were kept for this report.')
            colours = {'Positive': GOOD, 'Improvement': WARN, 'Review': NEUTRAL}
            ax.barh([_short(t.name.replace('Emerging: ', 'New: '), 26) for t in themes], [t.frequency for t in themes],
                    color=[colours.get(t.category, NEUTRAL) for t in themes], height=0.6)
            ax.set_xlabel('Comments mentioning the theme')
            from matplotlib.patches import Patch
            present = [n for n in colours if any(t.category == n for t in themes)]
            ax.legend(handles=[Patch(color=colours[n], label=n) for n in present], fontsize=7, frameon=False,
                      loc='lower right')
            ax.grid(axis='x', color=MIST); ax.set_axisbelow(True)
        elif kind == 'recommend':
            m = context.metrics
            yes, total = m.get('recommendation_count') or 0, m.get('recommendation_total') or 0
            if total:
                ax.pie([yes, total - yes], colors=[NAVY, LILAC], startangle=90, counterclock=False,
                       wedgeprops={'width': 0.34, 'edgecolor': 'white'})
                ax.text(0, 0.08, f'{yes / total * 100:.0f}%', ha='center', va='center', fontsize=17,
                        fontweight='bold', color=NAVY)
                ax.text(0, -0.24, 'would recommend', ha='center', va='center', fontsize=7.5, color=MUTED)
                ax.set_aspect('equal')
            else:
                ax.text(0.5, 0.5, 'No recommendation answers', ha='center', va='center', color=MUTED)
            ax.axis('off')
        elif kind in ('group_bar', 'group_box'):
            data, counts = _groups(frame, spec)
            if data.empty:
                raise ValueError(f"Not enough responses per {GROUPS[spec['group']]} to compare (need {MIN_GROUP}+ each).")
            order = data.groupby('group')['value'].mean().sort_values().index.tolist()
            if kind == 'group_bar':
                means = data.groupby('group')['value'].mean().reindex(order)
                ax.barh([f'{_short(g)} (n={counts[g]})' for g in order], means.values, color=PLUM, height=0.55)
                for i, value in enumerate(means.values):
                    ax.text(value + 0.04, i, f'{value:.2f}', va='center', fontsize=7.5, fontweight='bold', color=INK)
                ax.set_xlim(1, 5.2); ax.set_xlabel(f"Average {LABELS[spec['measure']].lower()} (1 to 5)")
                ax.grid(axis='x', color=MIST); ax.set_axisbelow(True)
            else:
                box = ax.boxplot([data.loc[data['group'] == g, 'value'].values for g in order], **_horizontal(),
                                 patch_artist=True, widths=0.5, showmeans=True,
                                 medianprops={'color': NAVY, 'linewidth': 1.6},
                                 meanprops={'marker': 'D', 'markerfacecolor': 'white', 'markeredgecolor': NAVY, 'markersize': 4},
                                 whiskerprops={'color': NEUTRAL}, capprops={'color': NEUTRAL},
                                 flierprops={'marker': 'o', 'markersize': 2.5, 'markerfacecolor': NEUTRAL, 'markeredgecolor': NEUTRAL, 'alpha': 0.5})
                for patch in box['boxes']:
                    patch.set_facecolor(LILAC); patch.set_edgecolor(PLUM)
                ax.set_yticks(range(1, len(order) + 1), [f'{_short(g)} (n={counts[g]})' for g in order], fontsize=7.5)
                ax.set_xlim(0.6, 5.4); ax.set_xlabel(f"{LABELS[spec['measure']]} (1 to 5)")
                ax.grid(axis='x', color=MIST); ax.set_axisbelow(True)
        elif kind == 'trend':
            dates = pd.to_datetime(frame.get('RecordedDate'), errors='coerce')
            values = pd.to_numeric(frame[spec['measure']], errors='coerce')
            data = pd.DataFrame({'month': dates.dt.to_period('M'), 'value': values.where(values.between(1, 5))}).dropna()
            monthly = data.groupby('month')['value'].agg(['mean', 'count'])
            monthly = monthly[monthly['count'] >= MIN_GROUP]
            if monthly.empty:
                raise ValueError('Not enough dated responses to show a trend.')
            x = [p.to_timestamp() for p in monthly.index]
            ax.plot(x, monthly['mean'], color=PLUM, linewidth=2, marker='o', markersize=3.5)
            ax.fill_between(x, monthly['mean'], 1, color=MIST)
            ax.set_ylim(1, 5); ax.set_ylabel('Average (1 to 5)')
            ax.grid(axis='y', color=MIST); ax.set_axisbelow(True)
            fig.autofmt_xdate(rotation=0, ha='center')
            import matplotlib.dates as mdates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=6))
    except ValueError as exc:
        ax.clear(); ax.axis('off')
        ax.text(0.5, 0.5, str(exc), ha='center', va='center', wrap=True, color=MUTED, fontsize=8)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', facecolor='white')
    plt.close(fig)
    return buffer.getvalue()
