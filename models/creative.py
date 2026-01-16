from typing import Optional
from pydantic import BaseModel, Field
from .strategy import AdPlatform


class YandexCreative(BaseModel):
    """Creative for Yandex.Direct (RSY)."""

    headline: str = Field(..., max_length=56, description="Main headline (max 56 chars)")
    text: str = Field(..., max_length=81, description="Ad text (max 81 chars)")
    quick_links: list[str] = Field(
        default_factory=list, max_length=4, description="Up to 4 quick links, 30 chars each"
    )
    image_url: Optional[str] = Field(None, description="Banner image URL")
    image_size: str = Field(default="1080x607", description="Image dimensions")


class VKCreative(BaseModel):
    """Creative for VK Ads."""

    headline: str = Field(..., max_length=40, description="Headline (max 40 chars)")
    text: str = Field(..., max_length=220, description="Ad text (recommended max 220)")
    text_full: Optional[str] = Field(None, max_length=2000, description="Full text if needed")
    image_url: Optional[str] = None
    image_size: str = Field(default="1080x607", description="Image dimensions")
    button_text: Optional[str] = Field(None, max_length=25)


class TelegramCreative(BaseModel):
    """Creative for Telegram Ads."""

    text: str = Field(..., max_length=160, description="Ad text (max 160 chars)")
    button_text: str = Field(..., max_length=25, description="CTA button text")
    button_url: Optional[str] = None


class Creative(BaseModel):
    """A single creative."""

    id: str
    hypothesis_id: str = Field(..., description="Which hypothesis this tests")
    platform: AdPlatform
    variant: str = Field(default="A", description="A/B variant identifier")
    yandex: Optional[YandexCreative] = None
    vk: Optional[VKCreative] = None
    telegram: Optional[TelegramCreative] = None


class CreativeSet(BaseModel):
    """Set of creatives for a project."""

    creatives: list[Creative] = Field(default_factory=list)
    total_by_platform: dict[str, int] = Field(default_factory=dict)

    def count_by_platform(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.creatives:
            platform = c.platform.value
            counts[platform] = counts.get(platform, 0) + 1
        return counts


class BannerSpec(BaseModel):
    """Specification for banner generation."""

    creative_id: str
    platform: AdPlatform
    size: str  # e.g., "1080x607"
    headline: str
    text: Optional[str] = None
    style_hints: str = ""
    brand_colors: list[str] = Field(default_factory=list)


class Banner(BaseModel):
    """Generated banner."""

    id: str
    creative_id: str
    spec: BannerSpec
    image_url: str
    generated_at: str
