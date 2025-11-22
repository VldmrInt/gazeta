"""
Модуль для работы с Telegram API через Telethon.
Обеспечивает подключение к Telegram и получение сообщений.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat, User, Message
from telethon.errors import SessionPasswordNeededError
import asyncio

logger = logging.getLogger(__name__)


class TelegramService:
    """Сервис для работы с Telegram."""

    def __init__(self, api_id: int, api_hash: str, phone: str, session_name: str = "session"):
        """
        Инициализация Telegram клиента.

        Args:
            api_id: API ID из my.telegram.org
            api_hash: API Hash из my.telegram.org
            phone: Номер телефона
            session_name: Имя файла сессии
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.client: Optional[TelegramClient] = None

    async def connect(self):
        """Подключиться к Telegram."""
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start(phone=self.phone)

        if not await self.client.is_user_authorized():
            logger.info("Требуется авторизация")
            await self.client.send_code_request(self.phone)
            try:
                await self.client.sign_in(self.phone)
            except SessionPasswordNeededError:
                logger.error("Требуется 2FA пароль")
                raise

        logger.info("Успешно подключено к Telegram")

    async def disconnect(self):
        """Отключиться от Telegram."""
        if self.client:
            await self.client.disconnect()
            logger.info("Отключено от Telegram")

    async def get_entity_info(self, identifier: str) -> Dict[str, Any]:
        """
        Получить информацию о канале/чате.

        Args:
            identifier: Username (@channel) или ID канала/чата

        Returns:
            Словарь с информацией
        """
        try:
            entity = await self.client.get_entity(identifier)

            info = {
                "id": entity.id,
                "type": self._get_entity_type(entity),
                "title": getattr(entity, "title", None),
                "username": getattr(entity, "username", None),
            }

            return info
        except Exception as e:
            logger.error(f"Ошибка получения информации о {identifier}: {e}")
            raise

    def _get_entity_type(self, entity) -> str:
        """
        Определить тип entity.

        Args:
            entity: Telegram entity

        Returns:
            'channel', 'chat', или 'user'
        """
        if isinstance(entity, Channel):
            return "channel" if entity.broadcast else "chat"
        elif isinstance(entity, Chat):
            return "chat"
        elif isinstance(entity, User):
            return "user"
        else:
            return "unknown"

    async def get_messages(
        self,
        identifier: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = None,
    ) -> List[Dict[str, Any]]:
        """
        Получить сообщения из канала/чата за период.

        Args:
            identifier: Username или ID канала/чата
            start_date: Начало периода
            end_date: Конец периода
            limit: Максимальное количество сообщений

        Returns:
            Список сообщений
        """
        messages = []

        try:
            entity = await self.client.get_entity(identifier)
            entity_type = self._get_entity_type(entity)

            logger.info(f"Получение сообщений из {identifier} ({entity_type}) "
                       f"с {start_date} по {end_date}")

            # Получить сообщения
            async for message in self.client.iter_messages(
                entity,
                offset_date=end_date,
                reverse=False,
                limit=limit,
            ):
                # Проверить, что сообщение в нужном диапазоне
                if message.date < start_date:
                    break

                if message.date >= end_date:
                    continue

                # Извлечь информацию о сообщении
                msg_data = await self._extract_message_data(message, entity)
                messages.append(msg_data)

            logger.info(f"Получено {len(messages)} сообщений из {identifier}")
            return messages

        except Exception as e:
            logger.error(f"Ошибка получения сообщений из {identifier}: {e}")
            return []

    async def _extract_message_data(
        self, message: Message, entity
    ) -> Dict[str, Any]:
        """
        Извлечь данные из сообщения.

        Args:
            message: Telegram сообщение
            entity: Канал/чат

        Returns:
            Словарь с данными сообщения
        """
        # Получить текст сообщения
        text = message.text or message.message or ""

        # Создать ссылку на сообщение
        link = await self._create_message_link(entity, message)

        # Информация об отправителе (для чатов)
        sender_id = None
        sender_name = None

        if message.sender:
            sender_id = message.sender_id
            if hasattr(message.sender, "first_name"):
                sender_name = message.sender.first_name
                if hasattr(message.sender, "last_name") and message.sender.last_name:
                    sender_name += f" {message.sender.last_name}"
            elif hasattr(message.sender, "title"):
                sender_name = message.sender.title

        return {
            "message_id": message.id,
            "date": message.date,
            "text": text,
            "link": link,
            "sender_id": sender_id,
            "sender_name": sender_name,
        }

    async def _create_message_link(self, entity, message: Message) -> str:
        """
        Создать ссылку на сообщение.

        Args:
            entity: Канал/чат
            message: Сообщение

        Returns:
            Ссылка на сообщение
        """
        if hasattr(entity, "username") and entity.username:
            # Публичный канал/чат
            return f"https://t.me/{entity.username}/{message.id}"
        else:
            # Приватный канал/чат
            # Для приватных чатов используем формат c/chat_id/message_id
            chat_id = str(entity.id).replace("-100", "")
            return f"https://t.me/c/{chat_id}/{message.id}"

    async def send_message(
        self, chat_id: str, text: str, parse_mode: str = "HTML"
    ) -> bool:
        """
        Отправить сообщение в чат.

        Args:
            chat_id: ID чата
            text: Текст сообщения
            parse_mode: Режим парсинга ('HTML' или 'Markdown')

        Returns:
            True если успешно отправлено
        """
        try:
            # Разбить длинное сообщение на части (Telegram лимит ~4096 символов)
            max_length = 4000
            if len(text) <= max_length:
                await self.client.send_message(
                    chat_id, text, parse_mode=parse_mode
                )
            else:
                # Разбить на части
                parts = self._split_message(text, max_length)
                for i, part in enumerate(parts):
                    await self.client.send_message(
                        chat_id, part, parse_mode=parse_mode
                    )
                    # Небольшая задержка между частями
                    if i < len(parts) - 1:
                        await asyncio.sleep(0.5)

            logger.info(f"Сообщение отправлено в {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в {chat_id}: {e}")
            return False

    def _split_message(self, text: str, max_length: int) -> List[str]:
        """
        Разбить длинное сообщение на части.

        Args:
            text: Исходный текст
            max_length: Максимальная длина части

        Returns:
            Список частей
        """
        parts = []
        current_part = ""

        lines = text.split("\n")

        for line in lines:
            # Если добавление строки превысит лимит
            if len(current_part) + len(line) + 1 > max_length:
                if current_part:
                    parts.append(current_part)
                    current_part = ""

                # Если одна строка больше лимита, разбить её
                if len(line) > max_length:
                    while len(line) > max_length:
                        parts.append(line[:max_length])
                        line = line[max_length:]
                    current_part = line
                else:
                    current_part = line
            else:
                if current_part:
                    current_part += "\n"
                current_part += line

        if current_part:
            parts.append(current_part)

        return parts

    async def resolve_username(self, username: str) -> Optional[int]:
        """
        Получить ID по username.

        Args:
            username: Username (с @ или без)

        Returns:
            ID или None
        """
        try:
            entity = await self.client.get_entity(username)
            return entity.id
        except Exception as e:
            logger.error(f"Не удалось найти {username}: {e}")
            return None
