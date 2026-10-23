# langchain-mrscraper

LangChain tools for the [MrScraper Python SDK](https://pypi.org/project/mrscraper-sdk/). The toolkit exposes the same ten public services as `mrscraper-sdk>=0.7.0`.

## Installation

```bash
pip install -U langchain-mrscraper
```

The Python SDK and LangChain Core are installed automatically.

## Quick start

```python
import os
from langchain_mrscraper import MrScraperJSON, MrScraperToolkit

os.environ["MRSCRAPER_API_KEY"] = "your-token"

tools = MrScraperToolkit().get_tools()
result = MrScraperJSON().invoke({
    "url": "http://cireba.com/cayman-islands-real-estate-listings/",
    "prompt": "Extract property names, prices, locations, and listing URLs.",
})
print(result)
```

Every tool supports `.invoke(...)` and `await .ainvoke(...)`. Authentication can be supplied through `token`, `mrscraper_api_key`, `MRSCRAPER_API_KEY`, or `MRSCRAPER_API_TOKEN` (in that order). You can also inject an existing `mrscraper.MrScraper` client using `client=...`.

## Available tools

| Class | Tool name | SDK method / defaults |
| --- | --- | --- |
| `MrScraperHTML` | `mrscraper_scraper_html` | `scraper_html`; HTML output |
| `MrScraperMarkdown` | `mrscraper_scraper_markdown` | `scraper_markdown`; Markdown output |
| `MrScraperScreenshot` | `mrscraper_get_screenshot` | `get_screenshot`; `full_page=True`, `timeout=300`, `wait_until="domcontentloaded"` |
| `MrScraperJSON` | `mrscraper_scraper_json` | `scraper_json`; general agent, default extraction prompt |
| `MrScraperMultiplePage` | `mrscraper_scraper_multiple_page` | `scraper_multiple_page`; listing agent, `max_pages=3` |
| `MrScraperSitemap` | `mrscraper_scraper_sitemap` | `scraper_sitemap`; map agent, `max_depth=2`, `max_pages=3`, `limit=1000` |
| `MrScraperBrand` | `mrscraper_scrape_brand` | `scrape_brand`; `bundle="clean"` (`clean`, `full`, or `none`) |
| `MrScraperGetBrand` | `mrscraper_get_brand` | `get_brand`; required `job_id`, optional `output` |
| `MrScraperWebSearch` | `mrscraper_web_search` | `web_search`; Google v2 sync service |
| `MrScraperAccount` | `mrscraper_account` | `account`; account, quota, and rate limits |

HTML, Markdown, and screenshot flags are selected inside the SDK and are absent from tool parameters. The shared low-level request method is internal. JSON extraction always uses the general agent; multiple-page extraction uses listing; sitemap discovery uses map.

## Select tools for an agent

```python
from langchain_mrscraper import MrScraperToolkit

tools = MrScraperToolkit(
    token="your-token",
    tool_names=["mrscraper_scraper_json", "mrscraper_scraper_sitemap"],
).get_tools()
```

`load_mrscraper_tools(...)` accepts the same configuration. `tool_names` filters by the exact names above; an empty list returns no tools.

## Sitemap patterns and listing extraction

```python
from langchain_mrscraper import MrScraperMultiplePage, MrScraperSitemap

listing = MrScraperMultiplePage().invoke({
    "url": "http://cireba.com/cayman-islands-real-estate-listings/",
    "prompt": "Extract all property listings with prices and URLs.",
    "max_pages": 3,
})

sitemap = MrScraperSitemap().invoke({
    "url": "https://docs.mrscraper.com",
    "max_depth": 2,
    "max_pages": 3,
    "limit": 1000,
    "include_patterns": r"/products/.*",
    "exclude_patterns": r"/blog/.*",
})
```

Patterns are passed unchanged as `includePatterns` and `excludePatterns` in the API JSON body. Omit them to leave the corresponding fields unset.

## Brand jobs and binary output

```python
import base64
import json
from pathlib import Path
from langchain_mrscraper import MrScraperBrand, MrScraperGetBrand

job = MrScraperBrand().invoke({"url": "https://www.brooksrunning.com", "bundle": "clean"})
print(job)  # Read the job ID from the API response.

result = json.loads(MrScraperGetBrand().invoke({"job_id": "YOUR_JOB_ID", "output": "bundle"}))
Path("brand.zip").write_bytes(base64.b64decode(result["data"]["base64"]))
```

Omit `output` to retrieve job metadata, or use `html`, `bundle`, `screenshot`, or `screenshot_full` to download a file. Tool results are JSON strings containing the SDK's `status_code`, `data`, and `headers`. Binary image/ZIP `data` is represented losslessly as `{"encoding": "base64", "base64": "...", "size_bytes": 123}`. HTML remains text and JSON remains structured data. The content type is retained in `headers`.

## Google search

```python
from langchain_mrscraper import MrScraperWebSearch

result = MrScraperWebSearch().invoke({
    "url": "Cayman Islands real estate",  # A Google search URL also works.
    "raw": False,
    "format": "json",
    "region": "us",
    "language": "en",
    "page": 1,
})
```

Search delegates to the Python SDK's `/api/google/serp/v2/sync` service. The SDK compatibility default is `raw=True`, which selects HTML and overrides `format`; set `raw=False` for JSON. Search also accepts `render_js` and a positive `timeout` (default 600 seconds).

## Shared scraping controls

HTML, Markdown, JSON, listing, sitemap, and brand tools accept `timeout` (120 seconds by default), `geo_code`, `proxy_country`, `block_resources`, `browser_rendering`, `super`, `use_proxy`, `proxy`, `wait_for_selector`, `wait_until`, `home_page` (API `warmStart`), `bypass_proxy`, `cookie_jar`, `headers`, `max_retries`, `token_cap`, `stream`, and `discard_token_secret`.

Screenshot accepts the same controls except `browser_rendering`, which the SDK always enables, and adds `full_page`. `get_brand` accepts `job_id`, `output`, and `timeout`; `account` accepts `timeout` (30 seconds by default). Invalid URLs, limits, bundle/output values, or unsupported fields are rejected by the tool schema before making a request.

## Migration from the earlier integration

`MrScraperFetchHTML` and `MrScraperGoogleSerp` remain import aliases for `MrScraperHTML` and `MrScraperWebSearch`; they now use the current SDK services and current tool names. Update filters from `mrscraper_fetch_html` to `mrscraper_scraper_html` and from `mrscraper_google_serp` to `mrscraper_web_search`. The old search `session_cookie` argument is removed.

The earlier `MrScraperCreateScraper`, AI/manual rerun, bulk rerun, and result-list/retrieve tools are removed because those methods are absent from the current SDK. For extraction, use `MrScraperJSON` or `MrScraperMultiplePage` and rename `message` to `prompt`. For map discovery, use `MrScraperSitemap` and its crawl/pattern controls. For brand follow-up, use `MrScraperGetBrand` with the brand job ID. These services return their API results directly.

## Testing

```bash
pip install -e '.[dev]'
pytest tests/unit_tests -v
pytest -m 'not integration'
```

Live smoke tests are opt-in and consume API quota:

```bash
MRSCRAPER_RUN_LIVE=1 MRSCRAPER_API_KEY=your-token pytest tests/integration_tests -m integration -v
```

## Local release workflow

1. Update `version` in `pyproject.toml` when ready to release.
2. Build: `python -m build`.
3. Validate: `python -m twine check dist/*`.
4. Upload to TestPyPI: `python -m twine upload --repository testpypi dist/*`.
5. Verify installation, then upload to PyPI: `python -m twine upload dist/*`.

Provider and per-tool documentation for a LangChain docs submission live in `docs/providers/mrscraper.mdx` and `docs/tools/*.mdx`.
