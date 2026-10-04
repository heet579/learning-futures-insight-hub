import json
import os
from openai import AzureOpenAI
from src.ai.base_provider import DraftTextProvider, DRAFT_SYSTEM_PROMPT, minimised_context
from src.models import AnalysisContext

class AzureAIProvider(DraftTextProvider):
    """Optional approved Azure OpenAI adapter; never selected without explicit UI consent."""
    name = "Approved External Provider"

    def __init__(self) -> None:
        required = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"]
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise ValueError("Azure provider is not configured: " + ", ".join(missing))
        self.deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        self.client = AzureOpenAI(
            timeout=45,
            max_retries=1,
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        )

    def _request(self, task: str, context: AnalysisContext, audience: str) -> str:
        response = self.client.chat.completions.create(
            model=self.deployment,
            temperature=0,
            messages=[
                {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
                {"role": "user", "content": f"Task: {task}\nAudience: {audience}\nAnalysis:\n{json.dumps(minimised_context(context))}"},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The approved provider returned an empty response.")
        return content.strip()
