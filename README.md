# langchain-mrscraper

LangChain integration package for the [MrScraper SDK](https://pypi.org/project/mrscraper-sdk/).

This package exposes MrScraper capabilities as LangChain tools so agents can:

- Fetch rendered HTML from protected websites
- Scrape Google SERP (search results) synchronously
- Create AI scrapers from natural-language prompts
- Rerun AI/manual scrapers (single and bulk)
- List and fetch scraping results

## Installation

```bash
pip install -U langchain-mrscraper
```

or:

```bash
uv add langchain-mrscraper
```

`mrscraper-sdk` is installed automatically as a dependency, so users do not need to install it separately.

## Quick start

```python
import os
from langchain_mrscraper import MrScraperToolkit

os.environ["MRSCRAPER_API_KEY"] = "your-token"

tools = MrScraperToolkit().get_tools()
```

## Use with an agent

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_mrscraper import MrScraperToolkit

tools = MrScraperToolkit(token="your-token").get_tools()
agent = create_react_agent(ChatOpenAI(model="gpt-4o-mini"), tools)
```

## Available tools

- `mrscraper_google_serp`
- `mrscraper_fetch_html`
- `mrscraper_create_scraper`
- `mrscraper_rerun_ai_scraper`
- `mrscraper_bulk_rerun_ai_scraper`
- `mrscraper_rerun_manual_scraper`
- `mrscraper_bulk_rerun_manual_scraper`
- `mrscraper_get_all_results`
- `mrscraper_get_result_by_id`

## API styles

You can initialize via:

- `MrScraperToolkit(...).get_tools()` (recommended)
- `load_mrscraper_tools(...)` convenience function
- per-tool constructors with `token="..."` or `mrscraper_api_key="..."`
- environment variables `MRSCRAPER_API_KEY` (preferred) or `MRSCRAPER_API_TOKEN`

## Tools vs. loaders

This integration is intentionally tools-first. MrScraper endpoints are action-oriented
(fetch, create, rerun, list, retrieve) and best represented as `BaseTool` methods that
agents can call explicitly.

A document loader abstraction is usually better when the primary job is deterministic
"URL -> documents" ingestion into vector stores. MrScraper can support that in a
separate package later, but this package should remain focused on agent tools.

## Testing

```bash
pytest tests/unit_tests -v
```

Integration smoke tests (real API):

```bash
MRSCRAPER_API_KEY=your-token pytest tests/integration_tests -m integration -v
```

## Local release workflow

1. Update `version` in `pyproject.toml`
2. Build: `python -m build`
3. Upload to TestPyPI: `twine upload --repository testpypi dist/*`
4. Verify install from TestPyPI
5. Upload to PyPI: `twine upload dist/*`

## Docs files for LangChain PR

- Provider page: `docs/providers/mrscraper.mdx`
- Tool pages: `docs/tools/*.mdx` (one page per tool)

These are prepared to submit to `langchain-ai/docs`.
