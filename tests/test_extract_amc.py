from am_downloader.extract_amc import extract_amc_records


def test_extract_amc_visible_links() -> None:
    html = '<a href="/amc/1"><img src="logo.png" />AMC One</a>'
    payload = extract_amc_records(html, "https://example.com")
    assert payload["records"] == [
        {"name": "AMC One", "url": "/amc/1", "logo_url": "logo.png"}
    ]


def test_extract_amc_fallback_warning() -> None:
    payload = extract_amc_records("<html></html>", "https://example.com")
    assert payload["warnings"]
