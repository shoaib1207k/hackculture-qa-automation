"""Verbatim checks: transcript vs what the agent must say.

PLACEHOLDER until the verbatim agent is built. It marks every check
"uncertain", so the gate can never auto-pass a call whose required
statements have not actually been checked."""

import logging

from ...common.evidence import resolve_evidence
from ...common.verdicts import build_verdict
from ...models import Check, CheckVerdict, Lead, TranscriptSegment

logger = logging.getLogger(__name__)


async def run_verbatim_checks(segments: list[TranscriptSegment], lead: Lead, checks: list[Check],
                              checklist_version: str) -> list[CheckVerdict]:
    logger.warning("verbatim placeholder: %d checks marked uncertain", len(checks))
    return [build_verdict(lead, c, checklist_version, "uncertain", 0.0, [],
                          resolve_evidence(segments, []),
                          "Verbatim evaluation is not built yet; routed to a human")
            for c in checks]
