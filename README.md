# langchain-mrscraper

![MrScraper](./mrscraper.jpeg)

LangChain tools integration for the [MrScraper](https://mrscraper.com) web-scraping API.

> [MrScraper](https://mrscraper.com) turns any website into clean, structured data via a stealth browser and AI-powered scrapers. It handles JavaScript rendering, bot detection, proxies, and anti-scraping measures automatically.

This package wraps every MrScraper API capability as a [LangChain Tool](https://docs.langchain.com/oss/python/langchain/tools), so LLM agents can scrape the web, create AI scrapers, rerun them in bulk, and retrieve results — all through natural-language tool calls.

---

## Overview

### Integration details

| Class | Package | Serializable | [JS support](https://js.langchain.com) | PyPI |
| :--- | :--- | :---: | :---: | :---: |
| `MrScraperFetchHTMLTool` | `langchain-mrscraper` | beta | ❌ | ![PyPI - Version](https://img.shields.io/pypi/v/langchain-mrscraper?style=flat-square&label=%20) |
| `MrScraperCreateScraperTool` | `langchain-mrscraper` | beta | ❌ | |
| `MrScraperRerunScraperTool` | `langchain-mrscraper` | beta | ❌ | |
| `MrScraperBulkRerunAIScraperTool` | `langchain-mrscraper` | beta | ❌ | |
| `MrScraperRerunManualScraperTool` | `langchain-mrscraper` | beta | ❌ | |
| `MrScraperBulkRerunManualScraperTool` | `langchain-mrscraper` | beta | ❌ | |
| `MrScraperGetAllResultsTool` | `langchain-mrscraper` | beta | ❌ | |
| `MrScraperGetResultByIdTool` | `langchain-mrscraper` | beta | ❌ | |

### Features

- **Stealth HTML fetching** — Render JavaScript, bypass bot detection, geo-proxy support
- **AI-powered scrapers** — Create scrapers with natural-language instructions (no CSS selectors needed)
- **Bulk operations** — Rerun scrapers across multiple URLs in a single batch
- **Manual scraper support** — Rerun dashboard-built scrapers programmatically
- **Result management** — Paginated listing, search, date filtering, and individual result retrieval
- **Full async support** — All tools support both sync (`invoke`) and async (`ainvoke`)
- **Pydantic schemas** — Every tool has a typed `args_schema` for reliable LLM tool calling

---

## Setup

### Credentials

Get your API token at [app.mrscraper.com](https://app.mrscraper.com).

```python
import getpass
import os

if "MRSCRAPER_API_TOKEN" not in os.environ:
    os.environ["MRSCRAPER_API_TOKEN"] = getpass.getpass("Enter your MrScraper API key: ")
```

Optionally enable [LangSmith](https://smith.langchain.com) tracing:

```python
os.environ["LANGSMITH_API_KEY"] = getpass.getpass("Enter your LangSmith API key: ")
os.environ["LANGSMITH_TRACING"] = "true"
```

### Installation

```bash
pip install -U langchain-mrscraper
```

Or with uv:

```bash
uv add langchain-mrscraper
```

Requires Python 3.9+. Installs `mrscraper-sdk` and `langchain-core` as dependencies.

---

## Instantiation

### Load all tools (recommended)

```python
from langchain_mrscraper import load_tools

tools = load_tools(token="MRSCRAPER_API_TOKEN")
```

### Load with an existing client

```python
from mrscraper import MrScraper
from langchain_mrscraper import load_tools

client = MrScraper(token="MRSCRAPER_API_TOKEN")
tools = load_tools(client=client)
```

### Load only specific tools

```python
tools = load_tools(
    token="MRSCRAPER_API_TOKEN",
    tool_names=["mrscraper_fetch_html", "mrscraper_create_scraper"],
)
```

### Instantiate individual tools

```python
from mrscraper import MrScraper
from langchain_mrscraper import MrScraperFetchHTMLTool, MrScraperCreateScraperTool

client = MrScraper(token="MRSCRAPER_API_TOKEN")
fetch_tool = MrScraperFetchHTMLTool(client=client)
create_tool = MrScraperCreateScraperTool(client=client)
```

---

## Invocation

### Direct invocation

```python
# Fetch rendered HTML from a URL
result = fetch_tool.invoke({"url": "https://example.com"})
print(result)

# Create an AI scraper
result = create_tool.invoke({
    "url": "https://example.com/products",
    "message": "Extract all product names and prices",
    "agent": "listing",
})
print(result)
```

### Async invocation

```python
import asyncio

result = asyncio.run(fetch_tool.ainvoke({
    "url": "https://example.com",
    "geo_code": "US",
    "timeout": 60,
}))
```

### As a ToolCall (model-generated)

```python
model_generated_tool_call = {
    "args": {"url": "https://example.com"},
    "id": "call_1",
    "name": "mrscraper_fetch_html",
    "type": "tool_call",
}
result = fetch_tool.invoke(model_generated_tool_call)
# Returns a ToolMessage
```

### Within an agent

```python
from langchain_mrscraper import load_tools
from langchain_anthropic import ChatAnthropic

tools = load_tools(token="MRSCRAPER_API_TOKEN")
llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)

# Bind tools to the model
llm_with_tools = llm.bind_tools(tools)

# Or use with an agent framework
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(llm, tools)
result = agent.invoke({
    "messages": [{"role": "user", "content": "Fetch the HTML of https://example.com and tell me the page title"}],
})
```

---

## Available tools

### `mrscraper_fetch_html` — Fetch rendered HTML

Fetch the fully rendered HTML of any webpage using MrScraper's stealth browser. Handles JavaScript rendering, bot detection, and geo-proxying.

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `url` | `str` | Yes | — | Full URL to fetch |
| `timeout` | `int` | No | `120` | Max seconds to wait |
| `geo_code` | `str` | No | `"US"` | ISO country code for proxy geo |
| `block_resources` | `bool` | No | `False` | Block images/CSS/fonts for speed |

### `mrscraper_create_scraper` — Create an AI scraper

Create and immediately run an AI-powered scraper using natural-language instructions. No CSS selectors or XPath required.

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `url` | `str` | Yes | — | Target URL to scrape |
| `message` | `str` | Yes | — | Natural-language extraction instructions |
| `agent` | `"general" \| "listing" \| "map"` | No | `"general"` | Agent type |
| `proxy_country` | `str \| None` | No | `None` | ISO country code for proxy |
| `max_depth` | `int` | No | `2` | (Map only) Crawl depth |
| `max_pages` | `int` | No | `50` | (Map only) Max pages |
| `limit` | `int` | No | `1000` | (Map only) Max records |
| `include_patterns` | `str` | No | `""` | (Map only) `\|\|`-separated URL regex to include |
| `exclude_patterns` | `str` | No | `""` | (Map only) `\|\|`-separated URL regex to exclude |

**Agent types:**

| Agent | Best for |
|-------|----------|
| `"general"` | Any single page (default) |
| `"listing"` | Product listings, job boards, search results |
| `"map"` | Crawling all sub-pages of a site |

### `mrscraper_rerun_scraper` — Rerun an AI scraper

Rerun an existing AI scraper on a new URL. Reuses the extraction logic from a previously created scraper.

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `scraper_id` | `str` | Yes | — | Scraper ID (from `create_scraper`) |
| `url` | `str` | Yes | — | Target URL |
| `max_depth` | `int` | No | `2` | (Map only) Crawl depth |
| `max_pages` | `int` | No | `50` | (Map only) Max pages |
| `limit` | `int` | No | `1000` | (Map only) Max records |
| `include_patterns` | `str` | No | `""` | (Map only) Include URL patterns |
| `exclude_patterns` | `str` | No | `""` | (Map only) Exclude URL patterns |

### `mrscraper_bulk_rerun_ai_scraper` — Bulk rerun AI scraper

Rerun an AI scraper on multiple URLs in a single batch request. More efficient than calling rerun one by one.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `scraper_id` | `str` | Yes | Scraper ID to rerun |
| `urls` | `list[str]` | Yes | List of target URLs (min 1) |

### `mrscraper_rerun_manual_scraper` — Rerun a manual scraper

Rerun a scraper created manually via the [MrScraper dashboard](https://app.mrscraper.com) on a new URL.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `scraper_id` | `str` | Yes | Manual scraper ID (from dashboard) |
| `url` | `str` | Yes | Target URL |

### `mrscraper_bulk_rerun_manual_scraper` — Bulk rerun manual scraper

Rerun a manual scraper on multiple URLs in one batch.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `scraper_id` | `str` | Yes | Manual scraper ID |
| `urls` | `list[str]` | Yes | List of target URLs (min 1) |

### `mrscraper_get_all_results` — List all results

Retrieve a paginated, sortable, filterable list of all scraping results.

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `sort_field` | `str` | No | `"updatedAt"` | Field to sort by |
| `sort_order` | `"ASC" \| "DESC"` | No | `"DESC"` | Sort direction |
| `page_size` | `int` | No | `10` | Results per page |
| `page` | `int` | No | `1` | Page number (1-indexed) |
| `search` | `str \| None` | No | `None` | Free-text search |
| `date_range_column` | `str \| None` | No | `None` | Column for date filter |
| `start_at` | `str \| None` | No | `None` | ISO-8601 start date |
| `end_at` | `str \| None` | No | `None` | ISO-8601 end date |

### `mrscraper_get_result_by_id` — Get a single result

Retrieve full details of a specific scraping result by its unique ID.

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `result_id` | `str` | Yes | Result ID |

---

## Response format

All tools return a JSON string with:

| Key | Type | Description |
|-----|------|-------------|
| `status_code` | `int` | HTTP status code |
| `data` | `Any` | Parsed JSON body or raw HTML |
| `headers` | `dict` | Response headers |

---

## Testing

### Run unit tests (no API key needed)

```bash
pytest tests/unit_tests/ -v
```

### Run integration tests (real API)

```bash
MRSCRAPER_API_TOKEN=your_token pytest tests/integration_tests/ -m integration -v
```

---

## Project structure

```
langchain-mrscraper/
├── pyproject.toml
├── README.md
├── LICENSE
├── mrscraper.jpeg
├── src/
│   └── langchain_mrscraper/
│       ├── __init__.py
│       └── tools.py
├── tests/
│   ├── unit_tests/
│   │   └── test_tools.py
│   └── integration_tests/
│       └── test_tools.py
└── docs/
    ├── mrscraper_provider.mdx
    └── mrscraper_tools.mdx
```

---

## How to publish to PyPI

### 1. Prerequisites

- [PyPI account](https://pypi.org/account/register/) with [API token](https://pypi.org/manage/account/token/) (2FA required)
- Build tools: `pip install build twine`

### 2. Bump version

In `pyproject.toml`:

```toml
version = "0.1.1"
```

### 3. Build

```bash
python -m build
```

### 4. Upload

**Test PyPI (recommended first):**

```bash
twine upload --repository testpypi dist/*
```

**Production PyPI:**

```bash
twine upload dist/*
# Username: __token__
# Password: your PyPI API token
```

### 5. Verify

```bash
pip install langchain-mrscraper
```

---

## Adding docs to LangChain

To list this integration on the [LangChain integrations page](https://docs.langchain.com/oss/python/integrations/providers/overview):

1. Fork the [LangChain docs repo](https://github.com/langchain-ai/docs)
2. Copy the `.mdx` files from this repo's `docs/` folder:
   - `docs/mrscraper_provider.mdx` → `src/oss/python/integrations/providers/mrscraper.mdx`
   - `docs/mrscraper_tools.mdx` → `src/oss/python/integrations/tools/mrscraper.mdx`
3. Open a PR to the docs repo

See the [LangChain publish guide](https://docs.langchain.com/oss/python/contributing/publish-langchain) for details.

---

## License

MIT © [MrScraper](https://mrscraper.com)
