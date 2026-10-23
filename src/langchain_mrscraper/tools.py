"""LangChain tools backed by the public MrScraper Python SDK services."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar, Literal, Optional, Union
from urllib.parse import urlparse

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mrscraper import MrScraper


def _encode_binary(value: Any) -> dict[str, Any]:
    """Preserve image and ZIP responses in JSON without decoding binary as text."""
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


class _PageInput(_ToolInput):
    """Shared page, proxy, header, and retry controls; output is chosen by the tool."""

    url: str = Field(min_length=1, description="HTTP or HTTPS URL to scrape.")
    timeout: int = Field(
        default=120, gt=0, le=300, description="Page timeout in seconds (1–300)."
    )
    geo_code: str = Field(default="US", description="Geographic country code.")
    proxy_country: Optional[str] = Field(
        default=None, description="Proxy country code."
    )
    block_resources: Optional[bool] = Field(
        default=False, description="Block page resources."
    )
    super: bool = Field(default=False, description="Enable the super scraping tier.")
    use_proxy: bool = Field(default=True, description="Use a proxy for this request.")
    proxy: Optional[str] = Field(default=None, description="Custom proxy address.")
    wait_for_selector: Optional[str] = Field(
        default=None, description="CSS selector to wait for."
    )
    wait_until: Optional[str] = Field(
        default=None, description="Browser page-load event."
    )
    home_page: bool = Field(
        default=False, description="Warm the session via the home page."
    )
    bypass_proxy: bool = Field(default=False, description="Bypass the proxy.")
    cookie_jar: Optional[str] = Field(default=None, description="Request cookie jar.")
    headers: Optional[Union[dict[str, str], str]] = Field(
        default=None, description="Target HTTP headers."
    )
    max_retries: int = Field(default=3, ge=0, description="Maximum retries.")
    token_cap: Optional[int] = Field(
        default=None, ge=0, description="Maximum token budget."
    )
    stream: Optional[bool] = Field(
        default=None, description="Request streaming from the API."
    )
    discard_token_secret: str = Field(
        default="", description="Discard-token secret, if required."
    )

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an HTTP or HTTPS URL")
        return value


class ScraperHTMLInput(_PageInput):
    browser_rendering: Optional[bool] = Field(
        default=None, description="Render JavaScript."
    )


class ScraperMarkdownInput(ScraperHTMLInput):
    """Fetch Markdown; format flags are selected automatically."""


class ScreenshotInput(_PageInput):
    full_page: bool = Field(default=True, description="Capture the entire page.")
    timeout: int = Field(
        default=300, gt=0, le=300, description="Page timeout in seconds (1–300)."
    )
    wait_until: Optional[str] = Field(
        default="domcontentloaded", description="Browser page-load event."
    )


class ScraperJSONInput(ScraperHTMLInput):
    prompt: str = Field(
        default="Extract all data as complete as possible.",
        min_length=1,
        description="Natural-language extraction instructions (general agent).",
    )


class MultiplePageInput(ScraperHTMLInput):
    prompt: str = Field(
        default="Extract all entry data as complete as possible.",
        min_length=1,
        description="Instructions for extracting listing entries across pages.",
    )
    max_pages: int = Field(default=3, gt=0, description="Maximum listing pages.")


class SitemapInput(ScraperHTMLInput):
    max_depth: int = Field(default=2, ge=0, description="Maximum crawl depth.")
    max_pages: int = Field(default=3, gt=0, description="Maximum pages to crawl.")
    limit: int = Field(default=1000, gt=0, description="Maximum discovered records.")
    include_patterns: Optional[str] = Field(
        default=None, description="Include URL pattern string, unchanged."
    )
    exclude_patterns: Optional[str] = Field(
        default=None, description="Exclude URL pattern string, unchanged."
    )


class BrandInput(ScraperHTMLInput):
    bundle: Literal["clean", "full", "none"] = Field(
        default="clean", description="Brand bundle mode."
    )


class GetBrandInput(_ToolInput):
    job_id: str = Field(
        min_length=1, description="Brand job ID returned by scrape_brand."
    )
    output: Optional[Literal["html", "bundle", "screenshot", "screenshot_full"]] = (
        Field(
            default=None, description="Output to download; omit to read job metadata."
        )
    )
    timeout: float = Field(
        default=600.0, gt=0, allow_inf_nan=False, description="HTTP timeout in seconds."
    )

    @field_validator("job_id")
    @classmethod
    def _nonblank_job_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("job_id must be non-empty")
        return value


class WebSearchInput(_ToolInput):
    url: str = Field(
        min_length=1, description="Google query text or a full Google search URL."
    )
    raw: bool = Field(
        default=True,
        description="Compatibility option: true requests HTML and overrides format.",
    )
    region: Optional[str] = Field(default=None, description="Search country code.")
    language: Optional[str] = Field(default=None, description="Search language code.")
    page: Optional[int] = Field(
        default=None, ge=1, description="One-based result page."
    )
    format: Literal["json", "html"] = Field(
        default="json", description="Response format; use raw=false for JSON."
    )
    render_js: bool = Field(
        default=False, description="Render JavaScript-dependent search features."
    )
    timeout: float = Field(
        default=600.0, gt=0, allow_inf_nan=False, description="HTTP timeout in seconds."
    )

    @field_validator("url")
    @classmethod
    def _nonblank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("url must contain a search query or Google URL")
        return value


class AccountInput(_ToolInput):
    timeout: float = Field(
        default=30.0, gt=0, allow_inf_nan=False, description="HTTP timeout in seconds."
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
        # Keep explicit None values: screenshot wait_until=None must disable the
        # SDK's default domcontentloaded wait. The SDK omits unset API fields.
        params = schema.model_validate(kwargs).model_dump()
        result = await getattr(self._get_client(), self.sdk_method)(**params)
        return _serialize_response(result)


class MrScraperHTML(MrScraperBaseTool):
    """Retrieve page HTML."""

    name: str = "mrscraper_scraper_html"
    description: str = (
        "Retrieve HTML from a URL. The SDK selects HTML output automatically."
    )
    args_schema: type[BaseModel] = ScraperHTMLInput
    sdk_method: ClassVar[str] = "scraper_html"


class MrScraperMarkdown(MrScraperBaseTool):
    """Retrieve page Markdown."""

    name: str = "mrscraper_scraper_markdown"
    description: str = (
        "Retrieve Markdown from a URL. The SDK selects Markdown output automatically."
    )
    args_schema: type[BaseModel] = ScraperMarkdownInput
    sdk_method: ClassVar[str] = "scraper_markdown"


class MrScraperScreenshot(MrScraperBaseTool):
    """Capture a screenshot."""

    name: str = "mrscraper_get_screenshot"
    description: str = "Capture a browser screenshot, full page by default. Binary data is returned as base64."
    args_schema: type[BaseModel] = ScreenshotInput
    sdk_method: ClassVar[str] = "get_screenshot"


class MrScraperJSON(MrScraperBaseTool):
    """Extract structured data from a page."""

    name: str = "mrscraper_scraper_json"
    description: str = (
        "Extract structured JSON from a URL using a prompt and the general agent."
    )
    args_schema: type[BaseModel] = ScraperJSONInput
    sdk_method: ClassVar[str] = "scraper_json"


class MrScraperMultiplePage(MrScraperBaseTool):
    """Extract entries across listing pages."""

    name: str = "mrscraper_scraper_multiple_page"
    description: str = "Extract listing entries across multiple pages using a prompt; defaults to 3 pages."
    args_schema: type[BaseModel] = MultiplePageInput
    sdk_method: ClassVar[str] = "scraper_multiple_page"


class MrScraperSitemap(MrScraperBaseTool):
    """Discover URLs with the map agent."""

    name: str = "mrscraper_scraper_sitemap"
    description: str = "Discover site URLs with crawl depth, page and record limits, and include/exclude patterns."
    args_schema: type[BaseModel] = SitemapInput
    sdk_method: ClassVar[str] = "scraper_sitemap"


class MrScraperBrand(MrScraperBaseTool):
    """Start a brand scraping job."""

    name: str = "mrscraper_scrape_brand"
    description: str = "Scrape a website's brand with a clean, full, or none bundle. Returns a job for get_brand."
    args_schema: type[BaseModel] = BrandInput
    sdk_method: ClassVar[str] = "scrape_brand"


class MrScraperGetBrand(MrScraperBaseTool):
    """Read brand job metadata or download an output."""

    name: str = "mrscraper_get_brand"
    description: str = "Read a brand job by job_id or download its HTML, bundle, or screenshot; binary data is base64."
    args_schema: type[BaseModel] = GetBrandInput
    sdk_method: ClassVar[str] = "get_brand"


class MrScraperWebSearch(MrScraperBaseTool):
    """Search Google using the SDK's v2 synchronous search service."""

    name: str = "mrscraper_web_search"
    description: str = "Search Google using query text or a Google URL. Set raw=false and format=json for structured results."
    args_schema: type[BaseModel] = WebSearchInput
    sdk_method: ClassVar[str] = "web_search"


class MrScraperAccount(MrScraperBaseTool):
    """Read account usage and subscription details."""

    name: str = "mrscraper_account"
    description: str = (
        "Read account identity, subscription, quota, token usage, and rate limits."
    )
    args_schema: type[BaseModel] = AccountInput
    sdk_method: ClassVar[str] = "account"


# Import aliases only: the toolkit always advertises the current service names.
MrScraperFetchHTML = MrScraperHTML
MrScraperGoogleSerp = MrScraperWebSearch

TOOL_CLASSES: tuple[type[MrScraperBaseTool], ...] = (
    MrScraperHTML,
    MrScraperMarkdown,
    MrScraperScreenshot,
    MrScraperJSON,
    MrScraperMultiplePage,
    MrScraperSitemap,
    MrScraperBrand,
    MrScraperGetBrand,
    MrScraperWebSearch,
    MrScraperAccount,
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
    """Factory object that returns the ten public SDK services as LangChain tools."""

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
