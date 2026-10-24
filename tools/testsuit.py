"""Run the project checks from any working directory using this Python interpreter."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.suite_catalog import SUITES, selected_paths  # noqa: E402

REQUIRED = {
    'pytest': 'pytest', 'pandas': 'pandas', 'numpy': 'numpy', 'sklearn': 'scikit-learn',
    'pydantic': 'pydantic', 'dotenv': 'python-dotenv', 'docx': 'python-docx',
    'python_calamine': 'python-calamine', 'openai': 'openai', 'anthropic': 'anthropic',
    'fastapi': 'fastapi', 'httpx': 'httpx', 'uvicorn': 'uvicorn', 'multipart': 'python-multipart',
}


def parser():
    result = argparse.ArgumentParser(description='Insight Hub test suite with local, isolated test data.')
    result.add_argument('--list', action='store_true', help='List available test groups without running tests')
    result.add_argument('--suite', choices=tuple(SUITES), action='append', help='Run a group; repeat to combine groups')
    result.add_argument('-k', '--match', help='Run test names matching a pytest expression')
    result.add_argument('--headless', action='store_true', help='Skip tests that require a Tk window')
    result.add_argument('--fail-fast', action='store_true', help='Stop after the first failure')
    result.add_argument('--verbose', action='store_true', help='Show every test name')
    result.add_argument('--no-color', action='store_true', help='Disable ANSI console colors')
    result.add_argument('--strict-skips', action='store_true', help='Treat skipped tests as a failed run')
    result.add_argument('--output-dir', type=Path, default=ROOT / 'test-results' / 'latest', help='Directory for JSON and JUnit reports')
    return result


def missing_dependencies(headless=False):
    needed = dict(REQUIRED)
    if not headless:
        needed['tkinter'] = 'Tkinter (install the Python Tk component)'
    return [package for module, package in needed.items() if importlib.util.find_spec(module) is None]


def isolated_environment(folder):
    """Do not inherit production credentials or locations for writable app state."""
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith(('GEMINI_', 'ANTHROPIC_', 'AZURE_OPENAI_', 'GOOGLE_')) or key in {
            'SERVER_URL', 'DATABASE_URL', 'DATABASE_URL_UNPOOLED', 'ADMIN_USERNAME', 'ADMIN_PASSWORD',
            'INSIGHT_HUB_TEST_DATABASE_URL', 'EVALUATION_DATA_PATH', 'UNIVERSITY_LOGO_PATH',
            'PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'REQUIRE_DESKTOP_TESTS',
        }:
            env.pop(key, None)
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHON_DOTENV_DISABLED='1',
               AUDIT_LOG_PATH=str(folder / 'audit.jsonl'), REPORT_LIBRARY_PATH=str(folder / 'reports.sqlite3'),
               LOGIN_USERS_FILE=str(folder / 'users.txt'), DATABASE_URL=str(folder / 'server.sqlite3'),
               SECRET_KEY='isolated-tests-only', PYTHONIOENCODING='utf-8')
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT), str(ROOT / 'ai-learning-evaluation')))
    return env


def main(argv=None):
    options = parser().parse_args(argv)
    if options.list:
        for name, (description, _) in SUITES.items():
            paths = selected_paths(ROOT, [name])
            print(f'{name:10} {description} ({len(paths)} files)')
        return 0
    missing = missing_dependencies(options.headless)
    if missing:
        print('SETUP REQUIRED: ' + ', '.join(missing), file=sys.stderr)
        print('Install into this interpreter:\n  "' + sys.executable +
              '" -m pip install -r "' + str(ROOT / 'ai-learning-evaluation/server/requirements.txt') + '"', file=sys.stderr)
        return 2
    paths = selected_paths(ROOT, options.suite)
    if not paths:
        print('NO TESTS: no files matched the selected groups.', file=sys.stderr)
        return 5
    directory = options.output_dir.resolve()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f'Cannot create report directory: {exc}', file=sys.stderr)
        return 2
    command = [sys.executable, '-m', 'pytest', '-c', str(ROOT / 'pytest.ini'), '-p', 'no:cacheprovider',
               '-p', 'no:terminal', '-p', 'tools.suite_reporter', '--junitxml', str(directory / 'junit.xml')]
    if options.match:
        command += ['-k', options.match]
    if options.fail_fast:
        command.append('-x')
    print('LEARNING FUTURES | TEST SUITE', flush=True)
    print('Groups: ' + ', '.join(options.suite or SUITES), flush=True)
    with tempfile.TemporaryDirectory(prefix='insight-hub-tests-') as temporary:
        env = isolated_environment(Path(temporary))
        env.update(INSIGHT_HUB_SUITE_OUTPUT=str(directory), INSIGHT_HUB_SUITE_HEADLESS=str(int(options.headless)),
                   INSIGHT_HUB_SUITE_VERBOSE=str(int(options.verbose)),
                   INSIGHT_HUB_SUITE_STRICT_SKIPS=str(int(options.strict_skips)),
                   INSIGHT_HUB_SUITE_COLOR=str(int(not options.no_color and sys.stdout.isatty() and 'NO_COLOR' not in os.environ)))
        try:
            return subprocess.call(command + paths, cwd=ROOT, env=env)
        except KeyboardInterrupt:
            print('\nTest run interrupted.', file=sys.stderr)
            return 130


if __name__ == '__main__':
    raise SystemExit(main())
