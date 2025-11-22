"""
Модуль для форматирования отчетов.
Создаёт красивые HTML-отчеты для Telegram.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ReportFormatter:
    """Форматтер отчетов."""

    def __init__(self, title: str = "📰 Дневная сводка"):
        """
        Инициализация форматтера.

        Args:
            title: Заголовок отчета
        """
        self.title = title

    def format_daily_report(
        self,
        date: datetime,
        channels_data: Dict[str, List[Dict[str, Any]]],
        chats_data: Dict[str, Dict[str, Any]],
    ) -> str:
        """
        Сформировать дневной отчет.

        Args:
            date: Дата отчета
            channels_data: Данные каналов {identifier: [messages]}
            chats_data: Данные чатов {identifier: {info, digest, messages}}

        Returns:
            Отформатированный отчет в HTML
        """
        report_parts = []

        # Заголовок
        date_str = date.strftime("%d.%m.%Y")
        header = f"<b>{self.title}</b>\n"
        header += f"📅 {date_str}\n"
        header += "─" * 30 + "\n\n"
        report_parts.append(header)

        # Раздел с чатами (с повесткой дня)
        if chats_data:
            report_parts.append(self._format_chats_section(chats_data))

        # Раздел с каналами (просто посты)
        if channels_data:
            report_parts.append(self._format_channels_section(channels_data))

        # Футер со статистикой
        total_chats = len(chats_data)
        total_channels = len(channels_data)
        total_chat_messages = sum(
            len(data.get("messages", [])) for data in chats_data.values()
        )
        total_channel_messages = sum(len(msgs) for msgs in channels_data.values())

        footer = "\n" + "─" * 30 + "\n"
        footer += f"📊 <b>Статистика:</b>\n"
        footer += f"• Чатов: {total_chats} ({total_chat_messages} сообщений)\n"
        footer += f"• Каналов: {total_channels} ({total_channel_messages} постов)\n"

        report_parts.append(footer)

        return "".join(report_parts)

    def _format_chats_section(
        self, chats_data: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Форматировать раздел с чатами и повестками дня.

        Args:
            chats_data: Данные чатов

        Returns:
            Отформатированная секция
        """
        if not chats_data:
            return ""

        section = "🗨 <b>ОБСУЖДЕНИЯ В ЧАТАХ</b>\n\n"

        for identifier, data in chats_data.items():
            info = data.get("info", {})
            digest = data.get("digest", "")
            messages = data.get("messages", [])

            # Заголовок чата
            title = info.get("title", identifier)
            username = info.get("username", "")

            section += f"💬 <b>{title}</b>"
            if username:
                section += f" (@{username})"
            section += f"\n📊 Сообщений: {len(messages)}\n\n"

            # Повестка дня
            if digest:
                section += "<b>Основные темы:</b>\n"
                section += digest + "\n\n"
            else:
                section += "<i>Повестка дня не сгенерирована</i>\n\n"

            section += "─" * 25 + "\n\n"

        return section

    def _format_channels_section(
        self, channels_data: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Форматировать раздел с каналами.

        Args:
            channels_data: Данные каналов {identifier: [messages]}

        Returns:
            Отформатированная секция
        """
        if not channels_data:
            return ""

        section = "📢 <b>ПОСТЫ ИЗ КАНАЛОВ</b>\n\n"

        for identifier, messages in channels_data.items():
            if not messages:
                continue

            # Получить информацию о канале из первого сообщения
            first_msg = messages[0]
            title = first_msg.get("title", identifier)
            username = first_msg.get("username", "")

            section += f"📣 <b>{title}</b>"
            if username:
                section += f" (@{username})"
            section += f"\n📊 Постов: {len(messages)}\n\n"

            # Посты
            for msg in messages:
                section += self._format_message(msg)

            section += "─" * 25 + "\n\n"

        return section

    def _format_message(self, message: Dict[str, Any]) -> str:
        """
        Форматировать одно сообщение.

        Args:
            message: Данные сообщения

        Returns:
            Отформатированное сообщение
        """
        text = message.get("text", "")
        link = message.get("link", "")
        date = message.get("date")

        # Обрезать длинный текст
        max_length = 300
        if text and len(text) > max_length:
            text = text[:max_length] + "..."

        formatted = ""

        # Время
        if date:
            if isinstance(date, str):
                time_str = date
            else:
                time_str = date.strftime("%H:%M")
            formatted += f"🕐 {time_str} "

        # Текст
        if text:
            # Экранировать HTML специальные символы
            text = self._escape_html(text)
            formatted += text

        # Ссылка
        if link:
            formatted += f' <a href="{link}">↗</a>'

        formatted += "\n\n"

        return formatted

    def _escape_html(self, text: str) -> str:
        """
        Экранировать HTML специальные символы (базовая защита).

        Args:
            text: Исходный текст

        Returns:
            Экранированный текст
        """
        # Базовое экранирование для HTML
        replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def format_simple_list(
        self, title: str, messages: List[Dict[str, Any]]
    ) -> str:
        """
        Форматировать простой список сообщений.

        Args:
            title: Заголовок списка
            messages: Список сообщений

        Returns:
            Отформатированный список
        """
        result = f"<b>{title}</b>\n"
        result += f"Всего сообщений: {len(messages)}\n\n"

        for msg in messages:
            result += self._format_message(msg)

        return result

    def format_error_report(self, error: str) -> str:
        """
        Форматировать отчет об ошибке.

        Args:
            error: Описание ошибки

        Returns:
            Отформатированный отчет об ошибке
        """
        report = f"<b>⚠️ Ошибка формирования отчета</b>\n\n"
        report += f"{error}\n"
        return report
