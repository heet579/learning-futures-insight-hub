# Requirements and evaluation framework

## Must-have acceptance requirements

1. Load a representative CSV and report missing required columns without crashing.
2. Mask obvious PII patterns before analysis and disclose limitations.
3. Correctly calculate response, completeness, rating, satisfaction and recommendation metrics.
4. Identify explainable themes and retain supporting comments.
5. Generate distinct facilitator/client reports with required sections and evidence.
6. Mark every initial report `DRAFT — REQUIRES HUMAN REVIEW`.
7. Let staff edit, explicitly confirm review, approve and export.
8. Record timestamp, filename, count, audience, mode and review status without raw comments.

## Prototype evaluation framework

| Dimension | Check | Evidence |
|---|---|---|
| Data accuracy | Golden manual calculations match output | pytest metrics fixture |
| Grounding | Sample every material claim to a metric/theme/comment | report review checklist |
| Relevance | Facilitator/client reviewers rate usefulness | 1–5 stakeholder rubric |
| Consistency | Same input preserves report structure | deterministic tests |
| Clarity | Reviewer can understand findings/actions | UAT questionnaire |
| Privacy | Planted PII absent after masking/reporting | privacy tests + manual scan |
| Human acceptance | Edit and explicit approval work | demo/UAT evidence |

Proposed targets from the approved scope (including >=95% sampled factual traceability and median >=4/5 reviewer clarity/relevance) remain subject to client confirmation.

## Final Non-Functional Requirements Baseline

Implementation and validation are reported separately below. A feature being present or covered by automated tests does not mean that Learning Futures has accepted it. Existing proposed targets above are not approved acceptance thresholds; unresolved thresholds remain **TBC with stakeholder**. NFR-02 applies only to supported and approved report types. A Learning Futures program-level report remains separate functional scope unless it is explicitly agreed.

### NFR-01 Accuracy / Groundedness

- **Final Requirement:** Material report findings must be supported by source evidence and checked before approval across the desktop and browser workflows.
- **Acceptance Criteria:** Calculated metrics match reference data; unsupported figures, quotes and evidence references block approval; CLEAR review exposes the evidence needed to challenge material claims; and a recorded sample of material factual claims traces to metrics or reviewed comments. The sampled traceability threshold is **TBC with stakeholder**.
- **Test Method:** Golden-data calculations, invalid or unsupported evidence tests, CLEAR workflow tests, fixed-data report inspection, and documented human sampling of material claims.
- **Implementation Status:** Partially Implemented — metrics are calculated in Python; generated claims cite fact IDs; grounding checks reject unknown figures, quotes and evidence IDs; and CLEAR Check plus the second-reviewer gate require review before approval. Relevant implementation and tests are in `src/analytics/`, `src/reporting/grounding.py`, `src/review/`, `src/storage/reports.py`, and `tests/test_grounding.py` / `tests/test_review*.py`.
- **Validation Status:** Automated metric, grounding and CLEAR checks run in the test suite and CI. Stakeholder acceptance of the sampling method, threshold and representative reviewed outputs is pending.
- **Remaining Gap:** Automated grounding cannot establish that every supported statement is a fair interpretation or that every material omission has been identified. No stakeholder-approved claim-sampling result is recorded.

### NFR-02 Consistency

- **Final Requirement:** Supported and approved stakeholder-specific report types must preserve their agreed structure, terminology, metric definitions, review rules and audience boundaries across local, Gemini-assisted, desktop and browser paths.
- **Acceptance Criteria:** Each supported and approved report type retains its required sections, evidence rules, audience boundaries and metric definitions on repeated generation; desktop and browser approval paths apply the same CLEAR and second-reviewer rules; stakeholder-approved examples define acceptable wording variation.
- **Test Method:** Template and workflow regression tests, repeated generation from fixed data, desktop/API/browser-path comparison, and stakeholder review of representative outputs for each supported type.
- **Implementation Status:** Partially Implemented — facilitator and client reports use shared reporting and review modules, fixed structural expectations, common CLEAR validation and persistent report workflow rules. Automated reporting, API, desktop and review tests cover both audiences and multiple generation paths.
- **Validation Status:** Structural and workflow regressions are automated. Approval of report templates, terminology, tone and acceptable wording variation is pending.
- **Remaining Gap:** Generated wording can vary, and no stakeholder-approved reference set exists for each audience and generation mode. Program-level reporting remains a separate functional scope decision.

