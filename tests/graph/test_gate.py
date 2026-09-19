from hackathon_qa_automation.graph.gate import decide
from hackathon_qa_automation.models import CheckVerdict


def verdict(check_id="c", critical=True, v="pass", confidence=1.0):
    return CheckVerdict(check_id=check_id, check_type="factual", critical=critical, verdict=v,
                        confidence=confidence, evidence_segment_ids=[], timestamp_start=None,
                        timestamp_end=None, evidence_text="", reasoning="", retailer_id="r",
                        checklist_version="v")


# --- gate ---------------------------------------------------------------------

def test_gate_rules():
    assert decide("L", [verdict(v="fail")], sample_rate=0).decision == "HOLD"
    assert decide("L", [verdict(critical=False, v="fail")], sample_rate=0).decision == "AUTO_PASS"
    assert decide("L", [verdict(v="uncertain")], sample_rate=0).decision == "HUMAN_QA"
    assert decide("L", [verdict(confidence=0.5)], sample_rate=0).decision == "HUMAN_QA"
    assert decide("L", [verdict()], sample_rate=0).decision == "AUTO_PASS"
    # a critical fail is never softened by an uncertain check elsewhere
    assert decide("L", [verdict("a", v="fail"), verdict("b", v="uncertain")],
                  sample_rate=0).decision == "HOLD"


def test_clean_call_sampling_is_deterministic():
    assert decide("L", [verdict()], sample_rate=1.0).decision == "HUMAN_QA"
    first = decide("3613790", [verdict()]).decision
    assert all(decide("3613790", [verdict()]).decision == first for _ in range(5))
    hits = sum(decide(str(i), [verdict()]).decision == "HUMAN_QA" for i in range(5000))
    assert 150 < hits < 350  # ~5% of 5000
