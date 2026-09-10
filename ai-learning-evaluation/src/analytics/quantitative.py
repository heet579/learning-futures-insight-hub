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
    available = [c for c in REQUIRED_COLUMNS if c in df]
    completeness = float(df[available].notna().mean().mean() * 100) if len(df) and available else 0
    return {
        "response_count": len(df),
        "response_completeness": round(completeness, 1),
        "ratings": ratings,
        "satisfaction_percent": round(float((pd.to_numeric(df.get("OverallSatisfaction"), errors="coerce") >= 4).mean() * 100), 1) if len(df) and "OverallSatisfaction" in df else None,
        "recommendation_percent": round(float(positive[recognised].mean() * 100), 1) if recognised.any() else None,
        "strongest_area": max(means, key=means.get) if means else None,
        "lowest_area": min(means, key=means.get) if means else None,
    }

