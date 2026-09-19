"""Strands agent for verbatim checks. It extracts and cites; Python decides."""

import logging
import time

from strands import Agent

from ...common.evidence import segments_to_prompt_block
from ...common.prompts import TRANSCRIPT_RULES
from ...llm import build_model
from ...models import Check, TranscriptSegment
from .schemas import ConsentExtraction, VerbatimExtraction

logger = logging.getLogger(__name__)

# Reasoning effort for this agent; see scripts/verbatim/try_verbatim.py to compare.
VERBATIM_EFFORT = "none"
CONSENT_EFFORT = "none"

VERBATIM_PROMPT = (
    "You are a strict compliance auditor for sales calls. For each required element, decide "
    "whether the AGENT clearly conveyed it. A wrong 'present' lets a non-compliant sale "
    "through, so when in doubt the answer is present=false.\n"
    "- Only the AGENT's words count. Something the customer said, or asked ('are you "
    "recording this?'), never counts.\n"
    "- Judge meaning, not exact wording: a paraphrase is fine. But EVERY part of the "
    "element must be conveyed. If an element has several parts (for example 'quality "
    "assurance and training') and only some were said, present=false.\n"
    "- A negation ('this call is not recorded') is not present.\n"
    "- Announcing that a statement is coming, or asking whether it may be read, does not "
    "count; the statement itself must be made.\n"
    "- present=true requires a quote: the exact words the agent said, copied character for "
    "character, and the ONE segment ID where they appear (the first complete statement if "
    "it was said more than once). If not present, quote=null and segment_ids=[].\n"
    "- Return exactly one entry per required element, copying the element text exactly.\n"
    + TRANSCRIPT_RULES)


def build_verbatim_agent() -> Agent:
    return Agent(name="verbatim_check", model=build_model(VERBATIM_EFFORT),
                 system_prompt=VERBATIM_PROMPT, callback_handler=None)


async def extract_verbatim(segments: list[TranscriptSegment], check: Check) -> VerbatimExtraction:
    logger.info("extract_verbatim start check=%s elements=%d", check.check_id,
                len(check.required_elements))
    started = time.perf_counter()
    elements = "\n".join(f"- {e}" for e in check.required_elements)
    # A fresh agent per call: an Agent keeps its message history.
    try:
        result = await build_verbatim_agent().invoke_async(
            f"Transcript:\n{segments_to_prompt_block(segments)}\n\n---\n"
            f"check_id={check.check_id}\nCheck: {check.description}\n"
            f"Required elements:\n{elements}",
            structured_output_model=VerbatimExtraction)
    except Exception:
        logger.exception("extract_verbatim failed check=%s after %.1fs",
                         check.check_id, time.perf_counter() - started)
        raise
    out = result.structured_output
    logger.info("extract_verbatim done check=%s present=%s in %.1fs", check.check_id,
                [e.present for e in out.elements], time.perf_counter() - started)
    for e in out.elements:
        logger.debug("extract_verbatim check=%s element=%r present=%s conf=%.2f segments=%s "
                     "quote=%r", check.check_id, e.element, e.present, e.confidence,
                     e.segment_ids, e.quote)
    logger.debug("extract_verbatim check=%s reasoning=%s", check.check_id, out.reasoning)
    return out


# ---------------------------------------------------------------------------
# Customer response -- did the CUSTOMER agree when asked? A different question
# from "did the agent say it", so a separate agent with a three-way outcome.
# ---------------------------------------------------------------------------

CONSENT_PROMPT = (
    "You are a strict compliance auditor for sales calls. The agent must get the "
    "CUSTOMER's explicit agreement to a statement. Find the agent's statement, then the "
    "customer's reply to it, and give one outcome:\n"
    "- agreed: the customer clearly says yes, agrees, or says it is fine / okay in direct "
    "reply to the agent's statement.\n"
    "- refused: the customer says no, objects, or asks not to be recorded / asks the agent "
    "to stop.\n"
    "- no_clear_response: there is no customer reply to it in the transcript; or the "
    "customer only asks a question, changes the subject, or gives an unclear answer; or the "
    "reply is not in a separate CUSTOMER segment (for example it is buried inside the "
    "agent's own turn). Never guess 'agreed'.\n"
    "Only the CUSTOMER's words count as the answer, and only an answer that comes AFTER "
    "the agent's statement.\n"
    "Cite the ONE agent segment with the statement and the ONE customer segment with the "
    "answer, each with the exact words copied character for character. If there is no "
    "clear answer, leave the response fields null.\n" + TRANSCRIPT_RULES)


def build_consent_agent() -> Agent:
    return Agent(name="customer_response_check", model=build_model(CONSENT_EFFORT),
                 system_prompt=CONSENT_PROMPT, callback_handler=None)


async def extract_consent(segments: list[TranscriptSegment], check: Check) -> ConsentExtraction:
    logger.info("extract_consent start check=%s", check.check_id)
    started = time.perf_counter()
    try:
        result = await build_consent_agent().invoke_async(
            f"Transcript:\n{segments_to_prompt_block(segments)}\n\n---\n"
            f"check_id={check.check_id}\nCheck: {check.description}\n"
            f"The customer must: {check.required_elements[0]}",
            structured_output_model=ConsentExtraction)
    except Exception:
        logger.exception("extract_consent failed check=%s after %.1fs",
                         check.check_id, time.perf_counter() - started)
        raise
    out = result.structured_output
    logger.info("extract_consent done check=%s outcome=%s confidence=%.2f prompt=%s response=%s "
                "in %.1fs", check.check_id, out.outcome, out.confidence, out.prompt_segment_id,
                out.response_segment_id, time.perf_counter() - started)
    logger.debug("extract_consent check=%s prompt_quote=%r response_quote=%r reasoning=%s",
                 check.check_id, out.prompt_quote, out.response_quote, out.reasoning)
    return out
