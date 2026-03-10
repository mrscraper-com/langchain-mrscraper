"""
Integration tests for langchain-mrscraper tools.

These tests hit the REAL MrScraper API. They require a valid
MRSCRAPER_API_TOKEN environment variable.

Run with:
    MRSCRAPER_API_TOKEN=your_token pytest tests/integration_tests/ -m integration -v
"""

from __future__ import annotations

import json
import os

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
    async def test_fetch_html_returns_html(self, fetch_tool):
        result = await fetch_tool.ainvoke({"url": "https://books.toscrape.com/"})
        parsed = json.loads(result)
        assert parsed["status_code"] == 200
        assert "<html" in parsed["data"].lower()

    async def test_fetch_html_with_geo_code(self, fetch_tool):
        result = await fetch_tool.ainvoke({
            "url": "https://books.toscrape.com/",
            "geo_code": "US",
            "timeout": 60,
        })
        parsed = json.loads(result)
        assert parsed["status_code"] == 200


@pytest.mark.integration
@pytest.mark.asyncio
class TestGetAllResultsIntegration:
    async def test_get_all_results_returns_data(self, get_all_results_tool):
        result = await get_all_results_tool.ainvoke({
            "page": 1,
            "page_size": 5,
        })
        parsed = json.loads(result)
        assert parsed["status_code"] == 200
        assert "data" in parsed
