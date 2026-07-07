from __future__ import annotations

from pathlib import Path
from io import StringIO
from typing import Any

import pandas as pd

from .utils import utc_now_iso


def extract_benchmark_records(raw_dir: Path) -> dict[str, Any]:
    warnings: list[str] = []
    records: list[dict[str, Any]] = []
    xlsx_path = raw_dir / "benchmark_tier1.xlsx"
    if xlsx_path.exists():
        try:
            sheets = pd.read_excel(xlsx_path, sheet_name=None)
            for sheet_name, frame in sheets.items():
                records.append(
                    {
                        "source": xlsx_path.name,
                        "sheet": sheet_name,
                        "columns": [str(col) for col in frame.columns],
                        "rows": frame.fillna("").to_dict(orient="records"),
                    }
                )
        except Exception as exc:
            warnings.append(f"Failed to parse benchmark XLSX: {exc}")
    if not records:
        for path in sorted(raw_dir.glob("benchmark_*.html")):
            try:
                tables = pd.read_html(StringIO(path.read_text(encoding="utf-8", errors="replace")))
            except Exception as exc:
                warnings.append(f"Failed to parse {path.name}: {exc}")
                continue
            for idx, table in enumerate(tables):
                if table.empty:
                    continue
                records.append(
                    {
                        "source": path.name,
                        "table_index": idx,
                        "columns": [str(col) for col in table.columns],
                        "rows": table.fillna("").to_dict(orient="records"),
                    }
                )
    if not records:
        warnings.append("No structured benchmark data extracted")
    return {
        "extracted_at_utc": utc_now_iso(),
        "records": records,
        "warnings": warnings,
    }
