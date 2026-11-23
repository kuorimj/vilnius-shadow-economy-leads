import gzip
import json
from pathlib import Path

from shadow.extract import google_collect, oxylabs
from shadow.extract.google_collect import CollectSummary
from shadow.extract.oxylabs import FetchResult

FIXTURE = Path(__file__).parent / "fixtures" / "google_local_kavine_seskine.json"


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.ok = status_code < 400
        self.payload = payload
        self.text = json.dumps(payload or {"title": "FAULT"})

    def json(self):
        return self.payload


def test_fetch_retries_faults_then_succeeds(monkeypatch):
    responses = [FakeResponse(500), FakeResponse(500), FakeResponse(200, {"results": []})]
    monkeypatch.setenv("OXYLABS_WEB_API_KEY", "test-key")
    monkeypatch.setattr(oxylabs.requests, "post", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr(oxylabs.time, "sleep", lambda seconds: None)

    result = oxylabs.fetch_google_local("kavinė Šeškinė Vilnius")

    assert result.data == {"results": []}
    assert [a["status"] for a in result.attempts] == [500, 500, 200]


def test_fetch_retries_rate_limiting(monkeypatch):
    responses = [FakeResponse(429), FakeResponse(200, {"results": []})]
    monkeypatch.setenv("OXYLABS_WEB_API_KEY", "test-key")
    monkeypatch.setattr(oxylabs.requests, "post", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr(oxylabs.time, "sleep", lambda seconds: None)

    result = oxylabs.fetch_google_local("kavinė Šeškinė Vilnius")

    assert result.data == {"results": []}
    assert [a["status"] for a in result.attempts] == [429, 200]


def test_fetch_does_not_retry_client_errors(monkeypatch):
    calls = []
    monkeypatch.setenv("OXYLABS_WEB_API_KEY", "test-key")
    monkeypatch.setattr(oxylabs.requests, "post", lambda *args, **kwargs: calls.append(1) or FakeResponse(400))

    result = oxylabs.fetch_google_local("kavinė Šeškinė Vilnius")

    assert result.data is None
    assert len(calls) == 1


def test_collect_saves_raw_logs_attempts_and_skips_existing(monkeypatch, tmp_path):
    response = json.loads(FIXTURE.read_text(encoding="utf-8"))
    attempts = [
        {"attempt": 1, "started_at": "t1", "status": 500, "error": "fault"},
        {"attempt": 2, "started_at": "t2", "status": 200, "error": None},
    ]
    calls = []

    def fake_fetch(query):
        calls.append(query)
        return FetchResult(data=response, attempts=attempts)

    monkeypatch.setattr(google_collect, "fetch_google_local", fake_fetch)

    summary = google_collect.collect("2026-11", ["cafe_restaurant"], ["seskine"], data_dir=tmp_path)

    out_dir = google_collect.raw_dir("2026-11", tmp_path)
    with gzip.open(out_dir / "cafe_restaurant__seskine.json.gz", "rt", encoding="utf-8") as f:
        saved = json.load(f)
    log_lines = (out_dir / "_attempts.jsonl").read_text(encoding="utf-8").splitlines()

    assert summary == CollectSummary(collected=1)
    assert calls == ["kavinė Šeškinė Vilnius"]
    assert saved["meta"]["attempts"] == 2
    assert saved["response"] == response
    assert len(log_lines) == 2

    second = google_collect.collect("2026-11", ["cafe_restaurant"], ["seskine"], data_dir=tmp_path)

    assert second.already_had == 1
    assert len(calls) == 1


def test_collect_records_failed_queries(monkeypatch, tmp_path):
    monkeypatch.setattr(
        google_collect,
        "fetch_google_local",
        lambda query: FetchResult(data=None, attempts=[{"attempt": 1, "status": 500}]),
    )

    summary = google_collect.collect("2026-11", ["car_repair"], ["zirmunai"], data_dir=tmp_path)

    assert summary.failed == ["autoservisas Žirmūnai Vilnius"]
    assert not (google_collect.raw_dir("2026-11", tmp_path) / "car_repair__zirmunai.json").exists()