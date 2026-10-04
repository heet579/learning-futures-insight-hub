from typing import Any
import pandas as pd
from src.config import RATING_COLUMNS, REQUIRED_COLUMNS

LABELS = {
    "OverallSatisfaction": "Overall satisfaction",
    "ContentQuality": "Content quality",
    "FacilitatorEffectiveness": "Facilitator effectiveness",
    "CourseRelevance": "Course relevance",
}

def calculate_metrics(df: pd.DataFrame) -> dict[str, Any]:
    ratings: dict[str, dict[str, Any]] = {}
    for column in RATING_COLUMNS:
        values = pd.to_numeric(df[column], errors="coerce") if column in df else pd.Series(dtype=float)
        valid = values.where(values.between(1, 5)).dropna()
        ratings[column] = {
            "label": LABELS[column],
            "mean": round(float(valid.mean()), 2) if len(valid) else None,
            "median": float(valid.median()) if len(valid) else None,
            "count": int(valid.count()),
            "distribution": {str(i): int((valid == i).sum()) for i in range(1, 6)},
        }
    recommend = df.get("WouldRecommend", pd.Series(dtype=str)).astype(str).str.lower()
    recognised = recommend.isin(["yes", "no", "true", "false", "1", "0"])
    positive = recommend.isin(["yes", "true", "1"])
    means = {k: v["mean"] for k, v in ratings.items() if v["mean"] is not None}
    # Completeness only covers fields the source actually supplied. A field that is
    # blank in every row (e.g. ClientType in real Qualtrics exports) was never collected,
    # so counting it would understate how complete the real answers are.
    present = [c for c in REQUIRED_COLUMNS if c in df and df[c].notna().any()]
    not_in_source = [c for c in REQUIRED_COLUMNS if c not in present]
    completeness = float(df[present].notna().mean().mean() * 100) if len(df) and present else 0
    # Satisfaction uses the same denominator as the rating mean: valid 1-5 answers only.
    overall = ratings["OverallSatisfaction"]
    satisfied = overall["distribution"]["4"] + overall["distribution"]["5"]
    return {
        "response_count": len(df),
        "response_completeness": round(completeness, 1),
        "fields_not_in_source": not_in_source,
        "ratings": ratings,
        "satisfaction_count": satisfied,
        "satisfaction_percent": round(satisfied / overall["count"] * 100, 1) if overall["count"] else None,
        "recommendation_count": int(positive[recognised].sum()),
        "recommendation_total": int(recognised.sum()),
        "recommendation_percent": round(float(positive[recognised].mean() * 100), 1) if recognised.any() else None,
        "strongest_area": max(means, key=means.get) if means else None,
        "lowest_area": min(means, key=means.get) if means else None,
    }

