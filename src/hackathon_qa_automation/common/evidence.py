"""Evidence handling: never trust a model-produced timestamp or segment ID.
Pure Python, no LLM calls."""

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..models import TranscriptSegment

logger = logging.getLogger(__name__)


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
    if unknown:
        logger.warning("resolve_evidence model cited segments that do not exist: %s", unknown)
    if not matched:
        return Evidence(unknown_ids=unknown)
    evidence = Evidence(start=min(s.start for s in matched), end=max(s.end for s in matched),
                        text=" / ".join(s.text for s in matched), unknown_ids=unknown)
    logger.debug("resolve_evidence ids=%s -> %.1f-%.1fs", segment_ids, evidence.start, evidence.end)
    return evidence


def squash(text: str) -> str:
    return " ".join(text.casefold().split())


def quote_is_grounded(segments: list[TranscriptSegment], segment_ids: list[str],
                      quote: Optional[str]) -> bool:
    """True only if the quote the model relied on appears verbatim (ignoring
    case and whitespace) in a segment it cited. A pass or fail is only
    trustworthy when this holds."""
    if not quote or not quote.strip():
        logger.warning("quote_is_grounded no quote given for segments=%s", segment_ids)
        return False
    wanted = squash(quote)
    grounded = any(wanted in squash(s.text) for s in segments if s.segment_id in segment_ids)
    if not grounded:
        logger.warning("quote_is_grounded quote NOT found in cited segments=%s", segment_ids)
    else:
        logger.debug("quote_is_grounded ok segments=%s", segment_ids)
    return grounded
