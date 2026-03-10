"""
LangChain integration for MrScraper.

Provides tools that wrap the MrScraper API for use with LangChain agents and chains.

Quick start::

    from langchain_mrscraper import MrScraperLoader

    tools = MrScraperLoader(token="MRSCRAPER_API_TOKEN").load()
    # Use with an agent, e.g. create_react_agent(model, tools)
"""

from .tools import (
    MrScraperBulkRerunAIScraperTool,
    MrScraperBulkRerunManualScraperTool,
    MrScraperCreateScraperTool,
    MrScraperFetchHTMLTool,
    MrScraperGetAllResultsTool,
    MrScraperGetResultByIdTool,
    MrScraperRerunManualScraperTool,
    MrScraperRerunScraperTool,
    MrScraperLoader,
)

__all__ = [
    "MrScraperLoader",
    "MrScraperFetchHTMLTool",
    "MrScraperCreateScraperTool",
    "MrScraperRerunScraperTool",
    "MrScraperBulkRerunAIScraperTool",
    "MrScraperRerunManualScraperTool",
    "MrScraperBulkRerunManualScraperTool",
    "MrScraperGetAllResultsTool",
    "MrScraperGetResultByIdTool",
]

__version__ = "0.1.0"
