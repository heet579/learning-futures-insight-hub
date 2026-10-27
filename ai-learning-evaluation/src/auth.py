"""Local accounts in an ignored UTF-8 file with PBKDF2 password hashes."""
import argparse
import base64
import getpass
import hashlib
import hmac
import os
import re
import secrets
import tempfile
from pathlib import Path

HASH_SCHEME = 'pbkdf2_sha256'
PBKDF2_ITERATIONS = 600_000
MIN_PBKDF2_ITERATIONS = 100_000
MAX_PBKDF2_ITERATIONS = 2_000_000
SALT_BYTES = 16
HEADER = ('# Local accounts: username<TAB>PBKDF2 password hash\n'
          '# Generate entries with python -m src.auth init/add/entry. Never commit this file.\n'
          '# Blank lines and lines starting with # are ignored. Comment out a user to disable access.\n')


class AccountFileError(ValueError):
    """Account configuration cannot be used safely."""


def users_path():
    project = Path(__file__).resolve().parents[1]
    configured = Path(os.getenv('LOGIN_USERS_FILE', '').strip() or 'config/users.txt').expanduser()
    return configured if configured.is_absolute() else project / configured


def normalize_username(username):
    username = username.strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.@-]{0,63}', username):
        raise ValueError('Use 1–64 letters, numbers, dots, underscores, @ or hyphens for the username.')
    return username


def validate_password(password):
    if not 1 <= len(password) <= 1024:
        raise ValueError('Use a nonempty password up to 1024 characters.')
    if any(character in password for character in '\r\n\t\v\f\x1c\x1d\x1e\x85\u2028\u2029'):
        raise ValueError('Passwords cannot contain tabs or line breaks.')
    return password


def _b64encode(value):
    return base64.urlsafe_b64encode(value).decode('ascii')


def _b64decode(value):
    return base64.b64decode(value.encode('ascii'), altchars=b'-_', validate=True)


def _password_hash_parts(encoded):
    try:
        scheme, iterations_text, salt_text, digest_text = encoded.split('$')
        iterations = int(iterations_text)
        salt, digest = _b64decode(salt_text), _b64decode(digest_text)
    except (ValueError, TypeError, UnicodeError):
        raise ValueError('Invalid password hash.') from None
    if (scheme != HASH_SCHEME or not MIN_PBKDF2_ITERATIONS <= iterations <= MAX_PBKDF2_ITERATIONS
            or len(salt) < SALT_BYTES or len(digest) != hashlib.sha256().digest_size):
        raise ValueError('Invalid password hash.')
    return iterations, salt, digest


def hash_password(password, *, iterations=PBKDF2_ITERATIONS, salt=None):
    """Return a self-contained PBKDF2 hash; never persist the supplied password."""
    password = validate_password(password)
    if not MIN_PBKDF2_ITERATIONS <= iterations <= MAX_PBKDF2_ITERATIONS:
        raise ValueError('Unsupported PBKDF2 iteration count.')
    salt = secrets.token_bytes(SALT_BYTES) if salt is None else salt
    if len(salt) < SALT_BYTES:
        raise ValueError('Password salts must be at least 16 bytes.')
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return f'{HASH_SCHEME}${iterations}${_b64encode(salt)}${_b64encode(digest)}'


def verify_password(password, encoded):
    """Verify a password against a supported encoded hash in constant time."""
    try:
        validate_password(password)
        iterations, salt, expected = _password_hash_parts(encoded)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return hmac.compare_digest(actual, expected)


def read_users(path=None):
    path = Path(path) if path is not None else users_path()
    try:
        content = path.read_text(encoding='utf-8-sig')
    except OSError:
        raise AccountFileError('Account file unavailable. Ask the app administrator to configure users.txt.') from None
    except UnicodeError:
        raise AccountFileError('Save users.txt as UTF-8 text.') from None
    accounts = {}
    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        try:
            username, password_hash = re.split(r'[ \t]+', line.lstrip(), maxsplit=1)
            username = normalize_username(username)
            _password_hash_parts(password_hash)
            if username in accounts:
                raise ValueError
        except ValueError:
            raise AccountFileError(
                f'Check account file line {number}: use a unique username followed by a supported password hash. '
                'Create entries with python -m src.auth add USERNAME.') from None
        accounts[username] = password_hash
    if not accounts:
        raise AccountFileError('No active accounts. Ask the app administrator to configure users.txt.')
    return accounts


