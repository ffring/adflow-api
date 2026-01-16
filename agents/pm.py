from typing import Optional
from pydantic import BaseModel, Field
from .base import BaseAgent, AgentTask, AgentResponse, ReviewResult, TaskType
from models.project import ProjectBrief, ProjectSettings
from models.artifact import Question


class AnalysisResult(BaseModel):
    """Result of website/channel analysis."""

    brief: ProjectBrief
    questions: list[Question]
    initial_observations: str = ""


class ProjectManagerAgent(BaseAgent):
    """Project Manager agent - coordinates the team and communicates with user."""

    name = "project_manager"
    role = "Project Manager"

    @property
    def system_prompt(self) -> str:
        from .prompts import PM_SYSTEM_PROMPT
        return PM_SYSTEM_PROMPT

    async def execute(self, task: AgentTask) -> AgentResponse:
        """Execute PM task."""
        try:
            if task.task_type == TaskType.ANALYZE:
                result = await self.analyze_source(task)
                return AgentResponse(success=True, output=result)
            elif task.task_type == TaskType.REVIEW:
                result = await self.review_work(task)
                return AgentResponse(success=True, output=result)
            else:
                return AgentResponse(
                    success=False, error_message=f"Unknown task type: {task.task_type}"
                )
        except Exception as e:
            return AgentResponse(success=False, error_message=str(e))

    async def analyze_source(self, task: AgentTask) -> AnalysisResult:
        """Analyze website or Telegram channel."""
        parsed_data = task.input_data

        prompt = f"""Проанализируй информацию о бизнесе и сформулируй бриф.

ДАННЫЕ ПАРСИНГА:
{self.format_context({'parsed_data': parsed_data})}

На основе этих данных:

1. Заполни бриф проекта:
   - business_name: название бизнеса
   - business_description: краткое описание (2-3 предложения)
   - products_services: список продуктов/услуг
   - unique_selling_points: уникальные преимущества
   - target_url: целевой URL
   - detected_niche: определённая ниша
   - detected_language: язык (ru/en)

2. Сформулируй 3-5 важных вопросов клиенту:
   - Бюджет (обязательно)
   - Цели рекламной кампании
   - Описание целевой аудитории (если не очевидно)
   - Ограничения или особые пожелания

Каждый вопрос должен иметь:
- id: уникальный идентификатор
- question: текст вопроса
- question_type: "text", "number", или "select"
- options: варианты ответа (для select)
- required: обязательный ли вопрос

3. Добавь свои наблюдения в initial_observations"""

        return await self.complete_structured(prompt, AnalysisResult)

    async def review_work(self, task: AgentTask) -> ReviewResult:
        """Review work from another agent."""
        work_type = task.context.get("work_type", "unknown")
        work_content = task.input_data
        criteria = task.context.get("criteria", [])

        prompt = f"""Проверь качество работы и дай оценку.

ТИП РАБОТЫ: {work_type}

СОДЕРЖИМОЕ:
{self.format_context({'content': work_content})}

КРИТЕРИИ ОЦЕНКИ:
{chr(10).join(f'- {c}' for c in criteria) if criteria else '- Общее качество и полнота'}

Оцени работу по шкале 0-10.
- 8-10: Отлично, можно принимать
- 5-7: Нормально, но есть замечания
- 0-4: Требует серьёзной доработки

Если оценка ниже 8, укажи конкретные проблемы и инструкции по исправлению."""

        return await self.complete_structured(prompt, ReviewResult)

    async def generate_final_summary(self, task: AgentTask) -> str:
        """Generate final package summary for user."""
        context = task.context

        prompt = f"""Подготовь финальное резюме рекламного пакета для клиента.

ДАННЫЕ ПРОЕКТА:
{self.format_context(context)}

Составь краткое, профессиональное резюме:
1. Что было сделано
2. Какие рекламные системы охвачены
3. Сколько креативов подготовлено
4. Ключевые рекомендации по запуску
5. Следующие шаги

Пиши кратко и по делу."""

        return await self.complete(prompt)
