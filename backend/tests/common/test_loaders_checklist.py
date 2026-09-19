from datetime import date

import pytest

from hackathon_qa_automation.common.loaders import load_checklist, load_lead, load_transcript
from hackathon_qa_automation.models import Check

LEAD_ID = "3613790"


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


def test_every_check_has_a_human_name_and_a_missing_one_falls_back_to_the_id():
    lead = load_lead(LEAD_ID)
    version = load_checklist(lead.retailer_id).version_for(lead.call_date)
    names = {c.check_id: c.name for c in version.checks}
    assert names["plan_price_intro"] == "Introductory plan price"
    assert all("_" not in n for n in names.values())
    assert Check(check_id="plan_price_intro", type="factual", critical=True,
                 crm_field="x").name == "Plan price intro"
