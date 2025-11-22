"""
Модуль для сбора сообщений из Telegram-каналов и чатов.
Координирует работу с Telegram API и базой данных.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from .telegram_client import TelegramService
from .database import Database

logger = logging.getLogger(__name__)


class MessageCollector:
    """Класс для сбора сообщений из Telegram источников."""

    def __init__(self, telegram: TelegramService, database: Database):
        """
        Инициализация коллектора.

        Args:
            telegram: Сервис для работы с Telegram
            database: База данных
        """
        self.telegram = telegram
        self.database = database

    async def collect_from_source(
        self,
        identifier: str,
        source_type: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Tuple[int, int]:
        """
        Собрать сообщения из одного источника.

        Args:
            identifier: Идентификатор канала/чата
            source_type: Тип источника ('channel' или 'chat')
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Кортеж (всего сообщений, новых сообщений)
        """
        logger.info(f"Сбор сообщений из {identifier} ({source_type})")

        try:
            # Получить информацию об источнике
            entity_info = await self.telegram.get_entity_info(identifier)

            # Добавить/обновить источник в БД
            source_id = await self.database.add_source(
                identifier=identifier,
                source_type=source_type,
                title=entity_info.get("title"),
                username=entity_info.get("username"),
            )

            # Получить сообщения
            messages = await self.telegram.get_messages(
                identifier, start_date, end_date
            )

            # Сохранить в БД
            new_messages = 0
            for msg in messages:
                is_new = await self.database.add_message(
                    source_id=source_id,
                    message_id=msg["message_id"],
                    date=msg["date"],
                    text=msg["text"],
                    link=msg["link"],
                    sender_id=msg["sender_id"],
                    sender_name=msg["sender_name"],
                )
                if is_new:
                    new_messages += 1

            logger.info(
                f"Из {identifier}: получено {len(messages)} сообщений, "
                f"новых: {new_messages}"
            )

            return len(messages), new_messages

        except Exception as e:
            logger.error(f"Ошибка сбора сообщений из {identifier}: {e}")
            return 0, 0

    async def collect_from_all_sources(
        self,
        sources: List[Tuple[str, str]],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, int]:
        """
        Собрать сообщения из всех источников.

        Args:
            sources: Список кортежей (идентификатор, тип)
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Статистика сбора
        """
        total_messages = 0
        total_new = 0
        failed_sources = []

        logger.info(
            f"Начало сбора сообщений из {len(sources)} источников "
            f"за период {start_date} - {end_date}"
        )

        for identifier, source_type in sources:
            try:
                messages_count, new_count = await self.collect_from_source(
                    identifier, source_type, start_date, end_date
                )
                total_messages += messages_count
                total_new += new_count

            except Exception as e:
                logger.error(f"Не удалось собрать из {identifier}: {e}")
                failed_sources.append(identifier)

        stats = {
            "total_sources": len(sources),
            "total_messages": total_messages,
            "new_messages": total_new,
            "failed_sources": len(failed_sources),
        }

        logger.info(
            f"Сбор завершён: {total_messages} сообщений "
            f"({total_new} новых) из {len(sources)} источников"
        )

        if failed_sources:
            logger.warning(f"Не удалось собрать из: {', '.join(failed_sources)}")

        return stats

    async def collect_yesterday(
        self, sources: List[Tuple[str, str]]
    ) -> Dict[str, int]:
        """
        Собрать сообщения за вчерашний день.

        Args:
            sources: Список источников

        Returns:
            Статистика сбора
        """
        # Определить вчерашний день (с 00:00 до 23:59:59)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today - timedelta(days=1)
        yesterday_end = today

        return await self.collect_from_all_sources(
            sources, yesterday_start, yesterday_end
        )

    async def collect_today(
        self, sources: List[Tuple[str, str]]
    ) -> Dict[str, int]:
        """
        Собрать сообщения за сегодняшний день (до текущего момента).

        Args:
            sources: Список источников

        Returns:
            Статистика сбора
        """
        # Определить сегодняшний день
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        now = datetime.now()

        return await self.collect_from_all_sources(sources, today_start, now)

    async def collect_last_n_hours(
        self, sources: List[Tuple[str, str]], hours: int
    ) -> Dict[str, int]:
        """
        Собрать сообщения за последние N часов.

        Args:
            sources: Список источников
            hours: Количество часов

        Returns:
            Статистика сбора
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        return await self.collect_from_all_sources(sources, start_time, end_time)
