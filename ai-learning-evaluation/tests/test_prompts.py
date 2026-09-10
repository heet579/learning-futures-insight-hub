from src.ai.prompt_engine import load_prompt

def test_all_five_prompt_purposes_are_available():
    names = ["analysis_prompt", "executive_summary_prompt", "facilitator_prompt", "client_prompt", "recommendations_prompt"]
    for name in names:
        prompt = load_prompt(name)
        assert "Do not invent" in prompt
        assert "human review" in prompt.lower()

