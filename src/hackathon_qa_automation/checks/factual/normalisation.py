"""PARKED: rule-based value normalisation. Nothing calls this yet -- factual
comparison is done by the comparison agent. Kept for the last step, when we
decide whether any of it should move back into code."""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from ...common.evidence import squash
from ...models import MatchKind


# ---------------------------------------------------------------------------
# Value normalisation -- for factual checks the LLM extracts a spoken value
# and Python decides equality. Real typos (gmial vs gmail) must still fail.
# ---------------------------------------------------------------------------

_ZERO_WORDS = {"free", "zero", "nothing", "no cost", "no charge"}
_MONEY = re.compile(
    r"^\$?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>¢|c|cents?|dollars?|aud)?"
    r"\s*(?:(?:/|per)\s*(?:kwh|day|month|mo))?\s*(?:aud)?$")


def _money(raw: str) -> Optional[Decimal]:
    """Dollars as a Decimal. Cents ("31.9c/kWh") are converted so they compare
    equal to their dollar form ("$0.319")."""
    v = raw.strip().casefold()
    if v in _ZERO_WORDS:
        return Decimal(0)
    m = _MONEY.match(v)
    if not m:
        return None
    try:
        amount = Decimal(m.group("num").replace(",", ""))
    except InvalidOperation:
        return None
    return amount / 100 if m.group("unit") in ("¢", "c", "cent", "cents") else amount


def _email(raw: str) -> str:
    v = raw.strip().casefold()
    if "@" not in v:  # spoken form: "sarah dot mitchell at example dot com"
        v = re.sub(r"\s+dot\s+", ".", v)
        v = re.sub(r"\s+at\s+", "@", v)
        v = re.sub(r"\s+underscore\s+", "_", v)
    return re.sub(r"\s+", "", v)


def _phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return "0" + digits[2:] if digits.startswith("61") else digits  # +61 4.. == 04..


_STREET_TYPES = {"drive": "dr", "street": "st", "road": "rd", "avenue": "ave",
                 "court": "ct", "place": "pl", "lane": "ln", "crescent": "cres"}


def _address(raw: str) -> str:
    tokens = re.sub(r"[^\w\s/]", " ", raw.casefold()).split()
    return " ".join(_STREET_TYPES.get(t, t) for t in tokens)


def _text(raw: str) -> str:
    return squash(raw).strip(".,;:!?")


def values_match(kind: MatchKind, spoken: Optional[str], crm: Optional[str]) -> bool:
    """Missing on either side is never a match. Unparseable money never
    matches either, so a garbled value cannot slip through as a pass."""
    if spoken is None or crm is None:
        return False
    if kind == "money":
        a, b = _money(str(spoken)), _money(str(crm))
        return a is not None and b is not None and a == b
    normalise = {"email": _email, "phone": _phone, "address": _address, "text": _text}[kind]
    return normalise(str(spoken)) == normalise(str(crm))
