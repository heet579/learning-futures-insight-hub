# Jira backlog

Each story format is **Title — description** (owner; priority). Acceptance criteria follow.

## Epic 1 — Requirements & Discovery

**Validate survey/report baseline —** obtain anonymised export, data dictionary and current report examples (Heet; Highest). **AC:** approved samples stored only in approved location; mapping and open decisions documented.

**Confirm acceptance measures —** agree grounding, clarity, relevance and effort baselines (Xinling; High). **AC:** named reviewer, rubric and thresholds approved.

## Epic 2 — Qualtrics Data Processing

**Canonical import mapper —** map confirmed Qualtrics headers/scales to internal schema (Gopi; Highest). **AC:** three representative exports load; changes/errors are explicit; no silent coercion.

**Approved API spike —** test read-only sandbox access after authorisation (Gopi; Medium). **AC:** security approval recorded; pagination/retry/data-minimisation tests pass.

## Epic 3 — Analytics

**Course filters and comparison gates —** segment course/delivery while blocking invalid comparisons (Gopi; High). **AC:** filters reconcile counts; mismatch yields “insufficient comparability”.

**Theme benchmark —** manually code a sample and compare theme coverage/minority concerns (Zhongyi; Highest). **AC:** error analysis and improvement actions documented.

## Epic 4 — AI / Prompt Framework

**Structured prompt schema —** implement JSON claim/evidence output for an approved provider (Zhongyi; High). **AC:** invalid/unsupported output rejected; PII regression set passes.

**Provider evaluation —** compare local and approved-provider outputs (Zhongyi; Medium). **AC:** groundedness, consistency and cost/latency reported transparently.

## Epic 5 — Report Generation

**Validate audience templates —** incorporate client examples and confirmed differences (Heet; Highest). **AC:** facilitator and client reviewers approve mandatory sections/tone.

**Production export styling —** branded, accessible DOCX/PDF if required (Gopi; Medium). **AC:** opens correctly; headings/tables/alt text pass visual/accessibility QA.

## Epic 6 — User Interface

**Multi-course workflow —** select/scope analysis before report generation (Xinling; High). **AC:** active filters visible in every chart/report.

**Accessible review experience —** keyboard, contrast, error and mobile/laptop QA (Xinling; High). **AC:** agreed WCAG 2.2 AA checklist passes.

## Epic 7 — Responsible AI & Security

**Data protection assessment —** document data flow, classification, retention and approved services (Esrat; Highest). **AC:** client/university owner signs controls.

**Cultural/minority-view test suite —** add indirect, multilingual and low-frequency safety cases (Esrat; High). **AC:** reviewer can see ambiguity/dissent; no demographic inference.

## Epic 8 — Testing

**End-to-end regression suite —** cover malformed files, metrics, PII, reports, approval and exports (Gopi; Highest). **AC:** CI passes and failures block release.

**Stakeholder UAT —** run task-based review and capture scores/issues (Xinling; Highest). **AC:** agreed participants complete rubric; actions prioritised.

## Epic 9 — Stakeholder Presentation

**Demo rehearsal and screenshots —** rehearse 3/5-minute versions and fallback (Heet; Highest). **AC:** time met twice; five clean screenshots and fallback available.

## Epic 10 — Documentation & Handover

**Operator and technical handover —** update setup, architecture, known limits and roadmap (Esrat; High). **AC:** another team member installs/runs/tests from README unaided.

