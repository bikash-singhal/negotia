import logging

from pydantic import BaseModel, ConfigDict

from app.domains.negotiation_state.exceptions import (
    EmptyNegotiationStateResponseError,
    InvalidNegotiationStateDataError,
    InvalidNegotiationStateJsonError,
)
from app.domains.negotiation_state.models import NegotiationState
from app.domains.negotiation_turn.models import NegotiationTurn
from app.llm.observability import generate_with_observability
from app.llm.provider import LLMProvider
from app.llm.structured_json import parse_structured_json
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
        payload = parse_structured_json(
            raw_response,
            _NegotiationStatePayload,
            logger=logger,
            operation="negotiation_state_extraction",
            session_id=turns[0].session_id if turns else None,
            empty_response_error=EmptyNegotiationStateResponseError,
            invalid_json_error=InvalidNegotiationStateJsonError,
            invalid_data_error=InvalidNegotiationStateDataError,
        )

        return NegotiationState(
            latest_user_position=payload.latest_user_position,
            latest_opponent_position=payload.latest_opponent_position,
            agreements=payload.agreements,
            open_topics=payload.open_topics,
            unresolved_items=payload.unresolved_items,
            negotiation_stage=payload.negotiation_stage,
        )
