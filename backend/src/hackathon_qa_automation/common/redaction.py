"""Guardrail: a spoken card number must never reach the transcript view.

Redaction is deliberately over-eager: any run of 13-19 digits (spaces and dashes
allowed between them) is masked, whether or not it passes a card checksum, because
a mistyped or mis-transcribed card number still must not be shown. Card numbers
spoken as words ("four two four two ...") are not caught by this."""

import re

from ..models import TranscriptSegment

CARD_PLACEHOLDER = "[CARD NUMBER REDACTED]"
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def redact_card_numbers(text: str) -> str:
    return _CARD.sub(CARD_PLACEHOLDER, text)


def redact_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    return [s.model_copy(update={"text": redact_card_numbers(s.text), "words": []})
            for s in segments]
