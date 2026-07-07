from am_downloader.extract_nav import parse_navall_text


def test_parse_navall_text_preserves_section_and_amc() -> None:
    sample = """Open Ended Schemes(Debt Scheme - Banking and PSU Fund)
Aditya Birla Sun Life Mutual Fund
Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
100001;INF000000001;;Fund A - Direct Growth;12.3456;02-Jul-2026
100002;INF000000002;INF000000003;Fund B - IDCW;23.4567;02-Jul-2026
"""

    rows = parse_navall_text(sample)

    assert len(rows) == 2
    assert rows[0]["scheme_code"] == "100001"
    assert rows[0]["section"] == "Open Ended Schemes(Debt Scheme - Banking and PSU Fund)"
    assert rows[0]["amc_name"] == "Aditya Birla Sun Life Mutual Fund"
    assert rows[1]["isin_reinvestment"] == "INF000000003"
