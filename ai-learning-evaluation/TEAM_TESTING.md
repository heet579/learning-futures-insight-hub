# Teammate testing guide

## Windows: start here

1. Install Python 3.13 with Tcl/Tk support if it is not already installed. The app was tested with Python 3.13.5 on Windows.
2. Clone the repository (or extract the ZIP) into a normal folder, such as Documents. Do not run it inside the ZIP preview.
3. In PowerShell, inside `ai-learning-evaluation`, run `powershell -ExecutionPolicy Bypass -File run_app.ps1`. The first launch creates a private .venv and downloads the dependencies, so allow a few minutes and keep an internet connection available.
4. The app opens empty. Click **Import CSV / Excel** and choose `data/synthetic_qualtrics_evaluation.csv`. Without a Gemini key the app still works: drafts use local fixed wording.
5. Later launches: `.venv\Scripts\python.exe app.py`.

If setup fails, capture the full error message. Do not change your computer's security settings; ask your IT team if Python or scripts are restricted.

## macOS / Linux

The source is portable. Automated tests also run on Linux (Docker and CI). From a terminal in the extracted folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Tkinter must be available in that Python installation. If a Tk import fails, send the error and OS details to Heet.

## Manual acceptance checklist

Record Pass or Fail for each check:

| Check | Expected result |
| --- | --- |
| Launch | App opens empty with PENDING cards and no error dialog |
| Import | `data/synthetic_qualtrics_evaluation.csv` loads; cards and rating bars fill in |
| Search | A known response ID returns the correct row; nonsense text returns no matches |
| Response detail | Selecting a row shows complete masked content below the table |
| Themes (Gate 1) | First decision asks for your name; every theme can be confirmed, re-categorised or rejected |
| Draft blocked | Get Gemini draft refuses until every theme is decided |
| Draft | Facilitator and client drafts generate (Gemini, or local wording if no key) |
| Ask Gemini revision | A request such as "write a short summary" shows a before/after preview with cited evidence |
| Review claims (Gate 2) | Every sentence is listed; rejecting removes it from the draft |
| Fabricated figure | Typing "99.9% of learners..." in the draft cannot be accepted and blocks submission |
| Quotes (Gate 3) | Each quote must be cleared or removed; possible names are flagged |
| Submit (Gate 4) | Submit is refused while anything is pending; succeeds once all checks pass |
| Same approver | Approving with the author's name is refused |
| Return for changes | Requires notes; the report goes back to the author |
| Edit after submit | Any edit sends the report back to Draft |
| Approve & export | The Word file ends with a Review record naming author and approver |
| Audit log | The panel shows "chain verified"; the log holds no learner comments |
| Unsaved work | Importing new data or closing warns about an unsaved draft |
| Invalid CSV | A CSV with wrong columns shows an error and keeps the previous dataset |
| Resize | Navigation and the review panel stay usable at your screen size and scaling |

Please use synthetic data for shared test reports. Each teammate runs an independent local copy; changes do not synchronise to other PCs. Save exported reports outside the application folder if you plan to replace it with a newer ZIP.

## Report a bug

Copy this template into your team issue tracker or message:

- Tester:
- Windows/macOS/Linux version:
- Screen resolution and display scaling:
- Python version:
- Steps to reproduce:
- Expected result:
- Actual result:
- Screenshot or full error text:
- Severity: blocks demo / major / minor / visual

## Automated tests (optional)

After setup on Windows:

```powershell
.venv\Scripts\python.exe -m pytest -q
```

The suite has about 136 tests covering import, metrics, themes, Gemini requests (mocked), the review gates, the audit log and the desktop workflow. Desktop tests need a display. A passing suite does not guarantee every teammate's environment is identical.

## macOS blank or grey window

A partially blank window can be caused by an old or incompatible Tcl/Tk runtime. The updated app rejects macOS Tk versions below 8.6.11, uses native font selection and portable navigation styling, and reports startup exceptions. This does not prove that every blank window has the same cause.

1. Install Python 3.13 from https://www.python.org/downloads/macos/ using its bundled Tcl/Tk support.
2. Pull the latest project changes and open Terminal in `ai-learning-evaluation`.
3. Run the following to create a fresh environment while keeping the previous one:

```sh
python3.13 -m venv .venv-mac
.venv-mac/bin/python -m pip install -r requirements.txt
.venv-mac/bin/python app.py
```

Use the last line for later launches. If Python was installed somewhere else, use its full path in the first line.

If the screen is still blank, send the output of:

```sh
.venv-mac/bin/python app.py --diagnose
.venv-mac/bin/python -m tkinter
```

Also include the macOS version and whether the small Tk test window renders. `--diagnose` prints only runtime information and executable paths; it does not read survey data. Review the path before sharing it publicly.

Python's official Tcl/Tk guidance: https://www.python.org/download/mac/tcltk/
