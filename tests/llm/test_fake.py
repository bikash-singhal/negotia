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


def test_generate_returns_deterministic_debrief_json() -> None:
    provider = FakeLLMProvider()
    system_prompt = "You are an expert negotiation debrief analyst."

    first_response = provider.generate(
        system_prompt=system_prompt,
        user_prompt="First set of stored observations.",
    )
    second_response = provider.generate(
        system_prompt=system_prompt,
        user_prompt="Second set of stored observations.",
    )

    assert first_response == second_response
    assert '"repeated_strengths": []' in first_response
    assert '"confidence": "low"' in first_response


def test_generate_returns_deterministic_strategy_json() -> None:
    provider = FakeLLMProvider()
    system_prompt = "You are an expert negotiation strategy advisor."

    first_response = provider.generate(
        system_prompt=system_prompt,
        user_prompt="First persisted debrief.",
    )
    second_response = provider.generate(
        system_prompt=system_prompt,
        user_prompt="Second persisted debrief.",
    )

    assert first_response == second_response
    assert '"primary_objective"' in first_response
    assert '"expected_outcome"' in first_response
    assert '"prioritized_tactics"' in first_response


def test_generate_returns_deterministic_memory_json() -> None:
    provider = FakeLLMProvider()
    system_prompt = "You are an expert negotiation memory analyst."

    first_response = provider.generate(
        system_prompt=system_prompt,
        user_prompt="First set of persisted artifacts.",
    )
    second_response = provider.generate(
        system_prompt=system_prompt,
        user_prompt="Second set of persisted artifacts.",
    )

    assert first_response == second_response
    assert '"stable_strengths"' in first_response
    assert '"highest_priority_skill"' in first_response
    assert '"sessions_analyzed": 2' in first_response


def test_memory_response_uses_supplied_session_count() -> None:
    response = FakeLLMProvider().generate(
        system_prompt="You are an expert negotiation memory analyst.",
        user_prompt="Persisted artifacts from 3 negotiation sessions\n\n...",
    )

    assert '"sessions_analyzed": 3' in response


def test_stream_returns_deterministic_chunks() -> None:
    provider = FakeLLMProvider()

    first_chunks = list(provider.stream("system", "user"))
    second_chunks = list(provider.stream("different", "prompts"))

    assert first_chunks == second_chunks
    assert len(first_chunks) > 1
    assert "".join(first_chunks) == EXPECTED_RESPONSE
