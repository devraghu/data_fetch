"""Read structured AMFI AAUM on an approved GitHub runner; emit one summary row."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from ing1_amfi_readonly_probe import LIMIT, NoRedirect

ENDPOINT = "https://www.amfiindia.com/api/average-aum-schemewise"
REPOSITORY = "devraghu/data_fetch"
_ID = re.compile(r"[0-9]{1,12}")
_AMOUNT = re.compile(r"(?:0|[1-9][0-9]{0,23})(?:\.[0-9]{1,10})?")
_COMPONENTS = (
    "ExcludingFundOfFundsDomesticButIncludingFundOfFundsOverseas",
    "FundOfFundsDomestic",
)
Fetch = Callable[[str, str], tuple[dict, bytes | None]]


class AaumError(ValueError):
    pass


def fetch(target: str, url: str) -> tuple[dict, bytes | None]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Referer": "https://www.amfiindia.com/aum-data/average-aum",
        },
    )
    try:
        with build_opener(NoRedirect).open(request, timeout=35) as reply:
            if reply.headers.get("Content-Encoding", "identity") != "identity":
                return {"outcome": "unsupported_encoding"}, None
            raw = reply.read(LIMIT + 1)
    except HTTPError as exc:
        return {"outcome": "http_error", "status": exc.code}, None
    except (URLError, TimeoutError, OSError):
        return {"outcome": "transport_error"}, None
    if not 0 < len(raw) <= LIMIT:
        return {"outcome": "outside_byte_limit"}, None
    return {"target": target, "outcome": "observed_bytes"}, raw


def _id(value: object) -> str:
    if type(value) not in (int, str) or not _ID.fullmatch(str(value)):
        raise AaumError("INVALID_AMFI_ID")
    return str(value)


def _request(request: Fetch, target: str, **params: str) -> tuple[object, bytes]:
    url = f"{ENDPOINT}?{urlencode(params)}"
    summary, raw = request(target, url)
    if raw is None:
        outcome = summary.get("outcome")
        if outcome not in {
            "http_error",
            "transport_error",
            "unsupported_encoding",
            "outside_byte_limit",
        }:
            outcome = "unavailable"
        raise AaumError(f"{target}:{outcome}")
    try:
        doc = json.loads(raw, parse_float=Decimal)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise AaumError(f"{target}:invalid_json") from exc
    if not isinstance(doc, dict) or "data" not in doc:
        raise AaumError(f"{target}:invalid_envelope")
    return doc["data"], raw


def _require_id(rows: object, wanted: str, stage: str) -> None:
    if not isinstance(rows, list):
        raise AaumError(f"{stage}:invalid_options")
    matches = [row for row in rows if isinstance(row, dict) and str(row.get("id")) == wanted]
    if len(matches) != 1:
        raise AaumError(f"{stage}:requested_id_not_unique")


def _valued(scheme: object) -> tuple[str, bool]:
    if not isinstance(scheme, dict):
        raise AaumError("aaum_scheme_rows:invalid_scheme")
    names = [key for key in ("AMFI_Code", "amfi_code") if key in scheme]
    averages = [key for key in ("AverageAumForTheMonth", "averageAumForTheMonth") if key in scheme]
    if len(names) != 1 or len(averages) != 1:
        raise AaumError("aaum_scheme_rows:ambiguous_or_missing_fields")
    code = _id(scheme[names[0]])
    average = scheme[averages[0]]
    if not isinstance(average, dict):
        raise AaumError("aaum_scheme_rows:invalid_average_block")
    present = [average[key] for key in _COMPONENTS if average.get(key) not in (None, "")]
    if any(
        type(value) not in (str, int, Decimal) or not _AMOUNT.fullmatch(str(value))
        for value in present
    ):
        raise AaumError("aaum_scheme_rows:invalid_amount")
    return code, bool(present)


def download_aaum(
    request: Fetch, *, mf_id: str, financial_year_id: str, period_id: str
) -> tuple[bytes, dict]:
    """Fetch one explicit year/period/scope; never substitute a different source."""
    mf, year, period = map(_id, (mf_id, financial_year_id, period_id))
    params = {"strType": "Categorywise", "MF_ID": mf}
    years, _ = _request(request, "aaum_years", **params)
    _require_id(years, year, "aaum_years")
    periods, _ = _request(request, "aaum_periods", **params, fyId=year)
    _require_id(
        periods.get("periods") if isinstance(periods, dict) else None, period, "aaum_periods"
    )
    rows, raw = _request(request, "aaum_scheme_rows", **params, fyId=year, periodId=period)
    if not isinstance(rows, list):
        raise AaumError("aaum_scheme_rows:invalid_groups")
    seen: set[str] = set()
    count = valued = 0
    for group in rows:
        if not isinstance(group, dict) or not isinstance(group.get("schemes"), list):
            raise AaumError("aaum_scheme_rows:invalid_group")
        for scheme in group["schemes"]:
            count += 1
            code, has_amount = _valued(scheme)
            if code in seen:
                raise AaumError("aaum_scheme_rows:duplicate_scheme")
            seen.add(code)
            valued += int(has_amount)
    if not valued:
        raise AaumError("aaum_scheme_rows:no_valued_schemes")
    return raw, {
        "target": "aaum_scheme_rows",
        "outcome": "scheme_values_observed",
        "financial_year_id": year,
        "period_id": period,
        "mf_id": mf,
        "scheme_count": count,
        "valued_schemes": valued,
        "coverage": "unqualified",
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _resolve_id(rows: object, field: str, *required: str) -> str:
    if not isinstance(rows, list):
        raise AaumError("aaum_discovery:invalid_options")
    match = [
        row
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get(field), str)
        and all(word in row[field].lower() for word in required)
    ]
    if len(match) != 1:
        raise AaumError(f"aaum_discovery:{field}_not_unique_or_unavailable")
    return _id(match[0].get("id"))


def _axis_row(groups: object) -> dict:
    if not isinstance(groups, list):
        raise AaumError("aaum_scheme_rows:invalid_groups")
    matching: list[dict] = []
    for group in groups:
        if not isinstance(group, dict):
            raise AaumError("aaum_scheme_rows:invalid_group")
        records = group.get("schemes", [group])
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise AaumError("aaum_scheme_rows:invalid_scheme_list")
        matching.extend(
            row for row in records if str(row.get("AMFI_Code", row.get("amfi_code"))) == "135762"
        )
    if len(matching) != 1:
        raise AaumError("aaum_scheme_rows:axis_code_missing_or_ambiguous")
    [row] = matching
    return row


def _axis_values(groups: object) -> dict[str, str]:
    row = _axis_row(groups)
    for key in ("ISIN", "ISIN_Growth", "isin", "isinGrowth"):
        if row.get(key) not in (None, "", "-", "INF846K01WO1"):
            raise AaumError("aaum_scheme_rows:axis_isin_mismatch")
    if row.get("AAUM") not in (None, ""):
        values = {"reported_quarter_average": str(row["AAUM"])}
    else:
        _, present = _valued(row)
        if not present:
            raise AaumError("aaum_scheme_rows:axis_amount_unavailable")
        average = row.get("AverageAumForTheMonth", row.get("averageAumForTheMonth"))
        values = {
            key: str(average[key]) for key in _COMPONENTS if average.get(key) not in (None, "")
        }
    if any(not _AMOUNT.fullmatch(value) for value in values.values()):
        raise AaumError("aaum_scheme_rows:invalid_amount")
    return values


def download_axis_quarter(request: Fetch) -> tuple[bytes, dict]:
    """Request Axis only, then retain the exact scheme from its quarter response."""
    params = {"strType": "Categorywise", "MF_ID": "53"}
    years, _ = _request(request, "aaum_years", **params)
    year = _resolve_id(years, "financial_year", "2026", "2027")
    periods, _ = _request(request, "aaum_periods", **params, fyId=year)
    choices = periods.get("periods") if isinstance(periods, dict) else None
    period = _resolve_id(choices, "period", "jul", "sep")
    groups, raw = _request(request, "aaum_scheme_rows", **params, fyId=year, periodId=period)
    values = _axis_values(groups)
    summary = {
        "target": "aaum_scheme_rows",
        "outcome": "axis_scheme_values_observed",
        "scheme_code": "135762",
        "mf_id": "53",
        "financial_year_id": year,
        "period_id": period,
        "requested_period": "2026-07-01/2026-09-30",
        "observed_fields": sorted(values),
        "code_exact_match": True,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "scope": "one_scheme",
        "coverage": "unqualified",
    }
    return json.dumps(summary | {"values_as_reported": values}, sort_keys=True).encode(), summary


def main() -> int:
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
    ):
        print('{"outcome":"approved_github_runner_required"}')
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--financial-year-id")
    parser.add_argument("--period-id")
    parser.add_argument("--mf-id", default="0")
    parser.add_argument("--axis-quarter", action="store_true")
    args = parser.parse_args()
    if not args.axis_quarter and (not args.financial_year_id or not args.period_id):
        parser.error("provide explicit year and period IDs or --axis-quarter")
    try:
        runner = Path(os.environ["RUNNER_TEMP"]) / "arthikamf-aaum-response.json"
        if args.axis_quarter:
            raw, summary = download_axis_quarter(fetch)
        else:
            raw, summary = download_aaum(
                fetch,
                mf_id=args.mf_id,
                financial_year_id=args.financial_year_id,
                period_id=args.period_id,
            )
        with runner.open("xb") as out:
            out.write(raw)
    except (AaumError, OSError, KeyError) as exc:
        reason = str(exc) if isinstance(exc, AaumError) else "runner_storage_error"
        print(json.dumps({"target": "aaum_scheme_rows", "outcome": "failed", "reason": reason}))
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
