from src.ai.base_provider import AIProvider
from src.models import AnalysisContext

def _rating(context: AnalysisContext, key: str) -> float | None:
    return context.metrics.get("ratings", {}).get(key, {}).get("mean")

class LocalDemoProvider(AIProvider):
    name = "Local Demonstration Mode"

    def executive_summary(self, context: AnalysisContext, audience: str) -> str:
        count = context.metrics["response_count"]
        overall = _rating(context, "OverallSatisfaction")
        relevance = _rating(context, "CourseRelevance")
        top = next((t for t in context.themes if t.category == "Positive"), None)
        improvement = next((t for t in context.themes if t.category == "Improvement"), None)
        parts = [f"This draft summarises {count} learner evaluation response(s) for {context.course_name}."]
        if overall is not None:
            parts.append(f"Overall satisfaction averaged {overall:.2f}/5.")
        if audience == "client" and relevance is not None:
            parts.append(f"Course relevance averaged {relevance:.2f}/5, indicating the reported value to participants.")
        if top:
            parts.append(f"The most frequent positive theme was {top.name.lower()} ({top.frequency} related comment(s)).")
        if improvement:
            parts.append(f"The leading improvement theme was {improvement.name.lower()} ({improvement.frequency} related comment(s)).")
        parts.append("These findings are descriptive and require human interpretation before use.")
        return " ".join(parts)

    def recommendations(self, context: AnalysisContext, audience: str) -> list[str]:
        actions: list[str] = []
        for theme in context.themes:
            if theme.category != "Improvement":
                continue
            if theme.name == "Practical activities":
                actions.append("Review whether an additional applied exercise can be added, then test its usefulness in the next delivery.")
            elif theme.name == "Pacing":
                actions.append("Review session timing and add structured checkpoints so learners can signal when clarification is needed.")
            elif theme.name == "Technical issues":
                actions.append("Complete a pre-session technology check and provide a simple fallback access guide.")
            else:
                actions.append(f"Review the supporting feedback about {theme.name.lower()} and agree a proportionate change with the delivery team.")
        if not actions:
            actions.append("Maintain the current approach and monitor the same metrics and themes in the next comparable delivery.")
        return actions[:4]

