# Superadmin and user management

Desktop and browser accounts share the same server roles. Only **superadmins** can
list or manage users. **Admins** retain report-review and oversight access. **Members**
create and submit reports. Everyone can update their own profile and password.

| Action | Member | Admin | Superadmin |
|---|---|---|---|
| Create and submit reports | Yes | Yes | Yes |
| Review reports under the existing assignment rules | Assigned only | Yes | Yes |
| View oversight | No | Yes | Yes |
| Create users and assign member/admin/superadmin | No | No | Yes |
| Edit other users, reset passwords, enable/disable | No | No | Yes |
| Approve/reject signup requests or remove users | No | No | Yes |
| Change own profile/password | Yes | Yes | Yes |

## Set up the first superadmin

Run from `ai-learning-evaluation`, against the intended server database:

```text
python -m server.manage create-user YOUR_USERNAME --role superadmin
```

The command prompts for a password and stores a hash. To promote an existing active,
approved account while keeping its password:

```text
python -m server.manage promote-superadmin EXISTING_USERNAME
```

For Render without a shell, set `SUPERADMIN_USERNAME` and `SUPERADMIN_PASSWORD` in the
service environment and redeploy. Bootstrap creates a **new** account only. It never
promotes an existing username or overwrites its password. After the first successful
setup, remove the bootstrap password from the environment. Existing admins keep their
role and no longer manage users. Do not put real passwords in `.env.example` or Git.

## Use the dashboards

Sign in again after a role change. The browser opens the **Superadmin dashboard** after
superadmin sign-in; it is also in the top navigation. On the desktop, choose **Superadmin
dashboard** in the sidebar or account menu. Desktop management needs `SERVER_URL` and a
server with this update; offline `config/users.txt` accounts remain separate.

Use **Create user** to set a username, optional name/email, initial password and role.
Usernames stay fixed because reports and audit records refer to them. **Edit** changes
profile details and roles. Passwords cannot be viewed; **Reset password** sets a new one.
Search and role filtering help locate an account. Signup requests still need approval.

**Remove user** immediately revokes access, hides the account from the dashboard and
reserves the username. It retains the database account as a disabled tombstone so report
ownership and review history remain intact. It does not erase their reports or audit
records. Disabled accounts can be enabled again; removed accounts cannot be restored
through this dashboard. Removal includes an explicit confirmation.

A superadmin cannot remove/disable their own account or change their own role. Another
superadmin must make those changes. Role and removal operations run transactionally and
protect the last active superadmin. The server rechecks the account's current role on
every request, so stale tokens cannot retain user-management privileges after demotion.

## API

All user-management routes require a superadmin bearer token:

- `GET /users` and `POST /users`: list or create users.
- `PATCH /users/{username}`: update name, email and/or role.
- `DELETE /users/{username}`: remove access while retaining history.
- Existing `/approve`, `/reject`, `/active`, `/role` and `/password` actions remain available.

The API rejects replacing an existing account through Create user. Use the explicit edit
or password-reset operation. Account responses and audit events do not expose passwords
or password hashes. Role changes, updates and removals are audited.

Deploy the updated server before using either updated interface. The `deleted` account
column is added automatically on initialisation for SQLite and Postgres; no existing
account is automatically promoted or removed. Back up the database before deployment.
