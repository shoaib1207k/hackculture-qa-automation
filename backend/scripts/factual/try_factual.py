import asyncio, time, sys
from hackathon_qa_automation.checks.factual.agents import extract_factual
from hackathon_qa_automation.common.evidence import quote_is_grounded, resolve_evidence
from hackathon_qa_automation.common.loaders import load_checklist, load_lead, load_transcript
from hackathon_qa_automation.common.logging_config import setup_logging

setup_logging()


async def main():
    lead = load_lead("3613790"); segs = load_transcript("3613790").segments
    checks = {c.check_id: c for c in load_checklist(lead.retailer_id).version_for(lead.call_date).checks}
    ids = [k for k, c in checks.items() if c.type == "factual"]
    t = time.time()
    outs = await asyncio.gather(*(extract_factual(segs, checks[i]) for i in ids))
    print(f"{time.time()-t:.1f}s for {len(ids)} checks in parallel")
    for i, o in zip(ids, outs):
        ev = resolve_evidence(segs, o.segment_ids)
        crm_value = lead.fields.get(checks[i].crm_field) if checks[i].crm_field else None
        print(f"\n{i}  crm={crm_value!r}\n  value={o.value!r} conf={o.confidence} "
              f"segs={o.segment_ids} t={ev.start}-{ev.end} grounded={quote_is_grounded(segs, o.segment_ids, o.quote)}"
              f"\n  quote={o.quote!r}\n  why={o.reasoning}")
asyncio.run(main())
