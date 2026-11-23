"""Collect Google local results for every category x area, saving raw responses to disk."""

import gzip
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from shadow.config import AREAS, CATEGORIES
from shadow.extract.oxylabs import fetch_google_local


def raw_dir(month: str, data_dir: str = "data") -> Path:
    return Path(data_dir) / "raw" / month / "google_local"


@dataclass
class CollectSummary:
    collected: int = 0
    already_had: int = 0
    failed: list[str] = field(default_factory=list)


def collect(month: str, categories: list[str], areas: list[str], data_dir: str = "data") -> CollectSummary:
    out_dir = raw_dir(month, data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    attempts_log = out_dir / "_attempts.jsonl"
    summary = CollectSummary()

    for category in categories:
        for area in areas:
            out_file = out_dir / f"{category}__{area}.json.gz"
            if out_file.exists():
                summary.already_had += 1
                continue

            query = f"{CATEGORIES[category]} {AREAS[area]} Vilnius"
            print(f"Fetching {query!r}...", flush=True)
            result = fetch_google_local(query)

            with attempts_log.open("a", encoding="utf-8") as log:
                for attempt in result.attempts:
                    line = {"category": category, "area": area, "query": query, **attempt}
                    log.write(json.dumps(line, ensure_ascii=False) + "\n")

            if result.data is None:
                summary.failed.append(query)
                print(f"  failed after {len(result.attempts)} attempt(s)", flush=True)
                continue

            record = {
                "meta": {
                    "category": category,
                    "area": area,
                    "query": query,
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "attempts": len(result.attempts),
                },
                "response": result.data,
            }
            partial = out_file.with_name(out_file.name + ".partial")
            with gzip.open(partial, "wt", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False)
            partial.replace(out_file)
            summary.collected += 1
            print(f"  saved {out_file.name} after {len(result.attempts)} attempt(s)", flush=True)

    return summary


def load_raw(month: str, data_dir: str = "data") -> list[dict]:
    records = []
    for path in sorted(raw_dir(month, data_dir).glob("*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            records.append({**json.load(f), "source_file": path.name})
    return records


def load_attempts(month: str, data_dir: str = "data") -> list[dict]:
    log = raw_dir(month, data_dir) / "_attempts.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]