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
    url: str = Field(description="Absolute HTTP or HTTPS page URL.")

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
        description="Page timeout in seconds; transport adds 30 seconds.",
    )
    geo_code: str = Field(
        default="us",
        pattern=r"^[A-Za-z]{2}$",
        description="Country to load the page from.",
    )
    proxy_country: str = Field(
        default="us", pattern=r"^[A-Za-z]{2}$", description="Proxy server country."
    )
    super: bool = Field(default=False, description="Use real-device routing.")
    wait_until: Literal["domcontentloaded", "load", "networkidle0", "networkidle2"] = (
        "domcontentloaded"
    )
    proxy: Optional[str] = Field(
        default=None, min_length=1, description="Custom proxy URL."
    )
    max_retries: Optional[int] = Field(
        default=None, ge=0, strict=True, description="Retry limit; omit for no limit."
    )
    save_result: bool = Field(
        default=False, description="Save this result to the dashboard."
    )


class LoadingInput(PageInput):
    block_resources: bool = Field(
        default=False, description="Block images, fonts, and stylesheets."
    )
    wait_for_selector: Optional[str] = Field(
        default=None, min_length=1, description="CSS selector to wait for."
    )
    return_cookie: bool = Field(
        default=False, description="Include browser session cookies."
    )


class ScrapeHtmlInput(LoadingInput):
    browser_rendering: bool = Field(
        default=False, description="Enable browser rendering."
    )


class ScrapeMarkdownInput(ScrapeHtmlInput):
    html: bool = Field(
        default=False, description="Also return HTML; forces browser rendering."
    )


class GetScreenshotInput(LoadingInput):
    screenshot: Literal["full", "top"] = "full"
    html: bool = True
    markdown: bool = False


class ScrapeJsonInput(PageInput):
    prompt: str = Field(
        default="Extract all data as complete as possible.",
        min_length=1,
        description="Extraction instruction; append 'Json Schema:' and a schema to shape the output.",
    )
    browser_rendering: bool = False
    html: bool = False
    screenshot: bool = False

    @field_validator("prompt")
    @classmethod
    def _prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must be non-empty")
        return value


class WebSearchInput(_ToolInput):
    query: str = Field(min_length=1, max_length=1000, description="Search query text.")
    country: str = Field(
        default="us",
        pattern=r"^[A-Za-z]{2}$",
        description="Country for localized results.",
    )
    num_results: int = Field(
        default=10, ge=10, le=100, strict=True, description="Number of ranked results."
    )
    timeout: float = Field(
        default=120.0,
        gt=0,
        allow_inf_nan=False,
        description="HTTP deadline in seconds.",
    )

    @field_validator("query", mode="before")
    @classmethod
    def _query(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("query must be non-empty")
        return value.strip()


class AccountInput(_ToolInput):
    timeout: float = Field(
        default=30.0, gt=0, allow_inf_nan=False, description="HTTP deadline in seconds."
    )


class MrScraperBaseTool(BaseTool):
    """Resolve authentication and delegate both invocation styles to the SDK."""

    name: str = "mrscraper"
    description: str = "Base MrScraper SDK service wrapper."
    client: Any = Field(default=None, exclude=True, repr=False)
    token: Optional[str] = Field(default=None, exclude=True, repr=False)
    mrscraper_api_key: Optional[str] = Field(default=None, exclude=True, repr=False)
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


class MrScraperAccount(MrScraperBaseTool):
    name: str = "mrscraper_account"
    description: str = "Read account identity, subscription, token usage, remaining quota, and rate limits."
    args_schema: type[BaseModel] = AccountInput
    sdk_method: ClassVar[str] = "account"


class MrScraperScrapeHTML(MrScraperBaseTool):
    name: str = "mrscraper_scrape_html"
    description: str = (
        "Retrieve a public page as raw HTML. Browser rendering is optional."
    )
    args_schema: type[BaseModel] = ScrapeHtmlInput
    sdk_method: ClassVar[str] = "scrape_html"


class MrScraperScrapeMarkdown(MrScraperBaseTool):
    name: str = "mrscraper_scrape_markdown"
    description: str = "Retrieve clean Markdown from a public page. html=true also returns HTML and forces browser rendering."
    args_schema: type[BaseModel] = ScrapeMarkdownInput
    sdk_method: ClassVar[str] = "scrape_markdown"


class MrScraperGetScreenshot(MrScraperBaseTool):
    name: str = "mrscraper_get_screenshot"
    description: str = "Capture a base64 screenshot of the full page or top viewport. Browser rendering is always enabled."
    args_schema: type[BaseModel] = GetScreenshotInput
    sdk_method: ClassVar[str] = "get_screenshot"


class MrScraperScrapeBrand(MrScraperBaseTool):
    name: str = "mrscraper_scrape_brand"
    description: str = "Extract a website brand as JSON with bundle=none."
    args_schema: type[BaseModel] = UrlInput
    sdk_method: ClassVar[str] = "scrape_brand"


class MrScraperScrapeJSON(MrScraperBaseTool):
    name: str = "mrscraper_scrape_json"
    description: str = "Extract structured JSON with the general agent. Long prompts use the documented POST fallback. Append Json Schema: and a schema to shape output."
    args_schema: type[BaseModel] = ScrapeJsonInput
    sdk_method: ClassVar[str] = "scrape_json"


class MrScraperWebSearch(MrScraperBaseTool):
    name: str = "mrscraper_web_search"
    description: str = "Search the web for ranked results with titles, URLs, descriptions, and sources."
    args_schema: type[BaseModel] = WebSearchInput
    sdk_method: ClassVar[str] = "web_search"


TOOL_CLASSES: tuple[type[MrScraperBaseTool], ...] = (
    MrScraperAccount,
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
