from __future__ import annotations

from research.netconfeval_repro.adapters import ChatMessage, ModelResponse


def test_adapter_dataclasses_are_importable() -> None:
    message = ChatMessage(role="user", content="hello")
    response = ModelResponse(content="{}", prompt_tokens=1, completion_tokens=2)

    assert message.role == "user"
    assert response.completion_tokens == 2
