from hackathon_qa_automation.checks.behaviour.metrics import compute_dead_air, compute_interruptions
from hackathon_qa_automation.common.loaders import load_transcript
from hackathon_qa_automation.models import TranscriptSegment

LEAD_ID = "3613790"


def seg(sid, speaker, start, end, text="x"):
    return TranscriptSegment(segment_id=sid, speaker=speaker, start=start, end=end, text=text)


# --- behaviour --------------------------------------------------------------

def test_dead_air_and_interruptions():
    segs = [seg("S1", "AGENT", 0, 5), seg("S2", "CUSTOMER", 52, 55),  # 47s gap
            seg("S3", "AGENT", 54, 60)]                                # overlaps S2
    flagged, gap, ids = compute_dead_air(segs)
    assert flagged and gap == 47 and ids == ["S1", "S2"]
    assert compute_interruptions(segs) == (1, ["S2", "S3"])


def test_fixture_has_no_dead_air():
    flagged, _, _ = compute_dead_air(load_transcript(LEAD_ID).segments)
    assert not flagged
