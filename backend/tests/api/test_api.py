"""HTTP layer only: routing, caching, validation, status codes. The workflow is
faked, so no API calls; the workflow itself is covered by tests/test_pipeline.py."""

import pytest
from fastapi.testclient import TestClient

from hackathon_qa_automation.api import routes
from hackathon_qa_automation.api.app import app
from hackathon_qa_automation.models import CheckVerdict
from hackathon_qa_automation.pipeline import LeadScore
from hackathon_qa_automation.store import ScoreStore


@pytest.fixture
def store(tmp_path):
    return ScoreStore(tmp_path)


@pytest.fixture
def client(store):
    app.dependency_overrides[routes.get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_score(lead_id="3613792", decision="AUTO_PASS", error=None, evidence="t", reasoning="r"):
    verdict = CheckVerdict(
        check_id="recording_disclaimer", check_name="Recording disclaimer", check_type="verbatim", critical=True, verdict="pass",
        confidence=0.99, evidence_segment_ids=["S004"], timestamp_start=10.2, timestamp_end=38.0,
        evidence_text=evidence, reasoning=reasoning, retailer_id="retailer1",
        checklist_version="R1-v3")
    return LeadScore(lead_id=lead_id, retailer_id="retailer1", call_date="2026-09-19",
                     checklist_version="R1-v3", decision=decision,
                     reasons=["all critical checks passed"], verdicts=[verdict], error=error)


def fake_workflow(monkeypatch, **kwargs):
    calls = []

    async def _score(lead_id):
        calls.append(lead_id)
        return make_score(lead_id, **kwargs)

    monkeypatch.setattr(routes, "score_lead", _score)
    return calls


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_leads_list_shows_every_lead_with_a_score_only_once_processed(client, store):
    store.save(make_score("3613792"))
    rows = {r["lead_id"]: r for r in client.get("/api/leads").json()}
    assert list(rows) == ["3613790", "3613791", "3613792", "3613793"]
    assert rows["3613792"]["customer_name"] == "Sarah Mitchell"
    assert rows["3613792"]["retailer_id"] == "retailer1" and rows["3613792"]["call_date"] == "2026-09-19"
    assert rows["3613792"]["score"]["decision"] == "AUTO_PASS"
    assert rows["3613790"]["score"] is None  # not processed yet


def test_processing_a_lead_fills_in_its_score_in_the_list(client, monkeypatch):
    fake_workflow(monkeypatch)
    before = {r["lead_id"]: r["score"] for r in client.get("/api/leads").json()}
    assert before["3613793"] is None
    client.post("/api/leads/3613793/score")
    after = {r["lead_id"]: r["score"] for r in client.get("/api/leads").json()}
    assert after["3613793"]["decision"] == "AUTO_PASS" and after["3613790"] is None


def test_a_failed_scoring_leaves_the_lead_unprocessed_in_the_list(client, monkeypatch):
    fake_workflow(monkeypatch, decision="HUMAN_QA", error="RuntimeError: model down")
    client.post("/api/leads/3613792/score")
    assert {r["lead_id"]: r["score"] for r in client.get("/api/leads").json()}["3613792"] is None


def test_lead_detail_has_crm_transcript_and_score(client, store):
    store.save(make_score("3613792"))
    d = client.get("/api/leads/3613792").json()
    assert d["crm"]["email"] == "sarah.mitchell@example.com"
    assert len(d["transcript"]) == 122 and d["transcript"][0]["segment_id"] == "S001"
    assert d["score"]["decision"] == "AUTO_PASS"


def test_score_runs_the_workflow_and_saves_the_result(client, store, monkeypatch):
    calls = fake_workflow(monkeypatch)
    r = client.post("/api/leads/3613792/score")
    assert r.status_code == 200 and r.json()["decision"] == "AUTO_PASS"
    assert r.json()["verdicts"][0]["evidence_segment_ids"] == ["S004"]
    assert calls == ["3613792"] and store.get("3613792").decision == "AUTO_PASS"


def test_the_score_carries_the_confidence_threshold_the_gate_uses(client, monkeypatch):
    fake_workflow(monkeypatch)
    assert client.post("/api/leads/3613792/score").json()["confidence_threshold"] == 0.75


def test_a_saved_score_is_returned_without_rerunning_unless_forced(client, store, monkeypatch):
    calls = fake_workflow(monkeypatch)
    client.post("/api/leads/3613792/score")
    client.post("/api/leads/3613792/score")
    assert calls == ["3613792"]  # the second request used the saved score
    client.post("/api/leads/3613792/score?force=true")
    assert calls == ["3613792", "3613792"]


def test_a_scoring_failure_is_not_an_http_error_and_is_not_saved(client, store, monkeypatch):
    calls = fake_workflow(monkeypatch, decision="HUMAN_QA", error="RuntimeError: model down")
    r = client.post("/api/leads/3613792/score")
    assert r.status_code == 200
    assert r.json()["decision"] == "HUMAN_QA" and "model down" in r.json()["error"]
    assert store.get("3613792") is None
    client.post("/api/leads/3613792/score")
    assert len(calls) == 2  # nothing was saved, so it tried again


def test_card_numbers_are_redacted_in_the_score_and_the_transcript(client, store, monkeypatch):
    fake_workflow(monkeypatch, evidence="my card is 4111 1111 1111 1111 ok",
                  reasoning="quoted 4111-1111-1111-1111")
    body = client.post("/api/leads/3613792/score").json()
    assert "4111" not in str(body) and "[CARD NUMBER REDACTED]" in body["verdicts"][0]["evidence_text"]
    assert "4111" not in str(client.get("/api/leads/3613792").json())


def test_unknown_lead_is_404_and_never_reaches_the_workflow(client, monkeypatch):
    async def boom(lead_id):
        raise AssertionError("workflow must not run for an unknown lead")
    monkeypatch.setattr(routes, "score_lead", boom)
    assert client.post("/api/leads/9999999/score").status_code == 404
    assert client.get("/api/leads/9999999").status_code == 404


@pytest.mark.parametrize("bad", ["..%2F..%2Fetc", "a b", "x" * 65, "3613790%00", "lead.json"])
def test_lead_id_that_could_escape_the_data_folder_is_rejected(client, bad):
    for method in (client.post, client.get):
        url = f"/api/leads/{bad}/score" if method == client.post else f"/api/leads/{bad}"
        assert method(url).status_code in (404, 422)


def test_score_only_accepts_post(client):
    assert client.get("/api/leads/3613792/score").status_code == 405