def authenticate(username, password, path=None):
    from src.remote import ServerError, ServerUnavailable, login, server_url
    if server_url():
        # Shared accounts on the Insight Hub server; users.txt is not used.
        try:
            return login(username, password)
        except (ServerError, ServerUnavailable) as exc:
            raise AccountFileError(str(exc)) from None
    # Reload on every attempt: file edits apply without restarting the app.
    accounts = read_users(path)
    try:
        username = normalize_username(username)
    except ValueError:
        username = ''
    expected = accounts.get(username)
    if not password or len(password) > 1024:
        return None
    if expected is None:
        return None
    return username if verify_password(password, expected) else None


def _write_users(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write('\n'.join(lines) + '\n')
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def add_user(username, password, path=None, replace=False):
    username = normalize_username(username)
    validate_password(password)
    path = Path(path) if path is not None else users_path()
    if path.exists():
        original = path.read_text(encoding='utf-8-sig')
        # Validate existing active entries, allowing a commented-out/empty file.
        if any(line.strip() and not line.lstrip().startswith('#') for line in original.splitlines()):
            accounts = read_users(path)
        else:
            accounts = {}
        if username in accounts and not replace:
            raise ValueError('That account exists. Use --replace to change its password.')
        lines = [line for line in original.splitlines()
                 if not (line.strip() and not line.lstrip().startswith('#')
                         and line.split()[0].lower() == username)]
    else:
        lines = HEADER.rstrip().splitlines()
    lines.append(f'{username}\t{hash_password(password)}')
    _write_users(path, lines)
    return path


def initialize_users(accounts, path=None):
    """Create a new account file with at least two distinct local accounts."""
    path = Path(path) if path is not None else users_path()
    if path.exists():
        raise FileExistsError(f'{path} already exists; refusing to overwrite it.')
    prepared, seen = [], set()
    for username, password in accounts:
        username = normalize_username(username)
        if username in seen:
            raise ValueError('Bootstrap usernames must be unique.')
        seen.add(username)
        prepared.append(f'{username}\t{hash_password(password)}')
    if len(prepared) < 2:
        raise ValueError('Bootstrap requires at least two accounts for the review workflow.')
    _write_users(path, HEADER.rstrip().splitlines() + prepared)
    return path


def _prompt_password(username):
    password = getpass.getpass(f'Password for {username}: ')
    if password != getpass.getpass(f'Confirm password for {username}: '):
        raise ValueError(f'Passwords for {username} do not match.')
    return validate_password(password)


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    parser = argparse.ArgumentParser(description='Manage hashed Insight Hub accounts (administrator tool).')
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('add', help='Add one hashed account to users.txt')
    add.add_argument('username')
    add.add_argument('--replace', action='store_true', help='Replace an existing account password')
    entry = commands.add_parser('entry', help='Print one hashed account line to paste into users.txt')
    entry.add_argument('username')
    init = commands.add_parser('init', help='Create a new users.txt with at least two accounts')
    init.add_argument('usernames', nargs='+')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            if len(args.usernames) < 2:
                raise ValueError('Provide at least two distinct usernames for author and second reviewer accounts.')
            usernames = [normalize_username(name) for name in args.usernames]
            if len(set(usernames)) != len(usernames):
                raise ValueError('Bootstrap usernames must be unique.')
            path = users_path()
            if path.exists():
                raise FileExistsError(f'{path} already exists; refusing to overwrite it.')
            accounts = [(name, _prompt_password(name)) for name in usernames]
            path = initialize_users(accounts, path)
            print(f'Created {len(accounts)} hashed local accounts in {path}.')
        else:
            username = normalize_username(args.username)
            password = _prompt_password(username)
            if args.command == 'entry':
                print(f'{username}\t{hash_password(password)}')
            else:
                path = add_user(username, password, replace=args.replace)
                print(f'Account {username} saved as a password hash in {path}.')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
