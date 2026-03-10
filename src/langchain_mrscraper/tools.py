"""
LangChain tools for the MrScraper API.

Each tool wraps a MrScraper client method with a Pydantic args schema
so LLMs can invoke them via tool calls.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from mrscraper import MrScraper

class FetchHTMLInput(BaseModel):
    """Input for fetching rendered HTML from a URL."""

    url: str = Field(description="The full URL to fetch (e.g. https://example.com/page)")
    timeout: int = Field(default=120, description="Maximum seconds to wait for the page (default 120)")
    geo_code: str = Field(default="US", description="ISO country code for proxy geo (e.g. US, GB, SG)")
    block_resources: bool = Field(
        default=False,
        description="If True, block images/CSS/fonts to speed up the request",
    )


class CreateScraperInput(BaseModel):
    """Input for creating and running an AI-powered scraper."""

    url: str = Field(description="Target URL to scrape")
    message: str = Field(
        description="Natural-language description of what to extract (e.g. 'Extract all product names and prices')",
    )
    agent: Literal["general", "listing", "map"] = Field(
        default="general",
        description="Agent type: general (any page), listing (listings/grids), map (crawl sub-pages)",
    )
    proxy_country: str | None = Field(default=None, description="ISO country code for proxy (e.g. US, GB)")
    max_depth: int = Field(default=2, description="(Map agent only) Crawl depth from start URL")
    max_pages: int = Field(default=50, description="(Map agent only) Max pages to process")
    limit: int = Field(default=1000, description="(Map agent only) Max records to extract")
    include_patterns: str = Field(default="", description="(Map agent only) ||-separated URL regex to include")
    exclude_patterns: str = Field(default="", description="(Map agent only) ||-separated URL regex to exclude")


class RerunScraperInput(BaseModel):
    """Input for rerunning an existing AI scraper on a (new) URL."""

    scraper_id: str = Field(description="ID of the scraper to rerun (from create_scraper)")
    url: str = Field(description="Target URL; can be the original or a different page")
    max_depth: int = Field(default=2, description="(Map agent only) Crawl depth")
    max_pages: int = Field(default=50, description="(Map agent only) Max pages")
    limit: int = Field(default=1000, description="(Map agent only) Max records")
    include_patterns: str = Field(default="", description="(Map agent only) Include URL patterns")
    exclude_patterns: str = Field(default="", description="(Map agent only) Exclude URL patterns")


class BulkRerunAIScraperInput(BaseModel):
    """Input for rerunning an AI scraper on multiple URLs in one batch."""

    scraper_id: str = Field(description="ID of the AI scraper to rerun")
    urls: list[str] = Field(
        description="List of target URLs to scrape (at least one required)",
        min_length=1,
    )


class RerunManualScraperInput(BaseModel):
    """Input for rerunning a manually configured scraper on a single URL."""

    scraper_id: str = Field(description="ID of the manual scraper (from MrScraper dashboard)")
    url: str = Field(description="Target URL; page structure should match scraper's target")


class BulkRerunManualScraperInput(BaseModel):
    """Input for rerunning a manual scraper on multiple URLs in one batch."""

    scraper_id: str = Field(description="ID of the manual scraper")
    urls: list[str] = Field(
        description="List of target URLs (at least one required)",
        min_length=1,
    )


class GetAllResultsInput(BaseModel):
    """Input for listing scraping results with pagination and filters."""

    sort_field: Literal[
        "createdAt", "updatedAt", "id", "type", "url", "status", "error", "tokenUsage", "runtime"
    ] = Field(default="updatedAt", description="Field to sort by")
    sort_order: Literal["ASC", "DESC"] = Field(default="DESC", description="Sort order")
    page_size: int = Field(default=10, description="Results per page")
    page: int = Field(default=1, description="Page number (1-indexed)")
    search: str | None = Field(default=None, description="Free-text search across result fields")
    date_range_column: str | None = Field(default=None, description="Column for date filter (e.g. updatedAt)")
    start_at: str | None = Field(default=None, description="ISO-8601 start date for date range")
    end_at: str | None = Field(default=None, description="ISO-8601 end date for date range")


class GetResultByIdInput(BaseModel):
    """Input for fetching a single scraping result by ID."""

    result_id: str = Field(description="Unique ID of the result (from scraper runs or get_all_results)")


def _serialize_response(result: dict[str, Any]) -> str:
    """Convert API response to a string suitable for tool output."""
    import json
    try:
        return json.dumps(result, indent=2, default=str)
    except Exception:
        return str(result)


class MrScraperFetchHTMLTool(BaseTool):
    """Fetch the rendered HTML of a page via the MrScraper stealth browser."""

    name: str = "mrscraper_fetch_html"
    description: str = (
        "Fetch the rendered HTML of a webpage using MrScraper's stealth browser. "
        "Use this when you need raw HTML from a URL (handles JavaScript, bot detection, optional geo proxy)."
    )
    args_schema: Type[BaseModel] = FetchHTMLInput
    client: MrScraper = Field(exclude=True, description="MrScraper API client")

    def _run(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        return asyncio.run(self._arun(args))

    async def _arun(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        result = await self.client.fetch_html(
            url=args["url"],
            timeout=args.get("timeout", 120),
            geo_code=args.get("geo_code", "US"),
            block_resources=args.get("block_resources", False),
        )
        return _serialize_response(result)


class MrScraperCreateScraperTool(BaseTool):
    """Create and run an AI-powered scraper with natural-language instructions."""

    name: str = "mrscraper_create_scraper"
    description: str = (
        "Create an AI scraper that extracts data from a URL based on a natural-language message. "
        "Returns scraper ID for later reruns. Agent types: general (any page), listing (product/list pages), map (crawl site)."
    )
    args_schema: Type[BaseModel] = CreateScraperInput
    client: MrScraper = Field(exclude=True, description="MrScraper API client")

    def _run(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        return asyncio.run(self._arun(args))

    async def _arun(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        result = await self.client.create_scraper(
            url=args["url"],
            message=args["message"],
            agent=args.get("agent", "general"),
            proxy_country=args.get("proxy_country"),
            max_depth=args.get("max_depth", 2),
            max_pages=args.get("max_pages", 50),
            limit=args.get("limit", 1000),
            include_patterns=args.get("include_patterns", ""),
            exclude_patterns=args.get("exclude_patterns", ""),
        )
        return _serialize_response(result)


class MrScraperRerunScraperTool(BaseTool):
    """Rerun an existing AI scraper on a (new) URL."""

    name: str = "mrscraper_rerun_scraper"
    description: str = (
        "Rerun an existing AI scraper on a URL. Reuses extraction logic from a previously created scraper."
    )
    args_schema: Type[BaseModel] = RerunScraperInput
    client: MrScraper = Field(exclude=True, description="MrScraper API client")

    def _run(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        return asyncio.run(self._arun(args))

    async def _arun(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        result = await self.client.rerun_scraper(
            scraper_id=args["scraper_id"],
            url=args["url"],
            max_depth=args.get("max_depth", 2),
            max_pages=args.get("max_pages", 50),
            limit=args.get("limit", 1000),
            include_patterns=args.get("include_patterns", ""),
            exclude_patterns=args.get("exclude_patterns", ""),
        )
        return _serialize_response(result)


class MrScraperBulkRerunAIScraperTool(BaseTool):
    """Rerun an AI scraper on multiple URLs in one batch."""

    name: str = "mrscraper_bulk_rerun_ai_scraper"
    description: str = (
        "Rerun an AI scraper on multiple URLs in a single batch. More efficient than rerunning one by one."
    )
    args_schema: Type[BaseModel] = BulkRerunAIScraperInput
    client: MrScraper = Field(exclude=True, description="MrScraper API client")

    def _run(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        return asyncio.run(self._arun(args))

    async def _arun(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        result = await self.client.bulk_rerun_ai_scraper(
            scraper_id=args["scraper_id"],
            urls=args["urls"],
        )
        return _serialize_response(result)


class MrScraperRerunManualScraperTool(BaseTool):
    """Rerun a manually configured scraper (dashboard) on a single URL."""

    name: str = "mrscraper_rerun_manual_scraper"
    description: str = (
        "Rerun a manually configured scraper (created in MrScraper dashboard) on a new URL."
    )
    args_schema: Type[BaseModel] = RerunManualScraperInput
    client: MrScraper = Field(exclude=True, description="MrScraper API client")

    def _run(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        return asyncio.run(self._arun(args))

    async def _arun(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        result = await self.client.rerun_manual_scraper(
            scraper_id=args["scraper_id"],
            url=args["url"],
        )
        return _serialize_response(result)


class MrScraperBulkRerunManualScraperTool(BaseTool):
    """Rerun a manual scraper on multiple URLs in one batch."""

    name: str = "mrscraper_bulk_rerun_manual_scraper"
    description: str = (
        "Rerun a manual scraper on multiple URLs in a single batch. Use get_all_results or get_result_by_id to fetch results."
    )
    args_schema: Type[BaseModel] = BulkRerunManualScraperInput
    client: MrScraper = Field(exclude=True, description="MrScraper API client")

    def _run(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        return asyncio.run(self._arun(args))

    async def _arun(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        result = await self.client.bulk_rerun_manual_scraper(
            scraper_id=args["scraper_id"],
            urls=args["urls"],
        )
        return _serialize_response(result)


class MrScraperGetAllResultsTool(BaseTool):
    """List all scraping results with pagination and filters."""

    name: str = "mrscraper_get_all_results"
    description: str = (
        "Retrieve a paginated, sortable list of all scraping results. Can filter by search and date range."
    )
    args_schema: Type[BaseModel] = GetAllResultsInput
    client: MrScraper = Field(exclude=True, description="MrScraper API client")

    def _run(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        return asyncio.run(self._arun(args))

    async def _arun(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        result = await self.client.get_all_results(
            sort_field=args.get("sort_field", "updatedAt"),
            sort_order=args.get("sort_order", "DESC"),
            page_size=args.get("page_size", 10),
            page=args.get("page", 1),
            search=args.get("search"),
            date_range_column=args.get("date_range_column"),
            start_at=args.get("start_at"),
            end_at=args.get("end_at"),
        )
        return _serialize_response(result)


class MrScraperGetResultByIdTool(BaseTool):
    """Fetch a single scraping result by its ID."""

    name: str = "mrscraper_get_result_by_id"
    description: str = "Retrieve full details of a specific scraping result by its ID."
    args_schema: Type[BaseModel] = GetResultByIdInput
    client: MrScraper = Field(exclude=True, description="MrScraper API client")

    def _run(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        return asyncio.run(self._arun(args))

    async def _arun(self, tool_input: dict[str, Any] | None = None, **kwargs: Any) -> str:
        args = tool_input if tool_input is not None else kwargs
        result = await self.client.get_result_by_id(result_id=args["result_id"])
        return _serialize_response(result)

_TOOL_CLASSES = [
    MrScraperFetchHTMLTool,
    MrScraperCreateScraperTool,
    MrScraperRerunScraperTool,
    MrScraperBulkRerunAIScraperTool,
    MrScraperRerunManualScraperTool,
    MrScraperBulkRerunManualScraperTool,
    MrScraperGetAllResultsTool,
    MrScraperGetResultByIdTool,
]


def load_tools(
    token: str | None = None,
    client: MrScraper | None = None,
    *,
    tool_names: list[str] | None = None,
) -> list[BaseTool]:
    """
    Create LangChain tools for the MrScraper API.

    Provide either ``token`` or an existing ``client``. If both are given, ``client`` is used.

    Args:
        token: MrScraper API token (from https://app.mrscraper.com). Ignored if client is set.
        client: Existing MrScraper client. If None, one is created from token.
        tool_names: If set, only tools whose name is in this list are returned.
                    Default is all tools.

    Returns:
        List of BaseTool instances ready for use with LangChain agents.

    Example::

        from langchain_mrscraper import load_tools

        tools = load_tools(token="MRSCRAPER_API_TOKEN")
        # Use with an agent
        agent = create_react_agent(model, tools)
    """
    if client is None:
        if token is None:
            raise ValueError("Either token or client must be provided")
        client = MrScraper(token=token)

    tools = [cls(client=client) for cls in _TOOL_CLASSES]
    if tool_names is not None:
        names_set = set(tool_names)
        tools = [t for t in tools if t.name in names_set]
    return tools
