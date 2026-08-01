from collections.abc import Iterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> str: ...

    def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
    ) -> Iterator[str]: ...
