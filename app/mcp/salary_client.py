import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)

MCP_SALARY_TOOL = "get_salary_data"
_VALID_LEVELS = frozenset({"junior", "mid", "senior", "lead", "principal"})
_VALID_WORKPLACES = frozenset({"remote", "hybrid", "onsite"})


@dataclass(frozen=True)
class SalaryDataQuery:
    tag: str | None = None
    level: str | None = None
    workplace: str | None = None
    company: str | None = None

    def as_arguments(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "tag": self.tag,
                "level": self.level,
                "workplace": self.workplace,
                "company": self.company,
            }.items()
            if value is not None
        }


@dataclass(frozen=True)
class SalaryMarketData:
    average: int
    median: int
    p25: int
    p75: int
    minimum: int
    maximum: int
    count: int

    @classmethod
    def from_mapping(cls, value: object) -> "SalaryMarketData":
        if not isinstance(value, dict):
            raise TypeError("Salary tool result must be an object.")

        fields = {
            "average": "average",
            "median": "median",
            "p25": "p25",
            "p75": "p75",
            "min": "minimum",
            "max": "maximum",
            "count": "count",
        }
        parsed: dict[str, int] = {}
        for source_name, destination_name in fields.items():
            raw = value.get(source_name)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise TypeError(f"Salary tool field '{source_name}' is invalid.")
            if raw < 0 or int(raw) != raw:
                raise ValueError(f"Salary tool field '{source_name}' is invalid.")
            parsed[destination_name] = int(raw)

        if not parsed["minimum"] <= parsed["p25"] <= parsed["median"] <= parsed["p75"] <= parsed["maximum"]:
            raise ValueError("Salary tool percentiles are inconsistent.")

        return cls(**parsed)


class SalaryDataClient(Protocol):
    def get_salary_data(self, query: SalaryDataQuery) -> SalaryMarketData | None: ...


class McpSalaryDataClient:
    def __init__(
        self,
        *,
        enabled: bool,
        endpoint: str,
        timeout_seconds: float,
    ) -> None:
        self._enabled = enabled
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds

    def get_salary_data(self, query: SalaryDataQuery) -> SalaryMarketData | None:
        if not self._enabled:
            return None

        try:
            query = validate_query(query)
            result = asyncio.run(
                asyncio.wait_for(
                    self._call_tool(query),
                    timeout=self._timeout_seconds,
                )
            )
            return SalaryMarketData.from_mapping(_extract_result_mapping(result))
        except Exception as exc:  # noqa: BLE001 - external MCP failures must not block turns.
            logger.warning(
                "MCP salary lookup unavailable; continuing without market data (%s).",
                type(exc).__name__,
            )
            return None

    async def _call_tool(self, query: SalaryDataQuery) -> object:
        # Imported lazily so a disabled local configuration does not initialize
        # the external transport during application startup.
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        async with streamable_http_client(self._endpoint) as (
            read_stream,
            write_stream,
        ), ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(
                MCP_SALARY_TOOL,
                query.as_arguments(),
            )


def validate_query(query: SalaryDataQuery) -> SalaryDataQuery:
    if query.level is not None and query.level not in _VALID_LEVELS:
        raise ValueError("Unsupported salary level.")
    if query.workplace is not None and query.workplace not in _VALID_WORKPLACES:
        raise ValueError("Unsupported salary workplace.")
    return query


def _extract_result_mapping(result: object) -> dict[str, Any]:
    if isinstance(result, dict):
        structured_content = result.get("structured_content") or result.get(
            "structuredContent"
        )
    else:
        structured_content = getattr(result, "structured_content", None) or getattr(
            result,
            "structuredContent",
            None,
        )

    if isinstance(structured_content, dict):
        return structured_content

    content = (
        result.get("content")
        if isinstance(result, dict)
        else getattr(result, "content", None)
    )
    if not isinstance(content, list):
        raise TypeError("Salary tool result does not contain structured content.")

    for item in content:
        text = (
            item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
        )
        if not isinstance(text, str):
            continue
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Salary tool result does not contain JSON data.")
