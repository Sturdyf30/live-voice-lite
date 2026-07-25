from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class LanguageModel:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def respond(self, messages: list[dict[str, str]], user_text: str) -> str:
        full_messages = [
            {"role": "system", "content": self.settings.system_prompt},
            *messages,
            {"role": "user", "content": user_text},
        ]
        if self.settings.llm_backend == "openai_responses":
            return await self._responses_api(full_messages)
        return await self._chat_completions(full_messages)

    async def _chat_completions(self, messages: list[dict[str, str]]) -> str:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "stream": False,
            "max_tokens": self.settings.llm_max_output_tokens,
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.llm_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
        if response.status_code >= 400:
            detail = response.text[:1200]
            raise RuntimeError(f"LLM returned HTTP {response.status_code}: {detail}")

        body = response.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected chat-completions response: {body}") from exc

        if isinstance(content, list):
            content = "".join(
                str(part.get("text", "")) for part in content if isinstance(part, dict)
            )
        text = str(content).strip()
        if not text:
            raise RuntimeError("The language model returned an empty response.")
        return text

    async def _responses_api(self, messages: list[dict[str, str]]) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("Responses API mode requires the openai package.") from exc

        client = AsyncOpenAI(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
            timeout=self.settings.llm_timeout_seconds,
        )
        response = await client.responses.create(
            model=self.settings.llm_model,
            input=messages,
            max_output_tokens=self.settings.llm_max_output_tokens,
        )
        text = response.output_text.strip()
        if not text:
            raise RuntimeError("The Responses API returned an empty response.")
        return text
