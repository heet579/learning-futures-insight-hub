import pandas as pd
from src.config import REQUIRED_COLUMNS, RATING_COLUMNS, TEXT_COLUMNS
from src.models import ValidationResult

def validate_dataframe(df: pd.DataFrame) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if df.empty:
        errors.append("The file contains no survey responses.")
    if missing:
        errors.append("Missing required columns: " + ", ".join(missing))
    duplicates = int(df.duplicated(subset=["ResponseID"]).sum()) if "ResponseID" in df else 0
    if duplicates:
        warnings.append(f"{duplicates} duplicate ResponseID value(s) detected.")
    for column in RATING_COLUMNS:
        if column in df:
            numeric = pd.to_numeric(df[column], errors="coerce")
            invalid = int((df[column].notna() & numeric.isna()).sum())
            out_of_range = int(((numeric < 1) | (numeric > 5)).sum())
            if invalid or out_of_range:
                warnings.append(f"{column}: {invalid} non-numeric and {out_of_range} out-of-range value(s).")
    if "WouldRecommend" in df:
        allowed = {"yes", "no", "true", "false", "1", "0"}
        invalid = (~df["WouldRecommend"].astype(str).str.lower().isin(allowed)).sum()
        if invalid:
            warnings.append(f"WouldRecommend: {int(invalid)} unrecognised value(s).")
    if "RecordedDate" in df:
        parsed_dates = pd.to_datetime(df["RecordedDate"], errors="coerce", utc=True, format="mixed")
        invalid_dates = int((df["RecordedDate"].notna() & parsed_dates.isna()).sum())
        if invalid_dates:
            warnings.append(f"RecordedDate: {invalid_dates} invalid date value(s).")
    if "ResponseID" in df:
        blank_ids = int(df["ResponseID"].fillna("").astype(str).str.strip().eq("").sum())
        if blank_ids:
            warnings.append(f"ResponseID: {blank_ids} blank value(s).")
    present_text = [c for c in TEXT_COLUMNS if c in df]
    if present_text and df[present_text].isna().all(axis=1).mean() > 0.25:
        warnings.append("More than 25% of responses contain no qualitative feedback.")
    return ValidationResult(not errors, errors, warnings, len(df), missing)
