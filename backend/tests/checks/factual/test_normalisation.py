"""The parked rule-based normalisers. Nothing in the pipeline uses them yet."""

import pytest

from hackathon_qa_automation.checks.factual.normalisation import values_match


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
