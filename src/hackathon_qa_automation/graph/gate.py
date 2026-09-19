"""The gate: a hard business rule, no LLM. Nothing uncertain auto-passes."""

import hashlib
import logging
from typing import Literal

from pydantic import BaseModel

from ..models import CheckVerdict

logger = logging.getLogger(__name__)

Decision = Literal["HOLD", "HUMAN_QA", "AUTO_PASS"]

CONFIDENCE_THRESHOLD = 0.75
CLEAN_CALL_SAMPLE_RATE = 0.05


class GateDecision(BaseModel):
    decision: Decision
    reasons: list[str]


def sampled_for_qa(lead_id: str, rate: float = CLEAN_CALL_SAMPLE_RATE) -> bool:
    """Deterministic per lead, so a re-score of the same lead never flips."""
    bucket = int(hashlib.sha256(lead_id.encode()).hexdigest(), 16) % 10_000
    sampled = bucket < rate * 10_000
    logger.debug("sampled_for_qa lead=%s bucket=%d rate=%.2f -> %s", lead_id, bucket, rate, sampled)
    return sampled


def _decided(lead_id: str, decision: Decision, reasons: list[str]) -> GateDecision:
    logger.info("gate lead=%s decision=%s reasons=%s", lead_id, decision, reasons)
    return GateDecision(decision=decision, reasons=reasons)


def decide(lead_id: str, verdicts: list[CheckVerdict],
           sample_rate: float = CLEAN_CALL_SAMPLE_RATE) -> GateDecision:
    critical_fails = [v.check_id for v in verdicts if v.critical and v.verdict == "fail"]
    if critical_fails:
        return _decided(lead_id, "HOLD", [f"critical fail: {c}" for c in critical_fails])

    unresolved = [v.check_id for v in verdicts
                  if v.verdict == "uncertain" or v.confidence < CONFIDENCE_THRESHOLD]
    if unresolved:
        return _decided(lead_id, "HUMAN_QA",
                        [f"uncertain or low confidence: {c}" for c in unresolved])

    if sampled_for_qa(lead_id, sample_rate):
        return _decided(lead_id, "HUMAN_QA", ["clean call sampled for human review"])
    return _decided(lead_id, "AUTO_PASS", ["all critical checks passed"])
