"""Verbatim checks: did the agent convey each required statement?

The agent extracts and cites; Python then requires that the cited words really
are in the transcript AND were spoken by the agent. Consent is a check, not an
assumption, so anything the model cannot back with a real, quoted agent line is
"uncertain" -- never an automatic pass."""

import asyncio
import logging

from ...common.evidence import quote_is_grounded, resolve_evidence
from ...common.verdicts import build_verdict
from ...models import Check, CheckVerdict, Lead, TranscriptSegment
from .agents import extract_verbatim

logger = logging.getLogger(__name__)


def _key(text: str) -> str:
    return " ".join(text.casefold().split())


async def score_verbatim_check(segments: list[TranscriptSegment], lead: Lead, check: Check,
                               checklist_version: str) -> CheckVerdict:
    extraction = await extract_verbatim(segments, check)
    by_key = {_key(r.element): r for r in extraction.elements}
    results = [(e, by_key.get(_key(e))) for e in check.required_elements]
    speaker = {s.segment_id: s.speaker for s in segments}

    all_ids = [i for _, r in results if r for i in r.segment_ids]
    evidence = resolve_evidence(segments, all_ids)

    problems, missing = [], []
    for element, r in results:
        if r is None:
            problems.append(f"{element!r} was not assessed by the model")
        elif not r.present:
            missing.append(element)
        elif (per_element := resolve_evidence(segments, r.segment_ids)).unknown_ids or \
                not quote_is_grounded(segments, r.segment_ids, r.quote):
            problems.append(f"{element!r}: the cited words were not found in the transcript")
        elif any(speaker[i] != "AGENT" for i in r.segment_ids):
            problems.append(f"{element!r}: the cited words were not spoken by the agent")

    def verdict(result, confidence, reasoning):
        return build_verdict(lead, check, checklist_version, result, confidence, all_ids,
                             evidence, reasoning)

    if problems:
        logger.warning("verbatim check=%s evidence not trusted: %s", check.check_id, problems)
        return verdict("uncertain", 0.0,
                       f"The model's evidence was not trusted: {'; '.join(problems)}. "
                       f"{extraction.reasoning}")

    confidence = min(r.confidence for _, r in results)
    if missing:
        return verdict("fail", confidence,
                       f"Not conveyed by the agent: {missing}. {extraction.reasoning}")
    return verdict("pass", confidence,
                   f"All required elements were conveyed by the agent. {extraction.reasoning}")


async def run_verbatim_checks(segments: list[TranscriptSegment], lead: Lead, checks: list[Check],
                              checklist_version: str) -> list[CheckVerdict]:
    logger.info("verbatim start lead=%s checks=%d", lead.lead_id, len(checks))
    return list(await asyncio.gather(
        *(score_verbatim_check(segments, lead, c, checklist_version) for c in checks)))
