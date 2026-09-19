"""Verbatim verdict logic with the agent scripted: what Python does with good,
wrong and untrustworthy model output. No API calls."""

import asyncio

import pytest

from hackathon_qa_automation.checks.verbatim import scoring as verbatim
from hackathon_qa_automation.checks.verbatim.schemas import ElementResult, VerbatimExtraction
from hackathon_qa_automation.common.loaders import load_checklist, load_lead, load_transcript

LEAD_ID = "3613790"
ELEMENT = "States the call will be recorded for quality assurance and training"
QUOTE = "this call will be recorded for quality assuranceand, training purposes"


@pytest.fixture
def setup():
    lead = load_lead(LEAD_ID)
    version = load_checklist(lead.retailer_id).version_for(lead.call_date)
    check = next(c for c in version.checks if c.check_id == "recording_disclaimer")
    return lead, load_transcript(LEAD_ID).segments, check, version.version


def result(present=True, quote=QUOTE, ids=("S004",), confidence=0.95, element=ELEMENT):
    return ElementResult(element=element, present=present, quote=quote if present else None,
                         segment_ids=list(ids) if present else [], confidence=confidence)


def score(setup, monkeypatch, *results):
    lead, segments, check, version = setup

    async def fake_extract(_segments, _check):
        return VerbatimExtraction(elements=list(results), reasoning="r")

    monkeypatch.setattr(verbatim, "extract_verbatim", fake_extract)
    return asyncio.run(verbatim.score_verbatim_check(segments, lead, check, version))


def test_pass_carries_real_timestamps(setup, monkeypatch):
    v = score(setup, monkeypatch, result())
    assert v.verdict == "pass" and v.critical and v.checklist_version == "R1-v3"
    assert (v.timestamp_start, v.timestamp_end) == (10.2, 58.8)  # from S004, not the model
    assert v.confidence == 0.95


def test_element_not_conveyed_fails_with_the_models_confidence(setup, monkeypatch):
    v = score(setup, monkeypatch, result(present=False, confidence=0.9))
    assert v.verdict == "fail" and v.confidence == 0.9 and ELEMENT in v.reasoning


def test_hallucinated_segment_is_uncertain(setup, monkeypatch):
    assert score(setup, monkeypatch, result(ids=("S999",))).verdict == "uncertain"


def test_quote_not_in_cited_segment_is_uncertain(setup, monkeypatch):
    assert score(setup, monkeypatch, result(quote="you are being recorded")).verdict == "uncertain"


def test_customer_speech_never_counts_as_the_agent_conveying_it(setup, monkeypatch):
    # S003 is the customer's turn ("Good. Thanks. How are you?"): quote is real, speaker is wrong.
    v = score(setup, monkeypatch, result(quote="Thanks. How are you?", ids=("S003",)))
    assert v.verdict == "uncertain" and "not spoken by the agent" in v.reasoning


def test_element_the_model_skipped_is_uncertain(setup, monkeypatch):
    v = score(setup, monkeypatch)  # the model returned no elements at all
    assert v.verdict == "uncertain" and "was not assessed" in v.reasoning


def test_element_text_is_matched_ignoring_case_and_spacing(setup, monkeypatch):
    v = score(setup, monkeypatch, result(element="  " + ELEMENT.upper() + " "))
    assert v.verdict == "pass"
