"""Administrator tool for server accounts.

Point DATABASE_URL at the Neon database (in .env or the shell), then:
    python -m server.manage create-user lisa --role admin
    python -m server.manage create-user heet
    python -m server.manage list-users
    python -m server.manage disable-user heet
    python -m server.manage enable-user heet
    python -m server.manage check          # prove the database connection works

`neon deploy` (run from the repository root) writes DATABASE_URL to the root .env.local
or .env; those files are read too.
"""
import argparse
import getpass
from pathlib import Path


def main(argv=None):
    from dotenv import load_dotenv
    app_folder = Path(__file__).resolve().parents[1]
    for env_file in (app_folder / '.env', app_folder.parent / '.env.local', app_folder.parent / '.env'):
        load_dotenv(env_file, override=False)
    from server.app import default_database_url
    from src.storage.database import Database, UserStore, ROLES

    parser = argparse.ArgumentParser(description='Manage Insight Hub server accounts.')
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create-user', help='Create an account (or change it with --replace)')
    create.add_argument('username')
    create.add_argument('--role', choices=ROLES, default='member')
    create.add_argument('--replace', action='store_true', help='Change the password/role of an existing account')
    sub.add_parser('list-users')
    sub.add_parser('check', help='Connect, create tables if needed and verify the audit chain')
    for name in ('disable-user', 'enable-user'):
        sub.add_parser(name).add_argument('username')
    args = parser.parse_args(argv)

    import os
    database = Database(default_database_url(), os.getenv('DATABASE_URL_UNPOOLED', '').strip() or None)
    users = UserStore(database)
    try:
        if args.command == 'create-user':
            password = getpass.getpass('Password: ')
            if password != getpass.getpass('Confirm password: '):
                raise ValueError('Passwords do not match.')
            name = users.create(args.username, password, args.role, replace=args.replace)
            print(f'Account {name} ({args.role}) saved in {database.describe()}')
        elif args.command == 'check':
            check(database)
        elif args.command == 'list-users':
            for row in users.list():
                print(f"{row['username']:<24} {row['role']:<8} {'active' if row['active'] else 'disabled'}")
        else:
            users.set_active(args.username, args.command == 'enable-user')
            print(f"Account {args.username} {'enabled' if args.command == 'enable-user' else 'disabled'}.")
    except ValueError as exc:
        parser.exit(1, f'{exc}\n')


def check(database):
    """End-to-end database check that leaves no test data behind."""
    from src.storage.database import DatabaseAuditTrail, DatabaseReportRepository
    print(f'Database: {database.describe()}')
    database.initialise()
    with database.connect() as db:
        version = db.execute('SELECT version()').fetchone()[0] if database.is_postgres else 'SQLite'
        print(f'Connected: {version.split(",")[0]}')
        counts = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                  for table in ('users', 'reports', 'audit_log')}
    print('Tables ready: ' + ', '.join(f'{table}={count}' for table, count in counts.items()))
    # Write and read back inside a transaction that is rolled back.
    marker = 'connection-check'
    try:
        with database.connect() as db:
            with db:
                db.execute("INSERT INTO reports (id,owner,title,course,status,updated,version,snapshot) VALUES (?,?,?,?,?,?,?,?)",
                           (marker, marker, marker, marker, 'DRAFT', 'now', 1, '{}'))
                assert db.execute('SELECT title FROM reports WHERE id=?', (marker,)).fetchone()[0] == marker
                raise _Rollback
    except _Rollback:
        pass
    print('Write/read: OK (rolled back)')
    chain = DatabaseAuditTrail(database).verify()
    print(f"Audit chain: {chain['entries']} entries, {'verified' if chain['ok'] else 'BROKEN at ' + str(chain['broken_at'])}")
    DatabaseReportRepository(database).list_pending('check')
    print('Report library query: OK')


class _Rollback(Exception):
    pass


if __name__ == '__main__':
    main()
