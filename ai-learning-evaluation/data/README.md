# Data folder

The files committed here contain synthetic survey responses. The application starts empty; use **Import CSV / Excel** to select the files you want to analyse.

## Files included in a fresh checkout

| File or folder | Responses | Purpose |
|---|---:|---|
| `synthetic_qualtrics_evaluation.csv` | 3,000 | Standard demo covering 11 courses, three delivery modes, theme vocabulary and sample contact details for masking checks. |
| `synthetic_course_history.csv` | 3 summary rows | Example comparison input; the application does not infer trends automatically. |
| `synthetic_qualtrics_exports/` | 5,000 total | Five course exports, each containing 1,000 responses in both CSV and Excel formats. |

Each course export has three Qualtrics header rows followed by the responses:

| Course | Export filename stem, available as `.csv` and `.xlsx` |
|---|---|
| 8325 — Leadership and Management Essentials, August 2023 | `8325+-+Leadership+and+Management+Essentials+-+August+2023_September+21,+2026_13.22` |
| 8423 — Finance for Non-Financial Managers, November 2024 | `8423+-+Finance+for+Non-Financial+Managers+-+Nov+2024_September+21,+2026_13.26` |
| 8457 — From Team Member to Team Leader, July 2024 | `8457+-+From+Team+Member+to+Team+Leader+-+July+2024_September+21,+2026_13.25` |
| 8563 — Strategic Thinking, August 2025 | `8563+Strategic+Thinking+5+&+6+August+2025_September+21,+2026_13.31` |
| 8184 — Strategic Thinking, June 2023 | `Strategic+Thinking+-+8184+-+15+&+16+June+2023_September+21,+2026_13.29` |

CSV and Excel versions represent the same responses. Import one format per course when measuring cohort totals.

## Files generated on demand

The generator creates `synthetic_qualtrics_evaluation_large.csv` and `.xlsx` with 5,000 responses by default, plus a 3,000-response standard demo in both formats and the five course exports. The large canonical files and standard demo workbook are generated locally rather than required in a fresh checkout. CI generates its canonical test files in temporary storage.

Run these commands from `ai-learning-evaluation/` with the project Python environment active:

```sh
python -m scripts.generate_large_synthetic_data --output-dir data/generated
```

`data/generated/` is ignored by Git. To scale the large file to 10,000 responses and each course export to 2,000:

```sh
python -m scripts.generate_large_synthetic_data --output-dir data/generated --canonical-count 10000 --qualtrics-count 2000
```

For a small CSV-only sample:

```sh
python -m scripts.generate_large_synthetic_data --output-dir data/generated/small --canonical-count 10 --qualtrics-count 5 --no-excel
```

Both counts must be positive integers. The standard demo always contains 3,000 responses; the count options change the large canonical file and per-course exports. `--seed` controls reproducible sampling and defaults to `2026`. The explicit masking examples are injected at response positions 8, 24 and 65 when those positions exist, so very small samples may not cover every contact-detail pattern.

Without `--output-dir`, the generator writes into `data/`, including replacing the standard demo CSV. Use a separate output folder for experiments.

## Client-folder copies

**Real Qualtrics exports belong in `data/client/`, which is ignored by Git.** Generation leaves the client folder alone by default. To make a synthetic folder-drop sample inside the isolated output folder:

```sh
python -m scripts.generate_large_synthetic_data --output-dir data/generated --populate-client
```

This creates `data/generated/client/`. The older `--no-client` option is still accepted and explicitly selects the default behaviour. The Python function `generate_all_test_datasets(..., populate_client_folder=True)` also opts into copying.

## Verification

```sh
python ../tools/testsuit.py --suite data --headless --strict-skips --no-color
```

The data suite includes generator boundary checks, deterministic sampling, output-folder isolation, client-file preservation, CSV/Excel imports, privacy masking, and multi-course metrics. Tests use temporary generated canonical files and committed synthetic course exports; they do not read `data/client/`.

