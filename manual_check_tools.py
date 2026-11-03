"""Manual smoke check: call every MrScraper LangChain tool against the real API.

This spends API quota. It is not collected by pytest.

Usage:
    python manual_check_tools.py                       # run all cases
    python manual_check_tools.py --only mrscraper_account mrscraper_web_search
    python manual_check_tools.py --skip scraper_api_combined
    python manual_check_tools.py --async               # use ainvoke instead of invoke

--only/--skip accept a tool name (all of its cases) or a case label.

The token is read from --token, MRSCRAPER_API_KEY / MRSCRAPER_API_TOKEN, or the
repo's .env file. Full responses are written to debug_results/ (git-ignored);
screenshots (base64 in the response) are also decoded to image files.
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

from langchain_mrscraper import MrScraperToolkit

MIN_SDK = (0, 8, 0)
MAX_SDK = (0, 9, 0)
URL = "https://books.toscrape.com/"

# (case label, tool name, input) in run order. Account goes first because it is
# cheap and confirms the token before quota is spent on scraping.
CASES: list[tuple[str, str, dict[str, Any]]] = [
    ("account", "mrscraper_account", {}),
    ("scraper_api_html", "mrscraper_scraper_api", {"url": URL}),
    (
        "scraper_api_combined",
        "mrscraper_scraper_api",
        {"url": URL, "html": True, "markdown": True, "screenshot": True},
    ),
    (
        "web_search",
        "mrscraper_web_search",
        {"query": "e-menessaptieka.lv linkedin", "country": "us", "num_results": 10},
    ),
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
    if not MIN_SDK <= parts < MAX_SDK:
        sys.exit(
            f"mrscraper-sdk {installed} is installed but >=0.8.0,<0.9.0 is required "
            "(the tools call scraper_api, web_search, and account).\n"
            "Run: pip install -U 'mrscraper-sdk>=0.8.0,<0.9.0'"
        )
    print(f"mrscraper-sdk {installed}")


def preview(data: Any, limit: int = 300) -> str:
    if isinstance(data, dict) and data.get("encoding") == "base64":
        return f"<binary {data.get('size_bytes')} bytes, base64>"
    if isinstance(data, dict) and isinstance(data.get("screenshot"), str):
        size = len(data["screenshot"])
        data = {**data, "screenshot": f"<base64 screenshot, {size} chars>"}
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
    elif isinstance(data, dict) and isinstance(data.get("screenshot"), str):
        encoded = data["screenshot"].split(",", 1)[-1]  # tolerate a data: URL prefix
        image_path = out_dir / f"manual_{name}_{stamp}.png"
        image_path.write_bytes(base64.b64decode(encoded))
        paths.append(image_path)
    return paths


async def call_tool(tool: Any, payload: dict[str, Any], use_async: bool) -> str:
    if use_async:
        return await tool.ainvoke(payload)
    # invoke() runs its own event loop in a worker thread when one is already running.
    return tool.invoke(payload)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--token", help="MrScraper API token (overrides env/.env).")
    parser.add_argument(
        "--only", nargs="+", metavar="CASE", help="Run only these tools or case labels."
    )
    parser.add_argument(
        "--skip", nargs="+", metavar="CASE", default=[], help="Skip these tools or case labels."
    )
    parser.add_argument("--async", dest="use_async", action="store_true", help="Use ainvoke.")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "debug_results", help="Output directory."
    )
    args = parser.parse_args()

    check_sdk_version()
    tools = {t.name: t for t in MrScraperToolkit(token=load_token(args.token)).get_tools()}

    known = {label for label, _, _ in CASES} | {name for _, name, _ in CASES}
    unknown = (set(args.only or []) | set(args.skip)) - known
    if unknown:
        sys.exit(f"Unknown tool or case name(s): {', '.join(sorted(unknown))}\nKnown: {', '.join(sorted(known))}")

    args.out.mkdir(parents=True, exist_ok=True)
    summary: list[tuple[str, str, str, float]] = []

    for label, name, payload in CASES:
        selected = {label, name}
        if (args.only and not selected & set(args.only)) or selected & set(args.skip):
            continue

        print(f"\n=== {label} ({name})\ninput: {json.dumps(payload)}")
        started = time.perf_counter()
        try:
            raw = await call_tool(tools[name], dict(payload), args.use_async)
            elapsed = time.perf_counter() - started
            result = json.loads(raw)
        except Exception as exc:  # noqa: BLE001 - report and keep going so one failure doesn't hide the rest
            elapsed = time.perf_counter() - started
            print(f"ERROR after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
            summary.append((label, "FAIL", f"{type(exc).__name__}: {exc}"[:80], elapsed))
            continue

        status = result.get("status_code")
        ok = isinstance(status, int) and 200 <= status < 300
        print(f"status_code: {status}  ({elapsed:.1f}s)")
        print(f"data: {preview(result.get('data'))}")
        for path in save(args.out, label, raw, result):
            print(f"saved: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")

        summary.append((label, "PASS" if ok else "FAIL", f"HTTP {status}", elapsed))

    print("\n" + "=" * 72)
    for name, outcome, detail, elapsed in summary:
        print(f"{outcome:<5} {name:<34} {elapsed:>6.1f}s  {detail}")
    counts = {o: sum(1 for _, outcome, _, _ in summary if outcome == o) for o in ("PASS", "FAIL", "SKIP")}
    failed = counts["FAIL"]
    print(f"\n{counts['PASS']} passed, {failed} failed, {counts['SKIP']} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
