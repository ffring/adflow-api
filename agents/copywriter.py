from pydantic import BaseModel, Field
from .base import BaseAgent, AgentTask, AgentResponse, TaskType
from models.creative import Creative, CreativeSet, YandexCreative, VKCreative, TelegramCreative
from models.strategy import AdPlatform


class CopywriterAgent(BaseAgent):
    """Copywriter agent - creates ad copy for all platforms."""

    name = "copywriter"
    role = "Advertising Copywriter"
    system_prompt = """Ты — профессиональный копирайтер, специализирующийся на рекламных текстах.

Твоя экспертиза:
- Написание продающих заголовков и текстов
- Адаптация под разные рекламные площадки
- Соблюдение ограничений по символам
- Прохождение модерации рекламных систем

ОГРАНИЧЕНИЯ ПО ПЛОЩАДКАМ:

Яндекс.Директ (РСЯ):
- Заголовок: до 56 символов
- Текст: до 81 символа
- Быстрые ссылки: до 4 штук, по 30 символов каждая
- Запрещено: превосходная степень без доказательств, обещания гарантий

VK Реклама:
- Заголовок: до 40 символов
- Текст: до 220 символов (рекомендуется)
- Полный текст: до 2000 символов
- Запрещено: капс, множественные восклицательные знаки

Telegram Ads:
- Текст: до 160 символов (включая пробелы!)
- Кнопка: до 25 символов
- Только текст, без изображений
- Запрещено: эмодзи, кликбейт

ПРИНЦИПЫ РАБОТЫ:
1. Пиши кратко и ёмко
2. Используй конкретику вместо абстракций
3. Фокусируйся на выгоде для клиента
4. Создавай разные варианты для A/B тестов
5. Учитывай тон бренда из брифа
6. Избегай кликбейта и пустых обещаний"""

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
