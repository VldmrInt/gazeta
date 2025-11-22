"""
Модуль для генерации повестки дня из сообщений чатов.
Использует BotHub API для анализа обсуждений.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from .bothub_client import BotHubClient
from .database import Database

logger = logging.getLogger(__name__)


class DigestGenerator:
    """Генератор повестки дня из сообщений чатов."""

    def __init__(self, bothub: BotHubClient, database: Database):
        """
        Инициализация генератора.

        Args:
            bothub: Клиент BotHub API
            database: База данных
        """
        self.bothub = bothub
        self.database = database

    async def generate_digest_for_chat(
        self,
        identifier: str,
        start_date: datetime,
        end_date: datetime,
        max_topics: int = 7,
    ) -> Optional[str]:
        """
        Сгенерировать повестку дня для одного чата.

        Args:
            identifier: Идентификатор чата
            start_date: Начало периода
            end_date: Конец периода
            max_topics: Максимальное количество тем

        Returns:
            Повестка дня или None
        """
        logger.info(f"Генерация повестки для {identifier}")

        # Получить источник из БД
        source = await self.database.get_source_by_identifier(identifier)
        if not source:
            logger.error(f"Источник {identifier} не найден в БД")
            return None

        # Получить сообщения
        messages = await self.database.get_messages_by_date_range(
            start_date, end_date, source["id"]
        )

        if not messages:
            logger.warning(f"Нет сообщений из {identifier} за указанный период")
            return None

        # Подготовить текст для анализа
        message_texts = []
        for msg in messages:
            # Форматировать сообщение: [Автор] Текст
            if msg["sender_name"] and msg["text"]:
                formatted = f"[{msg['sender_name']}] {msg['text']}"
                message_texts.append(formatted)
            elif msg["text"]:
                message_texts.append(msg["text"])

        if not message_texts:
            logger.warning(f"Нет текстовых сообщений из {identifier}")
            return None

        # Ограничить количество сообщений, если их слишком много
        # (чтобы не превысить лимиты API)
        max_messages = 200
        if len(message_texts) > max_messages:
            # Взять равномерно распределённые сообщения
            step = len(message_texts) // max_messages
            message_texts = message_texts[::step][:max_messages]
            logger.info(
                f"Сообщений слишком много, взято {len(message_texts)} для анализа"
            )

        # Сгенерировать повестку через BotHub
        try:
            digest = await self.bothub.generate_digest(message_texts, max_topics=max_topics)
            logger.info(f"Повестка для {identifier} сгенерирована")
            return digest
        except Exception as e:
            logger.error(f"Ошибка генерации повестки для {identifier}: {e}")
            return None

    async def generate_digests_for_all_chats(
        self,
        start_date: datetime,
        end_date: datetime,
        max_topics: int = 7,
    ) -> Dict[str, str]:
        """
        Сгенерировать повестки для всех чатов.

        Args:
            start_date: Начало периода
            end_date: Конец периода
            max_topics: Максимальное количество тем

        Returns:
            Словарь {идентификатор_чата: повестка}
        """
        # Получить все источники типа 'chat'
        all_sources = await self.database.get_all_sources()
        chat_sources = [s for s in all_sources if s["type"] == "chat"]

        logger.info(f"Генерация повесток для {len(chat_sources)} чатов")

        digests = {}

        for source in chat_sources:
            identifier = source["identifier"]
            digest = await self.generate_digest_for_chat(
                identifier, start_date, end_date, max_topics
            )

            if digest:
                digests[identifier] = digest

        logger.info(f"Сгенерировано {len(digests)} повесток")
        return digests

    async def get_chat_message_count(
        self, identifier: str, start_date: datetime, end_date: datetime
    ) -> int:
        """
        Получить количество сообщений в чате за период.

        Args:
            identifier: Идентификатор чата
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Количество сообщений
        """
        source = await self.database.get_source_by_identifier(identifier)
        if not source:
            return 0

        messages = await self.database.get_messages_by_date_range(
            start_date, end_date, source["id"]
        )

        return len(messages)

    def format_digest(
        self, chat_title: str, chat_username: str, message_count: int, digest: str
    ) -> str:
        """
        Форматировать повестку дня для отображения.

        Args:
            chat_title: Название чата
            chat_username: Username чата
            message_count: Количество сообщений
            digest: Сгенерированная повестка

        Returns:
            Отформатированная повестка
        """
        header = f"💬 <b>{chat_title}</b>"
        if chat_username:
            header += f" (@{chat_username})"

        header += f"\n📊 Сообщений: {message_count}\n\n"
        header += "<b>Основные темы обсуждения:</b>\n\n"

        return header + digest
