"""Authentication and administrator file-edit workflow; no external services."""
import pytest

from src.auth import AccountFileError, add_user, authenticate, main, read_users, users_path


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
    assert 'alice\ta good password' in accounts.read_text()


def test_direct_file_edits_apply_at_next_attempt(accounts):
    with accounts.open('a', encoding='utf-8') as stream:
        stream.write('Bob bob password\n')
    assert authenticate('bob', 'bob password', accounts) == 'bob'
    accounts.write_text(accounts.read_text().replace('bob password', 'edited password'), encoding='utf-8')
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
    with pytest.raises(AccountFileError, match='line 4'):
        authenticate('alice', 'a good password', accounts)


def test_utf8_bom_and_password_spaces(accounts):
    add_user('user', ' password with spaces ', accounts)
    accounts.write_text(accounts.read_text(), encoding='utf-8-sig')
    assert authenticate('user', ' password with spaces ', accounts) == 'user'
    assert authenticate('user', 'password with spaces', accounts) is None


@pytest.mark.parametrize('password', ['', 'x' * 1025, 'password\nother', 'password\tother', 'pbkdf2_sha256$oldhash'])
def test_invalid_passwords_are_not_written(tmp_path, password):
    path = tmp_path / 'users.txt'
    with pytest.raises(ValueError):
        add_user('user', password, path)
    assert not path.exists()


def test_unicode_password_and_comments(tmp_path):
    path = tmp_path / 'users.txt'
    path.write_text('   # Comment\n\nuser café-password\n', encoding='utf-8')
    assert authenticate('user', 'café-password', path) == 'user'
    assert authenticate('user', 'cafe-password', path) is None


def test_direct_entry_with_short_password(tmp_path):
    path = tmp_path / 'users.txt'
    path.write_text('user 12345\n', encoding='utf-8')
    assert authenticate('user', '12345', path) == 'user'


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
    assert entry == 'newuser\tchosen password'
    with path.open('a', encoding='utf-8') as stream:
        stream.write(entry + '\n')
    assert authenticate('newuser', 'chosen password', path) == 'newuser'
