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

