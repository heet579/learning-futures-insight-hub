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

The implementation and validation statuses below are separate. Existing proposed targets above are not approved acceptance thresholds; unresolved thresholds are **TBC with stakeholder**. NFR-02 applies to supported and approved report types. A Learning Futures program-level report is not yet implemented and is a separate functional scope gap, not an NFR-02 acceptance failure.

### NFR-01 Accuracy / Groundedness

- **Final Requirement:** Material report findings must be supported by source evidence and checked before approval.
- **Acceptance Criteria:** Calculated metrics match reference data; unsupported figures and quotes block approval; a recorded sample of material factual claims traces to metrics or reviewed comments. The sampled traceability threshold is **TBC with stakeholder**.
- **Test Method:** Golden-data calculations, unsupported-claim tests, and documented human sampling of report claims.
- **Implementation Status:** Partially Implemented — metrics, evidence-ID checks, limited figure/quote grounding, and review gates exist in `src/analytics/quantitative.py`, `src/ai/gemini_provider.py`, `src/reporting/grounding.py`, and `src/ui/review.py`.
- **Validation Status:** Automated checks exist; stakeholder acceptance of claim sampling and threshold is pending.
- **Remaining Gap:** Automated grounding does not assess every interpretation or whether a supported number is attributed to the correct metric; no approved sampling result is recorded.

### NFR-02 Consistency

- **Final Requirement:** Supported and approved stakeholder-specific report types must follow their agreed structure, terminology, metric definitions, and tone across runs.
- **Acceptance Criteria:** Each supported and approved type retains its required sections, audience boundaries, and metric definitions on repeated generation; stakeholder-approved examples define acceptable wording variation.
- **Test Method:** Template regression tests, repeated generation from fixed data, and stakeholder review of representative outputs for each supported type.
- **Implementation Status:** Partially Implemented — `src/reporting/report_generator.py` uses a fixed structure for the currently supported facilitator and client audiences.
- **Validation Status:** Approval of report templates, terminology, and acceptable variation is pending.
- **Remaining Gap:** Generated wording consistency and approved audience-specific baselines have not been established. Program-level reporting remains a separate functional development item when its scope is confirmed.

### NFR-03 Privacy

- **Final Requirement:** Process only necessary data; PII, Gemini transfers, logs, exports, and retention must follow approved data-handling controls.
- **Acceptance Criteria:** Approved data-flow rules identify permitted fields and services; test payloads, logs, and exports contain no prohibited content; retention and deletion rules are documented and approved.
- **Test Method:** Planted-PII cases, intercepted Gemini request inspection, log/export scans, and data-owner review.
- **Implementation Status:** Partially Implemented — `src/privacy/pii_masker.py` masks email, Australian phone, and URL patterns; `src/ai/insights.py` limits insight evidence to calculated facts and fixed theme counts; `src/ai/gemini_provider.py` masks section text and instructions for revisions.
- **Validation Status:** Approved service, payload, and retention boundaries and a data-owner review are pending.
- **Remaining Gap:** Pattern masking can miss names and contextual identifiers; a revised section or user instruction can contain details not caught by the patterns. Audit notes also need inspection for sensitive content.

### NFR-04 Security

- **Final Requirement:** This semester PoC must use an approved environment, protect secrets and project data, follow approved data handling, and separate report author and approver roles where Learning Futures confirms that workflow requirement.
- **Acceptance Criteria:** The PoC environment and data handling are approved; secrets are absent from source, logs, and exports; if author/approver separation is confirmed, the same named person cannot approve their own report. Production-grade authentication or RBAC is not a mandatory MVP criterion unless separately agreed.
- **Test Method:** Environment approval record, secret/configuration review, and author/approver workflow tests.
- **Implementation Status:** Partially Implemented — `src/workflow.py` enforces different entered names for author and approver; `.gitignore` excludes local secrets and client data; Docker binds to localhost and runs as a non-root user.
- **Validation Status:** Environment and data-handling approval, and stakeholder confirmation of role separation, are pending.
- **Remaining Gap:** Entered names are not authenticated identities; any requirement for authenticated access or RBAC belongs to a later stakeholder decision.

### NFR-05 Usability

- **Final Requirement:** A Learning Futures user without specialist AI knowledge must be able to understand and complete the reporting workflow.
- **Acceptance Criteria:** Target users can complete the agreed import, analysis, drafting, review, and export tasks; acceptable completion and clarity criteria are **TBC with stakeholder**.
- **Test Method:** Observed task-based stakeholder UAT with issues, outcomes, and retest results recorded.
- **Implementation Status:** Implemented for the current Tkinter workflow — navigation, progress, errors, and review guidance exist in `src/ui/desktop.py` and `src/ui/review.py`; the Tkinter UI has been successfully launched and inspected on macOS.
- **Validation Status:** Formal Learning Futures stakeholder UAT is pending.
- **Remaining Gap:** Target users have not yet validated workflow comprehension and usability against agreed criteria.

### NFR-06 Maintainability

- **Final Requirement:** Active prompts, assumptions, data mappings, and workflow steps must be documented, version controlled, and kept aligned with the running system.
- **Acceptance Criteria:** Documentation matches active code; each output can identify the prompt and mapping versions used; changes receive regression review.
- **Test Method:** Code-to-document comparison, version/provenance inspection, and change-regression review.
- **Implementation Status:** Partially Implemented — mappings, assumptions, workflow documentation, and prompt files are in the repository, but the active Gemini prompts are constructed in `src/ai/gemini_provider.py`.
- **Validation Status:** Documentation alignment and version traceability review are pending.
- **Remaining Gap:** Runtime prompt versions are not recorded, and some project documents need reconciliation with the current implementation.

