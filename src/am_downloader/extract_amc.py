from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .utils import utc_now_iso


def extract_amc_records(html: str, source_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for anchor in soup.find_all("a", href=True):
        name = anchor.get_text(" ", strip=True)
        href = anchor.get("href", "").strip()
        img = anchor.find("img")
        logo = img.get("src", "").strip() if img else ""
        if not name or len(name) < 3:
            continue
        key = (name, href, logo)
        if key in seen:
            continue
        seen.add(key)
        records.append({
            "name": name,
            "url": href or None,
            "logo_url": logo or None,
        })
    warnings = []
    if not records:
        warnings.append("No AMC member data extracted from raw HTML")
    return {
        "source_url": source_url,
        "extracted_at_utc": utc_now_iso(),
        "records": records,
        "warnings": warnings,
    }
