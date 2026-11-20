"""ING1.01 bounded feasibility probe; not a collector, importer or publication grant."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

LIMIT = 16_384
TIMEOUT = 12
TARGETS = (
    ("amfi_nav", "nav", "https://portal.amfiindia.com/spages/NAVAll.txt"),
    ("mfapi_history", "json", "https://api.mfapi.in/mf/100027"),
    ("amfi_aum_page", "html", "https://www.amfiindia.com/aum-data/average-aum"),
    ("amfi_benchmark_page", "html", "https://www.amfiindia.com/otherdata/listofbenchmarkindices"),
    ("amfi_amc_page", "html", "https://www.amfiindia.com/aboutamfi?tab=members"),
    ("amfi_historical_page", "html", "https://www.amfiindia.com/net-asset-value/nav-download"),
    ("tigzig_archive_page", "html", "https://www.tigzig.com/apis/mf-nav"),
    ("nse_reports_page", "html", "https://www.nseindia.com/all-reports"),
    ("nse_actions", "json", "https://www.nseindia.com/api/corporates-corporateActions"),
    ("nse_cash_flows", "json", "https://www.nseindia.com/api/fiidiiTradeReact"),
    ("bse_reports_page", "html", "https://www.bseindia.com/markets/MarketInfo/BhavCopy.aspx"),
    ("nifty_history_page", "html", "https://www.niftyindices.com/reports/historical-data"),
    ("rbi_data_page", "html", "https://data.rbi.org.in"),
    ("rbi_publications_page", "html", "https://www.rbi.org.in"),
    ("nsdl_fpi_page", "html", "https://www.fpi.nsdl.co.in"),
    ("investing_10y_page", "html", "https://www.investing.com/rates-bonds/india-10-year-bond-yield-historical-data"),
    ("trendlyne_page", "html", "https://trendlyne.com/mutual-fund/"),
    ("fred_page", "html", "https://fred.stlouisfed.org"),
    ("yahoo_page", "html", "https://finance.yahoo.com"),
    ("nse_terms", "html", "https://www.nseindia.com/terms-of-use"),
    ("bse_disclaimer", "html", "https://www.bseindia.com/static/about/disclaimer.aspx"),
    ("yahoo_terms", "html", "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html"),
    ("fred_terms", "html", "https://fred.stlouisfed.org/legal/"),
)


def classify(status: int, body: bytes, kind: str, truncated: bool) -> str:
    if status in (401, 403):
        return "access_denied"
    if status == 429:
        return "rate_limited"
    if status >= 500:
        return "upstream_error"
    if status != 200:
        return "http_error"
    if not body.strip():
        return "malformed_200"
    if kind == "json":
        if body.lstrip().startswith(b"<"):
            return "malformed_200"
        if truncated:
            return "truncated_sample_unvalidated"
        try:
            value = json.loads(body)
        except (ValueError, UnicodeError):
            return "malformed_200"
        return "json_shape_only" if isinstance(value, (list, dict)) else "malformed_200"
    if kind == "nav":
        if b"Scheme Code;" not in body or body.lstrip().startswith(b"<"):
            return "malformed_200"
        return "nav_header_sample_only"
    return "landing_page_only_not_dataset" if b"<" in body else "unexpected_content"


def probe(target: tuple[str, str, str]) -> dict:
    name, kind, url = target
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Only fixed public HTTPS targets are permitted")
    result = {
        "target": name, "url": url, "expected_kind": kind,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    try:
        request = Request(url, headers={"User-Agent": "ArthikaMF-ING1.01-read-only-audit"})
        with urlopen(request, timeout=TIMEOUT) as response:
            body = response.read(LIMIT + 1)
            truncated = len(body) > LIMIT
            body = body[:LIMIT]
            result.update(
                http_status=response.status, content_type=response.headers.get("Content-Type"),
                sample_bytes=len(body), sample_truncated=truncated,
                sample_sha256=hashlib.sha256(body).hexdigest(),
                classification=classify(response.status, body, kind, truncated),
            )
    except HTTPError as error:
        result.update(http_status=error.code, classification=classify(error.code, b"", kind, False))
    except (URLError, TimeoutError, OSError):
        # Never print exception text, proxy details, headers, credentials or response bodies.
        result["classification"] = "transport_error"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-label", choices=("local-development", "github-runner"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=4) as pool:
        observations = list(pool.map(probe, TARGETS))
    result = {
        "audit_format_version": 1, "step": "ING1.01", "host": args.host_label,
        "github_run_id": os.getenv("GITHUB_RUN_ID"),
        "github_commit": os.getenv("GITHUB_SHA"),
        "limit_bytes_per_response": LIMIT, "timeout_seconds": TIMEOUT,
        "workers": 4, "permission": "unknown; no payload publication authorized",
        "caveat": "Reachability/shape only; not freshness, complete schema, coverage or rights verification. Failed targets do not cancel others. No raw payloads retained.",
        "observations": observations,
    }
    text = json.dumps(result, ensure_ascii=True, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
