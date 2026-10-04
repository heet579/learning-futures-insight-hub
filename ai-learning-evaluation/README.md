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

## Application workflow

1. Launch the app. Cards show PENDING until you choose **Import CSV / Excel**. Import your survey files or `data/synthetic_qualtrics_evaluation.csv` for a demo, then review the response count, satisfaction, recommendation and completeness cards and rating chart.
2. Change the course scope and show how the dashboard updates.
3. In **Explore data**, switch to the **Survey data** tab, search for a response or phrase, and select a row to inspect its full masked content.
4. Open **Themes & evidence**, select a theme to show the supporting comments, or switch to **Ask a question** for a grounded local Q&A.
5. Open **Report studio**, choose facilitator or client and a draft provider (Local Analysis, or Claude/Azure OpenAI if configured — external providers need consent ticked), and click **Generate draft**. Switch between the reading preview and editable draft.
6. Enter a reviewer name, confirm the checks, and use **Approve & export** to save Word or Markdown. **Save draft** works without approval and retains a draft label. The **Evidence check** line next to the review checklist blocks approval if the draft contains a number or quote that doesn't match the analysed data.
7. In **Feedback & revisions**, request changes via the local assistant, Copilot hand-off, or the same Claude/Azure OpenAI providers.

The application starts empty, even when `data/client/` or `EVALUATION_DATA_PATH` is configured. **Import CSV / Excel** (Ctrl+O) accepts one or more compatible survey files and replaces the active dataset after validation. A bold uppercase filename beside the import button identifies the selected file during processing and after loading; multiple imports also show the additional file count. See [data requirements](data/README.md) and [column definitions](docs/data_dictionary.md). Synthetic records remain identified by the source filename when explicitly imported.

## Interface and workflow

- Purple/white navigation sidebar (3 sections: Explore data, Themes & evidence, Report studio), consistent typography, clear page descriptions.
- Metric cards, proportional rating bars and an evidence summary.
- Search across all selected responses, striped data rows, full response detail and quality warnings.
- Selectable themes with keyword and comment evidence.
- Formatted report preview, editable drafts, named review, Word/Markdown export.
- Background analysis, progress indicator, friendly failures and disabled actions while processing.
- Unsaved-report protection and review confirmation reset after editing.

The preview displays at most 1,000 matching rows; analysis and search include every row in the selected scope. Changing data or scope clears old drafts after warning about unsaved work. Invalid files preserve the prior workspace. Ctrl+O opens a CSV.

## Scope and limitations

Initial reports default to local deterministic analysis; Claude or Azure OpenAI can be selected instead (or for feedback revisions) once configured, with explicit per-use consent. Feedback revisions can also use offline edits or human-supplied wording (e.g. via Copilot). Pattern masking needs human checking. Themes are indicators and recommendations need review. Workspace state is in memory, so save before closing. Review names are entered by the operator, not authenticated identities.

Older architecture documents and unused UI helpers describe the previous prototype; their Streamlit instructions no longer apply. The desktop implementation is `src/ui/desktop.py`; `app.py` and `launch_app.pyw` launch it. Existing ingestion, analytics, privacy and reporting modules are reused.

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

Use the **Feedback & revisions** tab after generating a report. Preview before applying; every applied revision clears approval and can be undone. Local feedback edits are deterministic. For Copilot, enter your requested changes and click **Open Copilot with prompt**. The app copies a privacy-minimised prompt and opens Microsoft Copilot; paste the Copilot answer into **Replacement section**, then preview and apply it before exporting. Choose Azure AI for free-form instructions only after configuring the optional provider and approving external processing.

The [Docker guide](../DOCKER.md) explains how teammates can clone the repository and run the same Python desktop in a local browser using Docker Compose, without host Python/Tk setup.
