from tauri_assistant.rag.prompts import SYSTEM_PROMPT, build_system_prompt


def test_build_system_prompt_with_empty_context_returns_bare_system_prompt() -> None:
    assert build_system_prompt("") == SYSTEM_PROMPT


def test_build_system_prompt_appends_context() -> None:
    result = build_system_prompt("[1] some > heading\nsome text")
    assert result.startswith(SYSTEM_PROMPT)
    assert result == f"{SYSTEM_PROMPT}\n\nContext:\n[1] some > heading\nsome text"
