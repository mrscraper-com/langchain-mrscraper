"""Integration tests for langchain-mrscraper (real API smoke tests)."""

from __future__ import annotations

import json
import os

import pytest

from langchain_mrscraper import MrScraperCreateScraper, MrScraperToolkit

MRSCRAPER_TOKEN = os.getenv("MRSCRAPER_API_KEY") or os.getenv("MRSCRAPER_API_TOKEN")


def _parse_result(output: str) -> dict:
    return json.loads(output)


@pytest.fixture(scope="module")
def api_token() -> str:
    if not MRSCRAPER_TOKEN:
        pytest.skip("Set MRSCRAPER_API_KEY or MRSCRAPER_API_TOKEN to run integration tests.")
    return MRSCRAPER_TOKEN


@pytest.fixture(scope="module")
def toolkit(api_token: str) -> MrScraperToolkit:
    return MrScraperToolkit(token=api_token)


@pytest.mark.integration
def test_toolkit_loads_all_tools(toolkit: MrScraperToolkit) -> None:
    tools = toolkit.get_tools()
    assert len(tools) == 9
    assert {tool.name for tool in tools} >= {
        "mrscraper_google_serp",
        "mrscraper_fetch_html",
        "mrscraper_create_scraper",
        "mrscraper_get_all_results",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_html_returns_html(toolkit: MrScraperToolkit) -> None:
    tools = {tool.name: tool for tool in toolkit.get_tools()}
    fetch_tool = tools["mrscraper_fetch_html"]
    raw = await fetch_tool.ainvoke({"url": "https://books.toscrape.com/"})
    result = _parse_result(raw)

    assert result["status_code"] == 200
    assert "<html" in result["data"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_all_results_returns_data(toolkit: MrScraperToolkit) -> None:
    tools = {tool.name: tool for tool in toolkit.get_tools()}
    get_all_tool = tools["mrscraper_get_all_results"]
    raw = await get_all_tool.ainvoke({"page": 1, "page_size": 2})
    result = _parse_result(raw)

    assert result["status_code"] == 200
    assert "data" in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_scraper_returns_identifier(api_token: str) -> None:
    tool = MrScraperCreateScraper(token=api_token)
    raw = await tool.ainvoke(
        {
            "url": "https://books.toscrape.com/",
            "message": "Extract the store title.",
            "agent": "general",
        }
    )
    result = _parse_result(raw)
    payload = result["data"]["data"]

    assert result["status_code"] in {200, 201}
    assert "id" in payload or "scraperId" in payload
