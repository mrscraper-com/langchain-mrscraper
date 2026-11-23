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
        (package.MrScraperScrapeHTML, {"timeout": 331}),
        (package.MrScraperScrapeHTML, {"timeout": 0}),
        (package.MrScraperScrapeHTML, {"url": "file:///tmp/a"}),
        (package.MrScraperScrapeHTML, {"screenshot": True}),
        (package.MrScraperScrapeHTML, {"screenshot": "bottom"}),
        (package.MrScraperScrapeHTML, {"screenshot": "99x800"}),
        (package.MrScraperScrapeHTML, {"screenshot": "1280x800-301"}),
        (package.MrScraperScrapeHTML, {"screenshot": "1280x800\n"}),
        (package.MrScraperScrapeHTML, {"action": " "}),
        (package.MrScraperScrapeHTML, {"geo_code": "usa"}),
        (package.MrScraperScrapeHTML, {"max_age": -1}),
        (package.MrScraperScrapeHTML, {"max_age": 604800001}),
        (package.MrScraperScrapeHTML, {"token_cap": 10}),
        (package.MrScraperScrapeHTML, {"save_result": False}),
        (package.MrScraperScrapeJSON, {"save_result": True}),
        (package.MrScraperGetScreenshot, {"token_cap": 10}),
        (package.MrScraperScrapeHTML, {"wait_for_selector": " "}),
        (package.MrScraperScrapeHTML, {"wait_for_selector": "a" * 501}),
        (package.MrScraperScrapeMarkdown, {"max_retries": -1}),
        (package.MrScraperScrapeMarkdown, {"html": True}),
        (package.MrScraperGetScreenshot, {"screenshot": "top"}),
        (package.MrScraperGetScreenshot, {"browser_rendering": True}),
        (package.MrScraperGetScreenshot, {"action": "x"}),
        (package.MrScraperScrapeJSON, {"prompt": " "}),
        (package.MrScraperScrapeJSON, {"return_cookie": True}),
        (package.MrScraperScrapeJSON, {"action": "x"}),
        (package.MrScraperScrapeBrand, {"save_result": True}),
        (package.MrScraperScrapeBrand, {"max_age": 0}),
        (package.MrScraperScrapeBrand, {"bundle": "full"}),
        (package.MrScraperScrapeBrand, {"timeout": 331}),
        (package.MrScraperScrapeBrand, {"timeout": True}),
        (package.MrScraperScrapeBrand, {"warm_start": "true"}),
        (package.MrScraperScrapeBrand, {"geo_code": "usa"}),
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
    "cls",
    [
        package.MrScraperScrapeHTML,
        package.MrScraperScrapeMarkdown,
        package.MrScraperScrapeJSON,
    ],
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


def test_warm_start_rejected_for_screenshots(client):
    with pytest.raises(ValidationError):
        package.MrScraperGetScreenshot(client=client).invoke(
            {"url": URL, "warm_start": True}
        )
    client.get_screenshot.assert_not_awaited()


@pytest.mark.parametrize(
    "cls,option",
    [
        (cls, option)
        for cls in (
            package.MrScraperScrapeHTML,
            package.MrScraperScrapeMarkdown,
            package.MrScraperGetScreenshot,
            package.MrScraperScrapeJSON,
        )
        for option in (
            "super",
            "wait_until",
            "proxy_country",
            "proxy",
            "return_cookie",
            "save_result",
            "token_cap",
        )
    ]
    + [
        (package.MrScraperGetScreenshot, "html"),
        (package.MrScraperGetScreenshot, "markdown"),
        (package.MrScraperScrapeMarkdown, "screenshot"),
    ],
)
def test_undocumented_inputs_are_rejected(cls, option, client):
    with pytest.raises(ValidationError):
        cls(client=client).invoke({"url": URL, option: "value"})
    getattr(client, cls.sdk_method).assert_not_awaited()


async def _requests(cls, *inputs):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        tool = cls(client=MrScraper("test", http_client=http))
        for value in inputs:
            await tool.ainvoke(value)
    return [list(call.url.params.multi_items()) for call in calls]


