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
    MrScraperBrand,
    MrScraperFetchHTML,
    MrScraperGetBrand,
    MrScraperGoogleSerp,
    MrScraperHTML,
    MrScraperJSON,
    MrScraperMultiplePage,
    MrScraperScreenshot,
    MrScraperSitemap,
    MrScraperToolkit,
    MrScraperWebSearch,
    load_mrscraper_tools,
)
from langchain_mrscraper.tools import TOOL_CLASSES
from mrscraper import MrScraper

URL = "http://cireba.com/cayman-islands-real-estate-listings/"


def _input_for(tool_cls: type[BaseTool]) -> dict:
    if tool_cls is MrScraperAccount:
        return {}
    if tool_cls is MrScraperGetBrand:
        return {"job_id": "brand-1"}
    if tool_cls is MrScraperWebSearch:
        return {"url": "Cayman Islands real estate", "raw": False}
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
    if "url" in _input_for(tool_cls):
        assert method.call_args.kwargs["url"] == _input_for(tool_cls)["url"]
    assert "html" not in method.call_args.kwargs
    assert "markdown" not in method.call_args.kwargs
    assert "screenshot" not in method.call_args.kwargs


@pytest.mark.parametrize("tool_cls", TOOL_CLASSES)
@pytest.mark.asyncio
async def test_async_routes_to_corresponding_sdk_method(tool_cls, fake_client) -> None:
    tool = tool_cls(client=fake_client)
    result = json.loads(await tool.ainvoke(_input_for(tool_cls)))
    assert result["status_code"] == 200
    getattr(fake_client, tool.sdk_method).assert_awaited_once()


@pytest.mark.parametrize(
    ("tool_cls", "field", "value"),
    [(MrScraperHTML, "url", URL), (MrScraperGetBrand, "job_id", "brand-1")],
)
def test_sync_plain_string_input(tool_cls, field, value, fake_client) -> None:
    result = json.loads(tool_cls(client=fake_client).invoke(value))
    assert result["status_code"] == 200
    method = getattr(fake_client, tool_cls.sdk_method)
    method.assert_awaited_once()
    assert method.call_args.kwargs[field] == value


