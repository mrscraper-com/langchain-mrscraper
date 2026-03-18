"""
Integration tests for langchain-mrscraper tools.

These tests hit the REAL MrScraper API. All API responses are
automatically saved into debug_results/*.json

Run with:
    MRSCRAPER_API_TOKEN=your_token pytest tests/integration_tests/ -m integration -v
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from langchain_mrscraper import (
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


def _parse_result(result):
    """Extract JSON from tool result (handles both raw string and ToolMessage)."""
    content = result.content if hasattr(result, "content") else result
    return json.loads(content)


@pytest.fixture(scope="module")
def api_token():
    if not MRSCRAPER_TOKEN:
        pytest.skip("Set MRSCRAPER_API_TOKEN env var to run integration tests.")
    return MRSCRAPER_TOKEN


@pytest.fixture(scope="module")
def tools(api_token):
    return MrScraperLoader(token=api_token).load()


@pytest.fixture(scope="module")
def fetch_tool(api_token):
    from mrscraper import MrScraper
    client = MrScraper(token=api_token)
    return MrScraperFetchHTMLTool(client=client)


@pytest.fixture(scope="module")
def get_all_results_tool(api_token):
    from mrscraper import MrScraper
    client = MrScraper(token=api_token)
    return MrScraperGetAllResultsTool(client=client)

# Integration tests
@pytest.mark.integration
class TestMrScraperLoaderIntegration:
    def test_load_all_tools(self, tools):
        assert len(tools) == 8
        names = {t.name for t in tools}
        assert "mrscraper_fetch_html" in names
        assert "mrscraper_create_scraper" in names
        assert "mrscraper_get_all_results" in names


@pytest.mark.integration
@pytest.mark.asyncio
class TestFetchHTMLIntegration:
    async def test_fetch_html_returns_200_and_html(self, fetch_tool):
        raw = await fetch_tool.ainvoke({"url": "https://books.toscrape.com/"})
        result = _parse_result(raw)
        save_result("fetch_html_basic", result)

        assert isinstance(result, dict)
        assert result["status_code"] == 200
        assert "data" in result
        assert "<html" in result["data"].lower()

    async def test_fetch_html_respects_geo_code(self, fetch_tool):
        raw = await fetch_tool.ainvoke({
            "url": "https://books.toscrape.com/",
            "geo_code": "US",
            "timeout": 60,
        })
        result = _parse_result(raw)
        save_result("fetch_html_geo_us", result)

        assert isinstance(result, dict)
        assert result["status_code"] == 200
        assert "data" in result


@pytest.mark.integration
@pytest.mark.asyncio
class TestGetAllResultsIntegration:
    async def test_get_all_results_returns_structure(self, get_all_results_tool):
        raw = await get_all_results_tool.ainvoke({
            "page": 1,
            "page_size": 5,
        })
        result = _parse_result(raw)
        save_result("get_all_results", result)

        assert result["status_code"] == 200
        assert "data" in result


@pytest.mark.integration
@pytest.mark.asyncio
class TestCreateScraperIntegration:
    async def test_create_scraper_general_returns_id(self, api_token):
        from mrscraper import MrScraper
        client = MrScraper(token=api_token)
        tool = MrScraperCreateScraperTool(client=client)
        raw = await tool.ainvoke({
            "url": "https://books.toscrape.com/",
            "message": "Extract the main heading text only.",
            "agent": "general",
        })
        result = _parse_result(raw)
        save_result("create_scraper_general", result)

        assert result["status_code"] == 200 or result["status_code"] == 201
        assert "data" in result
        assert "id" in result["data"]["data"] or "scraperId" in result["data"]["data"]
