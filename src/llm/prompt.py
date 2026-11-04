from pathlib import Path

_PROMPT_DIR = Path(__file__).parent / "prompts"
_PROMPT_NAMES = {"chat_system_v1", "categorize_system_v1"}


def load_prompt(name: str) -> str:
    if name not in _PROMPT_NAMES:
        raise ValueError(f"Prompt sconosciuto: {name}")
    return (_PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
