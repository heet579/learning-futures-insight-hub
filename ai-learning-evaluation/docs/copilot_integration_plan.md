# Microsoft Copilot integration plan

| Current prototype | Potential Microsoft component |
|---|---|
| CSV uploader | Qualtrics approved export/API connector |
| Python validation/privacy workflow | Power Automate flow and governed custom connector/action |
| Analysis context | Dataverse/SharePoint controlled record or approved API payload |
| Local deterministic provider | Copilot Studio agent with structured prompts and approved model |
| Streamlit dashboard | Power BI and/or Power Apps |
| Session review | Teams/SharePoint approval workflow |
| Markdown/DOCX download | SharePoint document generation and retention controls |
| JSONL audit | Purview/Dataverse/Power Platform audit controls |

Phases: confirm licensing/data classification; define canonical schema and DLP boundary; prototype read-only connector; evaluate model grounding/privacy on approved datasets; introduce approval workflow; perform security, accessibility and UAT; deploy with monitoring and rollback. Copilot Studio should receive masked/minimised structured context, never an unrestricted raw export by default. No Microsoft integration is implemented in this MVP.