### NFR-03 Privacy

- **Final Requirement:** Process only necessary data; PII, Gemini and Google transfers, browser/API traffic, Render/Neon storage, logs, exports, backups and retention must follow approved data-handling controls.
- **Acceptance Criteria:** An approved data-flow record identifies permitted fields, services, environments and storage locations; test payloads, logs, audit events and exports contain no prohibited content or credentials; access, retention, deletion and backup rules are documented and approved.
- **Test Method:** Planted-PII tests, Gemini request inspection, API/log/export/audit scans, database field review, deployment configuration review, and data-owner review of Render, Neon and Google use.
- **Implementation Status:** Partially Implemented — PII masking covers configured email, Australian phone and URL patterns; Gemini receives constrained calculated evidence and masked revision text; secrets and client data paths are ignored by Git; shared data is stored through the FastAPI service in Neon Postgres; and provider calls are isolated from automated tests.
- **Validation Status:** Privacy and data-boundary tests run in CI. Approval of external services, permitted payloads, production datasets, retention/deletion, backup handling and data-owner review is pending.
- **Remaining Gap:** Pattern masking can miss names and contextual identifiers. User-entered instructions, review notes and imported content still require governance, and the repository does not establish stakeholder-approved retention or deletion periods.

### NFR-04 Security / Authentication / Credential Protection

- **Final Requirement:** Desktop, browser and FastAPI paths must authenticate users, enforce the approved role and report-assignment boundaries, protect credentials and deployment secrets, and preserve independent author/second-reviewer accountability.
- **Acceptance Criteria:** Passwords are never stored or returned in readable form; tokens and Google identities are verified server-side; disabled, deleted or demoted accounts cannot retain protected access; only superadmins can manage accounts; report actions use the authenticated identity; the author cannot approve their own report; secrets remain outside source, logs and exports; and the deployed environment and role matrix are approved.
- **Test Method:** Authentication and credential tests, protected-route and role-boundary tests for all five roles, stale-token/demotion tests, self-action and last-superadmin protection tests, author/second-reviewer workflow tests, secret/configuration review, and deployment security review.
- **Implementation Status:** Partially Implemented — local and shared passwords use salted PBKDF2-HMAC-SHA256 hashes; FastAPI issues signed bearer tokens and rechecks current account state; Google ID tokens are verified; five roles (`member`, `admin`, `facilitator`, `client`, `superadmin`) are supported; superadmin-only account management is enforced transactionally; and signed-in author and second-reviewer identities are used in report workflow and audit records.
- **Validation Status:** Automated authentication, account, API-boundary, superadmin, browser-permission and workflow tests run in CI. Formal security review, deployment approval and stakeholder confirmation of the final role/assignment matrix are pending.
- **Remaining Gap:** The prototype has no recorded independent penetration test or production security acceptance. Requirements for MFA, token/session lifetime and revocation policy, rate limiting, recovery, monitoring and incident response remain **TBC with stakeholder**.

### NFR-05 Usability

- **Final Requirement:** A Learning Futures user without specialist AI knowledge must be able to complete the supported import, analysis, drafting, CLEAR review, second-reviewer and export workflow in the desktop or browser interface appropriate to their role.
- **Acceptance Criteria:** Target users can complete agreed tasks, understand draft and approval status, identify what CLEAR requires, recover from validation and service errors, and distinguish author, reviewer, admin and superadmin actions. Acceptable completion and clarity criteria are **TBC with stakeholder**.
- **Test Method:** Observed role-based stakeholder UAT on desktop and browser, including account administration and failure recovery, with issues, outcomes and retest results recorded.
- **Implementation Status:** Implemented for prototype workflows — desktop and browser interfaces provide signed-in, role-aware navigation; import and progress feedback; report drafting; CLEAR guidance; second-reviewer handoff; report library; profile controls; and superadmin account management.
- **Validation Status:** Automated desktop, API and browser regression checks cover key interactions. Formal Learning Futures stakeholder UAT across supported roles and devices is pending.
- **Remaining Gap:** Automated tests do not demonstrate user comprehension, efficient task completion or acceptable recovery from real deployment delays. No approved role-based UAT result is recorded.

