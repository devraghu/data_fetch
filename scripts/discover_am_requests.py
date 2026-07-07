from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


OUT = Path("publish/arthikamf/am/discovery")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    "https://www.amfiindia.com/aum-data/average-aum",
    "https://www.amfiindia.com/otherdata/fund-performance",
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices",
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=debtSchemes",
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=equitySchemes",
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=equitySectoral",
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=equityThematic",
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=hybridSchemes",
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=solutionOriented",
    "https://www.amfiindia.com/aboutamfi?tab=members",
]

INTERESTING_WORDS = [
    "gateway",
    "pollingsebi",
    "api",
    "fundperformance",
    "aum",
    "average-aum",
    "benchmark",
    "listofbenchmarkindices",
    "amc",
    "member",
    "profile",
    "download",
    "xlsx",
    "json",
]


def is_interesting(url: str) -> bool:
    lower = url.lower()
    return "amfiindia.com" in lower and any(word.lower() in lower for word in INTERESTING_WORDS)


def safe_filename(url: str, suffix: str = "") -> str:
    parsed = urlparse(url)
    raw = parsed.netloc + "_" + parsed.path.strip("/").replace("/", "_")
    if parsed.query:
        raw += "_" + parsed.query.replace("&", "_").replace("=", "_")
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")[:180]
    if suffix and not raw.endswith(suffix):
        raw += suffix
    return raw or "response"


async def main() -> None:
    records = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            viewport={"width": 1440, "height": 1200},
        )
        page = await context.new_page()

        async def on_request(request):
            url = request.url
            if not is_interesting(url):
                return
            records.append(
                {
                    "type": "request",
                    "method": request.method,
                    "url": url,
                    "resource_type": request.resource_type,
                    "headers": {
                        k: v
                        for k, v in request.headers.items()
                        if k.lower() in {"accept", "content-type", "origin", "referer", "user-agent", "x-requested-with"}
                    },
                    "post_data": request.post_data,
                }
            )

        async def on_response(response):
            url = response.url
            if not is_interesting(url):
                return
            try:
                body = await response.body()
            except Exception as exc:
                body = b""
                body_error = repr(exc)
            else:
                body_error = None
            content_type = response.headers.get("content-type", "")
            suffix = ".bin"
            if "json" in content_type.lower():
                suffix = ".json"
            elif "html" in content_type.lower():
                suffix = ".html"
            elif "text" in content_type.lower():
                suffix = ".txt"
            elif "excel" in content_type.lower() or "spreadsheet" in content_type.lower():
                suffix = ".xlsx"
            filename = safe_filename(url, suffix)
            path = OUT / "responses" / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            if body:
                path.write_bytes(body)
            records.append(
                {
                    "type": "response",
                    "url": url,
                    "status": response.status,
                    "content_type": content_type,
                    "body_bytes": len(body),
                    "saved_to": str(path) if body else None,
                    "body_error": body_error,
                }
            )

        page.on("request", on_request)
        page.on("response", on_response)

        for url in PAGES:
            try:
                await page.goto(url, wait_until="networkidle", timeout=90_000)
                await page.wait_for_timeout(7000)
                html = await page.content()
                page_file = OUT / "pages" / safe_filename(url, ".html")
                page_file.parent.mkdir(parents=True, exist_ok=True)
                page_file.write_text(html, encoding="utf-8")
            except Exception as exc:
                records.append({"type": "page_error", "url": url, "error": repr(exc)})

        await browser.close()

    manifest = {"fetched_at_utc": fetched_at, "records": records}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
