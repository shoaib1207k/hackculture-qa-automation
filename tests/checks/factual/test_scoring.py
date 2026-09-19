"""The factual verdict logic with both agents scripted: these test what Python
does with good, wrong and untrustworthy model output. No API calls."""

import asyncio

import pytest

from hackathon_qa_automation.checks.factual import scoring as factual
from hackathon_qa_automation.checks.factual.schemas import FactualComparison, FactualExtraction
from hackathon_qa_automation.common.loaders import load_checklist, load_lead, load_transcript

LEAD_ID = "3613790"


@pytest.fixture
def setup():
    lead = load_lead(LEAD_ID)
    version = load_checklist(lead.retailer_id).version_for(lead.call_date)
    checks = {c.check_id: c for c in version.checks}
    return lead, load_transcript(LEAD_ID).segments, checks, version.version


def extraction(value="sarah.mitchell@example.com", quote="sarah.mitchell@example.com",
               ids=("S040",), confidence=0.95):
    return FactualExtraction(value=value, quote=quote, segment_ids=list(ids),
                             confidence=confidence, reasoning="r")


def comparison(verdict="match", confidence=0.9):
    return FactualComparison(verdict=verdict, confidence=confidence, reasoning="c")


def score(setup, monkeypatch, ext, cmp, check_id="email_match"):
    lead, segments, checks, version = setup
    calls = {"compare": 0}

    async def fake_extract(_segments, _check):
        return ext

    async def fake_compare(_spoken, _crm, _check):
        calls["compare"] += 1
        return cmp

    monkeypatch.setattr(factual, "extract_factual", fake_extract)
    monkeypatch.setattr(factual, "compare_factual", fake_compare)
    v = asyncio.run(factual.score_factual_check(segments, lead, checks[check_id], version))
    return v, calls["compare"]


@pytest.mark.parametrize("cmp_verdict,expected", [("match", "pass"), ("mismatch", "fail"),
                                                  ("uncertain", "uncertain")])
def test_comparison_result_maps_to_verdict(setup, monkeypatch, cmp_verdict, expected):
    v, _ = score(setup, monkeypatch, extraction(), comparison(cmp_verdict))
    assert v.verdict == expected and v.critical and v.checklist_version == "R1-v3"


def test_pass_carries_real_timestamps_and_min_confidence(setup, monkeypatch):
    v, _ = score(setup, monkeypatch, extraction(confidence=0.95), comparison(confidence=0.8))
    assert (v.timestamp_start, v.timestamp_end) == (439.6, 460.9)  # from S040, not the model
    assert v.confidence == 0.8


def test_hallucinated_segment_is_uncertain_and_skips_comparison(setup, monkeypatch):
    v, compared = score(setup, monkeypatch, extraction(ids=("S999",)), comparison())
    assert v.verdict == "uncertain" and v.timestamp_start is None and compared == 0


def test_quote_not_in_cited_segment_is_uncertain(setup, monkeypatch):
    v, compared = score(setup, monkeypatch, extraction(quote="sarah@somewhere.com"), comparison())
    assert v.verdict == "uncertain" and compared == 0


def test_value_never_stated_is_uncertain(setup, monkeypatch):
    v, compared = score(setup, monkeypatch,
                        extraction(value=None, quote=None, ids=()), comparison())
    assert v.verdict == "uncertain" and compared == 0


def test_missing_crm_value_is_uncertain(setup, monkeypatch):
    setup[0].fields.pop("email")
    v, compared = score(setup, monkeypatch, extraction(), comparison())
    assert v.verdict == "uncertain" and compared == 0


def test_run_factual_checks_runs_every_check(setup, monkeypatch):
    lead, segments, checks, version = setup
    monkeypatch.setattr(factual, "extract_factual", lambda *_: _async(extraction()))
    monkeypatch.setattr(factual, "compare_factual", lambda *_: _async(comparison()))
    factual_checks = [c for c in checks.values() if c.type == "factual"]
    out = asyncio.run(factual.run_factual_checks(segments, lead, factual_checks, version))
    assert [v.check_id for v in out] == [c.check_id for c in factual_checks]


async def _async(value):
    return value
