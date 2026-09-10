# Testing strategy

Automated tests cover successful/missing-column ingestion, manually calculated golden metrics, email/phone masking, empty and sufficient theme inputs, mandatory report sections, audience differentiation and draft/approval status. Run `pytest -q`. Presentation QA additionally uploads a malformed CSV, checks all tabs at common laptop resolution, inspects planted PII absence, compares report claims to evidence, edits/approves both audiences and opens Markdown/DOCX exports. Future testing should add Qualtrics fixtures, prompt/model regression sets, fairness/indirect-language cases, security tests, accessibility audit and stakeholder UAT.

