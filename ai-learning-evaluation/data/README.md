# Data folder

Only synthetic, wholly fabricated data is tracked in git:

- `synthetic_qualtrics_evaluation.csv`: standard 3,000-response demo file with balanced ratings, 8 themes, and sample PII for regex masking demonstrations.
- `synthetic_qualtrics_evaluation.xlsx`: Excel workbook version of the standard demo file.
- `synthetic_qualtrics_evaluation_large.csv`: high-volume 5,000-response stress-test dataset across 11 courses and 3 delivery modes.
- `synthetic_qualtrics_evaluation_large.xlsx`: Excel workbook version of the high-volume dataset.
- `synthetic_course_history.csv`: illustrates a comparison input; the app does not claim trends automatically.
- `synthetic_qualtrics_exports/`: authentic 3-header raw Qualtrics export files (1,000 responses each in both `.csv` and `.xlsx`) mirroring the real 2023, 2024, and 2025 PACE / Learning Futures course survey templates:
  - `8325+-+Leadership+and+Management+Essentials+-+August+2023_September+21,+2026_13.22.csv` (and `.xlsx`)
  - `8423+-+Finance+for+Non-Financial+Managers+-+Nov+2024_September+21,+2026_13.26.csv` (and `.xlsx`)
  - `8457+-+From+Team+Member+to+Team+Leader+-+July+2024_September+21,+2026_13.25.csv` (and `.xlsx`)
  - `8563+Strategic+Thinking+5+&+6+August+2025_September+21,+2026_13.31.csv` (and `.xlsx`)
  - `Strategic+Thinking+-+8184+-+15+&+16+June+2023_September+21,+2026_13.29.csv` (and `.xlsx`)

### Regenerating or scaling synthetic data

Run the synthetic data generator anytime:

```sh
# Generate 10,000 canonical rows and 2,000 rows per Qualtrics course:
python -m scripts.generate_large_synthetic_data --canonical-count 10000 --qualtrics-count 2000
```

**Real Qualtrics exports go in `data/client/`.** That folder is ignored by git. Import real or synthetic test files with **Import CSV / Excel**; the app never uploads or copies them externally.

