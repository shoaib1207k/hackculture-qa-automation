"""Redaction of a whole score before it leaves the API."""

from ..common.redaction import redact_card_numbers
from ..pipeline import LeadScore


def redact_score(score: LeadScore) -> LeadScore:
    """The evidence text and reasoning quote the transcript, so they are redacted too."""
    return score.model_copy(update={"verdicts": [
        v.model_copy(update={"evidence_text": redact_card_numbers(v.evidence_text),
                             "reasoning": redact_card_numbers(v.reasoning)})
        for v in score.verdicts]})
