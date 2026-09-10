"""Generate deterministic, wholly synthetic Qualtrics-like evaluation data."""
from pathlib import Path
import random
import pandas as pd

SEED = 208
ROOT = Path(__file__).resolve().parents[1]

POSITIVE = [
    "The facilitator explained the concepts clearly.",
    "The practical activities made the content useful for my work.",
    "The examples and case studies were relevant and engaging.",
    "The course materials were clear and useful after the session.",
    "Interactive discussion helped me understand the topic.",
]
IMPROVE = [
    "More practical exercises would have helped.",
    "The content was useful but some sections moved too quickly.",
    "More industry examples and case studies would improve the course.",
    "The online platform had a brief audio issue.",
    "Allow more time for questions and group discussion.",
]
NEUTRAL = [
    "The course covered the expected material.",
    "No additional comments.",
    "The session was as described.",
]

def clipped_rating(rng: random.Random, centre: float) -> int:
    return max(1, min(5, round(rng.gauss(centre, 0.75))))

def build_responses(count: int = 128) -> pd.DataFrame:
    rng = random.Random(SEED)
    courses = [
        ("LF-101", "Leading Effective Teams", "Face-to-face", "Corporate", "FAC-014"),
        ("LF-205", "Applied Project Communication", "Online", "Government", "FAC-022"),
        ("LF-310", "Digital Service Foundations", "Hybrid", "Corporate", "FAC-009"),
    ]
    rows = []
    for i in range(count):
        code, name, mode, client, facilitator = courses[i % len(courses)]
        overall = clipped_rating(rng, 4.15)
        rows.append({
            "ResponseID": f"R_{1001+i}",
            "RecordedDate": (pd.Timestamp("2026-08-01") + pd.Timedelta(days=i % 28)).isoformat(),
            "CourseCode": code, "CourseName": name, "DeliveryMode": mode,
            "ClientType": client, "FacilitatorCode": facilitator,
            "OverallSatisfaction": overall,
            "ContentQuality": clipped_rating(rng, 4.0),
            "FacilitatorEffectiveness": clipped_rating(rng, 4.4),
            "CourseRelevance": clipped_rating(rng, 4.1),
            "WouldRecommend": "Yes" if overall >= 4 or rng.random() < 0.35 else "No",
            "MostValuableAspect": rng.choice(POSITIVE),
            "WhatCouldImprove": rng.choice(IMPROVE) if rng.random() < 0.72 else "",
            "AdditionalComments": rng.choice(NEUTRAL + POSITIVE) if rng.random() < 0.55 else "",
        })
    rows[4]["AdditionalComments"] = "My email is fake.student@example.com if you need more detail."
    rows[37]["AdditionalComments"] = "Call me on 0412 345 678 about the audio issue."
    rows[84]["AdditionalComments"] = "Notes are at https://example.invalid/learner-notes"
    return pd.DataFrame(rows)

def build_history() -> pd.DataFrame:
    return pd.DataFrame([
        {"CourseCode": "LF-101", "DeliveryPeriod": "2026-Q1", "ResponseCount": 39, "OverallSatisfaction": 4.08, "CourseRelevance": 4.02},
        {"CourseCode": "LF-205", "DeliveryPeriod": "2026-Q1", "ResponseCount": 35, "OverallSatisfaction": 3.94, "CourseRelevance": 4.01},
        {"CourseCode": "LF-310", "DeliveryPeriod": "2026-Q1", "ResponseCount": 42, "OverallSatisfaction": 4.12, "CourseRelevance": 4.10},
    ])

if __name__ == "__main__":
    (ROOT / "data").mkdir(exist_ok=True)
    build_responses().to_csv(ROOT / "data" / "synthetic_qualtrics_evaluation.csv", index=False)
    build_history().to_csv(ROOT / "data" / "synthetic_course_history.csv", index=False)
    print("Synthetic datasets generated.")

