"""Bounded, summary-only Package C AMFI qualification for an approved runner."""

from __future__ import annotations

import csv
import json
import os
import sys
from collections.abc import Callable
from io import StringIO

from ing1_amfi_aaum_runner import (
    REPOSITORY,
    AaumError,
    download_axis_quarter,
)
from ing1_amfi_aaum_runner import (
    fetch as fetch_aaum,
)
from ing1_amfi_readonly_probe import TARGETS, fetch

SCHEME_CODE = "135762"
MAX_SUMMARY_FIELDS = 40
Fetch = Callable[[str, str], tuple[dict, bytes | None]]


def _base_summary(target: str, result: dict, payload: bytes | None) -> dict:
    summary = {
        "target": target,
        "outcome": result.get("outcome", "unavailable"),
    }
    for key in ("status", "media", "bytes", "sha256"):
        if key in result:
            summary[key] = result[key]
    if payload is not None and "sha256" not in summary:
        import hashlib

        summary["sha256"] = hashlib.sha256(payload).hexdigest()
    return summary


def summarize_navall(result: dict, payload: bytes | None) -> dict:
    summary = _base_summary("navall", result, payload)
    if payload is None:
        return summary
    lines = payload.decode("utf-8-sig", errors="replace").splitlines()
    header = next((line for line in lines if line.startswith("Scheme Code;")), "")
    matches = sum(line.split(";", 1)[0].strip() == SCHEME_CODE for line in lines)
    summary.update(
        {
            "outcome": "summary_observed",
            "physical_lines": len(lines),
            "expected_header": bool(header),
            "requested_scheme_code_match_count": matches,
        }
    )
    return summary


def summarize_scheme_master(result: dict, payload: bytes | None) -> dict:
    summary = _base_summary("scheme_master", result, payload)
    if payload is None:
        return summary
    try:
        rows = list(csv.reader(StringIO(payload.decode("utf-8-sig"))))
    except (UnicodeError, csv.Error):
        return summary | {"outcome": "invalid_csv"}
    if not rows:
        return summary | {"outcome": "empty_csv"}
    code_columns = [
        index
        for index, name in enumerate(rows[0])
        if name.strip().lower().replace("_", " ") in {"amfi code", "scheme code", "code"}
    ]
    match_count = None
    if len(code_columns) == 1:
        code_index = code_columns[0]
        match_count = sum(
            code_index < len(row) and row[code_index].strip() == SCHEME_CODE for row in rows[1:]
        )
    summary.update(
        {
            "outcome": "summary_observed",
            "data_rows": max(0, len(rows) - 1),
            "header_field_count": len(rows[0]),
            "header_fields": rows[0][:MAX_SUMMARY_FIELDS],
            "header_fields_truncated": len(rows[0]) > MAX_SUMMARY_FIELDS,
            "scheme_code_column_unique": len(code_columns) == 1,
            "requested_scheme_code_match_count": match_count,
        }
    )
    return summary


def qualify(request: Fetch = fetch, aaum_request: Fetch = fetch_aaum) -> list[dict]:
    summaries = []
    for target in ("navall", "scheme_master"):
        result, payload = request(target, TARGETS[target])
        summaries.append(
            summarize_navall(result, payload)
            if target == "navall"
            else summarize_scheme_master(result, payload)
        )
    try:
        retained, summary = download_axis_quarter(aaum_request)
        # Only the code/field-scope summary leaves the parsing routine.
        del retained
        summaries.append(summary)
    except AaumError as exc:
        summaries.append(
            {
                "target": "aaum_scheme_rows",
                "outcome": "failed",
                "reason": str(exc)[:120],
                "scheme_code": SCHEME_CODE,
                "scope": "one_scheme",
            }
        )
    return summaries


def main() -> int:
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
    ):
        print('{"outcome":"approved_github_runner_required"}')
        return 2
    for summary in qualify():
        print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
