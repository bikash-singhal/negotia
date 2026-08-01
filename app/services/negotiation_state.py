import json
import logging

from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.observability import log_event
from app.domains.negotiation_state.exceptions import (
    EmptyNegotiationStateResponseError,
    InvalidNegotiationStateDataError,
    InvalidNegotiationStateJsonError,
)
from app.domains.negotiation_state.models import NegotiationState
from app.domains.negotiation_turn.models import NegotiationTurn
from app.llm.observability import generate_with_observability
from app.llm.provider import LLMProvider
from app.prompts.negotiation_state import NegotiationStatePromptBuilder

logger = logging.getLogger(__name__)


class _NegotiationStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latest_user_position: str | None
    latest_opponent_position: str | None
    agreements: list[str]
    open_topics: list[str]
    unresolved_items: list[str]
    negotiation_stage: str


class NegotiationStateExtractor:
    def __init__(
        self,
        prompt_builder: NegotiationStatePromptBuilder,
        llm_provider: LLMProvider,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider

    def extract(self, turns: list[NegotiationTurn]) -> NegotiationState:
        raw_response = generate_with_observability(
            self._llm_provider,
            logger,
            "negotiation_state_extraction",
            system_prompt=self._prompt_builder.build_system_prompt(),
            user_prompt=self._prompt_builder.build_user_prompt(turns),
            session_id=turns[0].session_id if turns else None,
            temperature=0.0,
        )
        response = raw_response.strip()
        if not response:
            _log_parse_failure(
                turns,
                output_length=len(raw_response),
                fence_detected=False,
                failure_category="empty_output",
            )
            raise EmptyNegotiationStateResponseError()

        normalized_response, fence_detected = _remove_outer_json_fence(response)
        try:
            data = json.loads(normalized_response)
        except json.JSONDecodeError:
            _log_parse_failure(
                turns,
                output_length=len(raw_response),
                fence_detected=fence_detected,
                failure_category="invalid_json",
            )
            raise InvalidNegotiationStateJsonError() from None

        try:
            payload = _NegotiationStatePayload.model_validate(data)
        except ValidationError:
            _log_parse_failure(
                turns,
                output_length=len(raw_response),
                fence_detected=fence_detected,
                failure_category="invalid_schema",
            )
            raise InvalidNegotiationStateDataError() from None

        return NegotiationState(
            latest_user_position=payload.latest_user_position,
            latest_opponent_position=payload.latest_opponent_position,
            agreements=payload.agreements,
            open_topics=payload.open_topics,
            unresolved_items=payload.unresolved_items,
            negotiation_stage=payload.negotiation_stage,
        )


def _remove_outer_json_fence(response: str) -> tuple[str, bool]:
    fence_detected = "```" in response
    if not response.startswith("```") or not response.endswith("```"):
        return response, fence_detected

    opening_line, separator, fenced_content = response.partition("\n")
    if not separator or opening_line.strip().lower() not in {"```", "```json"}:
        return response, fence_detected

    return fenced_content.removesuffix("```").strip(), True


def _log_parse_failure(
    turns: list[NegotiationTurn],
    *,
    output_length: int,
    fence_detected: bool,
    failure_category: str,
) -> None:
    log_event(
        logger,
        logging.WARNING,
        "negotiation_state_parse_failed",
        operation="negotiation_state_extraction",
        session_id=turns[0].session_id if turns else None,
        stage="state_parsing",
        output_length=output_length,
        fence_detected=fence_detected,
        failure_category=failure_category,
        outcome="failure",
    )
