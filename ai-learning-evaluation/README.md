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

Windows setup launcher: `./run_demo.ps1`. After dependencies are installed in your default Python, double-click `launch_demo.pyw` to open without a console. macOS/Linux: `bash run_demo.sh` (Linux may require `python3-tk`).

## Demo walkthrough (about 3 minutes)

1. Launch the app. Included synthetic data loads automatically. Show the response count, satisfaction, recommendation and completeness cards, then the rating chart.
2. Change the course scope and show how the dashboard updates.
3. Open **Survey data**, search for a response or phrase, and select a row to inspect its full masked content.
4. Open **Themes & evidence** and select a theme to show the supporting comments.
5. Open **Report studio**, choose facilitator or client, and click **Generate draft**. Switch between the reading preview and editable draft.
6. Enter a reviewer name, confirm the checks, and use **Approve & export** to save Word or Markdown. **Save draft** works without approval and retains a draft label.
7. Open **Data assistant** and click a suggested question to show an answer grounded in the active scope.

Use **Load demo** to return to the included file. **New sample** generates a reproducible 500-response scenario. **Open CSV** loads a compatible local export. Keep the included data for a predictable presentation.

## Interface and workflow

- Navy navigation sidebar, consistent typography, teal actions and clear page descriptions.
- Metric cards, proportional rating bars and an evidence summary.
- Search across all selected responses, striped data rows, full response detail and quality warnings.
- Selectable themes with keyword and comment evidence.
- Formatted report preview, editable drafts, named review, Word/Markdown export.
- Background analysis, progress indicator, friendly failures and disabled actions while processing.
- Unsaved-report protection and review confirmation reset after editing.

The preview displays at most 1,000 matching rows; analysis and search include every row in the selected scope. Changing data or scope clears old drafts after warning about unsaved work. Invalid files preserve the prior workspace. Ctrl+O opens a CSV.

## Scope and limitations

The desktop UI uses local deterministic analysis; it does not call external AI providers. Pattern masking needs human checking. Themes are indicators and recommendations need review. Workspace state is in memory, so save before closing. Review names are entered by the operator, not authenticated identities.

Older architecture documents and unused UI helpers describe the previous prototype; their Streamlit instructions no longer apply. The desktop implementation is `src/ui/desktop.py`; `app.py` and `launch_demo.pyw` launch it. Existing ingestion, analytics, privacy and reporting modules are reused.

## Verification

Run `python -m pytest -q`. Desktop regression tests cover loading, navigation, searches beyond the preview limit, invalid files, scope changes, unsaved work, preview/edit behavior, approval and export, theme evidence and local Q&A. Desktop tests require an available Tk display.

## macOS display troubleshooting

For a grey or partially blank screen, use the [Mac recovery steps](TEAM_TESTING.md#macos-blank-or-grey-window). The app now checks the actual Tk runtime before drawing the interface, uses the system font, and displays only the selected page. Startup and callback errors are reported instead of silently leaving an incomplete window.

Run `python app.py --diagnose` to print the Python, Tcl/Tk and window-system versions without loading data. This release's compatibility changes were verified with Windows tests; the affected Mac must still be retested.

## Feedback and Docker distribution

Use the **Feedback & revisions** tab after generating a report. Preview before applying; every applied revision clears approval and can be undone. Offline edits are deterministic. Choose Azure AI for free-form instructions only after configuring the optional provider and approving external processing.

The [Docker guide](../DOCKER.md) explains how teammates can clone the repository and run the same Python desktop in a local browser using Docker Compose, without host Python/Tk setup.
