from typing import AsyncIterator, Optional, List, Dict
import json
from openai import AsyncOpenAI
from config import settings


class LLMClient:
    """DeepSeek API client with streaming support."""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.model = settings.DEEPSEEK_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        context: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Generate a non-streaming response."""
        messages = [{"role": "system", "content": system_prompt}]

        if context:
            for ctx in context:
                messages.append(ctx)

        messages.append({"role": "user", "content": user_message})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=False
        )

        return response.choices[0].message.content

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

    def build_qa_prompt(
        self,
        query: str,
        contexts: List[Dict[str, str]]
    ) -> str:
        """Build prompt for RAG with deep synthesis of query and context."""
        # Build context with clear structure
        context_items = []
        for i, ctx in enumerate(contexts):
            context_items.append(f"""【参考资料 {i+1}】（来源：{ctx['source']}）
中文理解：{ctx['text_zh']}
英文原文：{ctx['text_en']}""")

        context_text = "\n\n---\n\n".join(context_items)

        prompt = f"""## 任务：基于检索结果进行哲学咨询式回答

### 用户的问题
{query}

### 从知识库检索到的相关参考资料
{context_text}

### 回答要求

请综合理解用户的问题和检索到的参考资料，以 Oscar Brenifier 的哲学咨询风格进行回答：

1. **问题理解**：首先识别用户问题的核心是什么
2. **知识联结**：将参考资料中的相关内容与用户问题关联起来
3. **哲学回应**：以苏格拉底式对话的风格回应，通过追问帮助用户深化理解
4. **引用标注**：回答中引用参考资料时用 [编号] 标注

### 回答风格
- 保持 Oscar 的直接、挑战但非评判的风格
- 用问题引导用户思考，而非直接给出答案
- 如参考资料中有相关的哲学观点或对话示例，可以结合进行阐述

请开始回答："""
        return prompt

    def build_system_prompt(self) -> str:
        """Build base system prompt for the assistant."""
        return """你是一个专业的哲学咨询师，擅长运用苏格拉底式追问法帮助用户深化自我认知和思考。

你的特点：
- 通过提问而非直接给出答案来引导用户
- 直接、清晰、挑战性的沟通风格
- 接受困惑和不确定是思考的正常部分
- 善于指出逻辑矛盾和模糊表述
- 结合东方哲学（如佛教）和西方哲学（如存在主义）的视角

在回答时，你会先理解用户的问题，然后结合检索到的哲学咨询记录和资料，以对话的方式引导用户深入思考。"""
