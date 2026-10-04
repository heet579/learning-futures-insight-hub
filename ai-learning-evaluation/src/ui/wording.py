"""Product-facing labels, separate from internal provider identifiers."""
import re

REVISION_MODES = {
    'Edit from feedback': 'Local assistant',
    'Manual replacement': 'Human / Copilot replacement',
}


def service_message(error):
    """Keep actionable errors without exposing implementation names in dialogs."""
    text = str(error)
    text = re.sub(r'https://aistudio\.google\.com/apikey\.?', 'your service administrator', text)
    text = re.sub(r'gemini-[\w.-]+', 'the configured cloud model', text)
    text = text.replace('GEMINI_API_KEY', 'the service access key').replace('GEMINI_MODEL', 'the service configuration')
    for name in ('Azure OpenAI', 'Azure AI', 'Claude AI', 'Gemini', 'Claude', 'OpenAI', 'Anthropic'):
        text = text.replace(name, 'The service')
    text = text.replace('the configured cloud model', 'the configured service')
    text = text.replace('or use local insights', 'or try again later').replace('Use local insights or try again', 'Please try again')
    text = text.replace('Your local analysis is still available.', 'Your survey overview is still available.')
    text = text.replace('The local assistant supports:', 'Supported edits:').replace('Copilot replacement', 'replacement section')
    return text
