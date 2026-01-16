import json
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel
import httpx
from config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMService:
    """Wrapper around OpenRouter API for agent interactions."""

    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=self.settings.openrouter_base_url,
                headers={
                    "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                    "HTTP-Referer": "https://adflow-web-b4t.pages.dev",
                    "X-Title": "AdFlow AI",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self.client

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Simple completion without structured output."""
        client = self._get_client()
        model = model or self.settings.llm_model_main

        response = await client.post(
            "/chat/completions",
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"]

    async def complete_structured(
        self,
        system_prompt: str,
        user_message: str,
        output_schema: Type[T],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.5,
    ) -> T:
        """Completion with structured JSON output parsed into Pydantic model."""
        model = model or self.settings.llm_model_main

        # Add JSON schema instruction to system prompt
        schema_json = json.dumps(output_schema.model_json_schema(), indent=2, ensure_ascii=False)
        full_system = f"""{system_prompt}

ВАЖНО: Твой ответ должен быть валидным JSON, соответствующим следующей схеме:
```json
{schema_json}
```

Отвечай ТОЛЬКО валидным JSON без дополнительного текста."""

        response_text = await self.complete(
            system_prompt=full_system,
            user_message=user_message,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Try to extract JSON from response
        json_text = self._extract_json(response_text)
        data = json.loads(json_text)

        return output_schema.model_validate(data)

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Multi-turn chat completion."""
        client = self._get_client()
        model = model or self.settings.llm_model_main

        all_messages = [{"role": "system", "content": system_prompt}] + messages

        response = await client.post(
            "/chat/completions",
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": all_messages,
            },
        )
        response.raise_for_status()
        data = response.json()

        return data["choices"][0]["message"]["content"]

    def _extract_json(self, text: str) -> str:
        """Extract JSON from response that might have markdown code blocks."""
        text = text.strip()

        # Try to find JSON in code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Try to find JSON object/array directly
        if text.startswith("{") or text.startswith("["):
            return text

        # Last resort: find first { and last }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return text[start:end]

        return text


# Global instance
llm_service = LLMService()
