import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://webapi.oxylabs.io/v1/scrape/google/maps"
HEADERS = {"Authorization": f"Bearer {os.environ['OXYLABS_WEB_API_KEY']}"}

variants = {
    "restaurant_query_nojs": {"query": "restoranas Vilnius", "pages": 1, "output": ["html"]},
    "cafe_query_js": {"query": "kavinė Vilnius", "pages": 1, "output": ["html"], "run_js": True},
    "restaurant_url": {"url": "https://www.google.com/maps/search/restoranas+Vilnius", "output": ["html"]},
}

out_dir = Path("samples")
out_dir.mkdir(exist_ok=True)

for name, body in variants.items():
    print(f"Trying {name}...")
    response = requests.post(API_URL, headers=HEADERS, json=body, timeout=150)
    print(f"  status {response.status_code}")
    if response.ok:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_file = out_dir / f"{name}_{stamp}.json"
        out_file.write_text(json.dumps(response.json(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  saved {out_file}")
    else:
        print(f"  {response.text[:300]}")