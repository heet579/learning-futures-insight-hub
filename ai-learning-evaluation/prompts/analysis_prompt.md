# Survey Analysis Prompt

Analyse the supplied structured metrics and masked comments. You must only use information contained in the provided analysis. Do not invent facts, causes, comparisons or trends. For each finding return `claim`, `evidence_metrics`, `theme_frequency`, `representative_comment_ids`, and `confidence_note`. If evidence is insufficient, state that no conclusion can be made. Do not expose personal information. All findings require human review. Output valid JSON only.
