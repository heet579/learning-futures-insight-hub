from abc import ABC, abstractmethod
from src.models import AnalysisContext

class AIProvider(ABC):
    name: str

    @abstractmethod
    def executive_summary(self, context: AnalysisContext, audience: str) -> str: ...

    @abstractmethod
    def recommendations(self, context: AnalysisContext, audience: str) -> list[str]: ...

