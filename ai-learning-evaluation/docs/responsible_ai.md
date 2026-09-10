# Responsible AI for learner evaluation reporting

## Controls

- **Privacy/confidentiality:** use synthetic or approved anonymised exports; minimise fields; mask obvious email, Australian phone and URL patterns before analysis; do not silently send data externally. Pattern matching is not enterprise anonymisation and may miss names, unusual identifiers or contextual re-identification.
- **Hallucination/grounding:** deterministic local generation uses only calculated metrics and retained theme evidence. Future prompts prohibit invented facts and require insufficiency statements. Staff sample claims against source evidence.
- **Bias and representation:** recurring themes can over-emphasise majority comments and understate minority concerns. Ratings can reflect response/non-response bias. Do not infer learner demographics or causal explanations.
- **Cultural interpretation:** indirect language varies across cultures. “The session was quite interesting, although some parts may perhaps have benefited from additional explanation” can contain a real improvement signal despite positive wording. Avoid sentiment as ground truth, retain source comments, and require culturally aware human interpretation.
- **Transparency:** the UI labels local mode, discloses its methods and never calls it Copilot. Draft/report status is visible.
- **Human oversight/accountability:** a named staff role checks metrics, evidence, privacy, tone and recommendations before approval. AI does not publish or make business decisions.
- **Data minimisation/traceability:** audit only filename, counts, audience, mode, timestamp and status; do not log comments.
- **Accessibility/inclusion:** clear headings, readable contrast, text labels rather than colour-only meaning, plain language and DOCX/Markdown alternatives. WCAG 2.2 AA is the proposed production target.

## Human review checklist

Confirm calculations; inspect representative and dissenting comments; remove identifying context; soften unsupported causality; verify audience-appropriate detail; assess cultural nuance; ensure recommendations follow evidence; record approval. When uncertain, state uncertainty or remove the claim.

