"""Parse Google local results pages, as returned by the Oxylabs google/maps endpoint.

Google serves at least two card layouts for the same kind of page:
- Layout A: price and category are separate pieces ("€10–20", "· Lithuanian"), the
  reviews label reads "Rated 4.5 out of 5, 16K user reviews", and coordinates sit in a
  script array keyed by the place's CID.
- Layout B: price and category share one piece ("· €10–20 · Lithuanian"), a status
  ("Open", "Closed") comes before the address, the reviews label reads
  "15.9K reviews for <name>", and coordinates sit in a script array keyed by the /g/ ID.
"""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

RATING = re.compile(r"Rated ([\d.]+) out of 5")
REVIEWS = re.compile(r"([\d.,]+)(K?) (?:user )?reviews")
YEARS_IN_BUSINESS = re.compile(r"(\d+)\+ years in business")
STATUS_WORDS = ("Open", "Closed", "Closes", "Opens", "Temporarily closed", "Permanently closed")
CITY_ONLY = {"Vilnius, Lithuania", "Vilnius"}

COORDS_BY_CID = re.compile(
    r'\[0,null,"(\d+)",null,null,null,null,"/searchviewer[^"]*",(-?\d+\.\d+),(-?\d+\.\d+)'
)
COORDS_LAYOUT_B = re.compile(r'\[(-?\d+\.\d+),(-?\d+\.\d+)\]\],null,\["/searchviewer')
GOOGLE_ID = re.compile(r'"(/g/[^"]+)"')
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
    years_in_business: int | None
    lat: float | None
    lng: float | None


def html_from_response(response: dict) -> str:
    return response["results"][0]["html"]


def clean(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return text.replace("\u2066", "").replace("\u2069", "").strip()


def parse_reviews(number: str, suffix: str) -> tuple[int, bool]:
    value = float(number.replace(",", ""))
    if suffix == "K":
        return round(value * 1000), True
    return int(value), False


def is_status(piece: str) -> bool:
    return piece.startswith(STATUS_WORDS)


def coordinates_by_google_id(html: str) -> dict[str, tuple[float, float]]:
    coords = {}
    for match in COORDS_LAYOUT_B.finditer(html):
        before = html[max(0, match.start() - 5000) : match.start()]
        ids = GOOGLE_ID.findall(before)
        if ids:
            coords[ids[-1]] = (float(match[1]), float(match[2]))
    return coords


def split_category_piece(piece: str) -> tuple[str | None, str | None]:
    parts = [part.strip() for part in piece.split("·") if part.strip()]
    price = next((part for part in parts if part.startswith("€")), None)
    category = next((part for part in reversed(parts) if not part.startswith("€")), None)
    return category, price


def split_address_piece(piece: str) -> tuple[str | None, int | None]:
    years = None
    address_parts = []
    for part in (part.strip() for part in piece.split("·")):
        match = YEARS_IN_BUSINESS.fullmatch(part)
        if match:
            years = int(match[1])
        elif part:
            address_parts.append(part)
    address = " · ".join(address_parts) or None
    if address in CITY_ONLY:
        address = None
    return address, years


def parse_card(card, cid_lookup, coords_by_cid, coords_by_gid) -> Listing:
    google_id = card["id"].removeprefix("pv-")
    pieces = [clean(piece) for piece in card.stripped_strings]
    pieces = [piece for piece in pieces if piece not in ("", "·", ":")]
    labels = " | ".join(tag["aria-label"] for tag in card.find_all(attrs={"aria-label": True}))

    rating_match = RATING.search(labels)
    rating = float(rating_match[1]) if rating_match else None
    reviews_count, reviews_rounded = None, False
    reviews_match = REVIEWS.search(labels)
    if reviews_match:
        reviews_count, reviews_rounded = parse_reviews(reviews_match[1], reviews_match[2])

    category, address, years = None, None, None
    price_band = next((piece for piece in pieces if piece.startswith("€")), None)
    for i, piece in enumerate(pieces):
        if piece.startswith("·"):
            category, inline_price = split_category_piece(piece)
            price_band = price_band or inline_price
            rest = [p for p in pieces[i + 1 :] if not is_status(p)]
            if rest and not rest[0].startswith("·"):
                address, years = split_address_piece(rest[0])
            break

    ancestor = card.find_parent(attrs={"data-ludocid": True})
    cid = ancestor["data-ludocid"] if ancestor else cid_lookup.get(google_id)
    lat, lng = coords_by_cid.get(cid) or coords_by_gid.get(google_id) or (None, None)

    return Listing(
        google_id=google_id,
        cid=cid,
        name=pieces[0],
        rating=rating,
        reviews_count=reviews_count,
        reviews_rounded=reviews_rounded,
        category=category,
        address=address,
        price_band=price_band,
        years_in_business=years,
        lat=lat,
        lng=lng,
    )


def parse_listings(html: str) -> list[Listing]:
    cid_lookup = {google_id: cid for cid, google_id in GOOGLE_ID_TO_CID.findall(html)}
    coords_by_cid = {cid: (float(lat), float(lng)) for cid, lat, lng in COORDS_BY_CID.findall(html)}
    coords_by_gid = coordinates_by_google_id(html)

    soup = BeautifulSoup(html, "lxml")
    return [
        parse_card(card, cid_lookup, coords_by_cid, coords_by_gid)
        for card in soup.select('div[id^="pv-/g/"]')
    ]