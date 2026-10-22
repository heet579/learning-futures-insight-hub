"""Hashed authentication and administrator bootstrap workflow; no external services."""
import os
from pathlib import Path
import subprocess

import pytest

from src.auth import (AccountFileError, add_user, authenticate, hash_password,
                      initialize_users, main, read_users, users_path, verify_password)
from src.workflow import ReviewWorkflow


@pytest.fixture
def accounts(tmp_path):
    path = tmp_path / 'users.txt'
    add_user('Alice', 'a good password', path)
    return path


def test_credentials_and_case(accounts):
    assert authenticate(' ALICE ', 'a good password', accounts) == 'alice'
    assert authenticate('alice', 'A good password', accounts) is None
    assert authenticate('unknown', 'a good password', accounts) is None
    assert authenticate('alice', '', accounts) is None
    assert authenticate('alice', 'x' * 1025, accounts) is None
    stored = read_users(accounts)['alice']
    assert stored.startswith('pbkdf2_sha256$')
    assert 'a good password' not in accounts.read_text()
    assert verify_password('a good password', stored)


def test_hash_uses_random_salt_and_rejects_wrong_password():
    first = hash_password('correct horse battery staple')
    second = hash_password('correct horse battery staple')
    assert first != second
    assert verify_password('correct horse battery staple', first)
    assert not verify_password('wrong password', first)


def test_direct_file_edits_apply_at_next_attempt(accounts):
    add_user('Bob', 'bob password', accounts)
    assert authenticate('bob', 'bob password', accounts) == 'bob'
    add_user('Bob', 'edited password', accounts, replace=True)
    assert authenticate('bob', 'bob password', accounts) is None
    assert authenticate('bob', 'edited password', accounts) == 'bob'
    accounts.write_text(accounts.read_text().replace('alice\t', '#alice\t'), encoding='utf-8')
    assert authenticate('alice', 'a good password', accounts) is None
    assert authenticate('bob', 'edited password', accounts) == 'bob'


def test_add_and_reset_preserve_comments(accounts):
    original = accounts.read_text()
    with pytest.raises(ValueError, match='exists'):
        add_user('ALICE', 'new password', accounts)
    assert accounts.read_text() == original
    add_user('Alice', 'new password', accounts, replace=True)
    assert authenticate('alice', 'new password', accounts) == 'alice'
    assert authenticate('alice', 'a good password', accounts) is None
    assert accounts.read_text().startswith('#')


@pytest.mark.parametrize('content', [
    '', '# Only comments\n', 'alice\n', 'alice\t\n',
    'alice plaintext-password\n',
    'alice pbkdf2_sha256$9999999999$00$00\n',
])
def test_unconfigured_and_malformed_files_fail_closed(tmp_path, content):
    path = tmp_path / 'users.txt'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(AccountFileError):
        authenticate('alice', 'password', path)


def test_missing_file_and_duplicate_users_fail_closed(accounts, tmp_path):
    with pytest.raises(AccountFileError, match='unavailable'):
        read_users(tmp_path / 'missing.txt')
    encoded = read_users(accounts)['alice']
    with accounts.open('a', encoding='utf-8') as stream:
        stream.write(f'ALICE {encoded}\n')
    with pytest.raises(AccountFileError, match='line 5'):
        authenticate('alice', 'a good password', accounts)


def test_utf8_bom_and_password_spaces(accounts):
    add_user('user', ' password with spaces ', accounts)
    accounts.write_text(accounts.read_text(), encoding='utf-8-sig')
    assert authenticate('user', ' password with spaces ', accounts) == 'user'
    assert authenticate('user', 'password with spaces', accounts) is None


@pytest.mark.parametrize('password', ['', 'x' * 1025, 'password\nother', 'password\tother'])
def test_invalid_passwords_are_not_written(tmp_path, password):
    path = tmp_path / 'users.txt'
    with pytest.raises(ValueError):
        add_user('user', password, path)
    assert not path.exists()


def test_unicode_password_and_comments(tmp_path):
    path = tmp_path / 'users.txt'
    path.write_text('   # Comment\n\n', encoding='utf-8')
    add_user('user', 'café-password', path)
    assert authenticate('user', 'café-password', path) == 'user'
    assert authenticate('user', 'cafe-password', path) is None


def test_direct_entry_with_short_password(tmp_path):
    path = tmp_path / 'users.txt'
    add_user('user', '12345', path)
    assert authenticate('user', '12345', path) == 'user'


def test_bootstrap_creates_two_hashed_accounts_and_refuses_overwrite(tmp_path):
    path = tmp_path / 'users.txt'
    initialize_users([('demo-author', 'author password'),
                      ('demo-reviewer', 'reviewer password')], path)
    content = path.read_text()
    assert 'author password' not in content
    assert 'reviewer password' not in content
    assert content.count('pbkdf2_sha256$') == 2
    if os.name != 'nt':
        assert path.stat().st_mode & 0o777 == 0o600
    assert authenticate('demo-author', 'author password', path) == 'demo-author'
    assert authenticate('demo-reviewer', 'reviewer password', path) == 'demo-reviewer'
    before = path.read_bytes()
    with pytest.raises(FileExistsError, match='refusing to overwrite'):
        initialize_users([('new-author', 'new author password'),
                          ('new-reviewer', 'new reviewer password')], path)
    assert path.read_bytes() == before


