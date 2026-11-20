import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "ing1_probe", Path(__file__).resolve().parents[1] / "scripts/ing1_access_probe.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.mark.parametrize(
    "status,body,kind,truncated,expected",
    [
        (403, b"secret upstream body", "json", False, "access_denied"),
        (401, b"", "nav", False, "access_denied"),
        (429, b"", "json", False, "rate_limited"),
        (503, b"", "json", False, "upstream_error"),
        (404, b"", "json", False, "http_error"),
        (200, b"<html>Access denied</html>", "json", False, "malformed_200"),
        (200, b"<html>login</html>", "nav", False, "malformed_200"),
        (200, b'{"broken":', "json", False, "malformed_200"),
        (200, b"", "nav", False, "malformed_200"),
        (200, b'{"data":[]}', "json", False, "json_shape_only"),
        (200, b'{"data":[', "json", True, "truncated_sample_unvalidated"),
        (200, b"Scheme Code;ISIN;NAV\n123;A;1", "nav", True, "nav_header_sample_only"),
        (200, b"<html>Reports</html>", "html", True, "landing_page_only_not_dataset"),
        (200, b"null", "json", False, "malformed_200"),
    ],
)
def test_classification(status, body, kind, truncated, expected):
    assert probe.classify(status, body, kind, truncated) == expected


def test_bounded_sample_does_not_expose_body(monkeypatch):
    class Response:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            assert limit == probe.LIMIT + 1
            return b"private-body-" * (limit // 13 + 1)

    monkeypatch.setattr(probe, "urlopen", lambda *args, **kwargs: Response())
    result = probe.probe(("fixture", "json", "https://example.com/fixed"))
    assert result["sample_bytes"] == probe.LIMIT
    assert result["sample_truncated"]
    assert len(result["sample_sha256"]) == 64
    assert "private-body" not in str(result)


def test_transport_error_is_sanitized(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("secret proxy password")

    monkeypatch.setattr(probe, "urlopen", fail)
    result = probe.probe(("fixture", "json", "https://example.com/fixed"))
    assert result["classification"] == "transport_error"
    assert "password" not in str(result)


def test_no_auth_or_cleartext_targets():
    for _, _, url in probe.TARGETS:
        assert url.startswith("https://") and "@" not in url
