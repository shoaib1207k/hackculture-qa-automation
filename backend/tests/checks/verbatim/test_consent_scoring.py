"""Customer-response (consent) verdict logic with the agent scripted. No API calls.

Uses lead 3613792, where the customer's "Yes, that's fine." is its own segment
(S004a) right after the agent's disclaimer (S004)."""

import asyncio

import pytest

from hackathon_qa_automation.checks.verbatim import scoring as verbatim
from hackathon_qa_automation.checks.verbatim.schemas import ConsentExtraction
from hackathon_qa_automation.common.loaders import load_checklist, load_lead, load_transcript

LEAD_ID = "3613792"
PROMPT_QUOTE = "this call will be recorded for quality assurance and training purposes"


@pytest.fixture
def setup():
    lead = load_lead(LEAD_ID)
    version = load_checklist(lead.retailer_id).version_for(lead.call_date)
    check = next(c for c in version.checks if c.check_id == "recording_consent")
    return lead, load_transcript(LEAD_ID).segments, check, version.version


def extraction(outcome="agreed", prompt_id="S004", prompt_quote=PROMPT_QUOTE,
               response_id="S004a", response_quote="Yes, that's fine.", confidence=0.95):
    return ConsentExtraction(outcome=outcome, prompt_segment_id=prompt_id, prompt_quote=prompt_quote,
                             response_segment_id=response_id, response_quote=response_quote,
                             confidence=confidence, reasoning="r")


def score(setup, monkeypatch, ext):
    lead, segments, check, version = setup

    async def fake_extract(_segments, _check):
        return ext

    monkeypatch.setattr(verbatim, "extract_consent", fake_extract)
    return asyncio.run(verbatim.score_customer_response_check(segments, lead, check, version))


def test_check_is_critical_and_customer_spoken(setup):
    assert setup[2].critical and setup[2].spoken_by == "CUSTOMER"


def test_agreed_passes_with_the_customers_timestamp(setup, monkeypatch):
    v = score(setup, monkeypatch, extraction())
    assert v.verdict == "pass" and v.critical and v.confidence == 0.95
    assert (v.timestamp_start, v.timestamp_end) == (38.4, 40.0)  # the customer's line, from S004a


def test_refused_fails(setup, monkeypatch):
    v = score(setup, monkeypatch, extraction(outcome="refused", response_quote="Yes, that's fine."))
    assert v.verdict == "fail" and v.confidence == 0.95


def test_no_clear_response_is_uncertain(setup, monkeypatch):
    v = score(setup, monkeypatch, extraction(outcome="no_clear_response", response_id=None,
                                             response_quote=None))
    assert v.verdict == "uncertain" and v.confidence == 0.0


def test_answer_inside_the_agents_turn_is_uncertain(setup, monkeypatch):
    # The malformed-transcript case: the "yes" sits in an AGENT segment.
    v = score(setup, monkeypatch, extraction(response_id="S004", response_quote="training purposes"))
    assert v.verdict == "uncertain" and "not spoken by the customer" in v.reasoning


def test_answer_before_the_statement_is_uncertain(setup, monkeypatch):
    v = score(setup, monkeypatch, extraction(response_id="S003", response_quote="Good. Thanks."))
    assert v.verdict == "uncertain" and "does not come after" in v.reasoning


@pytest.mark.parametrize("kwargs", [
    {"response_id": "S999"},                              # segment does not exist
    {"response_quote": "Absolutely, go ahead."},          # quote not in the cited segment
    {"prompt_id": "S999"},                                # the agent's statement is invented
    {"prompt_quote": "we are recording you"},             # statement quote not in its segment
    {"prompt_id": "S004a", "prompt_quote": "Yes, that's fine."},  # the "statement" is the customer's
])
def test_untrustworthy_evidence_is_uncertain(setup, monkeypatch, kwargs):
    assert score(setup, monkeypatch, extraction(**kwargs)).verdict == "uncertain"
