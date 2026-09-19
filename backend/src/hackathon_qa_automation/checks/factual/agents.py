"""Strands agents. Each one extracts and cites; Python decides."""

import logging
import time

from strands import Agent

from ...common.evidence import segments_to_prompt_block
from ...common.prompts import TRANSCRIPT_RULES
from ...llm import build_model
from ...models import Check, TranscriptSegment
from .schemas import FactualComparison, FactualExtraction

logger = logging.getLogger(__name__)

# Reasoning effort per agent. Extraction and comparison are lookups against short
# inputs: "none" is fastest, cites tighter evidence, and passed the same tests as
# "low". Raise an agent's effort only where a test shows it helps.
EXTRACTION_EFFORT = "none"
COMPARISON_EFFORT = "none"

FACTUAL_PROMPT = (
    "You extract facts spoken on a sales call so they can be compared with CRM data. "
    "You do NOT decide whether a fact is correct, and you never see the CRM value.\n"
    "You are given ONE field, described precisely. Extract exactly that field:\n"
    "- Never substitute a related field. If the field is the connection address, do not "
    "return the delivery address; if it is the introductory price, do not return the "
    "regular price; if it is the modem's upfront cost, do not return the plan price. The "
    "description says what the field is NOT; obey it.\n"
    "- Prefer what the AGENT read out or confirmed for that field. A customer's aside about "
    "something else does not count as confirming this field.\n"
    "- Report the FINAL value for THAT field. If it was corrected later, use the corrected "
    "value.\n"
    "- If the field was never stated, return null. Do not infer it from a related field.\n"
    "- Transcribe exactly as spoken. Keep number words as words. Do not fix typos, do not "
    "complete a partial value, do not convert formats.\n"
    "- The quote must contain the value itself, copied character for character.\n"
    "- Cite the ONE segment where that final value was stated or confirmed: exactly one "
    "segment ID, unless the value itself is split across consecutive turns. Do not list "
    "every segment that mentions it; a person will jump to that timestamp to hear it.\n"
    + TRANSCRIPT_RULES)


def build_factual_agent() -> Agent:
    return Agent(name="factual_extraction", model=build_model(EXTRACTION_EFFORT),
                 system_prompt=FACTUAL_PROMPT, callback_handler=None)


async def extract_factual(segments: list[TranscriptSegment], check: Check) -> FactualExtraction:
    logger.info("extract_factual start check=%s segments=%d", check.check_id, len(segments))
    started = time.perf_counter()
    # A fresh agent per call: an Agent keeps its message history, which would
    # otherwise leak one check's transcript and answer into the next.
    try:
        result = await build_factual_agent().invoke_async(
            f"Transcript:\n{segments_to_prompt_block(segments)}\n\n---\n"
            f"check_id={check.check_id}\nFind the final value for: {check.description}.",
            structured_output_model=FactualExtraction)
    except Exception:
        logger.exception("extract_factual failed check=%s after %.1fs",
                         check.check_id, time.perf_counter() - started)
        raise
    out = result.structured_output
    logger.info("extract_factual done check=%s found=%s confidence=%.2f segments=%s in %.1fs",
                check.check_id, out.value is not None, out.confidence, out.segment_ids,
                time.perf_counter() - started)
    logger.debug("extract_factual check=%s value=%r quote=%r reasoning=%s",
                 check.check_id, out.value, out.quote, out.reasoning)
    return out


# ---------------------------------------------------------------------------
# Comparison -- spoken value vs CRM value. This agent never sees the transcript
# (and the extraction agent never sees the CRM value), so neither can be
# nudged toward a match.
# ---------------------------------------------------------------------------

COMPARISON_PROMPT = (
    "You compare a value spoken on a sales call with the value recorded in the CRM, and "
    "decide whether they state the SAME fact. You are a strict auditor: a wrong 'match' "
    "lets a bad sale through.\n"
    "These differences do NOT change the fact: number words vs digits ('forty two dollars "
    "and ninety' = 42.90), currency and unit formatting ('$42.90', '42.90 AUD'), cents vs "
    "dollars for the same amount, 'free' / 'no extra cost' / 'zero dollars upfront' = 0.00, "
    "upper/lower case, punctuation, spoken 'dot' / 'at' in an email, digits spoken one by "
    "one, and standard abbreviations (Dr = Drive, St = Street).\n"
    "Everything else IS a mismatch, including: a different number or amount; a single "
    "wrong, missing, extra or transposed character in an email, name or ID (never excuse it "
    "as a typo or transcription error -- the customer's record must be exactly right); a "
    "part present on one side and missing on the other (unit number, postcode, suburb).\n"
    "If you cannot tell whether two values are the same fact, answer 'uncertain'. "
    "Never guess a 'match'.")


def build_comparison_agent() -> Agent:
    return Agent(name="factual_comparison", model=build_model(COMPARISON_EFFORT),
                 system_prompt=COMPARISON_PROMPT, callback_handler=None)


async def compare_factual(spoken: str, crm: str, check: Check) -> FactualComparison:
    logger.info("compare_factual start check=%s", check.check_id)
    logger.debug("compare_factual check=%s spoken=%r crm=%r", check.check_id, spoken, crm)
    started = time.perf_counter()
    try:
        result = await build_comparison_agent().invoke_async(
            f"Field: {(check.crm_field or check.check_id).replace('_', ' ')}\n"
            f"Spoken on the call: {spoken}\nRecorded in CRM: {crm}",
            structured_output_model=FactualComparison)
    except Exception:
        logger.exception("compare_factual failed check=%s after %.1fs",
                         check.check_id, time.perf_counter() - started)
        raise
    out = result.structured_output
    logger.info("compare_factual done check=%s verdict=%s confidence=%.2f in %.1fs",
                check.check_id, out.verdict, out.confidence, time.perf_counter() - started)
    logger.debug("compare_factual check=%s reasoning=%s", check.check_id, out.reasoning)
    return out
