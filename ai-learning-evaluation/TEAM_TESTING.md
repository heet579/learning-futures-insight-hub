# Teammate testing guide

## Windows: start here

1. Install Python 3.13 with Tcl/Tk support if it is not already installed. The app was tested with Python 3.13.5 on Windows.
2. Extract the entire ZIP into a normal folder, such as Documents. Do not run it inside the ZIP preview.
3. Double-click START_DEMO.cmd. First launch creates a private .venv and downloads the dependencies, so allow a few minutes and keep an internet connection available.
4. The app opens with synthetic demo data. No API keys, accounts or external AI service are needed.
5. On subsequent runs, double-click START_DEMO.cmd again. Installed dependencies are reused.

If setup fails, capture the full error message. Do not change your computer's security settings; ask your IT team if Python or scripts are restricted.

## macOS / Linux

The source is portable, but this release has only been checked on Windows. From a terminal in the extracted folder:

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
| Launch | Demo loads, controls are visible, no error dialog |
| Dashboard | Response count, ratings, recommendation and completeness are shown |
| Course scope | Switching course changes the displayed population and metrics |
| Open CSV | Included data/synthetic_qualtrics_evaluation.csv loads correctly |
| Search | A known response ID returns the correct row; nonsense text returns no matches |
| Response detail | Selecting a row shows complete masked content below the table |
| Themes | Selecting a theme shows supporting comments and keywords |
| Generate report | Both facilitator and client drafts generate and have a reading preview |
| Edit report | Changes appear in the preview; editing clears review confirmation |
| Save draft | Word/Markdown saves with a draft label |
| Approval required | Reviewed export requires a reviewer name and checked confirmation |
| Reviewed export | Saved document opens and contains the reviewer and edited wording |
| Unsaved work | Changing datasets or closing warns about an unsaved draft; declining keeps it |
| Invalid CSV | A CSV with wrong columns shows an error and preserves the previous dataset |
| Data assistant | Suggested questions return answers for the selected scope |
| Resize | Navigation and controls remain usable at your normal screen resolution and scaling |

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

Current local verification: 30 tests passed on Windows. This is not a guarantee that every teammate's environment is identical.
