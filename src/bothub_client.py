"""
Модуль для работы с BotHub API.
Используется для генерации повестки дня из сообщений чатов.
"""

import logging
import aiohttp
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class BotHubClient:
    """Клиент для работы с BotHub API."""

    def __init__(self, api_key: str, api_url: str = "https://bothub.chat/api/v2/openai/v1"):
        """
        Инициализация BotHub клиента.

        Args:
            api_key: API ключ BotHub
            api_url: URL API (по умолчанию BotHub OpenAI-compatible endpoint)
        """
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.chat_endpoint = f"{self.api_url}/chat/completions"

    async def generate_digest(
        self,
        messages: List[str],
        model: str = "openai/gpt-4o-mini",
        max_topics: int = 7,
    ) -> Optional[str]:
        """
        Сгенерировать повестку дня из сообщений чата.

        Args:
            messages: Список текстов сообщений
            model: Модель для использования
            max_topics: Максимальное количество тем

        Returns:
            Сгенерированная повестка дня или None в случае ошибки
        """
        if not messages:
            logger.warning("Нет сообщений для генерации повестки")
            return None

        # Объединить сообщения в один текст
        combined_text = "\n".join(messages)

        # Создать промпт
        prompt = self._create_digest_prompt(combined_text, max_topics)

        try:
            # Отправить запрос к API
            digest = await self._send_chat_request(prompt, model)
            return digest

        except Exception as e:
            logger.error(f"Ошибка генерации повестки через BotHub: {e}")
            return None

    def _create_digest_prompt(self, messages_text: str, max_topics: int) -> str:
        """
        Создать промпт для генерации повестки дня.

        Args:
            messages_text: Объединённый текст сообщений
            max_topics: Максимальное количество тем

        Returns:
            Промпт для модели
        """
        prompt = f"""Проанализируй следующие сообщения из чата и выдели {max_topics} основных тем обсуждения.

Требования:
1. Определи {max_topics} наиболее обсуждаемых или важных тем
2. Для каждой темы напиши краткое описание (1-2 предложения)
3. Отсортируй темы по важности/активности обсуждения
4. Используй понятный и лаконичный язык
5. Формат ответа:

🔹 <Название темы 1>
<Краткое описание темы>

🔹 <Название темы 2>
<Краткое описание темы>

...и т.д.

Сообщения для анализа:

{messages_text}

Повестка дня:"""

        return prompt

    async def _send_chat_request(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """
        Отправить запрос к chat completions API.

        Args:
            prompt: Промпт для модели
            model: Название модели
            temperature: Температура генерации
            max_tokens: Максимальное количество токенов

        Returns:
            Ответ модели
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.chat_endpoint, headers=headers, json=payload, timeout=60
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"BotHub API вернул статус {response.status}: {error_text}"
                    )

                data = await response.json()

                # Извлечь ответ
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    raise Exception("Некорректный ответ от BotHub API")

    async def test_connection(self) -> bool:
        """
        Проверить подключение к BotHub API.

        Returns:
            True если API доступно
        """
        try:
            response = await self._send_chat_request(
                "Привет! Ответь одним словом: 'работает'",
                model="openai/gpt-4o-mini",
                max_tokens=10,
            )
            logger.info(f"BotHub API доступно. Тестовый ответ: {response}")
            return True
        except Exception as e:
            logger.error(f"BotHub API недоступно: {e}")
            return False

    async def summarize_channel_posts(
        self, posts: List[str], model: str = "openai/gpt-4o-mini"
    ) -> Optional[str]:
        """
        Создать краткую сводку постов из канала (опционально).

        Args:
            posts: Список текстов постов
            model: Модель для использования

        Returns:
            Краткая сводка или None
        """
        if not posts:
            return None

        combined_text = "\n\n---\n\n".join(posts)

        prompt = f"""Вот посты из канала за день. Создай краткую сводку (2-3 предложения) о чём в основном были посты:

{combined_text}

Краткая сводка:"""

        try:
            summary = await self._send_chat_request(prompt, model, max_tokens=200)
            return summary
        except Exception as e:
            logger.error(f"Ошибка создания сводки постов: {e}")
            return None
