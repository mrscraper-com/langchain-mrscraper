"""LangChain tools for the MrScraper web scraping API."""

from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal, Optional, Sequence, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from mrscraper import MrScraper


def _serialize_response(result: dict[str, Any]) -> str:
    """Convert API response dict to tool output text."""
    return json.dumps(result, indent=2, default=str)


def _run_coro_sync(coro: Any) -> Any:
    """Run coroutine from sync context, including active event loop environments."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # When already in an event loop (e.g. notebooks), run coroutine in a fresh loop
    # inside a worker thread to avoid nested-loop RuntimeError.
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


class FetchHTMLInput(BaseModel):
    """Input schema for fetching rendered HTML."""

    url: str = Field(description="The full URL to fetch.")
    timeout: int = Field(default=120, description="Max seconds to wait for page load.")
    geo_code: str = Field(default="US", description="Two-letter proxy country code.")
    block_resources: bool = Field(
        default=False,
        description="Whether to block image/CSS/font resources for faster loading.",
    )


class CreateScraperInput(BaseModel):
    """Input schema for creating and running an AI scraper."""

    url: str = Field(description="Target URL to scrape.")
    message: str = Field(description="Natural-language extraction instructions.")
    agent: Literal["general", "listing", "map"] = Field(
        default="general",
        description="Scraper mode: general, listing, or map.",
    )
    proxy_country: Optional[str] = Field(default=None, description="Two-letter proxy country code.")
    max_depth: int = Field(default=2, description="Map mode: crawl depth.")
    max_pages: int = Field(default=50, description="Map mode: max pages to crawl.")
    limit: int = Field(default=1000, description="Map mode: max records to extract.")
    include_patterns: str = Field(default="", description="Map mode: include URL regex patterns.")
    exclude_patterns: str = Field(default="", description="Map mode: exclude URL regex patterns.")


class RerunAIScraperInput(BaseModel):
    """Input schema for rerunning an AI scraper."""

    scraper_id: str = Field(description="Existing AI scraper ID.")
    url: str = Field(description="URL to run the scraper against.")
    max_depth: int = Field(default=2, description="Map mode: crawl depth.")
    max_pages: int = Field(default=50, description="Map mode: max pages to crawl.")
    limit: int = Field(default=1000, description="Map mode: max records to extract.")
    include_patterns: str = Field(default="", description="Map mode: include URL regex patterns.")
    exclude_patterns: str = Field(default="", description="Map mode: exclude URL regex patterns.")


class BulkRerunAIScraperInput(BaseModel):
    """Input schema for bulk rerunning an AI scraper."""

    scraper_id: str = Field(description="Existing AI scraper ID.")
    urls: list[str] = Field(min_length=1, description="One or more target URLs.")


class RerunManualScraperInput(BaseModel):
    """Input schema for rerunning a manual scraper."""

    scraper_id: str = Field(description="Manual scraper ID from MrScraper dashboard.")
    url: str = Field(description="URL to run the scraper against.")


class BulkRerunManualScraperInput(BaseModel):
    """Input schema for bulk rerunning a manual scraper."""

    scraper_id: str = Field(description="Manual scraper ID from MrScraper dashboard.")
    urls: list[str] = Field(min_length=1, description="One or more target URLs.")


class GetAllResultsInput(BaseModel):
    """Input schema for listing results."""

    sort_field: Literal[
        "createdAt",
        "updatedAt",
        "id",
        "type",
        "url",
        "status",
        "error",
        "tokenUsage",
        "runtime",
    ] = Field(default="updatedAt", description="Field used for sorting.")
    sort_order: Literal["ASC", "DESC"] = Field(default="DESC", description="Sort direction.")
    page_size: int = Field(default=10, description="Results per page.")
    page: int = Field(default=1, description="Page number, starting at 1.")
    search: Optional[str] = Field(default=None, description="Free text search string.")
    date_range_column: Optional[str] = Field(default=None, description="Date field for range filtering.")
    start_at: Optional[str] = Field(default=None, description="ISO-8601 start date.")
    end_at: Optional[str] = Field(default=None, description="ISO-8601 end date.")


class GetResultByIdInput(BaseModel):
    """Input schema for fetching a single result."""

    result_id: str = Field(description="MrScraper result ID.")


class MrScraperBaseTool(BaseTool):
    """Base class for all MrScraper tools."""

    client: Any = Field(default=None, exclude=True, repr=False)
    token: Optional[str] = Field(default=None, exclude=True, repr=False)
    mrscraper_api_key: Optional[str] = Field(default=None, exclude=True, repr=False)

    @staticmethod
    def _first_arg_or_kwargs(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
        """Normalize args for direct and low-level calls."""
        if args and isinstance(args[0], dict):
            return {**kwargs, **args[0]}
        return kwargs

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


class MrScraperFetchHTML(MrScraperBaseTool):
    """Fetch rendered HTML for a webpage."""

    name: str = "mrscraper_fetch_html"
    description: str = (
        "Fetch rendered HTML using MrScraper's stealth browser. "
        "Useful when you need full page HTML after JavaScript execution."
    )
    args_schema: Type[BaseModel] = FetchHTMLInput

    def _run(self, *args: Any, **kwargs: Any) -> str:
        params = self._first_arg_or_kwargs(args, kwargs)
        return _run_coro_sync(self._arun(**params))

    async def _arun(self, **kwargs: Any) -> str:
        result = await self._get_client().fetch_html(**kwargs)
        return _serialize_response(result)


class MrScraperCreateScraper(MrScraperBaseTool):
    """Create and run an AI scraper."""

    name: str = "mrscraper_create_scraper"
    description: str = (
        "Create and run an AI-powered scraper from natural-language instructions. "
        "Returns scraper metadata, including scraper ID for follow-up runs."
    )
    args_schema: Type[BaseModel] = CreateScraperInput

    def _run(self, *args: Any, **kwargs: Any) -> str:
        params = self._first_arg_or_kwargs(args, kwargs)
        return _run_coro_sync(self._arun(**params))

    async def _arun(self, **kwargs: Any) -> str:
        result = await self._get_client().create_scraper(**kwargs)
        return _serialize_response(result)


class MrScraperRerunAIScraper(MrScraperBaseTool):
    """Rerun an existing AI scraper."""

    name: str = "mrscraper_rerun_ai_scraper"
    description: str = (
        "Rerun an existing AI scraper on a different URL while preserving extraction logic."
    )
    args_schema: Type[BaseModel] = RerunAIScraperInput

    def _run(self, *args: Any, **kwargs: Any) -> str:
        params = self._first_arg_or_kwargs(args, kwargs)
        return _run_coro_sync(self._arun(**params))

    async def _arun(self, **kwargs: Any) -> str:
        result = await self._get_client().rerun_scraper(**kwargs)
        return _serialize_response(result)


class MrScraperBulkRerunAIScraper(MrScraperBaseTool):
    """Rerun an AI scraper for multiple URLs."""

    name: str = "mrscraper_bulk_rerun_ai_scraper"
    description: str = "Bulk rerun an AI scraper across multiple URLs."
    args_schema: Type[BaseModel] = BulkRerunAIScraperInput

    def _run(self, *args: Any, **kwargs: Any) -> str:
        params = self._first_arg_or_kwargs(args, kwargs)
        return _run_coro_sync(self._arun(**params))

    async def _arun(self, **kwargs: Any) -> str:
        result = await self._get_client().bulk_rerun_ai_scraper(**kwargs)
        return _serialize_response(result)


class MrScraperRerunManualScraper(MrScraperBaseTool):
    """Rerun a dashboard-defined manual scraper."""

    name: str = "mrscraper_rerun_manual_scraper"
    description: str = "Rerun a manual dashboard scraper on a target URL."
    args_schema: Type[BaseModel] = RerunManualScraperInput

    def _run(self, *args: Any, **kwargs: Any) -> str:
        params = self._first_arg_or_kwargs(args, kwargs)
        return _run_coro_sync(self._arun(**params))

    async def _arun(self, **kwargs: Any) -> str:
        result = await self._get_client().rerun_manual_scraper(**kwargs)
        return _serialize_response(result)


class MrScraperBulkRerunManualScraper(MrScraperBaseTool):
    """Rerun a manual scraper for multiple URLs."""

    name: str = "mrscraper_bulk_rerun_manual_scraper"
    description: str = (
        "Bulk rerun a manual scraper across multiple URLs in one request."
    )
    args_schema: Type[BaseModel] = BulkRerunManualScraperInput

    def _run(self, *args: Any, **kwargs: Any) -> str:
        params = self._first_arg_or_kwargs(args, kwargs)
        return _run_coro_sync(self._arun(**params))

    async def _arun(self, **kwargs: Any) -> str:
        result = await self._get_client().bulk_rerun_manual_scraper(**kwargs)
        return _serialize_response(result)


class MrScraperGetAllResults(MrScraperBaseTool):
    """Get paginated scraping results."""

    name: str = "mrscraper_get_all_results"
    description: str = (
        "List scraping results with pagination, sorting, search, and date filters."
    )
    args_schema: Type[BaseModel] = GetAllResultsInput

    def _run(self, *args: Any, **kwargs: Any) -> str:
        params = self._first_arg_or_kwargs(args, kwargs)
        return _run_coro_sync(self._arun(**params))

    async def _arun(self, **kwargs: Any) -> str:
        result = await self._get_client().get_all_results(**kwargs)
        return _serialize_response(result)


class MrScraperGetResultById(MrScraperBaseTool):
    """Get one scraping result by ID."""

    name: str = "mrscraper_get_result_by_id"
    description: str = "Fetch a specific scraping result by result ID."
    args_schema: Type[BaseModel] = GetResultByIdInput

    def _run(self, *args: Any, **kwargs: Any) -> str:
        params = self._first_arg_or_kwargs(args, kwargs)
        return _run_coro_sync(self._arun(**params))

    async def _arun(self, **kwargs: Any) -> str:
        result = await self._get_client().get_result_by_id(**kwargs)
        return _serialize_response(result)


TOOL_CLASSES: tuple[type[MrScraperBaseTool], ...] = (
    MrScraperFetchHTML,
    MrScraperCreateScraper,
    MrScraperRerunAIScraper,
    MrScraperBulkRerunAIScraper,
    MrScraperRerunManualScraper,
    MrScraperBulkRerunManualScraper,
    MrScraperGetAllResults,
    MrScraperGetResultById,
)


def load_mrscraper_tools(
    *,
    token: Optional[str] = None,
    mrscraper_api_key: Optional[str] = None,
    client: Optional[MrScraper] = None,
    tool_names: Optional[Sequence[str]] = None,
) -> list[BaseTool]:
    """Construct a configured list of MrScraper tools."""
    resolved_client = client
    resolved_token = (
        token
        or mrscraper_api_key
        or os.getenv("MRSCRAPER_API_KEY")
        or os.getenv("MRSCRAPER_API_TOKEN")
    )
    if resolved_client is None:
        if resolved_token is None:
            raise ValueError(
                "Either client, token, or mrscraper_api_key must be provided "
                "(or set MRSCRAPER_API_KEY / MRSCRAPER_API_TOKEN)."
            )
        resolved_client = MrScraper(token=resolved_token)

    tools = [tool_cls(client=resolved_client) for tool_cls in TOOL_CLASSES]
    if tool_names is None:
        return tools

    requested = set(tool_names)
    return [tool for tool in tools if tool.name in requested]


class MrScraperToolkit:
    """Factory object that returns configured MrScraper LangChain tools."""

    def __init__(
        self,
        *,
        token: Optional[str] = None,
        mrscraper_api_key: Optional[str] = None,
        client: Optional[MrScraper] = None,
        tool_names: Optional[Sequence[str]] = None,
    ) -> None:
        self._token = token
        self._mrscraper_api_key = mrscraper_api_key
        self._client = client
        self._tool_names = tool_names

    def get_tools(self) -> list[BaseTool]:
        """Return a list of MrScraper tools ready for LangChain agents."""
        return load_mrscraper_tools(
            token=self._token,
            mrscraper_api_key=self._mrscraper_api_key,
            client=self._client,
            tool_names=self._tool_names,
        )

