# Code map: where each screen and feature lives

All paths are inside `ai-learning-evaluation/`. Search for the function name; line numbers change too often to list.

## Start-up

| What | File | Key functions |
|---|---|---|
| Entry point | `app.py`, `launch_app.pyw` | call `src.ui.runtime.main()` |
| Tk checks, `.env` loading, `--diagnose` | `src/ui/runtime.py` | `launch`, `check_tk_version`, `runtime_details` |
| Sign-in screen and workspace access gate | `src/ui/login.py`, `src/ui/runtime.py` | `LoginScreen`, `open_workspace` |
| Editable text accounts and administrator commands | `src/auth.py`, `config/users.txt` (local, ignored) | `authenticate`, `read_users`, `add_user`, `main` |
| Main window, sidebar, toolbar, page switching | `src/ui/desktop.py` | `DesktopApp.__init__`, `shell`, `styles`, `navigate`, `sync_controls` |
| Colours | `src/ui/theme.py` | constants |
| Product wording in error dialogs | `src/ui/wording.py` | `service_message`, `REVISION_MODES` |

`DesktopApp` is one window built from four mixin classes: `ReviewUI` (review gates), `RevisionUI` (feedback and revisions), `InsightsUI` and `QuestionsUI`.

## Page 01 · Explore data

| Tab / feature | File | Key functions |
|---|---|---|
| Import CSV / Excel, file badge, background loading | `src/ui/desktop.py` | `open_file`, `load`, `apply_analysis` |
| Overview cards, rating bars, "At a glance", quality line | `src/ui/desktop.py` | `build_overview`, `draw_chart`, `apply_analysis` |
| Survey data table, search, row detail | `src/ui/desktop.py` | `build_data`, `queue_search`, `filter_rows`, `inspect_row` |
| Insights & suggestions tab (local overview + Get insights) | `src/ui/insights.py` | `build_insights`, `show_local_insights`, `generate_insights` |

## Page 02 · Themes & evidence

| Tab / feature | File | Key functions |
|---|---|---|
| Theme list and comment detail | `src/ui/desktop.py` | `build_themes`, `inspect_theme` |
| Gate 1: confirm / re-categorise / reject, reviewer name | `src/ui/review.py` | `build_theme_review_controls`, `confirm_theme`, `reject_theme`, `reviewer_name`, `theme_detail_text` |
| Ask a question tab | `src/ui/desktop.py` (`build_assistant`) and `src/ui/questions.py` (`ask`) | |

## Page 03 · Report studio

| Tab / feature | File | Key functions |
|---|---|---|
| Get Gemini draft (local fallback) | `src/ui/desktop.py` | `generate`, `_apply_generated_report` |
| Edit draft and Reading preview tabs | `src/ui/desktop.py` | `build_report`, `edited`, `refresh_preview`, `update_evidence_check` |
| Feedback & revisions tab (Ask Gemini, offline edits, manual) | `src/ui/revisions.py` | `build_revision_ui`, `propose_feedback`, `apply_feedback`, `undo_revision` |
| Review claims tab (Gates 2 and 3) | `src/ui/review.py` | `build_claims_tab`, `refresh_claims`, `inspect_claim`, `accept_claim`, `reject_claim` |
| Human review panel (Gates 4–6) | `src/ui/review.py` | `build_review_panel`, `update_review_panel`, `submit_for_approval`, `return_for_changes`, `approval_problems` |
| Approve & export, Save draft | `src/ui/desktop.py` | `export` |

## Logic behind the screens (no Tkinter)

| Area | File | What it does |
|---|---|---|
| Reading files | `src/ingestion/qualtrics_loader.py` | Qualtrics header handling, question-text mapping, Likert → 1–5, recommend score → Yes/No, course from filename |
| Validation | `src/ingestion/validator.py` | Missing columns (errors) and data-quality warnings |
| Masking | `src/privacy/pii_masker.py` | Email, phone and URL patterns |
| Metrics | `src/analytics/quantitative.py` | Means, distributions, satisfaction, recommend, completeness |
| Themes | `src/analytics/themes.py`, `src/analytics/qualitative.py` | Keyword rules plus TF-IDF/NMF emerging topics |
| Fact sheet for AI | `src/ai/insights.py` | ID-tagged facts, local overview, insights rendering |
| Gemini | `src/ai/gemini_provider.py` | Insights, answers, section rewrites; JSON schema and evidence-ID validation |
| Local draft wording | `src/ai/local_provider.py` | Fixed-wording summary and recommendations |
| Optional providers | `src/ai/azure_provider.py`, `src/ai/anthropic_provider.py`, `src/ai/base_provider.py` | Not used by the current screens |
| Report template | `src/reporting/report_generator.py` | 13-section draft, approval wording |
| Revisions | `src/reporting/revisions.py` | Section bounds, offline edits, Gemini rewrite, apply/undo rules |
| Evidence check | `src/reporting/grounding.py` | Figures and quotes vs calculated data, rounding-aware |
| Word / Markdown export | `src/reporting/exporter.py` | `docx_bytes`, `markdown_bytes` |
| Gate 1 logic | `src/review/themes.py` | `ThemeReview`, `matched_keywords` |
| Gates 2, 3, 5 logic | `src/review/claims.py` | `extract_claims`, `ClaimLedger`, `remove_claim`, `possible_names`, `ai_text_retained` |
| Gate 4 logic | `src/workflow.py` | `ReviewWorkflow`: submit, return, approve, reopen |
| Gate 6 logic | `src/audit/logger.py`, `src/review/record.py` | `AuditTrail` hash chain; Review record page |
| Shared data classes | `src/models.py`, `src/config.py` | `AnalysisContext`, `Theme`, `ReportDraft`; required columns |

## Tests

`tests/` mirrors the modules above. `tests/test_desktop.py` drives the real window; `tests/test_review.py` covers the gates without a window.
