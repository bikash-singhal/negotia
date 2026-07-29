from app.llm.fake import FakeLLMProvider
from app.llm.provider import LLMProvider

EXPECTED_RESPONSE = (
    "I understand your position, but those terms are difficult for us to accept."
)


def test_fake_provider_satisfies_protocol() -> None:
    assert isinstance(FakeLLMProvider(), LLMProvider)


def test_generate_returns_expected_response() -> None:
    provider = FakeLLMProvider()

    response = provider.generate(
        system_prompt="Act as a negotiation counterpart.",
        user_prompt="Can you improve the offer?",
    )

    assert response == EXPECTED_RESPONSE


def test_generate_is_deterministic() -> None:
    provider = FakeLLMProvider()

    first_response = provider.generate(
        system_prompt="First system prompt.",
        user_prompt="First user prompt.",
    )
    second_response = provider.generate(
        system_prompt="Second system prompt.",
        user_prompt="Second user prompt.",
    )

    assert first_response == second_response == EXPECTED_RESPONSE
