import hashlib
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
from openai import AsyncOpenAI
from config import settings


class Translator:
    """Batch translation from English to Chinese with caching."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or settings.TRANSLATION_CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)
        self.client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self._cache: Dict[str, str] = {}

    def _get_cache_path(self, text_hash: str) -> Path:
        """Get cache file path for a text hash."""
        return self.cache_dir / f"{text_hash}.json"

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
            "hash": text_hash
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def translate_single(self, text: str) -> str:
        """Translate a single text to Chinese."""
        # Check cache first
        cached = self._load_from_cache(text)
        if cached:
            return cached

        # Call DeepSeek API
        response = await self.client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional translator. Translate the following English text to Chinese. Be faithful to the original, preserve professional terminology, and do not add extra explanations."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.3,
            max_tokens=2048
        )

        translation = response.choices[0].message.content.strip()

        # Save to cache
        self._save_to_cache(text, translation)

        return translation

    async def translate_batch(
        self,
        texts: List[str],
        max_concurrency: int = 5
    ) -> List[str]:
        """Translate multiple texts concurrently with rate limiting."""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def translate_with_limit(text: str) -> str:
            async with semaphore:
                return await self.translate_single(text)

        tasks = [translate_with_limit(text) for text in texts]
        return await asyncio.gather(*tasks)

    def translate_batch_sync(self, texts: List[str]) -> List[str]:
        """Synchronous wrapper for batch translation."""
        return asyncio.run(self.translate_batch(texts))
