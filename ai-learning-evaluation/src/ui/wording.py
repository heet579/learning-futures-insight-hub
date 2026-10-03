"""Product-facing labels, separate from internal provider identifiers."""
import re

DRAFT_MODES = {
    'Local analysis': 'Local Analysis',
    'Cloud analysis': 'Gemini',
    'Cloud alternative': 'Claude',
    'Institutional cloud': 'Azure OpenAI',
}
REVISION_MODES = {
    'Local assistant': 'Local assistant',
    'Manual replacement': 'Human / Copilot replacement',
    'Institutional cloud': 'Azure AI',
    'Cloud alternative': 'Claude AI',
}


def service_message(error):
    """Keep actionable errors without exposing implementation names in dialogs."""
    text = str(error)
    text = re.sub(r'https://aistudio\.google\.com/apikey\.?', 'your service administrator', text)
    text = re.sub(r'gemini-[\w.-]+', 'the configured cloud model', text)
    text = text.replace('GEMINI_API_KEY', 'the cloud access key').replace('GEMINI_MODEL', 'the cloud model setting')
    for name in ('Azure OpenAI', 'Azure AI', 'Claude AI', 'Gemini', 'Claude', 'OpenAI', 'Anthropic'):
        text = text.replace(name, 'Cloud service')
    return text