### NFR-07 Transparency

- **Final Requirement:** AI-assisted content, supporting evidence, limitations, and review status must be identifiable; recommendations must remain open to challenge, editing, or removal.
- **Acceptance Criteria:** Reviewers can identify content source, inspect cited evidence and limitations, and accept, revise, or remove recommendations; exports distinguish drafts from approved reports.
- **Test Method:** Local, Gemini, and revised report walkthroughs; exported-report inspection; user comprehension checks.
- **Implementation Status:** Partially Implemented — `src/reporting/report_generator.py` labels draft status and analysis method; `src/review/claims.py` and `src/ui/review.py` support source/evidence inspection and claim decisions.
- **Validation Status:** Stakeholder comprehension and export review are pending.
- **Remaining Gap:** Clarity of AI-origin labels and limitations across all report and revision paths has not been formally validated.

### NFR-08 Accessibility

- **Final Requirement:** The desktop PoC and exported reports must follow applicable, stakeholder-agreed accessible design principles. WCAG 2.2 AA is a proposed benchmark for any future web interface, not a claim of current Tkinter conformance.
- **Acceptance Criteria:** The agreed desktop/export checklist covers keyboard operation, focus, readable text, perceivable errors, and document structure; the checklist and any pass criteria are **TBC with stakeholder**.
- **Test Method:** Keyboard and assistive-technology review, contrast/error checks, exported-document audit, and user testing.
- **Implementation Status:** Partially Implemented — the Tkinter UI uses labels and a file-open shortcut; `src/reporting/exporter.py` creates structured DOCX headings.
- **Validation Status:** The desktop accessibility checklist has not been agreed or formally tested.
- **Remaining Gap:** No current WCAG conformance claim or completed desktop/export accessibility audit is supported by evidence.

### NFR-09 Performance

- **Final Requirement:** A representative report-generation cycle must fit an acceptable review session on agreed data and equipment.
- **Acceptance Criteria:** Import, analysis, generation, export, memory use, and UI responsiveness are measured under documented conditions; all unconfirmed performance thresholds are **TBC with stakeholder** after benchmarking.
- **Test Method:** Repeatable stage-by-stage benchmarks, separating local processing from Gemini/network time, plus end-to-end review-session timing.
- **Implementation Status:** Partially Implemented — `src/ui/desktop.py` runs longer operations in a background worker; insight and question views use session caches.
- **Validation Status:** Representative benchmark results and an approved performance budget are pending.
- **Remaining Gap:** No measured baseline or stakeholder-approved time, memory, or responsiveness threshold is recorded.

### NFR-10 Auditability

- **Final Requirement:** An output must be explainable through its dataset, report and prompt/model versions, evaluation result, timestamps, and review/approval events without retaining raw comments or secrets in the audit record.
- **Acceptance Criteria:** An exported report can be traced through generation, revision, review, approval, and source dataset; version and evaluation references survive a restart; audit integrity and sensitive-data checks pass.
- **Test Method:** End-to-end provenance reconstruction, restart check, audit-chain tamper test, and audit-content scan.
- **Implementation Status:** Partially Implemented — `src/audit/logger.py` records timestamps and a hash-chained audit trail; `src/review/record.py` adds approval times and report/audit hashes to approved exports.
- **Validation Status:** Existing audit tests cover parts of the chain; complete output-provenance validation is pending.
- **Remaining Gap:** Persistent report versions, prompt versions, and complete dataset-to-output provenance are not implemented; in-memory revision history is not a persistent report version record.

## Stakeholder Decisions Pending

1. Approve report structure, terminology, tone, and examples for each supported stakeholder-specific type. Confirm program-level reporting separately as functional scope.
2. Confirm the factual-grounding sampling method and threshold: **TBC with stakeholder**.
3. Approve permitted datasets, Gemini use and payload limits, the PoC environment, data storage, and retention/deletion rules.
4. Confirm whether named author/approver separation is required for the PoC and whether authenticated access or RBAC is needed in later phases.
5. Agree on UAT participants and usability success criteria: **TBC with stakeholder**.
6. Approve the applicable desktop and export accessibility checklist; decide on a web benchmark only if a web interface is delivered.
7. Agree on representative data, equipment, and performance targets after baseline measurement: **TBC with stakeholder**.

## NFR Follow-up Validation

- Review fixed-data reports for factual grounding, structure, terminology, audience suitability, AI-origin disclosure, and recommendation traceability (NFR-01, NFR-02, NFR-07).
- Inspect Gemini requests, logs, exports, secret handling, role separation, and approved PoC data flows using synthetic and approved fixtures (NFR-03, NFR-04).
- Run Learning Futures task-based UAT and the agreed desktop/export accessibility audit (NFR-05, NFR-08).
- Record repeatable stage timings, memory, UI responsiveness, device/data conditions, and stakeholder acceptance of the resulting performance budget (NFR-09).
- Reconstruct one complete report history after restart; check dataset/output linkage, version identifiers, audit-chain integrity, and absence of raw comments or secrets (NFR-06, NFR-10).
