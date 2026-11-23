"""Manually test one MrScraper LangChain tool at a time with a real token.

Each call spends API quota. Not collected by pytest.

    python manual_test.py status
    python manual_test.py scrape_html --url https://example.com --args '{"screenshot":"top","max_age":3600000}'
    python manual_test.py get_screenshot --url https://example.com --args '{"wait_for_selector":"body"}'
    python manual_test.py scrape_brand --url https://example.com --args '{"timeout":120,"warm_start":true,"geo_code":"gb"}'
    python manual_test.py web_search --query "python web scraping" --args '{"country":"us","num_results":10}'

Add --async to call ainvoke instead of invoke. The token comes from --token,
MRSCRAPER_API_KEY / MRSCRAPER_API_TOKEN, or MRSCRAPER_API_TOKEN=... in .env.
The full response is saved to debug_results/ (git-ignored); a screenshot is
also saved next to it using its image format.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from langchain_mrscraper import (
    MrScraperGetScreenshot,
    MrScraperScrapeBrand,
    MrScraperScrapeHTML,
    MrScraperScrapeJSON,
    MrScraperScrapeMarkdown,
    MrScraperStatus,
    MrScraperWebSearch,
)

TOOLS = {
    "status": MrScraperStatus,
    "scrape_html": MrScraperScrapeHTML,
    "scrape_markdown": MrScraperScrapeMarkdown,
    "get_screenshot": MrScraperGetScreenshot,
    "scrape_brand": MrScraperScrapeBrand,
    "scrape_json": MrScraperScrapeJSON,
    "web_search": MrScraperWebSearch,
}


def load_token(cli_token: Optional[str]) -> str:
    token = (
        cli_token or os.getenv("MRSCRAPER_API_KEY") or os.getenv("MRSCRAPER_API_TOKEN")
    )
    env_file = ROOT / ".env"
    if not token and env_file.exists():
        for line in env_file.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() in {"MRSCRAPER_API_KEY", "MRSCRAPER_API_TOKEN"}:
                token = value.strip().strip("'\"")
                break
    if not token:
        sys.exit(
            "No token found. Pass --token, set MRSCRAPER_API_KEY, or add it to .env"
        )
    return token


def check_sdk_version() -> None:
    try:
        installed = version("mrscraper-sdk")
    except PackageNotFoundError:
        sys.exit("mrscraper-sdk is not installed. Run: pip install -e .")
    major_minor = tuple(int(p) for p in installed.split(".")[:2])
    if major_minor != (0, 12):
        sys.exit(
            f"mrscraper-sdk {installed} is installed but >=0.12.0,<0.13.0 is required.\n"
            "Run: pip install -U 'mrscraper-sdk>=0.12.0,<0.13.0'"
        )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    options = json.loads(args.args)
    if not isinstance(options, dict):
        raise TypeError("--args must be a JSON object")
    if args.tool == "status":
        return options
    return {
        ("query" if args.tool == "web_search" else "url"): (
            args.query if args.tool == "web_search" else args.url
        ),
        **options,
    }


def image_extension(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp"
    return ".bin"


def save(tool: str, raw: str, result: dict[str, Any]) -> list[Path]:
    out_dir = ROOT / "debug_results"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = [out_dir / f"manual_{tool}_{stamp}.json"]
    paths[0].write_text(raw)
    data = result.get("data")
    if isinstance(data, dict) and isinstance(data.get("screenshot"), str):
        encoded = data["screenshot"].split(",", 1)[-1]  # tolerate a data: URL prefix
        content = base64.b64decode(encoded)
        paths.append(out_dir / f"manual_{tool}_{stamp}{image_extension(content)}")
        paths[1].write_bytes(content)
    return paths


def print_summary(tool: str, result: dict[str, Any]) -> None:
    data = result.get("data")
    if (
        tool == "web_search"
        and isinstance(data, dict)
        and isinstance(data.get("data"), list)
    ):
        for item in data["data"]:
            print(f"  {item.get('rank')}. {item.get('title')}\n     {item.get('url')}")
        return
    if isinstance(data, dict) and isinstance(data.get("screenshot"), str):
        data = {**data, "screenshot": f"<base64, {len(data['screenshot'])} chars>"}
    text = (
        data
        if isinstance(data, str)
        else json.dumps(data, indent=2, ensure_ascii=False)
    )
    print(
        text if len(text) <= 1500 else text[:1500] + "\n... (truncated, see saved file)"
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--token", help="MrScraper API token (overrides env/.env).")
    parser.add_argument(
        "--async", dest="use_async", action="store_true", help="Use ainvoke."
    )
    parser.add_argument("tool", choices=TOOLS)
    parser.add_argument("--url", default="https://example.com")
    parser.add_argument("--query", default="python web scraping")
    parser.add_argument(
        "--args", default="{}", help="JSON overrides using Python snake_case names"
    )

    args = parser.parse_args()
    check_sdk_version()

    tool = TOOLS[args.tool](token=load_token(args.token))
    payload = build_payload(args)
    print(f"tool:  {tool.name}\ninput: {json.dumps(payload)}\n")

    started = time.perf_counter()
    try:
        raw = await tool.ainvoke(payload) if args.use_async else tool.invoke(payload)
    except Exception as exc:  # noqa: BLE001 - show the error instead of a traceback
        print(
            f"FAIL after {time.perf_counter() - started:.1f}s: {type(exc).__name__}: {exc}"
        )
        return 1
    elapsed = time.perf_counter() - started

    result = json.loads(raw)
    status = result.get("status_code")
    print_summary(args.tool, result)
    print()
    for path in save(args.tool, raw, result):
        print(f"saved: {path.relative_to(ROOT)}")
    ok = isinstance(status, int) and 200 <= status < 300
    print(f"{'PASS' if ok else 'FAIL'}  HTTP {status}  ({elapsed:.1f}s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
