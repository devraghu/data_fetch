"""Scoped AMFI runner probe: publish only counts, shape and hashes to logs."""

import hashlib
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

LIMIT = 16 * 1024 * 1024
TARGETS = {
    "navall": "https://portal.amfiindia.com/spages/NAVAll.txt",
    "scheme_master": "https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?mf=0",
    "aaum_years": "https://www.amfiindia.com/api/average-aum-schemewise?strType=Categorywise&MF_ID=0",
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(name: str, url: str) -> tuple[dict, bytes | None]:
    opener = build_opener(NoRedirect)
    result = {"target": name}
    try:
        request = Request(url, headers={"Accept-Encoding": "identity"})
        with opener.open(request, timeout=15) as response:
            result["status"] = response.status
            result["media"] = response.headers.get_content_type()
            if response.headers.get("Content-Encoding", "identity") != "identity":
                return result | {"outcome": "unsupported_encoding"}, None
            payload = response.read(LIMIT + 1)
    except HTTPError as exc:
        return result | {"status": exc.code, "outcome": "http_error"}, None
    except (URLError, TimeoutError, OSError):
        return result | {"outcome": "transport_error"}, None
    if not 0 < len(payload) <= LIMIT:
        return result | {"outcome": "outside_byte_limit"}, None
    result |= {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    return result | {"outcome": "observed_bytes"}, payload


def _path(payload: bytes | None, *keys: str):
    if payload is None:
        return None
    try:
        doc = json.loads(payload)
    except (ValueError, UnicodeError, RecursionError):
        return None
    for key in keys:
        if not isinstance(doc, dict):
            return None
        doc = doc.get(key)
    return doc


def _first_id(rows: object) -> str | None:
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return None
    value = rows[0].get("id")
    if type(value) not in {int, str} or not re.fullmatch(r"[0-9]{1,12}", str(value)):
        return None
    return str(value)


def aaum_probe():
    """Use a single, syntactically verified year and period ID; report shape only."""
    base = TARGETS["aaum_years"]
    result, payload = fetch("aaum_years", base)
    year = _first_id(_path(payload, "data"))
    yield result | {"usable_year_id": year is not None}
    if year is None:
        return
    result, payload = fetch("aaum_periods", f"{base}&fyId={year}")
    period = _first_id(_path(payload, "data", "periods"))
    yield result | {"usable_period_id": period is not None}
    if period is None:
        return
    result, payload = fetch("aaum_scheme_rows", f"{base}&fyId={year}&periodId={period}")
    groups = _path(payload, "data")
    schemes = (
        [
            row
            for group in groups
            if isinstance(group, dict) and isinstance(group.get("schemes"), list)
            for row in group["schemes"]
            if isinstance(row, dict)
        ]
        if isinstance(groups, list)
        else []
    )
    yield result | {
        "scheme_count": len(schemes),
        "monthly_average_blocks": sum(
            isinstance(row.get("AverageAumForTheMonth", row.get("averageAumForTheMonth")), dict)
            for row in schemes
        ),
        "financial_year_id": year,
        "period_id": period,
    }


def probe(name: str, url: str) -> dict:
    result, payload = fetch(name, url)
    if payload is None:
        return result
    if payload.lstrip().startswith(b"<"):
        return result | {"outcome": "html_or_xml"}
    return result | {
        "outcome": "observed_bytes",
        "header_sample": b"Scheme Code;" in payload[:16384],
        "lines": payload.count(b"\n"),
    }


if __name__ == "__main__":
    if len(sys.argv) != 1:
        raise SystemExit(2)
    for key in ("navall", "scheme_master"):
        print(json.dumps(probe(key, TARGETS[key]), sort_keys=True), flush=True)
    for item in aaum_probe():
        print(json.dumps(item, sort_keys=True), flush=True)
