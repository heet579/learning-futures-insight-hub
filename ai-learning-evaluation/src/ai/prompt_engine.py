from pathlib import Path
from src.config import ROOT

def load_prompt(name: str) -> str:
    path = ROOT / "prompts" / f"{name}.md"
    if not path.exists():
        raise ValueError(f"Unknown prompt template: {name}")
    return path.read_text(encoding="utf-8")

