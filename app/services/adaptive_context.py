from uuid import UUID

from app.domains.adaptive_context.models import AdaptiveContext
from app.services.memory import MemoryService


class AdaptiveContextService:
    def __init__(self, memory_service: MemoryService) -> None:
        self._memory_service = memory_service

    def get_context(self, user_id: UUID) -> AdaptiveContext | None:
        record = self._memory_service.get_latest(user_id)
        if record is None:
            return None

        memory = record.memory
        return AdaptiveContext(
            focus_areas=list(memory.priority_focus_areas),
            coaching_focus=list(memory.improving_skills),
            opponent_adjustments=list(memory.persistent_risks),
            strengths=list(memory.recurring_strengths),
        )
