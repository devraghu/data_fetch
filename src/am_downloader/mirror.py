from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from .config import (
    AM_WEB_AMC_MEMBERS_URL,
    AM_WEB_AMC_REFERER,
    AM_WEB_AUM_REFERER,
    AM_WEB_AUM_URL,
    AM_WEB_BENCHMARK_REFERER,
    AM_WEB_BENCHMARK_XLSX_URL,
    AM_WEB_NAVALL_URL,
    BENCHMARK_PAGES,
    DEFAULT_HEADERS,
    Settings,
)
from .fund_performance import (
    build_payloads,
    determine_report_date,
    fetch_filters,
    fetch_fund_performance,
    fetch_is_holiday,
    fetch_subcategories,
    parse_subcategory_ids,
)
from .http_client import AmHttpClient, FetchResult
from .utils import ensure_dir, sha256_bytes, utc_now_iso, write_json


@dataclass(slots=True)
class MirrorResult:
    metadata: dict[str, Any]
    output_dir: Path


class AmMirror:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AmHttpClient(
            timeout_seconds=settings.timeout_seconds,
            max_attempts=settings.max_attempts,
            backoff_seconds=settings.backoff_seconds,
        )

    def close(self) -> None:
        self.client.close()

    def run(self) -> MirrorResult:
        latest_dir = ensure_dir(self.settings.output_dir)
        raw_dir = ensure_dir(latest_dir / "raw")
        fp_dir = ensure_dir(latest_dir / "fund_performance")
        subcat_dir = ensure_dir(fp_dir / "subcategories")
        data_dir = ensure_dir(fp_dir / "data")
        ensure_dir(latest_dir / "extracted")

        metadata: dict[str, Any] = {
            "fetched_at_utc": utc_now_iso(),
            "report_date": None,
            "runner": os.getenv("GITHUB_ACTIONS") and "github-actions" or "local",
            "sources": {},
            "errors": [],
            "warnings": [],
        }

        self._mirror_navall(raw_dir / "NAVAll.txt", metadata)
        self._mirror_optional_html(
            raw_dir / "aum_average_aum.html",
            metadata,
            key="aum_average_aum",
            url=AM_WEB_AUM_URL,
            referer=AM_WEB_AUM_REFERER,
        )
        self._mirror_benchmarks(raw_dir, metadata)
        self._mirror_optional_html(
            raw_dir / "amc_members.html",
            metadata,
            key="amc_members",
            url=AM_WEB_AMC_MEMBERS_URL,
            referer=AM_WEB_AMC_REFERER,
        )
        self._mirror_fund_performance(fp_dir, subcat_dir, data_dir, metadata)

        write_json(latest_dir / "metadata.json", metadata)
        return MirrorResult(metadata=metadata, output_dir=latest_dir)

    def _headers(self, referer: str | None = None) -> dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        if referer:
            headers["Referer"] = referer
        return headers

    def _publish_root(self) -> Path:
        for candidate in [self.settings.output_dir, *self.settings.output_dir.parents]:
            if candidate.name == "publish":
                return candidate
        return self.settings.output_dir.parents[2]

    def _record_result(
        self,
        *,
        key: str,
        url: str,
        path: Path,
        result: FetchResult,
        metadata: dict[str, Any],
        required: bool,
    ) -> None:
        source: dict[str, Any] = {
            "url": url,
            "final_url": result.final_url,
            "status_code": result.status_code,
            "content_type": result.content_type,
            "bytes": len(result.body),
            "saved_path": str(path.relative_to(self._publish_root())) if path.exists() else None,
            "sha256": sha256_bytes(result.body) if result.body else None,
            "error": result.error,
        }
        metadata["sources"][key] = source
        if result.ok and result.body:
            ensure_dir(path.parent)
            path.write_bytes(result.body)
            source["saved_path"] = str(path.relative_to(self._publish_root()))
        elif required:
            metadata["errors"].append(f"{key} download failed: {result.error or result.status_code}")
        else:
            metadata["warnings"].append(f"{key} download failed: {result.error or result.status_code}")

    def _mirror_navall(self, path: Path, metadata: dict[str, Any]) -> None:
        result = self.client.request("GET", AM_WEB_NAVALL_URL, headers=self._headers())
        self._record_result(
            key="navall",
            url=AM_WEB_NAVALL_URL,
            path=path,
            result=result,
            metadata=metadata,
            required=True,
        )
        if result.ok:
            text = result.body.decode("utf-8", errors="replace")
            if "Scheme Code" not in text or "Net Asset Value" not in text:
                metadata["errors"].append("navall validation failed: expected headers missing")

    def _mirror_optional_html(
        self,
        path: Path,
        metadata: dict[str, Any],
        *,
        key: str,
        url: str,
        referer: str,
    ) -> None:
        result = self.client.request("GET", url, headers=self._headers(referer))
        self._record_result(
            key=key,
            url=url,
            path=path,
            result=result,
            metadata=metadata,
            required=False,
        )

    def _mirror_benchmarks(self, raw_dir: Path, metadata: dict[str, Any]) -> None:
        xlsx_result = self.client.request(
            "GET",
            AM_WEB_BENCHMARK_XLSX_URL,
            headers=self._headers(AM_WEB_BENCHMARK_REFERER),
        )
        self._record_result(
            key="benchmark_xlsx",
            url=AM_WEB_BENCHMARK_XLSX_URL,
            path=raw_dir / "benchmark_tier1.xlsx",
            result=xlsx_result,
            metadata=metadata,
            required=False,
        )
        for filename, url in BENCHMARK_PAGES.items():
            result = self.client.request("GET", url, headers=self._headers(AM_WEB_BENCHMARK_REFERER))
            self._record_result(
                key=filename.removesuffix(".html"),
                url=url,
                path=raw_dir / filename,
                result=result,
                metadata=metadata,
                required=False,
            )

    def _mirror_fund_performance(
        self,
        fp_dir: Path,
        subcat_dir: Path,
        data_dir: Path,
        metadata: dict[str, Any],
    ) -> None:
        filters = fetch_filters(self.client)
        self._record_result(
            key="fund_performance_filters",
            url=filters.url,
            path=fp_dir / "filters.json",
            result=filters,
            metadata=metadata,
            required=True,
        )
        if not filters.ok or not filters.body:
            return

        import json

        filters_payload = json.loads(filters.body.decode("utf-8", errors="replace"))
        report_date = determine_report_date(self.client, self.settings.report_date_override)
        metadata["report_date"] = report_date

        holiday = fetch_is_holiday(self.client, report_date)
        self._record_result(
            key="fund_performance_is_holiday",
            url=holiday.url,
            path=fp_dir / "isHoliday.json",
            result=holiday,
            metadata=metadata,
            required=False,
        )

        maturity_ids = []
        category_ids = []
        from .fund_performance import parse_filter_dimensions

        maturity_ids, category_ids = parse_filter_dimensions(filters_payload)
        subcategory_map: dict[int, list[int]] = {}
        for category_id in category_ids:
            result = fetch_subcategories(self.client, category_id)
            self._record_result(
                key=f"fund_performance_subcategory_{category_id}",
                url=result.url,
                path=subcat_dir / f"category_{category_id}.json",
                result=result,
                metadata=metadata,
                required=False,
            )
            if result.ok and result.body:
                try:
                    payload = json.loads(result.body.decode("utf-8", errors="replace"))
                    subcategory_map[category_id] = parse_subcategory_ids(payload)
                except Exception as exc:
                    metadata["warnings"].append(
                        f"subcategory parse failed for category {category_id}: {exc}"
                    )

        payloads = build_payloads(filters_payload, subcategory_map, report_date)
        success_count = 0
        for payload in payloads:
            result = fetch_fund_performance(self.client, payload.to_dict())
            self._record_result(
                key=f"fund_performance_{payload.file_slug().removesuffix('.json')}",
                url=result.url,
                path=data_dir / payload.file_slug(),
                result=result,
                metadata=metadata,
                required=False,
            )
            if result.ok and result.body:
                success_count += 1
        if success_count == 0:
            metadata["errors"].append("fund performance download failed: no data responses saved")
