from hackathon_qa_automation.common.evidence import quote_is_grounded, resolve_evidence
from hackathon_qa_automation.common.loaders import load_transcript
from hackathon_qa_automation.models import TranscriptSegment

LEAD_ID = "3613790"


def seg(sid, speaker, start, end, text="x"):
    return TranscriptSegment(segment_id=sid, speaker=speaker, start=start, end=end, text=text)


# --- evidence and grounding ------------------------------------------------

def test_evidence_resolves_real_times_and_flags_unknown_ids():
    segs = [seg("S1", "AGENT", 1.0, 3.0, "a"), seg("S2", "CUSTOMER", 4.0, 6.0, "b")]
    ev = resolve_evidence(segs, ["S1", "S2", "S999"])
    assert (ev.start, ev.end, ev.unknown_ids) == (1.0, 6.0, ["S999"])
    none = resolve_evidence(segs, ["S999"])
    assert none.start is None and none.unknown_ids == ["S999"]


def test_quote_grounding():
    transcript = load_transcript(LEAD_ID).segments
    assert quote_is_grounded(transcript, ["S040"], "sarah.mitchell@example.com")
    assert quote_is_grounded(transcript, ["S040"], "  SARAH.mitchell@example.com ")
    assert not quote_is_grounded(transcript, ["S040"], "sarah.mitchell@gmial.com")
    assert not quote_is_grounded(transcript, ["S001"], "sarah.mitchell@example.com")  # wrong segment
    assert not quote_is_grounded(transcript, ["S040"], None)
    assert not quote_is_grounded(transcript, ["S040"], "")
