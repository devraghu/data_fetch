from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

AM_WEB_NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"

AM_WEB_AUM_URL = "https://www.amfiindia.com/aum-data/average-aum"

AM_WEB_FUND_PERFORMANCE_PAGE_URL = "https://www.amfiindia.com/otherdata/fund-performance"
AM_WEB_FUND_PERFORMANCE_FILTERS_URL = (
    "https://www.amfiindia.com/gateway/pollingsebi/api/amfi/fundperformancefilters"
)
AM_WEB_FUND_PERFORMANCE_HOLIDAY_URL = (
    "https://www.amfiindia.com/gateway/pollingsebi/api/amfi/isHoliday"
)
AM_WEB_FUND_PERFORMANCE_SUBCATEGORY_URL = (
    "https://www.amfiindia.com/gateway/pollingsebi/api/amfi/getsubcategory"
)
AM_WEB_FUND_PERFORMANCE_URL = (
    "https://www.amfiindia.com/gateway/pollingsebi/api/amfi/fundperformance"
)

AM_WEB_BENCHMARK_URL = "https://www.amfiindia.com/otherdata/listofbenchmarkindices"
AM_WEB_BENCHMARK_URL_DEBT = "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=debtSchemes"
AM_WEB_BENCHMARK_URL_EQUITY = "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=equitySchemes"
AM_WEB_BENCHMARK_URL_EQUITY_SECTORAL = (
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=equitySectoral"
)
AM_WEB_BENCHMARK_URL_EQUITY_THEMATIC = (
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=equityThematic"
)
AM_WEB_BENCHMARK_URL_HYBRID = "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=hybridSchemes"
AM_WEB_BENCHMARK_URL_SOLUTION = (
    "https://www.amfiindia.com/otherdata/listofbenchmarkindices?tab=solutionOriented"
)
AM_WEB_BENCHMARK_XLSX_URL = "https://www.amfiindia.com/Themes/Theme1/downloads/ListofTier1_Benchmark.xlsx"

AM_WEB_AMC_MEMBERS_URL = "https://www.amfiindia.com/aboutamfi?tab=members"

AM_WEB_REFERER = "https://www.amfiindia.com/"
AM_WEB_PERFORMANCE_REFERER = "https://www.amfiindia.com/polling/amfi/fund-performance"
AM_WEB_AUM_REFERER = "https://www.amfiindia.com/aum-data/average-aum"
AM_WEB_BENCHMARK_REFERER = "https://www.amfiindia.com/otherdata/listofbenchmarkindices"
AM_WEB_AMC_REFERER = "https://www.amfiindia.com/aboutamfi?tab=members"
AM_WEB_ORIGIN = "https://www.amfiindia.com"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/json,text/plain,*/*",
}

JSON_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": AM_WEB_ORIGIN,
}

TEXT_POST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "text/plain",
    "Origin": AM_WEB_ORIGIN,
}

BENCHMARK_PAGES = {
    "benchmark_default.html": AM_WEB_BENCHMARK_URL,
    "benchmark_debt.html": AM_WEB_BENCHMARK_URL_DEBT,
    "benchmark_equity.html": AM_WEB_BENCHMARK_URL_EQUITY,
    "benchmark_equity_sectoral.html": AM_WEB_BENCHMARK_URL_EQUITY_SECTORAL,
    "benchmark_equity_thematic.html": AM_WEB_BENCHMARK_URL_EQUITY_THEMATIC,
    "benchmark_hybrid.html": AM_WEB_BENCHMARK_URL_HYBRID,
    "benchmark_solution.html": AM_WEB_BENCHMARK_URL_SOLUTION,
}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value or not value.strip():
        return default
    return int(value.strip())


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value or not value.strip():
        return default
    return float(value.strip())


@dataclass(slots=True)
class Settings:
    output_dir: Path
    report_date_override: str | None = None
    timeout_seconds: float = _env_float("AM_TIMEOUT_SECONDS", 30.0)
    max_attempts: int = _env_int("AM_MAX_ATTEMPTS", 4)
    backoff_seconds: float = _env_float("AM_BACKOFF_SECONDS", 1.5)
    raw_only: bool = False

    @classmethod
    def from_env(cls, output_dir: str | Path, report_date_override: str | None = None, raw_only: bool = False) -> "Settings":
        return cls(
            output_dir=Path(output_dir),
            report_date_override=report_date_override or os.getenv("AM_REPORT_DATE") or None,
            raw_only=raw_only,
        )
