from dataclasses import dataclass
from typing import NotRequired, TypedDict
from uuid import UUID

from app.domains.debrief.models import NegotiationDebriefRecord
from app.domains.memory.models import NegotiatorMemoryRecord
from app.domains.negotiation.models import NegotiationSession
from app.domains.strategy.models import NegotiationStrategyRecord


class CompletionWorkflowState(TypedDict):
    session_id: UUID
    session: NotRequired[NegotiationSession]
    debrief_record: NotRequired[NegotiationDebriefRecord]
    strategy_record: NotRequired[NegotiationStrategyRecord]
    memory_record: NotRequired[NegotiatorMemoryRecord | None]


class CompletionWorkflowUpdate(TypedDict, total=False):
    session: NegotiationSession
    debrief_record: NegotiationDebriefRecord
    strategy_record: NegotiationStrategyRecord
    memory_record: NegotiatorMemoryRecord | None


@dataclass(frozen=True)
class CompletionWorkflowResult:
    session: NegotiationSession
    debrief_record: NegotiationDebriefRecord
    strategy_record: NegotiationStrategyRecord
    memory_record: NegotiatorMemoryRecord | None
