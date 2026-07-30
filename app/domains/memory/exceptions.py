from uuid import UUID


class EmptyMemoryHistoryError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Memory extraction requires persisted debrief and strategy records."
        )


class DuplicateMemoryDebriefSessionError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            f"Memory input contains duplicate debriefs for session '{session_id}'."
        )


class DuplicateMemoryStrategySessionError(Exception):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(
            f"Memory input contains duplicate strategies for session '{session_id}'."
        )


class MismatchedMemoryArtifactSetError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Memory generation requires matching debrief and strategy session sets."
        )


class EmptyMemoryResponseError(Exception):
    def __init__(self) -> None:
        super().__init__("The LLM provider returned an empty memory response.")


class InvalidMemoryJsonError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "The LLM provider returned invalid JSON for memory extraction."
        )


class InvalidMemoryDataError(Exception):
    def __init__(self) -> None:
        super().__init__("The LLM provider returned structurally invalid memory data.")


class MemorySessionsAnalyzedMismatchError(Exception):
    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            "The extracted memory session count does not match the supplied history."
        )


class InsufficientMemoryHistoryError(Exception):
    def __init__(self, session_count: int) -> None:
        self.session_count = session_count
        super().__init__(
            "Memory generation requires at least two completed negotiation sessions."
        )


class NegotiatorMemoryAlreadyExistsError(Exception):
    def __init__(self, trigger_session_id: UUID) -> None:
        self.trigger_session_id = trigger_session_id
        super().__init__(
            "A negotiator Memory record already exists for completion trigger "
            f"'{trigger_session_id}'."
        )
