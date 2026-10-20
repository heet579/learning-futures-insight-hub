# Learning Futures Insight Hub — Python Desktop

Native Python desktop application using Tkinter/ttk. No Streamlit, browser or web server is required.

## Install and launch

For cloning, updates and team branches, see the [repository connection guide](../README.md).

```powershell
cd ai-learning-evaluation
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Windows setup launcher: `./run_app.ps1`. After dependencies are installed in your default Python, double-click `launch_app.pyw` to open without a console. macOS/Linux: run `python app.py` after installing requirements (Linux may require `python3-tk`).

## Sign in and manage accounts

The app opens on a sign-in screen. There is no signup, and the workspace is built only after a valid username and password. The repository includes the shared prototype accounts in `config/users.txt`. To add another account from the application folder:

```powershell
python -m src.auth add newuser
```

Enter and confirm a nonempty password when prompted. Accounts live in **`config/users.txt`**, an editable UTF-8 plain text file tracked in Git. Each active line contains a username, one tab or space, and the readable password (up to 1024 characters). Usernames are case-insensitive; passwords are case-sensitive. Spaces inside passwords are preserved; tabs and line breaks are not allowed. Commit and push account-file changes to share them with the team; teammates receive those changes when they pull.

To add a user, open `config/users.txt` and add a line such as `alex ExamplePassword123`. Change their password by editing the second value directly. Alternatively, `python -m src.auth add USERNAME` appends an account for you, `python -m src.auth entry USERNAME` prints a line to paste, and `python -m src.auth add USERNAME --replace` resets a password. Remove a line or put `#` at its beginning to disable an account. Changes take effect at the next login attempt; an already-open workspace stays open until closed. Use the account menu in the top-right corner to switch accounts or sign out without restarting the application.

Passwords are stored as plain text for the current prototype. Blank lines and `#` comments are allowed; malformed or duplicate active accounts block login and identify the line to fix. See [the file template](config/users.example.txt). `LOGIN_USERS_FILE` can point to another text file; relative paths resolve from the application folder. Anyone who can read the file can see the passwords, and anyone with write access can manage users. Existing password hashes must be replaced with readable passwords.

For Docker Compose, accounts persist in the host's `shared/users.txt`. Copy `config/users.txt` to `../shared/users.txt` to use the repository's accounts, or after starting the container run `docker compose exec insight-hub python -m src.auth add admin` to create the first account if the file has none. You can then edit `shared/users.txt` directly; this Docker copy remains local and is not updated by Git pulls. Other Docker launch methods must set `LOGIN_USERS_FILE` to a writable, persistent account-file location.

## Application workflow

1. Launch the app and sign in to **Report library**. Choose **Create report** to start immediately without naming it, or **Continue editing** to reopen a saved draft. In Explore data, choose **Import CSV / Excel**. Import your survey files or `data/synthetic_qualtrics_evaluation.csv` for a demo, then review the response count, mean overall rating, recommendation and completeness cards and the rating chart.
2. In **Explore data**, switch to the **Survey data** tab, search for a response or phrase, and select a row to inspect its full masked content.
3. Open **Themes & evidence**. For each theme read the supporting comments (the matched keyword is shown under each one), then **Confirm**, change the category, or **Reject** it. Only confirmed themes go into the report. **Ask a question** answers from the calculated evidence.
4. Use **Continue to themes** and **Continue to report** to follow the workflow; the latter becomes available once all themes are reviewed. In **Report studio**, choose facilitator or client and click **Generate draft**. If Gemini is not set up, or the request fails and you agree, a local draft with fixed wording is created instead and the status line says so.
5. Generated drafts open in **Reading preview**. Use **Edit draft** for direct changes, or in **Feedback & revisions**, pick a section and a method: **Ask Gemini** (rewrite from your request, e.g. "write a short summary"), **Edit from feedback** (offline rules) or **Manual replacement**. Preview, then Apply or Undo.
6. In **Check facts & quotes**, accept or reject every sentence and bullet, and clear or remove every learner quote.
7. In **Human review**, click **Submit for review**. This saves the current draft (asking for its title if needed), checks the stored review decisions, and publishes a locked snapshot to other accounts' **Pending review** lists.
8. Use **Switch account** and sign in as a different reviewer. Open **Library → Pending review → Review report**, read the report and evidence, then open **Review decision**. Both names come from the signed-in accounts. Select the approver role, confirm the checks and click **Approve report**, or **Return for changes** with required notes.
9. Approval is saved before export. Click **Export approved** for Word/Markdown. Both the author and approving reviewer can reopen it under **Approved** and export again after restarting. Cancelling or failing an export does not undo approval. For a returned report, its author opens **My reports**, reads the notes in Human review, edits, checks new claims and submits again.

See [the complete demo walkthrough](DEMO_REVIEW_WALKTHROUGH.md).

## Human review workflow