@pytest.mark.parametrize(
    ("tool_cls", "field", "value"),
    [(MrScraperHTML, "url", URL), (MrScraperGetBrand, "job_id", "brand-1")],
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
    assert (
        json.loads(MrScraperHTML(client=fake_client).invoke({"url": URL}))[
            "status_code"
        ]
        == 200
    )


def test_screenshot_defaults_and_viewport_option(fake_client) -> None:
    tool = MrScraperScreenshot(client=fake_client)
    tool.invoke({"url": URL})
    params = fake_client.get_screenshot.call_args.kwargs
    assert params["timeout"] == 300
    assert params["wait_until"] == "domcontentloaded"
    assert params["full_page"] is True
    assert "browser_rendering" not in params
    tool.invoke({"url": URL, "full_page": False})
    assert fake_client.get_screenshot.call_args.kwargs["full_page"] is False
    tool.invoke({"url": URL, "wait_until": None})
    assert fake_client.get_screenshot.call_args.kwargs["wait_until"] is None


def test_sitemap_patterns_preserved_and_optional_patterns_omitted(fake_client) -> None:
    tool = MrScraperSitemap(client=fake_client)
    tool.invoke({"url": URL})
    params = fake_client.scraper_sitemap.call_args.kwargs
    assert (params["max_depth"], params["max_pages"], params["limit"]) == (2, 3, 1000)
    assert params["include_patterns"] is None
    assert params["exclude_patterns"] is None
    include = r"https:\/\/www|.scrapethissite\.com\/products\/*"
    exclude = r"/blog/.*||/private/.*"
    tool.invoke({"url": URL, "include_patterns": include, "exclude_patterns": exclude})
    assert fake_client.scraper_sitemap.call_args.kwargs["include_patterns"] == include
    assert fake_client.scraper_sitemap.call_args.kwargs["exclude_patterns"] == exclude


def test_extraction_prompt_and_listing_defaults(fake_client) -> None:
    MrScraperJSON(client=fake_client).invoke(
        {"url": URL, "prompt": "Extract all properties"}
    )
    assert (
        fake_client.scraper_json.call_args.kwargs["prompt"] == "Extract all properties"
    )
    assert "agent" not in fake_client.scraper_json.call_args.kwargs
    MrScraperMultiplePage(client=fake_client).invoke({"url": URL})
    assert fake_client.scraper_multiple_page.call_args.kwargs["max_pages"] == 3
    assert (
        fake_client.scraper_multiple_page.call_args.kwargs["prompt"]
        == "Extract all entry data as complete as possible."
    )


@pytest.mark.parametrize("bundle", ["clean", "full", "none"])
def test_brand_bundle_modes(bundle, fake_client) -> None:
    MrScraperBrand(client=fake_client).invoke({"url": URL, "bundle": bundle})
    assert fake_client.scrape_brand.call_args.kwargs["bundle"] == bundle


@pytest.mark.parametrize(
    "output", [None, "html", "bundle", "screenshot", "screenshot_full"]
)
def test_get_brand_outputs(output, fake_client) -> None:
    payload = {"job_id": "brand-1"}
    if output is not None:
        payload["output"] = output
    MrScraperGetBrand(client=fake_client).invoke(payload)
    assert fake_client.get_brand.call_args.kwargs.get("output") == output


@pytest.mark.parametrize("tool_cls", [MrScraperScreenshot, MrScraperGetBrand])
def test_binary_output_round_trip(tool_cls, fake_client) -> None:
    data = b"\x00\xff\x80PNG\r\n\x00"
    getattr(fake_client, tool_cls.sdk_method).return_value = {
        "status_code": 200,
        "data": data,
        "headers": {"content-type": "image/png"},
    }
    result = json.loads(tool_cls(client=fake_client).invoke(_input_for(tool_cls)))
    assert result["data"]["encoding"] == "base64"
    assert result["data"]["size_bytes"] == len(data)
    assert base64.b64decode(result["data"]["base64"]) == data
    assert result["headers"]["content-type"] == "image/png"


@pytest.mark.parametrize(
    ("tool_cls", "payload"),
    [
        (MrScraperHTML, {"url": "ftp://example.com"}),
        (MrScraperHTML, {"url": URL, "html": True}),
        (MrScraperHTML, {"url": URL, "timeout": 0}),
        (MrScraperHTML, {"url": URL, "timeout": 301}),
        (MrScraperHTML, {"url": URL, "max_retries": -1}),
        (MrScraperScreenshot, {"url": URL, "browser_rendering": False}),
        (MrScraperMultiplePage, {"url": URL, "max_pages": 0}),
        (MrScraperSitemap, {"url": URL, "max_depth": -1}),
        (MrScraperSitemap, {"url": URL, "limit": 0}),
        (MrScraperBrand, {"url": URL, "bundle": "other"}),
        (MrScraperGetBrand, {"job_id": " "}),
        (MrScraperGetBrand, {"job_id": "brand-1", "output": "zip"}),
        (MrScraperWebSearch, {"url": " "}),
        (MrScraperWebSearch, {"url": "query", "page": 0}),
        (MrScraperWebSearch, {"url": "query", "format": "markdown"}),
        (MrScraperAccount, {"timeout": float("inf")}),
    ],
)
def test_invalid_inputs_fail_before_sdk_call(tool_cls, payload, fake_client) -> None:
    with pytest.raises(ValidationError):
        tool_cls(client=fake_client).invoke(payload)
    getattr(fake_client, tool_cls.sdk_method).assert_not_awaited()


def test_toolkit_has_only_ten_public_services_and_shares_client(fake_client) -> None:
    tools = MrScraperToolkit(client=fake_client).get_tools()
    assert len(tools) == 10
    assert len({tool.name for tool in tools}) == 10
    assert all(tool.client is fake_client for tool in tools)
    assert not any("scraper_api" in tool.name for tool in tools)
    assert {tool.sdk_method for tool in tools} == {
        "scraper_html",
        "scraper_markdown",
        "get_screenshot",
        "scraper_json",
        "scraper_multiple_page",
        "scraper_sitemap",
        "scrape_brand",
        "get_brand",
        "web_search",
        "account",
    }


def test_filter_and_empty_filter(fake_client) -> None:
    tools = MrScraperToolkit(
        client=fake_client,
        tool_names=["mrscraper_scraper_json", "mrscraper_scraper_sitemap"],
    ).get_tools()
    assert [tool.name for tool in tools] == [
        "mrscraper_scraper_json",
        "mrscraper_scraper_sitemap",
    ]
    assert load_mrscraper_tools(client=fake_client, tool_names=[]) == []


def test_aliases_use_current_sdk_methods(fake_client) -> None:
    MrScraperFetchHTML(client=fake_client).invoke({"url": URL})
    MrScraperGoogleSerp(client=fake_client).invoke({"url": "query", "raw": False})
    fake_client.scraper_html.assert_awaited_once()
    fake_client.web_search.assert_awaited_once()


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
    assert len(tools) == 10


@pytest.mark.parametrize("env_name", ["MRSCRAPER_API_KEY", "MRSCRAPER_API_TOKEN"])
def test_per_tool_env_auth(env_name, fake_client) -> None:
    with (
        patch(
            "langchain_mrscraper.tools.MrScraper", return_value=fake_client
        ) as factory,
        patch.dict("os.environ", {env_name: "env-token"}, clear=True),
    ):
        MrScraperHTML().invoke({"url": URL})
    factory.assert_called_once_with(token="env-token")


def test_explicit_auth_overrides_env(fake_client) -> None:
    with (
        patch(
            "langchain_mrscraper.tools.MrScraper", return_value=fake_client
        ) as factory,
        patch.dict("os.environ", {"MRSCRAPER_API_KEY": "env-token"}, clear=True),
    ):
        MrScraperHTML(token="explicit-token").invoke({"url": URL})
    factory.assert_called_once_with(token="explicit-token")


def test_exports() -> None:
    for cls in TOOL_CLASSES:
        assert getattr(langchain_mrscraper, cls.__name__) is cls
    assert hasattr(langchain_mrscraper, "__version__")
    assert "MrScraperCreateScraper" not in langchain_mrscraper.__all__
