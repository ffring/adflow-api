from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel, Field
from services.llm import llm_service

T = TypeVar("T", bound=BaseModel)


class TaskType(str, Enum):
    ANALYZE = "analyze"
    CREATE = "create"
    REVIEW = "review"
    REVISE = "revise"


class AgentTask(BaseModel):
    """A task for an agent to execute."""

    task_type: TaskType
    description: str
    input_data: Any = None
    context: dict = Field(default_factory=dict)
    max_retries: int = 3


class AgentResponse(BaseModel):
    """Response from an agent."""

    success: bool
    output: Any = None
    error_message: Optional[str] = None
    reasoning: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewResult(BaseModel):
    """Result of a review by PM."""

    approved: bool
    score: int = Field(default=0, ge=0, le=10, description="Quality score 0-10")
    feedback: str = ""
    revision_instructions: Optional[str] = None
    critical_issues: list[str] = Field(default_factory=list)


class BaseAgent(ABC):
    """Base class for all agents."""

    name: str
    role: str
    system_prompt: str

    def __init__(self):
        self.llm = llm_service

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResponse:
        """Execute a task and return response."""
        pass

    async def complete(
        self,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Simple text completion."""
        return await self.llm.complete(
            system_prompt=self.system_prompt,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def complete_structured(
        self,
        user_message: str,
        output_schema: Type[T],
        temperature: float = 0.5,
        max_tokens: int = 4096,
    ) -> T:
        """Structured completion with Pydantic model output."""
        return await self.llm.complete_structured(
            system_prompt=self.system_prompt,
            user_message=user_message,
            output_schema=output_schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def format_context(self, context: dict) -> str:
        """Format context dict into readable string for prompt."""
        parts = []
        for key, value in context.items():
            if isinstance(value, BaseModel):
                value = value.model_dump_json(indent=2, exclude_none=True)
            elif isinstance(value, dict):
                import json

                value = json.dumps(value, indent=2, ensure_ascii=False)
            parts.append(f"## {key.replace('_', ' ').title()}\n{value}")
        return "\n\n".join(parts)
