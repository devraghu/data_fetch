#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from am_downloader.config import (
    AM_WEB_AMC_MEMBERS_URL,
    AM_WEB_AUM_URL,
)
from am_downloader.extract_amc import extract_amc_records
from am_downloader.extract_aum import extract_aum_records
from am_downloader.extract_benchmarks import extract_benchmark_records
from am_downloader.extract_nav import parse_navall_text
from am_downloader.utils import write_csv, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract structured AM data from raw mirror output")
    parser.add_argument("--input", required=True, help="Raw input directory")
    parser.add_argument("--output", required=True, help="Extraction output directory")
    args = parser.parse_args()

    raw_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    nav_path = raw_dir / "NAVAll.txt"
    if nav_path.exists():
        nav_records = parse_navall_text(nav_path.read_text(encoding="utf-8", errors="replace"))
        write_json(out_dir / "nav_schemes.json", nav_records)
        write_csv(
            out_dir / "nav_schemes.csv",
            nav_records,
            [
                "scheme_code",
                "isin_growth_or_payout",
                "isin_reinvestment",
                "scheme_name",
                "nav",
                "date",
                "section",
                "amc_name",
            ],
        )

    aum_path = raw_dir / "aum_average_aum.html"
    if aum_path.exists():
        aum_payload = extract_aum_records(aum_path.read_text(encoding="utf-8", errors="replace"), AM_WEB_AUM_URL)
        write_json(out_dir / "aum.json", aum_payload)

    benchmark_payload = extract_benchmark_records(raw_dir)
    write_json(out_dir / "benchmarks.json", benchmark_payload)

    amc_path = raw_dir / "amc_members.html"
    if amc_path.exists():
        amc_payload = extract_amc_records(amc_path.read_text(encoding="utf-8", errors="replace"), AM_WEB_AMC_MEMBERS_URL)
        write_json(out_dir / "amc_members.json", amc_payload)

    print(f"Extraction complete: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
