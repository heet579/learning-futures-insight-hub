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
    'ratings_violin': 'Shape of ratings for each area (violin plot)',
    'histogram': 'How many learners gave each rating',
    'themes': 'What learners talked about (themes)',
    'recommend': 'Would recommend the course',
    'share': 'Who responded',
    'group_bar': 'Average rating compared by group',
    'group_box': 'Spread of ratings compared by group (box plot)',
    'group_stacked': 'Ratings compared by group (1 to 5)',
    'heatmap': 'Average ratings by group and area (heat map)',
    'scatter': 'How two ratings move together',
    'trend': 'Average rating over time (by month)',
}
NEEDS_MEASURE = {'histogram', 'group_bar', 'group_box', 'group_stacked', 'trend', 'scatter'}
NEEDS_GROUP = {'group_bar', 'group_box', 'group_stacked', 'heatmap', 'share'}
DEFAULT_CHARTS = [{'kind': 'ratings_stacked'}, {'kind': 'ratings_box'}, {'kind': 'themes'}, {'kind': 'recommend'}]


# ---- specs ---------------------------------------------------------------------------------
def clean_spec(spec):
    """Validate a chart spec from a person, the AI or a request; raises ValueError when unusable."""
    if not isinstance(spec, dict) or spec.get('kind') not in KINDS:
        raise ValueError('That chart type is not available.')
    out = {'kind': spec['kind']}
    if out['kind'] in NEEDS_MEASURE:
        measure = spec.get('measure') or 'OverallSatisfaction'
        if measure not in RATING_COLUMNS:
            raise ValueError('Choose a rating to chart.')
        out['measure'] = measure
    if out['kind'] == 'scatter':
        other = spec.get('measure2') or next(c for c in RATING_COLUMNS if c != out['measure'])
        if other not in RATING_COLUMNS or other == out['measure']:
            raise ValueError('A scatter plot needs two different ratings.')
        out['measure2'] = other
    if out['kind'] in NEEDS_GROUP:
        group = spec.get('group') or ('DeliveryMode' if out['kind'] == 'share' else None)
        if group not in GROUPS:
            raise ValueError('Choose what to compare by: course, delivery mode, facilitator or client type.')
        out['group'] = group
    title = str(spec.get('title') or '').strip()
    out['title'] = title[:90] or default_title(out)
    reason = str(spec.get('reason') or '').strip()
    if reason:
        out['reason'] = reason[:200]
    return out


def default_title(spec):
    kind = spec['kind']
    measure = LABELS.get(spec.get('measure', ''), '')
    group = GROUPS.get(spec.get('group', ''), '')
    if kind in ('group_bar', 'group_box', 'group_stacked'):
        verb = {'group_bar': 'Average', 'group_box': 'Spread of', 'group_stacked': 'Ratings of'}[kind]
        return f'{verb} {measure.lower()} by {group}'
    if kind == 'trend':
        return f'{measure} over time'
    if kind == 'histogram':
        return f'How learners rated {measure.lower()}'
    if kind == 'scatter':
        return f"{measure} against {LABELS[spec['measure2']].lower()}"
    if kind == 'heatmap':
        return f'Average ratings by {group}'
    if kind == 'share':
        return f'Responses by {group}'
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


def _measures_in(t):
    found = []
    for word, column in _MEASURES:
        index = t.find(word)
        if index >= 0 and column not in [c for _, c in found]:
            found.append((index, column))
    if 'facilitator effectiveness' in t:
        found = [(i, c) for i, c in found if c != 'FacilitatorEffectiveness'] + [(t.find('facilitator effectiveness'), 'FacilitatorEffectiveness')]
    return [c for _, c in sorted(found)]


