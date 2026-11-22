from shadow.match.names import distinctive_name, street_key
from shadow.match.places import Candidate, activity_fits, decide


def test_distinctive_name_drops_legal_forms_generic_words_and_accents():
    assert distinctive_name('Uždaroji akcinė bendrovė "MELGA"') == "melga"
    assert distinctive_name("Autoservisas AUTOVELA Vilniuje") == "autovela"
    assert distinctive_name('UAB "UŽUPIO KAVINĖ"') == "uzupio"
    assert distinctive_name("Užupio kavinė") == "uzupio"


def test_neighbourhood_names_are_not_distinctive():
    assert distinctive_name("Barber Justiniškės") == ""
    assert distinctive_name('Uždaroji akcinė bendrovė "JUSTINIŠKĖS"') == ""


def test_street_key_reads_register_and_google_addresses_the_same_way():
    assert street_key("Vilnius, Pilies g. 16-3, LT-01123") == "pilies g. 16"
    assert street_key("Pilies g. 16") == "pilies g. 16"
    assert street_key("Vilnius, S. Stanevičiaus g. 95, LT-07114") == "s. staneviciaus g. 95"
    assert street_key("Gedimino pr. 9") == "gedimino pr. 9"
    assert street_key("Šiaurės miestelis") is None
    assert street_key(None) is None


def test_activity_fits_category():
    assert activity_fits(["cafe_restaurant"], "56.11.00")
    assert activity_fits(["hair_beauty"], "96.22.00")
    assert not activity_fits(["cafe_restaurant"], "68.20.00")
    assert not activity_fits(["car_repair"], None)


def candidate(code, fits=False, address=False):
    return Candidate(company_code=code, name_similarity=1.0, activity_fits=fits, same_address=address)


def test_decide_outcomes():
    assert decide([]) == ("unmatched", None)
    assert decide([candidate("1", fits=True)]) == ("confirmed", candidate("1", fits=True))
    assert decide([candidate("1", address=True)])[0] == "confirmed"
    assert decide([candidate("1")]) == ("possible", candidate("1"))
    assert decide([candidate("1"), candidate("2")]) == ("ambiguous", None)


def test_second_signal_resolves_several_candidates():
    status, chosen = decide([candidate("1"), candidate("2", fits=True)])
    assert status == "confirmed"
    assert chosen.company_code == "2"


def test_two_confirmed_candidates_stay_ambiguous():
    assert decide([candidate("1", fits=True), candidate("2", fits=True)]) == ("ambiguous", None)