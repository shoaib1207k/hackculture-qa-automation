"""Run the customer-consent check live on real and doctored versions of the call.

    uv run python scripts/verbatim/try_consent.py
    OPENAI_REASONING_EFFORT=low uv run python scripts/verbatim/try_consent.py   # compare effort

Leads: 3613792 = customer says "Yes, that's fine." (own segment, S004a);
       3613793 = customer refuses; 3613790 = the original malformed transcript
       (the customer's reply is buried inside the agent's turn).
Add a case: append a row to CASES -- (name, lead id, function that edits the segments, expected).
"""

import asyncio
import time

from hackathon_qa_automation.checks.verbatim.scoring import score_customer_response_check
from hackathon_qa_automation.common.loaders import load_checklist, load_lead, load_transcript
from hackathon_qa_automation.common.logging_config import setup_logging


def reply(text):
    def edit(segs):
        next(s for s in segs if s.segment_id == "S004a").text = text
    return edit


def no_statement_but_a_yes(segs):
    """The agent never gives the disclaimer, yet the customer says yes out of nowhere."""
    s4 = next(s for s in segs if s.segment_id == "S004")
    s4.text = "Yeah. I'm good. Thank you. Now let me double check the address."


CASES = [
    ("customer: 'Yes, that's fine.'", "3613792", lambda s: None, "pass"),
    ("customer: 'Yeah okay.'", "3613792", reply("Yeah okay."), "pass"),
    ("customer refuses", "3613793", lambda s: None, "fail"),
    ("customer: 'Not really, no.'", "3613792", reply("Not really, no."), "fail"),
    ("malformed: reply buried in agent turn", "3613790", lambda s: None, "uncertain"),
    ("customer asks a question instead", "3613792", reply("Hmm, what's that for?"), "uncertain"),
    ("customer does not answer", "3613792", reply("Sorry, can you say that again?"), "uncertain"),
    ("a yes with no statement before it", "3613792", no_statement_but_a_yes, "uncertain"),
]


async def main():
    setup_logging()

    async def run(name, lead_id, edit):
        lead = load_lead(lead_id)
        version = load_checklist(lead.retailer_id).version_for(lead.call_date)
        check = next(c for c in version.checks if c.check_id == "recording_consent")
        segs = load_transcript(lead_id).segments
        edit(segs)
        return await score_customer_response_check(segs, lead, check, version.version)

    started = time.time()
    verdicts = await asyncio.gather(*(run(n, i, e) for n, i, e, _ in CASES))
    bad = 0
    for (name, _, _, expected), v in zip(CASES, verdicts):
        ok = v.verdict == expected
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} exp={expected:9} got={v.verdict:9} conf={v.confidence:.2f} "
              f"{v.evidence_segment_ids}  {name}")
        if not ok:
            print(f"      {v.reasoning}")
    print(f"\n{len(CASES) - bad}/{len(CASES)} as expected in {time.time() - started:.1f}s")


asyncio.run(main())