def parse_request(text):
    """Turn a plain-English description into a chart spec. Returns (spec, explanation)."""
    t = ' ' + re.sub(r'\s+', ' ', (text or '').lower()) + ' '
    if not t.strip():
        raise ValueError('Describe the chart you want, for example "box plot of satisfaction by delivery mode".')
    group = None
    match = (re.search(r'\b(?:by|per|each|across|between|for every|of each|split by)\b(.*)', t)
             or re.search(r'\b(?:compare[ds]?|comparing)\b(.*)', t))
    tail = match.group(1) if match else ''
    for word, column in _GROUP_WORDS:
        if word in tail or (word in t and re.search(r'pie|donut|doughnut|share|who responded|proportion|heat ?map|matrix', t)):
            group = column
            break
    measures = _measures_in(t)
    measure = measures[0] if measures else None
    if re.search(r'scatter|correlat|relationship|against|versus|\bvs\b', t) and len(measures) >= 2:
        spec = {'kind': 'scatter', 'measure': measures[0], 'measure2': measures[1]}
    elif re.search(r'heat ?map|matrix|grid of', t):
        spec = {'kind': 'heatmap', 'group': group or 'CourseName'}
    elif re.search(r'theme|topic|talk(ed)? about|comment', t):
        spec = {'kind': 'themes'}
    elif re.search(r'recommend', t):
        spec = {'kind': 'recommend'}
    elif re.search(r'pie|donut|doughnut|who responded|share of responses|proportion|how many (?:people|learners|responses)', t) and group:
        spec = {'kind': 'share', 'group': group}
    elif re.search(r'over time|trend|month|timeline|change over|line', t):
        spec = {'kind': 'trend', 'measure': measure or 'OverallSatisfaction'}
    elif re.search(r'violin', t) and not group:
        spec = {'kind': 'ratings_violin'}
    elif group:
        if re.search(r'stack|likert|1 to 5|breakdown|split', t):
            kind = 'group_stacked'
        elif re.search(r'box|spread|range|variation|violin|distribution', t):
            kind = 'group_box'
        else:
            kind = 'group_bar'
        spec = {'kind': kind, 'measure': measure or 'OverallSatisfaction', 'group': group}
    elif re.search(r'histogram|distribution|how many (?:gave|rated)|frequency', t) and measure:
        spec = {'kind': 'histogram', 'measure': measure}
    elif re.search(r'box|spread|range|variation', t):
        spec = {'kind': 'ratings_box'}
    elif re.search(r'stack|likert|1 to 5|how (people|learners) rated|breakdown|split', t):
        spec = {'kind': 'ratings_stacked'}
    elif re.search(r'average|mean|rating|score|bar', t):
        spec = {'kind': 'ratings_bar'}
    else:
        raise ValueError('I could not match that to a chart. Try "average ratings", "box plot by course", '
                         '"themes", "would recommend", "heat map by course" or "satisfaction over time".')
    spec = clean_spec(spec)
    return spec, f"Added: {spec['title']}."


def describe_catalogue():
    """The chart catalogue in words, for the AI."""
    return {'kinds': KINDS, 'measures': {c: LABELS[c] for c in RATING_COLUMNS}, 'groups': GROUPS,
            'needs_measure': sorted(NEEDS_MEASURE), 'needs_group': sorted(NEEDS_GROUP)}


def request_chart(text, provider=None):
    """Plain words to a chart: local rules first, then the AI for anything unusual."""
    try:
        return parse_request(text)
    except ValueError as local_error:
        if provider is None or not hasattr(provider, 'chart_request'):
            raise
        try:
            result = provider.chart_request(text, describe_catalogue())
        except Exception:
            raise local_error from None
        if not result.get('possible'):
            raise ValueError(result.get('message') or str(local_error))
        spec = clean_spec({k: result.get(k) for k in ('kind', 'measure', 'measure2', 'group', 'title')})
        return spec, f"Added: {spec['title']}."


# ---- the AI (or the rules) choose the charts -------------------------------------------------------
def candidates(frame, context):
    """Charts that suit this data, best first, each with the reason it suits."""
    out = []

    def add(score, spec, reason):
        try:
            out.append((score, clean_spec({**spec, 'reason': reason})))
        except ValueError:
            pass

    rated = [c for c in RATING_COLUMNS if len(_ratings(frame, c))]
    if rated:
        add(10, {'kind': 'ratings_stacked'}, 'Shows every rating from 1 to 5 for each area at a glance.')
        add(6, {'kind': 'ratings_box'}, 'Shows how spread out the ratings are, not just the average.')
    best = None
    for column in GROUPS:
        if column not in frame or 'OverallSatisfaction' not in frame:
            continue
        data, counts = _groups(frame, {'group': column, 'measure': 'OverallSatisfaction'})
        groups = data['group'].nunique() if not data.empty else 0
        if groups < 2:
            continue
        means = data.groupby('group')['value'].mean()
        spread = means.max() - means.min()
        if best is None or spread > best[0]:
            best = (spread, column, groups)
    if best:
        spread, column, groups = best
        label = GROUPS[column]
        if spread >= 0.2:
            add(9 + spread, {'kind': 'group_box', 'measure': 'OverallSatisfaction', 'group': column},
                f'Satisfaction differs by {label} (gap of {spread:.2f} points), so a comparison helps.')
        else:
            add(5, {'kind': 'group_bar', 'measure': 'OverallSatisfaction', 'group': column},
                f'Shows that results were similar across each {label}.')
        if groups >= 3 and len(rated) >= 3:
            add(6.5, {'kind': 'heatmap', 'group': column}, f'Compares all rated areas across each {label} in one view.')
        add(4, {'kind': 'share', 'group': column}, f'Shows who responded, by {label}.')
    themes = [t for t in context.themes]
    if len(themes) >= 2:
        add(8, {'kind': 'themes'}, 'Shows what learners wrote about most often.')
    if 'RecordedDate' in frame:
        dates = pd.to_datetime(frame['RecordedDate'], errors='coerce')
        months = dates.dt.to_period('M').value_counts()
        if (months >= MIN_GROUP).sum() >= 3:
            add(7, {'kind': 'trend', 'measure': 'OverallSatisfaction'}, 'Responses span several months, so the trend is useful.')
    if context.metrics.get('recommendation_total'):
        add(6.8, {'kind': 'recommend'}, 'The headline share of learners who would recommend the course.')
    out.sort(key=lambda item: -item[0])
    seen, ordered = set(), []
    for _, spec in out:
        key = (spec['kind'], spec.get('group'), spec.get('measure'))
        if key not in seen:
            seen.add(key)
            ordered.append(spec)
    return ordered