| Gate | What a person must do | What the app enforces |
|---|---|---|
| 1 Themes | Confirm, re-categorise or reject each theme after reading its comments. | **Get draft** is blocked until every theme is decided. Changing a theme after drafting blocks submission until a new draft is made. |
| 2 Claims | Accept or reject every sentence and bullet. Each shows its source: Calculated, AI-written or Human-edited, plus the figures checked and the evidence Gemini cited. | A claim with a figure or quote that is not in the data cannot be accepted. Editing a claim's text makes it pending again. Rejecting removes it from the draft. |
| 3 Quotes | Clear each learner quote for identifying detail, or remove it. Possible names are highlighted. | Quotes are separate items in the claim list and must be decided. |
| 4 Two people | The author submits; a different person approves. Client reports need a "Learning Futures lead". Returning a report needs notes. | Self-approval and self-return are refused. Submitted and approved text is locked. Only the owner can edit a returned report and resubmit it. |
| 5 Pace | Take time to check evidence. | If five or more decisions are made with a median gap under 3 seconds, a "Fast review" warning is shown and printed in the Review record. |
| 6 Record | — | Every import, theme and claim decision, revision, submission, return, approval and export is appended to a hash-chained audit log (default `~/.learning_futures_insight_hub/review_audit_log.jsonl`, or `AUDIT_LOG_PATH`). Each line holds the SHA-256 of the previous one, so edits to history are detected. The log holds names, decisions, counts and hashes, never learner comments. Approved exports end with a **Review record** page. Approval is refused if the log cannot be written. |

The workspace requires sign-in. Theme and claim decisions, revisions, draft saves and submission use the signed-in account. The author account is read-only. The second reviewer name also comes from the signed-in account. The approver role is self-selected in this demo; it is not an administrator-assigned account permission. Client reports still require selecting Learning Futures lead.

The top-right account menu supports **Switch account** and **Sign out**. Unsaved reports offer save-to-library, discard or cancel. A failed/cancelled save keeps the session open. Background operations block switching. Saved drafts remain available to the same account after signing in again.

## Local report library

- **Report library** is the home screen and the first sidebar destination. **Create report** opens a clean workspace; naming happens only on first **Save draft**. The save button is available throughout the three workflow pages after importing data; subsequent saves update that draft.
- Data and partial theme-review progress can be saved before generating any report text. Old saved report snapshots remain readable. Creating another report leaves saved copies in the library, and warns before discarding unsaved work.
- Report studio starts with a short guide, opens generated drafts in Reading preview, and shows the next review action above the report. Approval details open on click. Regenerating explicitly confirms that text, claim decisions, revisions and approval progress will be replaced.
- **My reports** lists reports you own, including saved drafts, submissions and returned reports. **Pending review** lists other accounts' submissions. **Approved** lists approved reports that you authored or approved. Only submitted snapshots are shared with all other signed-in accounts; unsubmitted drafts stay owner-only. Approved reports are accessible to their author and approving reviewer.
- Report cards show the report title, scope, status, first reviewer (the draft owner) and last-saved time. **Continue editing**, **Review report** or **View report** reflects the current state. Only the owner of an editable draft sees **More**, which expands the normally hidden **Rename** and **Delete draft** actions. Click More again, click outside, or press Escape to close them. Only one card's actions can be open at a time. Renaming keeps its data and review progress; unsaved edits in an open draft remain unsaved. Deletion asks for confirmation and permanently removes the saved draft. If it is currently open, its workspace and unsaved changes are also cleared and Library is shown. Original survey files, exports and the audit log remain.
- Rename and delete are limited to the owner's editable drafts. Version checks reject changes to a draft that another workspace has updated; refresh and reopen it before retrying.
- Choose **Create report** to start a separate report. Multiple drafts are supported; report IDs do not depend on the title.
- Snapshots contain the imported dataset, masked analysis data, calculated context, report text, theme/claim decisions, workflow events and revision proposals/results. Source files need not remain at their original paths.
- **Export draft** remains available in Human review and produces a document, not a restorable workspace.
- Only the owner can edit, rename or delete an editable draft. Submission, approval and return use version checks inside a database transaction. A stale reviewer must reopen the report; they cannot overwrite another reviewer's decision.
- The local library persists DRAFT, AWAITING HUMAN REVIEW, CHANGES REQUESTED and HUMAN REVIEWED states. Existing databases are migrated automatically without deleting saved drafts. Approved export text and its review record are stored with the approved version. This is a shared local database, not cross-computer cloud collaboration.
- Default database: `~/.learning_futures_insight_hub/reports.sqlite3`. Set `REPORT_LIBRARY_PATH` for another persistent local location. In Docker, point it to `/workspace/reports.sqlite3` so the existing shared volume preserves it across container recreation.
- The SQLite file contains survey and review data. It is local application data; do not commit or share it as source code. This prototype does not encrypt the database or protect it from someone with filesystem access.
- JSON snapshots are schema-versioned; SQLite access is isolated in `src/storage/reports.py` for future replacement with a cloud API.

## Calculation notes

