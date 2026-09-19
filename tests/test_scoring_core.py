from datetime import date

import pytest

from hackathon_qa_automation.deterministic import (compute_dead_air, compute_interruptions,
                                                   quote_is_grounded, resolve_evidence,
                                                   values_match)
from hackathon_qa_automation.gate import decide
from hackathon_qa_automation.loaders import load_checklist, load_lead, load_transcript
from hackathon_qa_automation.models import Check, CheckVerdict, TranscriptSegment

LEAD_ID = "3613790"


def seg(sid, speaker, start, end, text="x"):
    return TranscriptSegment(segment_id=sid, speaker=speaker, start=start, end=end, text=text)


def verdict(check_id="c", critical=True, v="pass", confidence=1.0):
    return CheckVerdict(check_id=check_id, check_type="factual", critical=critical, verdict=v,
                        confidence=confidence, evidence_segment_ids=[], timestamp_start=None,
                        timestamp_end=None, evidence_text="", reasoning="", retailer_id="r",
                        checklist_version="v")


# --- fixtures load and are consistent -------------------------------------

def test_fixture_loads_and_resolves_live_version():
    lead, transcript = load_lead(LEAD_ID), load_transcript(LEAD_ID)
    checklist = load_checklist(lead.retailer_id)
    version = checklist.version_for(lead.call_date)
    assert version.version == "R1-v3"
    assert len(transcript.segments) == 120
    factual = [c for c in version.checks if c.type == "factual"]
    assert factual and all(c.crm_field in lead.fields for c in factual)


def test_version_is_picked_by_call_date_not_latest():
    cl = load_checklist("retailer1")
    with pytest.raises(ValueError):
        cl.version_for(date(2025, 1, 1))  # before any version was live


def test_checklist_config_errors_fail_at_load():
    with pytest.raises(ValueError):
        Check(check_id="a", type="factual", critical=True)  # no crm_field
    with pytest.raises(ValueError):
        Check(check_id="a", type="verbatim", critical=True)  # no required_elements
    with pytest.raises(ValueError):
        Check(check_id="a", type="factual", crm_field="email")  # critical not set


# --- factual comparison ----------------------------------------------------

@pytest.mark.parametrize("kind,spoken,crm,expected", [
    ("money", "42.90", "42.90 AUD", True),
    ("money", "$42.90", "42.90 AUD", True),
    ("money", "forty two ninety", "42.90 AUD", False),  # unparseable never matches
    ("money", "28.6 cents", "31.9c/kWh", False),        # the brief's worked example
    ("money", "31.9 cents per kWh", "31.9c/kWh", True),
    ("money", "31.9c/kWh", "$0.319", True),             # cents == dollars
    ("money", "free", "0.00 AUD", True),
    ("money", "$0", "0.00 AUD", True),
    ("money", "$5", "0.00 AUD", False),
    ("email", "sarah.mitchell@example.com", "sarah.mitchell@example.com", True),
    ("email", "sarah dot mitchell at example dot com", "sarah.mitchell@example.com", True),
    ("email", "j.smith@gmail.com", "j.smith@gmial.com", False),  # typo must fail
    ("phone", "0412 555 783", "0412555783", True),
    ("phone", "+61 412 555 783", "0412 555 783", True),
    ("address", "18 Harbour View Drive, Parramatta NSW 2150",
     "18 Harbour View Dr Parramatta NSW 2150", True),
    ("address", "18 Harbour View Drive, Parramatta NSW 2150",
     "Unit 4, 18 Harbour View Drive, Parramatta NSW 2150", False),  # missing unit
    ("text", "Netcom CF40 Wi-Fi 6.", "netcom cf40 wi-fi 6", True),
])
def test_values_match(kind, spoken, crm, expected):
    assert values_match(kind, spoken, crm) is expected


def test_missing_value_never_matches():
    assert not values_match("text", None, "x")
    assert not values_match("text", "x", None)


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
