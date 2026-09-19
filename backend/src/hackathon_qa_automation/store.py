"""The latest score for each lead, kept as JSON files under var/scores/.

Stands in for a database. Writes are atomic (temp file then rename), so a reader
never sees a half-written score."""

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from .pipeline import LeadScore

logger = logging.getLogger(__name__)

VAR_DIR = Path(__file__).resolve().parents[2] / "var"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class ScoreStore:
    def __init__(self, directory: Path = VAR_DIR / "scores"):
        self.directory = directory

    def _path(self, lead_id: str) -> Path:
        if not _SAFE_ID.match(lead_id):
            raise ValueError(f"Unsafe lead id: {lead_id!r}")
        return self.directory / f"{lead_id}.json"

    def get(self, lead_id: str) -> Optional[LeadScore]:
        path = self._path(lead_id)
        if not path.is_file():
            return None
        try:
            return LeadScore.model_validate_json(path.read_text())
        except ValueError:
            # A stored score this code can no longer read is treated as missing, so it is re-scored.
            logger.warning("store: unreadable score for lead=%s, ignoring it", lead_id)
            return None

    def save(self, score: LeadScore) -> None:
        path = self._path(score.lead_id)
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write(score.model_dump_json(indent=2))
        os.replace(tmp, path)
        logger.info("store: saved lead=%s decision=%s", score.lead_id, score.decision)