### NFR-06 Maintainability

- **Final Requirement:** Active prompts, assumptions, data mappings, interfaces, deployment configuration, role rules and workflow steps must be documented, version controlled and kept aligned with the running system.
- **Acceptance Criteria:** Documentation matches active desktop, browser, API and deployment behaviour; shared business rules are not inconsistently duplicated; each output can identify relevant model/prompt and mapping versions; changes receive regression review in CI.
- **Test Method:** Code-to-document comparison, prompt and mapping provenance inspection, API/workflow parity review, clean-environment setup review, and CI regression review.
- **Implementation Status:** Partially Implemented — analytics, reporting and CLEAR rules are shared across interfaces; architecture, deployment, browser, superadmin, data and testing guides are version controlled; and the automated suite covers desktop, SQLite, FastAPI, browser checks and disposable Postgres.
- **Validation Status:** GitHub Actions runs Linux tests with SQLite and Postgres and exercises the Windows test launcher; JSON and JUnit evidence is retained by CI. A formal documentation-alignment and maintainability review is pending.
- **Remaining Gap:** Runtime outputs do not carry complete prompt/model/mapping version provenance, and documentation can drift as the prototype changes. Operational ownership and change-control expectations are not stakeholder-approved.

### NFR-07 Transparency / Human Oversight

- **Final Requirement:** AI-assisted content, supporting evidence, limitations, review decisions and approval state must be identifiable; authorised humans must be able to challenge, revise, return or remove recommendations before release.
- **Acceptance Criteria:** Reviewers can distinguish draft from approved content, inspect cited evidence and limitations, complete CLEAR questions, record caveats or concerns, return an unsuitable report, and identify the author and independent second reviewer in the final review record.
- **Test Method:** Local and Gemini-assisted walkthroughs, CLEAR approve/return/concern cases, role and assignment tests, exported-report inspection, oversight-panel review, and stakeholder comprehension checks.
- **Implementation Status:** Partially Implemented — initial reports are marked as drafts; evidence and review states are exposed; CLEAR captures structured reviewer answers and caveats; reports can be revised or returned; second-reviewer approval is recorded; and the oversight view reports review activity and warning signals.
- **Validation Status:** CLEAR, handoff, reporting, API and oversight behaviours have automated coverage. Stakeholder comprehension and representative export review are pending.
- **Remaining Gap:** The clarity of AI-origin labels, limitations, evidence presentation and oversight signals has not been formally validated with target users across both interfaces and all output formats.

### NFR-08 Accessibility

- **Final Requirement:** The browser, desktop interface and exported reports must follow applicable, stakeholder-agreed accessible design principles. WCAG 2.2 AA is a proposed benchmark for the web interface, not a current conformance claim.
- **Acceptance Criteria:** The agreed checklist covers keyboard operation, focus order and visibility, labels, contrast, text resizing, perceivable errors, status announcements and exported-document structure. The benchmark, assistive technologies and pass criteria are **TBC with stakeholder**.
- **Test Method:** Keyboard-only and assistive-technology review, automated and manual web checks, desktop focus/error review, contrast and resizing checks, exported DOCX audit, and target-user testing.
- **Implementation Status:** Partially Implemented — both interfaces provide labelled controls and visible validation/status feedback, and DOCX exports use structured headings; the browser has responsive styling and the desktop exposes keyboard-supported actions.
- **Validation Status:** General UI regressions are tested, but no completed accessibility audit or conformance assessment is recorded.
- **Remaining Gap:** No current WCAG conformance claim is supported. Screen-reader behaviour, keyboard coverage, focus management, contrast, zoom/reflow and exported-document accessibility require formal assessment.

### NFR-09 Performance / Reliability

