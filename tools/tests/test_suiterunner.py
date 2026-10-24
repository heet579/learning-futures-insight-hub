"""Exercise the real CLI against tiny disposable projects, never the live app state."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from tools.suite_catalog import group_for, selected_paths
from tools.suite_reporter import ResultBook
from tools.testsuit import isolated_environment, main


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'project with spaces'
    (root / 'tools').mkdir(parents=True)
    source = Path(__file__).resolve().parents[1]
    for name in ('__init__.py', 'testsuit.py', 'suite_catalog.py', 'suite_reporter.py'):
        shutil.copyfile(source / name, root / 'tools' / name)
    (root / 'ai-learning-evaluation' / 'tests').mkdir(parents=True)
    (root / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    return root


def run_project(project, source, *args):
    (project / 'ai-learning-evaluation/tests/test_metrics.py').write_text(source, encoding='utf-8')
    process = subprocess.run([sys.executable, str(project / 'tools/testsuit.py'), '--suite', 'data', '--no-color', *args],
                             cwd=project.parent, text=True, encoding='utf-8', capture_output=True, timeout=45)
    report_path = project / 'test-results/latest/results.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else None
    return process, report


def test_success_reports_match_console_and_junit(project):
    process, report = run_project(project, 'def test_ok():\n    assert 2 + 2 == 4\n')
    assert process.returncode == 0, process.stdout + process.stderr
    assert report['counts'] == {'passed': 1} and report['status'] == 'PASSED'
    assert 'TEST RESULTS BY AREA' in process.stdout and '\x1b[' not in process.stdout
    junit = ET.parse(project / 'test-results/latest/junit.xml')
    assert sum(int(suite.get('tests')) for suite in junit.findall('testsuite')) == 1


def test_failed_run_is_nonzero_and_fail_fast_keeps_collected_total(project):
    source = 'def test_bad():\n    assert False, "example failure"\ndef test_after():\n    pass\n'
    process, report = run_project(project, source, '--fail-fast')
    assert process.returncode == 1
    assert report['collected'] == 2 and report['executed'] == 1
    assert report['counts'] == {'failed': 1} and 'example failure' in process.stdout


def test_assertion_comparisons_keep_readable_diagnostics(project):
    process, report = run_project(project, 'def test_bad():\n    assert ["actual"] == ["expected"]\n')
    assert process.returncode == 1 and report['counts'] == {'failed': 1}
    assert "At index 0 diff" in process.stdout
    assert 'terminalreporter is not None' not in process.stdout


def test_skip_is_visible_and_strict_mode_fails(project):
    source = 'import pytest\n@pytest.mark.skip(reason="display unavailable")\ndef test_skip():\n    pass\n'
    process, report = run_project(project, source)
    assert process.returncode == 0 and report['status'] == 'PASSED WITH SKIPS'
    assert report['counts'] == {'skipped': 1}
    process, report = run_project(project, source, '--strict-skips')
    assert process.returncode == 1 and report['exit_code'] == 1


def test_collection_error_is_not_a_success(project):
    process, report = run_project(project, 'def invalid syntax\n')
    assert process.returncode == 2
    assert len(report['collection_errors']) == 1
    assert '[COLLECTION ERROR]' in process.stdout


def test_module_skips_and_warnings_are_preserved(project):
    (project / 'ai-learning-evaluation/tests/test_privacy.py').write_text(
        'import pytest\npytest.skip("optional module", allow_module_level=True)\n', encoding='utf-8')
    source = 'import warnings\ndef test_warn():\n    warnings.warn("review this warning", UserWarning)\n'
    process, report = run_project(project, source)
    assert process.returncode == 0 and report['status'] == 'PASSED WITH SKIPS'
    assert len(report['collection_skips']) == 1
    assert any(item['message'] == 'review this warning' for item in report['warnings'])
    assert '[SKIPPED MODULE]' in process.stdout and 'Warnings (' in process.stdout


def test_empty_selection_is_not_a_success(project):
    process, report = run_project(project, 'def test_ok():\n    pass\n', '-k', 'does_not_exist')
    assert process.returncode == 5
    assert report['status'] == 'NO TESTS' and report['deselected'] == 1


def test_unexpected_pass_fails_and_expected_failure_stays_distinct(project):
    source = ('import pytest\n@pytest.mark.xfail(reason="known issue")\ndef test_known():\n    assert False\n'
              '@pytest.mark.xfail(reason="fixed issue")\ndef test_fixed():\n    assert True\n')
    process, report = run_project(project, source)
    assert process.returncode == 1
    assert report['counts'] == {'xfailed': 1, 'xpassed': 1}


def test_headless_uses_fixtures_without_creating_a_window(project):
    source = ('import pytest\n@pytest.fixture\ndef tk_runtime():\n    raise RuntimeError("must not open a window")\n'
              'def test_window(tk_runtime):\n    pass\n')
    process, report = run_project(project, source, '--headless')
    assert process.returncode == 0
    assert report['counts'] == {'skipped': 1}


def test_dotenv_and_external_network_are_disabled(project):
    source = ('import dotenv, os, socket\n'
              'def test_isolation():\n'
              '    assert dotenv.load_dotenv() is False\n'
              '    assert os.environ["DATABASE_URL"].endswith("server.sqlite3")\n'
              '    import pytest\n'
              '    with socket.socket() as connection:\n'
              '        with pytest.raises(RuntimeError, match="External network"):\n'
              '            connection.connect(("192.0.2.1", 443))\n')
    process, report = run_project(project, source)
    assert process.returncode == 0, process.stdout + process.stderr


def test_environment_clears_cloud_and_postgres_without_changing_parent(monkeypatch, tmp_path):
    for key in ('GEMINI_API_KEY', 'DATABASE_URL', 'INSIGHT_HUB_TEST_DATABASE_URL', 'SERVER_URL', 'PYTEST_ADDOPTS'):
        monkeypatch.setenv(key, 'private-value')
    env = isolated_environment(tmp_path)
    assert 'GEMINI_API_KEY' not in env and 'SERVER_URL' not in env
    assert 'INSIGHT_HUB_TEST_DATABASE_URL' not in env and 'PYTEST_ADDOPTS' not in env
    assert env['DATABASE_URL'] == str(tmp_path / 'server.sqlite3')
    import os
    assert os.environ['DATABASE_URL'] == 'private-value'


def test_postgres_requires_explicit_disposable_url(monkeypatch, capsys):
    monkeypatch.delenv('INSIGHT_HUB_TEST_DATABASE_URL', raising=False)
    assert main(['--postgres']) == 2
    assert 'disposable Postgres database' in capsys.readouterr().err


def test_new_files_are_discovered_by_default_and_unknowns_are_visible(project):
    file = project / 'ai-learning-evaluation/tests/test_new_feature.py'
    file.touch()
    assert selected_paths(project, None) == ['ai-learning-evaluation/tests/test_new_feature.py']
    assert group_for('ai-learning-evaluation/tests/test_new_feature.py::test_one') == 'other'
    assert group_for('tools/tests/test_suiterunner.py::test_one') == 'runner'


def test_teardown_error_overrides_pass_without_double_counting():
    book = ResultBook()
    common = dict(nodeid='ai-learning-evaluation/tests/test_metrics.py::test_one', duration=.1, skipped=False)
    book.record(SimpleNamespace(**common, when='call', failed=False, passed=True))
    book.record(SimpleNamespace(**common, when='teardown', failed=True, passed=False, longreprtext='cleanup failed'))
    assert book.counts() == {'error': 1}
    assert len(book.tests) == 1 and next(iter(book.tests.values()))['duration'] == pytest.approx(.2)
