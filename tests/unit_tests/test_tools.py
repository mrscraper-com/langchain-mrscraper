"""Tool contract tests with injected SDK clients; no real API requests."""

from __future__ import annotations

import base64
import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools import BaseTool
from pydantic import ValidationError

import langchain_mrscraper
from langchain_mrscraper import (
    MrScraperAccount,
    MrScraperScraperAPI,
    MrScraperToolkit,
    MrScraperWebSearch,
    load_mrscraper_tools,
)
from langchain_mrscraper.tools import TOOL_CLASSES
from mrscraper import MrScraper

URL = "https://books.toscrape.com/"
QUERY = "e-menessaptieka.lv linkedin"


def _input_for(tool_cls: type[BaseTool]) -> dict:
    if tool_cls is MrScraperAccount:
        return {}
    if tool_cls is MrScraperWebSearch:
        return {"query": QUERY}
    return {"url": URL}


@pytest.fixture
def fake_client() -> MagicMock:
    client = MagicMock(spec=MrScraper)
    for tool_cls in TOOL_CLASSES:
        setattr(
            client,
            tool_cls.sdk_method,
            AsyncMock(
                return_value={
                    "status_code": 200,
                    "data": {"ok": True},
                    "headers": {},
                }
            ),
        )
    return client


def test_exactly_three_public_sdk_methods_are_wrapped() -> None:
    public = {
        name
        for name, member in inspect.getmembers(MrScraper, inspect.iscoroutinefunction)
        if not name.startswith("_")
    }
    assert public == {"scraper_api", "web_search", "account"}
    assert {tool_cls.sdk_method for tool_cls in TOOL_CLASSES} == public


@pytest.mark.parametrize("tool_cls", TOOL_CLASSES)
def test_tool_matches_sdk_schema_and_defaults(tool_cls, fake_client) -> None:
    tool = tool_cls(client=fake_client)
    assert isinstance(tool, BaseTool)
    assert tool.name == f"mrscraper_{tool.sdk_method}"
    schema = tool.args_schema
    assert "properties" in schema.model_json_schema()
    sdk_params = dict(inspect.signature(getattr(MrScraper, tool.sdk_method)).parameters)
    sdk_params.pop("self")
    assert set(schema.model_fields) == set(sdk_params)
    for name, field in schema.model_fields.items():
        default = sdk_params[name].default
        if default is inspect.Parameter.empty:
            assert field.is_required()
        else:
            assert field.default == default


@pytest.mark.parametrize("tool_cls", TOOL_CLASSES)
def test_sync_routes_to_corresponding_sdk_method(tool_cls, fake_client) -> None:
    tool = tool_cls(client=fake_client)
    output = json.loads(tool.invoke(_input_for(tool_cls)))
    assert output == {"status_code": 200, "data": {"ok": True}, "headers": {}}
    method = getattr(fake_client, tool.sdk_method)
    method.assert_awaited_once()
    for key, value in _input_for(tool_cls).items():
        assert method.call_args.kwargs[key] == value


@pytest.mark.parametrize("tool_cls", TOOL_CLASSES)
@pytest.mark.asyncio
async def test_async_routes_to_corresponding_sdk_method(tool_cls, fake_client) -> None:
    tool = tool_cls(client=fake_client)
    result = json.loads(await tool.ainvoke(_input_for(tool_cls)))
    assert result["status_code"] == 200
    getattr(fake_client, tool.sdk_method).assert_awaited_once()


@pytest.mark.parametrize(
    ("tool_cls", "field", "value"),
    [(MrScraperScraperAPI, "url", URL), (MrScraperWebSearch, "query", QUERY)],
)
def test_sync_plain_string_input(tool_cls, field, value, fake_client) -> None:
    result = json.loads(tool_cls(client=fake_client).invoke(value))
    assert result["status_code"] == 200
    method = getattr(fake_client, tool_cls.sdk_method)
    method.assert_awaited_once()
    assert method.call_args.kwargs[field] == value


@pytest.mark.parametrize(
    ("tool_cls", "field", "value"),
    [(MrScraperScraperAPI, "url", URL), (MrScraperWebSearch, "query", QUERY)],
)
@pytest.mark.asyncio
async def test_async_plain_string_input(tool_cls, field, value, fake_client) -> None:
    result = json.loads(await tool_cls(client=fake_client).ainvoke(value))
    assert result["status_code"] == 200
    method = getattr(fake_client, tool_cls.sdk_method)
    method.assert_awaited_once()
    assert method.call_args.kwargs[field] == value


