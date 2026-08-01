import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.domains.coach.exceptions import (
    EmptyCoachObservationResponseError,
    InvalidCoachObservationDataError,
    InvalidCoachObservationJsonError,
)
from app.domains.coach.models import CoachObservation, CoachObservationRecord
from app.domains.debrief.exceptions import (
    EmptyDebriefResponseError,
    InvalidDebriefDataError,
    InvalidDebriefJsonError,
)
from app.domains.debrief.models import NegotiationDebrief, NegotiationDebriefRecord
from app.domains.memory.exceptions import (
    EmptyMemoryResponseError,
    InvalidMemoryDataError,
    InvalidMemoryJsonError,
)
from app.domains.negotiation_state.exceptions import (
    EmptyNegotiationStateResponseError,
    InvalidNegotiationStateDataError,
    InvalidNegotiationStateJsonError,
)
from app.domains.strategy.exceptions import (
    EmptyStrategyResponseError,
    InvalidStrategyDataError,
    InvalidStrategyJsonError,
)
from app.domains.strategy.models import (
    NegotiationStrategy,
    NegotiationStrategyRecord,
    NegotiationTactic,
)
from app.llm.provider import LLMProvider
from app.prompts.coach import CoachPromptBuilder
from app.prompts.debrief import DebriefPromptBuilder
from app.prompts.memory import MemoryPromptBuilder
from app.prompts.negotiation_state import NegotiationStatePromptBuilder
from app.prompts.strategy import StrategyPromptBuilder
from app.services.coach import CoachObservationExtractor
from app.services.debrief import DebriefExtractor
from app.services.memory import MemoryExtractor
from app.services.negotiation_state import NegotiationStateExtractor
from app.services.strategy import StrategyExtractor

Invocation = Callable[[], object]
InvocationFactory = Callable[[str], tuple[Invocation, MagicMock]]


@dataclass(frozen=True)
class ExtractorContract:
    name: str
    operation: str
    logger_name: str
    build_invocation: InvocationFactory
    valid_payload: dict[str, object]
    invalid_field: str
    invalid_value: object
    empty_error: type[Exception]
    invalid_json_error: type[Exception]
    invalid_data_error: type[Exception]


def _provider(response: str) -> MagicMock:
    provider = MagicMock(spec=LLMProvider)
    provider.generate.return_value = response
    return provider


def _state_invocation(response: str) -> tuple[Invocation, MagicMock]:
    provider = _provider(response)
    extractor = NegotiationStateExtractor(
        NegotiationStatePromptBuilder(),
        provider,
    )
    return lambda: extractor.extract([]), provider


def _coach_invocation(response: str) -> tuple[Invocation, MagicMock]:
    provider = _provider(response)
    extractor = CoachObservationExtractor(CoachPromptBuilder(), provider)
    return lambda: extractor.extract([], None), provider


def _observation_record() -> CoachObservationRecord:
    return CoachObservationRecord(
        id=uuid4(),
        session_id=uuid4(),
        user_turn_id=uuid4(),
        opponent_turn_id=uuid4(),
        observation=CoachObservation(
            strengths=[],
            weaknesses=[],
            missed_opportunities=[],
            risk_signals=[],
            confidence="low",
        ),
        created_at=datetime.now(UTC),
    )


def _debrief_invocation(response: str) -> tuple[Invocation, MagicMock]:
    provider = _provider(response)
    extractor = DebriefExtractor(DebriefPromptBuilder(), provider)
    observation = _observation_record()
    return lambda: extractor.extract([observation]), provider


def _debrief_record(session_id: UUID | None = None) -> NegotiationDebriefRecord:
    return NegotiationDebriefRecord(
        id=uuid4(),
        session_id=session_id or uuid4(),
        debrief=NegotiationDebrief(
            repeated_strengths=[],
            repeated_weaknesses=[],
            key_missed_opportunities=[],
            recurring_risks=[],
            overall_assessment="Insufficient evidence for a detailed assessment.",
            confidence="low",
        ),
        observation_count=1,
        created_at=datetime.now(UTC),
    )


