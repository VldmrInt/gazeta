"""
Модуль для работы с базой данных SQLite.
Хранит информацию о каналах, сообщениях и отчетах.
"""

import aiosqlite
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с SQLite базой данных."""

    def __init__(self, db_path: str):
        """
        Инициализация подключения к базе данных.

        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None

        # Создать директорию для БД, если не существует
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        """Установить соединение с базой данных."""
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row
        await self.init_schema()
        logger.info(f"Подключено к базе данных: {self.db_path}")

    async def disconnect(self):
        """Закрыть соединение с базой данных."""
        if self.connection:
            await self.connection.close()
            logger.info("Отключено от базы данных")

    async def init_schema(self):
        """Создать схему базы данных, если она не существует."""
        async with self.connection.cursor() as cursor:
            # Таблица источников (каналы и чаты)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier TEXT UNIQUE NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT,
                    username TEXT,
                    last_updated TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица сообщений
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    date TIMESTAMP NOT NULL,
                    text TEXT,
                    link TEXT,
                    sender_id INTEGER,
                    sender_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (source_id) REFERENCES sources (id),
                    UNIQUE(source_id, message_id)
                )
            """)

            # Таблица отчетов
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    sent_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Индексы для быстрого поиска
            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_date
                ON messages(date)
            """)

            await cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_source
                ON messages(source_id, date)
            """)

            await self.connection.commit()
            logger.info("Схема базы данных инициализирована")

    # === Методы для работы с источниками ===

    async def add_source(
        self, identifier: str, source_type: str, title: str = None, username: str = None
    ) -> int:
        """
        Добавить или обновить источник.

        Args:
            identifier: Идентификатор канала/чата
            source_type: Тип ('channel' или 'chat')
            title: Название канала/чата
            username: Username канала/чата

        Returns:
            ID источника
        """
        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO sources (identifier, type, title, username, last_updated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(identifier) DO UPDATE SET
                    title = COALESCE(?, title),
                    username = COALESCE(?, username),
                    last_updated = ?
                """,
                (
                    identifier,
                    source_type,
                    title,
                    username,
                    datetime.now(),
                    title,
                    username,
                    datetime.now(),
                ),
            )
            await self.connection.commit()

            # Получить ID
            await cursor.execute(
                "SELECT id FROM sources WHERE identifier = ?", (identifier,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_source_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Получить источник по идентификатору.

        Args:
            identifier: Идентификатор канала/чата

        Returns:
            Словарь с данными источника или None
        """
        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM sources WHERE identifier = ?", (identifier,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_sources(self) -> List[Dict[str, Any]]:
        """
        Получить все источники.

        Returns:
            Список словарей с данными источников
        """
        async with self.connection.cursor() as cursor:
            await cursor.execute("SELECT * FROM sources ORDER BY created_at")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # === Методы для работы с сообщениями ===

    async def add_message(
        self,
        source_id: int,
        message_id: int,
        date: datetime,
        text: str = None,
        link: str = None,
        sender_id: int = None,
        sender_name: str = None,
    ) -> bool:
        """
        Добавить сообщение в базу данных.

        Args:
            source_id: ID источника
            message_id: ID сообщения в Telegram
            date: Дата сообщения
            text: Текст сообщения
            link: Ссылка на сообщение
            sender_id: ID отправителя
            sender_name: Имя отправителя

        Returns:
            True если добавлено, False если уже существовало
        """
        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO messages (source_id, message_id, date, text, link, sender_id, sender_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (source_id, message_id, date, text, link, sender_id, sender_name),
                )
                await self.connection.commit()
                return True
        except aiosqlite.IntegrityError:
            # Сообщение уже существует
            return False

    async def get_messages_by_date_range(
        self, start_date: datetime, end_date: datetime, source_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Получить сообщения за период времени.

        Args:
            start_date: Начало периода
            end_date: Конец периода
            source_id: ID источника (опционально)

        Returns:
            Список словарей с данными сообщений
        """
        async with self.connection.cursor() as cursor:
            if source_id:
                await cursor.execute(
                    """
                    SELECT m.*, s.identifier, s.type, s.title, s.username
                    FROM messages m
                    JOIN sources s ON m.source_id = s.id
                    WHERE m.date >= ? AND m.date < ? AND m.source_id = ?
                    ORDER BY m.date
                    """,
                    (start_date, end_date, source_id),
                )
            else:
                await cursor.execute(
                    """
                    SELECT m.*, s.identifier, s.type, s.title, s.username
                    FROM messages m
                    JOIN sources s ON m.source_id = s.id
                    WHERE m.date >= ? AND m.date < ?
                    ORDER BY m.date
                    """,
                    (start_date, end_date),
                )

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_messages_grouped_by_source(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Получить сообщения за период, сгруппированные по источникам.

        Args:
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Словарь {идентификатор_источника: [сообщения]}
        """
        messages = await self.get_messages_by_date_range(start_date, end_date)

        grouped = {}
        for msg in messages:
            identifier = msg["identifier"]
            if identifier not in grouped:
                grouped[identifier] = []
            grouped[identifier].append(msg)

        return grouped

    # === Методы для работы с отчетами ===

    async def save_report(self, date: str, content: str) -> int:
        """
        Сохранить отчет.

        Args:
            date: Дата отчета (YYYY-MM-DD)
            content: Содержание отчета

        Returns:
            ID отчета
        """
        async with self.connection.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO reports (date, content)
                VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET content = ?
                """,
                (date, content, content),
            )
            await self.connection.commit()
            return cursor.lastrowid

    async def mark_report_sent(self, report_id: int):
        """
        Отметить отчет как отправленный.

        Args:
            report_id: ID отчета
        """
        async with self.connection.cursor() as cursor:
            await cursor.execute(
                "UPDATE reports SET sent_at = ? WHERE id = ?",
                (datetime.now(), report_id),
            )
            await self.connection.commit()

    async def get_report_by_date(self, date: str) -> Optional[Dict[str, Any]]:
        """
        Получить отчет по дате.

        Args:
            date: Дата отчета (YYYY-MM-DD)

        Returns:
            Словарь с данными отчета или None
        """
        async with self.connection.cursor() as cursor:
            await cursor.execute("SELECT * FROM reports WHERE date = ?", (date,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    # === Утилиты ===

    async def get_stats(self) -> Dict[str, int]:
        """
        Получить статистику базы данных.

        Returns:
            Словарь со статистикой
        """
        async with self.connection.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM sources")
            sources_count = (await cursor.fetchone())[0]

            await cursor.execute("SELECT COUNT(*) FROM messages")
            messages_count = (await cursor.fetchone())[0]

            await cursor.execute("SELECT COUNT(*) FROM reports")
            reports_count = (await cursor.fetchone())[0]

            return {
                "sources": sources_count,
                "messages": messages_count,
                "reports": reports_count,
            }