- **Final Requirement:** Representative local and shared report workflows must remain responsive and complete reliably under agreed data sizes, concurrency, network and Render/Neon operating conditions.
- **Acceptance Criteria:** Import, analysis, generation, API operations, report-library access, review, export, memory use, concurrency and recovery from service delay/failure are measured under documented conditions. Thresholds and service expectations are **TBC with stakeholder** after baseline measurement.
- **Test Method:** Repeatable stage-by-stage benchmarks, local versus Gemini/network timing, SQLite versus Neon tests, concurrent API scenarios, Render cold-start and failure-recovery checks, and end-to-end review-session timing.
- **Implementation Status:** Partially Implemented — desktop long-running work uses background execution; session data is cached; the FastAPI service uses pooled database access; remote Neon connections require TLS; and the suite exercises SQLite and disposable Postgres paths.
- **Validation Status:** Functional reliability is covered by automated tests and CI, but no stakeholder-approved performance, availability or capacity baseline is recorded.
- **Remaining Gap:** There are no recorded representative benchmarks or approved response-time, memory, concurrency, availability, backup/recovery or Render cold-start expectations.

### NFR-10 Auditability / Traceability

- **Final Requirement:** A report must be explainable through its source dataset, calculated evidence, report versions, generation method, authenticated actors, CLEAR decisions, second-reviewer outcome, timestamps and approval/export events without placing raw comments, credentials or secrets in the audit record.
- **Acceptance Criteria:** An approved export can be reconstructed through import, generation, revision, submission, CLEAR review, return/approval and source evidence; account and role-management actions are attributable; persistent records survive restart; audit integrity and sensitive-data checks pass.
- **Test Method:** End-to-end provenance reconstruction after restart, report-version and actor checks, CLEAR/review-record inspection, account-action audit tests, audit-chain tamper tests, and sensitive-content scans across SQLite and Postgres.
- **Implementation Status:** Partially Implemented — the report library persists report versions and workflow state; authenticated author and reviewer identities, CLEAR answers and approval records are stored; account changes are audited; and the audit logger uses a hash chain. Shared deployments persist reports and audit data in Neon through FastAPI.
- **Validation Status:** Audit, report-library, handoff, API and Postgres tests cover significant parts of the chain. Complete stakeholder-reviewed output provenance and operational audit validation are pending.
- **Remaining Gap:** Complete prompt/model/mapping version identifiers and a formally validated dataset-to-export reconstruction are not recorded for every path. Retention, access to audit records, backup/recovery and operational monitoring rules remain unapproved.

## Stakeholder Decisions Pending

1. Approve report structure, terminology, tone and representative examples for each supported stakeholder-specific type; confirm program-level reporting separately as functional scope.
2. Confirm the factual-grounding sampling method and threshold: **TBC with stakeholder**.
3. Approve permitted datasets and fields, Gemini and Google use, Render/Neon hosting, storage locations, backups, and retention/deletion rules.
4. Confirm the production role and assignment matrix for member, facilitator, client, admin and superadmin accounts, including second-reviewer independence and who may approve each audience's reports.
5. Confirm authentication and operational security expectations, including whether MFA, session controls, rate limiting, security monitoring, recovery and incident response are required for the intended deployment.
6. Agree on UAT participants, supported devices/browsers and usability success criteria: **TBC with stakeholder**.
7. Approve the applicable browser, desktop and export accessibility benchmark, assistive technologies and pass criteria.
8. Agree on representative data sizes, concurrency, deployment conditions and performance/reliability targets after baseline measurement: **TBC with stakeholder**.
9. Approve audit access, retention, backup/recovery and required prompt/model/mapping provenance for released reports.

## NFR Follow-up Validation

- Review fixed-data facilitator and client reports across local/Gemini and desktop/browser paths for factual grounding, structure, terminology, audience suitability, AI-origin disclosure and recommendation traceability (NFR-01, NFR-02, NFR-07).
- Inspect Gemini/Google requests, FastAPI traffic, logs, exports, credential handling, role enforcement and approved Render/Neon data flows using synthetic or explicitly approved fixtures (NFR-03, NFR-04).
- Run role-based Learning Futures UAT and the agreed browser, desktop and export accessibility assessment (NFR-05, NFR-08).
- Record repeatable local and shared stage timings, memory, concurrency, UI responsiveness, Render/Neon conditions and recovery outcomes before seeking agreement on a performance budget (NFR-09).
- Reconstruct one complete report history after restart, including source evidence, report versions, generation provenance, CLEAR answers, second-reviewer identity, approval/export events and audit-chain integrity (NFR-06, NFR-10).

