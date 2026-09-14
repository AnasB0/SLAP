from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv


@dataclass(slots=True)
class LLMResponse:
    ok: bool
    content: str
    provider: str
    error: str | None = None


class OpenRouterClient:
    def __init__(self) -> None:
        load_dotenv()
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> LLMResponse:
        if not self.api_key:
            return LLMResponse(
                ok=False,
                content="OpenRouter is not configured. The deterministic SLA tools are still available. Add OPENROUTER_API_KEY to .env to enable LLM reasoning.",
                provider="fallback",
                error="Missing OPENROUTER_API_KEY",
            )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return LLMResponse(ok=True, content=content, provider="openrouter")
        except Exception as exc:
            return LLMResponse(
                ok=False,
                content="OpenRouter is temporarily unavailable. The application will continue with deterministic investigation and mitigation behavior.",
                provider="fallback",
                error=str(exc),
            )
