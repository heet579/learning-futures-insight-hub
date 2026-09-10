from pathlib import Path
from typing import BinaryIO
import pandas as pd

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


