# User guide

## Start

Run `./run_app.ps1` on Windows or follow the README manual commands. The app opens with the included synthetic file; no upload or credentials are required.

## Workflow

1. Import a Qualtrics-compatible CSV or retain the bundled synthetic file.
2. Select one course in **Analysis scope**. An all-course aggregate is allowed but is clearly labelled.
3. Review Data Quality errors/warnings and the counts of removed email, phone and URL patterns.
4. Check KPI calculations and valid response counts.
5. Inspect qualitative comments and expand every material theme to see evidence.
6. Choose Facilitator or Commercial client and generate a draft.
7. The generated report opens on **Edit draft**. Type directly into any part of the report; manual edits always clear prior approval.
8. In **Feedback & revisions**, select a section and enter feedback. Use the local assistant, or choose **Open Copilot with prompt**, paste the copied prompt into the approved Microsoft Copilot session, and paste its answer into **Replacement section**. Preview before applying. Azure AI remains optional and requires explicit confirmation.
9. Enter the reviewer name, verify the evidence/privacy/wording checklist, and explicitly confirm the review.
10. Export Markdown or DOCX. Draft exports retain their visible draft label.

## Invalid input

Missing required columns stop analysis with a plain-language list. Invalid dates, ratings, recommendation values, blank IDs and duplicates create warnings. Fix the source where possible; never suppress a warning simply to produce a report.

## Reviewer checklist

Reconcile response scope/counts; check every material claim; inspect disagreement and low-frequency concerns; remove contextual identifiers; confirm audience tone; assess indirect/cultural language; ensure recommendations are feasible and evidence-based; approve only when accountable for the result.
