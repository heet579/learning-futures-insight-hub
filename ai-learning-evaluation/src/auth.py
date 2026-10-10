"""Local accounts in an editable UTF-8 text file; no registration service."""
import argparse
import getpass
import hmac
import os
import re
import tempfile
from pathlib import Path

HEADER = '# One account per line: username<TAB>plain-text password\n# Blank lines and lines starting with # are ignored. Comment out a user to disable access.\n'


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
    if password.startswith('pbkdf2_sha256$'):
        raise ValueError('Replace the old password hash with a plain-text password.')
    return password


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
            username, password = re.split(r'[ \t]', line.lstrip(), maxsplit=1)
            username = normalize_username(username)
            validate_password(password)
            if username in accounts:
                raise ValueError
        except ValueError:
            raise AccountFileError(f'Check account file line {number}: use a unique username, one tab or space, and a nonempty plain-text password up to 1024 characters.') from None
        accounts[username] = password
    if not accounts:
        raise AccountFileError('No active accounts. Ask the app administrator to configure users.txt.')
    return accounts


def authenticate(username, password, path=None):
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
    return username if hmac.compare_digest(password.encode('utf-8'), expected.encode('utf-8')) else None


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
    lines.append(f'{username}\t{password}')
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace atomically so a simultaneous login never reads a partial file.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write('\n'.join(lines) + '\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    parser = argparse.ArgumentParser(description='Manage Insight Hub accounts (administrator tool).')
    parser.add_argument('command', choices=['add', 'entry'], help='Add an account or print a line to paste into users.txt')
    parser.add_argument('username')
    parser.add_argument('--replace', action='store_true', help='Replace an existing account password')
    args = parser.parse_args()
    try:
        username = normalize_username(args.username)
        password = getpass.getpass('Password: ')
        if password != getpass.getpass('Confirm password: '):
            raise ValueError('Passwords do not match.')
        if args.command == 'entry':
            print(f'{username}\t{validate_password(password)}')
        else:
            print(f'Account {username} saved in {add_user(username, password, replace=args.replace)}')
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
