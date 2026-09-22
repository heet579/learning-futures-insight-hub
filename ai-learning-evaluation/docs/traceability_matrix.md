# MVP traceability matrix

| Requirement | Implementation | Verification |
|---|---|---|
| CSV ingestion and graceful errors | `src/ingestion` | `test_ingestion.py` |
| Real PACE/Qualtrics export mapping (question-text based, identifier columns dropped) | `src/ingestion/qualtrics_loader.py::load_qualtrics_export/_folder` | `test_qualtrics_real_export.py` |
| Missing/invalid data warnings | validator + Data Quality tab | ingestion tests + manual malformed upload |
| Privacy preprocessing | `src/privacy` before analytics | `test_privacy.py` |
| Quantitative KPIs/distributions | `src/analytics/quantitative.py` | golden metrics test |
| Themes with evidence | theme rules + TF-IDF/NMF + expanders | `test_themes.py` + visual QA |
| Grounded reports | `AnalysisContext` and provider interface | reporting tests |
| Automated claim-evidence check, approval blocked on unsupported claims | `src/reporting/grounding.py`, gated in `DesktopApp.export` | `test_grounding.py`, `test_approval_refused_when_draft_has_fabricated_claim` |
| Facilitator/client difference | audience templates and disclosure | reporting tests |
| Human review | visible editable draft, feedback preview/apply/undo, named reviewer, confirmation, approval | revision/reporting tests + UI walkthrough |
| Markdown/DOCX export | `src/reporting/exporter.py` | export signature test |
| Auditability | metadata-only JSONL events | `test_audit.py` |
| Local/no-credential mode | `LocalAnalysisProvider` default | end-to-end smoke test |
| Copilot structured prompting | privacy-minimised copied prompt, approved external Copilot session, pasted replacement with preview | revision tests + UI walkthrough |
| Optional approved provider | explicit UI consent + minimised Azure payload | configuration/manual integration test required |
| Presentation/handover | `docs/` pack and sample reports | team rehearsal checklist |
