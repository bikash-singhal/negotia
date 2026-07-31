from uuid import UUID

from app.domains.negotiation.models import NegotiationStatus


class ScenarioNotFoundError(Exception):
    def __init__(self, scenario_id: UUID) -> None:
        self.scenario_id = scenario_id
        super().__init__(f"Scenario with id '{scenario_id}' was not found.")


class InvalidNegotiationStatusTransitionError(Exception):
    def __init__(
        self,
        session_id: UUID,
        current_status: NegotiationStatus,
        target_status: NegotiationStatus,
    ) -> None:
        self.session_id = session_id
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Negotiation session '{session_id}' cannot transition from "
            f"'{current_status.value}' to '{target_status.value}'."
        )


class NegotiationCompletionWithoutTurnsError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            f"Negotiation session '{session_id}' cannot be completed without turns."
        )


class NegotiationCompletionLatestTurnFromUserError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            f"Negotiation session '{session_id}' cannot be completed while "
            "the latest turn is from the user."
        )


class NegotiationCompletionRequiresExchangeError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            f"Negotiation session '{session_id}' cannot be completed without "
            "a completed user-opponent exchange."
        )


class CompletedNegotiationMissingDebriefError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            f"Completed negotiation session '{session_id}' is missing its debrief."
        )


class CompletedNegotiationMissingStrategyError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            f"Completed negotiation session '{session_id}' is missing its strategy."
        )


class CompletionArtifactsChangedError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            "Negotiation completion artifacts changed during preparation for "
            f"session '{session_id}'; completion must be prepared again."
        )