- **Overall rating** (card) is the mean of valid 1–5 answers. **Satisfaction %** is answers of 4 or 5 divided by valid answers, the same denominator as the mean.
- **Completeness** covers only fields the survey actually collected. Fields that are blank in every row (for real exports: DeliveryMode, ClientType, FacilitatorCode) are listed in the report as not collected.
- Qualtrics **"Selected Choice"** answers (preset option lists) are not treated as comments. The free-text "Other" box is. When two free-text questions map to the same field, both answers are kept.
- The **evidence check** accepts figures that round to a real value at the precision written ("97%" for 97.4%) and treats "5/5" as a point on the rating scale.

The application starts empty, even when `data/client/` or `EVALUATION_DATA_PATH` is configured. **Import CSV / Excel** (Ctrl+O) accepts one or more compatible survey files and replaces the active dataset after validation. A bold uppercase filename beside the import button identifies the selected file during processing and after loading; multiple imports also show the additional file count. See [data requirements](data/README.md) and [column definitions](docs/data_dictionary.md). Synthetic records remain identified by the source filename when explicitly imported.

## Interface and workflow

- Purple/white navigation sidebar (Report library home, followed by Explore data, Themes & evidence, Report studio), consistent typography, clear page descriptions.
- Metric cards, proportional rating bars and an evidence summary.
- Search across all selected responses, striped data rows, full response detail and quality warnings.
- Selectable themes with keyword and comment evidence.
- Formatted report preview, editable drafts, named review, Word/Markdown export.
- Background analysis, progress indicator, friendly failures and disabled actions while processing.
- Unsaved-report protection and review confirmation reset after editing.

The preview displays at most 1,000 matching rows; analysis and search include every row in the selected scope. Changing data or scope clears old drafts after warning about unsaved work. Invalid files preserve the prior workspace. Ctrl+O opens a CSV.

## Scope and limitations

Drafts use Gemini when `GEMINI_API_KEY` is set and fall back to local fixed wording otherwise. Section revisions can use Gemini, offline edits or human-supplied wording. Pattern masking and the name flags need human checking. Themes are indicators and recommendations need review. Use Save draft to persist editable workspace state in the local library before closing; the review audit log is also kept on disk.

The desktop implementation is `src/ui/desktop.py` with the review screens in `src/ui/review.py`; `app.py` and `launch_app.pyw` launch it. [docs/code_map.md](docs/code_map.md) lists where every screen and feature lives, and [docs/architecture.md](docs/architecture.md) shows the data flow.

### Known limitations

- **PII masking is regex-based** (email, AU phone, URL patterns only). Free-text comments can still contain names or other identifying detail that no pattern catches; a human reviewer must read every comment before export, not just trust the mask count.
- **Real PACE/Qualtrics exports carry no `ClientType` or `FacilitatorCode` column**, and `DeliveryMode` isn't present either. These fields are left blank for client data rather than guessed; any report language depending on them is unavailable for that scope.
- **Theme extraction is rule-keyword plus TF-IDF/NMF**, not semantic understanding. It surfaces recurring terms, not verified sentiment; treat themes as a starting point for the reviewer, not a finding.
- **The Evidence check (`src/reporting/grounding.py`) verifies numbers and quotes only** — percentages, rating means, response/comment counts and quoted feedback, checked against the computed metrics and theme evidence. It does not assess whether prose claims are reasonable, only whether the figures and quotes present are real; a human reviewer must still judge the writing itself.
- **Rating sub-questions in real exports don't map one-to-one onto the four canonical rating categories.** Only the closest-matching item per category is used (see `docs/data_dictionary.md`); the remaining sub-questions (enrolment ease, communication timing, presenter subject knowledge, Q&A helpfulness) are not currently reported.

## Verification

Run `python -m pytest -q`. Desktop regression tests cover loading, navigation, searches beyond the preview limit, invalid files, scope changes, unsaved work, preview/edit behavior, approval and export, theme evidence and local Q&A. Desktop tests require an available Tk display.

## macOS display troubleshooting

For a grey or partially blank screen, use the [Mac recovery steps](TEAM_TESTING.md#macos-blank-or-grey-window). The app now checks the actual Tk runtime before drawing the interface, uses the system font, and displays only the selected page. Startup and callback errors are reported instead of silently leaving an incomplete window.

Run `python app.py --diagnose` to print the Python, Tcl/Tk and window-system versions without loading data. This release's compatibility changes were verified with Windows tests; the affected Mac must still be retested.

## Feedback and Docker distribution

Use the **Feedback & revisions** tab after generating a report. Preview before applying; every applied revision clears approval and can be undone. **Ask Gemini** rewrites the selected section from your request; **Edit from feedback** applies offline rules; **Manual replacement** uses wording you paste or write (for example from Microsoft Copilot). Rewritten sentences appear in **Check facts & quotes** and must be accepted like any other claim.

The [Docker guide](../DOCKER.md) explains how teammates can clone the repository and run the same Python desktop in a local browser using Docker Compose, without host Python/Tk setup.
