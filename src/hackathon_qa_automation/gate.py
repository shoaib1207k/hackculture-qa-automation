"""The gate: a hard business rule, no LLM. Nothing uncertain auto-passes."""

import hashlib
from typing import Literal

from pydantic import BaseModel

from .models import CheckVerdict

Decision = Literal["HOLD", "HUMAN_QA", "AUTO_PASS"]

CONFIDENCE_THRESHOLD = 0.75
CLEAN_CALL_SAMPLE_RATE = 0.05


class GateDecision(BaseModel):
    decision: Decision
    reasons: list[str]


def sampled_for_qa(lead_id: str, rate: float = CLEAN_CALL_SAMPLE_RATE) -> bool:
    """Deterministic per lead, so a re-score of the same lead never flips."""
    bucket = int(hashlib.sha256(lead_id.encode()).hexdigest(), 16) % 10_000
    return bucket < rate * 10_000


def decide(lead_id: str, verdicts: list[CheckVerdict],
           sample_rate: float = CLEAN_CALL_SAMPLE_RATE) -> GateDecision:
    critical_fails = [v.check_id for v in verdicts if v.critical and v.verdict == "fail"]
    if critical_fails:
        return GateDecision(decision="HOLD",
                            reasons=[f"critical fail: {c}" for c in critical_fails])

    unresolved = [v.check_id for v in verdicts
                  if v.verdict == "uncertain" or v.confidence < CONFIDENCE_THRESHOLD]
    if unresolved:
        return GateDecision(decision="HUMAN_QA",
                            reasons=[f"uncertain or low confidence: {c}" for c in unresolved])

    if sampled_for_qa(lead_id, sample_rate):
        return GateDecision(decision="HUMAN_QA", reasons=["clean call sampled for human review"])
    return GateDecision(decision="AUTO_PASS", reasons=["all critical checks passed"])
