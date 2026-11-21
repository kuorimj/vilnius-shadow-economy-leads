import json
from pathlib import Path

import pytest

from shadow.extract.google_local import html_from_response, parse_listings

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    response = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return parse_listings(html_from_response(response))


@pytest.mark.parametrize(
    "name",
    [
        "google_local_kavine_vilnius_p1.json",
        "google_local_kavine_vilnius_p2.json",
        "google_local_kavine_seskine.json",
        "google_local_kavine_seskine_missing_rating.json",
    ],
)
def test_every_listing_has_ids_and_coordinates(name):
    listings = load(name)
    assert len(listings) == 20
    for listing in listings:
        assert listing.name
        assert listing.cid is not None
        assert listing.lat is not None and listing.lng is not None


def test_first_listing_fields():
    first = load("google_local_kavine_vilnius_p1.json")[0]
    assert first.name == "Etno Dvaras"
    assert first.google_id == "/g/1tdzk7fn"
    assert first.cid == "13950149882539119249"
    assert first.rating == 4.5
    assert first.reviews_count == 16000
    assert first.reviews_rounded is True
    assert first.category == "Lithuanian"
    assert first.address == "Pilies g. 16"
    assert first.price_band == "€10–20"
    assert (first.lat, first.lng) == (54.68343, 25.289381)


def test_exact_review_count_and_missing_price():
    listings = load("google_local_kavine_seskine.json")
    amigo = next(listing for listing in listings if listing.name == "UAB Amigo LT")
    assert amigo.reviews_count == 4
    assert amigo.reviews_rounded is False
    assert amigo.price_band is None
    assert amigo.address == "Šeškinės g. 26"


def test_listing_without_reviews():
    listings = load("google_local_kavine_seskine_missing_rating.json")
    bar = next(listing for listing in listings if listing.name == "BARAS - KAVINĖ STADIONAS")
    assert bar.rating is None
    assert bar.reviews_count is None
    assert bar.category == "Bar"
    assert bar.address == "Šeškinės g. 28B"