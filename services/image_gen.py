from typing import Optional
from pydantic import BaseModel
import httpx
from config import get_settings


class BannerRequest(BaseModel):
    """Request for banner generation."""

    prompt: str
    width: int = 1080
    height: int = 607
    style: str = "advertising"
    text_overlay: Optional[str] = None
    brand_colors: list[str] = []


class BannerResponse(BaseModel):
    """Response from banner generation."""

    image_url: str
    width: int
    height: int
    prompt_used: str


class ImageGenService:
    """Service for generating banners via nano-banana API (or mock)."""

    def __init__(self):
        self.settings = get_settings()
        self.mock_mode = True  # Will switch to False when API is available

    async def generate_banner(self, request: BannerRequest) -> BannerResponse:
        """Generate a banner image."""
        if self.mock_mode:
            return await self._mock_generate(request)
        else:
            return await self._real_generate(request)

    async def _mock_generate(self, request: BannerRequest) -> BannerResponse:
        """Mock banner generation - returns placeholder image."""
        # Use placeholder.com or similar service for mock
        placeholder_url = (
            f"https://placehold.co/{request.width}x{request.height}/1a1a2e/eee"
            f"?text=Banner+{request.width}x{request.height}"
        )

        return BannerResponse(
            image_url=placeholder_url,
            width=request.width,
            height=request.height,
            prompt_used=request.prompt,
        )

    async def _real_generate(self, request: BannerRequest) -> BannerResponse:
        """Real banner generation via nano-banana API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.settings.nano_banana_api_url}/generate",
                headers={
                    "Authorization": f"Bearer {self.settings.nano_banana_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": request.prompt,
                    "width": request.width,
                    "height": request.height,
                    "style": request.style,
                    "text_overlay": request.text_overlay,
                    "brand_colors": request.brand_colors,
                },
            )
            response.raise_for_status()
            data = response.json()

            return BannerResponse(
                image_url=data["image_url"],
                width=data.get("width", request.width),
                height=data.get("height", request.height),
                prompt_used=data.get("prompt", request.prompt),
            )

    async def generate_batch(self, requests: list[BannerRequest]) -> list[BannerResponse]:
        """Generate multiple banners."""
        results = []
        for req in requests:
            result = await self.generate_banner(req)
            results.append(result)
        return results

    def get_sizes_for_platform(self, platform: str) -> list[tuple[int, int]]:
        """Get recommended banner sizes for a platform."""
        sizes = {
            "yandex_direct": [
                (1080, 607),  # 16:9
                (450, 450),  # 1:1
                (300, 250),  # Medium rectangle
                (728, 90),  # Leaderboard
                (160, 600),  # Wide skyscraper
            ],
            "vk_ads": [
                (1080, 607),  # 16:9
                (1080, 1080),  # 1:1
                (600, 600),  # Carousel card
            ],
            "telegram_ads": [],  # No images in TG Ads
        }
        return sizes.get(platform, [(1080, 607)])


# Global instance
image_gen_service = ImageGenService()