@pytest.mark.asyncio
async def test_sync_invocation_inside_running_loop(fake_client) -> None:
    result = MrScraperScraperAPI(client=fake_client).invoke({"url": URL})
    assert json.loads(result)["status_code"] == 200


def test_scraper_api_defaults_to_html_only(fake_client) -> None:
    MrScraperScraperAPI(client=fake_client).invoke({"url": URL})
    params = fake_client.scraper_api.call_args.kwargs
    assert (params["html"], params["markdown"], params["screenshot"]) == (
        True,
        False,
        False,
    )
    assert params["timeout"] == 120
    assert params["geo_code"] == "US"
    assert params["browser_rendering"] is None


def test_scraper_api_forwards_output_flags_and_page_controls(fake_client) -> None:
    MrScraperScraperAPI(client=fake_client).invoke(
        {
            "url": URL,
            "html": True,
            "markdown": True,
            "screenshot": True,
            "wait_for_selector": ".product_pod",
            "wait_until": "domcontentloaded",
            "headers": {"Accept-Language": "en"},
            "proxy_country": "gb",
        }
    )
    params = fake_client.scraper_api.call_args.kwargs
    assert (params["html"], params["markdown"], params["screenshot"]) == (
        True,
        True,
        True,
    )
    assert params["wait_for_selector"] == ".product_pod"
    assert params["wait_until"] == "domcontentloaded"
    assert params["headers"] == {"Accept-Language": "en"}
    assert params["proxy_country"] == "gb"


def test_scraper_api_markdown_only(fake_client) -> None:
    MrScraperScraperAPI(client=fake_client).invoke(
        {"url": URL, "html": False, "markdown": True}
    )
    params = fake_client.scraper_api.call_args.kwargs
    assert (params["html"], params["markdown"]) == (False, True)


def test_web_search_forwards_country_and_num_results(fake_client) -> None:
    MrScraperWebSearch(client=fake_client).invoke(
        {"query": QUERY, "country": "us", "num_results": 100}
    )
    params = fake_client.web_search.call_args.kwargs
    assert params == {
        "query": QUERY,
        "country": "us",
        "num_results": 100,
        "timeout": 600.0,
    }


def test_web_search_defaults(fake_client) -> None:
    MrScraperWebSearch(client=fake_client).invoke({"query": QUERY})
    params = fake_client.web_search.call_args.kwargs
    assert params["country"] is None
    assert params["num_results"] == 10


def test_scraper_api_combined_output_is_preserved(fake_client) -> None:
    data = {"html": "<html></html>", "markdown": "# Books", "screenshot": "iVBORw0K"}
    fake_client.scraper_api.return_value = {
        "status_code": 200,
        "data": data,
        "headers": {"content-type": "application/json"},
    }
    result = json.loads(
        MrScraperScraperAPI(client=fake_client).invoke(
            {"url": URL, "markdown": True, "screenshot": True}
        )
    )
    assert result["data"] == data


def test_binary_output_round_trip(fake_client) -> None:
    data = b"\x00\xff\x80PNG\r\n\x00"
    fake_client.scraper_api.return_value = {
        "status_code": 200,
        "data": data,
        "headers": {"content-type": "image/png"},
    }
    result = json.loads(
        MrScraperScraperAPI(client=fake_client).invoke(
            {"url": URL, "html": False, "screenshot": True}
        )
    )
    assert result["data"]["encoding"] == "base64"
    assert result["data"]["size_bytes"] == len(data)
    assert base64.b64decode(result["data"]["base64"]) == data
    assert result["headers"]["content-type"] == "image/png"


