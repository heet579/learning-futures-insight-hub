from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

RATING_COLUMNS = [
    "OverallSatisfaction", "ContentQuality",
    "FacilitatorEffectiveness", "CourseRelevance",
]
TEXT_COLUMNS = ["MostValuableAspect", "WhatCouldImprove", "AdditionalComments"]
REQUIRED_COLUMNS = [
    "ResponseID", "RecordedDate", "CourseCode", "CourseName", "DeliveryMode",
    "ClientType", "FacilitatorCode", *RATING_COLUMNS, "WouldRecommend", *TEXT_COLUMNS,
]

def external_provider_configured() -> bool:
    return all(os.getenv(key) for key in (
        "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"
    ))

