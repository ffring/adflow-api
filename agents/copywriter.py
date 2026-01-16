from pydantic import BaseModel, Field
from .base import BaseAgent, AgentTask, AgentResponse, TaskType
from models.creative import Creative, CreativeSet, YandexCreative, VKCreative, TelegramCreative
from models.strategy import AdPlatform


class CopywriterAgent(BaseAgent):
    """Copywriter agent - creates ad copy for all platforms."""

    name = "copywriter"
    role = "Advertising Copywriter"

    @property
    def system_prompt(self) -> str:
        from .prompts import COPYWRITER_SYSTEM_PROMPT
        return COPYWRITER_SYSTEM_PROMPT

    async def execute(self, task: AgentTask) -> AgentResponse:
        """Execute copywriter task."""
        try:
            if task.task_type == TaskType.CREATE:
                result = await self.create_copy(task)
                return AgentResponse(success=True, output=result)
            elif task.task_type == TaskType.REVISE:
                result = await self.revise_copy(task)
                return AgentResponse(success=True, output=result)
            else:
                return AgentResponse(
                    success=False, error_message=f"Unknown task type: {task.task_type}"
                )
        except Exception as e:
            return AgentResponse(success=False, error_message=str(e))

    async def create_copy(self, task: AgentTask) -> CreativeSet:
        """Create ad copy for all hypotheses."""
        hypotheses = task.context.get("hypotheses", {})
        brief = task.context.get("brief", {})
        strategy = task.context.get("strategy", {})

        prompt = f"""Напиши рекламные тексты для всех гипотез.

БРИФ:
{self.format_context({'brief': brief})}

СТРАТЕГИЯ:
{self.format_context({'strategy': strategy})}

ГИПОТЕЗЫ:
{self.format_context({'hypotheses': hypotheses})}

Для каждой гипотезы создай креативы согласно указанному количеству (creatives_needed).
Каждый креатив должен быть уникальным вариантом для A/B тестирования.

Формат ответа - список креативов:

Для каждого креатива укажи:
- id: уникальный ID (c1, c2, c3...)
- hypothesis_id: ID гипотезы (h1, h2...)
- platform: yandex_direct, vk_ads или telegram_ads
- variant: буква варианта (A, B, C...)

В зависимости от платформы заполни соответствующее поле:

Для yandex_direct заполни поле yandex:
- headline: заголовок (до 56 символов!)
- text: текст (до 81 символа!)
- quick_links: быстрые ссылки (до 4 шт, по 30 символов)

Для vk_ads заполни поле vk:
- headline: заголовок (до 40 символов!)
- text: короткий текст (до 220 символов)
- text_full: полный текст если нужен (до 2000)
- button_text: текст кнопки (до 25 символов)

Для telegram_ads заполни поле telegram:
- text: текст объявления (до 160 символов! считай точно!)
- button_text: текст кнопки (до 25 символов)

ВАЖНО:
- Строго соблюдай лимиты символов
- Считай символы перед записью
- Создавай разнообразные варианты
- Учитывай тон коммуникации из стратегии

Также укажи total_by_platform - количество креативов по платформам."""

        return await self.complete_structured(prompt, CreativeSet)

    async def revise_copy(self, task: AgentTask) -> CreativeSet:
        """Revise copy based on feedback."""
        original = task.input_data
        feedback = task.context.get("feedback", "")

        prompt = f"""Доработай рекламные тексты на основе обратной связи.

ИСХОДНЫЕ ТЕКСТЫ:
{self.format_context({'original': original})}

ОБРАТНАЯ СВЯЗЬ:
{feedback}

Внеси необходимые изменения:
1. Исправь указанные проблемы
2. Сохрани общую структуру
3. Проверь соблюдение лимитов символов
4. Улучши качество текстов"""

        return await self.complete_structured(prompt, CreativeSet)
