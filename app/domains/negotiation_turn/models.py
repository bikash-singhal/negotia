from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class NegotiationTurnSpeaker(StrEnum):
    USER = "user"
    OPPONENT = "opponent"


@dataclass
class NegotiationTurn:
    id: UUID
    session_id: UUID
    speaker: NegotiationTurnSpeaker
    content: str
    turn_number: int
    created_at: datetime
