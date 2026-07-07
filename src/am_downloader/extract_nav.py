from __future__ import annotations

import csv
from io import StringIO


def parse_navall_text(text: str) -> list[dict[str, str | None]]:
    records: list[dict[str, str | None]] = []
    current_section: str | None = None
    current_amc: str | None = None
    reader = csv.reader(StringIO(text), delimiter=";")
    for raw_row in reader:
        row = [item.strip() for item in raw_row]
        if not any(row):
            continue
        if len(row) == 1:
            line = row[0]
            lower = line.lower()
            if lower.startswith("scheme code"):
                continue
            if "schemes(" in lower or "schemes (" in lower or line.endswith(")"):
                current_section = line
                current_amc = None
            else:
                current_amc = line
            continue
        if len(row) < 6:
            continue
        scheme_code = row[0]
        if not scheme_code.isdigit():
            continue
        records.append(
            {
                "scheme_code": scheme_code,
                "isin_growth_or_payout": row[1] or None,
                "isin_reinvestment": row[2] or None,
                "scheme_name": row[3] or None,
                "nav": row[4] or None,
                "date": row[5] or None,
                "section": current_section,
                "amc_name": current_amc,
            }
        )
    return records