def test_bootstrap_requires_two_distinct_accounts(tmp_path):
    with pytest.raises(ValueError, match='at least two'):
        initialize_users([('only-author', 'password')], tmp_path / 'one.txt')
    with pytest.raises(ValueError, match='unique'):
        initialize_users([('same', 'first password'), ('SAME', 'second password')], tmp_path / 'duplicate.txt')


def test_bootstrapped_identities_preserve_two_person_review_rules(tmp_path):
    path = tmp_path / 'users.txt'
    initialize_users([('demo-author', 'author password'),
                      ('demo-reviewer', 'reviewer password')], path)
    author = authenticate('demo-author', 'author password', path)
    reviewer = authenticate('demo-reviewer', 'reviewer password', path)
    workflow = ReviewWorkflow()
    workflow.submit(author)
    with pytest.raises(ValueError, match='different person'):
        workflow.approve(author)
    workflow.return_for_changes(reviewer, 'Clarify the recommendation evidence.')
    assert workflow.status == 'CHANGES REQUESTED'
    workflow.submit(author)
    workflow.approve(reviewer)
    assert workflow.status == 'HUMAN REVIEWED'
    assert workflow.reviewer == author
    assert workflow.approver == reviewer


def test_default_path_is_independent_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('LOGIN_USERS_FILE', '')
    assert users_path().name == 'users.txt'
    assert users_path().parent.name == 'config'
    monkeypatch.setenv('LOGIN_USERS_FILE', str(tmp_path / 'accounts.txt'))
    assert users_path() == tmp_path / 'accounts.txt'


def test_administrator_cli_add_and_paste_entry(monkeypatch, tmp_path, capsys):
    path = tmp_path / 'users.txt'
    loaded = []
    monkeypatch.setattr('dotenv.load_dotenv', lambda path, **kwargs: loaded.append(path))
    monkeypatch.setenv('LOGIN_USERS_FILE', str(path))
    monkeypatch.setattr('getpass.getpass', lambda prompt: 'chosen password')
    monkeypatch.setattr('sys.argv', ['src.auth', 'add', 'admin'])
    main()
    assert loaded[0].name == '.env'
    assert authenticate('admin', 'chosen password', path) == 'admin'
    assert 'chosen password' not in capsys.readouterr().out
    monkeypatch.setattr('sys.argv', ['src.auth', 'entry', 'newuser'])
    main()
    entry = capsys.readouterr().out.strip()
    assert entry.startswith('newuser\tpbkdf2_sha256$')
    assert 'chosen password' not in entry
    with path.open('a', encoding='utf-8') as stream:
        stream.write(entry + '\n')
    assert authenticate('newuser', 'chosen password', path) == 'newuser'


def test_administrator_cli_bootstraps_two_accounts_without_printing_passwords(monkeypatch, tmp_path, capsys):
    path = tmp_path / 'users.txt'
    passwords = iter(['first secret', 'first secret', 'second secret', 'second secret'])
    monkeypatch.setenv('LOGIN_USERS_FILE', str(path))
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.setattr('getpass.getpass', lambda prompt: next(passwords))
    monkeypatch.setattr('sys.argv', ['src.auth', 'init', 'demo-author', 'demo-reviewer'])
    main()
    output = capsys.readouterr().out
    assert 'Created 2 hashed local accounts' in output
    assert 'first secret' not in output and 'second secret' not in output
    assert authenticate('demo-author', 'first secret', path) == 'demo-author'
    assert authenticate('demo-reviewer', 'second secret', path) == 'demo-reviewer'


def test_administrator_cli_does_not_prompt_before_refusing_overwrite(monkeypatch, tmp_path):
    path = tmp_path / 'users.txt'
    path.write_text('existing file stays untouched\n', encoding='utf-8')
    prompted = []
    monkeypatch.setenv('LOGIN_USERS_FILE', str(path))
    monkeypatch.setattr('dotenv.load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.setattr('getpass.getpass', lambda prompt: prompted.append(prompt) or 'secret')
    monkeypatch.setattr('sys.argv', ['src.auth', 'init', 'demo-author', 'demo-reviewer'])
    with pytest.raises(SystemExit):
        main()
    assert prompted == []
    assert path.read_text() == 'existing file stays untouched\n'


def test_runtime_users_file_is_ignored_and_not_tracked():
    repository = Path(__file__).resolve().parents[2]
    candidate = repository / 'ai-learning-evaluation' / 'config' / 'users.txt'
    if not (repository / '.git').exists():
        pytest.skip('Git metadata is not present in this test environment.')
    ignored = subprocess.run(['git', 'check-ignore', '--no-index', str(candidate)], cwd=repository,
                             capture_output=True, text=True, check=False)
    tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', str(candidate.relative_to(repository))],
                             cwd=repository, capture_output=True, text=True, check=False)
    assert ignored.returncode == 0
    # Before the deletion is committed, the worktree may still report the path
    # in the index; the deliverable must at least remove it and mark it ignored.
    assert tracked.returncode != 0 or not candidate.exists()
