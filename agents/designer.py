from pydantic import BaseModel, Field
from .base import BaseAgent, AgentTask, AgentResponse, TaskType
from models.creative import Banner, BannerSpec, CreativeSet
from models.strategy import AdPlatform
from services.image_gen import image_gen_service, BannerRequest


class BannerSet(BaseModel):
    """Set of generated banners."""

    banners: list[Banner] = Field(default_factory=list)
    total_count: int = 0


class DesignerAgent(BaseAgent):
    """Designer agent - creates banner images via image generation API."""

    name = "designer"
    role = "Art Director / Designer"

    @property
    def system_prompt(self) -> str:
        from .prompts import DESIGNER_SYSTEM_PROMPT
        return DESIGNER_SYSTEM_PROMPT

    async def execute(self, task: AgentTask) -> AgentResponse:
        """Execute designer task."""
        try:
            if task.task_type == TaskType.CREATE:
                result = await self.create_banners(task)
                return AgentResponse(success=True, output=result)
            elif task.task_type == TaskType.REVISE:
                result = await self.revise_banners(task)
                return AgentResponse(success=True, output=result)
            else:
                return AgentResponse(
                    success=False, error_message=f"Unknown task type: {task.task_type}"
                )
        except Exception as e:
            return AgentResponse(success=False, error_message=str(e))

    async def create_banners(self, task: AgentTask) -> BannerSet:
        """Create banners for creatives."""
        creatives: CreativeSet = task.context.get("creatives")
        brief = task.context.get("brief", {})
        strategy = task.context.get("strategy", {})

        if not creatives:
            return BannerSet(banners=[], total_count=0)

        # Generate banner specs using LLM
        specs = await self._generate_banner_specs(creatives, brief, strategy)

        # Generate actual banners
        banners = []
        for spec in specs:
            banner = await self._generate_banner(spec)
            banners.append(banner)

        return BannerSet(banners=banners, total_count=len(banners))

    async def _generate_banner_specs(
        self, creatives: CreativeSet, brief: dict, strategy: dict
    ) -> list[BannerSpec]:
        """Generate banner specifications using LLM."""

        # Filter creatives that need banners (not Telegram)
        visual_creatives = [
            c for c in creatives.creatives if c.platform != AdPlatform.TELEGRAM_ADS
        ]

        if not visual_creatives:
            return []

        prompt = f"""Создай технические задания для баннеров.

БРИФ:
{self.format_context({'brief': brief})}

СТРАТЕГИЯ:
{self.format_context({'strategy': strategy})}

КРЕАТИВЫ (нужны баннеры):
{self.format_context({'creatives': [c.model_dump() for c in visual_creatives]})}

Для каждого креатива создай спецификацию баннера:
- creative_id: ID креатива
- platform: платформа
- size: размер (например "1080x607")
- headline: заголовок для баннера
- text: дополнительный текст (опционально)
- style_hints: подсказки по стилю (цвета, настроение, элементы)
- brand_colors: основные цвета бренда (если известны)

Выбирай основной размер для каждой платформы:
- yandex_direct: 1080x607
- vk_ads: 1080x607

Создай по одному баннеру на креатив."""

        class BannerSpecList(BaseModel):
            specs: list[BannerSpec]

        result = await self.complete_structured(prompt, BannerSpecList)
        return result.specs

    async def _generate_banner(self, spec: BannerSpec) -> Banner:
        """Generate actual banner image."""
        import uuid
        from datetime import datetime

        # Parse size
        width, height = map(int, spec.size.split("x"))

        # Create prompt for image generation
        prompt = f"""Рекламный баннер: {spec.headline}
Стиль: {spec.style_hints}
Профессиональный, чистый дизайн для рекламы."""

        # Generate via service
        request = BannerRequest(
            prompt=prompt,
            width=width,
            height=height,
            style="advertising",
            text_overlay=spec.headline,
            brand_colors=spec.brand_colors,
        )

        response = await image_gen_service.generate_banner(request)

        return Banner(
            id=str(uuid.uuid4()),
            creative_id=spec.creative_id,
            spec=spec,
            image_url=response.image_url,
            generated_at=datetime.utcnow().isoformat(),
        )

    async def revise_banners(self, task: AgentTask) -> BannerSet:
        """Revise banners based on feedback."""
        original: BannerSet = task.input_data
        feedback = task.context.get("feedback", "")

        # For now, just regenerate with updated specs
        # In real implementation, would adjust prompts based on feedback

        prompt = f"""На основе обратной связи скорректируй спецификации баннеров.

ТЕКУЩИЕ БАННЕРЫ:
{self.format_context({'banners': [b.model_dump() for b in original.banners]})}

ОБРАТНАЯ СВЯЗЬ:
{feedback}

Обнови спецификации с учётом замечаний."""

        class BannerSpecList(BaseModel):
            specs: list[BannerSpec]

        result = await self.complete_structured(prompt, BannerSpecList)

        # Regenerate banners
        banners = []
        for spec in result.specs:
            banner = await self._generate_banner(spec)
            banners.append(banner)

        return BannerSet(banners=banners, total_count=len(banners))
