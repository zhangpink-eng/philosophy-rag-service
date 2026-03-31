import hashlib
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Literal
from openai import AsyncOpenAI
from config import settings


class Translator:
    """
    Batch translation with caching.

    支持 DeepSeek 和 MiniMax 两种模型
    """

    def __init__(
        self,
        provider: Literal["deepseek", "minimax"] = "minimax",
        cache_dir: Optional[Path] = None
    ):
        self.provider = provider
        self.cache_dir = cache_dir or settings.TRANSLATION_CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)

        # 根据 provider 选择配置
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

        self._cache: Dict[str, str] = {}

    def _get_cache_path(self, text_hash: str) -> Path:
        """Get cache file path for a text hash."""
        return self.cache_dir / f"{self.provider}_{text_hash}.json"

    def _hash_text(self, text: str) -> str:
        """Generate hash for text."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _load_from_cache(self, text: str) -> Optional[str]:
        """Load translation from cache if exists."""
        text_hash = self._hash_text(text)
        cache_path = self._get_cache_path(text_hash)

        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("translation")
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def _save_to_cache(self, text: str, translation: str) -> None:
        """Save translation to cache."""
        text_hash = self._hash_text(text)
        cache_path = self._get_cache_path(text_hash)

        data = {
            "original": text,
            "translation": translation,
            "hash": text_hash,
            "provider": self.provider,
            "model": self.model
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_system_prompt(self, target_lang: str) -> str:
        """Get system prompt for translation direction."""
        if target_lang == "zh":
            return "You are a professional translator. Translate the following English text to Chinese. Be faithful to the original, preserve professional terminology, and do not add extra explanations."
        elif target_lang == "en":
            return "You are a professional translator. Translate the following Chinese text to English. Be faithful to the original, preserve professional terminology, and do not add extra explanations."
        else:
            return "You are a professional translator. Be faithful to the original, preserve professional terminology, and do not add extra explanations."

    async def translate_single(
        self,
        text: str,
        target_lang: str = "zh"
    ) -> str:
        """Translate a single text with fallback to DeepSeek."""
        # Check cache first
        cached = self._load_from_cache(text)
        if cached:
            return cached

        # Try MiniMax first
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(target_lang)
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                temperature=0.3,
                max_tokens=4096
            )
        except Exception as e:
            # Fallback to DeepSeek if MiniMax fails
            print(f"  MiniMax failed ({e}), trying DeepSeek...")
            from openai import AsyncOpenAI
            deepseek_client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL
            )
            response = await deepseek_client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(target_lang)
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                temperature=0.3,
                max_tokens=4096
            )

        raw_translation = response.choices[0].message.content

        # 清理 thinking tags (MiniMax 模型会输出思考过程)
        translation = self._clean_thinking_tags(raw_translation)

        # Save to cache
        self._save_to_cache(text, translation)

        return translation

    def _clean_thinking_tags(self, text: str) -> str:
        """清理 thinking/reasoning tags"""
        import re
        # 移除 <think>...</think> 标签及其内容
        cleaned = re.sub(r'<think>[\s\S]*?</think>', '', text)
        # 清理多余空白
        cleaned = ' '.join(cleaned.split())
        return cleaned.strip()

    async def translate_batch(
        self,
        texts: List[str],
        target_lang: str = "zh",
        max_concurrency: int = 5
    ) -> List[str]:
        """Translate multiple texts concurrently with rate limiting."""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def translate_with_limit(text: str) -> str:
            async with semaphore:
                return await self.translate_single(text, target_lang)

        tasks = [translate_with_limit(text) for text in texts]
        return await asyncio.gather(*tasks)

    def translate_batch_sync(
        self,
        texts: List[str],
        target_lang: str = "zh"
    ) -> List[str]:
        """Synchronous wrapper for batch translation."""
        return asyncio.run(self.translate_batch(texts, target_lang))


# 便捷函数：使用 MiniMax 翻译
def translate_texts(
    texts: List[str],
    target_lang: str = "zh"
) -> List[str]:
    """
    翻译文本列表（使用 MiniMax）

    Args:
        texts: 文本列表
        target_lang: 目标语言 "zh" 或 "en"

    Returns:
        翻译后的文本列表
    """
    translator = Translator(provider="minimax")
    return translator.translate_batch_sync(texts, target_lang)
