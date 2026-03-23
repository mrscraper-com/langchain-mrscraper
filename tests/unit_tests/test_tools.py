"""Unit tests for langchain-mrscraper tools (no real API calls)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import BaseTool

from langchain_mrscraper import (
    MrScraperBulkRerunAIScraper,
    MrScraperBulkRerunManualScraper,
    MrScraperCreateScraper,
    MrScraperFetchHTML,
    MrScraperGetAllResults,
    MrScraperGetResultById,
    MrScraperRerunManualScraper,
    MrScraperRerunScraper,
    MrScraperToolkit,
    load_mrscraper_tools,
)

ALL_TOOL_CLASSES = [
    MrScraperFetchHTML,
    MrScraperCreateScraper,
    MrScraperRerunScraper,
    MrScraperBulkRerunAIScraper,
    MrScraperRerunManualScraper,
    MrScraperBulkRerunManualScraper,
    MrScraperGetAllResults,
    MrScraperGetResultById,
]


@pytest.fixture
def fake_client() -> MagicMock:
    client = MagicMock()
    client.fetch_html = AsyncMock(return_value={"status_code": 200, "data": "<html></html>", "headers": {}})
    client.create_scraper = AsyncMock(return_value={"status_code": 201, "data": {"data": {"id": "scr_1"}}, "headers": {}})
    client.rerun_scraper = AsyncMock(return_value={"status_code": 200, "data": {"id": "run_1"}, "headers": {}})
    client.bulk_rerun_ai_scraper = AsyncMock(return_value={"status_code": 200, "data": {"job_id": "job_ai"}, "headers": {}})
    client.rerun_manual_scraper = AsyncMock(return_value={"status_code": 200, "data": {"id": "run_m1"}, "headers": {}})
    client.bulk_rerun_manual_scraper = AsyncMock(return_value={"status_code": 200, "data": {"job_id": "job_manual"}, "headers": {}})
    client.get_all_results = AsyncMock(return_value={"status_code": 200, "data": {"items": []}, "headers": {}})
    client.get_result_by_id = AsyncMock(return_value={"status_code": 200, "data": {"id": "res_1"}, "headers": {}})
    return client


def _parse_result(content: str) -> dict:
    return json.loads(content)


@pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
def test_tool_structure(tool_cls: type[BaseTool], fake_client: MagicMock) -> None:
    tool = tool_cls(client=fake_client)
    assert isinstance(tool, BaseTool)
    assert tool.name.startswith("mrscraper_")
    assert len(tool.description) > 10
    schema = tool.args_schema.model_json_schema()
    assert "properties" in schema


def test_tool_names_unique(fake_client: MagicMock) -> None:
    names = [cls(client=fake_client).name for cls in ALL_TOOL_CLASSES]
    assert len(names) == len(set(names))


def test_tool_invocation_routes_to_client(fake_client: MagicMock) -> None:
    tool = MrScraperFetchHTML(client=fake_client)
    output = tool.invoke({"url": "https://example.com"})
    parsed = _parse_result(output)
    assert parsed["status_code"] == 200
    fake_client.fetch_html.assert_called_once()
    assert fake_client.fetch_html.call_args.kwargs["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_async_tool_invocation_routes_to_client(fake_client: MagicMock) -> None:
    tool = MrScraperCreateScraper(client=fake_client)
    output = await tool.ainvoke(
        {
            "url": "https://example.com/products",
            "message": "Extract titles and prices",
        }
    )
    parsed = _parse_result(output)
    assert parsed["status_code"] == 201
    fake_client.create_scraper.assert_called_once()
    assert fake_client.create_scraper.call_args.kwargs["url"] == "https://example.com/products"
    assert fake_client.create_scraper.call_args.kwargs["message"] == "Extract titles and prices"


def test_toolkit_get_tools_with_client(fake_client: MagicMock) -> None:
    toolkit = MrScraperToolkit(client=fake_client)
    tools = toolkit.get_tools()
    assert len(tools) == 8


def test_toolkit_filter_by_name(fake_client: MagicMock) -> None:
    toolkit = MrScraperToolkit(client=fake_client, tool_names=["mrscraper_fetch_html"])
    tools = toolkit.get_tools()
    assert [tool.name for tool in tools] == ["mrscraper_fetch_html"]


def test_load_function_raises_without_client_or_token() -> None:
    with patch("langchain_mrscraper.tools.os.getenv", return_value=None):
        with pytest.raises(ValueError, match="Either client, token, or mrscraper_api_key"):
            load_mrscraper_tools()


def test_load_function_creates_client_from_token() -> None:
    with patch("langchain_mrscraper.tools.MrScraper") as mocked_client_cls:
        mocked_client_cls.return_value = MagicMock()
        tools = load_mrscraper_tools(token="token-123")
    assert len(tools) == 8
    mocked_client_cls.assert_called_once_with(token="token-123")


def test_tool_can_init_with_token() -> None:
    fake_client = MagicMock()
    fake_client.fetch_html = AsyncMock(
        return_value={"status_code": 200, "data": "<html></html>", "headers": {}}
    )
    with patch("langchain_mrscraper.tools.MrScraper", return_value=fake_client) as mocked_client_cls:
        tool = MrScraperFetchHTML(token="token-xyz")
        raw = tool.invoke({"url": "https://example.com"})
    parsed = _parse_result(raw)
    assert parsed["status_code"] == 200
    mocked_client_cls.assert_called_once_with(token="token-xyz")


def test_tool_uses_env_api_key_when_token_not_passed() -> None:
    fake_client = MagicMock()
    fake_client.fetch_html = AsyncMock(
        return_value={"status_code": 200, "data": "<html></html>", "headers": {}}
    )
    with patch("langchain_mrscraper.tools.MrScraper", return_value=fake_client) as mocked_client_cls:
        with patch.dict("os.environ", {"MRSCRAPER_API_KEY": "env-key-123"}, clear=False):
            tool = MrScraperFetchHTML()
            tool.invoke({"url": "https://example.com"})
    mocked_client_cls.assert_called_once_with(token="env-key-123")


def test_exports() -> None:
    import langchain_mrscraper

    assert hasattr(langchain_mrscraper, "MrScraperToolkit")
    assert hasattr(langchain_mrscraper, "load_mrscraper_tools")
    assert hasattr(langchain_mrscraper, "__version__")
