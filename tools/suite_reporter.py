"""Pytest hooks for readable progress, honest totals and machine-readable results."""
from collections import Counter, defaultdict
import io
import json
import ipaddress
import os
from pathlib import Path
import socket
import time
from urllib.parse import urlsplit

import pytest

from tools.suite_catalog import SUITES, group_for


class ResultBook:
    """One result per test, including setup/teardown errors and expected failures."""
    def __init__(self):
        self.tests = {}

    def record(self, report):
        item = self.tests.setdefault(report.nodeid, {
            'id': report.nodeid, 'suite': group_for(report.nodeid), 'outcome': 'incomplete',
            'duration': 0.0, 'detail': '',
        })
        item['duration'] += report.duration
        expected = getattr(report, 'wasxfail', None)
        if report.failed:
            item['outcome'] = ('xpassed' if '[XPASS(strict)]' in report.longreprtext else 'failed') if report.when == 'call' else 'error'
            item['detail'] = report.longreprtext
        elif report.skipped and item['outcome'] not in {'failed', 'error'}:
            item['outcome'] = 'xfailed' if expected else 'skipped'
            item['detail'] = str(report.longrepr)
        elif expected and report.passed and report.when == 'call':
            item['outcome'], item['detail'] = 'xpassed', str(expected)
        elif report.when == 'call' and report.passed and item['outcome'] == 'incomplete':
            item['outcome'] = 'passed'
        return item

    def counts(self, items=None):
        return dict(Counter(item['outcome'] for item in (self.tests.values() if items is None else items)))


@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    # Patch before collection: server.app and runtime otherwise read the real .env.
    import dotenv
    import dotenv.main
    dotenv.load_dotenv = dotenv.main.load_dotenv = lambda *args, **kwargs: False
    # Keep pytest's assertion highlighter available; disabling the terminal plugin
    # breaks rich assertion comparisons on pytest 8. Send only its duplicate UI
    # to an in-memory stream, while our hooks print the user-facing report.
    from _pytest._io import TerminalWriter
    terminal = config.pluginmanager.get_plugin('terminalreporter')
    terminal._tw = TerminalWriter(file=io.StringIO())
    config.pluginmanager.register(SuiteReporter(config), 'insight-hub-console-report')


def pytest_collection_modifyitems(items):
    if os.environ.get('INSIGHT_HUB_SUITE_HEADLESS') == '1':
        for item in items:
            if {'tk_runtime', 'desktop'} & set(item.fixturenames):
                item.add_marker(pytest.mark.skip(reason='Desktop display disabled by --headless.'))


@pytest.fixture(autouse=True)
def local_network_only(monkeypatch):
    """Provider tests must use doubles; permit loopback servers and the opted-in test DB."""
    allowed = set()
    test_db = os.environ.get('INSIGHT_HUB_TEST_DATABASE_URL')
    if test_db:
        parsed = urlsplit(test_db)
        allowed.add(parsed.hostname)
        allowed.update(address[4][0] for address in socket.getaddrinfo(parsed.hostname, parsed.port or 5432))
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def check(address):
        if not isinstance(address, tuple):  # Unix-domain socket; no external host.
            return
        host = address[0]
        if host == 'localhost' or host in allowed:
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise RuntimeError('External network calls are disabled in the test suite; mock the provider.')

    def connect(sock, address):
        check(address)
        return original_connect(sock, address)

    def connect_ex(sock, address):
        check(address)
        return original_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', connect_ex)


