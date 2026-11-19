# MrScraper LangChain Tools

![MrScraper](./mrscraper.jpeg)

Seven tools matching the [MrScraper CLI](https://github.com/mrscraper-com/cli), backed by the async Python SDK. Tool names and arguments use Python snake_case.

| CLI command | Tool name | Exported class | Purpose |
| --- | --- | --- | --- |
| `status` | `mrscraper_status` | `MrScraperStatus` | Raw account status API response |
| `scrape-html` | `mrscraper_scrape_html` | `MrScraperScrapeHTML` | Raw page HTML |
| `scrape-markdown` | `mrscraper_scrape_markdown` | `MrScraperScrapeMarkdown` | Markdown, optionally with HTML |
| `get-screenshot` | `mrscraper_get_screenshot` | `MrScraperGetScreenshot` | Full-page or top-viewport screenshot |
| `scrape-brand` | `mrscraper_scrape_brand` | `MrScraperScrapeBrand` | Website brand data as JSON |
| `scrape-json` | `mrscraper_scrape_json` | `MrScraperScrapeJSON` | Structured extraction using a prompt |
| `web-search` | `mrscraper_web_search` | `MrScraperWebSearch` | Ranked web search results |

## Installation and authentication

Requires Python 3.9+, LangChain Core, and `mrscraper-sdk>=0.10.0,<0.11.0` with the seven-service interface below. Obtain a token from [the MrScraper app](https://app.mrscraper.com).

```bash
python -m pip install -U langchain-mrscraper
export MRSCRAPER_API_TOKEN="YOUR_TOKEN"
```

Before these releases are published, install the local SDK and integration together:

```bash
python -m pip install -e ../sdk-python -e '.[test]'
```

Pass `token=`, `mrscraper_api_key=`, or an existing `client=MrScraper(...)` when constructing a tool or toolkit. Otherwise, credentials come from `MRSCRAPER_API_KEY`, then `MRSCRAPER_API_TOKEN`. Authentication is configured outside tool inputs.

## Quickstart

```python
import json

from langchain_mrscraper import MrScraperToolkit


tools = MrScraperToolkit().get_tools()
by_name = {tool.name: tool for tool in tools}
result = by_name["mrscraper_scrape_html"].invoke({
    "url": "https://example.com",
    "browser_rendering": True,
})
print(json.loads(result)["data"])
```

Tools return a JSON string and support both `invoke` and `ainvoke`, including synchronous invocation in notebooks with a running event loop. Examples use `example.com` as the target; replace it for your use case. Live requests use your account quota.

## Shared page parameters

These fields apply to HTML, Markdown, screenshots, and JSON extraction. Unsupported fields are rejected by the Pydantic input schemas.

| CLI option | Python argument | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| URL argument | `url` | `str` | required | Absolute HTTP or HTTPS page URL. |
| `--timeout` | `timeout` | `int` | `300` | Page deadline in seconds, 1–300; HTTP transport adds 30 seconds. |
| `--geo-code` | `geo_code` | `str` | `"us"` | Country to load the page from; two ASCII letters, sent in lowercase. |
| `--proxy-country` | `proxy_country` | `str` | `"us"` | Proxy server country; two ASCII letters, sent in lowercase. |
| `--super` | `super` | `bool` | `False` | Use real-device routing. |
| `--wait-until` | `wait_until` | literal string | `"domcontentloaded"` | Also accepts `"load"`, `"networkidle0"`, or `"networkidle2"`. |
| `--proxy` | `proxy` | `str` or `None` | `None` | Custom proxy URL; omitted when unset. |
| `--max-retries` | `max_retries` | `int` or `None` | `None` | Nonnegative retry limit; omission means no limit. Zero is preserved. |
| `--save-result` | `save_result` | `bool` | `False` | Save the result in the dashboard. |

HTML, Markdown, and screenshots also accept these controls. JSON extraction does not accept them.

| CLI option | Python argument | Type | Default | Meaning |
| --- | --- | --- | --- | --- |
| `--block-resources` | `block_resources` | `bool` | `False` | Block images, fonts, and stylesheets. |
| `--wait-for-selector` | `wait_for_selector` | `str` or `None` | `None` | CSS selector to wait for; omitted when unset. |
| `--return-cookie` | `return_cookie` | `bool` | `False` | Include browser session cookies. |

Use Python `True`, `False`, and `None` in dictionaries. JSON passed to a manual runner uses `true`, `false`, and `null`. Options left unset use the defaults above.

## Service examples

### Status

```python
import json
from langchain_mrscraper import MrScraperStatus

result = json.loads(MrScraperStatus().invoke({}))
print(result["data"])
```

Status takes an empty input object. Its HTTP deadline is fixed at 600 seconds, matching the CLI. The complete API response body is preserved inside `data`, including its original fields and nesting. No account summary, redaction of body fields, or calculated fields are added. Sensitive response headers are removed. When the API wraps account details in `data`, access them through `result["data"]["data"]`.

### Scrape HTML

```python
import json
from langchain_mrscraper import MrScraperScrapeHTML

result = json.loads(MrScraperScrapeHTML().invoke({
    "url": "https://example.com",
    "browser_rendering": True,
    "wait_for_selector": ".content",
    "wait_until": "networkidle2",
    "timeout": 120,
    "geo_code": "us",
    "proxy_country": "us",
    "super": False,
    "max_retries": 0,
    "save_result": False,
    "block_resources": False,
    "return_cookie": False,
}))
print(result["data"])
```

`browser_rendering` is a `bool`, default `False`. HTML always requests `html=true`, `markdown=false`, and `screenshot=false`. The default body is HTML text; some page controls can make the API return JSON instead.

### Scrape Markdown

```python
import json
from langchain_mrscraper import MrScraperScrapeMarkdown

result = json.loads(MrScraperScrapeMarkdown().invoke({
    "url": "https://example.com",
    "html": True,
    "browser_rendering": False,
}))
print(result["data"])
```

`html` and `browser_rendering` are booleans, both default `False`. Setting `html=True` forces browser rendering and returns both outputs as JSON. Otherwise, Markdown is returned as text. This service always requests `markdown=true` and `screenshot=false`.

### Get screenshot

```python
import base64
import json
from pathlib import Path
from langchain_mrscraper import MrScraperGetScreenshot

result = json.loads(MrScraperGetScreenshot().invoke({
    "url": "https://example.com",
    "screenshot": "top",
    "html": False,
    "markdown": True,
}))
image = result["data"]["screenshot"]
Path("page.png").write_bytes(base64.b64decode(image))
```

| Argument | Type | Default | Meaning |
| --- | --- | --- | --- |
| `screenshot` | `"full"` or `"top"` | `"full"` | Entire page or top viewport. |
| `html` | `bool` | `True` | Include page HTML. |
| `markdown` | `bool` | `False` | Include Markdown. |

Browser rendering is always enabled; there is no `browser_rendering` input for screenshots. Screenshot JSON retains the upstream base64 image. The API can still include HTML when `html=False` is requested.

### Scrape brand

```python
import json
from langchain_mrscraper import MrScraperScrapeBrand

result = json.loads(MrScraperScrapeBrand().invoke({
    "url": "https://example.com",
}))
print(result["data"])
```

Only `url` is accepted. The request uses `action=brand-scraping&bundle=none` and a fixed 120-second HTTP deadline. Brand data is typically in `result["data"]["data"]["brand"]`; the API's structure is preserved.

### Scrape JSON

```python
import json
from langchain_mrscraper import MrScraperScrapeJSON

result = json.loads(MrScraperScrapeJSON().invoke({
    "url": "https://example.com",
    "prompt": 'Extract the page title. Json Schema: {"type":"object","properties":{"title":{"type":"string"}}}',
    "browser_rendering": True,
    "html": False,
    "screenshot": False,
    "timeout": 180,
}))
print(result["data"])
```

| Argument | Type | Default | Meaning |
| --- | --- | --- | --- |
| `prompt` | `str` | `"Extract all data as complete as possible."` | Nonempty extraction instruction. Append `Json Schema:` and a schema to shape output. |
| `browser_rendering` | `bool` | `False` | Enable browser rendering. |
| `html` | `bool` | `False` | Include HTML. |
| `screenshot` | `bool` | `False` | Include a base64 screenshot. |

The SDK uses the `general` agent and GET requests. If the encoded URL exceeds 8,000 characters, it uses POST with `url`, `prompt`, and `agent` in the body and page controls in the query. Loading and cookie controls are unavailable.

### Web search

```python
import json
from langchain_mrscraper import MrScraperWebSearch

result = json.loads(MrScraperWebSearch().invoke({
    "query": "site:example.com documentation",
    "country": "id",
    "num_results": 20,
}))
print(result["data"])
```

| Argument | Type | Default | Meaning |
| --- | --- | --- | --- |
| `query` | `str` | required | Trimmed query text, 1–1,000 characters. |
| `country` | `str` | `"us"` | Two-letter country code, sent in lowercase. |
| `num_results` | `int` | `10` | Requested result count, 10–100; fewer may be returned. |

Search uses a fixed 120-second HTTP deadline and has no `timeout` input. The result retains the API's `success`, `message`, and `data` fields, with ranked titles, URLs, descriptions, and sources.

## Async use and tool selection

```python
import asyncio
import json
from langchain_mrscraper import MrScraperToolkit, load_mrscraper_tools

async def main():
    toolkit = MrScraperToolkit(tool_names=["mrscraper_scrape_markdown"])
    tool = toolkit.get_tools()[0]
    result = json.loads(await tool.ainvoke({"url": "https://example.com"}))
    print(result["data"])

asyncio.run(main())

# An empty selection returns no tools.
assert load_mrscraper_tools(token="YOUR_TOKEN", tool_names=[]) == []
```

A toolkit shares one SDK client across its tools. To reuse an HTTP connection pool, construct `MrScraper(http_client=http_client)` and pass it as `client=`. Manage the supplied HTTP client's lifetime yourself.

## Responses and errors

Each tool returns a JSON string containing `status_code`, `data`, and `headers`. Parse it with `json.loads`:

```json
{
  "status_code": 200,
  "data": "<html><body>Example</body></html>",
  "headers": {"content-type": "text/html"}
}
```

JSON response bodies keep their API fields and nesting; text remains a string. Binary responses are encoded as `{ "encoding": "base64", "base64": "…", "size_bytes": 123 }`. Combined page outputs retain the API structure.

Invalid input raises Pydantic `ValidationError`. Authentication, HTTP, and transport failures propagate as the Python SDK's `AuthenticationError`, `APIError`, and `NetworkError` respectively. `APIError.status_code` contains the HTTP status when available.

## Migration

Replace `MrScraperAccount` / `mrscraper_account` with `MrScraperStatus` / `mrscraper_status`. Status returns the raw API body; remove its old `timeout` input. Search also uses a fixed transport deadline and no longer accepts `timeout`.

Replace the combined `scraper_api` service with `scrape_html`, `scrape_markdown`, or `get_screenshot`. Use the latter two for combined outputs. Replace `full_page` with `screenshot="full"` or `"top"`. Search uses `query`, `country`, and `num_results`. Legacy job, sitemap, rerun, result, and bundle-download methods are outside this seven-service interface.

## Development and manual checks

```bash
python -m pip install -e ../sdk-python -e '.[test]'
python -m pytest -m "not integration" -q
```

The offline suite compares each tool schema and default with the Python SDK and exercises real SDK request construction with local HTTP responses. Manual checks make live calls and use quota:

```bash
export MRSCRAPER_API_TOKEN="YOUR_TOKEN"
python manual_test.py status
python manual_test.py scrape_html --url https://example.com
python manual_test.py scrape_markdown --url https://example.com --args '{"html":true}'
python manual_test.py get_screenshot --url https://example.com --args '{"screenshot":"top"}'
python manual_test.py scrape_brand --url https://example.com
python manual_test.py scrape_json --url https://example.com --args '{"prompt":"Extract the page title"}'
python manual_test.py web_search --query 'site:example.com documentation' --args '{"country":"id","num_results":20}'
python manual_check_tools.py --async --only mrscraper_web_search
```

Add `--async` before the service in `manual_test.py` for `ainvoke`. Responses and screenshots are saved under `debug_results/`; failures exit nonzero. The opt-in live pytest suite requires `MRSCRAPER_RUN_LIVE=1`.

## License

MIT. See [LICENSE](./LICENSE).
