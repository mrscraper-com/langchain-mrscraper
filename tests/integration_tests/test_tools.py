"""Opt-in checks for every tool; real requests spend API quota."""

import json
import os

import pytest

from langchain_mrscraper.tools import TOOL_CLASSES

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("cls", TOOL_CLASSES)
async def test_live_tool(cls):
    if os.getenv("MRSCRAPER_RUN_LIVE") != "1":
        pytest.skip("Set MRSCRAPER_RUN_LIVE=1")
    if not (os.getenv("MRSCRAPER_API_TOKEN") or os.getenv("MRSCRAPER_API_KEY")):
        pytest.skip("Set a token")
    tool = cls()
    payload = (
        {}
        if cls.sdk_method == "account"
        else {"query": "web scraping"}
        if cls.sdk_method == "web_search"
        else {"url": "https://books.toscrape.com/"}
    )
    result = json.loads(await tool.ainvoke(payload))
    assert result["status_code"] == 200 and result["data"] is not None
