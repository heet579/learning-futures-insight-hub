"""Validation and integration tests for the generated large synthetic datasets."""
from pathlib import Path
import pytest
import pandas as pd

from src.analytics.qualitative import collect_comments
from src.analytics.quantitative import calculate_metrics
from src.analytics.themes import extract_themes
from src.config import DATA_DIR, REQUIRED_COLUMNS
from src.ingestion.qualtrics_loader import load_qualtrics_export, load_qualtrics_folder, load_survey
from src.ingestion.validator import validate_dataframe
from src.privacy.pii_masker import detect_pii_counts, mask_dataframe
from src import workspace


@pytest.fixture(scope="module")
def data_directory():
    return Path(DATA_DIR)


@pytest.fixture(scope="module")
def large_canonical_files(tmp_path_factory, data_directory):
    csv_path = data_directory / "synthetic_qualtrics_evaluation_large.csv"
    xlsx_path = data_directory / "synthetic_qualtrics_evaluation_large.xlsx"
    if csv_path.exists() and xlsx_path.exists():
        return csv_path, xlsx_path

    from scripts.generate_large_synthetic_data import generate_canonical_responses, write_dataframe_to_xlsx
    temp_dir = tmp_path_factory.mktemp("large_synthetic")
    csv_gen = temp_dir / "synthetic_qualtrics_evaluation_large.csv"
    xlsx_gen = temp_dir / "synthetic_qualtrics_evaluation_large.xlsx"
    df = generate_canonical_responses(5000, seed=2026)
    df.to_csv(csv_gen, index=False)
    write_dataframe_to_xlsx(xlsx_gen, df)
    return csv_gen, xlsx_gen


def test_large_canonical_csv_loads_and_validates(large_canonical_files):
    large_csv, _ = large_canonical_files
    assert large_csv.exists(), f"Missing {large_csv}"

    df = load_survey(large_csv)
    assert len(df) == 5000
    assert list(df.columns) == REQUIRED_COLUMNS

    validation = validate_dataframe(df)
    assert validation.valid, f"Validation errors: {validation.errors}"
    assert len(validation.errors) == 0

    metrics = calculate_metrics(df)
    assert metrics["response_count"] == 5000
    assert metrics["satisfaction_percent"] > 70.0
    assert metrics["recommendation_percent"] > 70.0
    assert metrics["response_completeness"] > 80.0

    # Qualitative themes verification
    comments = collect_comments(df)
    assert len(comments) > 8000
    themes = extract_themes(comments)
    assert len(themes) >= 7
    theme_names = {t.name for t in themes}
    assert "Facilitator quality" in theme_names
    assert "Practical activities" in theme_names
    assert "Course relevance" in theme_names

    # PII masking verification
    pre_counts = detect_pii_counts(df)
    assert pre_counts["emails"] > 0
    assert pre_counts["phones"] > 0
    assert pre_counts["urls"] > 0

    masked_df, changed = mask_dataframe(df)
    assert changed > 0
    assert changed <= pre_counts["emails"] + pre_counts["phones"] + pre_counts["urls"]
    post_counts = detect_pii_counts(masked_df)
    assert post_counts == {"emails": 0, "phones": 0, "urls": 0}


def test_large_canonical_xlsx_matches_csv(large_canonical_files):
    large_csv, large_xlsx = large_canonical_files
    assert large_xlsx.exists() and large_csv.exists()

    df_csv = load_survey(large_csv)
    df_xlsx = load_survey(large_xlsx)

    assert len(df_xlsx) == len(df_csv) == 5000
    assert list(df_xlsx.columns) == list(df_csv.columns) == REQUIRED_COLUMNS
    assert df_xlsx["OverallSatisfaction"].mean() == pytest.approx(df_csv["OverallSatisfaction"].mean(), abs=0.01)


@pytest.mark.parametrize("course_stem, expected_code, expected_name_part", [
    ("8325+-+Leadership+and+Management+Essentials+-+August+2023_September+21,+2026_13.22", "8325", "Leadership and Management Essentials"),
    ("8423+-+Finance+for+Non-Financial+Managers+-+Nov+2024_September+21,+2026_13.26", "8423", "Finance for Non-Financial Managers"),
    ("8457+-+From+Team+Member+to+Team+Leader+-+July+2024_September+21,+2026_13.25", "8457", "From Team Member to Team Leader"),
    ("8563+Strategic+Thinking+5+&+6+August+2025_September+21,+2026_13.31", "8563", "Strategic Thinking"),
    ("Strategic+Thinking+-+8184+-+15+&+16+June+2023_September+21,+2026_13.29", "8184", "Strategic Thinking"),
])
def test_qualtrics_course_exports_map_correctly(data_directory, course_stem, expected_code, expected_name_part):
    exports_dir = data_directory / "synthetic_qualtrics_exports"
    csv_file = exports_dir / f"{course_stem}.csv"
    xlsx_file = exports_dir / f"{course_stem}.xlsx"

    assert csv_file.exists(), f"Missing CSV {csv_file}"
    assert xlsx_file.exists(), f"Missing XLSX {xlsx_file}"

    for path in (csv_file, xlsx_file):
        df = load_survey(path)
        assert len(df) == 1000, f"Expected 1000 rows in {path.name}, got {len(df)}"
        assert list(df.columns) == REQUIRED_COLUMNS
        assert df["CourseCode"].iloc[0] == expected_code
        assert expected_name_part in df["CourseName"].iloc[0]

        # Ratings validation
        for col in ["OverallSatisfaction", "ContentQuality", "FacilitatorEffectiveness", "CourseRelevance"]:
            valid_ratings = df[col].dropna()
            assert len(valid_ratings) > 850
            assert valid_ratings.between(1, 5).all()

        # Recommendation validation
        valid_rec = df["WouldRecommend"].dropna()
        assert len(valid_rec) > 850
        assert set(valid_rec.unique()).issubset({"Yes", "No"})

        # Qualitative text mapped
        assert df["MostValuableAspect"].dropna().str.len().gt(0).any()
        assert df["WhatCouldImprove"].dropna().str.len().gt(0).any()


def test_qualtrics_client_folder_multi_load(data_directory):
    client_dir = data_directory / "client"
    folder = client_dir if client_dir.is_dir() else (data_directory / "synthetic_qualtrics_exports")
    assert folder.is_dir()

    combined = load_qualtrics_folder(folder)
    assert len(combined) == 5000  # 5 course files * 1000 responses
    assert combined["CourseCode"].nunique() == 5

    # Run analysis through workspace
    masked, ctx, count, courses = workspace.analyse(combined, "PACE_2023_2025_Cohort")
    assert ctx.metrics["response_count"] == 5000
    assert len(ctx.themes) >= 6
    assert courses == [
        "Finance for Non-Financial Managers - Nov 2024",
        "From Team Member to Team Leader - July 2024",
        "Leadership and Management Essentials - August 2023",
        "Strategic Thinking - 15 & 16 June 2023",
        "Strategic Thinking 5 & 6 August 2025",
    ]

    # Course scope filtering
    scope = "Finance for Non-Financial Managers - Nov 2024"
    masked, sub_ctx, _, _ = workspace.analyse(combined, "Client Drop", scope=scope)
    assert sub_ctx.metrics["response_count"] == 1000
    assert sub_ctx.course_name == scope
