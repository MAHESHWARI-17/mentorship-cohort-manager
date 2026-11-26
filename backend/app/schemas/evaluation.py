from typing import Dict, Literal

from pydantic import BaseModel, Field


class MentorEvaluationRequest(BaseModel):
    competencyScores: Dict[str, int]
    behaviorScores: Dict[str, int]
    strengths: str = Field(min_length=1, max_length=5000)
    growthAreas: str = Field(min_length=1, max_length=5000)
    recommendation: Literal["ready_now", "ready_with_coaching", "not_yet_ready"]
