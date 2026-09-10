# Two-week delivery plan — five-person team

## Goal and delivery boundary

Deliver a working learning-evaluation application: import Qualtrics feedback through an API or CSV, validate and mask it, persist the processed data, calculate metrics and themes, generate evidence-backed facilitator/client reports, and require human review before approved export.

Deliver the same application in two forms: a hosted web app and a local Docker installation opened in a browser. This plan treats “software” as a locally installable application, not a separate native Windows executable. A native installer is a later milestone if required.

Assume ten working days, five available team members, and reuse of the existing Python/Streamlit prototype. This is a tested capstone MVP, not a complete enterprise production rollout. Obtain approved Qualtrics sandbox credentials, a representative survey schema, approved AI credentials if needed, and a hosting destination on day 1. Use synthetic data until real-data access and handling are approved.

## Proposed architecture

- Streamlit: simple login, import, job status, dashboard, evidence, report editing, approval and download screens.
- FastAPI: authenticated backend contracts for imports, jobs, datasets, analysis and report versions.
- PostgreSQL: users/roles, imports, masked responses, metrics, report versions, job status and audit metadata.
- Python worker: durable database-backed job queue for ETL and report generation; bounded retries and safe recovery after restart.
- Existing Python modules: validation, masking, metrics, themes, providers and DOCX export, moved behind backend services.
- Docker Compose: UI, API, worker and database, with persistent volumes and health checks. A hosted reverse proxy provides HTTPS; local deployment binds to localhost by default.
- Qualtrics connector: request export, poll completion, download and map responses. Keep CSV import available.
- AI provider: retain the deterministic offline mode; optionally use the configured approved provider with masked evidence only. Clearly display active mode and provider failures.

Pipeline: API/CSV → restricted temporary staging → mapping/validation → reject or quarantine invalid records → PII masking → transactional load → metrics/themes → draft reports → human review → approved export.

Use survey ID + response ID for source identity, and source hashes/version metadata for repeat-import detection. Re-importing unchanged data must not duplicate records or reports. Record source question/scale metadata; compare courses only when their surveys are confirmed comparable. Delete temporary raw files after processing according to the agreed retention policy; never put tokens or raw comments into logs.

## Ownership

| Person | Primary ownership | Required deliverables | Reviewer |
|---|---|---|---|
| Heet | Architecture, backend foundation, Docker and integration | API contracts, authentication/roles, Compose stack, deployment, integrated demo | Gopi |
| Gopi | Qualtrics/CSV ingestion, ETL and database | Connector, mappings, migrations, worker, deduplication, retries, import tests | Heet |
| Zhongyi | Analytics, AI and reporting | Reused metrics/themes, evidence references, provider integration, versioned drafts and exports | Esrat |
| Xinling | UI and user journey | API-connected screens, progress/errors, report editor and approval UX, browser QA | Heet |
| Esrat | Test data, independent QA, privacy and handover | Fixtures, acceptance checks, privacy/grounding evidence, UAT, installation/user guides | Zhongyi |

Owners implement their packages and tests; Esrat coordinates independent verification rather than carrying all testing alone.

## Daily execution

