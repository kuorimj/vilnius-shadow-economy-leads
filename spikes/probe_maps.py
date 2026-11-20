import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://webapi.oxylabs.io/v1/scrape/google/maps"
API_KEY = os.environ["OXYLABS_WEB_API_KEY"]

schema = {
    "type": "object",
    "properties": {
        "places": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                    "category": {"type": "string"},
                    "rating": {"type": "number"},
                    "reviews_count": {"type": "integer"},
                },
            },
        }
    },
}

body = {
    "query": "restoranas Vilnius",
    "domain": "lt",
    "locale": "lt_LT",
    "location": "LT",
    "pages": 1,
    "output": ["html", "json"],
    "json": {"schema": schema},
}

response = requests.post(
    API_URL,
    headers={"Authorization": f"Bearer {API_KEY}"},
    json=body,
    timeout=150,
)
if not response.ok:
    print(f"Status: {response.status_code}")
    print(response.text[:2000])
    raise SystemExit(1)
data = response.json()

out_dir = Path("samples")
out_dir.mkdir(exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out_file = out_dir / f"google_maps_{stamp}.json"
out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"Saved full response to {out_file}")
print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])