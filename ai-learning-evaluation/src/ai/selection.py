"""Choose the AI service: Claude or Gemini.

AI_PROVIDER=claude or AI_PROVIDER=gemini picks one explicitly. Otherwise Claude is used when
ANTHROPIC_API_KEY is set, else Gemini. Raises ValueError when neither is configured, so callers
fall back to local wording exactly as before.
"""
import os


def ai_provider():
    choice = os.getenv('AI_PROVIDER', '').strip().lower()
    has_claude = bool(os.getenv('ANTHROPIC_API_KEY', '').strip())
    if choice == 'claude' or (choice != 'gemini' and has_claude):
        from src.ai.claude_provider import ClaudeAIProvider
        return ClaudeAIProvider()
    from src.ai.gemini_provider import GeminiAIProvider
    return GeminiAIProvider()
