"""LangChain tools backed by the public MrScraper Python SDK services."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar, Literal, Optional
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


class UrlInput(_ToolInput):
    url: str = Field(description="Absolute HTTP or HTTPS URL of the page to process.")

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("url must be an HTTP or HTTPS URL")
        return value


class PageInput(UrlInput):
    timeout: int = Field(
        default=300,
        ge=1,
        le=300,
        strict=True,
        description="Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 additional seconds.",
    )
    geo_code: str = Field(
        default="us",
        pattern="^[A-Za-z]{2}$",
        description="Two-letter country code to load the page from, sent in lowercase.",
    )
    proxy_country: str = Field(
        default="us",
        pattern="^[A-Za-z]{2}$",
        description="Two-letter country code of the proxy server, sent in lowercase.",
    )
    super: bool = Field(
        default=False, description="Whether to route the request through real devices."
    )
    wait_until: Literal["domcontentloaded", "load", "networkidle0", "networkidle2"] = (
        Field(
            default="domcontentloaded",
            description="Navigation completion event to wait for: domcontentloaded, load, networkidle0, or networkidle2.",
        )
    )
    proxy: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Custom proxy URL used to load the page.",
    )
    max_retries: Optional[int] = Field(
        default=None,
        ge=0,
        strict=True,
        description="Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit.",
    )
    save_result: bool = Field(
        default=False,
        description="Whether to save the result to the dashboard Result tab.",
    )


class LoadingInput(PageInput):
    block_resources: bool = Field(
        default=False,
        description="Whether to block images, fonts, and stylesheets while loading the page.",
    )
    wait_for_selector: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Wait for the page to contain the specified CSS selector before returning the result.",
    )
    return_cookie: bool = Field(
        default=False,
        description="Whether to include browser session cookies in the response.",
    )


class ScrapeHtmlInput(LoadingInput):
    warm_start: bool = Field(
        default=False,
        strict=True,
        description="Whether to enable warm start for more reliable scraping, at the cost of additional latency.",
    )
    browser_rendering: bool = Field(
        default=False,
        description="Whether to render the page in a browser before returning the result.",
    )


class ScrapeMarkdownInput(ScrapeHtmlInput):
    html: bool = Field(
        default=False,
        description="Whether to include the page HTML in the response.",
    )


class GetScreenshotInput(LoadingInput):
    screenshot: Literal["full", "top"] = Field(
        default="full",
        description="Screenshot area to capture: full for the entire page or top for the top viewport.",
    )
    html: bool = Field(
        default=True,
        description="Whether to include the page HTML in the response.",
    )
    markdown: bool = Field(
        default=False,
        description="Whether to include the page Markdown in the response.",
    )


class ScrapeJsonInput(PageInput):
    prompt: str = Field(
        default="Extract all data as complete as possible.",
        min_length=1,
        description="Instructions describing the data to extract. Append Json Schema: and a JSON schema to shape the output.",
    )
    browser_rendering: bool = Field(
        default=False,
        description="Whether to render the page in a browser before returning the result.",
    )
    html: bool = Field(
        default=False,
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
    country: str = Field(
        default="us",
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
    description: str = "Retrieve a page as Markdown. Including HTML also enables browser rendering and returns both outputs as JSON."
    args_schema: type[BaseModel] = ScrapeMarkdownInput
    sdk_method: ClassVar[str] = "scrape_markdown"


class MrScraperGetScreenshot(MrScraperBaseTool):
    name: str = "mrscraper_get_screenshot"
    description: str = "Capture a base64 screenshot of the full page or top viewport. Browser rendering is always enabled."
    args_schema: type[BaseModel] = GetScreenshotInput
    sdk_method: ClassVar[str] = "get_screenshot"


class MrScraperScrapeBrand(MrScraperBaseTool):
    name: str = "mrscraper_scrape_brand"
    description: str = (
        "Extract a website's colors, typography, logos, and social links as JSON."
    )
    args_schema: type[BaseModel] = UrlInput
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
