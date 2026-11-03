"""LangChain tools backed by the public MrScraper Python SDK services."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any, ClassVar, Optional, Union
from urllib.parse import urlparse

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class ScraperAPIInput(_ToolInput):
    """Output flags plus page, proxy, header, and retry controls for ``scraper_api``."""

    url: str = Field(min_length=1, description="HTTP or HTTPS URL to fetch.")
    html: bool = Field(default=True, description="Return the rendered page HTML.")
    markdown: bool = Field(default=False, description="Return the page as Markdown.")
    screenshot: bool = Field(
        default=False,
        description="Return a base64 screenshot; enables browser rendering.",
    )
    timeout: int = Field(
        default=120, gt=0, le=300, description="Page timeout in seconds (1–300)."
    )
    geo_code: str = Field(default="US", description="Geographic country code.")
    proxy_country: Optional[str] = Field(
        default=None, description="Proxy country code."
    )
    block_resources: Optional[bool] = Field(
        default=False, description="Block images, CSS, and fonts."
    )
    browser_rendering: Optional[bool] = Field(
        default=None,
        description="Force (true) or disable (false) JavaScript rendering; "
        "omit to let the service decide.",
    )
    super: bool = Field(default=False, description="Use real-device routing.")
    use_proxy: bool = Field(default=True, description="Use a proxy for this request.")
    proxy: Optional[str] = Field(
        default=None, description="Custom proxy as username:password@host:port."
    )
    wait_for_selector: Optional[str] = Field(
        default=None, description="CSS selector to wait for."
    )
    wait_until: Optional[str] = Field(
        default=None, description="Page lifecycle event, e.g. domcontentloaded."
    )
    home_page: bool = Field(
        default=False, description="Visit the site's root page first."
    )
    bypass_proxy: bool = Field(default=False, description="Bypass the proxy.")
    cookie_jar: Optional[str] = Field(
        default=None, description="Cookie configuration string."
    )
    headers: Optional[Union[dict[str, str], str]] = Field(
        default=None, description="Target HTTP headers as an object or JSON string."
    )
    max_retries: int = Field(default=3, ge=0, description="Maximum retries.")
    token_cap: Optional[int] = Field(
        default=None, ge=0, description="Maximum retry-token budget."
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

    @model_validator(mode="after")
    def _outputs(self) -> ScraperAPIInput:
        if not (self.html or self.markdown or self.screenshot):
            raise ValueError(
                "At least one of html, markdown, or screenshot must be true"
            )
        if self.screenshot and self.browser_rendering is False:
            raise ValueError(
                "screenshot requires browser rendering; omit browser_rendering"
            )
        return self


class WebSearchInput(_ToolInput):
    query: str = Field(min_length=1, description="The search query.")
    country: Optional[str] = Field(
        default=None,
        description="Country code for localized results, e.g. us; omit for the default.",
    )
    num_results: int = Field(
        default=10, ge=10, le=100, description="Number of results to return (10–100)."
    )
    timeout: float = Field(
        default=600.0, gt=0, allow_inf_nan=False, description="HTTP timeout in seconds."
    )

    @field_validator("query")
    @classmethod
    def _nonblank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must contain a search query")
        return value

    @field_validator("country")
    @classmethod
    def _nonblank_country(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("country must be non-empty when provided")
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
        # The SDK omits None values from the request, so pass every field through.
        params = schema.model_validate(kwargs).model_dump()
        result = await getattr(self._get_client(), self.sdk_method)(**params)
        return _serialize_response(result)


class MrScraperScraperAPI(MrScraperBaseTool):
    """Fetch a page as HTML, Markdown, a screenshot, or a combination."""

    name: str = "mrscraper_scraper_api"
    description: str = (
        "Fetch a public web page as rendered HTML, Markdown, screenshot, or a "
        "combination. HTML only (the default) returns the HTML string in data; "
        "combined outputs return an object with html, markdown, and screenshot "
        "(base64) entries. At least one of html, markdown, or screenshot must be true."
    )
    args_schema: type[BaseModel] = ScraperAPIInput
    sdk_method: ClassVar[str] = "scraper_api"


class MrScraperWebSearch(MrScraperBaseTool):
    """Search the web using MrScraper."""

    name: str = "mrscraper_web_search"
    description: str = (
        "Search the web for real-time results: website URLs, titles, and descriptions. "
        "Returns ranked results with rank, title, url, description, and source."
    )
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


TOOL_CLASSES: tuple[type[MrScraperBaseTool], ...] = (
    MrScraperScraperAPI,
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
    """Factory object that returns the three public SDK services as LangChain tools."""

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
