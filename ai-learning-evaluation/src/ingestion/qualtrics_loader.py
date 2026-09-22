import re
from pathlib import Path
from typing import BinaryIO
import pandas as pd
from src.config import REQUIRED_COLUMNS, RATING_COLUMNS

def _normalize_qualtrics_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Detect and remove standard Qualtrics 3-row header metadata rows if present."""
    if df.empty or len(df) == 0:
        return df
    drop_indices = []
    for idx in range(min(3, len(df))):
        row_values = [str(v).strip() for v in df.iloc[idx].values if pd.notna(v)]
        row_str = " ".join(row_values)
        if (
            "ImportId" in row_str
            or "Response ID" in row_str
            or "{" in row_str
            or (idx == 0 and len(row_values) > 0 and row_values[0] == df.columns[0])
        ):
            drop_indices.append(idx)
    if drop_indices:
        df = df.drop(index=drop_indices).reset_index(drop=True)
    return df

def load_csv(source: str | Path | BinaryIO) -> pd.DataFrame:
    """Load a Qualtrics-compatible CSV and return friendly errors."""
    try:
        df = pd.read_csv(source)
    except UnicodeDecodeError:
        try:
            if hasattr(source, "seek"):
                source.seek(0)
            df = pd.read_csv(source, encoding="latin-1")
        except Exception as exc:
            raise ValueError(f"The CSV encoding could not be read: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"The uploaded file is not a readable CSV: {exc}") from exc

    return _normalize_qualtrics_headers(df)


# --- Real Qualtrics export support -----------------------------------------
# Live PACE/Learning Futures exports use generic question codes (Q2_1, Q4_3, ...)
# that shift between survey template versions, and carry no CourseCode/ClientType/
# FacilitatorCode columns at all. Column identity is therefore resolved from the
# question-text row (Qualtrics' second header row) rather than from fixed names,
# and columns with no canonical fit are dropped rather than guessed at.

IDENTIFIER_COLUMNS = [
    "IPAddress", "RecipientLastName", "RecipientFirstName", "RecipientEmail",
    "ExternalReference", "LocationLatitude", "LocationLongitude",
]

LIKERT_SCALE = {
    "strongly disagree": 1, "somewhat disagree": 2,
    "neither agree nor disagree": 3, "somewhat agree": 4, "strongly agree": 5,
}

# (required keywords, canonical field): a column matches a field when every keyword
# appears somewhere in its question text. Keyword sets (not exact phrases) so minor
# wording changes between survey template versions still match. First match wins.
RATING_TEXT_MAP = [
    (("overall", "satisfied", "course"), "OverallSatisfaction"),
    (("materials", "useful"), "ContentQuality"),
    (("presenter", "effective"), "FacilitatorEffectiveness"),
    (("apply", "learnt", "course"), "CourseRelevance"),
]
TEXT_QUESTION_MAP = [
    (("really", "enjoyed"), "MostValuableAspect"),
    (("could", "improved"), "WhatCouldImprove"),
    (("feedback", "suggestions", "presenters"), "AdditionalComments"),
    (("would", "recommend"), "AdditionalComments"),
]
NPS_KEYWORDS = ("likely", "recommend")


def _match_question(text: str) -> str | None:
    lowered = text.lower()
    for keywords, field in (*RATING_TEXT_MAP, *TEXT_QUESTION_MAP):
        if all(k in lowered for k in keywords):
            return field
    return None


def _course_from_filename(filename: str) -> tuple[str | None, str | None]:
    """Derive CourseCode/CourseName from a PACE export filename; neither column exists in the data itself."""
    stem = Path(filename).stem.replace("+", " ")
    stem = re.sub(r"_[A-Za-z]+ \d{1,2}, \d{4}.*$", "", stem)  # drop the export timestamp suffix
    code_match = re.search(r"\b(\d{3,6})\b", stem)
    code = code_match.group(1) if code_match else None
    name = stem
    if code:
        name = re.sub(rf"\b{code}\b", "", name)
    name = re.sub(r"\s*-\s*", " - ", name)
    name = re.sub(r"(?:\s*-\s*){2,}", " - ", name)
    name = re.sub(r"\s+", " ", name).strip(" -")
    return code, (name or None)


def is_raw_qualtrics_export(path: str | Path) -> bool:
    """Cheap header-only check: is this an unmapped Qualtrics export rather than the canonical schema?"""
    header = pd.read_csv(path, nrows=0).columns
    if "ResponseID" in header:
        return False  # already canonical (e.g. the synthetic demo file)
    return "ResponseId" in header or "StartDate" in header


def load_qualtrics_export(path: str | Path) -> pd.DataFrame:
    """Load one real PACE/Qualtrics course export and map it onto the canonical schema."""
    path = Path(path)
    raw = pd.read_csv(path)
    if raw.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    question_text = raw.iloc[0]
    df = _normalize_qualtrics_headers(raw)
    df = df.drop(columns=[c for c in IDENTIFIER_COLUMNS if c in df.columns])

    rename: dict[str, str] = {}
    for column in df.columns:
        if column == "ResponseId":
            rename[column] = "ResponseID"
            continue
        if "GROUP" in column.upper():
            continue  # categorical NPS bucket; we derive our own from the numeric score
        text = str(question_text.get(column, ""))
        if all(k in text.lower() for k in NPS_KEYWORDS):
            rename[column] = "NPSScore"
            continue
        field = _match_question(text)
        if field:
            rename[column] = field
    df = df.rename(columns=rename)
    df = df.loc[:, ~df.columns.duplicated()]

    for column in RATING_COLUMNS:
        if column in df:
            df[column] = df[column].astype(str).str.strip().str.lower().map(LIKERT_SCALE)

    if "NPSScore" in df:
        nps = pd.to_numeric(df["NPSScore"], errors="coerce")
        df["WouldRecommend"] = nps.map(lambda v: "Yes" if v >= 7 else "No" if pd.notna(v) else pd.NA)
        df = df.drop(columns=["NPSScore"])

    if "RecordedDate" in df:
        parsed = pd.to_datetime(df["RecordedDate"], dayfirst=True, errors="coerce")
        df["RecordedDate"] = parsed.dt.strftime("%Y-%m-%dT%H:%M:%S")

    df["CourseCode"], df["CourseName"] = _course_from_filename(path.name)

    for column in REQUIRED_COLUMNS:
        if column not in df:
            df[column] = pd.NA
    return df[REQUIRED_COLUMNS]


def load_qualtrics_folder(folder: str | Path) -> pd.DataFrame:
    """Load and combine every course export CSV in a folder (e.g. one client's data/client/ drop)."""
    folder = Path(folder)
    files = sorted(folder.glob("*.csv"))
    if not files:
        raise ValueError(f"No CSV files found in {folder}")
    return pd.concat([load_qualtrics_export(f) for f in files], ignore_index=True)


