# Data folder

Only synthetic, made-up data is tracked in git:

- `synthetic_qualtrics_evaluation.csv`: deterministic demo responses, including a few fake contact details to demonstrate masking.
- `synthetic_course_history.csv`: illustrates a future comparison input; the app does not claim trends automatically.

**Real Qualtrics exports go in `data/client/`.** That folder is ignored by git, and `.gitignore` also blocks any other CSV or Excel file placed directly in `data/`. Import real files with **Import CSV / Excel**; the app never uploads or copies them.
