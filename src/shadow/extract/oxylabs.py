"""Call the Oxylabs Web API Google Maps endpoint, retrying intermittent faults."""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

API_URL = "https://webapi.oxylabs.io/v1/scrape/google/maps"
MAX_ATTEMPTS = 5
TIMEOUT_SECONDS = 150
TOO_MANY_REQUESTS = 429


@dataclass
class FetchResult:
    data: dict | None = None
    attempts: list[dict] = field(default_factory=list)


def fetch_google_local(query: str) -> FetchResult:
    headers = {"Authorization": f"Bearer {os.environ['OXYLABS_WEB_API_KEY']}"}
    body = {"query": query, "pages": 1, "output": ["html"], "run_js": True}
    result = FetchResult()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            response = requests.post(API_URL, headers=headers, json=body, timeout=TIMEOUT_SECONDS)
            status = response.status_code
            error = None if response.ok else response.text[:200]
        except requests.RequestException as exc:
            response = None
            status = None
            error = f"{type(exc).__name__}: {exc}"

        result.attempts.append(
            {"attempt": attempt, "started_at": started_at, "status": status, "error": error}
        )

        if response is not None and response.ok:
            result.data = response.json()
            return result
        if status is not None and status < 500 and status != TOO_MANY_REQUESTS:
            return result
        if attempt < MAX_ATTEMPTS:
            time.sleep(5 * attempt)

    return result