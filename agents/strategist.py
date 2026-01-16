from pydantic import BaseModel, Field
from .base import BaseAgent, AgentTask, AgentResponse, TaskType
from models.strategy import Strategy, Hypothesis, HypothesesArtifact, AdPlatform


class StrategistAgent(BaseAgent):
    """Strategist agent - develops marketing strategy and hypotheses."""

    name = "strategist"
    role = "Marketing Strategist"

    @property
    def system_prompt(self) -> str:
        from .prompts import STRATEGIST_SYSTEM_PROMPT
        return STRATEGIST_SYSTEM_PROMPT

    async def execute(self, task: AgentTask) -> AgentResponse:
        """Execute strategist task."""
        try:
            if task.task_type == TaskType.CREATE:
                if task.context.get("output_type") == "hypotheses":
                    result = await self.create_hypotheses(task)
                else:
                    result = await self.create_strategy(task)
                return AgentResponse(success=True, output=result)
            elif task.task_type == TaskType.REVISE:
                result = await self.revise_work(task)
                return AgentResponse(success=True, output=result)
            else:
                return AgentResponse(
                    success=False, error_message=f"Unknown task type: {task.task_type}"
                )
        except Exception as e:
            return AgentResponse(success=False, error_message=str(e))

    async def create_strategy(self, task: AgentTask) -> Strategy:
        """Create marketing strategy based on brief."""
        brief = task.context.get("brief", {})
        settings = task.context.get("settings", {})

        prompt = f"""Разработай маркетинговую стратегию для рекламной кампании.

БРИФ:
{self.format_context({'brief': brief})}

НАСТРОЙКИ КЛИЕНТА:
{self.format_context({'settings': settings})}

Создай стратегию, включающую:

1. summary: Краткое резюме стратегии (2-3 предложения)

2. target_audiences: Сегменты целевой аудитории (1-3 сегмента)
   Для каждого сегмента укажи:
   - name: название сегмента
   - description: описание
   - demographics: демография
   - interests: интересы (список)
   - pain_points: боли/проблемы (список)
   - triggers: триггеры покупки (список)

3. platforms: Стратегия по платформам
   Для Яндекс.Директ, VK Реклама, Telegram Ads укажи:
   - platform: название платформы
   - enabled: использовать или нет (true/false)
   - formats: форматы рекламы (список)
   - targeting_approach: подход к таргетингу
   - creatives_count: количество креативов (5-20)
   - notes: заметки

4. budget_allocation: Распределение бюджета
   - platform: платформа
   - percentage: процент бюджета
   - rationale: обоснование

5. key_messages: Ключевые сообщения (3-5 штук)

6. tone_of_voice: Тон коммуникации

7. competitive_positioning: Позиционирование относительно конкурентов

8. success_metrics: Метрики успеха (3-5 штук)

Учитывай бюджет клиента при распределении и количестве креативов."""

        return await self.complete_structured(prompt, Strategy)

    async def create_hypotheses(self, task: AgentTask) -> HypothesesArtifact:
        """Create testing hypotheses based on strategy."""
        strategy = task.context.get("strategy", {})
        brief = task.context.get("brief", {})

        prompt = f"""На основе стратегии сформулируй гипотезы для тестирования.

СТРАТЕГИЯ:
{self.format_context({'strategy': strategy})}

БРИФ:
{self.format_context({'brief': brief})}

Создай список гипотез для A/B тестирования:

Для каждой гипотезы укажи:
- id: уникальный ID (h1, h2, h3...)
- name: короткое название гипотезы
- description: что тестируем
- target_audience: для какого сегмента ЦА
- platform: yandex_direct, vk_ads или telegram_ads
- message_angle: угол сообщения/оффер
- expected_outcome: ожидаемый результат
- priority: приоритет 1-5 (1 = высший)
- creatives_needed: сколько креативов нужно (2-5)

Правила:
- Создай 3-7 гипотез
- Каждая платформа должна иметь хотя бы 1 гипотезу (если включена в стратегии)
- Гипотезы должны тестировать разные углы: цена, качество, скорость, эмоции и т.д.
- Общее количество креативов не должно превышать лимиты из стратегии

Также укажи:
- total_creatives: общее количество креативов
- rationale: обоснование выбора гипотез"""

        return await self.complete_structured(prompt, HypothesesArtifact)

    async def revise_work(self, task: AgentTask) -> Strategy | HypothesesArtifact:
        """Revise strategy or hypotheses based on feedback."""
        original = task.input_data
        feedback = task.context.get("feedback", "")
        output_type = task.context.get("output_type", "strategy")

        prompt = f"""Доработай материал на основе обратной связи.

ИСХОДНЫЙ МАТЕРИАЛ:
{self.format_context({'original': original})}

ОБРАТНАЯ СВЯЗЬ:
{feedback}

Внеси необходимые изменения, сохраняя общую структуру.
Учти все замечания и улучши качество."""

        if output_type == "hypotheses":
            return await self.complete_structured(prompt, HypothesesArtifact)
        else:
            return await self.complete_structured(prompt, Strategy)
