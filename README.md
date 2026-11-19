# MrScraper LangChain Tools

![MrScraper](./mrscraper.jpeg)

LangChain tools backed by the seven-service MrScraper Python SDK.

## Overview

Seven services share the same descriptions, parameter meanings, and defaults across the CLI, SDKs, and integrations. Names, types, authentication, and code examples follow each surface's conventions. See the [API Reference](https://docs.mrscraper.com/docs/api/overview).

| Service                             | Public name                 | Description                                                                                                                     |
| ----------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| [Status](#status)                   | `mrscraper_status`          | Return the raw account status API response without summarizing, redacting body fields, or adding calculated fields.             |
| [Scrape HTML](#scrape-html)         | `mrscraper_scrape_html`     | Retrieve the raw HTML of a page. Browser rendering is optional.                                                                 |
| [Scrape Markdown](#scrape-markdown) | `mrscraper_scrape_markdown` | Retrieve a page as Markdown. Including HTML also enables browser rendering and returns both outputs as JSON.                    |
| [Get screenshot](#get-screenshot)   | `mrscraper_get_screenshot`  | Capture a base64 screenshot of the full page or top viewport. Browser rendering is always enabled.                              |
| [Scrape brand](#scrape-brand)       | `mrscraper_scrape_brand`    | Extract a website's colors, typography, logos, and social links as JSON.                                                        |
| [Scrape JSON](#scrape-json)         | `mrscraper_scrape_json`     | Extract structured JSON from a page using a natural-language prompt. Append Json Schema: and a JSON schema to shape the output. |
| [Web search](#web-search)           | `mrscraper_web_search`      | Search the web and return ranked results with titles, URLs, descriptions, and sources.                                          |

## Installation

Requires Python 3.9 or newer, LangChain Core, and `mrscraper-sdk>=0.10.0,<0.11.0` with the seven-service interface documented here.

```bash
python -m pip install --upgrade langchain-mrscraper
```

Before the matching releases are published, install both local checkouts together:

```bash
python -m pip install -e ../sdk-python -e '.[test]'
```

## Authentication

Obtain an API key from [the MrScraper app](https://app.mrscraper.com/api-tokens). API key used to authenticate the request.

```bash
export MRSCRAPER_API_TOKEN="YOUR_TOKEN"
```

Pass `token=`, `mrscraper_api_key=`, or an existing `client=MrScraper(...)` when constructing a tool or toolkit. Otherwise, credentials come from `MRSCRAPER_API_KEY`, then `MRSCRAPER_API_TOKEN`. Authentication is configured outside tool inputs.

## Quickstart

```python
import json
from langchain_mrscraper import MrScraperScrapeHTML

result = json.loads(MrScraperScrapeHTML().invoke({'url': 'https://example.com', 'browser_rendering': True, 'warm_start': True, 'wait_for_selector': 'body', 'timeout': 120, 'max_retries': 0}))
print(result["data"])
```

Examples use `example.com` as the sample target. Replace it for your use case. Live scraping and search calls consume account quota.

Response examples show selected keys and types observed in live API responses. Values are placeholders; page content, base64 images, and arrays are abbreviated. Actual responses may contain additional fields.

## Shared parameters

### Page controls

HTML, Markdown, screenshots, and JSON extraction share `url`, `timeout`, `geoCode`, `proxyCountry`, `super`, `waitUntil`, `proxy`, `maxRetries`, and `saveResult` (using the naming style shown below). Page defaults are 300 seconds, US geolocation/proxy country, real-device routing off, and dashboard saving off. Omitted retry limits mean no limit. Exact types, defaults, and standard descriptions appear in each service table.

### Loading controls

HTML, Markdown, and screenshots additionally accept `blockResources`, `waitForSelector`, and `returnCookie`. JSON extraction does not accept these controls. Browser rendering is optional for HTML, Markdown, and JSON; screenshots always enable it. Markdown with HTML also enables browser rendering.

## Service reference

### Status

#### Description

Return the raw account status API response without summarizing, redacting body fields, or adding calculated fields.

#### Parameters

This service takes no service parameters. Authentication is configured separately.

The HTTP deadline is fixed at 600 seconds. It is not a service parameter.

#### Example

```python
import json
from langchain_mrscraper import MrScraperStatus

result = json.loads(MrScraperStatus().invoke({}))
print(result["data"])
```

#### Response

The API body contains message and data. Account details remain nested in data, including subscriptionItem and scraperAllowance. The response envelope therefore exposes account details at data.data. Sensitive response headers are removed.

Decoded response after `json.loads(tool.invoke(...))`:

**Success response**

```json
{
  "status_code": 200,
  "data": {
    "message": "Example response",
    "data": {
      "id": "ACCOUNT_ID",
      "tokenLimit": 100000,
      "tokenUsage": 2500,
      "stripeStatus": "active",
      "user": {
        "name": "Example user",
        "email": "user@example.com",
        "isVerified": true
      },
      "subscriptionItem": {
        "name": "Example plan",
        "tokenLimit": 100000
      },
      "scraperAllowance": {
        "remaining": 97500,
        "plans": [
          {
            "remaining": 97500
          }
        ]
      }
    }
  },
  "headers": {
    "content-type": "application/json; charset=utf-8"
  }
}
```

### Scrape HTML

#### Description

Retrieve the raw HTML of a page. Browser rendering is optional.

#### Parameters

| Parameter           | HTTP field         | Type                                                            | Default              | Description                                                                                     |
| ------------------- | ------------------ | --------------------------------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------- |
| `url`               | `url`              | str                                                             | Required             | Absolute HTTP or HTTPS URL of the page to process.                                              |
| `timeout`           | `timeout`          | int                                                             | `300`                | Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 additional seconds.     |
| `geo_code`          | `geoCode`          | str                                                             | `"us"`               | Two-letter country code to load the page from, sent in lowercase.                               |
| `proxy_country`     | `proxyCountry`     | str                                                             | `"us"`               | Two-letter country code of the proxy server, sent in lowercase.                                 |
| `super`             | `super`            | bool                                                            | `False`              | Whether to route the request through real devices.                                              |
| `wait_until`        | `waitUntil`        | str: `domcontentloaded`, `load`, `networkidle0`, `networkidle2` | `"domcontentloaded"` | Navigation completion event to wait for: domcontentloaded, load, networkidle0, or networkidle2. |
| `proxy`             | `proxy`            | str                                                             | `None` (omitted)     | Custom proxy URL used to load the page.                                                         |
| `max_retries`       | `maxRetries`       | int                                                             | `None` (omitted)     | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit.          |
| `save_result`       | `saveResult`       | bool                                                            | `False`              | Whether to save the result to the dashboard Result tab.                                         |
| `block_resources`   | `blockResources`   | bool                                                            | `False`              | Whether to block images, fonts, and stylesheets while loading the page.                         |
| `wait_for_selector` | `waitForSelector`  | str                                                             | `None` (omitted)     | Wait for the page to contain the specified CSS selector before returning the result.            |
| `return_cookie`     | `returnCookie`     | bool                                                            | `False`              | Whether to include browser session cookies in the response.                                     |
| `browser_rendering` | `browserRendering` | bool                                                            | `False`              | Whether to render the page in a browser before returning the result.                            |
| `warm_start`        | `warmStart`        | bool                                                            | `False`              | Whether to enable warm start for more reliable scraping, at the cost of additional latency.     |

#### Example

```python
import json
from langchain_mrscraper import MrScraperScrapeHTML

result = json.loads(MrScraperScrapeHTML().invoke({'url': 'https://example.com', 'browser_rendering': True, 'warm_start': True, 'wait_for_selector': 'body', 'timeout': 120, 'max_retries': 0}))
print(result["data"])
```

#### Response

The default response body is HTML text. Additional controls can cause the API to return JSON; the returned structure is preserved.

Decoded response after `json.loads(tool.invoke(...))`:

**Success response**

```json
{
  "status_code": 200,
  "data": "<html><body>Example page content...</body></html>",
  "headers": {
    "content-type": "text/html; charset=utf-8"
  }
}
```

### Scrape Markdown

#### Description

Retrieve a page as Markdown. Including HTML also enables browser rendering and returns both outputs as JSON.

#### Parameters

| Parameter           | HTTP field         | Type                                                            | Default              | Description                                                                                     |
| ------------------- | ------------------ | --------------------------------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------- |
| `url`               | `url`              | str                                                             | Required             | Absolute HTTP or HTTPS URL of the page to process.                                              |
| `timeout`           | `timeout`          | int                                                             | `300`                | Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 additional seconds.     |
| `geo_code`          | `geoCode`          | str                                                             | `"us"`               | Two-letter country code to load the page from, sent in lowercase.                               |
| `proxy_country`     | `proxyCountry`     | str                                                             | `"us"`               | Two-letter country code of the proxy server, sent in lowercase.                                 |
| `super`             | `super`            | bool                                                            | `False`              | Whether to route the request through real devices.                                              |
| `wait_until`        | `waitUntil`        | str: `domcontentloaded`, `load`, `networkidle0`, `networkidle2` | `"domcontentloaded"` | Navigation completion event to wait for: domcontentloaded, load, networkidle0, or networkidle2. |
| `proxy`             | `proxy`            | str                                                             | `None` (omitted)     | Custom proxy URL used to load the page.                                                         |
| `max_retries`       | `maxRetries`       | int                                                             | `None` (omitted)     | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit.          |
| `save_result`       | `saveResult`       | bool                                                            | `False`              | Whether to save the result to the dashboard Result tab.                                         |
| `block_resources`   | `blockResources`   | bool                                                            | `False`              | Whether to block images, fonts, and stylesheets while loading the page.                         |
| `wait_for_selector` | `waitForSelector`  | str                                                             | `None` (omitted)     | Wait for the page to contain the specified CSS selector before returning the result.            |
| `return_cookie`     | `returnCookie`     | bool                                                            | `False`              | Whether to include browser session cookies in the response.                                     |
| `browser_rendering` | `browserRendering` | bool                                                            | `False`              | Whether to render the page in a browser before returning the result.                            |
| `warm_start`        | `warmStart`        | bool                                                            | `False`              | Whether to enable warm start for more reliable scraping, at the cost of additional latency.     |
| `html`              | `html`             | bool                                                            | `False`              | Whether to include the page HTML in the response.                                               |

#### Example

```python
import json
from langchain_mrscraper import MrScraperScrapeMarkdown

result = json.loads(MrScraperScrapeMarkdown().invoke({'url': 'https://example.com', 'html': True, 'warm_start': True}))
print(result["data"])
```

#### Response

The default response body is Markdown text. Enabling HTML returns JSON containing both HTML and Markdown.

Decoded response after `json.loads(tool.invoke(...))`:

**With html enabled**

```json
{
  "status_code": 200,
  "data": {
    "html": "<html>...</html>",
    "markdown": "# Example page\n\n..."
  },
  "headers": {
    "content-type": "application/json"
  }
}
```

**Default Markdown text**

```json
{
  "status_code": 200,
  "data": "# Example page\n\nExample Markdown content...",
  "headers": {
    "content-type": "text/markdown; charset=utf-8"
  }
}
```

### Get screenshot

#### Description

Capture a base64 screenshot of the full page or top viewport. Browser rendering is always enabled.

#### Parameters

| Parameter           | HTTP field        | Type                                                            | Default              | Description                                                                                     |
| ------------------- | ----------------- | --------------------------------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------- |
| `url`               | `url`             | str                                                             | Required             | Absolute HTTP or HTTPS URL of the page to process.                                              |
| `timeout`           | `timeout`         | int                                                             | `300`                | Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 additional seconds.     |
| `geo_code`          | `geoCode`         | str                                                             | `"us"`               | Two-letter country code to load the page from, sent in lowercase.                               |
| `proxy_country`     | `proxyCountry`    | str                                                             | `"us"`               | Two-letter country code of the proxy server, sent in lowercase.                                 |
| `super`             | `super`           | bool                                                            | `False`              | Whether to route the request through real devices.                                              |
| `wait_until`        | `waitUntil`       | str: `domcontentloaded`, `load`, `networkidle0`, `networkidle2` | `"domcontentloaded"` | Navigation completion event to wait for: domcontentloaded, load, networkidle0, or networkidle2. |
| `proxy`             | `proxy`           | str                                                             | `None` (omitted)     | Custom proxy URL used to load the page.                                                         |
| `max_retries`       | `maxRetries`      | int                                                             | `None` (omitted)     | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit.          |
| `save_result`       | `saveResult`      | bool                                                            | `False`              | Whether to save the result to the dashboard Result tab.                                         |
| `block_resources`   | `blockResources`  | bool                                                            | `False`              | Whether to block images, fonts, and stylesheets while loading the page.                         |
| `wait_for_selector` | `waitForSelector` | str                                                             | `None` (omitted)     | Wait for the page to contain the specified CSS selector before returning the result.            |
| `return_cookie`     | `returnCookie`    | bool                                                            | `False`              | Whether to include browser session cookies in the response.                                     |
| `screenshot`        | `screenshot`      | str: `full`, `top`                                              | `"full"`             | Screenshot area to capture: full for the entire page or top for the top viewport.               |
| `html`              | `html`            | bool                                                            | `True`               | Whether to include the page HTML in the response.                                               |
| `markdown`          | `markdown`        | bool                                                            | `False`              | Whether to include the page Markdown in the response.                                           |

#### Example

```python
import json
from langchain_mrscraper import MrScraperGetScreenshot

result = json.loads(MrScraperGetScreenshot().invoke({'url': 'https://example.com', 'screenshot': 'top', 'html': False, 'markdown': True}))
print(result["data"])
```

#### Response

The response body contains a base64 screenshot and requested page outputs. The API can still include HTML when HTML output is disabled.

Decoded response after `json.loads(tool.invoke(...))`:

**Success response**

```json
{
  "status_code": 200,
  "data": {
    "html": "<html>...</html>",
    "screenshot": "BASE64_PNG_DATA",
    "markdown": "# Example page\n\n..."
  },
  "headers": {
    "content-type": "application/json; charset=utf-8"
  }
}
```

### Scrape brand

#### Description

Extract a website's colors, typography, logos, and social links as JSON.

#### Parameters

| Parameter | HTTP field | Type | Default  | Description                                        |
| --------- | ---------- | ---- | -------- | -------------------------------------------------- |
| `url`     | `url`      | str  | Required | Absolute HTTP or HTTPS URL of the page to process. |

The HTTP deadline is fixed at 120 seconds. It is not a service parameter.

The request uses `action=brand-scraping` and `bundle=none`; page controls are not accepted.

#### Example

```python
import json
from langchain_mrscraper import MrScraperScrapeBrand

result = json.loads(MrScraperScrapeBrand().invoke({'url': 'https://example.com'}))
print(result["data"])
```

#### Response

The API body contains message and a data object with job_id, status, url, final_url, brand, and error. Brand details are available at data.data.brand in the response envelope.

Decoded response after `json.loads(tool.invoke(...))`:

**Success response**

```json
{
  "status_code": 200,
  "data": {
    "data": {
      "job_id": "JOB_ID",
      "status": "succeeded",
      "url": "https://example.com",
      "final_url": "https://example.com",
      "brand": {
        "name": "Example brand",
        "colors": {
          "background": "#ffffff",
          "text": "#222222"
        },
        "typography": {
          "body": {
            "font_family": "Example font"
          }
        }
      },
      "error": null,
      "bundle_url": null
    },
    "message": "Example response"
  },
  "headers": {
    "content-type": "application/json"
  }
}
```

### Scrape JSON

#### Description

Extract structured JSON from a page using a natural-language prompt. Append Json Schema: and a JSON schema to shape the output.

#### Parameters

| Parameter           | HTTP field         | Type                                                            | Default                                       | Description                                                                                             |
| ------------------- | ------------------ | --------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `url`               | `url`              | str                                                             | Required                                      | Absolute HTTP or HTTPS URL of the page to process.                                                      |
| `timeout`           | `timeout`          | int                                                             | `300`                                         | Page load timeout in seconds, from 1 to 300. The HTTP request allows 30 additional seconds.             |
| `geo_code`          | `geoCode`          | str                                                             | `"us"`                                        | Two-letter country code to load the page from, sent in lowercase.                                       |
| `proxy_country`     | `proxyCountry`     | str                                                             | `"us"`                                        | Two-letter country code of the proxy server, sent in lowercase.                                         |
| `super`             | `super`            | bool                                                            | `False`                                       | Whether to route the request through real devices.                                                      |
| `wait_until`        | `waitUntil`        | str: `domcontentloaded`, `load`, `networkidle0`, `networkidle2` | `"domcontentloaded"`                          | Navigation completion event to wait for: domcontentloaded, load, networkidle0, or networkidle2.         |
| `proxy`             | `proxy`            | str                                                             | `None` (omitted)                              | Custom proxy URL used to load the page.                                                                 |
| `max_retries`       | `maxRetries`       | int                                                             | `None` (omitted)                              | Maximum number of retries, as a nonnegative integer. Omit this parameter for no limit.                  |
| `save_result`       | `saveResult`       | bool                                                            | `False`                                       | Whether to save the result to the dashboard Result tab.                                                 |
| `prompt`            | `prompt`           | str                                                             | `"Extract all data as complete as possible."` | Instructions describing the data to extract. Append Json Schema: and a JSON schema to shape the output. |
| `browser_rendering` | `browserRendering` | bool                                                            | `False`                                       | Whether to render the page in a browser before returning the result.                                    |
| `html`              | `html`             | bool                                                            | `False`                                       | Whether to include the page HTML in the response.                                                       |
| `screenshot`        | `screenshot`       | bool                                                            | `False`                                       | Whether to include a base64 screenshot in the response.                                                 |

The request uses `agent=general` and GET. If the encoded URL exceeds 8,000 characters, it switches to POST with `url`, `prompt`, and `agent` in the body; page controls remain in the query.

#### Example

```python
import json
from langchain_mrscraper import MrScraperScrapeJSON

result = json.loads(MrScraperScrapeJSON().invoke({'url': 'https://example.com', 'prompt': 'Extract the first 2 items with title and price. Json Schema: {"type":"array","items":{"type":"object","properties":{"title":{"type":"string"},"price":{"type":"string"}},"required":["title","price"]}}', 'browser_rendering': True}))
print(result["data"])
```

#### Response

Extraction results are in the API body's data field and follow the requested schema. Response metadata includes thread_id, token_usage, status, error, runtime, and cookies. html, markdown, and screenshot can be empty strings when not requested.

Decoded response after `json.loads(tool.invoke(...))`:

**Success response**

```json
{
  "status_code": 200,
  "data": {
    "success": true,
    "data": [
      {
        "title": "Example item",
        "price": "10.00"
      }
    ],
    "thread_id": "THREAD_ID",
    "token_usage": 1,
    "html": "",
    "markdown": "",
    "screenshot": "",
    "status": "Results ready",
    "error": "",
    "runtime": 1.23,
    "cookies": []
  },
  "headers": {
    "content-type": "application/json"
  }
}
```

### Web search

#### Description

Search the web and return ranked results with titles, URLs, descriptions, and sources.

#### Parameters

| Parameter     | HTTP field   | Type | Default  | Description                                                                                       |
| ------------- | ------------ | ---- | -------- | ------------------------------------------------------------------------------------------------- |
| `query`       | `query`      | str  | Required | Search query text, trimmed before sending, containing 1 to 1000 characters.                       |
| `country`     | `country`    | str  | `"us"`   | Two-letter country code to search from, sent in lowercase.                                        |
| `num_results` | `numResults` | int  | `10`     | Number of search results to request, as an integer from 10 to 100. Fewer results may be returned. |

The HTTP deadline is fixed at 120 seconds. It is not a service parameter.

#### Example

```python
import json
from langchain_mrscraper import MrScraperWebSearch

result = json.loads(MrScraperWebSearch().invoke({'query': 'site:example.com documentation', 'country': 'id', 'num_results': 20}))
print(result["data"])
```

#### Response

The API body contains success, message, a data array, and tokenUsage. Each result includes rank, title, url, description, and source.

Decoded response after `json.loads(tool.invoke(...))`:

**Success response**

```json
{
  "status_code": 200,
  "data": {
    "success": true,
    "message": "Example response",
    "data": [
      {
        "rank": 1,
        "title": "Example result",
        "url": "https://example.com",
        "description": "Example result description.",
        "source": "example.com"
      }
    ],
    "tokenUsage": 1
  },
  "headers": {
    "content-type": "application/json; charset=utf-8"
  }
}
```

## Response format

Successful services use an envelope containing `status_code`, `data`, and `headers`. The `data` field contains the API response body; its field names are not converted to the SDK's naming style. Status preserves the complete body without adding summary fields.

```json
{
  "status_code": 200,
  "data": "<html><body>Example page content...</body></html>",
  "headers": {
    "content-type": "text/html; charset=utf-8"
  }
}
```

Tools return a JSON string; parse it with `json.loads`. Binary bodies are represented as `{ "encoding": "base64", "base64": "...", "size_bytes": 123 }`. The underlying SDK response envelope is preserved.

## Error handling

Invalid tool inputs raise Pydantic `ValidationError`. Authentication, HTTP, and transport failures propagate as the Python SDK's `AuthenticationError`, `APIError`, and `NetworkError`. `APIError.status_code` contains the HTTP status when available. Unsupported fields are rejected, including extra fields passed to status.

## Integration features

### Configuration

Each tool supports `invoke` and `ainvoke`. Synchronous calls are also supported inside notebooks with a running event loop. `MrScraperToolkit` and `load_mrscraper_tools` share one SDK client across their tools. Use `tool_names` to filter by exact tool names; an empty list returns none.

### Advanced usage

Use async invocation and select only the services your workflow needs:

```python
import asyncio
import json
from langchain_mrscraper import MrScraperToolkit

async def main():
    tools = MrScraperToolkit(tool_names=["mrscraper_scrape_markdown"]).get_tools()
    result = json.loads(await tools[0].ainvoke({"url": "https://example.com"}))
    print(result["data"])

asyncio.run(main())
```

Pass an existing `MrScraper(http_client=http_client)` as `client=` to reuse a connection pool. Manage the HTTP client's lifetime yourself. The public tool classes are `MrScraperStatus`, `MrScraperScrapeHTML`, `MrScraperScrapeMarkdown`, `MrScraperGetScreenshot`, `MrScraperScrapeBrand`, `MrScraperScrapeJSON`, and `MrScraperWebSearch`.

### Troubleshooting

Install the matching Python SDK checkout before testing an unpublished integration release. Tool inputs use snake_case and reject unsupported fields. Parse the JSON string returned by a tool with `json.loads`; raw API nesting remains inside `data`.

## Migration

Replace `MrScraperAccount` / `mrscraper_account` with `MrScraperStatus` / `mrscraper_status`. Remove status/search timeout inputs. Replace combined `scraper_api` calls with the HTML, Markdown, or screenshot tools. Tool inputs use snake_case and match the Python SDK. The matching Python SDK must be available before publishing this integration release.

## Development and testing

### Automated checks

The automated suite checks service behavior without production API calls.

```bash
python -m pip install -e ../sdk-python -e '.[test]'
python -m pytest -m 'not integration' -q
ruff check src tests
mypy src
```

### Manual checks

The following commands call the live API using your credentials and consume quota.

```bash
python manual_test.py status
python manual_test.py scrape_html --url https://example.com
python manual_check_tools.py --async --only mrscraper_web_search
```

## License

MIT. See [LICENSE](./LICENSE).
