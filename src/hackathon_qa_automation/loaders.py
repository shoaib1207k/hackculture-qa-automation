"""Read the JSON fixtures that stand in for prod stores: the CRM record and
transcript for a lead, and the check library for a retailer."""

import json
from pathlib import Path

from .models import Checklist, Lead, Transcript

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_LEAD_HEADER = ("lead_id", "retailer_id", "call_date")


def load_lead(lead_id: str, data_dir: Path = DATA_DIR) -> Lead:
    raw = json.loads((data_dir / "leads" / lead_id / "crm.json").read_text())
    return Lead(**{k: raw[k] for k in _LEAD_HEADER},
                fields={k: v for k, v in raw.items() if k not in _LEAD_HEADER})


def load_transcript(lead_id: str, data_dir: Path = DATA_DIR) -> Transcript:
    return Transcript.model_validate_json(
        (data_dir / "leads" / lead_id / "transcript.json").read_text())


def load_checklist(retailer_id: str, data_dir: Path = DATA_DIR) -> Checklist:
    return Checklist.model_validate_json(
        (data_dir / "retailers" / retailer_id / "checklist.json").read_text())
