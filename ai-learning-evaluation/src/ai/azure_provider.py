import json
import os
from openai import AzureOpenAI
from src.ai.base_provider import AIProvider
from src.models import AnalysisContext

class AzureAIProvider(AIProvider):
    """Optional approved Azure OpenAI adapter; never selected without explicit UI consent."""
    name = "Approved External Provider"

    def __init__(self) -> None:
        required = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"]
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise ValueError("Azure provider is not configured: " + ", ".join(missing))
        self.deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )

    @staticmethod
    def _minimised_context(context: AnalysisContext) -> dict:
        return {
            "course_name": context.course_name,
            "metrics": context.metrics,
            "themes": [
                {"name": t.name, "keywords": t.keywords, "frequency": t.frequency, "category": t.category}
                for t in context.themes
            ],
            "warnings": context.warnings,
        }

    def _request(self, task: str, context: AnalysisContext, audience: str) -> str:
        system = (
            "You prepare evidence-grounded learner evaluation drafts. Use only supplied JSON; "
            "do not invent facts or causes; do not expose personal information; state uncertainty "
            "when evidence is insufficient; recommendations are advisory and require human review."
        )
        response = self.client.chat.completions.create(
            model=self.deployment,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Task: {task}\nAudience: {audience}\nAnalysis:\n{json.dumps(self._minimised_context(context))}"},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The approved provider returned an empty response.")
        return content.strip()

    def executive_summary(self, context: AnalysisContext, audience: str) -> str:
        return self._request("Write a concise executive summary with inline metric/theme evidence.", context, audience)

    def recommendations(self, context: AnalysisContext, audience: str) -> list[str]:
        text = self._request("Return up to four concise recommendations, one per line.", context, audience)
        return [line.lstrip("-• 0123456789.\t") for line in text.splitlines() if line.strip()][:4]
