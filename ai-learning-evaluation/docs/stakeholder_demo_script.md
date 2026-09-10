# Stakeholder demo script

## 3-minute version

1. **Overview (20 sec):** State “local demonstration mode” and show Upload → Analyse → Understand → Generate → Review → Export.
2. **Quality/privacy (25 sec):** Use the included synthetic file; show 128 rows, schema pass and planted PII masking notice.
3. **Dashboard (30 sec):** Point to five KPIs and the strongest/improvement theme cards.
4. **Themes (35 sec):** Open Pacing or Practical activities and show frequency, keywords and masked representative comments.
5. **Reports (35 sec):** Generate Facilitator; point to evidence and draft status. Switch/generate Commercial client and note outcome/value emphasis.
6. **Review/export (35 sec):** Edit a recommendation, enter reviewer role, tick the verification checklist, approve, then show Markdown/DOCX buttons.

Close: the prototype accelerates evidence and first drafting; staff remain accountable.

## 5-minute version

Add: explain invalid inputs do not crash; inspect the rating distribution/completeness; explain rule-based themes plus TF-IDF/NMF; point out no external service; compare exact facilitator/client wording; mention metadata-only audit; finish with the six client validation questions from slide 8.

## Recovery if the live demo fails

Run `streamlit run app.py` from the project environment; refresh the browser; remove the uploaded file to fall back to the bundled dataset; regenerate a report if session state resets. If startup is unavailable, use the sample reports in `reports/` and walk through README screenshots/process diagrams. Never claim an integration ran when using fallback material.

