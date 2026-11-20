import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://webapi.oxylabs.io/v1/scrape/google/maps"
HEADERS = {"Authorization": f"Bearer {os.environ['OXYLABS_WEB_API_KEY']}"}
MAX_ATTEMPTS = 3

BASE = {"pages": 1, "output": ["html"], "run_js": True}

variants = {
    "cafe_page2": {**BASE, "query": "kavinė Vilnius", "start_page": 2},
    "cafe_seskine": {**BASE, "query": "kavinė Šeškinė Vilnius"},
}

out_dir = Path("samples")
out_dir.mkdir(exist_ok=True)


def fetch(body):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = requests.post(API_URL, headers=HEADERS, json=body, timeout=150)
        if response.ok:
            return response
        print(f"  attempt {attempt}: status {response.status_code}")
        if response.status_code < 500 or attempt == MAX_ATTEMPTS:
            break
        time.sleep(5 * attempt)
    return response


for name, body in variants.items():
    print(f"Trying {name}...")
    response = fetch(body)
    if not response.ok:
        print(f"  gave up: {response.text[:300]}")
        continue

    data = response.json()
    html = data["results"][0]["html"]
    cards = len(re.findall(r'id="pv-/g/', html))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_file = out_dir / f"{name}_{stamp}.json"
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  saved {out_file}, {cards} listings found")