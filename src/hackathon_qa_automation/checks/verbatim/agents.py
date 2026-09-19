"""Strands agent for verbatim checks. It extracts and cites; Python decides."""

import logging
import time

from strands import Agent

from ...common.evidence import segments_to_prompt_block
from ...common.prompts import TRANSCRIPT_RULES
from ...llm import build_model
from ...models import Check, TranscriptSegment
from .schemas import VerbatimExtraction

logger = logging.getLogger(__name__)

# Reasoning effort for this agent; see scripts/verbatim/try_verbatim.py to compare.
VERBATIM_EFFORT = "none"

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
