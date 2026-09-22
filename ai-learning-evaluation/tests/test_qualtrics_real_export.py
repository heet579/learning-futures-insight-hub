"""Tests for mapping real PACE/Qualtrics course exports onto the canonical schema.

Uses a small fabricated CSV shaped like a real export (generic Q-codes, a
question-text header row, identifier columns, Likert text) -- never real
client rows.
"""
import pandas as pd
from src.ingestion.qualtrics_loader import load_qualtrics_export, load_qualtrics_folder, is_raw_qualtrics_export

HEADER = [
    "StartDate", "EndDate", "Status", "IPAddress", "Progress", "Duration (in seconds)",
    "Finished", "RecordedDate", "ResponseId", "RecipientLastName", "RecipientFirstName",
    "RecipientEmail", "ExternalReference", "LocationLatitude", "LocationLongitude",
    "DistributionChannel", "UserLanguage",
    "Q2_1", "Q2_5", "Q4_1", "Q4_4", "Q3_NPS_GROUP", "Q3", "Q7", "Q8",
]
QUESTION_TEXT = [
    "Start Date", "End Date", "Response Type", "IP Address", "Progress", "Duration (in seconds)",
    "Finished", "Recorded Date", "Response ID", "Recipient Last Name", "Recipient First Name",
    "Recipient Email", "External Data Reference", "Location Latitude", "Location Longitude",
    "Distribution Channel", "User Language",
    "Course feedback - Overall, I was satisfied with the course",
    "Course feedback - I will apply what I've learnt in this course",
    "Presenter feedback - Overall, the presenter(s) were effective",
    "Presenter feedback - The course materials provided were useful",
    "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague? - Group",
    "On a scale from 0-10, how likely are you to recommend this short course to a friend or colleague?",
    "In this course, I really enjoyed:",
    "This course could be improved by:",
]
IMPORT_ID_ROW = {"ResponseId": '{"ImportId":"ResponseID"}'}

ROW_A = {
    "RecordedDate": "10/8/2023 16:08", "ResponseId": "R_fake001",
    "RecipientEmail": None, "IPAddress": None,
    "Q2_1": "Strongly agree", "Q2_5": "Somewhat agree",
    "Q4_1": "Strongly agree", "Q4_4": "Strongly agree",
    "Q3_NPS_GROUP": "Promoter", "Q3": "9",
    "Q7": "Placeholder positive comment", "Q8": "Placeholder improvement comment",
}
ROW_B = {
    "RecordedDate": "11/8/2023 09:00", "ResponseId": "R_fake002",
    "RecipientEmail": None, "IPAddress": None,
    "Q2_1": "Somewhat disagree", "Q2_5": "Neither agree nor disagree",
    "Q4_1": "Somewhat agree", "Q4_4": None,
    "Q3_NPS_GROUP": "Detractor", "Q3": "3",
    "Q7": None, "Q8": "Another placeholder comment",
}


def _fake_export_csv() -> str:
    rows = [dict(zip(HEADER, QUESTION_TEXT)), IMPORT_ID_ROW, ROW_A, ROW_B]
    return pd.DataFrame(rows, columns=HEADER).to_csv(index=False)


def test_real_export_maps_ratings_identifiers_and_recommend(tmp_path):
    path = tmp_path / "8325+-+Fake+Course+-+August+2023_time.csv"
    path.write_text(_fake_export_csv(), encoding="utf-8")

    df = load_qualtrics_export(path)

    assert len(df) == 2
    assert list(df["OverallSatisfaction"]) == [5, 2]
    assert df["ContentQuality"].iloc[0] == 5 and pd.isna(df["ContentQuality"].iloc[1])
    assert list(df["FacilitatorEffectiveness"]) == [5, 4]
    assert list(df["CourseRelevance"]) == [4, 3]
    assert list(df["WouldRecommend"]) == ["Yes", "No"]
    assert df["MostValuableAspect"].iloc[0] == "Placeholder positive comment"
    assert pd.isna(df["MostValuableAspect"].iloc[1])
    assert list(df["WhatCouldImprove"]) == ["Placeholder improvement comment", "Another placeholder comment"]
    assert df["CourseCode"].iloc[0] == "8325"
    assert "Fake Course" in df["CourseName"].iloc[0]
    for column in ("RecipientEmail", "IPAddress", "RecipientFirstName", "RecipientLastName", "LocationLatitude", "LocationLongitude"):
        assert column not in df.columns
    assert df["RecordedDate"].iloc[0] == "2023-08-10T16:08:00"


def test_is_raw_qualtrics_export_detects_by_header(tmp_path):
    raw_path = tmp_path / "raw.csv"
    raw_path.write_text(_fake_export_csv(), encoding="utf-8")
    assert is_raw_qualtrics_export(raw_path) is True

    canonical_path = tmp_path / "canonical.csv"
    canonical_path.write_text("ResponseID,RecordedDate,CourseCode\n1,2026-01-01,C1\n", encoding="utf-8")
    assert is_raw_qualtrics_export(canonical_path) is False


def test_reworded_questions_still_map_via_keywords(tmp_path):
    """A future survey revision can reword questions slightly; keyword matching (not
    exact phrases) should still find the right canonical field."""
    reworded_text = list(QUESTION_TEXT)
    reworded_text[17] = "Course feedback - Overall I felt very satisfied with this course"
    reworded_text[19] = "Presenter feedback - The presenter was highly effective overall"
    rows = [dict(zip(HEADER, reworded_text)), IMPORT_ID_ROW, ROW_A, ROW_B]
    path = tmp_path / "8900+-+Reworded+Course+-+Jan+2024_time.csv"
    pd.DataFrame(rows, columns=HEADER).to_csv(path, index=False)

    df = load_qualtrics_export(path)

    assert list(df["OverallSatisfaction"]) == [5, 2]
    assert list(df["FacilitatorEffectiveness"]) == [5, 4]


def test_real_export_folder_combines_multiple_files(tmp_path):
    (tmp_path / "8325+-+Fake+Course+-+August+2023_time.csv").write_text(_fake_export_csv(), encoding="utf-8")
    (tmp_path / "8500+-+Another+Course+-+Sept+2023_time.csv").write_text(_fake_export_csv(), encoding="utf-8")
    (tmp_path / "__MACOSX").mkdir()

    combined = load_qualtrics_folder(tmp_path)

    assert len(combined) == 4
    assert set(combined["CourseCode"]) == {"8325", "8500"}
