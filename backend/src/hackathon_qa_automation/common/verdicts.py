"""One place that builds a CheckVerdict, so every check type fills it the same way."""

import logging

from ..models import Check, CheckVerdict, Lead, Verdict

from .evidence import Evidence

logger = logging.getLogger(__name__)


def build_verdict(lead: Lead, check: Check, checklist_version: str, verdict: Verdict,
                  confidence: float, segment_ids: list[str], evidence: Evidence,
                  reasoning: str) -> CheckVerdict:
    logger.info("%s check=%s verdict=%s confidence=%.2f segments=%s",
                check.type, check.check_id, verdict, confidence, segment_ids)
    return CheckVerdict(
        check_id=check.check_id, check_name=check.name, check_type=check.type, critical=check.critical,
        verdict=verdict, confidence=confidence, evidence_segment_ids=segment_ids,
        timestamp_start=evidence.start, timestamp_end=evidence.end,
        evidence_text=evidence.text, reasoning=reasoning, retailer_id=lead.retailer_id,
        checklist_version=checklist_version)
