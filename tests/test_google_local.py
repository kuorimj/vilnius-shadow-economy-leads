import json
from pathlib import Path

import pytest

from shadow.extract.google_local import html_from_response, parse_listings

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    response = data.get("response", data)
    return parse_listings(html_from_response(response))


@pytest.mark.parametrize(
    "name",
    [
        "google_local_kavine_vilnius_p1.json",
        "google_local_kavine_vilnius_p2.json",
        "google_local_kavine_seskine.json",
        "google_local_kavine_seskine_missing_rating.json",
        "google_local_layout_b_kavine_zirmunai.json",
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

def test_layout_b_card():
    listings = load("google_local_layout_b_kavine_zirmunai.json")
    pavlova = listings[0]
    assert pavlova.name == "Pavlova"
    assert pavlova.cid == "4993125732187605076"
    assert pavlova.rating == 4.6
    assert pavlova.reviews_count == 254
    assert pavlova.category == "Dessert"
    assert pavlova.price_band == "€10–15"
    assert pavlova.address == "Šiaurės miestelis"
    assert (pavlova.lat, pavlova.lng) == (54.714132, 25.29554)


def test_layout_b_keeps_branches_apart():
    branches = [listing for listing in load("google_local_layout_b_kavine_zirmunai.json") if listing.name == "Etno Dvaras"]
    assert len({branch.cid for branch in branches}) == 2
    assert {branch.address for branch in branches} == {"Šiaurės miestelis", "Pilies g. 16"}
    main = next(branch for branch in branches if branch.address == "Pilies g. 16")
    assert main.reviews_count == 15900
    assert main.reviews_rounded is True


def test_service_area_business_without_street_address():
    listings = load("google_local_autoservisas_zverynas.json")
    first = listings[0]
    assert first.category == "Car repair and maintenance service"
    assert first.address is None
    assert first.years_in_business == 7
    assert first.lat is not None


def test_listing_without_address_or_location():
    listings = load("google_local_autoservisas_zverynas.json")
    closed = next(listing for listing in listings if listing.name.startswith("Autoelektrikas Zacharov"))
    assert closed.category == "BMW dealer"
    assert closed.address is None
    assert closed.lat is None