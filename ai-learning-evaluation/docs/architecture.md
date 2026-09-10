# Architecture

## Current prototype

```mermaid
flowchart TD
  Q[Qualtrics-compatible survey export] --> V[Data validation layer]
  V --> P[Privacy processing]
  P --> QT[Quantitative analysis]
  P --> QL[Qualitative analysis]
  QT --> C[Grounded analysis context]
  QL --> C
  C --> A[Provider / prompt framework]
  A --> F[Facilitator report]
  A --> R[Commercial client report]
  F --> H[Human review]
  R --> H
  H --> O[Approved export]
```

The Streamlit app orchestrates pure Python modules. Validation never crashes on missing columns. Only masked text reaches analytics/reporting. Metrics and `Theme.evidence` form the analysis context; the deterministic provider converts only this context to prose. Raw personal data is not written to the audit log.

## Future Microsoft-aligned architecture

```mermaid
flowchart LR
  Q[Qualtrics] --> M[Approved Microsoft connector / API]
  M --> PA[Power Automate validation and routing]
  PA --> C[Copilot Studio agent and approved actions]
  C --> BI[Power BI / SharePoint report]
  BI --> T[Teams / SharePoint human approval]
```

This is a proposed migration, not implemented integration.

