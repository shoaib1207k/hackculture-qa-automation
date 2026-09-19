"""What the factual agents return. They extract and cite; Python decides."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class FactualExtraction(BaseModel):
    value: Optional[str] = Field(
        description="The final value the agent stated or confirmed, exactly as spoken. "
                    "Null if it was never stated.")
    quote: Optional[str] = Field(
        description="The exact words from the transcript the value was taken from, "
                    "copied character for character. Null if nothing was stated.")
    segment_ids: list[str] = Field(
        description="The single segment ID the quote appears in (more only if the value "
                    "spans consecutive turns).")
    confidence: float = Field(ge=0.0, le=1.0,
                              description="How sure you are that the value is exactly what was said.")
    reasoning: str


class FactualComparison(BaseModel):
    verdict: Literal["match", "mismatch", "uncertain"]
    confidence: float = Field(ge=0.0, le=1.0,
                              description="How sure you are of the verdict.")
    reasoning: str = Field(description="One or two sentences naming exactly what matched or differed.")
