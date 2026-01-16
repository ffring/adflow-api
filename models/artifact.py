from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    BRIEF = "brief"
    QUESTIONS = "questions"
    STRATEGY = "strategy"
    HYPOTHESES = "hypotheses"
    COPY = "copy"
    BANNERS = "banners"
    FINAL_PACKAGE = "final_package"


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"  # PM is reviewing
    REVISION = "revision"  # Sent back for revision
    APPROVED = "approved"
    USER_EDITED = "user_edited"  # User made changes


class Artifact(BaseModel):
    """An artifact produced during the pipeline."""

    id: str
    project_id: str
    type: ArtifactType
    status: ArtifactStatus = ArtifactStatus.PENDING
    version: int = 1
    content: Any = Field(default=None, description="Artifact content (type depends on artifact)")
    agent_name: str = Field(..., description="Which agent produced this")
    review_notes: Optional[str] = Field(None, description="PM review notes if revision needed")
    user_feedback: Optional[str] = Field(None, description="User feedback if any")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class Question(BaseModel):
    """A question for the user."""

    id: str
    question: str
    question_type: str = "text"  # text, select, multiselect, number, budget, channels
    options: Optional[list[str]] = None
    required: bool = True
    answer: Optional[str] = None
    category: str = Field(default="general", description="Категория: budget, goals, audience, channels, preferences")
    hint: Optional[str] = Field(None, description="Подсказка для пользователя")


class ClientInterview(BaseModel):
    """Структура интервью с клиентом."""

    # Бюджет
    budget_monthly: Optional[int] = Field(None, description="Месячный бюджет в рублях")
    budget_type: str = Field(default="flexible", description="fixed/flexible/test")
    test_budget: Optional[int] = Field(None, description="Бюджет на тестирование")

    # Цели
    primary_goal: str = Field(default="leads", description="leads/sales/awareness/traffic/installs")
    secondary_goals: list[str] = Field(default_factory=list)
    target_cpa: Optional[int] = Field(None, description="Целевая стоимость конверсии")
    target_monthly_leads: Optional[int] = Field(None, description="Целевое кол-во лидов/продаж")

    # Аудитория
    target_audience_description: str = Field(default="", description="Описание ЦА от клиента")
    geo: list[str] = Field(default_factory=lambda: ["Россия"], description="География")
    age_range: str = Field(default="", description="Возрастной диапазон")
    gender: str = Field(default="all", description="Пол: all/male/female")

    # Предпочтения по каналам
    preferred_platforms: list[str] = Field(default_factory=list, description="Какие каналы клиент предпочитает")
    excluded_platforms: list[str] = Field(default_factory=list, description="Какие каналы исключить")
    has_telegram_channel: bool = Field(default=False, description="Есть ли TG канал")
    telegram_channel_url: Optional[str] = None

    # Ограничения
    restrictions: list[str] = Field(default_factory=list, description="Ограничения по модерации/тематике")
    competitor_urls: list[str] = Field(default_factory=list, description="URL конкурентов")

    # Опыт
    previous_experience: str = Field(default="none", description="none/some/experienced")
    what_worked_before: str = Field(default="", description="Что работало раньше")
    what_failed_before: str = Field(default="", description="Что не сработало")


class QuestionsArtifact(BaseModel):
    """Questions artifact content."""

    questions: list[Question]
    all_answered: bool = False
    interview: Optional[ClientInterview] = Field(None, description="Заполненное интервью")
