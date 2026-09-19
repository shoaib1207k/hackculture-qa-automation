"""Behaviour checks: transcript only. Measurable signals are computed from the
timestamps, not judged by a model."""

import logging

from ...common.evidence import resolve_evidence
from ...common.verdicts import build_verdict
from ...models import Check, CheckVerdict, Lead, TranscriptSegment
from .metrics import (DEAD_AIR_THRESHOLD_S, MAX_INTERRUPTIONS, compute_dead_air,
                      compute_interruptions)

logger = logging.getLogger(__name__)


def run_behaviour_checks(segments: list[TranscriptSegment], lead: Lead, checks: list[Check],
                         checklist_version: str) -> list[CheckVerdict]:
    logger.info("behaviour start lead=%s checks=%d", lead.lead_id, len(checks))
    verdicts = []
    for check in checks:
        if check.check_id == "dead_air":
            flagged, gap, ids = compute_dead_air(segments)
            reasoning = f"Longest silence {gap:.1f}s (limit {DEAD_AIR_THRESHOLD_S:.0f}s)"
        elif check.check_id == "interruptions":
            count, ids = compute_interruptions(segments)
            flagged = count > MAX_INTERRUPTIONS
            reasoning = f"{count} overlapping turns (limit {MAX_INTERRUPTIONS})"
        else:
            logger.warning("behaviour check=%s has no evaluator", check.check_id)
            verdicts.append(build_verdict(lead, check, checklist_version, "uncertain", 0.0, [],
                                          resolve_evidence(segments, []),
                                          "No evaluator exists for this behaviour check yet"))
            continue
        verdicts.append(build_verdict(lead, check, checklist_version,
                                      "fail" if flagged else "pass", 1.0, ids,
                                      resolve_evidence(segments, ids), reasoning))
    return verdicts
