from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    BRIEF = "brief"
    QUESTIONS = "questions"
    STRATEGY = "strategy"
    HYPOTHESES = "hypotheses"
    COPY = "copy"
    BANNERS = "banners"
    FINAL_PACKAGE = "final_package"


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"  # PM is reviewing
    REVISION = "revision"  # Sent back for revision
    APPROVED = "approved"
    USER_EDITED = "user_edited"  # User made changes


class Artifact(BaseModel):
    """An artifact produced during the pipeline."""

    id: str
    project_id: str
    type: ArtifactType
    status: ArtifactStatus = ArtifactStatus.PENDING
    version: int = 1
    content: Any = Field(default=None, description="Artifact content (type depends on artifact)")
    agent_name: str = Field(..., description="Which agent produced this")
    review_notes: Optional[str] = Field(None, description="PM review notes if revision needed")
    user_feedback: Optional[str] = Field(None, description="User feedback if any")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class Question(BaseModel):
    """A question for the user."""

    id: str
    question: str
    question_type: str = "text"  # text, select, multiselect, number
    options: Optional[list[str]] = None
    required: bool = True
    answer: Optional[str] = None


class QuestionsArtifact(BaseModel):
    """Questions artifact content."""

    questions: list[Question]
    all_answered: bool = False
