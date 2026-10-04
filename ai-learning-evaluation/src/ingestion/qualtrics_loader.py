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
# Multiple-choice "Selected Choice" answers are deliberately NOT mapped: they are
# lists of preset options, not learner comments, and would create fake themes.
# The free-text "Other" box of the same question is a real comment and is kept.
TEXT_QUESTION_MAP = [
    (("really", "enjoyed"), "MostValuableAspect"),
    (("aspects", "enjoyed", "other", "text"), "MostValuableAspect"),
    (("could", "improved"), "WhatCouldImprove"),
    (("feedback", "suggestions", "presenters"), "AdditionalComments"),
    (("would", "recommend"), "AdditionalComments"),
]
NPS_KEYWORDS = ("likely", "recommend")


def _match_question(text: str) -> str | None:
    lowered = text.lower()
    if "selected choice" in lowered:
        return None
    for keywords, field in (*RATING_TEXT_MAP, *TEXT_QUESTION_MAP):
        if all(k in lowered for k in keywords):
            return field
    return None


def _merge_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Two questions can map to the same field (e.g. two free-text questions both feeding
    AdditionalComments). Text answers are joined so neither is lost; for any other field the
    first column wins."""
    from src.config import TEXT_COLUMNS
    merged: dict[str, pd.Series] = {}
    for position, column in enumerate(df.columns):
        series = df.iloc[:, position]
        if column not in merged:
            merged[column] = series
        elif column in TEXT_COLUMNS:
            first = merged[column]
            merged[column] = pd.Series([
                " / ".join(str(v).strip() for v in pair if pd.notna(v) and str(v).strip()) or pd.NA
                for pair in zip(first, series)
            ], index=df.index)
    return pd.DataFrame(merged, index=df.index)


def _course_from_filename(filename: str) -> tuple[str | None, str | None]:
    """Derive CourseCode/CourseName from a PACE export filename; neither column exists in the data itself."""
    stem = Path(filename).stem.replace("+", " ")
    stem = re.sub(r"_[A-Za-z]+ \d{1,2}, \d{4}.*$", "", stem)  # drop the export timestamp suffix
    code_match = re.search(r"\b(\d{3,6})\b", stem)
    code = code_match.group(1) if code_match else None
    name = stem
    if code:
        name = re.sub(rf"\b{code}\b", "", name)
    # Only a dash with spaces around it separates parts; "Non-Financial" stays intact.
    name = re.sub(r"\s+-\s+", " - ", name)
    name = re.sub(r"\s+-(?:\s+-)+\s+", " - ", name)
    name = re.sub(r"^\s*-\s+|\s+-\s*$", "", name)
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
    raw = _read_table(path)
    return _map_export(raw, path.name)


def _map_export(raw: pd.DataFrame, filename: str) -> pd.DataFrame:
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
    df = _merge_duplicate_columns(df)

    for column in RATING_COLUMNS:
        if column in df:
            values = df[column].astype(str).str.strip().str.lower()
            df[column] = values.map(LIKERT_SCALE).fillna(pd.to_numeric(values, errors="coerce"))

    if "NPSScore" in df:
        nps = pd.to_numeric(df["NPSScore"], errors="coerce")
        df["WouldRecommend"] = nps.map(lambda v: "Yes" if v >= 7 else "No" if pd.notna(v) else pd.NA)
        df = df.drop(columns=["NPSScore"])

    if "RecordedDate" in df:
        parsed = pd.to_datetime(df["RecordedDate"], dayfirst=True, errors="coerce")
        df["RecordedDate"] = parsed.dt.strftime("%Y-%m-%dT%H:%M:%S")

    df["CourseCode"], df["CourseName"] = _course_from_filename(filename)

    for column in REQUIRED_COLUMNS:
        if column not in df:
            df[column] = pd.NA
    return df[REQUIRED_COLUMNS]


def _read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(path, engine="calamine", sheet_name=0)
        except Exception as exc:
            raise ValueError("Cannot read this Excel workbook. Use a valid .xlsx/.xls file with survey data on its first sheet.") from exc
    if path.suffix.lower() == ".csv":
        try:
            return pd.read_csv(path)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin-1")
    raise ValueError("Choose a CSV, XLSX or XLS survey file.")


def load_survey(path: str | Path) -> pd.DataFrame:
    """Import canonical or three-header Qualtrics data from CSV or Excel."""
    raw = _read_table(path)
    if "ResponseID" not in raw and ("ResponseId" in raw or "StartDate" in raw):
        return _map_export(raw, Path(path).name)
    return _normalize_qualtrics_headers(raw)


def load_qualtrics_folder(folder: str | Path) -> pd.DataFrame:
    """Load and combine every course export CSV in a folder (e.g. one client's data/client/ drop)."""
    folder = Path(folder)
    files = sorted(folder.glob("*.csv"))
    if not files:
        raise ValueError(f"No CSV files found in {folder}")
    return pd.concat([load_qualtrics_export(f) for f in files], ignore_index=True)


