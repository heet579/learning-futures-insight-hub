# MVP traceability matrix

| Requirement | Implementation | Verification |
|---|---|---|
| CSV ingestion and graceful errors | `src/ingestion` | `test_ingestion.py` |
| Missing/invalid data warnings | validator + Data Quality tab | ingestion tests + manual malformed upload |
| Privacy preprocessing | `src/privacy` before analytics | `test_privacy.py` |
| Quantitative KPIs/distributions | `src/analytics/quantitative.py` | golden metrics test |
| Themes with evidence | theme rules + TF-IDF/NMF + expanders | `test_themes.py` + visual QA |
| Grounded reports | `AnalysisContext` and provider interface | reporting tests |
| Facilitator/client difference | audience templates and disclosure | reporting tests |
| Human review | editable draft, named role, confirmation, approval | reporting tests + UI walkthrough |
| Markdown/DOCX export | `src/reporting/exporter.py` | export signature test |
| Auditability | metadata-only JSONL events | `test_audit.py` |
| Local/no-credential mode | `LocalDemoProvider` default | end-to-end smoke test |
| Optional approved provider | explicit UI consent + minimised Azure payload | configuration/manual integration test required |
| Presentation/handover | `docs/` pack and sample reports | team rehearsal checklist |

