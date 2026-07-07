from __future__ import annotations

import json
import re
from io import StringIO
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from .utils import first_json_like, utc_now_iso


def extract_aum_records(html: str, source_url: str) -> dict[str, Any]:
    warnings: list[str] = []
    records: list[dict[str, Any]] = []
    try:
        tables = pd.read_html(StringIO(html))
    except Exception:
        tables = []
    for idx, table in enumerate(tables):
        if table.empty:
            continue
        records.append({
            "table_index": idx,
            "columns": [str(col) for col in table.columns],
            "rows": table.fillna("").to_dict(orient="records"),
        })
    if not records:
        soup = BeautifulSoup(html, "lxml")
        for script in soup.find_all("script"):
            script_text = script.get_text("\n", strip=True)
            if not script_text:
                continue
            candidate = first_json_like(script_text)
            if not candidate:
                continue
            try:
                records.append({"embedded_json": json.loads(candidate)})
                break
            except Exception:
                continue
    if not records:
        warnings.append("No structured AUM data extracted from raw HTML")
    return {
        "source_url": source_url,
        "extracted_at_utc": utc_now_iso(),
        "records": records,
        "warnings": warnings,
    }
