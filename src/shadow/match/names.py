"""Normalise business names and addresses so Google places can be compared with the register."""

import re
import unicodedata

from shadow.config import AREAS, GENERIC_NAME_WORDS

LEGAL_FORMS = re.compile(
    r"\b(uzdaroji akcine bendrove|akcine bendrove|mazoji bendrija|individuali imone|"
    r"viesoji istaiga|uab|mb|ii|vsi|ab)\b"
)
NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")
STREET = re.compile(r"([a-z][a-z .-]*?\s(?:g|pr|al|pl|skg|kel)\.)\s*(\d+[a-z]?)")


def plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


IGNORED_WORDS = GENERIC_NAME_WORDS | {plain(name) for name in AREAS.values()}


def distinctive_name(name: str) -> str:
    text = LEGAL_FORMS.sub(" ", plain(name))
    words = NON_ALPHANUMERIC.sub(" ", text).split()
    return " ".join(word for word in words if word not in IGNORED_WORDS)


def street_key(address: str | None) -> str | None:
    if not address:
        return None
    match = STREET.search(plain(address))
    if not match:
        return None
    return f"{match[1].strip()} {match[2]}"