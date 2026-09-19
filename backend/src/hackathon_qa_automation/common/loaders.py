"""Read the JSON fixtures that stand in for prod stores: the CRM record and
transcript for a lead, and the check library for a retailer."""

import json
import logging
from pathlib import Path

from ..models import Checklist, Lead, Transcript

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

_LEAD_HEADER = ("lead_id", "retailer_id", "call_date")


def load_lead(lead_id: str, data_dir: Path = DATA_DIR) -> Lead:
    raw = json.loads((data_dir / "leads" / lead_id / "crm.json").read_text())
    logger.info("load_lead lead=%s retailer=%s call_date=%s fields=%d",
                lead_id, raw["retailer_id"], raw["call_date"], len(raw) - len(_LEAD_HEADER))
    return Lead(**{k: raw[k] for k in _LEAD_HEADER},
                fields={k: v for k, v in raw.items() if k not in _LEAD_HEADER})


def load_transcript(lead_id: str, data_dir: Path = DATA_DIR) -> Transcript:
    transcript = Transcript.model_validate_json(
        (data_dir / "leads" / lead_id / "transcript.json").read_text())
    logger.info("load_transcript lead=%s segments=%d duration=%.0fs", lead_id,
                len(transcript.segments), max((s.end for s in transcript.segments), default=0))
    return transcript


def load_checklist(retailer_id: str, data_dir: Path = DATA_DIR) -> Checklist:
    checklist = Checklist.model_validate_json(
        (data_dir / "retailers" / retailer_id / "checklist.json").read_text())
    logger.info("load_checklist retailer=%s versions=%s", retailer_id,
                [v.version for v in checklist.versions])
    return checklist


def list_lead_ids(data_dir: Path = DATA_DIR) -> list[str]:
    """Leads that have both a CRM record and a transcript."""
    leads = data_dir / "leads"
    if not leads.is_dir():
        return []
    return sorted(p.name for p in leads.iterdir()
                  if (p / "crm.json").is_file() and (p / "transcript.json").is_file())
