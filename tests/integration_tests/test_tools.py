"""Opt-in live API smoke tests; normal test runs do not spend API quota."""

from __future__ import annotations

import json
import os

import pytest

from langchain_mrscraper import MrScraperToolkit

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def toolkit() -> MrScraperToolkit:
    if os.getenv("MRSCRAPER_RUN_LIVE") != "1":
        pytest.skip("Set MRSCRAPER_RUN_LIVE=1 to opt in to real API requests.")
    token = os.getenv("MRSCRAPER_API_KEY") or os.getenv("MRSCRAPER_API_TOKEN")
    if not token:
        pytest.skip("Set MRSCRAPER_API_KEY or MRSCRAPER_API_TOKEN.")
    return MrScraperToolkit(token=token)


@pytest.mark.asyncio
async def test_scraper_html(toolkit: MrScraperToolkit) -> None:
    tools = {tool.name: tool for tool in toolkit.get_tools()}
    raw = await tools["mrscraper_scraper_html"].ainvoke(
        {"url": "https://books.toscrape.com/"}
    )
    result = json.loads(raw)
    assert result["status_code"] == 200
    assert "<html" in result["data"].lower()


@pytest.mark.asyncio
async def test_scraper_json(toolkit: MrScraperToolkit) -> None:
    tools = {tool.name: tool for tool in toolkit.get_tools()}
    raw = await tools["mrscraper_scraper_json"].ainvoke(
        {
            "url": "https://books.toscrape.com/",
            "prompt": "Extract the store title.",
        }
    )
    result = json.loads(raw)
    assert result["status_code"] in {200, 201}
    assert "data" in result