def auto_choose(frame, context, provider=None, count=MAX_CHARTS):
    """Pick the charts for the report. The AI chooses from charts that suit the data when it is
    available; otherwise the rules above choose. Every chart carries the reason it was chosen."""
    options = candidates(frame, context)
    if not options:
        return []
    if provider is not None and hasattr(provider, 'choose_charts'):
        try:
            summary = {'responses': context.metrics['response_count'], 'themes': len(context.themes),
                       'satisfaction': context.metrics['ratings']['OverallSatisfaction']['mean']}
            picked = provider.choose_charts(summary, [{'id': i, 'title': s['title'], 'reason': s['reason']}
                                                      for i, s in enumerate(options)], count)
            chosen = []
            for item in picked:
                index = item.get('id')
                if isinstance(index, int) and 0 <= index < len(options) and options[index] not in chosen:
                    spec = dict(options[index])
                    if str(item.get('reason') or '').strip():
                        spec['reason'] = str(item['reason']).strip()[:200]
                    chosen.append(spec)
            if len(chosen) >= min(count, len(options), 2):
                return chosen[:count]
        except Exception:
            pass
    return options[:count]


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
        elif kind == 'ratings_violin':
            data, labels = [], []
            for column in RATING_COLUMNS:
                values = _ratings(frame, column)
                if len(values) >= MIN_GROUP:
                    data.append(values.values + 0.0); labels.append(LABELS[column].replace(' ', '\n', 1))
            if not data:
                raise ValueError('Not enough ratings to draw.')
            parts = ax.violinplot(data, showmeans=True, showextrema=False, widths=0.8)
            for body in parts['bodies']:
                body.set_facecolor(LILAC); body.set_edgecolor(PLUM); body.set_alpha(0.9)
            parts['cmeans'].set_color(NAVY)
            ax.set_xticks(range(1, len(labels) + 1), labels, fontsize=7.5)
            ax.set_ylim(0.6, 5.4); ax.set_ylabel('Rating (1 to 5)')
            ax.grid(axis='y', color=MIST); ax.set_axisbelow(True)
        elif kind == 'histogram':
            values = _ratings(frame, spec['measure'])
            if values.empty:
                raise ValueError('No ratings to draw.')
            counts = [(values == score).sum() for score in range(1, 6)]
            bars = ax.bar([str(i) for i in range(1, 6)], counts, color=SCALE, width=0.65)
            for bar, count in zip(bars, counts):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f'{count:,}', ha='center', va='bottom',
                        fontsize=7.5, color=INK)
            ax.set_xlabel(f"{LABELS[spec['measure']]} rating"); ax.set_ylabel('Learners')
            ax.grid(axis='y', color=MIST); ax.set_axisbelow(True)
        elif kind == 'share':
            group = frame[spec['group']].fillna('Not recorded').astype(str).str.strip().replace('', 'Not recorded')
            counts = group.value_counts()
            counts = counts[counts >= MIN_GROUP]
            if counts.empty:
                raise ValueError('Not enough responses per group to show.')
            if len(counts) > 6:
                counts = pd.concat([counts[:5], pd.Series({'Other': counts[5:].sum()})])
            colours = [NAVY, PLUM, '#8F77D2', LILAC, '#E28B6B', NEUTRAL][:len(counts)]
            wedges, _ = ax.pie(counts.values, colors=colours, startangle=90, counterclock=False,
                               wedgeprops={'width': 0.38, 'edgecolor': 'white'})
            total = counts.sum()
            ax.legend(wedges, [f'{_short(n, 22)} {v / total * 100:.0f}%' for n, v in counts.items()], fontsize=7,
                      frameon=False, loc='upper center', bbox_to_anchor=(0.5, 0.02), ncol=min(3, len(counts)))
            ax.text(0, 0, f'{total:,}\nresponses', ha='center', va='center', fontsize=8.5, color=NAVY, fontweight='bold')
            ax.set_aspect('equal'); ax.axis('off')
        elif kind == 'group_stacked':
            data, counts = _groups(frame, spec)
            if data.empty:
                raise ValueError(f"Not enough responses per {GROUPS[spec['group']]} to compare (need {MIN_GROUP}+ each).")
            order = data.groupby('group')['value'].mean().sort_values().index.tolist()
            left = [0.0] * len(order)
            labels = [f'{_short(g, 22)} (n={counts[g]})' for g in order]
            for score in range(1, 6):
                widths = [(data.loc[data['group'] == g, 'value'] == score).mean() * 100 for g in order]
                ax.barh(labels, widths, left=left, color=SCALE[score - 1], height=0.6, label=str(score))
                left = [l + w for l, w in zip(left, widths)]
            ax.set_xlim(0, 100); ax.set_xlabel(f"Share of {LABELS[spec['measure']].lower()} answers (%)")
            ax.legend(title='Rating', ncol=5, fontsize=7, title_fontsize=7, frameon=False,
                      loc='upper center', bbox_to_anchor=(0.3, -0.28), handlelength=1.2, columnspacing=0.8)
        elif kind == 'heatmap':
            column = spec['group']
            group = frame[column].fillna('Not recorded').astype(str).str.strip()
            counts = group.value_counts()
            keep = [g for g in counts.index if counts[g] >= MIN_GROUP][:8]
            measures = [c for c in RATING_COLUMNS if c in frame]
            if not keep or not measures:
                raise ValueError(f'Not enough responses per {GROUPS[column]} to compare.')
            table = pd.DataFrame({m: pd.to_numeric(frame[m], errors='coerce').where(lambda v: v.between(1, 5))
                                  for m in measures})
            table['group'] = group
            means = table[table['group'].isin(keep)].groupby('group')[measures].mean().reindex(keep)
            from matplotlib.colors import LinearSegmentedColormap
            cmap = LinearSegmentedColormap.from_list('plum', ['#F4F0FB', '#8F77D2', NAVY])
            low, high = float(means.min().min()), float(means.max().max())
            ax.imshow(means.values, cmap=cmap, aspect='auto', vmin=low - 0.05, vmax=high + 0.05)
            ax.set_xticks(range(len(measures)), [LABELS[m].replace(' ', '\n', 1) for m in measures], fontsize=7)
            ax.set_yticks(range(len(keep)), [f'{_short(g, 20)} (n={counts[g]})' for g in keep], fontsize=7)
            middle = (low + high) / 2
            for i in range(len(keep)):
                for j in range(len(measures)):
                    value = means.values[i, j]
                    ax.text(j, i, f'{value:.2f}', ha='center', va='center', fontsize=7,
                            color='white' if value > middle else INK)
            for side in ('left', 'bottom'):
                ax.spines[side].set_visible(False)
            ax.tick_params(length=0)
        elif kind == 'scatter':
            a = pd.to_numeric(frame[spec['measure']], errors='coerce')
            b = pd.to_numeric(frame[spec['measure2']], errors='coerce')
            data = pd.DataFrame({'a': a, 'b': b}).dropna()
            data = data[data['a'].between(1, 5) & data['b'].between(1, 5)]
            if len(data) < MIN_GROUP:
                raise ValueError('Not enough learners answered both questions.')
            import numpy as np
            jitter = np.random.default_rng(7)
            sample = data.sample(min(len(data), 1500), random_state=7)
            ax.scatter(sample['b'] + jitter.uniform(-0.18, 0.18, len(sample)),
                       sample['a'] + jitter.uniform(-0.18, 0.18, len(sample)), s=5, color=PLUM, alpha=0.25, linewidths=0)
            r = data['a'].corr(data['b'])
            ax.set_xlim(0.5, 5.5); ax.set_ylim(0.5, 5.5)
            ax.set_xlabel(LABELS[spec['measure2']]); ax.set_ylabel(LABELS[spec['measure']])
            ax.text(0.6, 5.25, f'correlation r = {r:.2f} (n={len(data):,})', fontsize=7.5, color=NAVY, fontweight='bold')
            ax.grid(color=MIST); ax.set_axisbelow(True)
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
