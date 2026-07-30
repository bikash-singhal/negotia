from app.domains.memory.models import NegotiatorMemoryRecord


class NegotiatorMemoryRepository:
    def __init__(self) -> None:
        self._records: list[NegotiatorMemoryRecord] = []

    def create(
        self,
        record: NegotiatorMemoryRecord,
    ) -> NegotiatorMemoryRecord:
        self._records.append(record)
        return record

    def get_latest(self) -> NegotiatorMemoryRecord | None:
        if not self._records:
            return None
        return self._records[-1]

    def list_all(self) -> list[NegotiatorMemoryRecord]:
        return list(self._records)
