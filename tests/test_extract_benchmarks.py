from pathlib import Path

from am_downloader.extract_benchmarks import extract_benchmark_records


def test_extract_benchmarks_from_html(tmp_path: Path) -> None:
    path = tmp_path / "benchmark_default.html"
    path.write_text(
        "<table><tr><th>Name</th></tr><tr><td>Nifty 50</td></tr></table>",
        encoding="utf-8",
    )
    payload = extract_benchmark_records(tmp_path)
    assert payload["records"]
