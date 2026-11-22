"""Collect Google local results for every category x area, saving raw responses to disk."""

import json
from datetime import datetime, timezone
from pathlib import Path

from shadow.config import AREAS, CATEGORIES
from shadow.extract.oxylabs import fetch_google_local


def raw_dir(month: str, data_dir: str = "data") -> Path:
    return Path(data_dir) / "raw" / month / "google_local"


def collect(month: str, categories: list[str], areas: list[str], data_dir: str = "data") -> dict:
    out_dir = raw_dir(month, data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    attempts_log = out_dir / "_attempts.jsonl"
    summary = {"collected": 0, "already_had": 0, "failed": []}

    for category in categories:
        for area in areas:
            out_file = out_dir / f"{category}__{area}.json"
            if out_file.exists():
                summary["already_had"] += 1
                continue

            query = f"{CATEGORIES[category]} {AREAS[area]} Vilnius"
            print(f"Fetching {query!r}...", flush=True)
            result = fetch_google_local(query)

            with attempts_log.open("a", encoding="utf-8") as log:
                for attempt in result.attempts:
                    line = {"category": category, "area": area, "query": query, **attempt}
                    log.write(json.dumps(line, ensure_ascii=False) + "\n")

            if result.data is None:
                summary["failed"].append(query)
                print(f"  failed after {len(result.attempts)} attempt(s)", flush=True)
                continue

            record = {
                "meta": {
                    "category": category,
                    "area": area,
                    "query": query,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "attempts": len(result.attempts),
                },
                "response": result.data,
            }
            out_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            summary["collected"] += 1
            print(f"  saved {out_file.name} after {len(result.attempts)} attempt(s)", flush=True)

    return summary


def load_raw(month: str, data_dir: str = "data") -> list[dict]:
    files = sorted(raw_dir(month, data_dir).glob("*.json"))
    return [{**json.loads(f.read_text(encoding="utf-8")), "source_file": f.name} for f in files]



def load_attempts(month: str, data_dir: str = "data") -> list[dict]:
    log = raw_dir(month, data_dir) / "_attempts.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]