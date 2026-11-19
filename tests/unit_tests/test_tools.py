"""Contract and delegation checks for all seven tools."""

import base64
import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

import langchain_mrscraper as package
from langchain_mrscraper import MrScraperToolkit, load_mrscraper_tools
from langchain_mrscraper.tools import TOOL_CLASSES
from mrscraper import MrScraper

URL = "https://example.com"


def payload(cls):
    return (
        {}
        if cls.sdk_method == "status"
        else {"query": "web scraping"}
        if cls.sdk_method == "web_search"
        else {"url": URL}
    )


@pytest.fixture
def client():
    obj = MagicMock(spec=MrScraper)
    for cls in TOOL_CLASSES:
        setattr(
            obj,
            cls.sdk_method,
            AsyncMock(
                return_value={"status_code": 200, "data": {"ok": True}, "headers": {}}
            ),
        )
    return obj


def test_seven_services():
    public = {
        name
        for name, fn in inspect.getmembers(MrScraper, inspect.iscoroutinefunction)
        if not name.startswith("_")
    }
    assert public == {
        "status",
        "scrape_html",
        "scrape_markdown",
        "get_screenshot",
        "scrape_brand",
        "scrape_json",
        "web_search",
    }
    assert {cls.sdk_method for cls in TOOL_CLASSES} == public


@pytest.mark.parametrize("cls", TOOL_CLASSES)
def test_schema_matches_sdk(cls):
    tool = cls()
    params = dict(inspect.signature(getattr(MrScraper, tool.sdk_method)).parameters)
    params.pop("self")
    assert set(tool.args_schema.model_fields) == set(params)
    for name, field in tool.args_schema.model_fields.items():
        default = params[name].default
        if default is inspect.Parameter.empty:
            assert field.is_required()
        else:
            assert field.default == default
    assert tool.name == f"mrscraper_{tool.sdk_method}"


@pytest.mark.parametrize("cls", TOOL_CLASSES)
def test_sync_invocation(cls, client):
    tool = cls(client=client)
    assert json.loads(tool.invoke(payload(cls)))["data"] == {"ok": True}
    getattr(client, cls.sdk_method).assert_awaited_once()


@pytest.mark.parametrize("cls", TOOL_CLASSES)
async def test_async_invocation(cls, client):
    tool = cls(client=client)
    assert json.loads(await tool.ainvoke(payload(cls)))["status_code"] == 200
    getattr(client, cls.sdk_method).assert_awaited_once()


@pytest.mark.parametrize(
    "cls", [cls for cls in TOOL_CLASSES if cls.sdk_method != "status"]
)
def test_plain_string(cls, client):
    tool = cls(client=client)
    value = next(iter(payload(cls).values()))
    assert json.loads(tool.invoke(value))["status_code"] == 200


async def test_sync_in_running_loop(client):
    assert (
        json.loads(package.MrScraperScrapeHTML(client=client).invoke({"url": URL}))[
            "status_code"
        ]
        == 200
    )


@pytest.mark.parametrize("cls", TOOL_CLASSES)
async def test_real_sdk_request_mapping(cls):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": {"tokenLimit": 100, "tokenUsage": 20}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        tool = cls(client=MrScraper("test", http_client=http))
        result = json.loads(await tool.ainvoke(payload(cls)))
    assert result["status_code"] == 200
    assert calls[0].method == "GET"
    if cls.sdk_method == "web_search":
        assert calls[0].url.params["action"] == "websearch"
    elif cls.sdk_method != "status":
        assert calls[0].url.params["url"] == URL


@pytest.mark.parametrize(
    "cls,extra",
    [
        (package.MrScraperScrapeHTML, {"timeout": 301}),
        (package.MrScraperScrapeHTML, {"url": "file:///tmp/a"}),
        (package.MrScraperScrapeMarkdown, {"max_retries": -1}),
        (package.MrScraperGetScreenshot, {"screenshot": True}),
        (package.MrScraperScrapeJSON, {"prompt": " "}),
        (package.MrScraperScrapeJSON, {"return_cookie": True}),
        (package.MrScraperScrapeBrand, {"save_result": True}),
        (package.MrScraperWebSearch, {"query": " "}),
        (package.MrScraperWebSearch, {"country": "usa"}),
        (package.MrScraperWebSearch, {"num_results": 9}),
        (package.MrScraperStatus, {"timeout": 30}),
    ],
)
def test_invalid_inputs(cls, extra, client):
    with pytest.raises(ValidationError):
        cls(client=client).invoke({**payload(cls), **extra})
    getattr(client, cls.sdk_method).assert_not_awaited()


def test_output_preserves_combined_and_binary(client):
    value = {
        "html": "<html>test</html>",
        "markdown": "# Test",
        "screenshot": "aGVsbG8=",
    }
    client.get_screenshot.return_value = {
        "status_code": 200,
        "data": value,
        "headers": {},
    }
    assert (
        json.loads(package.MrScraperGetScreenshot(client=client).invoke({"url": URL}))[
            "data"
        ]
        == value
    )
    client.get_screenshot.return_value = {
        "status_code": 200,
        "data": b"\x00\xffPNG",
        "headers": {},
    }
    data = json.loads(
        package.MrScraperGetScreenshot(client=client).invoke({"url": URL})
    )["data"]
    assert base64.b64decode(data["base64"]) == b"\x00\xffPNG"


def test_toolkit_filter_and_exports(client):
    tools = MrScraperToolkit(client=client).get_tools()
    assert len(tools) == 7 and all(tool.client is client for tool in tools)
    assert [
        t.name
        for t in load_mrscraper_tools(
            client=client, tool_names=["mrscraper_web_search"]
        )
    ] == ["mrscraper_web_search"]
    assert load_mrscraper_tools(client=client, tool_names=[]) == []
    for cls in TOOL_CLASSES:
        assert getattr(package, cls.__name__) is cls


@pytest.mark.parametrize("key", ["MRSCRAPER_API_KEY", "MRSCRAPER_API_TOKEN"])
def test_env_auth(key, client):
    with (
        patch.dict("os.environ", {key: "env-token"}, clear=True),
        patch("langchain_mrscraper.tools.MrScraper", return_value=client) as factory,
    ):
        tools = load_mrscraper_tools()
    factory.assert_called_once_with(token="env-token")
    assert len(tools) == 7


def test_missing_auth():
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(ValueError, match="Either client"),
    ):
        load_mrscraper_tools()


def test_shared_client_created_once(client):
    with patch("langchain_mrscraper.tools.MrScraper", return_value=client) as factory:
        tools = load_mrscraper_tools(token="explicit")
    factory.assert_called_once_with(token="explicit")
    assert all(t.client is client for t in tools)


@pytest.mark.parametrize(
    "cls", [package.MrScraperScrapeHTML, package.MrScraperScrapeMarkdown]
)
async def test_warm_start_reaches_the_sdk_request(cls):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        tool = cls(client=MrScraper("test", http_client=http))
        for value in [False, True]:
            await tool.ainvoke({"url": URL, "warm_start": value})
            assert calls[-1].url.params["warmStart"] == str(value).lower()
        for value in ["true", 1, None]:
            with pytest.raises(ValidationError):
                await tool.ainvoke({"url": URL, "warm_start": value})
    assert len(calls) == 2


@pytest.mark.parametrize(
    "cls", [package.MrScraperGetScreenshot, package.MrScraperScrapeJSON]
)
def test_warm_start_rejected_for_other_page_tools(cls, client):
    with pytest.raises(ValidationError):
        cls(client=client).invoke({"url": URL, "warm_start": True})
    getattr(client, cls.sdk_method).assert_not_awaited()
