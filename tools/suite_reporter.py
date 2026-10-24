"""Pytest hooks for readable progress, honest totals and machine-readable results."""
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import sys
import time

import pytest

from tools.suite_catalog import SUITES, group_for


class ResultBook:
    """One result per test, including setup/teardown errors and expected failures."""
    def __init__(self):
        self.tests = {}

    def record(self, report):
        item = self.tests.setdefault(report.nodeid, {
            'id': report.nodeid, 'suite': group_for(report.nodeid), 'outcome': 'passed',
            'duration': 0.0, 'detail': '',
        })
        item['duration'] += report.duration
        expected = getattr(report, 'wasxfail', None)
        if report.failed:
            item['outcome'] = 'failed' if report.when == 'call' else 'error'
            item['detail'] = report.longreprtext
        elif report.skipped and item['outcome'] not in {'failed', 'error'}:
            item['outcome'] = 'xfailed' if expected else 'skipped'
            item['detail'] = str(report.longrepr)
        elif expected and report.passed and report.when == 'call':
            item['outcome'], item['detail'] = 'xpassed', str(expected)
        return item

    def counts(self, items=None):
        return dict(Counter(item['outcome'] for item in (self.tests.values() if items is None else items)))


def pytest_configure(config):
    # Patch before collection: server.app and runtime otherwise read the real .env.
    import dotenv
    import dotenv.main
    dotenv.load_dotenv = dotenv.main.load_dotenv = lambda *args, **kwargs: False
    config.pluginmanager.register(SuiteReporter(config), 'insight-hub-console-report')


def pytest_collection_modifyitems(items):
    if os.environ.get('INSIGHT_HUB_SUITE_HEADLESS') == '1':
        for item in items:
            if {'tk_runtime', 'desktop'} & set(item.fixturenames):
                item.add_marker(pytest.mark.skip(reason='Desktop display disabled by --headless.'))


class SuiteReporter:
    def __init__(self, config):
        self.config, self.book = config, ResultBook()
        self.started = time.monotonic()
        self.collected = self.deselected = 0
        self.collection_errors = []
        self.file_totals, self.file_done = Counter(), Counter()
        self.verbose = os.environ.get('INSIGHT_HUB_SUITE_VERBOSE') == '1'
        self.color = os.environ.get('INSIGHT_HUB_SUITE_COLOR') == '1'

    def say(self, text, tone=None):
        colors = {'good': '32', 'bad': '31', 'warn': '33', 'heading': '36'}
        if self.color and tone in colors:
            text = f'\033[{colors[tone]}m{text}\033[0m'
        print(text, flush=True)

    def pytest_collection_finish(self, session):
        self.collected = len(session.items)
        self.file_totals.update(item.nodeid.split('::')[0] for item in session.items)
        self.say(f'\nCollected {self.collected} tests in {len(self.file_totals)} files.\n', 'heading')

    def pytest_deselected(self, items):
        self.deselected += len(items)

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append({'id': report.nodeid, 'detail': report.longreprtext})
            self.say(f'[COLLECTION ERROR] {report.nodeid}', 'bad')

    def pytest_runtest_logreport(self, report):
        item = self.book.record(report)
        if report.when != 'teardown':
            return
        if self.verbose:
            self.say(f'[{item["outcome"].upper():7}] {item["id"]} ({item["duration"]:.2f}s)',
                     'good' if item['outcome'] == 'passed' else 'bad' if item['outcome'] in {'failed', 'error', 'xpassed'} else 'warn')
        file = report.nodeid.split('::')[0]
        self.file_done[file] += 1
        if self.file_done[file] == self.file_totals[file]:
            records = [entry for entry in self.book.tests.values() if entry['id'].split('::')[0] == file]
            counts = self.book.counts(records)
            bad = any(counts.get(key, 0) for key in ('failed', 'error', 'xpassed'))
            skipped = counts.get('skipped', 0) + counts.get('xfailed', 0)
            status = 'FAIL' if bad else 'SKIP' if skipped else 'PASS'
            self.say(f'  [{status}] {Path(file).name:34} ' +
                     ', '.join(f'{count} {outcome}' for outcome, count in sorted(counts.items())),
                     'bad' if bad else 'warn' if skipped else 'good')

    def pytest_sessionfinish(self, session, exitstatus):
        counts = self.book.counts()
        if counts.get('xpassed') or (counts.get('skipped') and os.environ.get('INSIGHT_HUB_SUITE_STRICT_SKIPS') == '1'):
            session.exitstatus = 1
        code = int(session.exitstatus)
        elapsed = time.monotonic() - self.started
        status = ('PASSED WITH SKIPS' if counts.get('skipped') or counts.get('xfailed') else 'PASSED') if code == 0 else {
            1: 'FAILED', 2: 'INTERRUPTED OR COLLECTION ERROR', 3: 'INTERNAL ERROR', 4: 'USAGE ERROR', 5: 'NO TESTS',
        }.get(code, 'ERROR')
        self.say('\n' + '=' * 78, 'heading')
        self.say('TEST RESULTS BY AREA', 'heading')
        self.say(f'{"Area":12} {"Pass":>6} {"Fail":>6} {"Error":>6} {"Skip":>6} {"Xfail":>6} {"Xpass":>6} {"Seconds":>9}')
        groups = defaultdict(list)
        for item in self.book.tests.values():
            groups[item['suite']].append(item)
        for name in [*SUITES, 'other']:
            if name not in groups:
                continue
            summary = self.book.counts(groups[name])
            values = ''.join(f'{summary.get(key, 0):>7}' for key in ('passed', 'failed', 'error', 'skipped', 'xfailed', 'xpassed'))
            duration = sum(item['duration'] for item in groups[name])
            self.say(f'{name:12}{values} {duration:>9.2f}')
        for item in [*self.collection_errors, *[entry for entry in self.book.tests.values() if entry['outcome'] in {'failed', 'error', 'xpassed'}]]:
            self.say('\n' + item['id'], 'bad')
            self.say(item['detail'])
        self.say(f'\n{status} | {len(self.book.tests)}/{self.collected} executed | {self.deselected} deselected | {elapsed:.2f}s',
                 'bad' if code else 'warn' if 'SKIP' in status else 'good')
        slowest = sorted(self.book.tests.values(), key=lambda item: item['duration'], reverse=True)[:5]
        if slowest:
            self.say('\nSlowest tests:')
            for item in slowest:
                self.say(f'  {item["duration"]:7.2f}s  {item["id"]}')
        directory = Path(os.environ['INSIGHT_HUB_SUITE_OUTPUT'])
        payload = {'schema': 1, 'status': status, 'exit_code': code, 'duration': elapsed,
                   'collected': self.collected, 'executed': len(self.book.tests), 'deselected': self.deselected,
                   'counts': counts, 'tests': list(self.book.tests.values()), 'collection_errors': self.collection_errors}
        (directory / 'results.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
        self.say(f'\nReports: {directory / "results.json"}\n         {directory / "junit.xml"}')
