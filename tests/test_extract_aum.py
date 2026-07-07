from am_downloader.extract_aum import extract_aum_records


def test_extract_aum_html_table() -> None:
    html = """
    <html><body>
      <table>
        <tr><th>Scheme Code</th><th>Average AUM</th></tr>
        <tr><td>100001</td><td>123.4</td></tr>
      </table>
    </body></html>
    """
    payload = extract_aum_records(html, "https://example.com")
    assert payload["records"]
    assert payload["warnings"] == []


def test_extract_aum_graceful_fallback() -> None:
    payload = extract_aum_records("<html><body>No table</body></html>", "https://example.com")
    assert payload["records"] == []
    assert payload["warnings"]
