from abc import ABC, abstractmethod
from src.models import AnalysisContext

class AIProvider(ABC):
    name: str

    @abstractmethod
    def executive_summary(self, context: AnalysisContext, audience: str) -> str: ...

    @abstractmethod
    def recommendations(self, context: AnalysisContext, audience: str) -> list[str]: ...


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

