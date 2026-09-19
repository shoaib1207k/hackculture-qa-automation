"""Run the verbatim check live on the real call, doctored into cases with a known answer.

    uv run python scripts/verbatim/try_verbatim.py
    OPENAI_REASONING_EFFORT=low uv run python scripts/verbatim/try_verbatim.py   # compare effort

Each case rewrites the disclaimer sentence in segment S004 (or adds a customer line).
Add a case: append a row to CASES -- (name, function that edits the segments, expected verdict).
"""

import asyncio
import time

from hackathon_qa_automation.checks.verbatim.scoring import score_verbatim_check
from hackathon_qa_automation.common.loaders import load_checklist, load_lead, load_transcript
from hackathon_qa_automation.common.logging_config import setup_logging

LEAD_ID = "3613790"
SENTENCE = ("please be advised that this call will be recorded for quality "
            "assuranceand, training purposes.")


def in_s004(replacement):
    """Replace the disclaimer sentence inside the agent's S004 turn."""
    def edit(segs):
        s4 = next(s for s in segs if s.segment_id == "S004")
        assert SENTENCE in s4.text
        s4.text = s4.text.replace(SENTENCE, replacement)
    return edit


def customer_says_it(segs):
    in_s004("")(segs)
    next(s for s in segs if s.segment_id == "S003").text = (
        "Good. Thanks. Just so you know, this call is being recorded for quality "
        "assurance and training purposes. How are you?")


CASES = [
    ("real call: disclaimer read in full", lambda segs: None, "pass"),
    ("paraphrased", in_s004("please note this conversation is being recorded for quality "
                            "assurance and for training."), "pass"),
    ("disclaimer removed", in_s004(""), "fail"),
    ("only half said (no training)", in_s004("please be advised that this call will be "
                                             "recorded for quality assurance."), "fail"),
    ("negated", in_s004("please be advised that this call is not being recorded."), "fail"),
    ("announced but never read", in_s004("I need to read you a short recording statement in "
                                          "a moment."), "fail"),
    ("customer says it, agent does not", customer_says_it, "fail"),
]


async def main():
    setup_logging()
    lead = load_lead(LEAD_ID)
    version = load_checklist(lead.retailer_id).version_for(lead.call_date)
    check = next(c for c in version.checks if c.type == "verbatim")

    async def run(name, edit):
        segs = load_transcript(LEAD_ID).segments
        edit(segs)
        return await score_verbatim_check(segs, lead, check, version.version)

    started = time.time()
    verdicts = await asyncio.gather(*(run(n, e) for n, e, _ in CASES))
    bad = 0
    for (name, _, expected), v in zip(CASES, verdicts):
        ok = v.verdict == expected
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} exp={expected:9} got={v.verdict:9} conf={v.confidence:.2f} "
              f"{v.evidence_segment_ids}  {name}")
        if not ok:
            print(f"      {v.reasoning}")
    print(f"\n{len(CASES) - bad}/{len(CASES)} as expected in {time.time() - started:.1f}s")


asyncio.run(main())
