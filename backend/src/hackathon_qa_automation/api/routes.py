"""HTTP endpoints. The API triggers the workflow and serves what the UI needs;
all scoring lives in pipeline.score_lead()."""

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from ..common.loaders import list_lead_ids, load_lead, load_transcript
from ..common.redaction import redact_segments
from ..pipeline import LeadScore, score_lead
from ..store import ScoreStore
from .redaction import redact_score
from .schemas import LeadDetail, LeadSummary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# The lead id becomes part of a file path, so keep it to a safe alphabet.
LeadId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="Lead ID")]

_store = ScoreStore()


def get_store() -> ScoreStore:
    return _store


def _require_lead(lead_id: str) -> None:
    if lead_id not in list_lead_ids():
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")


def _saved_score(store: ScoreStore, lead_id: str):
    saved = store.get(lead_id)
    return redact_score(saved) if saved else None


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/leads", response_model=list[LeadSummary])
async def leads(store: ScoreStore = Depends(get_store)) -> list[LeadSummary]:
    """Every lead, each with its latest saved score, or null until it has been processed."""
    summaries = []
    for lead_id in list_lead_ids():
        lead = load_lead(lead_id)
        summaries.append(LeadSummary(
            lead_id=lead_id, customer_name=lead.fields.get("customer_name"),
            retailer_id=lead.retailer_id, call_date=lead.call_date,
            score=_saved_score(store, lead_id)))
    return summaries


@router.get("/leads/{lead_id}", response_model=LeadDetail)
async def lead_detail(lead_id: LeadId, store: ScoreStore = Depends(get_store)) -> LeadDetail:
    """The CRM record, the transcript (card numbers redacted) and the latest score."""
    _require_lead(lead_id)
    lead = load_lead(lead_id)
    return LeadDetail(
        lead_id=lead_id, customer_name=lead.fields.get("customer_name"),
        retailer_id=lead.retailer_id, call_date=lead.call_date, crm=lead.fields,
        transcript=redact_segments(load_transcript(lead_id).segments),
        score=_saved_score(store, lead_id))


@router.post("/leads/{lead_id}/score", response_model=LeadScore)
async def score(lead_id: LeadId, force: bool = False,
                store: ScoreStore = Depends(get_store)) -> LeadScore:
    """Run the QA workflow for one lead and return the decision with every check.

    Returns the saved score if there is one, unless `force=true` re-runs it. A
    scoring failure (a model error, a timeout) is not an HTTP error: the lead
    comes back as HUMAN_QA (or HOLD) with `error` set, is never auto-passed, and
    is not saved, so the next request tries again.
    """
    _require_lead(lead_id)
    if not force and (saved := _saved_score(store, lead_id)):
        logger.info("POST score lead=%s -> saved score (%s)", lead_id, saved.decision)
        return saved
    logger.info("POST score lead=%s force=%s", lead_id, force)
    started = time.perf_counter()
    result = await score_lead(lead_id)
    if not result.error:
        store.save(result)
    logger.info("POST score lead=%s decision=%s in %.1fs", lead_id, result.decision,
                time.perf_counter() - started)
    return redact_score(result)