async def test_defaults_reach_the_sdk_request():
    loading = [("timeout", "300"), ("warmStart", "false"), ("blockResources", "false")]
    saving = [("saveResult", "true"), ("maxAge", "0")]
    assert await _requests(package.MrScraperScrapeHTML, {"url": URL}) == [
        [
            ("url", URL),
            ("html", "true"),
            ("markdown", "false"),
            *loading,
            *saving,
            ("screenshot", "false"),
        ]
    ]
    assert await _requests(package.MrScraperScrapeMarkdown, {"url": URL}) == [
        [
            ("url", URL),
            ("markdown", "true"),
            ("html", "false"),
            ("screenshot", "false"),
            *loading,
            *saving,
        ]
    ]
    assert await _requests(package.MrScraperGetScreenshot, {"url": URL}) == [
        [
            ("url", URL),
            ("screenshot", "full"),
            ("html", "false"),
            ("markdown", "false"),
            ("browserRendering", "true"),
            ("timeout", "300"),
            *saving,
        ]
    ]
    assert await _requests(package.MrScraperScrapeJSON, {"url": URL}) == [
        [
            ("url", URL),
            ("prompt", "Extract all data as complete as possible."),
            ("agent", "general"),
            ("html", "true"),
            *loading,
            *saving,
            ("screenshot", "false"),
        ]
    ]
    assert await _requests(package.MrScraperWebSearch, {"query": " shoes "}) == [
        [("action", "websearch"), ("query", "shoes"), ("numResults", "10")]
    ]


async def test_options_reach_the_sdk_request():
    shared = {
        "timeout": 330,
        "wait_for_selector": ".ready",
        "geo_code": "ID",
        "max_age": 604800000,
        "max_retries": 0,
    }
    wire = [
        ("timeout", "330"),
        ("warmStart", "true"),
        ("blockResources", "true"),
        ("waitForSelector", ".ready"),
    ]
    # saveResult is always true and tokenCap is never sent.
    tail = [
        ("geoCode", "id"),
        ("saveResult", "true"),
        ("maxAge", "604800000"),
        ("maxRetries", "0"),
    ]
    loading = {"warm_start": True, "block_resources": True}
    (markdown,) = await _requests(
        package.MrScraperScrapeMarkdown,
        {"url": URL, **shared, **loading, "browser_rendering": False, "action": "a"},
    )
    assert markdown == [
        ("url", URL),
        ("markdown", "true"),
        ("html", "false"),
        ("screenshot", "false"),
        ("browserRendering", "false"),
        *wire,
        ("action", "a"),
        *tail,
    ]
    (json_request,) = await _requests(
        package.MrScraperScrapeJSON,
        {"url": URL, **shared, **loading, "html": False, "screenshot": True},
    )
    assert json_request == [
        ("url", URL),
        ("prompt", "Extract all data as complete as possible."),
        ("agent", "general"),
        ("html", "false"),
        *wire,
        *tail,
        ("screenshot", "true"),
    ]
    (search,) = await _requests(
        package.MrScraperWebSearch,
        {"query": "shoes", "country": "ID", "num_results": 100},
    )
    assert search == [
        ("action", "websearch"),
        ("query", "shoes"),
        ("country", "id"),
        ("numResults", "100"),
    ]


@pytest.mark.parametrize("screenshot", ["top", "full", "1280x800", "1920x1080-75"])
@pytest.mark.parametrize("browser_rendering", [None, True, False])
async def test_html_screenshot_sends_browser_rendering(screenshot, browser_rendering):
    value = {"url": URL, "screenshot": screenshot}
    if browser_rendering is not None:
        value["browser_rendering"] = browser_rendering
    (params,) = await _requests(package.MrScraperScrapeHTML, value)
    assert params[:4] == [
        ("url", URL),
        ("html", "true"),
        ("markdown", "false"),
        ("browserRendering", "true"),
    ]
    assert dict(params)["screenshot"] == screenshot


@pytest.mark.parametrize("browser_rendering", [None, True, False])
async def test_html_without_screenshot_keeps_browser_rendering(browser_rendering):
    value = {"url": URL}
    if browser_rendering is not None:
        value["browser_rendering"] = browser_rendering
    (params,) = await _requests(package.MrScraperScrapeHTML, value)
    assert dict(params).get("browserRendering") == (
        None if browser_rendering is None else str(browser_rendering).lower()
    )
    assert dict(params)["screenshot"] == "false"


async def test_brand_inputs_reach_the_sdk_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        tool = package.MrScraperScrapeBrand(client=MrScraper("test", http_client=http))
        await tool.ainvoke({"url": URL})
        await tool.ainvoke(
            {"url": URL, "timeout": 120, "warm_start": True, "geo_code": "GB"}
        )
    brand = [("action", "brand-scraping"), ("url", URL), ("bundle", "none")]
    # timeout is sent only when set; warmStart is always sent.
    assert list(calls[0].url.params.multi_items()) == [*brand, ("warmStart", "false")]
    assert list(calls[1].url.params.multi_items()) == [
        *brand,
        ("timeout", "120"),
        ("warmStart", "true"),
        ("geoCode", "gb"),
    ]
    # The brand deadline is the timeout, or 300 seconds when omitted, plus 30.
    assert [call.extensions["timeout"]["read"] for call in calls] == [330, 150]
