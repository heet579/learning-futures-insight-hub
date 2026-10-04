import json
import os
from anthropic import Anthropic
from src.ai.base_provider import DraftTextProvider, DRAFT_SYSTEM_PROMPT, minimised_context
from src.models import AnalysisContext


class AnthropicAIProvider(DraftTextProvider):
    """Optional approved Claude adapter; never selected without explicit UI consent."""
    name = "Approved External Provider (Claude)"

    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("Claude provider is not configured: ANTHROPIC_API_KEY")
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
        self.client = Anthropic(api_key=api_key, timeout=45, max_retries=1)

    def _request(self, task: str, context: AnalysisContext, audience: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=DRAFT_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Task: {task}\nAudience: {audience}\nAnalysis:\n{json.dumps(minimised_context(context))}",
            }],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("The Claude provider declined this request.")
        content = next((b.text for b in response.content if b.type == "text"), "")
        if not content:
            raise RuntimeError("The Claude provider returned an empty response.")
        return content.strip()
