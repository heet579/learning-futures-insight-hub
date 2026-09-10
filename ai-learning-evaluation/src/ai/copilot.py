"""Grounded, deterministic Copilot-style assistant for the offline prototype."""
from __future__ import annotations

from src.models import AnalysisContext


def answer_question(question: str, context: AnalysisContext) -> str:
    q = question.lower().strip()
    metrics = context.metrics
    ratings = metrics.get("ratings", {})
    themes = context.themes
    if not q:
        return "Ask about performance, themes, recommendations, participation, or risks."
    if any(word in q for word in ("rating", "score", "performance", "satisfaction")):
        available = [f"{v['label']} is {v['mean']:.2f}/5 (n={v['count']})" for v in ratings.values() if v.get("mean") is not None]
        return "; ".join(available) + f". Satisfaction at 4–5 is {metrics['satisfaction_percent']:.1f}%."
    if any(word in q for word in ("theme", "feedback", "learner", "said")):
        if not themes:
            return "No recurring qualitative theme met the current evidence threshold."
        return "The strongest recurring signals are " + "; ".join(f"{t.name} ({t.frequency} comments, {t.category.lower()})" for t in themes[:4]) + ". Inspect the Themes tab before acting."
    if any(word in q for word in ("recommend", "action", "improve", "next")):
        issues = [t for t in themes if t.category == "Improvement"]
        if not issues:
            return "Maintain the current approach and compare the same measures after the next delivery."
        return "Prioritise a small test for " + ", then ".join(t.name.lower() for t in issues[:3]) + ". Re-measure satisfaction and inspect comments after the next comparable delivery."
    if any(word in q for word in ("response", "participation", "complete", "sample")):
        return f"This scope contains {metrics['response_count']} responses with {metrics['response_completeness']:.1f}% field completeness."
    if any(word in q for word in ("risk", "confidence", "trust", "limit")):
        return "Treat themes as indicators, not ground truth. Check sample size, missingness, supporting comments and survey comparability; a human reviewer remains accountable for conclusions."
    return "I can answer from the active dataset about ratings, participation, learner themes, recommended actions, and evidence limitations."
