"""Parse Google local results pages, as returned by the Oxylabs google/maps endpoint."""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

RATING_LABEL = re.compile(r"Rated ([\d.]+) out of 5, ([\d.]+)(K?) user reviews")
CID_TO_COORDS = re.compile(
    r'\[0,null,"(\d+)",null,null,null,null,"/searchviewer[^"]*",(-?\d+\.\d+),(-?\d+\.\d+)'
)
GOOGLE_ID_TO_CID = re.compile(r'null,"(\d+)",null,"[^"]*",\d+,null,null,"(/g/[^"]+)"')


@dataclass
class Listing:
    google_id: str
    cid: str | None
    name: str
    rating: float | None
    reviews_count: int | None
    reviews_rounded: bool
    category: str | None
    address: str | None
    price_band: str | None
    lat: float | None
    lng: float | None


def html_from_response(response: dict) -> str:
    return response["results"][0]["html"]


def parse_reviews(number: str, suffix: str) -> tuple[int, bool]:
    if suffix == "K":
        return round(float(number) * 1000), True
    return int(number), False


def parse_listings(html: str) -> list[Listing]:
    coords_by_cid = {cid: (float(lat), float(lng)) for cid, lat, lng in CID_TO_COORDS.findall(html)}
    cid_by_google_id = {google_id: cid for cid, google_id in GOOGLE_ID_TO_CID.findall(html)}

    soup = BeautifulSoup(html, "lxml")
    listings = []

    for card in soup.select('div[id^="pv-/g/"]'):
        google_id = card["id"].removeprefix("pv-")
        parts = list(card.stripped_strings)

        rating = None
        reviews_count = None
        reviews_rounded = False
        label = card.find("span", attrs={"aria-label": RATING_LABEL})
        if label:
            match = RATING_LABEL.search(label["aria-label"])
            rating = float(match[1])
            reviews_count, reviews_rounded = parse_reviews(match[2], match[3])

        category = None
        address = None
        for i, part in enumerate(parts):
            if part.startswith("· "):
                category = part.removeprefix("· ")
                address = parts[i + 1] if i + 1 < len(parts) else None
                break

        price_band = next((part for part in parts if part.startswith("€")), None)

        cid = cid_by_google_id.get(google_id)
        lat, lng = coords_by_cid.get(cid, (None, None))

        listings.append(
            Listing(
                google_id=google_id,
                cid=cid,
                name=parts[0],
                rating=rating,
                reviews_count=reviews_count,
                reviews_rounded=reviews_rounded,
                category=category,
                address=address,
                price_band=price_band,
                lat=lat,
                lng=lng,
            )
        )

    return listings