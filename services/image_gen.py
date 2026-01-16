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
    """Service for generating banners via kie.ai (nano-banana) API."""

    def __init__(self):
        self.settings = get_settings()

    @property
    def mock_mode(self) -> bool:
        """Use mock mode if API key is not configured."""
        return not self.settings.nano_banana_api_key

    async def generate_banner(self, request: BannerRequest) -> BannerResponse:
        """Generate a banner image."""
        if self.mock_mode:
            return await self._mock_generate(request)
        else:
            return await self._real_generate(request)

    async def _mock_generate(self, request: BannerRequest) -> BannerResponse:
        """Mock banner generation - returns placeholder image."""
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
        """Real banner generation via kie.ai (nano-banana) API."""
        # Build detailed prompt for advertising banner
        full_prompt = self._build_prompt(request)

        async with httpx.AsyncClient(timeout=120.0) as client:
            # kie.ai API endpoint
            response = await client.post(
                f"{self.settings.nano_banana_api_url}/generate",
                headers={
                    "Authorization": f"Bearer {self.settings.nano_banana_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": full_prompt,
                    "width": request.width,
                    "height": request.height,
                    "style": "professional advertising banner",
                    "negative_prompt": "blurry, low quality, distorted text, watermark, logo",
                },
            )

            if response.status_code != 200:
                # Fallback to mock on error
                print(f"Image gen API error: {response.status_code} - {response.text}")
                return await self._mock_generate(request)

            data = response.json()

            return BannerResponse(
                image_url=data.get("image_url", data.get("url", "")),
                width=data.get("width", request.width),
                height=data.get("height", request.height),
                prompt_used=full_prompt,
            )

    def _build_prompt(self, request: BannerRequest) -> str:
        """Build detailed prompt for banner generation."""
        parts = [
            "Professional advertising banner design",
            f"Size: {request.width}x{request.height} pixels",
            f"Content: {request.prompt}",
        ]

        if request.text_overlay:
            parts.append(f"Main text overlay: '{request.text_overlay}'")

        if request.brand_colors:
            parts.append(f"Brand colors: {', '.join(request.brand_colors)}")

        parts.extend([
            "Style: clean, modern, minimalist",
            "High contrast, readable text",
            "Professional corporate design",
            "No watermarks, no stock photo marks",
        ])

        return ". ".join(parts)

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
