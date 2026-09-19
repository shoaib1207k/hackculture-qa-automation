"""Pure-Python helpers: evidence resolution, value comparison, and the
measurable behaviour checks. No LLM calls in this module -- the model
extracts and cites, Python decides."""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from .models import MatchKind, TranscriptSegment


def segments_to_prompt_block(segments: list[TranscriptSegment]) -> str:
    return "\n".join(f"[{s.segment_id}] {s.speaker} ({s.start:.1f}-{s.end:.1f}s): {s.text}"
                     for s in segments)


# ---------------------------------------------------------------------------
# Evidence -- never trust a model-produced timestamp or segment ID.
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    start: Optional[float] = None
    end: Optional[float] = None
    text: str = ""
    unknown_ids: list[str] = field(default_factory=list)  # cited but not in the transcript


def resolve_evidence(segments: list[TranscriptSegment], segment_ids: list[str]) -> Evidence:
    by_id = {s.segment_id: s for s in segments}
    matched = [by_id[i] for i in segment_ids if i in by_id]
    unknown = [i for i in segment_ids if i not in by_id]
    if not matched:
        return Evidence(unknown_ids=unknown)
    return Evidence(start=min(s.start for s in matched), end=max(s.end for s in matched),
                    text=" / ".join(s.text for s in matched), unknown_ids=unknown)


def _squash(text: str) -> str:
    return " ".join(text.casefold().split())


def quote_is_grounded(segments: list[TranscriptSegment], segment_ids: list[str],
                      quote: Optional[str]) -> bool:
    """True only if the quote the model relied on appears verbatim (ignoring
    case and whitespace) in a segment it cited. A pass or fail is only
    trustworthy when this holds."""
    if not quote or not quote.strip():
        return False
    wanted = _squash(quote)
    return any(wanted in _squash(s.text) for s in segments if s.segment_id in segment_ids)


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
    return _squash(raw).strip(".,;:!?")


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


# ---------------------------------------------------------------------------
# Behaviour checks -- deterministic where measurable.
# ---------------------------------------------------------------------------

DEAD_AIR_THRESHOLD_S = 10.0
MAX_INTERRUPTIONS = 2


def compute_dead_air(segments: list[TranscriptSegment], threshold_s: float = DEAD_AIR_THRESHOLD_S
                     ) -> tuple[bool, float, list[str]]:
    """Returns (flagged, longest_gap_seconds, [segment_ids bounding the gap])."""
    ordered = sorted(segments, key=lambda s: s.start)
    longest, ids = 0.0, []
    for a, b in zip(ordered, ordered[1:]):
        if b.start - a.end > longest:
            longest, ids = b.start - a.end, [a.segment_id, b.segment_id]
    return longest > threshold_s, longest, ids


def compute_interruptions(segments: list[TranscriptSegment]) -> tuple[int, list[str]]:
    """Counts adjacent, different-speaker segments that overlap in time."""
    ordered = sorted(segments, key=lambda s: s.start)
    count, ids = 0, []
    for a, b in zip(ordered, ordered[1:]):
        if a.speaker != b.speaker and b.start < a.end:
            count += 1
            ids += [a.segment_id, b.segment_id]
    return count, ids
