import pytest

from src.llm.prompt import load_prompt


@pytest.mark.parametrize("name", ["chat_system_v1", "categorize_system_v1"])
def test_load_prompt_returns_existing_prompt(name: str) -> None:
    assert load_prompt(name)


def test_load_prompt_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Prompt sconosciuto"):
        load_prompt("../config")
