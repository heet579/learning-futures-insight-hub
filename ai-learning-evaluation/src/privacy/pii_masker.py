import re
import pandas as pd
from src.config import TEXT_COLUMNS

EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"(?<!\w)(?:\+?61\s?|0)(?:[2-478](?:[ -]?\d){8}|4(?:[ -]?\d){8})(?!\w)")
URL = re.compile(r"\b(?:https?://|www\.)\S+", re.I)

def mask_text(value: object) -> object:
    if pd.isna(value):
        return value
    text = str(value)
    text = EMAIL.sub("[EMAIL REMOVED]", text)
    text = PHONE.sub("[PHONE REMOVED]", text)
    return URL.sub("[URL REMOVED]", text)

def mask_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    masked = df.copy()
    changes = 0
    for column in (c for c in TEXT_COLUMNS if c in masked):
        original = masked[column].copy()
        masked[column] = masked[column].map(mask_text)
        changes += int((original.fillna("").astype(str) != masked[column].fillna("").astype(str)).sum())
    return masked, changes

def detect_pii_counts(df: pd.DataFrame) -> dict[str, int]:
    """Count obvious patterns without retaining or returning matched values."""
    counts = {"emails": 0, "phones": 0, "urls": 0}
    for column in (c for c in TEXT_COLUMNS if c in df):
        for value in df[column].dropna().astype(str):
            counts["emails"] += len(EMAIL.findall(value))
            counts["phones"] += len(PHONE.findall(value))
            counts["urls"] += len(URL.findall(value))
    return counts
