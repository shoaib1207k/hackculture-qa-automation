"""The whole graph with the two LLM agents faked: tests the wiring, the gate and
the failure fallback without API calls."""

import pytest

from hackathon_qa_automation.checks.factual import scoring as factual
from hackathon_qa_automation.checks.factual.schemas import FactualComparison, FactualExtraction
from hackathon_qa_automation.checks.verbatim import scoring as verbatim
from hackathon_qa_automation.checks.verbatim.schemas import (ConsentExtraction, ElementResult,
                                                             VerbatimExtraction)
from hackathon_qa_automation.pipeline import score_lead


def fake_agents(monkeypatch, comparison="match", extract_error=None, disclaimer_read=True,
                consent="agreed"):
    async def extract(segments, check):
        if extract_error:
            raise extract_error
        # Every check cites S040, whose text contains the quote below.
        return FactualExtraction(value="v", quote="sarah.mitchell@example.com",
                                 segment_ids=["S040"], confidence=0.95, reasoning="r")

    async def compare(spoken, crm, check):
        verdict = comparison(check) if callable(comparison) else comparison
        return FactualComparison(verdict=verdict, confidence=0.95, reasoning="c")

    async def extract_disclaimer(segments, check):
        e = check.required_elements[0]
        return VerbatimExtraction(reasoning="r", elements=[ElementResult(
            element=e, present=disclaimer_read, confidence=0.95,
            quote="this call will be recorded for quality assuranceand, training purposes"
            if disclaimer_read else None, segment_ids=["S004"] if disclaimer_read else [])])

    async def extract_consent(segments, check):
        # S004 is the agent's turn, S005 the customer's reply that follows it.
        return ConsentExtraction(
            outcome=consent, confidence=0.95, reasoning="r",
            prompt_segment_id=None if consent == "no_clear_response" else "S004",
            prompt_quote="this call will be recorded for quality assuranceand, training purposes",
            response_segment_id=None if consent == "no_clear_response" else "S005",
            response_quote="They reduced it today to sixty five")

    monkeypatch.setattr(verbatim, "extract_verbatim", extract_disclaimer)
    monkeypatch.setattr(verbatim, "extract_consent", extract_consent)
    monkeypatch.setattr(factual, "extract_factual", extract)
    monkeypatch.setattr(factual, "compare_factual", compare)


async def test_a_clean_call_passes_every_check_and_auto_submits(monkeypatch):
    fake_agents(monkeypatch)
    score = await score_lead("3613790")
    assert score.error is None and score.checklist_version == "R1-v3"
    assert [v.check_id for v in score.verdicts if v.check_type == "factual"] == [
        "plan_price_intro", "plan_price_standard", "email_match", "service_address_match",
        "delivery_address_match", "modem_free"]
    assert len(score.verdicts) == 10
    assert {v.verdict for v in score.verdicts} == {"pass"}
    assert score.decision == "AUTO_PASS"


async def test_a_missing_disclaimer_holds_the_sale(monkeypatch):
    fake_agents(monkeypatch, disclaimer_read=False)
    score = await score_lead("3613790")
    assert score.decision == "HOLD"
    assert score.reasons == ["Critical check failed: Recording disclaimer"]


async def test_customer_refusing_recording_holds_the_sale(monkeypatch):
    fake_agents(monkeypatch, consent="refused")
    score = await score_lead("3613790")
    assert score.decision == "HOLD" and score.reasons == ["Critical check failed: Recording consent"]


async def test_no_clear_consent_routes_to_a_human_not_a_hold(monkeypatch):
    fake_agents(monkeypatch, consent="no_clear_response")
    score = await score_lead("3613790")
    assert score.decision == "HUMAN_QA"
    assert score.reasons == ["Unclear or low-confidence result: Recording consent"]


async def test_a_critical_fail_holds_the_sale_with_reasons(monkeypatch):
    fake_agents(monkeypatch, comparison=lambda c: "mismatch" if c.check_id == "email_match" else "match")
    score = await score_lead("3613790")
    assert score.decision == "HOLD"
    assert score.reasons == ["Critical check failed: Customer email"]


async def test_node_error_never_crashes_and_never_auto_passes(monkeypatch):
    fake_agents(monkeypatch, extract_error=RuntimeError("model down"))
    score = await score_lead("3613790")
    assert score.decision == "HUMAN_QA"
    assert "RuntimeError" in score.error and "model down" in score.error


async def test_node_error_after_a_finished_critical_fail_still_holds(monkeypatch):
    # Behaviour finishes; make it fail a critical check, then break the factual node.
    from hackathon_qa_automation.checks.behaviour import scoring as behaviour
    real = behaviour.run_behaviour_checks

    def failing(segments, lead, checks, version):
        return [v.model_copy(update={"verdict": "fail", "critical": True})
                for v in real(segments, lead, checks, version)]

    monkeypatch.setattr("hackathon_qa_automation.graph.nodes.run_behaviour_checks", failing)
    fake_agents(monkeypatch, extract_error=RuntimeError("model down"))
    score = await score_lead("3613790")
    assert score.decision == "HOLD" and score.error


async def test_missing_lead_data_is_a_caller_error(monkeypatch):
    fake_agents(monkeypatch)
    with pytest.raises(FileNotFoundError):
        await score_lead("9999999")
