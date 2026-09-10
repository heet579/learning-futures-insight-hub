# Stakeholder presentation — 8 slides

## Slide 1 — AI-Enabled Learning Evaluation Reporting

**On slide:** PG-S2-08 | Learning Futures | From survey data to reviewable stakeholder insight. Team: Heet, Gopi, Zhongyi, Xinling and Esrat.

**Purpose:** Establish the business outcome. **Talking points (30–45 sec):** We are exploring how controlled AI assistance can reduce repetitive first-draft work while retaining Learning Futures' professional judgement. Today we will show a runnable local prototype, not a finished enterprise platform. **Key message:** Faster insight, consistent reporting, human accountability. **Transition:** First, the current friction.

## Slide 2 — Current business problem

**On slide:** Qualtrics → responses collected → staff read ratings/comments → identify themes → write summaries/recommendations → prepare stakeholder report. Pain points: time, repetition, consistency and scale.

**Purpose:** Show the understood problem. **Talking points:** Collection is already digital; interpretation is the bottleneck. Quantitative and qualitative evidence must be reconciled manually for multiple audiences. **Key message:** The opportunity is the reporting workflow, not replacing Qualtrics. **Transition:** This reflects what we heard.

## Slide 3 — What we heard from Learning Futures

**On slide:** many surveys; manual analysis; faster executive summaries; trends where valid; recommendations; facilitator and client outputs; Microsoft/Copilot interest.

**Purpose:** Demonstrate requirements traceability. **Talking points:** We converted these needs into must-haves: safe input, grounded findings, audience adaptation, transparent limits and mandatory review. Trend claims remain conditional on comparable history. **Key message:** Scope follows stakeholder needs and semester feasibility. **Transition:** Here is the proposed workflow.

## Slide 4 — Proposed solution

**On slide:** Qualtrics-compatible export → validate → mask → analyse → grounded draft → human edit/approval → export.

**Purpose:** Explain the TO-BE process. **Talking points:** Automation prepares evidence and a consistent first draft. A staff member verifies claims and owns the final version; there is no autonomous publishing. **Key message:** AI assists; humans decide. **Transition:** We implemented the riskiest capabilities as a rapid MVP.

## Slide 5 — Prototype and architecture

**On slide:** Streamlit UI; pandas metrics; TF-IDF/NMF + transparent theme rules; deterministic local provider; Markdown/DOCX; audit metadata.

**Purpose:** Establish technical credibility without code detail. **Talking points:** The prototype runs without credentials and does not send data externally. Clean boundaries allow later Qualtrics, Copilot, Power Automate and Power BI substitution. **Key message:** Runnable today; migratable tomorrow. **Transition:** Let’s see the end-to-end story.

## Slide 6 — Prototype demonstration

**On slide:** Upload | quality/privacy | dashboard | themes/evidence | audience report | human approval | export.

**Purpose:** Frame the live demo. **Talking points:** Watch for three controls: planted PII is masked, themes open to source evidence, and the report cannot lose its draft status without explicit review. We will switch audiences to show adaptation. **Key message:** The MVP demonstrates a complete controlled workflow. **Transition:** Those controls form part of a broader Responsible AI approach.

## Slide 7 — Responsible AI and security

**On slide:** privacy-by-design; grounded outputs; transparent local mode; cultural nuance/minority views; human review; no automatic external release.

**Purpose:** Build calibrated trust. **Talking points:** Pattern masking and automated themes are deliberately described as limited. Indirect language and minority views require human interpretation. Audit records metadata, not raw comments. **Key message:** Reliability comes from controls and verification, not fluent prose. **Transition:** The prototype now needs client validation and governed integration.

## Slide 8 — Roadmap and feedback

**On slide:** Requirements → Prototype V1 → stakeholder validation → V2 → evaluation/UAT → final demo/handover. Questions: approved exports? report examples? priority metrics? audience differences? Microsoft access? privacy constraints?

**Purpose:** Secure decisions. **Talking points:** The next milestone is not more speculative automation; it is validation with representative approved inputs and current report examples. We will refine templates, acceptance thresholds and the Microsoft pathway from that evidence. **Key message:** Confirm the right problem and quality bar before enterprise integration. **Transition:** We welcome feedback on the prototype and these decisions.

