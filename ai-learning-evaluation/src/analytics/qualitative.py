import pandas as pd
from src.config import TEXT_COLUMNS

def collect_comments(df: pd.DataFrame) -> list[str]:
    comments: list[str] = []
    for column in (c for c in TEXT_COLUMNS if c in df):
        comments.extend(x.strip() for x in df[column].dropna().astype(str) if x.strip())
    return comments

