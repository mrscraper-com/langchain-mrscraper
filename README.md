# MrScraper LangChain Tools

![](./mrscraper.jpeg)

Seven services matching the [MrScraper CLI](https://github.com/mrscraper-com/cli).

| Service | Tool | Purpose |
| --- | --- | --- |
| `account` | `mrscraper_account` | Account, subscription, quota, and rate limits |
| `scrape-html` | `mrscraper_scrape_html` | Raw page HTML |
| `scrape-markdown` | `mrscraper_scrape_markdown` | Clean Markdown; optional HTML |
| `get-screenshot` | `mrscraper_get_screenshot` | Full-page or top-viewport base64 screenshot |
| `scrape-brand` | `mrscraper_scrape_brand` | Brand data as JSON |
| `scrape-json` | `mrscraper_scrape_json` | Structured extraction using a prompt |
| `web-search` | `mrscraper_web_search` | Ranked web search results |

## Install and use

Requires Python 3.9+, LangChain Core, and `mrscraper-sdk>=0.10.0,<0.11.0`. Publish/install the new Python SDK before installing this release. Obtain a token from [the app](https://app.mrscraper.com).

```bash
python -m pip install -U langchain-mrscraper
export MRSCRAPER_API_TOKEN="YOUR_TOKEN"
```

```python
from langchain_mrscraper import MrScraperToolkit, MrScraperScrapeJSON

# All seven tools share one SDK client.
tools = MrScraperToolkit().get_tools()
by_name = {tool.name: tool for tool in tools}
print(by_name["mrscraper_account"].invoke({}))
print(by_name["mrscraper_scrape_html"].invoke({"url": "https://books.toscrape.com/"}))
print(by_name["mrscraper_web_search"].invoke({"query": "web scraping", "country": "id", "num_results": 20}))
print(MrScraperScrapeJSON().invoke({"url": "https://books.toscrape.com/", "prompt": "Extract titles and prices"}))
```

Tools support `invoke` and `ainvoke`, including synchronous invocation in notebooks. They return a JSON string with `status_code`, `data`, and `headers`. Binary responses are encoded as `{ "encoding": "base64", "base64": "…", "size_bytes": 123 }`. API errors propagate from the SDK. Input schemas reject unsupported fields.

Exports: `MrScraperAccount`, `MrScraperScrapeHTML`, `MrScraperScrapeMarkdown`, `MrScraperGetScreenshot`, `MrScraperScrapeBrand`, `MrScraperScrapeJSON`, `MrScraperWebSearch`, `MrScraperToolkit`, and `load_mrscraper_tools`.

Pass `token=`, `mrscraper_api_key=`, or an existing `client=MrScraper(...)` to tools/toolkit, or set `MRSCRAPER_API_KEY` / `MRSCRAPER_API_TOKEN`. Use `tool_names=["mrscraper_web_search"]` to select tools; an empty list returns none. Account accepts a positive `timeout` (default 30 seconds) and returns the Python SDK's safe account summary.

## Options

| Python / LangChain | Node / MCP | Default | Meaning |
| --- | --- | --- | --- |
| `timeout` | `timeout` | `300` | Page deadline in seconds, integer 1–300 |
| `geo_code` | `geoCode` | `"us"` | Country to load the page from |
| `proxy_country` | `proxyCountry` | `"us"` | Proxy server country |
| `super` | `superMode` | `False` / `false` | Use real-device routing; sent as `super` |
| `wait_until` | `waitUntil` | `"domcontentloaded"` | Also accepts `load`, `networkidle0`, `networkidle2` |
| `proxy` | `proxy` | omitted | Custom proxy URL |
| `max_retries` | `maxRetries` | omitted | Nonnegative retry limit; omission means no limit |
| `save_result` | `saveResult` | `False` / `false` | Save the result in the dashboard |
| `block_resources` | `blockResources` | `False` / `false` | Block images, fonts, and stylesheets |
| `wait_for_selector` | `waitForSelector` | omitted | Wait for a CSS selector |
| `return_cookie` | `returnCookie` | `False` / `false` | Include session cookies |
| `browser_rendering` | `browserRendering` | `False` / `false` | Enable browser rendering |

The first eight page controls apply to HTML, Markdown, screenshots, and JSON. The three loading controls (`block_resources`/`blockResources`, `wait_for_selector`/`waitForSelector`, `return_cookie`/`returnCookie`) apply to HTML, Markdown, and screenshots. Browser rendering can be selected for HTML, Markdown, and JSON; screenshots always enable it.

Markdown accepts `html=False` / `html: false`; enabling HTML forces browser rendering. Screenshots accept `screenshot="full"` or `"top"`, `html=True` / `true`, and `markdown=False` / `false`. JSON accepts a `prompt` (default `"Extract all data as complete as possible."`), `html=False` / `false`, and `screenshot=False` / `false`. JSON does not expose loading or cookie controls. Brand takes only the target URL, plus authentication in the Node SDK.

Search takes `query`, `country="us"`, and `num_results=10` / `numResults: 10` (integer 10–100). Queries are trimmed and must contain 1–1,000 characters. Countries are two ASCII letters and are sent in lowercase. Search also accepts a positive local `timeout`, default 120 seconds. This timeout is not sent upstream as a page option.

## HTTP contract

The CLI repository is the source of truth for service behavior. These are seven services, using two API hosts:

| Service | Request |
| --- | --- |
| Account | `GET https://api.app.mrscraper.com/api/v1/subscription-accounts` |
| HTML | `GET https://api.mrscraper.com?url=…&html=true&markdown=false&screenshot=false` |
| Markdown | `GET https://api.mrscraper.com?url=…&html=false&markdown=true&screenshot=false` |
| Screenshot | `GET https://api.mrscraper.com?url=…&browserRendering=true&screenshot=full&html=true&markdown=false` |
| Brand | `GET https://api.mrscraper.com?action=brand-scraping&url=…&bundle=none` |
| JSON | `GET https://api.mrscraper.com?url=…&agent=general&prompt=…&html=false&screenshot=false` |
| Web search | `GET https://api.mrscraper.com?action=websearch&query=…&country=us&numResults=10` |

JSON uses GET until the encoded URL exceeds 8,000 characters. It then uses POST with `{ "url", "prompt", "agent": "general" }` in the JSON body and page controls in the query. Append `Json Schema:` and a JSON schema to the prompt to shape the extraction.

Authentication uses headers. Credentials are never placed in the query string. Page requests allow 30 seconds beyond the page timeout for HTTP transport; brand and search default to 120 seconds. Brand returns JSON synchronously with `bundle=none`.

## Migration

This release replaces the combined `scraper_api` service with `scrape_html`, `scrape_markdown`, and `get_screenshot`, and adds public `scrape_brand` and `scrape_json`. For combined outputs use `scrape_markdown(..., html=True)` or `get_screenshot(..., html=True, markdown=True)`. The old `full_page` option becomes `screenshot="full"` or `"top"`. LangChain tool names follow `mrscraper_<service>`.

Page defaults now match the CLI: 300-second timeout, US geolocation and proxy country, rendering off unless required by a chosen service, and no explicit retry limit. Search uses `query`, `country`, and a result count; old URL/locale/raw/format options are removed. Legacy scraper job, sitemap, rerun, result, and bundle-download methods are outside this seven-service API.

## Manual testing

These commands make live calls and consume quota. Each service can be tested separately.

```bash
# Before the Python SDK is published, install both local checkouts together:
python -m pip install -e ../sdk-python -e '.[test]'
export MRSCRAPER_API_TOKEN="YOUR_TOKEN"
python manual_check_tools.py            # all seven services
python manual_test.py account
python manual_test.py scrape_html
python manual_test.py scrape_markdown --args '{"html":true}'
python manual_test.py get_screenshot --args '{"screenshot":"top"}'
python manual_test.py scrape_brand --url https://mrscraper.com
python manual_test.py scrape_json --args '{"prompt":"Extract titles and prices"}'
python manual_test.py web_search --query "web scraping" --args '{"country":"id","num_results":20}'
python manual_check_tools.py --async --only mrscraper_web_search
```

Responses and screenshots are saved under `debug_results/`; failures exit nonzero. Add `--async` before the service in `manual_test.py` to use `ainvoke`.

## Development

```bash
python -m pytest -m "not integration" -q
# Opt-in live suite:
MRSCRAPER_RUN_LIVE=1 python -m pytest -m integration -q
```

Version 0.6.0 requires the Python SDK's seven-service release, 0.10.0.

## License

MIT © MrScraper
