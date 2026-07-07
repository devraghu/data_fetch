from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import requests

from .config import DEFAULT_HEADERS


@dataclass(slots=True)
class FetchResult:
    url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    body: bytes
    error: str | None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 300


class AmHttpClient:
    def __init__(self, *, timeout_seconds: float, max_attempts: int, backoff_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def close(self) -> None:
        self.session.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        data: str | bytes | None = None,
        json_payload: Any | None = None,
        allow_statuses: set[int] | None = None,
    ) -> FetchResult:
        last_error: str | None = None
        allow_statuses = allow_statuses or set()
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=data,
                    json=json_payload,
                    timeout=self.timeout_seconds,
                    allow_redirects=True,
                )
                if response.status_code in allow_statuses or 200 <= response.status_code < 300:
                    return FetchResult(
                        url=url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type"),
                        body=response.content,
                        error=None,
                    )
                last_error = f"HTTP {response.status_code}"
                if response.status_code < 500 and response.status_code not in allow_statuses:
                    return FetchResult(
                        url=url,
                        final_url=str(response.url),
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type"),
                        body=response.content,
                        error=last_error,
                    )
            except requests.RequestException as exc:
                last_error = repr(exc)
            if attempt < self.max_attempts:
                time.sleep(self.backoff_seconds * attempt)
        return FetchResult(
            url=url,
            final_url=None,
            status_code=None,
            content_type=None,
            body=b"",
            error=last_error or "request failed",
        )
