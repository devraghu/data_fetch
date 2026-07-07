from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def yesterday_ist() -> date:
    now_ist = datetime.now(IST)
    return (now_ist - timedelta(days=1)).date()


def previous_business_day_ist(start: date | None = None) -> date:
    current = start or yesterday_ist()
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def format_report_date(value: date) -> str:
    return value.strftime("%d-%b-%Y")


def slugify(value: str) -> str:
    cleaned = "".join(char if char.isalnum() else "_" for char in value.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_").lower() or "value"


def first_json_like(text: str) -> str | None:
    start = min((idx for idx in (text.find("{"), text.find("[")) if idx != -1), default=-1)
    if start == -1:
        return None
    for end in range(len(text), start, -1):
        snippet = text[start:end]
        try:
            json.loads(snippet)
            return snippet
        except Exception:
            continue
    return None
