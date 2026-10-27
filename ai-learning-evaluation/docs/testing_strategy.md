# Running the test suite

Run commands from the repository root. Use Python 3.12 or 3.13 with the application and server packages installed:

```text
python -m pip install -r ai-learning-evaluation/server/requirements.txt
```

The launchers use `TESTSUIT_PYTHON` when set, otherwise the app's `.venv` if available, otherwise Python on PATH. Install packages into that interpreter. The preflight check names missing dependencies and prints the appropriate installation command. Nothing is installed automatically.

## One command

PowerShell on Windows:

```powershell
./testsuit
```

Command Prompt on Windows:

```cmd
testsuit.cmd
```

macOS or Linux:

```sh
./testsuit
```

PowerShell resolves `./testsuit` to `testsuit.ps1`; the explicit `./testsuit.ps1` command also works. The Python entry point works from any directory: `python /path/to/learning-futures-insight-hub/tools/testsuit.py`.

If PowerShell policy prevents running `.ps1` files, use `./testsuit.cmd`. Set `TESTSUIT_PYTHON` to choose another interpreter. To run desktop tests on Linux without a display, install Xvfb and Python's Tk package and use `xvfb-run -a ./testsuit`.

## Select checks

These options work with every launcher:

```powershell
./testsuit.ps1 --list
./testsuit.ps1 --suite data
./testsuit.ps1 --suite api --suite accounts
./testsuit.ps1 --suite reports -k "approval or export"
./testsuit.ps1 --fail-fast --verbose
./testsuit.ps1 --headless --no-color
./testsuit.ps1 --strict-skips --output-dir test-results/release
```

| Group | Checks |
|---|---|
| `data` | CSV and Excel, Qualtrics layouts, incomplete data, metric denominators, themes, contact masking and source preservation |
| `analysis` | Mocked provider requests and errors, questions, evidence references and numeric grounding |
| `reports` | Report sections, revisions, approval gates, quote handling and audit integrity |
| `accounts` | Local and server accounts, sessions, Google sign-in doubles and sign-in screens |
| `desktop` | Navigation, report library, reviewer handoff, review screens and Tk compatibility |
| `api` | Browser workflows, ownership, upload limits, token expiry, request validation, stale versions and export gates |
| `runner` | Real CLI subprocesses, report accuracy, failures, skips, collection errors, interruption and isolation |

Without `--suite`, all `test_*.py` files in `ai-learning-evaluation/tests` and `tools/tests` run. New uncategorised files appear under `other`; add their stems to `tools/suite_catalog.py` to assign a group. Some account and API files also contain Tk integration tests, which are explicitly skipped with `--headless`.

## Read results

The console lists completed files, totals by area, failure details, warnings and the five slowest tests. Colors appear only in interactive terminals; `--no-color` or `NO_COLOR` disables them.

- **Pass** means the test completed successfully.
- **Fail** means the test body failed.
- **Error** means setup or cleanup failed; a cleanup failure overrides a passed body.
- **Skip** means the test was not run and is not counted as passed.
- **Xfail** means a declared expected failure occurred.
- **Xpass** means an expected failure unexpectedly passed, which fails the command.
- **Unfinished** means execution started but did not finish, for example during interruption.

Runs with skips are labelled `PASSED WITH SKIPS`. `--strict-skips` makes ordinary test or module skips fail; expected failures remain visible as Xfail. A headless run does not verify the desktop interface. Module skips are shown separately and included in JSON.

## Saved reports and exit codes

Pytest runs write `test-results/latest/results.json` and `junit.xml`, or the directory chosen with `--output-dir`. These generated files are ignored by Git. Subsequent runs overwrite the two report files. Preflight failures do not create fresh reports: check the command's exit code rather than an old file from a previous run.

JSON schema version 1 includes status, exit code, duration, collected/executed/deselected counts, outcome totals, individual identifiers, timings and failure/skip details, collection errors/skips, and warnings. JUnit XML is pytest's standard CI report. Area durations sum setup/body/cleanup time; wall-clock duration also includes collection and reporting.

| Code | Meaning |
|---|---|
| `0` | Selected tests passed; check skip and expected-failure counts |
| `1` | Test failure, setup/cleanup error, unexpected pass or strict-skip failure |
| `2` | CLI/setup failure, collection error or pytest interruption; read the console status |
| `3` | Internal pytest error |
| `4` | Pytest usage error |
| `5` | No tests selected |
| `130` | Launcher interrupted directly |

## Isolation and Postgres

The runner removes inherited service/API credentials, disables `.env` loading before collection, redirects writable state to temporary locations, and disables unrelated auto-loaded pytest plugins. Python UTF-8 mode keeps exported report text consistent on Windows. Provider calls use test doubles. TCP connections are limited to loopback servers, except for an explicitly selected Postgres test database. Live Gemini and Google services are not required. Plain `pytest` does not enable these runner-specific protections.

SQLite always runs. Postgres needs both `--postgres` and `INSIGHT_HUB_TEST_DATABASE_URL`. Existing fixtures empty the users, reports and audit tables, so use a disposable test database only:

```powershell
$env:INSIGHT_HUB_TEST_DATABASE_URL = 'postgresql://test_user:test_password@127.0.0.1:5432/insight_hub_test'
./testsuit.ps1 --suite api --postgres
```

The runner does not copy the application's `DATABASE_URL`. Install `psycopg[binary]` and `psycopg-pool` through the server requirements before opting in. The selected test database is the only non-loopback host allowed.

## CI and manual review

GitHub Actions runs the full suite with Xvfb, SQLite and a disposable Postgres service on Linux. Windows exercises the PowerShell launcher with explicit headless skips. Both jobs upload JSON and JUnit reports for seven days, including on failure. CI results become available after pushing these changes.

Manually check realistic anonymised uploads, layout at the target laptop resolution, contextual identifying details that regex masking cannot detect, interpretation quality and exported Word reports. Live external services, load testing, stakeholder acceptance and real Google OAuth credentials are outside the default suite.