@pytest.mark.parametrize(
    ("tool_cls", "payload"),
    [
        (MrScraperScraperAPI, {"url": "ftp://example.com"}),
        (MrScraperScraperAPI, {"url": URL, "html": False}),
        (
            MrScraperScraperAPI,
            {"url": URL, "html": False, "markdown": False, "screenshot": False},
        ),
        (
            MrScraperScraperAPI,
            {"url": URL, "screenshot": True, "browser_rendering": False},
        ),
        (MrScraperScraperAPI, {"url": URL, "timeout": 0}),
        (MrScraperScraperAPI, {"url": URL, "timeout": 301}),
        (MrScraperScraperAPI, {"url": URL, "max_retries": -1}),
        (MrScraperScraperAPI, {"url": URL, "prompt": "Extract titles"}),
        (MrScraperWebSearch, {"query": " "}),
        (MrScraperWebSearch, {"query": QUERY, "num_results": 9}),
        (MrScraperWebSearch, {"query": QUERY, "num_results": 101}),
        (MrScraperWebSearch, {"query": QUERY, "country": " "}),
        (MrScraperWebSearch, {"query": QUERY, "timeout": 0}),
        (MrScraperWebSearch, {"url": QUERY}),
        (MrScraperAccount, {"timeout": float("inf")}),
        (MrScraperAccount, {"timeout": 0}),
    ],
)
def test_invalid_inputs_fail_before_sdk_call(tool_cls, payload, fake_client) -> None:
    with pytest.raises(ValidationError):
        tool_cls(client=fake_client).invoke(payload)
    getattr(fake_client, tool_cls.sdk_method).assert_not_awaited()


def test_toolkit_has_only_three_public_services_and_shares_client(
    fake_client,
) -> None:
    tools = MrScraperToolkit(client=fake_client).get_tools()
    assert [tool.name for tool in tools] == [
        "mrscraper_scraper_api",
        "mrscraper_web_search",
        "mrscraper_account",
    ]
    assert all(tool.client is fake_client for tool in tools)


def test_filter_and_empty_filter(fake_client) -> None:
    tools = MrScraperToolkit(
        client=fake_client,
        tool_names=["mrscraper_web_search", "mrscraper_account"],
    ).get_tools()
    assert [tool.name for tool in tools] == [
        "mrscraper_web_search",
        "mrscraper_account",
    ]
    assert load_mrscraper_tools(client=fake_client, tool_names=[]) == []


def test_load_function_requires_auth() -> None:
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(ValueError, match="Either client, token, or mrscraper_api_key"),
    ):
        load_mrscraper_tools()


@pytest.mark.parametrize(
    "auth", [{"token": "token-123"}, {"mrscraper_api_key": "token-123"}]
)
def test_load_function_creates_shared_client(auth) -> None:
    with patch("langchain_mrscraper.tools.MrScraper") as factory:
        tools = load_mrscraper_tools(**auth)
    factory.assert_called_once_with(token="token-123")
    assert len(tools) == 3


@pytest.mark.parametrize("env_name", ["MRSCRAPER_API_KEY", "MRSCRAPER_API_TOKEN"])
def test_per_tool_env_auth(env_name, fake_client) -> None:
    with (
        patch(
            "langchain_mrscraper.tools.MrScraper", return_value=fake_client
        ) as factory,
        patch.dict("os.environ", {env_name: "env-token"}, clear=True),
    ):
        MrScraperScraperAPI().invoke({"url": URL})
    factory.assert_called_once_with(token="env-token")


def test_missing_auth_raises() -> None:
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(ValueError, match="Missing MrScraper API key"),
    ):
        MrScraperAccount().invoke({})


def test_explicit_auth_overrides_env(fake_client) -> None:
    with (
        patch(
            "langchain_mrscraper.tools.MrScraper", return_value=fake_client
        ) as factory,
        patch.dict("os.environ", {"MRSCRAPER_API_KEY": "env-token"}, clear=True),
    ):
        MrScraperScraperAPI(token="explicit-token").invoke({"url": URL})
    factory.assert_called_once_with(token="explicit-token")


def test_exports() -> None:
    for cls in TOOL_CLASSES:
        assert getattr(langchain_mrscraper, cls.__name__) is cls
    assert hasattr(langchain_mrscraper, "__version__")
    assert set(langchain_mrscraper.__all__) == {
        "MrScraperAccount",
        "MrScraperScraperAPI",
        "MrScraperToolkit",
        "MrScraperWebSearch",
        "load_mrscraper_tools",
    }
    for removed in (
        "MrScraperHTML",
        "MrScraperMarkdown",
        "MrScraperScreenshot",
        "MrScraperJSON",
        "MrScraperMultiplePage",
        "MrScraperSitemap",
        "MrScraperBrand",
        "MrScraperGetBrand",
        "MrScraperFetchHTML",
    ):
        assert not hasattr(langchain_mrscraper, removed)
