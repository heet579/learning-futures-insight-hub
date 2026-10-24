"""Claude (Anthropic API) as a drop-in alternative to Gemini.

Same prompts, the same fact sheet (no raw comments) and the same validation as the Gemini
adapter: only the transport differs. Claude is asked to answer through a single forced tool
whose input schema is the JSON schema the app expects, so the answer is always structured.

Configure in .env:  ANTHROPIC_API_KEY=sk-ant-...   (optional) ANTHROPIC_MODEL=claude-haiku-5-5
"""
import os
import re

from src.ai.gemini_provider import GeminiAIProvider

DEFAULT_MODEL = 'claude-haiku-5-5'   # fastest and lowest-cost current Claude model


def _json_schema(schema):
    """Gemini's OpenAPI-style schema (type: "OBJECT") -> standard JSON Schema (type: "object")."""
    if isinstance(schema, dict):
        out = {}
        for key, value in schema.items():
            if key == 'type' and isinstance(value, str):
                out[key] = value.lower()
            else:
                out[key] = _json_schema(value)
        return out
    if isinstance(schema, list):
        return [_json_schema(item) for item in schema]
    return schema


class ClaudeAIProvider(GeminiAIProvider):
    name = 'Claude'

    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY', '').strip().strip('"\'')
        self.model = os.getenv('ANTHROPIC_MODEL', '').strip().strip('"\'') or DEFAULT_MODEL
        if not self.api_key:
            raise ValueError('Set ANTHROPIC_API_KEY in ai-learning-evaluation/.env and restart the app. '
                             'Create a key at https://platform.claude.com/ (API keys).')
        if not re.fullmatch(r'[a-zA-Z0-9._-]+', self.model):
            raise ValueError('ANTHROPIC_MODEL must be a Claude model ID, for example claude-haiku-5-5.')
        self._cache = {}

    # Error messages from the shared validation say "Gemini"; name the right service.
    def _renamed(self, call, *args, **kwargs):
        try:
            return call(*args, **kwargs)
        except RuntimeError as exc:
            raise RuntimeError(str(exc).replace('Gemini', 'Claude')) from None

    def insights(self, context, audience='facilitator'):
        return self._renamed(super().insights, context, audience)

    def answer_question(self, context, question):
        return self._renamed(super().answer_question, context, question)

    def revise_section(self, context, section, current_text, instruction, audience):
        return self._renamed(super().revise_section, context, section, current_text, instruction, audience)

    def _request(self, body):
        import anthropic
        system = ''.join(part.get('text', '') for part in body['systemInstruction']['parts'])
        user = ''.join(part.get('text', '') for part in body['contents'][0]['parts'])
        schema = _json_schema(body['generationConfig']['responseSchema'])
        client = anthropic.Anthropic(api_key=self.api_key, timeout=60, max_retries=1)
        try:
            response = client.messages.create(
                model=self.model, max_tokens=4096, temperature=0, system=system,
                messages=[{'role': 'user', 'content': user}],
                tools=[{'name': 'respond', 'description': 'Return the result in the required structure.',
                        'input_schema': schema}],
                tool_choice={'type': 'tool', 'name': 'respond'},
            )
        except anthropic.AuthenticationError:
            raise RuntimeError('Claude authentication failed. Check ANTHROPIC_API_KEY.') from None
        except anthropic.PermissionDeniedError:
            raise RuntimeError('Claude access denied. Check the key and that the account has credit.') from None
        except anthropic.NotFoundError:
            raise RuntimeError('Claude model unavailable. Update ANTHROPIC_MODEL, for example claude-haiku-5-5.') from None
        except anthropic.RateLimitError:
            raise RuntimeError('Claude rate limit reached. Wait a moment and try again.') from None
        except anthropic.BadRequestError as exc:
            detail = getattr(exc, 'message', '') or str(exc)
            if 'credit' in detail.lower():
                raise RuntimeError('Your Anthropic account has no credit left. Add credit in the Claude Console '
                                   '(Settings > Billing).') from None
            raise RuntimeError(f'Claude rejected the request ({detail[:200]}).') from None
        except (anthropic.APIConnectionError, anthropic.APITimeoutError):
            raise RuntimeError('Could not reach Claude. Check your connection or use local insights.') from None
        except anthropic.APIError:
            raise RuntimeError('Claude is temporarily unavailable. Try again later or use local insights.') from None
        if response.stop_reason == 'refusal':
            raise RuntimeError('Claude declined this request.')
        block = next((b for b in response.content if getattr(b, 'type', '') == 'tool_use'), None)
        if block is None or not isinstance(block.input, dict):
            raise RuntimeError('Claude returned an incomplete response. Your local analysis is still available.')
        return block.input
