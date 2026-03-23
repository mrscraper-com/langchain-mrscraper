"""LangChain integration package for MrScraper tools."""

from importlib.metadata import PackageNotFoundError, version

from .tools import (
    MrScraperBulkRerunAIScraper,
    MrScraperBulkRerunManualScraper,
    MrScraperCreateScraper,
    MrScraperFetchHTML,
    MrScraperGetAllResults,
    MrScraperGetResultById,
    MrScraperRerunManualScraper,
    MrScraperRerunAIScraper,
    MrScraperToolkit,
    load_mrscraper_tools,
)

__all__ = [
    "load_mrscraper_tools",
    "MrScraperToolkit",
    "MrScraperFetchHTML",
    "MrScraperCreateScraper",
    "MrScraperRerunAIScraper",
    "MrScraperBulkRerunAIScraper",
    "MrScraperRerunManualScraper",
    "MrScraperBulkRerunManualScraper",
    "MrScraperGetAllResults",
    "MrScraperGetResultById",
]

try:
    __version__ = version("langchain-mrscraper")
except PackageNotFoundError:
    __version__ = "0.0.0"
