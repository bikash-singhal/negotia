import json

from pydantic import BaseModel, ConfigDict, ValidationError

from app.domains.negotiation_state.exceptions import (
    EmptyNegotiationStateResponseError,
    InvalidNegotiationStateDataError,
    InvalidNegotiationStateJsonError,
)
from app.domains.negotiation_state.models import NegotiationState
from app.domains.negotiation_turn.models import NegotiationTurn
from app.llm.provider import LLMProvider
from app.prompts.negotiation_state import NegotiationStatePromptBuilder


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
        response = self._llm_provider.generate(
            system_prompt=self._prompt_builder.build_system_prompt(),
            user_prompt=self._prompt_builder.build_user_prompt(turns),
        ).strip()
        if not response:
            raise EmptyNegotiationStateResponseError()

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            raise InvalidNegotiationStateJsonError() from None

        try:
            payload = _NegotiationStatePayload.model_validate(data)
        except ValidationError:
            raise InvalidNegotiationStateDataError() from None

        return NegotiationState(
            latest_user_position=payload.latest_user_position,
            latest_opponent_position=payload.latest_opponent_position,
            agreements=payload.agreements,
            open_topics=payload.open_topics,
            unresolved_items=payload.unresolved_items,
            negotiation_stage=payload.negotiation_stage,
        )
