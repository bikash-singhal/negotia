import asyncio
import json
from types import SimpleNamespace

from app.mcp.salary_client import (
    McpSalaryDataClient,
    SalaryDataQuery,
    SalaryMarketData,
)

VERIFIED_RESULT = {
    "average": 213400,
    "median": 205830,
    "p25": 190000,
    "p75": 241700,
    "min": 87500,
    "max": 365040,
    "count": 121,
}


class StubSalaryClient(McpSalaryDataClient):
    def __init__(self, result: object, timeout_seconds: float = 1.0) -> None:
        super().__init__(
            enabled=True,
            endpoint="https://aidevboard.com/mcp",
            timeout_seconds=timeout_seconds,
        )
        self.result = result
        self.queries: list[SalaryDataQuery] = []

    async def _call_tool(self, query: SalaryDataQuery) -> object:
        self.queries.append(query)
        return self.result


def test_salary_client_maps_verified_structured_result() -> None:
    client = StubSalaryClient({"structuredContent": VERIFIED_RESULT})
    query = SalaryDataQuery(tag="llm", level="senior", workplace="remote")

    result = client.get_salary_data(query)

    assert result == SalaryMarketData(
        average=213400,
        median=205830,
        p25=190000,
        p75=241700,
        minimum=87500,
        maximum=365040,
        count=121,
    )
    assert client.queries == [query]


def test_salary_client_maps_json_tool_content() -> None:
    client = StubSalaryClient({"content": [{"text": json.dumps(VERIFIED_RESULT)}]})

    result = client.get_salary_data(SalaryDataQuery())

    assert result is not None
    assert result.median == 205830


def test_salary_client_maps_official_sdk_structured_content() -> None:
    client = StubSalaryClient(
        SimpleNamespace(structured_content=VERIFIED_RESULT, content=[])
    )

    result = client.get_salary_data(SalaryDataQuery())

    assert result is not None
    assert result.average == 213400


def test_salary_client_returns_none_when_mcp_call_fails() -> None:
    class FailingSalaryClient(StubSalaryClient):
        async def _call_tool(self, query: SalaryDataQuery) -> object:
            raise RuntimeError("MCP unavailable")

    assert FailingSalaryClient(VERIFIED_RESULT).get_salary_data(SalaryDataQuery()) is None


def test_salary_client_returns_none_when_mcp_call_times_out() -> None:
    class SlowSalaryClient(StubSalaryClient):
        async def _call_tool(self, query: SalaryDataQuery) -> object:
            await asyncio.sleep(0.1)
            return VERIFIED_RESULT

    client = SlowSalaryClient(VERIFIED_RESULT, timeout_seconds=0.001)

    assert client.get_salary_data(SalaryDataQuery()) is None
