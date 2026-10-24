"""One catalogue shared by test selection and console reporting."""
from pathlib import Path

SUITES = {
    'data': ('Survey imports, calculations and privacy', (
        'ingestion', 'qualtrics_real_export', 'excel_import', 'metrics', 'themes', 'privacy', 'data_boundaries')),
    'analysis': ('Insights, questions and evidence checks', ('gemini', 'copilot', 'prompts', 'grounding')),
    'reports': ('Reports, revisions, review gates and audit', ('reporting', 'revisions', 'workflow', 'review', 'audit')),
    'accounts': ('Sign-in, accounts and session changes', ('auth', 'accounts', 'account_session', 'login')),
    'desktop': ('Desktop navigation, library and handoff', ('desktop', 'review_experience', 'library', 'handoff', 'runtime')),
    'api': ('Server and browser workflow', ('server', 'web_api', 'api_boundaries')),
    'runner': ('Test launcher and reporting regressions', ()),
}


def group_for(nodeid):
    stem = Path(nodeid.split('::', 1)[0]).stem.removeprefix('test_')
    if nodeid.replace('\\', '/').startswith('tools/tests/'):
        return 'runner'
    return next((name for name, (_, stems) in SUITES.items() if stem in stems), 'other')


def selected_paths(root, names):
    """Discover paths afresh so an all-suite run includes newly added tests."""
    files = sorted((root / 'ai-learning-evaluation' / 'tests').glob('test_*.py'))
    files += sorted((root / 'tools' / 'tests').glob('test_*.py'))
    return [str(path.relative_to(root)) for path in files
            if not names or group_for(path.relative_to(root).as_posix()) in names]
