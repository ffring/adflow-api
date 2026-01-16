from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AdPlatform(str, Enum):
    YANDEX_DIRECT = "yandex_direct"
    VK_ADS = "vk_ads"
    TELEGRAM_ADS = "telegram_ads"


class TargetAudience(BaseModel):
    """Target audience segment."""

    name: str = Field(..., description="Segment name")
    description: str = ""
    demographics: str = ""
    interests: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list, description="What motivates them to buy")


class BudgetAllocation(BaseModel):
    """Budget allocation for a platform."""

    platform: AdPlatform
    percentage: int = Field(..., ge=0, le=100)
    amount_rub: Optional[int] = None
    rationale: str = ""


class PlatformStrategy(BaseModel):
    """Strategy for a specific platform."""

    platform: AdPlatform
    enabled: bool = True
    formats: list[str] = Field(default_factory=list, description="Ad formats to use")
    targeting_approach: str = ""
    creatives_count: int = Field(default=5, ge=1, le=50)
    notes: str = ""


class Strategy(BaseModel):
    """Marketing strategy artifact."""

    summary: str = Field(..., description="Executive summary of the strategy")
    target_audiences: list[TargetAudience] = Field(default_factory=list)
    platforms: list[PlatformStrategy] = Field(default_factory=list)
    budget_allocation: list[BudgetAllocation] = Field(default_factory=list)
    key_messages: list[str] = Field(default_factory=list)
    tone_of_voice: str = ""
    competitive_positioning: str = ""
    success_metrics: list[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    """A hypothesis for testing."""

    id: str
    name: str = Field(..., description="Short hypothesis name")
    description: str = Field(..., description="What we're testing")
    target_audience: str = Field(..., description="Which audience segment")
    platform: AdPlatform
    message_angle: str = Field(..., description="Main message/angle to test")
    expected_outcome: str = ""
    priority: int = Field(default=1, ge=1, le=5, description="1=highest priority")
    creatives_needed: int = Field(default=3, ge=1, le=10)


class HypothesesArtifact(BaseModel):
    """Hypotheses artifact content."""

    hypotheses: list[Hypothesis]
    total_creatives: int = 0
    rationale: str = ""
