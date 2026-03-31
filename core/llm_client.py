from typing import AsyncIterator, Optional, List, Dict
import json
import re
import asyncio
from openai import AsyncOpenAI
from config import settings


class LLMClient:
    """Multi-provider LLM client (DeepSeek / MiniMax)."""

    def __init__(self, provider: str = "deepseek"):
        self.provider = provider
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

        if provider == "minimax":
            self.client = AsyncOpenAI(
                api_key=settings.MINIMAX_API_KEY,
                base_url=settings.MINIMAX_BASE_URL
            )
            self.model = settings.MINIMAX_MODEL
        else:
            self.client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL
            )
            self.model = settings.DEEPSEEK_MODEL

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        context: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Generate a non-streaming response with automatic retry."""
        messages = [{"role": "system", "content": system_prompt}]

        if context:
            for ctx in context:
                messages.append(ctx)

        messages.append({"role": "user", "content": user_message})

        # 重试策略：最多3次，间隔2s/4s/8s
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    stream=False
                )
                raw = response.choices[0].message.content
                return self._strip_thinking_content(raw)
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    await asyncio.sleep(wait)
                else:
                    raise e

    def _strip_thinking_content(self, text: str) -> str:
        """去掉回复开头的思考过程描述 `<think>...</think>`"""
        if not text:
            return text
        text = re.sub(r'^[\s\n]*<think>[\s\S]*?</think>', '', text, count=1)
        return text.strip()

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        context: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[str]:
        """Generate a streaming response."""
        messages = [{"role": "system", "content": system_prompt}]

        if context:
            for ctx in context:
                messages.append(ctx)

        messages.append({"role": "user", "content": user_message})

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
