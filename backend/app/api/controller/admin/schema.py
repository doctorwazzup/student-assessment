from pydantic import BaseModel, Field


class StageGoal(BaseModel):
    stage: int
    thresholds: dict[str, str]
    goal: str | None = None


class GoalsUpdate(BaseModel):
    stages: list[StageGoal]


class SaveGoalsResponse(BaseModel):
    saved: bool
    updated_stages: list[int]
