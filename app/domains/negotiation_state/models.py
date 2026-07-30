from dataclasses import dataclass


@dataclass(frozen=True)
class NegotiationState:
    latest_user_position: str | None
    latest_opponent_position: str | None
    agreements: list[str]
    open_topics: list[str]
    unresolved_items: list[str]
    negotiation_stage: str
