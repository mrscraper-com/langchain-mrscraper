"""
Unit tests for langchain-mrscraper tools.

These tests use a real MrScraper client created from an API token.
All API responses are automatically saved into debug_results/*.json

Run with:
    MRSCRAPER_API_TOKEN=your_token pytest tests/unit_tests/ -v
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest
from langchain_core.tools import BaseTool
from mrscraper import MrScraper

from langchain_mrscraper import (
    MrScraperBulkRerunAIScraperTool,
    MrScraperBulkRerunManualScraperTool,
    MrScraperCreateScraperTool,
    MrScraperFetchHTMLTool,
    MrScraperGetAllResultsTool,
    MrScraperGetResultByIdTool,
    MrScraperRerunManualScraperTool,
    MrScraperRerunScraperTool,
    MrScraperLoader,
)

MRSCRAPER_TOKEN = os.environ.get("MRSCRAPER_API_TOKEN", "")
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "debug_results")


def save_result(test_name: str, result: dict):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{test_name}_{timestamp}.json"
    filepath = os.path.join(DEBUG_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved result to: {os.path.abspath(filepath)}\n")


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


@pytest.fixture(scope="module")
def api_token():
    if not MRSCRAPER_TOKEN:
        pytest.skip("Set MRSCRAPER_API_TOKEN env var to run tests.")
    return MRSCRAPER_TOKEN


@pytest.fixture(scope="module")
def client(api_token):
    return MrScraper(token=api_token)


# ---------------------------------------------------------------------------
# Test: all tools are BaseTool subclasses
# ---------------------------------------------------------------------------


class TestToolStructure:
    """Verify that every tool has the correct class hierarchy and properties."""

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_is_base_tool_subclass(self, tool_cls):
        assert issubclass(tool_cls, BaseTool)

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_has_name(self, tool_cls, client):
        tool = tool_cls(client=client)
        assert isinstance(tool.name, str)
        assert len(tool.name) > 0
        assert tool.name.startswith("mrscraper_")

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_has_description(self, tool_cls, client):
        tool = tool_cls(client=client)
        assert isinstance(tool.description, str)
        assert len(tool.description) > 10

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_has_args_schema(self, tool_cls, client):
        tool = tool_cls(client=client)
        assert tool.args_schema is not None
        schema = tool.args_schema.model_json_schema()
        assert "properties" in schema

    @pytest.mark.parametrize("tool_cls", ALL_TOOL_CLASSES)
    def test_tool_name_is_unique(self, tool_cls, client):
        """Each tool class should have a distinct name."""
        names = [cls(client=client).name for cls in ALL_TOOL_CLASSES]
        assert len(names) == len(set(names)), "Duplicate tool names found"


# ---------------------------------------------------------------------------
# Test: MrScraperLoader
# ---------------------------------------------------------------------------


class TestMrScraperLoader:
    def test_load_with_token(self, api_token):
        loader = MrScraperLoader(token=api_token)
        tools = loader.load()
        assert len(tools) == 8

    def test_load_with_client(self, client):
        loader = MrScraperLoader(client=client)
        tools = loader.load()
        assert len(tools) == 8

    def test_load_filter_by_name(self, client):
        loader = MrScraperLoader(client=client, tool_names=["mrscraper_fetch_html"])
        tools = loader.load()
        assert len(tools) == 1
        assert tools[0].name == "mrscraper_fetch_html"

    def test_load_filter_multiple(self, client):
        loader = MrScraperLoader(
            client=client,
            tool_names=["mrscraper_fetch_html", "mrscraper_get_result_by_id"],
        )
        tools = loader.load()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"mrscraper_fetch_html", "mrscraper_get_result_by_id"}

    def test_load_empty_filter(self, client):
        loader = MrScraperLoader(client=client, tool_names=[])
        tools = loader.load()
        assert len(tools) == 0

    def test_load_no_token_no_client_raises(self):
        with pytest.raises(ValueError, match="Either token or client"):
            MrScraperLoader().load()


# ---------------------------------------------------------------------------
# Test: tool schemas have correct required/optional fields
# ---------------------------------------------------------------------------


class TestToolSchemas:
    def test_fetch_html_schema(self, client):
        tool = MrScraperFetchHTMLTool(client=client)
        schema = tool.args_schema.model_json_schema()
        assert "url" in schema["required"]
        props = schema["properties"]
        assert "url" in props
        assert "timeout" in props
        assert "geo_code" in props
        assert "block_resources" in props

    def test_create_scraper_schema(self, client):
        tool = MrScraperCreateScraperTool(client=client)
        schema = tool.args_schema.model_json_schema()
        assert "url" in schema["required"]
        assert "message" in schema["required"]
        props = schema["properties"]
        assert "agent" in props
        assert "proxy_country" in props

    def test_rerun_scraper_schema(self, client):
        tool = MrScraperRerunScraperTool(client=client)
        schema = tool.args_schema.model_json_schema()
        assert "scraper_id" in schema["required"]
        assert "url" in schema["required"]

    def test_bulk_rerun_ai_schema(self, client):
        tool = MrScraperBulkRerunAIScraperTool(client=client)
        schema = tool.args_schema.model_json_schema()
        assert "scraper_id" in schema["required"]
        assert "urls" in schema["required"]

    def test_rerun_manual_schema(self, client):
        tool = MrScraperRerunManualScraperTool(client=client)
        schema = tool.args_schema.model_json_schema()
        assert "scraper_id" in schema["required"]
        assert "url" in schema["required"]

    def test_bulk_rerun_manual_schema(self, client):
        tool = MrScraperBulkRerunManualScraperTool(client=client)
        schema = tool.args_schema.model_json_schema()
        assert "scraper_id" in schema["required"]
        assert "urls" in schema["required"]

    def test_get_all_results_schema_all_optional(self, client):
        tool = MrScraperGetAllResultsTool(client=client)
        schema = tool.args_schema.model_json_schema()
        assert schema.get("required") is None or len(schema.get("required", [])) == 0

    def test_get_result_by_id_schema(self, client):
        tool = MrScraperGetResultByIdTool(client=client)
        schema = tool.args_schema.model_json_schema()
        assert "result_id" in schema["required"]


# ---------------------------------------------------------------------------
# Test: tool invocation with real client (async)
# ---------------------------------------------------------------------------


def _parse_result(result):
    """Extract JSON from tool result (handles both raw string and ToolMessage)."""
    content = result.content if hasattr(result, "content") else result
    return json.loads(content)


class TestToolInvocation:
    @pytest.mark.asyncio
    async def test_fetch_html_invoke(self, client):
        tool = MrScraperFetchHTMLTool(client=client)
        raw = await tool.ainvoke({"url": "https://books.toscrape.com/"})
        result = _parse_result(raw)
        save_result("fetch_html_basic", result)

        assert isinstance(result, dict)
        assert result["status_code"] == 200 or result["status_code"] == 201
        assert "data" in result
        assert "<html" in result["data"].lower()

    @pytest.mark.asyncio
    async def test_get_all_results_invoke(self, client):
        tool = MrScraperGetAllResultsTool(client=client)
        raw = await tool.ainvoke({})
        result = _parse_result(raw)
        save_result("get_all_results", result)

        assert isinstance(result, dict)
        assert result["status_code"] == 200 or result["status_code"] == 201
        assert "data" in result

    @pytest.mark.asyncio
    async def test_create_scraper_invoke(self, client):
        tool = MrScraperCreateScraperTool(client=client)
        raw = await tool.ainvoke({
            "url": "https://books.toscrape.com/",
            "message": "Extract the main heading text only.",
            "agent": "general",
        })
        result = _parse_result(raw)
        save_result("create_scraper_general", result)

        assert isinstance(result, dict)
        assert result["status_code"] == 200 or result["status_code"] == 201
        assert "data" in result
        assert "id" in result["data"]["data"] or "scraperId" in result["data"]["data"]


# ---------------------------------------------------------------------------
# Test: tool_call format (as LLM would generate)
# ---------------------------------------------------------------------------


class TestToolCallFormat:
    @pytest.mark.asyncio
    async def test_invoke_with_tool_call(self, client):
        """Tools should accept a model-generated ToolCall dict."""
        tool = MrScraperFetchHTMLTool(client=client)
        tool_call = {
            "args": {"url": "https://books.toscrape.com/"},
            "id": "call_123",
            "name": "mrscraper_fetch_html",
            "type": "tool_call",
        }
        raw = await tool.ainvoke(tool_call)
        result = _parse_result(raw)
        save_result("fetch_html_tool_call", result)

        assert isinstance(result, dict)
        assert result["status_code"] == 200 or result["status_code"] == 201
        assert "data" in result


# ---------------------------------------------------------------------------
# Test: exports from __init__.py
# ---------------------------------------------------------------------------


class TestExports:
    def test_all_tool_classes_exported(self):
        import langchain_mrscraper
        for cls in ALL_TOOL_CLASSES:
            assert hasattr(langchain_mrscraper, cls.__name__)

    def test_mrscraper_loader_exported(self):
        import langchain_mrscraper
        assert hasattr(langchain_mrscraper, "MrScraperLoader")

    def test_version_exported(self):
        import langchain_mrscraper
        assert hasattr(langchain_mrscraper, "__version__")
        assert isinstance(langchain_mrscraper.__version__, str)
