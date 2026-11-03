"""Opt-in live API smoke tests; normal test runs do not spend API quota."""

from __future__ import annotations

import json
import os

import pytest

from langchain_mrscraper import MrScraperToolkit

pytestmark = pytest.mark.integration

URL = "https://books.toscrape.com/"


@pytest.fixture(scope="module")
def tools() -> dict:
    if os.getenv("MRSCRAPER_RUN_LIVE") != "1":
        pytest.skip("Set MRSCRAPER_RUN_LIVE=1 to opt in to real API requests.")
    token = os.getenv("MRSCRAPER_API_KEY") or os.getenv("MRSCRAPER_API_TOKEN")
    if not token:
        pytest.skip("Set MRSCRAPER_API_KEY or MRSCRAPER_API_TOKEN.")
    return {tool.name: tool for tool in MrScraperToolkit(token=token).get_tools()}


def test_account(tools: dict) -> None:
    result = json.loads(tools["mrscraper_account"].invoke({}))
    assert result["status_code"] == 200
    assert "token_remaining" in result["data"]


@pytest.mark.asyncio
async def test_scraper_api_html(tools: dict) -> None:
    result = json.loads(await tools["mrscraper_scraper_api"].ainvoke({"url": URL}))
    assert result["status_code"] == 200
    assert isinstance(result["data"], str)
    assert "<html" in result["data"].lower()


@pytest.mark.asyncio
async def test_scraper_api_combined_outputs(tools: dict) -> None:
    result = json.loads(
        await tools["mrscraper_scraper_api"].ainvoke(
            {"url": URL, "html": True, "markdown": True, "screenshot": True}
        )
    )
    assert result["status_code"] == 200
    data = result["data"]
    assert isinstance(data, dict)
    assert "<html" in data["html"].lower()
    assert data["markdown"]
    assert data["screenshot"]


@pytest.mark.asyncio
async def test_web_search(tools: dict) -> None:
    result = json.loads(
        await tools["mrscraper_web_search"].ainvoke(
            {"query": "e-menessaptieka.lv linkedin", "country": "us", "num_results": 10}
        )
    )
    assert result["status_code"] == 200
    items = result["data"]["data"]
    assert items
    assert {"rank", "title", "url"} <= set(items[0])
