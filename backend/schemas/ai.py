from typing import Optional
from pydantic import BaseModel, Field

class SummarizeIn(BaseModel):
    content: str = Field(min_length=1, description="Raw course content to summarize")
    prompt: Optional[str] = Field(
        default=None,
        description="Optional extra instruction, e.g. 'focus on formulas and definitions'",
    )
    max_words: int = Field(default=180, ge=60, le=800, description="Cap for summary length")
