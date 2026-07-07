from am_downloader.fund_performance import build_fund_performance_payload, parse_filter_dimensions


def test_build_fund_performance_payload() -> None:
    payload = build_fund_performance_payload(
        maturity_type=1,
        category=2,
        sub_category=3,
        mfid=0,
        report_date="02-Jul-2026",
    )
    assert payload == {
        "maturityType": 1,
        "category": 2,
        "subCategory": 3,
        "mfid": 0,
        "reportDate": "02-Jul-2026",
    }


def test_parse_filter_dimensions_falls_back_to_ids() -> None:
    payload = {
        "maturityTypes": [{"maturityType": 1, "name": "Open"}],
        "categories": [{"category": 7, "name": "Equity"}],
    }
    maturities, categories = parse_filter_dimensions(payload)
    assert maturities == [1]
    assert categories == [7]
