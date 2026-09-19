"""The whole graph with the two LLM agents faked: tests the wiring, the gate and
the failure fallback without API calls."""

import pytest

from hackathon_qa_automation.checks.factual import scoring as factual
from hackathon_qa_automation.checks.factual.schemas import FactualComparison, FactualExtraction
from hackathon_qa_automation.pipeline import score_lead


def fake_agents(monkeypatch, comparison="match", extract_error=None):
    async def extract(segments, check):
        if extract_error:
            raise extract_error
        # Every check cites S040, whose text contains the quote below.
        return FactualExtraction(value="v", quote="sarah.mitchell@example.com",
                                 segment_ids=["S040"], confidence=0.95, reasoning="r")

    async def compare(spoken, crm, check):
        verdict = comparison(check) if callable(comparison) else comparison
        return FactualComparison(verdict=verdict, confidence=0.95, reasoning="c")

    monkeypatch.setattr(factual, "extract_factual", extract)
    monkeypatch.setattr(factual, "compare_factual", compare)


async def test_every_check_runs_and_placeholder_verbatim_blocks_auto_pass(monkeypatch):
    fake_agents(monkeypatch)
    score = await score_lead("3613790")
    assert score.error is None and score.checklist_version == "R1-v3"
    assert [v.check_id for v in score.verdicts if v.check_type == "factual"] == [
        "plan_price_intro", "plan_price_standard", "email_match", "service_address_match",
        "delivery_address_match", "modem_free"]
    assert len(score.verdicts) == 9
    # every factual + behaviour check passes, but the verbatim placeholder is
    # "uncertain": a call is never auto-passed on unchecked required statements
    assert score.decision == "HUMAN_QA"
    assert score.reasons == ["uncertain or low confidence: recording_disclaimer"]


async def test_a_critical_fail_holds_the_sale_with_reasons(monkeypatch):
    fake_agents(monkeypatch, comparison=lambda c: "mismatch" if c.check_id == "email_match" else "match")
    score = await score_lead("3613790")
    assert score.decision == "HOLD"
    assert score.reasons == ["critical fail: email_match"]


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
