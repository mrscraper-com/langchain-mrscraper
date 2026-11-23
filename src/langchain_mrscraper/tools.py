"""LangChain tools backed by the public MrScraper Python SDK services."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar, Literal, Optional, Union
from urllib.parse import urlparse

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mrscraper import MrScraper


def _encode_binary(value: Any) -> dict[str, Any]:
    """Preserve binary responses (e.g. images) in JSON without decoding as text."""
    if isinstance(value, (bytes, bytearray)):
        return {
            "encoding": "base64",
            "base64": base64.b64encode(value).decode("ascii"),
            "size_bytes": len(value),
        }
    raise TypeError(f"Cannot serialize {type(value).__name__} as JSON")


def _serialize_response(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, default=_encode_binary)


def _run_coro_sync(coro: Any) -> Any:
    """Support synchronous tool calls inside notebooks with a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


class _ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _nonblank(value: Optional[str], name: str) -> Optional[str]:
    if value is not None and not value.strip():
        raise ValueError(f"{name} must be non-empty")
    return value


class UrlInput(_ToolInput):
    url: str = Field(description="Absolute HTTP or HTTPS URL of the page to process.")

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("url must be an HTTP or HTTPS URL")
        return value


class BrandInput(UrlInput):
    """Brand accepts the page timeout, warm start, and country controls."""

    timeout: Optional[int] = Field(
        default=None,
        ge=1,
        le=330,
        strict=True,
        description="Maximum seconds to wait for the scrape, from 1 to 330. The HTTP request allows 30 additional seconds.",
    )
    warm_start: bool = Field(
        default=False,
        strict=True,
        description="Whether to open the site's home page first to warm the session before loading the target URL.",
    )
    geo_code: Optional[str] = Field(
        default=None,
        pattern="^[A-Za-z]{2}$",
        description="Two-letter country code to load the page from, sent in lowercase.",
    )


class PageInput(UrlInput):
    """Page controls shared by HTML, Markdown, screenshots, and JSON extraction."""

    timeout: int = Field(
        default=300,
        ge=1,
        le=330,
        strict=True,
        description="Maximum seconds to wait for the scrape, from 1 to 330. The HTTP request allows 30 additional seconds.",
    )
    wait_for_selector: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="CSS selector or text to wait for on the page before returning the result, up to 500 characters.",
    )
    geo_code: Optional[str] = Field(
        default=None,
        pattern="^[A-Za-z]{2}$",
        description="Two-letter country code to load the page from, sent in lowercase.",
    )
    max_age: int = Field(
        default=0,
        ge=0,
        le=604800000,
        strict=True,
        description="Return a cached result of the same request when it is newer than the selected age. A cached result costs the same tokens as the original scrape.",
    )
    max_retries: Optional[int] = Field(
        default=None,
        ge=0,
        strict=True,
        description="Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit.",
    )

    @field_validator("wait_for_selector")
    @classmethod
    def _selector(cls, value: Optional[str]) -> Optional[str]:
        return _nonblank(value, "wait_for_selector")


class LoadingInput(PageInput):
    """Loading controls accepted by HTML, Markdown, and JSON extraction."""

    browser_rendering: Optional[bool] = Field(
        default=None,
        description="Whether to load the page in a browser: true always does and false never does. Omit it to load the page without a browser first and switch to a browser automatically if the request is blocked.",
    )
    warm_start: bool = Field(
        default=False,
        strict=True,
        description="Whether to open the site's home page first to warm the session before loading the target URL.",
    )
    block_resources: bool = Field(
        default=False,
        description="Whether to block images, fonts, and stylesheets while loading the page.",
    )


class _ActionInput(LoadingInput):
    action: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Scraper action that routes the request or simply flags it, useful for separating analytics per domain.",
    )

    @field_validator("action")
    @classmethod
    def _action(cls, value: Optional[str]) -> Optional[str]:
        return _nonblank(value, "action")


_SCREENSHOT_VIEWPORT = re.compile(r"([0-9]{3,4})x([0-9]{3,4})(?:-([0-9]{2,3}))?")


