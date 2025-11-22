"""
Конфигурация приложения.
Загружает настройки из .env файла и предоставляет удобный доступ к ним.
"""

import os
from pathlib import Path
from typing import List, Tuple
from dotenv import load_dotenv

# Загрузить .env файл
load_dotenv()

# Базовая директория проекта
BASE_DIR = Path(__file__).parent.parent


class Config:
    """Конфигурация приложения."""

    # Telegram API
    TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE", "")

    # BotHub API
    BOTHUB_API_KEY = os.getenv("BOTHUB_API_KEY", "")
    BOTHUB_API_URL = "https://bothub.chat/api/v2/openai/v1"

    # ID чата для отправки отчетов
    REPORT_CHAT_ID = os.getenv("REPORT_CHAT_ID", "")

    # Каналы для мониторинга
    @staticmethod
    def get_channels() -> List[Tuple[str, str]]:
        """
        Получить список каналов для мониторинга.

        Returns:
            List[Tuple[str, str]]: Список кортежей (идентификатор, тип)
                где тип: 'channel' или 'chat'
        """
        channels_str = os.getenv("CHANNELS", "")
        if not channels_str:
            return []

        channels = []
        for item in channels_str.split(","):
            item = item.strip()
            if ":" in item:
                identifier, channel_type = item.split(":", 1)
                channels.append((identifier.strip(), channel_type.strip()))
            else:
                # По умолчанию считаем каналом
                channels.append((item, "channel"))

        return channels

    # База данных
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/gazeta.db")

    # Timezone
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

    # Настройки отчета
    REPORT_TIME = os.getenv("REPORT_TIME", "09:00")
    REPORT_TITLE = os.getenv("REPORT_TITLE", "📰 Дневная сводка")

    # Логирование
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/gazeta.log")

    # Session file для Telethon
    SESSION_NAME = "gazeta_session"

    @classmethod
    def validate(cls) -> List[str]:
        """
        Проверить корректность конфигурации.

        Returns:
            List[str]: Список ошибок, пустой список если все ок
        """
        errors = []

        if not cls.TELEGRAM_API_ID or cls.TELEGRAM_API_ID == 0:
            errors.append("TELEGRAM_API_ID не установлен")

        if not cls.TELEGRAM_API_HASH:
            errors.append("TELEGRAM_API_HASH не установлен")

        if not cls.TELEGRAM_PHONE:
            errors.append("TELEGRAM_PHONE не установлен")

        if not cls.BOTHUB_API_KEY:
            errors.append("BOTHUB_API_KEY не установлен")

        if not cls.REPORT_CHAT_ID:
            errors.append("REPORT_CHAT_ID не установлен")

        channels = cls.get_channels()
        if not channels:
            errors.append("Не указаны каналы для мониторинга (CHANNELS)")

        return errors

    @classmethod
    def ensure_directories(cls):
        """Создать необходимые директории."""
        # Директория для базы данных
        db_dir = Path(cls.DATABASE_PATH).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        # Директория для логов
        if cls.LOG_FILE:
            log_dir = Path(cls.LOG_FILE).parent
            log_dir.mkdir(parents=True, exist_ok=True)


# Экземпляр конфигурации
config = Config()