def _strategy_invocation(response: str) -> tuple[Invocation, MagicMock]:
    provider = _provider(response)
    extractor = StrategyExtractor(StrategyPromptBuilder(), provider)
    debrief = _debrief_record()
    return lambda: extractor.extract(debrief), provider


def _strategy_record(debrief: NegotiationDebriefRecord) -> NegotiationStrategyRecord:
    return NegotiationStrategyRecord(
        id=uuid4(),
        session_id=debrief.session_id,
        debrief_id=debrief.id,
        strategy=NegotiationStrategy(
            primary_objective="Use conditional concessions.",
            expected_outcome="Protect value in future agreements.",
            prioritized_tactics=[
                NegotiationTactic(
                    priority=1,
                    title="Trade rather than concede",
                    rationale="Reciprocity protects value.",
                    actions=["Request reciprocal value."],
                    example_language=["I can agree if you can improve the terms."],
                    success_indicator="Every concession receives value.",
                )
            ],
            long_term_skills=["Concession planning"],
            preparation_checklist=["Define reciprocal asks"],
            avoid_next_time=["Avoid unilateral concessions"],
            confidence="low",
        ),
        created_at=datetime.now(UTC),
    )


def _memory_invocation(response: str) -> tuple[Invocation, MagicMock]:
    provider = _provider(response)
    extractor = MemoryExtractor(MemoryPromptBuilder(), provider)
    debriefs = [_debrief_record(), _debrief_record()]
    strategies = [_strategy_record(debrief) for debrief in debriefs]
    return lambda: extractor.extract(debriefs, strategies), provider


