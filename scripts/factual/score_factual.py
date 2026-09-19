"""Run the full factual path (extraction -> grounding -> comparison -> verdict)
live on a lead.

    uv run python scripts/factual/score_factual.py            # the real fixture: expect all pass
    uv run python scripts/factual/score_factual.py --defect   # tamper with the CRM: expect fails
"""

import asyncio
import sys
import time

from hackathon_qa_automation.checks.factual import run_factual_checks
from hackathon_qa_automation.common.loaders import load_checklist, load_lead, load_transcript
from hackathon_qa_automation.common.logging_config import setup_logging

LEAD_ID = "3613790"

# What --defect changes in the CRM record, to simulate an agent keying bad data.
DEFECTS = {
    "email": "sarah.mitchell@exmaple.com",                       # typo, like the brief's gmial
    "introductory_monthly_price": "45.90 AUD",                   # price differs from what was said
    "delivery_address": "18 Harbour View Drive, Parramatta NSW 2150",  # unit number missing
}


def mmss(seconds):
    return "--:--" if seconds is None else f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


async def main():
    setup_logging()
    lead, segments = load_lead(LEAD_ID), load_transcript(LEAD_ID).segments
    version = load_checklist(lead.retailer_id).version_for(lead.call_date)
    if "--defect" in sys.argv:
        lead.fields.update(DEFECTS)
        print("DEFECTS applied to CRM:", ", ".join(DEFECTS), "\n")
    checks = [c for c in version.checks if c.type == "factual"]

    started = time.time()
    verdicts = await run_factual_checks(segments, lead, checks, version.version)
    print(f"\n{len(checks)} factual checks in {time.time() - started:.1f}s  "
          f"(checklist {version.version})\n")
    for v in verdicts:
        crit = "critical" if v.critical else "non-critical"
        print(f"{v.verdict.upper():9} {v.check_id} ({crit}, conf {v.confidence:.2f}) "
              f"at {mmss(v.timestamp_start)}-{mmss(v.timestamp_end)}  {v.evidence_segment_ids}")
        print(f"          {v.reasoning}")


asyncio.run(main())
