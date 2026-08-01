import logging

from app.domains.scenario.exceptions import (
    EmptyScenarioGenerationResponseError,
    InvalidScenarioGenerationDataError,
    InvalidScenarioGenerationJsonError,
)
from app.domains.scenario.schemas import (
    ScenarioGeneratedFields,
    ScenarioGenerateRequest,
)
from app.llm.observability import generate_with_observability
from app.llm.provider import LLMProvider
from app.llm.structured_json import parse_structured_json
from app.prompts.scenario import ScenarioPromptBuilder

logger = logging.getLogger(__name__)


class ScenarioGenerator:
    def __init__(
        self,
        prompt_builder: ScenarioPromptBuilder,
        llm_provider: LLMProvider,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider

    def generate(
        self,
        request: ScenarioGenerateRequest,
    ) -> ScenarioGeneratedFields:
        raw_response = generate_with_observability(
            self._llm_provider,
            logger,
            "scenario_generation",
            system_prompt=self._prompt_builder.build_system_prompt(),
            user_prompt=self._prompt_builder.build_user_prompt(request),
            temperature=0.0,
        )
        return parse_structured_json(
            raw_response,
            ScenarioGeneratedFields,
            logger=logger,
            operation="scenario_generation",
            empty_response_error=EmptyScenarioGenerationResponseError,
            invalid_json_error=InvalidScenarioGenerationJsonError,
            invalid_data_error=InvalidScenarioGenerationDataError,
        )
