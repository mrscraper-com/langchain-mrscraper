"""LangChain integration for the public MrScraper Python SDK services."""

from importlib.metadata import PackageNotFoundError, version

from .tools import (
    MrScraperGetScreenshot,
    MrScraperScrapeBrand,
    MrScraperScrapeHTML,
    MrScraperScrapeJSON,
    MrScraperScrapeMarkdown,
    MrScraperStatus,
    MrScraperToolkit,
    MrScraperWebSearch,
    load_mrscraper_tools,
)

__all__ = [
    "MrScraperGetScreenshot",
    "MrScraperScrapeBrand",
    "MrScraperScrapeHTML",
    "MrScraperScrapeJSON",
    "MrScraperScrapeMarkdown",
    "MrScraperStatus",
    "MrScraperToolkit",
    "MrScraperWebSearch",
    "load_mrscraper_tools",
]

try:
    __version__ = version("langchain-mrscraper")
except PackageNotFoundError:
    __version__ = "0.0.0"
