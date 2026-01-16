from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AdPlatform(str, Enum):
    """Рекламные платформы и каналы."""

    # Яндекс
    YANDEX_DIRECT = "yandex_direct"  # Яндекс.Директ (РСЯ, поиск)
    YANDEX_BUSINESS = "yandex_business"  # Яндекс.Бизнес (карточки)

    # VK экосистема
    VK_ADS = "vk_ads"  # VK Реклама (таргет)
    VK_MARKET = "vk_market"  # VK Маркет

    # Telegram
    TELEGRAM_ADS = "telegram_ads"  # Telegram Ads (официальная реклама)
    TELEGRAM_SEEDING = "telegram_seeding"  # Посевы в TG каналах

    # Другие
    GOOGLE_ADS = "google_ads"  # Google Ads (для международных)
    META_ADS = "meta_ads"  # Meta (Instagram/Facebook)


class AdFormat(str, Enum):
    """Форматы рекламных креативов."""

    # Яндекс Директ
    YD_TEXT = "yd_text"  # Текстовое объявление на поиске
    YD_TEXT_IMAGE = "yd_text_image"  # Текстово-графическое (РСЯ)
    YD_SMART_BANNER = "yd_smart_banner"  # Смарт-баннер
    YD_VIDEO = "yd_video"  # Видео

    # VK
    VK_UNIVERSAL = "vk_universal"  # Универсальное объявление
    VK_CAROUSEL = "vk_carousel"  # Карусель
    VK_STORIES = "vk_stories"  # Истории
    VK_CLIPS = "vk_clips"  # Клипы

    # Telegram
    TG_ADS_TEXT = "tg_ads_text"  # Telegram Ads текст
    TG_SEEDING_POST = "tg_seeding_post"  # Пост для посева
    TG_SEEDING_FORWARD = "tg_seeding_forward"  # Репост с канала

    # Общие
    BANNER_HORIZONTAL = "banner_horizontal"  # 16:9
    BANNER_SQUARE = "banner_square"  # 1:1
    BANNER_VERTICAL = "banner_vertical"  # 9:16


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
    recommended: bool = Field(default=False, description="Рекомендуется стратегом")
    priority: int = Field(default=1, ge=1, le=5, description="Приоритет канала (1=высший)")
    min_budget_rub: int = Field(default=0, description="Минимальный бюджет для канала")
    expected_cpa_range: str = Field(default="", description="Ожидаемая стоимость конверсии")


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
