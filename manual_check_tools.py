"""Manual smoke check: call every MrScraper LangChain tool against the real API.

This spends API quota. It is not collected by pytest.

Usage:
    python manual_check_tools.py                       # run all tools
    python manual_check_tools.py --only mrscraper_account mrscraper_scraper_html
    python manual_check_tools.py --skip mrscraper_scrape_brand mrscraper_get_brand
    python manual_check_tools.py --async               # use ainvoke instead of invoke
    python manual_check_tools.py --brand-job-id JOB_ID --brand-output screenshot

The token is read from --token, MRSCRAPER_API_KEY / MRSCRAPER_API_TOKEN, or the
repo's .env file. Full responses are written to debug_results/ (git-ignored);
base64 binary payloads (screenshots, brand bundles) are also decoded to files.
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

from langchain_mrscraper import MrScraperToolkit  # noqa: E402

MIN_SDK = (0, 7, 0)

# One representative input per tool, in run order. Account goes first because it
# is cheap and confirms the token before quota is spent on scraping.
CASES: list[tuple[str, dict[str, Any]]] = [
    ("mrscraper_account", {}),
    ("mrscraper_scraper_html", {"url": "https://books.toscrape.com/"}),
    ("mrscraper_scraper_markdown", {"url": "https://books.toscrape.com/"}),
    (
        "mrscraper_get_screenshot",
        {"url": "https://books.toscrape.com/", "full_page": False},
    ),
    (
        "mrscraper_scraper_json",
        {
            "url": "https://books.toscrape.com/",
            "prompt": "Extract the first 5 book titles and prices.",
        },
    ),
    (
        "mrscraper_scraper_multiple_page",
        {
            "url": "https://books.toscrape.com/",
            "prompt": "Extract every book title and price.",
            "max_pages": 2,
        },
    ),
    (
        "mrscraper_scraper_sitemap",
        {
            "url": "https://books.toscrape.com/",
            "max_depth": 1,
            "max_pages": 2,
            "limit": 50,
        },
    ),
    (
        "mrscraper_web_search",
        {
            "url": "langchain web scraping",
            "raw": False,
            "format": "json",
            "region": "us",
            "language": "en",
            "page": 1,
        },
    ),
    ("mrscraper_scrape_brand", {"url": "https://www.brooksrunning.com", "bundle": "clean"}),
    # get_brand input is filled in from the scrape_brand result (or --brand-job-id).
    ("mrscraper_get_brand", {}),
]

BINARY_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/zip": ".zip",
}


def load_token(cli_token: Optional[str]) -> str:
    token = (
        cli_token
        or os.getenv("MRSCRAPER_API_KEY")
        or os.getenv("MRSCRAPER_API_TOKEN")
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
            "No token found. Pass --token, set MRSCRAPER_API_KEY, or add "
            "MRSCRAPER_API_TOKEN=... to .env"
        )
    return token


def check_sdk_version() -> None:
    try:
        installed = version("mrscraper-sdk")
    except PackageNotFoundError:
        sys.exit("mrscraper-sdk is not installed. Run: pip install -e .")
    parts = tuple(int(p) for p in installed.split(".")[:3] if p.isdigit())
    if parts < MIN_SDK:
        sys.exit(
            f"mrscraper-sdk {installed} is installed but >= 0.7.0 is required "
            "(the tools call scraper_html, web_search, scrape_brand, ...).\n"
            "Run: pip install -U 'mrscraper-sdk>=0.7.0'"
        )
    print(f"mrscraper-sdk {installed}")


def find_job_id(data: Any) -> Optional[str]:
    """Look for a brand job ID; the response field name is not fixed by the SDK."""
    if isinstance(data, dict):
        for key in ("job_id", "jobId", "id"):
            value = data.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value)
        for value in data.values():
            found = find_job_id(value)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_job_id(item)
            if found:
                return found
    return None


def preview(data: Any, limit: int = 300) -> str:
    if isinstance(data, dict) and data.get("encoding") == "base64":
        return f"<binary {data.get('size_bytes')} bytes, base64>"
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + " ..."


def save(out_dir: Path, name: str, raw: str, result: dict[str, Any]) -> list[Path]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = [out_dir / f"manual_{name}_{stamp}.json"]
    paths[0].write_text(raw)
    data = result.get("data")
    if isinstance(data, dict) and data.get("encoding") == "base64":
        headers = {k.lower(): v for k, v in (result.get("headers") or {}).items()}
        content_type = str(headers.get("content-type", "")).split(";")[0].strip()
        ext = BINARY_EXT.get(content_type, ".bin")
        binary_path = out_dir / f"manual_{name}_{stamp}{ext}"
        binary_path.write_bytes(base64.b64decode(data["base64"]))
        paths.append(binary_path)
    return paths


async def call_tool(tool: Any, payload: dict[str, Any], use_async: bool) -> str:
    if use_async:
        return await tool.ainvoke(payload)
    # invoke() runs its own event loop in a worker thread when one is already running.
    return tool.invoke(payload)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--token", help="MrScraper API token (overrides env/.env).")
    parser.add_argument("--only", nargs="+", metavar="TOOL", help="Run only these tools.")
    parser.add_argument("--skip", nargs="+", metavar="TOOL", default=[], help="Skip these tools.")
    parser.add_argument("--async", dest="use_async", action="store_true", help="Use ainvoke.")
    parser.add_argument("--brand-job-id", help="Existing brand job ID for get_brand.")
    parser.add_argument(
        "--brand-output",
        choices=["html", "bundle", "screenshot", "screenshot_full"],
        help="Download this get_brand output instead of reading job metadata.",
    )
    parser.add_argument(
        "--out", type=Path, default=ROOT / "debug_results", help="Output directory."
    )
    args = parser.parse_args()

    check_sdk_version()
    tools = {t.name: t for t in MrScraperToolkit(token=load_token(args.token)).get_tools()}

    known = {name for name, _ in CASES}
    unknown = (set(args.only or []) | set(args.skip)) - known
    if unknown:
        sys.exit(f"Unknown tool name(s): {', '.join(sorted(unknown))}\nKnown: {', '.join(sorted(known))}")

    args.out.mkdir(parents=True, exist_ok=True)
    brand_job_id = args.brand_job_id
    summary: list[tuple[str, str, str, float]] = []

    for name, payload in CASES:
        if (args.only and name not in args.only) or name in args.skip:
            continue
        payload = dict(payload)
        if name == "mrscraper_get_brand":
            if not brand_job_id:
                print(f"\n=== {name}\nSKIPPED: no job ID (run scrape_brand or pass --brand-job-id)")
                summary.append((name, "SKIP", "no job id", 0.0))
                continue
            payload["job_id"] = brand_job_id
            if args.brand_output:
                payload["output"] = args.brand_output

        print(f"\n=== {name}\ninput: {json.dumps(payload)}")
        started = time.perf_counter()
        try:
            raw = await call_tool(tools[name], payload, args.use_async)
            elapsed = time.perf_counter() - started
            result = json.loads(raw)
        except Exception as exc:  # report and keep going so one failure doesn't hide the rest
            elapsed = time.perf_counter() - started
            print(f"ERROR after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
            summary.append((name, "FAIL", f"{type(exc).__name__}: {exc}"[:80], elapsed))
            continue

        status = result.get("status_code")
        ok = isinstance(status, int) and 200 <= status < 300
        print(f"status_code: {status}  ({elapsed:.1f}s)")
        print(f"data: {preview(result.get('data'))}")
        for path in save(args.out, name, raw, result):
            print(f"saved: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")

        if name == "mrscraper_scrape_brand" and not brand_job_id:
            brand_job_id = find_job_id(result.get("data"))
            print(f"brand job id: {brand_job_id or 'NOT FOUND - check saved JSON'}")

        summary.append((name, "PASS" if ok else "FAIL", f"HTTP {status}", elapsed))

    print("\n" + "=" * 72)
    for name, outcome, detail, elapsed in summary:
        print(f"{outcome:<5} {name:<34} {elapsed:>6.1f}s  {detail}")
    counts = {o: sum(1 for _, outcome, _, _ in summary if outcome == o) for o in ("PASS", "FAIL", "SKIP")}
    failed = counts["FAIL"]
    print(f"\n{counts['PASS']} passed, {failed} failed, {counts['SKIP']} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
