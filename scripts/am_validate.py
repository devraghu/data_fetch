#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _require(path: Path, errors: list[str], message: str) -> None:
    if not path.exists() or path.stat().st_size == 0:
        errors.append(message)


def _require_json(path: Path, errors: list[str], message: str) -> None:
    if not path.exists() or path.stat().st_size == 0:
        errors.append(message)
        return
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{message}: invalid JSON ({exc})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate mirrored AM output")
    parser.add_argument("--input", required=True, help="publish/latest directory")
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="Validate only raw mirror outputs and metadata.",
    )
    args = parser.parse_args()

    root = Path(args.input)
    raw_dir = root / "raw"
    fp_dir = root / "fund_performance"
    extracted_dir = root / "extracted"
    errors: list[str] = []

    _require(root / "metadata.json", errors, "metadata.json missing")
    _require(raw_dir / "NAVAll.txt", errors, "NAVAll.txt missing")
    _require(fp_dir / "filters.json", errors, "fund performance filters missing")
    if not any((fp_dir / "data").glob("*.json")):
        errors.append("no fund performance data files found")
    _require(raw_dir / "aum_average_aum.html", errors, "AUM raw HTML missing")
    benchmark_files = list(raw_dir.glob("benchmark_*.html")) + list(raw_dir.glob("benchmark_*.xlsx"))
    if not benchmark_files:
        errors.append("benchmark raw files missing")
    _require(raw_dir / "amc_members.html", errors, "AMC members raw HTML missing")

    if not args.raw_only:
        for file_name in ["nav_schemes.json", "aum.json", "benchmarks.json", "amc_members.json"]:
            _require_json(extracted_dir / file_name, errors, f"{file_name} missing")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Validation complete: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
