"""High-volume, deterministic synthetic data for safe prototype demonstrations."""
from __future__ import annotations

import random
from datetime import datetime, timedelta

import pandas as pd


COURSES = [
    ("LF-101", "Executive Leadership & Team Performance", "Face-to-face", "Corporate", "FAC-014"),
    ("LF-205", "Applied Project & Stakeholder Communication", "Online", "Government", "FAC-022"),
    ("LF-310", "Digital Transformation Foundations", "Hybrid", "Corporate", "FAC-009"),
    ("LF-420", "AI Literacy & Strategic Technology", "Hybrid", "Higher Education", "FAC-031"),
    ("LF-515", "Strategic Change Leadership", "Online", "Not-for-profit", "FAC-018"),
    ("LF-605", "Healthcare Innovation & Clinical Leadership", "Face-to-face", "Healthcare", "FAC-027"),
    ("LF-710", "Defense Industry Governance & Strategy", "Hybrid", "Defense", "FAC-040"),
]

POSITIVE = [
    "The facilitator explained the concepts clearly with real-world case studies.",
    "The practical activities made the content immediately useful for my organizational role.",
    "The executive examples and industry insights were highly relevant and engaging.",
    "The course materials were comprehensive and useful reference for our team.",
    "Interactive group discussion helped me apply strategic thinking to my workplace.",
]
IMPROVEMENT = [
    "More practical exercises and workshop activities would have helped.",
    "The content was very useful, but some complex modules moved too quickly.",
    "More Adelaide University industry case studies would improve course impact.",
    "The online workshop platform had a minor audio connectivity delay.",
    "Allow more dedicated time for live Q&A and cross-functional discussion.",
]
NEUTRAL = ["The course covered all expected learning objectives.", "No additional comments.", "The professional development session was as described."]


def _rating(rng: random.Random, centre: float) -> int:
    return max(1, min(5, round(rng.gauss(centre, 0.78))))


def build_synthetic_responses(count: int = 2500, seed: int = 208) -> pd.DataFrame:
    """Return a Qualtrics-compatible synthetic dataset; no real people are represented."""
    rng = random.Random(seed)
    start = datetime(2025, 7, 1)
    rows = []
    effects = {
        "LF-101": .12, "LF-205": -.18, "LF-310": .04,
        "LF-420": .18, "LF-515": -.04, "LF-605": .10, "LF-710": .06
    }
    for index in range(count):
        code, name, mode, client, facilitator = COURSES[index % len(COURSES)]
        effect = effects[code]
        overall = _rating(rng, 4.08 + effect)
        recorded = start + timedelta(days=rng.randrange(0, 420))
        rows.append({
            "ResponseID": f"SYN-{seed}-{index + 1:06d}",
            "RecordedDate": recorded.isoformat(),
            "CourseCode": code,
            "CourseName": name,
            "DeliveryMode": mode,
            "ClientType": client,
            "FacilitatorCode": facilitator,
            "OverallSatisfaction": overall,
            "ContentQuality": _rating(rng, 3.98 + effect),
            "FacilitatorEffectiveness": _rating(rng, 4.30 + effect),
            "CourseRelevance": _rating(rng, 4.02 + effect),
            "WouldRecommend": "Yes" if overall >= 4 or rng.random() < .30 else "No",
            "MostValuableAspect": rng.choice(POSITIVE),
            "WhatCouldImprove": rng.choice(IMPROVEMENT) if rng.random() < .70 else "",
            "AdditionalComments": rng.choice(NEUTRAL + POSITIVE) if rng.random() < .48 else "",
        })
    return pd.DataFrame(rows)