class ScrapeHtmlInput(_ActionInput):
    screenshot: Union[Literal[False], str] = Field(
        default=False,
        description="Screenshot to capture with the HTML: false for none, full for the entire page, top for the first viewport, or a WIDTHxHEIGHT viewport from 100 to 3840 pixels with an optional -ZOOM percent from 25 to 300, such as 1280x800 or 1920x1080-75. Setting a screenshot also sends browserRendering=true.",
    )

    @field_validator("screenshot", mode="before")
    @classmethod
    def _screenshot(cls, value: Any) -> Any:
        if value is False or value in ("full", "top"):
            return value
        match = (
            _SCREENSHOT_VIEWPORT.fullmatch(value) if isinstance(value, str) else None
        )
        if match:
            width, height = int(match[1]), int(match[2])
            zoom = 100 if match[3] is None else int(match[3])
            if 100 <= width <= 3840 and 100 <= height <= 3840 and 25 <= zoom <= 300:
                return value
        raise ValueError(
            "screenshot must be false, full, top, or WIDTHxHEIGHT from 100 to 3840 "
            "pixels with an optional -ZOOM from 25 to 300, such as 1280x800 or 1920x1080-75"
        )


class ScrapeMarkdownInput(_ActionInput):
    """Markdown accepts the HTML controls without a screenshot."""


class GetScreenshotInput(PageInput):
    """Screenshots always render the full page in a browser."""


class ScrapeJsonInput(LoadingInput):
    prompt: str = Field(
        default="Extract all data as complete as possible.",
        min_length=1,
        description="Instructions describing the data to extract. Append Json Schema: and a JSON schema to shape the output.",
    )
    html: bool = Field(
        default=True,
        description="Whether to include the page HTML in the response.",
    )
    screenshot: bool = Field(
        default=False,
        description="Whether to include a base64 screenshot in the response.",
    )

    @field_validator("prompt")
    @classmethod
    def _prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must be non-empty")
        return value


