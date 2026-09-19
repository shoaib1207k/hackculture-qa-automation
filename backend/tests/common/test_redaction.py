import pytest

from hackathon_qa_automation.common.redaction import redact_card_numbers, redact_segments
from hackathon_qa_automation.models import TranscriptSegment

MASK = "[CARD NUMBER REDACTED]"


@pytest.mark.parametrize("text", [
    "it is 4111111111111111 thanks",
    "4111 1111 1111 1111",
    "4111-1111-1111-1111",
    "3782 822463 10005",                    # 15 digits (amex layout)
    "4111 1111 1111 1112",                  # fails the card checksum: still hidden
])
def test_card_like_numbers_are_masked(text):
    out = redact_card_numbers(text)
    assert MASK in out and not any(c.isdigit() for c in out)


@pytest.mark.parametrize("text", [
    "0412 555 783",                         # phone
    "IPR-48291736",                         # account number
    "ECX-7319452",                          # reference number
    "2150",                                 # postcode
    "seventy two dollars and ninety",
])
def test_ordinary_numbers_are_left_alone(text):
    assert redact_card_numbers(text) == text


def test_segments_are_redacted_and_word_timings_dropped():
    seg = TranscriptSegment(segment_id="S1", speaker="CUSTOMER", start=0, end=1,
                            text="card 4111 1111 1111 1111", words=[])
    assert redact_segments([seg])[0].text == f"card {MASK}"
    assert seg.text == "card 4111 1111 1111 1111"  # the original is untouched
