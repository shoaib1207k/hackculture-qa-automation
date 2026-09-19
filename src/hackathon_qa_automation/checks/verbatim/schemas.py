"""What the verbatim agent returns. It extracts and cites; Python decides."""

from typing import Optional

from pydantic import BaseModel, Field


class ElementResult(BaseModel):
    element: str = Field(description="The required element, copied exactly as given.")
    present: bool = Field(
        description="True only if the AGENT clearly conveyed every part of the element.")
    quote: Optional[str] = Field(
        description="The exact words the agent said that convey it, copied character for "
                    "character. Null if the element is not present.")
    segment_ids: list[str] = Field(
        description="The single segment ID the quote appears in. Empty if not present.")
    confidence: float = Field(ge=0.0, le=1.0,
                              description="How sure you are of the present/absent judgement.")


class VerbatimExtraction(BaseModel):
    elements: list[ElementResult]
    reasoning: str