class SuiteReporter:
    def __init__(self, config):
        self.config, self.book = config, ResultBook()
        self.started = time.monotonic()
        self.collected = self.deselected = 0
        self.collection_errors = []
        self.collection_skips, self.warnings = [], []
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
        file_count = len(self.file_totals)
        self.say(f'\nCollected {self.collected} tests in {file_count} {"file" if file_count == 1 else "files"}.\n', 'heading')

    def pytest_deselected(self, items):
        self.deselected += len(items)

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append({'id': report.nodeid, 'detail': report.longreprtext})
            self.say(f'[COLLECTION ERROR] {report.nodeid}', 'bad')
        elif report.skipped:
            self.collection_skips.append({'id': report.nodeid, 'detail': str(report.longrepr)})
            self.say(f'[SKIPPED MODULE] {report.nodeid}', 'warn')

    def pytest_warning_recorded(self, warning_message, nodeid):
        self.warnings.append({'id': nodeid, 'message': str(warning_message.message),
                              'category': warning_message.category.__name__})

    def pytest_internalerror(self, excrepr):
        self.say(str(excrepr), 'bad')

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
            bad = any(counts.get(key, 0) for key in ('failed', 'error', 'xpassed', 'incomplete'))
            skipped = counts.get('skipped', 0) + counts.get('xfailed', 0)
            status = 'FAIL' if bad else 'SKIP' if skipped else 'PASS'
            self.say(f'  [{status}] {Path(file).name:34} ' +
                     ', '.join(f'{count} {outcome}' for outcome, count in sorted(counts.items())),
                     'bad' if bad else 'warn' if skipped else 'good')

    def pytest_sessionfinish(self, session, exitstatus):
        counts = self.book.counts()
        has_skips = counts.get('skipped') or self.collection_skips
        if (counts.get('xpassed') or counts.get('incomplete') or (has_skips and os.environ.get('INSIGHT_HUB_SUITE_STRICT_SKIPS') == '1')) and not session.exitstatus:
            session.exitstatus = 1
        code = int(session.exitstatus)
        elapsed = time.monotonic() - self.started
        status = ('PASSED WITH SKIPS' if has_skips or counts.get('xfailed') else 'PASSED') if code == 0 else {
            1: 'FAILED', 2: 'COLLECTION ERROR' if self.collection_errors else 'INTERRUPTED',
            3: 'INTERNAL ERROR', 4: 'USAGE ERROR', 5: 'NO TESTS',
        }.get(code, 'ERROR')
        self.say('\n' + '=' * 78, 'heading')
        self.say('TEST RESULTS BY AREA', 'heading')
        self.say(f'{"Area":12} {"Pass":>6} {"Fail":>6} {"Error":>6} {"Skip":>6} {"Xfail":>6} {"Xpass":>6} {"Unfinished":>10} {"Seconds":>9}')
        groups = defaultdict(list)
        for item in self.book.tests.values():
            groups[item['suite']].append(item)
        for name in [*SUITES, 'other']:
            if name not in groups:
                continue
            summary = self.book.counts(groups[name])
            values = ''.join(f'{summary.get(key, 0):>7}' for key in ('passed', 'failed', 'error', 'skipped', 'xfailed', 'xpassed'))
            duration = sum(item['duration'] for item in groups[name])
            self.say(f'{name:12}{values} {summary.get("incomplete", 0):>10} {duration:>9.2f}')
        for item in [*self.collection_errors, *[entry for entry in self.book.tests.values() if entry['outcome'] in {'failed', 'error', 'xpassed'}]]:
            self.say('\n' + item['id'], 'bad')
            self.say(item['detail'])
        self.say(f'\n{status} | {len(self.book.tests)}/{self.collected} executed | {self.deselected} deselected | {elapsed:.2f}s',
                 'bad' if code else 'warn' if 'SKIP' in status else 'good')
        if self.warnings:
            self.say(f'\nWarnings ({len(self.warnings)}; full list in JSON):', 'warn')
            for warning in self.warnings[:5]:
                self.say(f'  {warning["category"]}: {warning["message"]}', 'warn')
        slowest = sorted(self.book.tests.values(), key=lambda item: item['duration'], reverse=True)[:5]
        if slowest:
            self.say('\nSlowest tests:')
            for item in slowest:
                self.say(f'  {item["duration"]:7.2f}s  {item["id"]}')
        directory = Path(os.environ['INSIGHT_HUB_SUITE_OUTPUT'])
        payload = {'schema': 1, 'status': status, 'exit_code': code, 'duration': elapsed,
                   'collected': self.collected, 'executed': len(self.book.tests), 'deselected': self.deselected,
                   'counts': counts, 'tests': list(self.book.tests.values()), 'collection_errors': self.collection_errors,
                   'collection_skips': self.collection_skips, 'warnings': self.warnings}
        (directory / 'results.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
        self.say(f'\nReports: {directory / "results.json"}\n         {directory / "junit.xml"}')
