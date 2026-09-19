"""Pydantic schemas: transcript, lead, checklist, and the final verdict."""

import logging
from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

CheckType = Literal["verbatim", "factual", "behaviour"]
Verdict = Literal["pass", "fail", "uncertain"]
# How a factual check normalises a spoken value before comparing it to CRM.
MatchKind = Literal["money", "email", "phone", "address", "text"]


# ---------------------------------------------------------------------------
# Transcript -- structured, timestamped segments. The model cites evidence by
# segment_id; Python resolves the real time. Word-level timing is optional
# because the fixture is turn-level, but a real transcription API returns it.
# ---------------------------------------------------------------------------

class Word(BaseModel):
    text: str
    start: float
    end: float


class TranscriptSegment(BaseModel):
    segment_id: str
    speaker: Literal["AGENT", "CUSTOMER"]
    start: float  # seconds
    end: float
    text: str
    words: list[Word] = Field(default_factory=list)


class Transcript(BaseModel):
    segments: list[TranscriptSegment]


# ---------------------------------------------------------------------------
# Lead -- the CRM record the transcript is checked against.
# ---------------------------------------------------------------------------

class Lead(BaseModel):
    lead_id: str
    retailer_id: str
    call_date: date
    fields: dict[str, Any]  # everything else in crm.json, keyed by CRM field name


# ---------------------------------------------------------------------------
# Checklist -- per retailer, versioned. A call is scored against the version
# whose effective_from is the latest one on or before the call date.
# ---------------------------------------------------------------------------

class Check(BaseModel):
    check_id: str
    description: str = ""
    type: CheckType
    critical: bool = False
    required_elements: list[str] = Field(default_factory=list)  # verbatim
    crm_field: Optional[str] = None  # factual
    match: MatchKind = "text"  # factual

    @model_validator(mode="after")
    def _validate(self) -> "Check":
        # Fail at load time, not per lead, on checklist config errors.
        if self.type != "behaviour" and "critical" not in self.model_fields_set:
            raise ValueError(f"Check {self.check_id!r} must set critical")
        if self.type == "verbatim" and not self.required_elements:
            raise ValueError(f"Verbatim check {self.check_id!r} has no required_elements")
        if self.type == "factual" and not self.crm_field:
            raise ValueError(f"Factual check {self.check_id!r} has no crm_field")
        return self


class ChecklistVersion(BaseModel):
    version: str
    effective_from: date
    checks: list[Check]

    @model_validator(mode="before")
    @classmethod
    def _checks_from_mapping(cls, data: Any) -> Any:
        # The JSON keys checks by id; the model wants the id on each check.
        if isinstance(data, dict) and isinstance(data.get("checks"), dict):
            data = {**data, "checks": [{"check_id": k, **v} for k, v in data["checks"].items()]}
        return data


class Checklist(BaseModel):
    retailer_id: str
    versions: list[ChecklistVersion]

    def version_for(self, call_date: date) -> ChecklistVersion:
        """The version that was live on the call date -- not the latest one."""
        live = [v for v in self.versions if v.effective_from <= call_date]
        if not live:
            raise ValueError(f"No checklist version for {self.retailer_id} was effective on {call_date}")
        chosen = max(live, key=lambda v: v.effective_from)
        logger.info("version_for retailer=%s call_date=%s -> %s (effective %s, %d checks)",
                    self.retailer_id, call_date, chosen.version, chosen.effective_from,
                    len(chosen.checks))
        return chosen


# ---------------------------------------------------------------------------
# The verdict -- every score resolves to a transcript line, a timestamp and
# the checklist version that was live on the call date.
# ---------------------------------------------------------------------------

class CheckVerdict(BaseModel):
    check_id: str
    check_type: CheckType
    critical: bool
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_segment_ids: list[str]
    timestamp_start: Optional[float]
    timestamp_end: Optional[float]
    evidence_text: str
    reasoning: str
    retailer_id: str
    checklist_version: str