CONTRACTS = [
    ExtractorContract(
        name="negotiation-state",
        operation="negotiation_state_extraction",
        logger_name="app.services.negotiation_state",
        build_invocation=_state_invocation,
        valid_payload={
            "latest_user_position": None,
            "latest_opponent_position": None,
            "agreements": [],
            "open_topics": [],
            "unresolved_items": [],
            "negotiation_stage": "opening",
        },
        invalid_field="agreements",
        invalid_value="invalid",
        empty_error=EmptyNegotiationStateResponseError,
        invalid_json_error=InvalidNegotiationStateJsonError,
        invalid_data_error=InvalidNegotiationStateDataError,
    ),
    ExtractorContract(
        name="coach",
        operation="coach_observation_extraction",
        logger_name="app.services.coach",
        build_invocation=_coach_invocation,
        valid_payload={
            "strengths": [],
            "weaknesses": [],
            "missed_opportunities": [],
            "risk_signals": [],
            "confidence": "low",
        },
        invalid_field="strengths",
        invalid_value="invalid",
        empty_error=EmptyCoachObservationResponseError,
        invalid_json_error=InvalidCoachObservationJsonError,
        invalid_data_error=InvalidCoachObservationDataError,
    ),
    ExtractorContract(
        name="debrief",
        operation="debrief_extraction",
        logger_name="app.services.debrief",
        build_invocation=_debrief_invocation,
        valid_payload={
            "repeated_strengths": [],
            "repeated_weaknesses": [],
            "key_missed_opportunities": [],
            "recurring_risks": [],
            "overall_assessment": "Insufficient evidence.",
            "confidence": "low",
        },
        invalid_field="repeated_strengths",
        invalid_value="invalid",
        empty_error=EmptyDebriefResponseError,
        invalid_json_error=InvalidDebriefJsonError,
        invalid_data_error=InvalidDebriefDataError,
    ),
    ExtractorContract(
        name="strategy",
        operation="strategy_extraction",
        logger_name="app.services.strategy",
        build_invocation=_strategy_invocation,
        valid_payload={
            "primary_objective": "Use conditional concessions.",
            "expected_outcome": "Protect value in future agreements.",
            "prioritized_tactics": [
                {
                    "priority": 1,
                    "title": "Trade rather than concede",
                    "rationale": "Reciprocity protects value.",
                    "actions": ["Request reciprocal value."],
                    "example_language": ["I can agree if you improve the terms."],
                    "success_indicator": "Every concession receives value.",
                }
            ],
            "long_term_skills": ["Concession planning"],
            "preparation_checklist": ["Define reciprocal asks"],
            "avoid_next_time": ["Avoid unilateral concessions"],
            "confidence": "low",
        },
        invalid_field="long_term_skills",
        invalid_value="invalid",
        empty_error=EmptyStrategyResponseError,
        invalid_json_error=InvalidStrategyJsonError,
        invalid_data_error=InvalidStrategyDataError,
    ),
    ExtractorContract(
        name="memory",
        operation="memory_extraction",
        logger_name="app.services.memory",
        build_invocation=_memory_invocation,
        valid_payload={
            "recurring_strengths": [],
            "recurring_weaknesses": [],
            "improving_skills": [],
            "persistent_risks": [],
            "priority_focus_areas": [],
            "recommended_drills": [],
            "sessions_analyzed": 2,
            "confidence": "low",
        },
        invalid_field="sessions_analyzed",
        invalid_value="invalid",
        empty_error=EmptyMemoryResponseError,
        invalid_json_error=InvalidMemoryJsonError,
        invalid_data_error=InvalidMemoryDataError,
    ),
]


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_accepts_valid_raw_json(
    contract: ExtractorContract,
) -> None:
    invoke, provider = contract.build_invocation(json.dumps(contract.valid_payload))

    invoke()

    assert provider.generate.call_args.kwargs["temperature"] == 0.0


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_accepts_surrounding_whitespace(
    contract: ExtractorContract,
) -> None:
    response = f" \n{json.dumps(contract.valid_payload)}\n "
    invoke, _ = contract.build_invocation(response)

    invoke()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_accepts_one_outer_json_fence(
    contract: ExtractorContract,
) -> None:
    response = f"```json\n{json.dumps(contract.valid_payload)}\n```"
    invoke, _ = contract.build_invocation(response)

    invoke()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_rejects_blank_response(
    contract: ExtractorContract,
) -> None:
    invoke, _ = contract.build_invocation("   \n")

    with pytest.raises(contract.empty_error):
        invoke()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_rejects_malformed_json(
    contract: ExtractorContract,
) -> None:
    invoke, _ = contract.build_invocation("{not valid JSON}")

    with pytest.raises(contract.invalid_json_error):
        invoke()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_rejects_explanatory_preamble(
    contract: ExtractorContract,
) -> None:
    response = "Here is the requested output:\n" + json.dumps(contract.valid_payload)
    invoke, _ = contract.build_invocation(response)

    with pytest.raises(contract.invalid_json_error):
        invoke()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_rejects_trailing_commentary(
    contract: ExtractorContract,
) -> None:
    response = json.dumps(contract.valid_payload) + "\nI hope this helps."
    invoke, _ = contract.build_invocation(response)

    with pytest.raises(contract.invalid_json_error):
        invoke()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_rejects_invalid_schema(
    contract: ExtractorContract,
) -> None:
    payload = dict(contract.valid_payload)
    payload[contract.invalid_field] = contract.invalid_value
    invoke, _ = contract.build_invocation(json.dumps(payload))

    with pytest.raises(contract.invalid_data_error):
        invoke()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_rejects_additional_keys(
    contract: ExtractorContract,
) -> None:
    payload = dict(contract.valid_payload)
    payload["unexpected"] = "not allowed"
    invoke, _ = contract.build_invocation(json.dumps(payload))

    with pytest.raises(contract.invalid_data_error):
        invoke()


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda case: case.name)
def test_structured_extractor_logs_no_sensitive_raw_output(
    contract: ExtractorContract,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_output = f"sensitive raw {contract.name} model output"
    invoke, _ = contract.build_invocation(sensitive_output)
    target_logger = logging.getLogger(contract.logger_name)
    previous_disabled = target_logger.disabled
    target_logger.disabled = False
    caplog.set_level(logging.WARNING, logger=contract.logger_name)

    try:
        with pytest.raises(contract.invalid_json_error):
            invoke()
    finally:
        target_logger.disabled = previous_disabled

    parse_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "structured_output_parse_failed"
        and getattr(record, "operation", None) == contract.operation
    )
    assert getattr(parse_record, "output_length", None) == len(sensitive_output)
    assert getattr(parse_record, "failure_category", None) == "invalid_json"
    assert sensitive_output not in "\n".join(
        record.getMessage() for record in caplog.records
    )
