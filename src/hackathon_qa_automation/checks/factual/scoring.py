"""Factual checks: transcript vs a CRM field.

Extraction agent (never sees the CRM value) -> Python grounds the quote and
resolves real timestamps -> comparison agent (never sees the transcript) ->
verdict. Anything the model cannot back with a real, quoted transcript line is
"uncertain", never an automatic pass or fail."""

import asyncio
import logging

from .agents import compare_factual, extract_factual
from ...common.evidence import quote_is_grounded, resolve_evidence
from ...common.verdicts import build_verdict
from ...models import Check, CheckVerdict, Lead, TranscriptSegment, Verdict

logger = logging.getLogger(__name__)

_VERDICT = {"match": "pass", "mismatch": "fail", "uncertain": "uncertain"}


async def score_factual_check(segments: list[TranscriptSegment], lead: Lead, check: Check,
                              checklist_version: str) -> CheckVerdict:
    def verdict(result: Verdict, confidence: float, segment_ids: list[str], evidence,
                reasoning: str) -> CheckVerdict:
        return build_verdict(lead, check, checklist_version, result, confidence, segment_ids,
                             evidence, reasoning)

    empty = resolve_evidence(segments, [])
    crm_value = lead.fields.get(check.crm_field)
    if crm_value is None:
        logger.warning("factual check=%s CRM has no value for %r", check.check_id, check.crm_field)
        return verdict("uncertain", 0.0, [], empty,
                       f"CRM has no value for {check.crm_field!r}; nothing to compare against")

    extraction = await extract_factual(segments, check)
    evidence = resolve_evidence(segments, extraction.segment_ids)
    if extraction.value is None:
        return verdict("uncertain", 0.0, extraction.segment_ids, evidence,
                       f"The value was not stated on the call. {extraction.reasoning}")
    if evidence.unknown_ids or not quote_is_grounded(segments, extraction.segment_ids,
                                                     extraction.quote):
        return verdict("uncertain", 0.0, extraction.segment_ids, evidence,
                       "The model's cited evidence could not be found in the transcript, "
                       f"so its answer was not trusted. {extraction.reasoning}")

    comparison = await compare_factual(extraction.value, str(crm_value), check)
    return verdict(_VERDICT[comparison.verdict],
                   min(extraction.confidence, comparison.confidence),
                   extraction.segment_ids, evidence,
                   f"Spoken {extraction.value!r} vs CRM {crm_value!r}: {comparison.verdict}. "
                   f"{comparison.reasoning}")


async def run_factual_checks(segments: list[TranscriptSegment], lead: Lead, checks: list[Check],
                             checklist_version: str) -> list[CheckVerdict]:
    logger.info("factual start lead=%s checks=%d", lead.lead_id, len(checks))
    return list(await asyncio.gather(
        *(score_factual_check(segments, lead, c, checklist_version) for c in checks)))
