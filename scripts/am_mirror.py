#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from am_downloader.config import Settings
from am_downloader.mirror import AmMirror


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror AM data into publish/arthikamf/am/latest")
    parser.add_argument("--report-date", help="AM report date like 02-Jul-2026")
    parser.add_argument("--output", default="publish/arthikamf/am/latest", help="Output directory")
    parser.add_argument("--raw-only", action="store_true", help="Mirror raw files only")
    args = parser.parse_args()

    settings = Settings.from_env(args.output, report_date_override=args.report_date, raw_only=args.raw_only)
    mirror = AmMirror(settings)
    try:
        result = mirror.run()
    finally:
        mirror.close()
    print(f"Mirror complete: {result.output_dir}")
    if result.metadata["errors"]:
        for error in result.metadata["errors"]:
            print(f"ERROR: {error}")
        return 1
    for warning in result.metadata["warnings"]:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
