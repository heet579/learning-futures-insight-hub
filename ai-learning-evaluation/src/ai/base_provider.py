from abc import ABC, abstractmethod
from src.models import AnalysisContext

DRAFT_SYSTEM_PROMPT = (
    "You prepare evidence-grounded learner evaluation drafts. Use only supplied JSON; "
    "do not invent facts or causes; do not expose personal information; state uncertainty "
    "when evidence is insufficient; recommendations are advisory and require human review."
)


class AIProvider(ABC):
    name: str

    @abstractmethod
    def executive_summary(self, context: AnalysisContext, audience: str) -> str: ...

    @abstractmethod
    def recommendations(self, context: AnalysisContext, audience: str) -> list[str]: ...


class DraftTextProvider(AIProvider):
    """Shared summary/recommendations wrapping for providers that return plain text."""

    def _request(self, task: str, context: AnalysisContext, audience: str) -> str: ...

    def executive_summary(self, context: AnalysisContext, audience: str) -> str:
        return self._request("Write a concise executive summary with inline metric/theme evidence.", context, audience)

    def recommendations(self, context: AnalysisContext, audience: str) -> list[str]:
        text = self._request("Return up to four concise recommendations, one per line.", context, audience)
        return [line.lstrip("-• 0123456789.\t") for line in text.splitlines() if line.strip()][:4]


def minimised_context(context: AnalysisContext) -> dict:
    """Aggregate-only payload for external providers; raw comments never leave the device."""
    return {
        "course_name": context.course_name,
        "metrics": context.metrics,
        "themes": [
            {"name": t.name, "keywords": t.keywords, "frequency": t.frequency, "category": t.category}
            for t in context.themes
        ],
        "warnings": context.warnings,
    }