class WebSearchInput(_ToolInput):
    query: str = Field(
        min_length=1,
        max_length=1000,
        description="Search query text, trimmed before sending, containing 1 to 1000 characters.",
    )
    country: Optional[str] = Field(
        default=None,
        pattern="^[A-Za-z]{2}$",
        description="Two-letter country code to search from, sent in lowercase.",
    )
    num_results: int = Field(
        default=10,
        ge=10,
        le=100,
        strict=True,
        description="Number of search results to request, as an integer from 10 to 100. Fewer results may be returned.",
    )

    @field_validator("query", mode="before")
    @classmethod
    def _query(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("query must be non-empty")
        return value.strip()


class StatusInput(_ToolInput):
    """Status takes no service parameters, matching the CLI."""


class MrScraperBaseTool(BaseTool):
    """Resolve authentication and delegate both invocation styles to the SDK."""

    name: str = "mrscraper"
    description: str = "Base MrScraper SDK service wrapper."
    client: Any = Field(default=None, exclude=True, repr=False)
    token: Optional[str] = Field(
        default=None,
        exclude=True,
        repr=False,
        description="API key used to authenticate the request.",
    )
    mrscraper_api_key: Optional[str] = Field(
        default=None,
        exclude=True,
        repr=False,
        description="API key used to authenticate the request.",
    )
    sdk_method: ClassVar[str]

    def _resolve_token(self) -> str:
        token = (
            self.token
            or self.mrscraper_api_key
            or os.getenv("MRSCRAPER_API_KEY")
            or os.getenv("MRSCRAPER_API_TOKEN")
        )
        if not token:
            raise ValueError(
                "Missing MrScraper API key. Pass `token` or `mrscraper_api_key` when "
                "initializing the tool, or set MRSCRAPER_API_KEY / MRSCRAPER_API_TOKEN."
            )
        return token

    def _get_client(self) -> MrScraper:
        if self.client is None:
            self.client = MrScraper(token=self._resolve_token())
        return self.client

    def _run(self, *args: Any, **kwargs: Any) -> str:
        return _run_coro_sync(self._arun(*args, **kwargs))

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        schema = self.args_schema
        if not isinstance(schema, type) or not issubclass(schema, BaseModel):
            raise TypeError("Tool must define a Pydantic input schema")
        if args:
            if len(args) != 1:
                raise TypeError("Pass one tool input string or dictionary")
            if isinstance(args[0], dict):
                kwargs = {**kwargs, **args[0]}
            elif isinstance(args[0], str):
                # BaseTool forwards a plain string as the first positional input.
                first_field = next(iter(schema.model_fields))
                kwargs = {**kwargs, first_field: args[0]}
            else:
                raise TypeError("Tool input must be a string or dictionary")
        # The SDK omits None values from the request, so pass every field through.
        params = schema.model_validate(kwargs).model_dump()
        result = await getattr(self._get_client(), self.sdk_method)(**params)
        return _serialize_response(result)


class MrScraperStatus(MrScraperBaseTool):
    name: str = "mrscraper_status"
    description: str = "Return the raw account status API response without summarizing, redacting body fields, or adding calculated fields."
    args_schema: type[BaseModel] = StatusInput
    sdk_method: ClassVar[str] = "status"

    def _to_args_and_kwargs(
        self, tool_input: str | dict[str, Any], tool_call_id: str | None
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        # BaseTool bypasses validation for schemas with no fields.
        StatusInput.model_validate(tool_input)
        return (), {}


class MrScraperScrapeHTML(MrScraperBaseTool):
    name: str = "mrscraper_scrape_html"
    description: str = "Retrieve the raw HTML of a page. Browser rendering is optional."
    args_schema: type[BaseModel] = ScrapeHtmlInput
    sdk_method: ClassVar[str] = "scrape_html"


class MrScraperScrapeMarkdown(MrScraperBaseTool):
    name: str = "mrscraper_scrape_markdown"
    description: str = (
        "Retrieve a page as clean Markdown. Browser rendering is optional."
    )
    args_schema: type[BaseModel] = ScrapeMarkdownInput
    sdk_method: ClassVar[str] = "scrape_markdown"


class MrScraperGetScreenshot(MrScraperBaseTool):
    name: str = "mrscraper_get_screenshot"
    description: str = "Capture a base64 PNG screenshot of the full page. Browser rendering is always enabled."
    args_schema: type[BaseModel] = GetScreenshotInput
    sdk_method: ClassVar[str] = "get_screenshot"


class MrScraperScrapeBrand(MrScraperBaseTool):
    name: str = "mrscraper_scrape_brand"
    description: str = (
        "Extract a website's colors, typography, logos, and social links as JSON."
    )
    args_schema: type[BaseModel] = BrandInput
    sdk_method: ClassVar[str] = "scrape_brand"


class MrScraperScrapeJSON(MrScraperBaseTool):
    name: str = "mrscraper_scrape_json"
    description: str = "Extract structured JSON from a page using a natural-language prompt. Append Json Schema: and a JSON schema to shape the output."
    args_schema: type[BaseModel] = ScrapeJsonInput
    sdk_method: ClassVar[str] = "scrape_json"


class MrScraperWebSearch(MrScraperBaseTool):
    name: str = "mrscraper_web_search"
    description: str = "Search the web and return ranked results with titles, URLs, descriptions, and sources."
    args_schema: type[BaseModel] = WebSearchInput
    sdk_method: ClassVar[str] = "web_search"


TOOL_CLASSES: tuple[type[MrScraperBaseTool], ...] = (
    MrScraperStatus,
    MrScraperScrapeHTML,
    MrScraperScrapeMarkdown,
    MrScraperGetScreenshot,
    MrScraperScrapeBrand,
    MrScraperScrapeJSON,
    MrScraperWebSearch,
)


def load_mrscraper_tools(
    *,
    token: Optional[str] = None,
    mrscraper_api_key: Optional[str] = None,
    client: MrScraper | None = None,
    tool_names: Sequence[str] | None = None,
) -> list[BaseTool]:
    """Construct tools with one shared SDK client and optional exact-name filtering."""
    resolved_client = client
    resolved_token = (
        token
        or mrscraper_api_key
        or os.getenv("MRSCRAPER_API_KEY")
        or os.getenv("MRSCRAPER_API_TOKEN")
    )
    if resolved_client is None:
        if not resolved_token:
            raise ValueError(
                "Either client, token, or mrscraper_api_key must be provided "
                "(or set MRSCRAPER_API_KEY / MRSCRAPER_API_TOKEN)."
            )
        resolved_client = MrScraper(token=resolved_token)

    tools: list[BaseTool] = [
        tool_cls(client=resolved_client) for tool_cls in TOOL_CLASSES
    ]
    if tool_names is None:
        return tools
    requested = set(tool_names)
    return [tool for tool in tools if tool.name in requested]


class MrScraperToolkit:
    """Factory object that returns the seven public SDK services as LangChain tools."""

    def __init__(
        self,
        *,
        token: Optional[str] = None,
        mrscraper_api_key: Optional[str] = None,
        client: MrScraper | None = None,
        tool_names: Sequence[str] | None = None,
    ) -> None:
        self._token = token
        self._mrscraper_api_key = mrscraper_api_key
        self._client = client
        self._tool_names = tool_names

    def get_tools(self) -> list[BaseTool]:
        return load_mrscraper_tools(
            token=self._token,
            mrscraper_api_key=self._mrscraper_api_key,
            client=self._client,
            tool_names=self._tool_names,
        )
