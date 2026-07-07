from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import json
from typing import Any

from .config import (
    AM_WEB_FUND_PERFORMANCE_FILTERS_URL,
    AM_WEB_FUND_PERFORMANCE_HOLIDAY_URL,
    AM_WEB_FUND_PERFORMANCE_SUBCATEGORY_URL,
    AM_WEB_FUND_PERFORMANCE_URL,
    AM_WEB_PERFORMANCE_REFERER,
    JSON_HEADERS,
    TEXT_POST_HEADERS,
)
from .http_client import AmHttpClient, FetchResult
from .utils import format_report_date, previous_business_day_ist, slugify, yesterday_ist


@dataclass(slots=True)
class PerformancePayload:
    maturity_type: int
    category: int
    sub_category: int
    mfid: int
    report_date: str

    def to_dict(self) -> dict[str, int | str]:
        return {
            "maturityType": self.maturity_type,
            "category": self.category,
            "subCategory": self.sub_category,
            "mfid": self.mfid,
            "reportDate": self.report_date,
        }

    def file_slug(self) -> str:
        return (
            f"maturity_{self.maturity_type}_category_{self.category}_"
            f"subcategory_{self.sub_category}_mfid_{self.mfid}.json"
        )


def build_fund_performance_payload(
    *,
    maturity_type: int,
    category: int,
    sub_category: int,
    mfid: int,
    report_date: str,
) -> dict[str, int | str]:
    return PerformancePayload(
        maturity_type=maturity_type,
        category=category,
        sub_category=sub_category,
        mfid=mfid,
        report_date=report_date,
    ).to_dict()


def fetch_filters(client: AmHttpClient) -> FetchResult:
    headers = dict(TEXT_POST_HEADERS)
    headers["Referer"] = AM_WEB_PERFORMANCE_REFERER
    return client.request("POST", AM_WEB_FUND_PERFORMANCE_FILTERS_URL, headers=headers, data="")


def fetch_is_holiday(client: AmHttpClient, report_date: str) -> FetchResult:
    headers = dict(JSON_HEADERS)
    headers["Referer"] = AM_WEB_PERFORMANCE_REFERER
    return client.request(
        "POST",
        AM_WEB_FUND_PERFORMANCE_HOLIDAY_URL,
        headers=headers,
        json_payload={"reportDate": report_date},
    )


def fetch_subcategories(client: AmHttpClient, category: int) -> FetchResult:
    headers = dict(JSON_HEADERS)
    headers["Referer"] = AM_WEB_PERFORMANCE_REFERER
    return client.request(
        "POST",
        AM_WEB_FUND_PERFORMANCE_SUBCATEGORY_URL,
        headers=headers,
        json_payload={"category": category},
    )


def fetch_fund_performance(client: AmHttpClient, payload: dict[str, Any]) -> FetchResult:
    headers = dict(JSON_HEADERS)
    headers["Referer"] = AM_WEB_PERFORMANCE_REFERER
    return client.request(
        "POST",
        AM_WEB_FUND_PERFORMANCE_URL,
        headers=headers,
        json_payload=payload,
    )


def _parse_json_bytes(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8", errors="replace"))


def _iter_named_ints(payload: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = []
        for value in payload.values():
            if isinstance(value, list):
                items.extend(value)
    else:
        return []
    matches = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = {str(key).lower(): value for key, value in item.items()}
        id_value = None
        label = None
        for key in keys:
            if key in normalized:
                try:
                    id_value = int(normalized[key])
                    break
                except Exception:
                    pass
        for label_key in ("name", "label", "categoryname", "subcategoryname", "text"):
            if label_key in normalized and normalized[label_key] is not None:
                label = str(normalized[label_key])
                break
        if id_value is not None:
            matches.append({"id": id_value, "label": label or str(id_value)})
    return matches


def parse_filter_dimensions(filters_payload: Any) -> tuple[list[int], list[int]]:
    categories = _iter_named_ints(filters_payload, ("category", "categoryid", "id"))
    maturities = _iter_named_ints(filters_payload, ("maturitytype", "maturitytypeid", "maturity", "id"))
    category_ids = sorted({item["id"] for item in categories})
    maturity_ids = sorted({item["id"] for item in maturities})
    if not maturity_ids:
        maturity_ids = [1]
    if not category_ids:
        category_ids = [1]
    return maturity_ids, category_ids


def parse_subcategory_ids(payload: Any) -> list[int]:
    items = _iter_named_ints(payload, ("subcategory", "subcategoryid", "id"))
    ids = sorted({item["id"] for item in items})
    return ids or [1]


def determine_report_date(client: AmHttpClient, override: str | None) -> str:
    if override:
        return override
    candidate = previous_business_day_ist(yesterday_ist())
    for _ in range(7):
        report_date = format_report_date(candidate)
        result = fetch_is_holiday(client, report_date)
        if not result.ok:
            return report_date
        try:
            payload = _parse_json_bytes(result.body)
        except Exception:
            return report_date
        holiday = False
        if isinstance(payload, dict):
            holiday = bool(payload.get("isHoliday") or payload.get("holiday"))
        elif isinstance(payload, bool):
            holiday = payload
        if not holiday:
            return report_date
        candidate -= timedelta(days=1)
        candidate = previous_business_day_ist(candidate)
    return format_report_date(candidate)


def build_payloads(filters_payload: Any, subcategory_map: dict[int, list[int]], report_date: str) -> list[PerformancePayload]:
    maturity_ids, category_ids = parse_filter_dimensions(filters_payload)
    payloads: list[PerformancePayload] = []
    for maturity_type in maturity_ids:
        for category in category_ids:
            for sub_category in subcategory_map.get(category, [1]):
                payloads.append(
                    PerformancePayload(
                        maturity_type=maturity_type,
                        category=category,
                        sub_category=sub_category,
                        mfid=0,
                        report_date=report_date,
                    )
                )
    if not payloads:
        payloads.append(PerformancePayload(1, 1, 1, 0, report_date))
    return payloads


def subcategory_file_name(category: int) -> str:
    return f"category_{slugify(str(category))}.json"
