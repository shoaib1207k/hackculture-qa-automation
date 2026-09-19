"""Response shapes the frontend reads."""

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel

from ..models import TranscriptSegment
from ..pipeline import LeadScore


class LeadSummary(BaseModel):
    lead_id: str
    customer_name: Optional[str]
    retailer_id: str
    call_date: date
    score: Optional[LeadScore]  # the latest saved score, or null if never scored


class LeadDetail(LeadSummary):
    crm: dict[str, Any]
    transcript: list[TranscriptSegment]  # card numbers already redacted
