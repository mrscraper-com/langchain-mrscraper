# langchain-mrscraper

LangChain tools for the [MrScraper Python SDK](https://pypi.org/project/mrscraper-sdk/). The toolkit exposes the three public services of `mrscraper-sdk>=0.9.0,<0.10.0`: the Scraper API, Web Search, and account usage.

## Installation

```bash
pip install -U langchain-mrscraper
```

The Python SDK and LangChain Core are installed automatically.

## Quick start

```python
import os
from langchain_mrscraper import MrScraperScraperAPI, MrScraperToolkit

os.environ["MRSCRAPER_API_KEY"] = "your-token"

tools = MrScraperToolkit().get_tools()  # all three tools for an agent

result = MrScraperScraperAPI().invoke({
    "url": "https://books.toscrape.com/",
    "markdown": True,
})
print(result)
```

Every tool supports `.invoke(...)` and `await .ainvoke(...)`. Authentication can be supplied through `token`, `mrscraper_api_key`, `MRSCRAPER_API_KEY`, or `MRSCRAPER_API_TOKEN` (in that order). You can also inject an existing `mrscraper.MrScraper` client using `client=...`.

## Available tools

| Class | Tool name | SDK method | Input fields |
| --- | --- | --- | --- |
| `MrScraperScraperAPI` | `mrscraper_scraper_api` | `scraper_api` | `url`, `html`, `markdown`, `screenshot`, plus page controls (below) |
| `MrScraperWebSearch` | `mrscraper_web_search` | `web_search` | `query`, `country`, `num_results` (10–100), `timeout` |
| `MrScraperAccount` | `mrscraper_account` | `account` | `timeout` |

Tool results are JSON strings containing the SDK's `status_code`, `data`, and `headers`.

## Scraper API

Fetch a public web page as rendered HTML, Markdown, screenshot, or a combination.

```python
import base64
import json
from langchain_mrscraper import MrScraperScraperAPI

tool = MrScraperScraperAPI()

html = json.loads(tool.invoke({"url": "https://books.toscrape.com/"}))
print(html["data"][:200])  # HTML only (the default) returns the HTML string

combined = json.loads(tool.invoke({
    "url": "https://books.toscrape.com/",
    "html": True,
    "markdown": True,
    "screenshot": True,
}))
print(combined["data"]["markdown"][:200])
png = base64.b64decode(combined["data"]["screenshot"])
```

`html` defaults to `True`; `markdown` and `screenshot` default to `False`. At least one must be true. Requesting Markdown or a screenshot returns an object in `data` with an entry for each requested output; the screenshot is a base64 string. `screenshot=True` enables browser rendering, so combining it with `browser_rendering=False` is rejected.

Page controls: `timeout` (1–300 seconds, default 120), `geo_code` (default `"US"`), `proxy_country`, `block_resources`, `browser_rendering`, `super`, `use_proxy`, `proxy`, `wait_for_selector`, `wait_until`, `home_page`, `bypass_proxy`, `cookie_jar`, `headers`, `max_retries`, `token_cap`, `stream`, and `discard_token_secret`. Invalid URLs, limits, or unsupported fields are rejected by the tool schema before a request is made.

## Web Search

Search the web for real-time results: website URLs, titles, and descriptions.

```python
from langchain_mrscraper import MrScraperWebSearch

result = MrScraperWebSearch().invoke({
    "query": "e-menessaptieka.lv linkedin",
    "country": "us",
    "num_results": 10,
})
```

`query` is required. `country` is optional (the service default applies when omitted). `num_results` is an integer from 10 to 100 (default 10). `timeout` defaults to 600 seconds. The response `data` is `{"success", "message", "data": [...]}`, where each result has `rank`, `title`, `url`, `description`, and `source`.

## Account

```python
from langchain_mrscraper import MrScraperAccount

print(MrScraperAccount().invoke({}))
```

Returns subscription status, token usage and limits, remaining quota, and rate limits. `timeout` defaults to 30 seconds.

## Select tools for an agent

```python
from langchain_mrscraper import MrScraperToolkit

tools = MrScraperToolkit(
    token="your-token",
    tool_names=["mrscraper_scraper_api", "mrscraper_web_search"],
).get_tools()
```

`load_mrscraper_tools(...)` accepts the same configuration. `tool_names` filters by the exact names above; an empty list returns no tools.

## Migration from 0.3.x

Version 0.5.0 requires `mrscraper-sdk>=0.9.0,<0.10.0`, which exposes exactly three public methods. The toolkit now returns three tools instead of ten.

| 0.3.x tool | 0.5.0 replacement |
| --- | --- |
| `MrScraperHTML` (`mrscraper_scraper_html`) | `MrScraperScraperAPI` with `{"url": ...}` |
| `MrScraperMarkdown` (`mrscraper_scraper_markdown`) | `MrScraperScraperAPI` with `{"url": ..., "html": False, "markdown": True}` |
| `MrScraperScreenshot` (`mrscraper_get_screenshot`) | `MrScraperScraperAPI` with `{"url": ..., "html": False, "screenshot": True}` |
| `MrScraperJSON`, `MrScraperMultiplePage`, `MrScraperSitemap`, `MrScraperBrand`, `MrScraperGetBrand` | Removed (no public SDK method). Fetch pages with `MrScraperScraperAPI` and let your model extract data, or pin `langchain-mrscraper<0.4`. |
| `MrScraperWebSearch` (`url`, `raw`, `format`, `region`, `language`, `page`, `render_js`) | `MrScraperWebSearch` (`query`, `country`, `num_results`, `timeout`) |
| `MrScraperAccount` | Unchanged |
| `MrScraperFetchHTML` import alias | Removed; use `MrScraperScraperAPI` |

Other notes:

- Screenshots now come back as a base64 string inside `data` (`data["screenshot"]`) together with any other requested outputs. The 0.3.x screenshot `full_page` option and its `timeout=300` / `wait_until="domcontentloaded"` defaults no longer exist; pass `timeout` and `wait_until` explicitly when needed.
- Update toolkit `tool_names` filters to `mrscraper_scraper_api`, `mrscraper_web_search`, and `mrscraper_account`.
- Earlier tools (create/rerun/bulk-rerun scrapers and result listing) remain removed.

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

`python manual_check_tools.py` runs every tool against the real API and saves responses to `debug_results/`.

## Local release workflow

1. Update `version` in `pyproject.toml` when ready to release.
2. Build: `python -m build`.
3. Validate: `python -m twine check dist/*`.
4. Upload to TestPyPI: `python -m twine upload --repository testpypi dist/*`.
5. Verify installation, then upload to PyPI: `python -m twine upload dist/*`.

Provider and per-tool documentation for a LangChain docs submission live in `docs/providers/mrscraper.mdx` and `docs/tools/*.mdx`.
