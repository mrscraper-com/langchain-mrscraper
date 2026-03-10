"""
Unit tests for langchain-mrscraper tools.

These tests do NOT hit the real MrScraper API. They verify that
tool classes are properly structured, have correct schemas, and
behave correctly with mocked responses.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import BaseTool

from langchain_mrscraper import (
    MrScraperBulkRerunAIScraperTool,
    MrScraperBulkRerunManualScraperTool,
    MrScraperCreateScraperTool,
    MrScraperFetchHTMLTool,
    MrScraperGetAllResultsTool,
    MrScraperGetResultByIdTool,
    MrScraperRerunManualScraperTool,
    MrScraperRerunScraperTool,
    load_tools,
)

FAKE_TOKEN = "test-token-abc123"

ALL_TOOL_CLASSES = [
    MrScraperFetchHTMLTool,
    MrScraperCreateScraperTool,
    MrScraperRerunScraperTool,
    MrScraperBulkRerunAIScraperTool,
    MrScraperRerunManualScraperTool,
    MrScraperBulkRerunManualScraperTool,
    MrScraperGetAllResultsTool,
    MrScraperGetResultByIdTool,
]


def _make_mock_client() -> MagicMock:
    """Create a MagicMock that mimics MrScraper with async methods."""
    client = MagicMock()
    fake_response: dict[str, Any] = {
        "status_code": 200,
        "data": "<html><body>Hello</body></html>",
        "headers": {"content-type": "text/html"},
    }
    client.fetch_html = AsyncMock(return_value=fake_response)
    client.create_scraper = AsyncMock(return_value=fake_response)
    client.rerun_scraper = AsyncMock(return_value=fake_response)
    client.bulk_rerun_ai_scraper = AsyncMock(return_value=fake_response)
    client.rerun_manual_scraper = AsyncMock(return_value=fake_response)
    client.bulk_rerun_manual_scraper = AsyncMock(return_value=fake_response)
    client.get_all_results = AsyncMock(return_value=fake_response)
    client.get_result_by_id = AsyncMock(return_value=fake_response)
    return client


# ---------------------------------------------------------------------------
# Test: all tools are BaseTool subclasses
# ---------------------------------------------------------------------------


class TestToolStructure:
    """Verify that every tool has the correct class hierarchy and properties."""

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_is_base_tool_subclass(self, tool_cls):
        assert issubclass(tool_cls, BaseTool)

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_has_name(self, tool_cls):
        tool = tool_cls(client=_make_mock_client())
        assert isinstance(tool.name, str)
        assert len(tool.name) > 0
        assert tool.name.startswith("mrscraper_")

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_has_description(self, tool_cls):
        tool = tool_cls(client=_make_mock_client())
        assert isinstance(tool.description, str)
        assert len(tool.description) > 10

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_has_args_schema(self, tool_cls):
        tool = tool_cls(client=_make_mock_client())
        assert tool.args_schema is not None
        schema = tool.args_schema.model_json_schema()
        assert "properties" in schema

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_tool_name_is_unique(self, tool_cls):
        """Each tool class should have a distinct name."""
        client = _make_mock_client()
        names = [cls(client=client).name for cls in ALL_TOOL_CLASSES]
        assert len(names) == len(set(names)), "Duplicate tool names found"


# ---------------------------------------------------------------------------
# Test: load_tools factory
# ---------------------------------------------------------------------------


class TestLoadTools:
    def test_load_tools_with_token(self):
        with patch("langchain_mrscraper.tools.MrScraper") as MockCls:
            MockCls.return_value = _make_mock_client()
            tools = load_tools(token=FAKE_TOKEN)
            assert len(tools) == 8
            MockCls.assert_called_once_with(token=FAKE_TOKEN)

    def test_load_tools_with_client(self):
        client = _make_mock_client()
        tools = load_tools(client=client)
        assert len(tools) == 8

    def test_load_tools_filter_by_name(self):
        client = _make_mock_client()
        tools = load_tools(client=client, tool_names=["mrscraper_fetch_html"])
        assert len(tools) == 1
        assert tools[0].name == "mrscraper_fetch_html"

    def test_load_tools_filter_multiple(self):
        client = _make_mock_client()
        tools = load_tools(
            client=client,
            tool_names=["mrscraper_fetch_html", "mrscraper_get_result_by_id"],
        )
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"mrscraper_fetch_html", "mrscraper_get_result_by_id"}

    def test_load_tools_empty_filter(self):
        client = _make_mock_client()
        tools = load_tools(client=client, tool_names=[])
        assert len(tools) == 0

    def test_load_tools_no_token_no_client_raises(self):
        with pytest.raises(ValueError, match="Either token or client"):
            load_tools()


# ---------------------------------------------------------------------------
# Test: tool schemas have correct required/optional fields
# ---------------------------------------------------------------------------


class TestToolSchemas:
    def test_fetch_html_schema(self):
        tool = MrScraperFetchHTMLTool(client=_make_mock_client())
        schema = tool.args_schema.model_json_schema()
        assert "url" in schema["required"]
        props = schema["properties"]
        assert "url" in props
        assert "timeout" in props
        assert "geo_code" in props
        assert "block_resources" in props

    def test_create_scraper_schema(self):
        tool = MrScraperCreateScraperTool(client=_make_mock_client())
        schema = tool.args_schema.model_json_schema()
        assert "url" in schema["required"]
        assert "message" in schema["required"]
        props = schema["properties"]
        assert "agent" in props
        assert "proxy_country" in props

    def test_rerun_scraper_schema(self):
        tool = MrScraperRerunScraperTool(client=_make_mock_client())
        schema = tool.args_schema.model_json_schema()
        assert "scraper_id" in schema["required"]
        assert "url" in schema["required"]

    def test_bulk_rerun_ai_schema(self):
        tool = MrScraperBulkRerunAIScraperTool(client=_make_mock_client())
        schema = tool.args_schema.model_json_schema()
        assert "scraper_id" in schema["required"]
        assert "urls" in schema["required"]

    def test_rerun_manual_schema(self):
        tool = MrScraperRerunManualScraperTool(client=_make_mock_client())
        schema = tool.args_schema.model_json_schema()
        assert "scraper_id" in schema["required"]
        assert "url" in schema["required"]

    def test_bulk_rerun_manual_schema(self):
        tool = MrScraperBulkRerunManualScraperTool(client=_make_mock_client())
        schema = tool.args_schema.model_json_schema()
        assert "scraper_id" in schema["required"]
        assert "urls" in schema["required"]

    def test_get_all_results_schema_all_optional(self):
        tool = MrScraperGetAllResultsTool(client=_make_mock_client())
        schema = tool.args_schema.model_json_schema()
        assert schema.get("required") is None or len(schema.get("required", [])) == 0

    def test_get_result_by_id_schema(self):
        tool = MrScraperGetResultByIdTool(client=_make_mock_client())
        schema = tool.args_schema.model_json_schema()
        assert "result_id" in schema["required"]


# ---------------------------------------------------------------------------
# Test: tool invocation with mocked client (async)
# ---------------------------------------------------------------------------


class TestToolInvocation:
    @pytest.mark.asyncio
    async def test_fetch_html_invoke(self):
        client = _make_mock_client()
        tool = MrScraperFetchHTMLTool(client=client)
        result = await tool.ainvoke({"url": "https://example.com"})
        client.fetch_html.assert_awaited_once()
        parsed = json.loads(result)
        assert parsed["status_code"] == 200

    @pytest.mark.asyncio
    async def test_create_scraper_invoke(self):
        client = _make_mock_client()
        tool = MrScraperCreateScraperTool(client=client)
        result = await tool.ainvoke({
            "url": "https://example.com",
            "message": "Extract product names",
        })
        client.create_scraper.assert_awaited_once()
        parsed = json.loads(result)
        assert parsed["status_code"] == 200

    @pytest.mark.asyncio
    async def test_rerun_scraper_invoke(self):
        client = _make_mock_client()
        tool = MrScraperRerunScraperTool(client=client)
        result = await tool.ainvoke({
            "scraper_id": "abc-123",
            "url": "https://example.com",
        })
        client.rerun_scraper.assert_awaited_once()
        parsed = json.loads(result)
        assert parsed["status_code"] == 200

    @pytest.mark.asyncio
    async def test_bulk_rerun_ai_invoke(self):
        client = _make_mock_client()
        tool = MrScraperBulkRerunAIScraperTool(client=client)
        result = await tool.ainvoke({
            "scraper_id": "abc-123",
            "urls": ["https://a.com", "https://b.com"],
        })
        client.bulk_rerun_ai_scraper.assert_awaited_once()
        parsed = json.loads(result)
        assert parsed["status_code"] == 200

    @pytest.mark.asyncio
    async def test_rerun_manual_invoke(self):
        client = _make_mock_client()
        tool = MrScraperRerunManualScraperTool(client=client)
        result = await tool.ainvoke({
            "scraper_id": "manual-123",
            "url": "https://example.com",
        })
        client.rerun_manual_scraper.assert_awaited_once()
        parsed = json.loads(result)
        assert parsed["status_code"] == 200

    @pytest.mark.asyncio
    async def test_bulk_rerun_manual_invoke(self):
        client = _make_mock_client()
        tool = MrScraperBulkRerunManualScraperTool(client=client)
        result = await tool.ainvoke({
            "scraper_id": "manual-123",
            "urls": ["https://a.com", "https://b.com"],
        })
        client.bulk_rerun_manual_scraper.assert_awaited_once()
        parsed = json.loads(result)
        assert parsed["status_code"] == 200

    @pytest.mark.asyncio
    async def test_get_all_results_invoke(self):
        client = _make_mock_client()
        tool = MrScraperGetAllResultsTool(client=client)
        result = await tool.ainvoke({})
        client.get_all_results.assert_awaited_once()
        parsed = json.loads(result)
        assert parsed["status_code"] == 200

    @pytest.mark.asyncio
    async def test_get_result_by_id_invoke(self):
        client = _make_mock_client()
        tool = MrScraperGetResultByIdTool(client=client)
        result = await tool.ainvoke({"result_id": "res-456"})
        client.get_result_by_id.assert_awaited_once()
        parsed = json.loads(result)
        assert parsed["status_code"] == 200


# ---------------------------------------------------------------------------
# Test: tool_call format (as LLM would generate)
# ---------------------------------------------------------------------------


class TestToolCallFormat:
    @pytest.mark.asyncio
    async def test_invoke_with_tool_call(self):
        """Tools should accept a model-generated ToolCall dict."""
        client = _make_mock_client()
        tool = MrScraperFetchHTMLTool(client=client)
        tool_call = {
            "args": {"url": "https://example.com"},
            "id": "call_123",
            "name": "mrscraper_fetch_html",
            "type": "tool_call",
        }
        result = await tool.ainvoke(tool_call)
        client.fetch_html.assert_awaited_once()
        assert "status_code" in result


# ---------------------------------------------------------------------------
# Test: exports from __init__.py
# ---------------------------------------------------------------------------


class TestExports:
    def test_all_tool_classes_exported(self):
        import langchain_mrscraper
        for cls in ALL_TOOL_CLASSES:
            assert hasattr(langchain_mrscraper, cls.__name__)

    def test_load_tools_exported(self):
        import langchain_mrscraper
        assert hasattr(langchain_mrscraper, "load_tools")

    def test_version_exported(self):
        import langchain_mrscraper
        assert hasattr(langchain_mrscraper, "__version__")
        assert isinstance(langchain_mrscraper.__version__, str)
