import pytest

from hackathon_qa_automation.pipeline import LeadScore
from hackathon_qa_automation.store import ScoreStore


def score(lead_id="3613792"):
    return LeadScore(lead_id=lead_id, retailer_id="retailer1", call_date="2026-09-19",
                     checklist_version="R1-v3", decision="HOLD", reasons=["critical fail: x"],
                     verdicts=[])


def test_round_trip_and_overwrite(tmp_path):
    store = ScoreStore(tmp_path)
    assert store.get("3613792") is None
    store.save(score())
    assert store.get("3613792").decision == "HOLD"
    store.save(score().model_copy(update={"decision": "AUTO_PASS"}))
    assert store.get("3613792").decision == "AUTO_PASS"
    assert [p.name for p in tmp_path.iterdir()] == ["3613792.json"]  # no temp files left behind


def test_an_unreadable_file_counts_as_missing(tmp_path):
    (tmp_path / "3613792.json").write_text("{not json")
    assert ScoreStore(tmp_path).get("3613792") is None


@pytest.mark.parametrize("bad", ["../x", "a/b", "", "x" * 65, "a.b"])
def test_unsafe_lead_ids_are_refused(tmp_path, bad):
    with pytest.raises(ValueError):
        ScoreStore(tmp_path).get(bad)
