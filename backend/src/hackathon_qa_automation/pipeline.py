"""score_lead(): load a lead, pick the checklist version live on the call date,
run the graph, and return one result. Never raises on a scoring failure."""

import logging
import time
from datetime import date
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from strands.multiagent.base import Status

from .common.loaders import DATA_DIR, load_checklist, load_lead, load_transcript
from .graph import build_graph
from .graph.gate import Decision, decide
from .graph.nodes import VERDICTS_KEY, GateResult
from .models import CheckVerdict

logger = logging.getLogger(__name__)


class LeadScore(BaseModel):
    lead_id: str
    retailer_id: str
    call_date: date
    checklist_version: str
    decision: Decision
    reasons: list[str]
    verdicts: list[CheckVerdict]
    error: Optional[str] = None


async def score_lead(lead_id: str, data_dir: Path = DATA_DIR) -> LeadScore:
    """A failure while scoring (a model error, a timeout) never crashes and never
    auto-passes: the lead goes to HUMAN_QA, or HOLD if a check that did finish
    already found a critical fail. Missing input data is a caller error and raises."""
    started = time.perf_counter()
    lead = load_lead(lead_id, data_dir)
    segments = load_transcript(lead_id, data_dir).segments
    version = load_checklist(lead.retailer_id, data_dir).version_for(lead.call_date)

    # A fresh dict per run: nodes write their verdicts into it.
    state = {"lead": lead, "segments": segments}
    try:
        result = await build_graph(version).invoke_async(f"Lead {lead_id}.", invocation_state=state)
        if result.status != Status.COMPLETED:
            raise RuntimeError(f"Graph finished with status {result.status}")
        gate: GateResult = result.results["gate"].result
        score = LeadScore(lead_id=lead_id, retailer_id=lead.retailer_id, call_date=lead.call_date,
                          checklist_version=version.version, decision=gate.decision,
                          reasons=gate.reasons, verdicts=gate.verdicts)
    except Exception as e:
        logger.exception("Scoring failed for lead %s", lead_id)
        partial = [v for vs in state.get(VERDICTS_KEY, {}).values() for v in vs]
        held = decide(lead_id, partial).decision == "HOLD"
        score = LeadScore(lead_id=lead_id, retailer_id=lead.retailer_id, call_date=lead.call_date,
                          checklist_version=version.version,
                          decision="HOLD" if held else "HUMAN_QA",
                          reasons=["Scoring did not complete: " + ("a finished check found a critical fail"
                                                                    if held else "routed to a human")],
                          verdicts=partial, error=f"{type(e).__name__}: {e}")
    logger.info("score_lead lead=%s decision=%s in %.1fs", lead_id, score.decision,
                time.perf_counter() - started)
    return score