| Day | Heet | Gopi | Zhongyi | Xinling | Esrat | Exit condition |
|---|---|---|---|---|---|---|
| 1 | Freeze scope, architecture and API contracts; record baseline test results | Inspect source schema; design database and request API access | Inventory reusable analytics/report code; define evidence contracts | Sketch the minimum screens and full user journey | Define acceptance cases, synthetic fixtures and access/retention checklist | Agreed contracts, owners, fixtures and dependency deadlines |
| 2 | Scaffold API, configuration, authentication and Compose | Create migrations, import/job tables and CSV ingestion service | Extract analytics/report services from UI dependencies | Build login/import/status screens against agreed mock responses | Add malformed, missing-field, duplicate and PII fixtures | Local stack starts; initial API and database work |
| 3 | Enforce roles and authenticated resource access | Implement worker, validation, masking and transactional load | Connect metrics/themes with stored evidence identifiers | Connect upload and job polling; show actionable errors | Verify metrics and masking; test access denial | CSV → stored masked dataset → analysis works end to end |
| 4 | Implement report/version/review API with Zhongyi | Implement Qualtrics export/poll/download/mapping and retry handling | Generate both draft types through provider boundary | Build dashboard and inspectable evidence views | Check API failures, schema changes and factual grounding | Analysis produces evidence-linked draft reports |
| 5 | Integrate and demonstrate week-one build | Add duplicate detection and job restart recovery | Add report edit/version/export service; test provider failure | Complete editor, review decisions and download flow | Execute first full acceptance run; log blockers | Import → draft → edit → approve → export works in Compose |
| 6 | Deploy hosted test instance with HTTPS and secrets | Complete approved live sandbox import if credentials exist | Validate approved AI provider if available; preserve offline mode | Improve validation messages, progress and navigation | Test hosted/local parity and browser compatibility | Hosted and local workflows usable; integration status documented |
| 7 | Harden sessions, health checks and restart behavior | Test interrupted imports, repeated imports and raw-file cleanup | Ensure edits invalidate approval; export only the approved version | Show version history, failed jobs and retry actions | Run privacy, permission and restart tests | No duplicate data, approval bypass or lost completed results |
| 8 | Resolve integration blockers; freeze features | Fix ETL defects and document mappings | Fix grounding/report issues and evaluate sample outputs | Run stakeholder UAT and fix usability blockers | Lead UAT, capture evidence and verify backup/restore | Agreed acceptance cases pass or have explicit recorded exceptions |
| 9 | Produce release candidate and install scripts | Verify migration, seed/demo data and recovery steps | Finalize report examples and provider configuration guide | Final UI smoke test and screenshots | Test fresh-machine setup; finish user/admin guides | Another person installs and runs the release from documentation |
| 10 | Tag release and lead final demo | Demonstrate live API/CSV ingestion and recovery | Demonstrate evidence, reports and approval behavior | Demonstrate complete user journey | Run final acceptance checklist and hand over results | Reproducible hosted/local release, demo and handover pack |

## Initial API contract

Freeze request/response models on day 1, including authentication, stable IDs, error shapes and permission rules.

- `POST /imports/csv` and `POST /imports/qualtrics`: enqueue an import and return a job ID.
- `GET /jobs/{id}`: stage, progress, safe error and retry status.
- `GET /datasets/{id}/analysis`: metrics, themes and evidence references.
- `POST /datasets/{id}/reports`: enqueue a draft for the selected audience.
- `GET /reports/{id}` and `PATCH /reports/{id}`: read/edit a version with a version check to prevent lost edits.
- `POST /reports/{id}/submit`, `/return`, `/approve`: authorized review transitions with reviewer identity and audit metadata.
- `GET /reports/{id}/export`: export the approved version; reject unapproved versions server-side.

## Acceptance criteria

1. A clean machine with Docker installed starts the stack using documented configuration and `docker compose up --build`; migrations and synthetic demo setup are documented.
2. Hosted and local editions complete the same workflow. Local offline mode works without external API credentials after images/dependencies are available.
3. CSV import always works. Live Qualtrics integration is accepted only after a successful authorized sandbox import; otherwise it is clearly recorded as unverified, with mocked contract tests and the access blocker documented.
4. Invalid files produce clear errors; repeated imports do not duplicate data; failed jobs expose safe errors and retry without corrupting completed work.
5. Planted PII fixtures are masked before analytics or external AI calls. Logs exclude secrets and raw responses. Pattern masking limitations remain disclosed.
6. Metrics match manually calculated fixtures. Sample report claims trace to dataset metrics or identifiable evidence; target at least 95% sampled factual traceability, subject to stakeholder agreement.
7. Both report audiences are supported. Drafts are visibly marked, approval is enforced by the API, and editing an approved report creates an unapproved version.
8. Completed imports and reports survive a restart; a backup can be restored; unauthorized users cannot import, approve or access another user's restricted resources.
9. Test 500 and 10,000 synthetic responses, recording runtime and memory on the demo machine. Set the performance budget on day 1 after measuring the baseline; the UI must remain responsive during processing.
10. Final handover includes source, configuration example without secrets, migrations, tests/results, deployment/install instructions, user guide, demo script and known limitations.

## Coordination and scope control

Daily: 15-minute stand-up, small pull requests, one reviewer per change, and integration into a working main branch. Run relevant unit tests and an import-to-export smoke test in CI. Reserve days 8–10 for acceptance, fixes and release; no new features after day 7.

If API access is unavailable by day 2, continue connector development against fixtures and deliver CSV as the working ingestion path. Do not call the live integration complete. If time slips, defer scheduled imports, conversational Q&A, advanced dashboards and visual polish before cutting ETL reliability, persistence, approval enforcement or basic security.

Out of scope for this fortnight: separate native desktop client, Kubernetes, enterprise SSO, full Microsoft Copilot/Teams/SharePoint/Power BI integrations, automatic report distribution and enterprise-grade anonymisation.
