# Shared server: Render + Neon

The desktop app (Tkinter) stays the same. What changes is where accounts, the Report library and
the audit log live:

```text
 Desktop app (any PC)                 Render (free web service)            Neon (free Postgres)
 ┌──────────────────────┐   HTTPS    ┌──────────────────────────┐   TLS   ┌──────────────────────┐
 │ app.py  SERVER_URL=… │ ─────────▶ │ server/app.py (FastAPI)  │ ──────▶ │ users, reports,      │
 │ src/remote.py        │  token     │ same review rules as the │         │ audit_log tables     │
 └──────────────────────┘            │ local app                │         └──────────────────────┘
                                     └──────────────────────────┘
```

* Desktops only know `SERVER_URL`. The database password lives in Render, never on a PC.
* The server decides who is signed in from a signed token, never from what the desktop sends, and
  applies the same ownership, version and review checks as the local library (an author cannot
  approve their own report; a stale reviewer cannot overwrite another decision).
* Approval is written to the server's hash-chained audit log before the approved export is stored.
* Without `SERVER_URL` the app runs fully locally, as before (useful offline and for tests).

> **Data warning.** A saved report snapshot includes the imported survey data, including the
> unmasked comments needed to reopen a workspace. With the shared server that data is stored in
> Neon. Use synthetic data only until Learning Futures approves storing real survey data there.

## 1. Create the database (Neon)

1. Sign up at <https://neon.tech> (free plan) and create a project, e.g. `insight-hub`.
   Pick the region closest to Render's (e.g. AWS Singapore or Oregon, matching step 2).
2. On the project dashboard choose **Connect**, keep the default database, and copy the
   connection string. It looks like
   `postgresql://user:password@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.
3. Keep it private. Do not commit it or paste it into chats or tickets.

The server creates its tables (`users`, `reports`, `audit_log`) on first start.

## 2. Deploy the API (Render)

1. Sign up at <https://render.com> with GitHub and allow access to this repository.
2. **New + → Blueprint**, pick the repository. Render reads [`render.yaml`](../../render.yaml).
3. When asked for values, enter:
   * `DATABASE_URL` – the Neon connection string from step 1.
   * `ADMIN_USERNAME` / `ADMIN_PASSWORD` – the first administrator (e.g. `heet`). It is created on
     startup if it does not exist. You can remove `ADMIN_PASSWORD` afterwards.
   * `SECRET_KEY` is generated automatically.
4. Deploy. When it is live, open `https://<service>.onrender.com/health`; it should show
   `{"ok": true, "database": "postgres"}`. Interactive API docs are at `/docs`.

Free plan behaviour: the service sleeps after about 15 idle minutes; the first request after that
takes up to about a minute. The sign-in screen says so while it waits.

## 3. Point every desktop at the server

In `ai-learning-evaluation/.env` on each PC:

```text
SERVER_URL=https://<service>.onrender.com
```

Restart the app and sign in with a server account. Leave `SERVER_URL` blank to go back to local mode.

## Accounts

Accounts on the server have a role: `member` (author/reviewer) or `admin` (also manages accounts).
Passwords are stored only as PBKDF2 hashes. `config/users.txt` is not used in shared mode.

From any PC with the project, put the Neon `DATABASE_URL` in your shell or `.env` (administrators
only) and run, inside `ai-learning-evaluation`:

```sh
pip install -r server/requirements.txt
python -m server.manage create-user lisa --role admin
python -m server.manage create-user xinling
python -m server.manage create-user esrat
python -m server.manage list-users
python -m server.manage disable-user someone      # takes effect immediately, even for open sessions
python -m server.manage create-user xinling --replace   # reset a password
```

Administrators can do the same through the API (`POST /users`, `GET /users`,
`POST /users/{name}/active?active=false`) from `/docs` after signing in.

## Run the server on your own PC (development)

```sh
cd ai-learning-evaluation
pip install -r server/requirements.txt
set ADMIN_USERNAME=admin & set ADMIN_PASSWORD=admin     # PowerShell: $env:ADMIN_USERNAME="admin"
uvicorn server.app:app --reload
```

Without `DATABASE_URL` it uses `reports/server_dev.sqlite3`. Then set
`SERVER_URL=http://127.0.0.1:8000` in `.env` and start `python app.py`.

## Tests

`python -m pytest -q` includes `tests/test_server.py`: the API on SQLite, and a two-account
handoff where two desktop workspaces save, submit and approve through a real HTTP server. Set
`INSIGHT_HUB_TEST_DATABASE_URL=postgresql://…` (a throwaway database; its tables are emptied) to run
the same tests on Postgres. GitHub Actions does this on every pull request.

## API summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service and database check |
| POST | `/auth/login` | Username + password → signed token |
| GET | `/auth/me` | Current account and role |
| GET | `/reports?view=mine\|pending\|approved` | Library lists |
| GET | `/reports/{id}` | Open a report the account may see |
| POST | `/reports` | Save a new or existing editable draft (version-checked) |
| POST | `/reports/{id}/rename` | Rename an owned draft |
| DELETE | `/reports/{id}?version=` | Delete an owned draft |
| POST | `/reports/{id}/transition` | `submit`, `return` or `approve` |
| POST | `/audit` · GET `/audit/verify` | Append to / verify the shared audit chain |
| GET/POST | `/users`, `/users/{name}/active` | Account management (admin) |

## Growing later

* More users or data: upgrade the Neon and Render plans; no code change.
* Faster first request: a paid Render instance does not sleep.
* Large datasets: store snapshots in object storage and keep only metadata in Postgres.
