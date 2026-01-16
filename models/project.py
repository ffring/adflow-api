from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class ProjectStatus(str, Enum):
    CREATED = "created"
    ANALYZING = "analyzing"
    QUESTIONS = "questions"  # Waiting for user answers
    STRATEGY = "strategy"
    HYPOTHESES = "hypotheses"
    COPYWRITING = "copywriting"
    DESIGN = "design"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectCreate(BaseModel):
    """Input from user to create a project."""

    url: HttpUrl = Field(..., description="URL of website or Telegram channel")
    name: Optional[str] = Field(None, description="Project name (auto-generated if empty)")


class ProjectBrief(BaseModel):
    """Extracted info about the business."""

    business_name: str = ""
    business_description: str = ""
    products_services: list[str] = Field(default_factory=list)
    unique_selling_points: list[str] = Field(default_factory=list)
    target_url: str = ""
    detected_niche: str = ""
    detected_language: str = "ru"


class ProjectSettings(BaseModel):
    """User-provided settings after initial questions."""

    budget_monthly: Optional[int] = Field(None, description="Monthly budget in RUB")
    goals: list[str] = Field(default_factory=list, description="Campaign goals")
    target_audience_description: str = ""
    excluded_platforms: list[str] = Field(default_factory=list)
    brand_guidelines: Optional[str] = None
    competitors: list[str] = Field(default_factory=list)
    additional_notes: str = ""


class Project(BaseModel):
    """Main project model."""

    id: str = Field(..., description="Unique project ID")
    user_id: str = Field(..., description="Owner user ID")
    name: str
    url: str
    status: ProjectStatus = ProjectStatus.CREATED
    brief: Optional[ProjectBrief] = None
    settings: Optional[ProjectSettings] = None
    current_stage: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
