from app.domains.scenario.models import ScenarioDifficulty
from app.domains.scenario.schemas import ScenarioGenerateRequest
from app.prompts.scenario import ScenarioPromptBuilder


def _request() -> ScenarioGenerateRequest:
    return ScenarioGenerateRequest(
        title="Salary negotiation at Microsoft",
        difficulty=ScenarioDifficulty.INTERMEDIATE,
        description="Negotiate an improved compensation package professionally.",
    )


def test_system_prompt_requires_exact_json_only_contract() -> None:
    prompt = ScenarioPromptBuilder().build_system_prompt()

    assert "exactly one valid JSON object" in prompt
    assert "DO NOT wrap the JSON in Markdown" in prompt
    assert "DO NOT include a preamble" in prompt
    assert '"industry"' in prompt
    assert '"opponent_role"' in prompt
    assert '"objective"' in prompt
    assert '"personality"' in prompt
    assert '"negotiation_style"' in prompt
    assert '"constraints"' in prompt
    assert '"hidden_context"' in prompt
    assert '"walk_away_conditions"' in prompt
    assert "do not include additional keys" in prompt


def test_user_prompt_contains_only_user_scenario_context() -> None:
    prompt = ScenarioPromptBuilder().build_user_prompt(_request())

    assert "Title: Salary negotiation at Microsoft" in prompt
    assert "Difficulty: intermediate" in prompt
    assert "Description: Negotiate an improved compensation package" in prompt


def test_prompts_are_deterministic() -> None:
    builder = ScenarioPromptBuilder()

    assert builder.build_system_prompt() == builder.build_system_prompt()
    assert builder.build_user_prompt(_request()) == builder.build_user_prompt(
        _request()
    )
