"""Administrator tool for server accounts.

Point DATABASE_URL at the Neon database (in .env or the shell), then:
    python -m server.manage create-user lisa --role admin
    python -m server.manage create-user heet
    python -m server.manage list-users
    python -m server.manage disable-user heet
    python -m server.manage enable-user heet
"""
import argparse
import getpass
from pathlib import Path


def main(argv=None):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    from server.app import default_database_url
    from src.storage.database import Database, UserStore, ROLES

    parser = argparse.ArgumentParser(description='Manage Insight Hub server accounts.')
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create-user', help='Create an account (or change it with --replace)')
    create.add_argument('username')
    create.add_argument('--role', choices=ROLES, default='member')
    create.add_argument('--replace', action='store_true', help='Change the password/role of an existing account')
    sub.add_parser('list-users')
    for name in ('disable-user', 'enable-user'):
        sub.add_parser(name).add_argument('username')
    args = parser.parse_args(argv)

    database = Database(default_database_url())
    users = UserStore(database)
    try:
        if args.command == 'create-user':
            password = getpass.getpass('Password: ')
            if password != getpass.getpass('Confirm password: '):
                raise ValueError('Passwords do not match.')
            name = users.create(args.username, password, args.role, replace=args.replace)
            print(f'Account {name} ({args.role}) saved in {database.describe()}')
        elif args.command == 'list-users':
            for row in users.list():
                print(f"{row['username']:<24} {row['role']:<8} {'active' if row['active'] else 'disabled'}")
        else:
            users.set_active(args.username, args.command == 'enable-user')
            print(f"Account {args.username} {'enabled' if args.command == 'enable-user' else 'disabled'}.")
    except ValueError as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
