#!/usr/bin/env python3
"""
Gazeta - Система автоматического сбора сообщений из Telegram
и формирования дневных сводок.

Главный скрипт для запуска системы.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
import coloredlogs

# Добавить src в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.database import Database
from src.telegram_client import TelegramService
from src.bothub_client import BotHubClient
from src.collector import MessageCollector
from src.digest_generator import DigestGenerator
from src.report_formatter import ReportFormatter


# Настройка логирования
def setup_logging(log_level: str = "INFO"):
    """Настроить логирование."""
    # Создать директорию для логов
    if config.LOG_FILE:
        Path(config.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    # Формат логов
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Цветные логи для консоли
    coloredlogs.install(
        level=log_level,
        fmt=fmt,
        level_styles={
            "debug": {"color": "green"},
            "info": {"color": "cyan"},
            "warning": {"color": "yellow"},
            "error": {"color": "red"},
            "critical": {"color": "red", "bold": True},
        },
    )

    # Логи в файл
    if config.LOG_FILE:
        file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt))
        logging.getLogger().addHandler(file_handler)


logger = logging.getLogger(__name__)


async def collect_and_report(send_report: bool = True):
    """
    Собрать сообщения и сгенерировать отчет.

    Args:
        send_report: Отправить ли отчет в Telegram
    """
    # Проверить конфигурацию
    errors = config.validate()
    if errors:
        logger.error("Ошибки конфигурации:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("Проверьте файл .env")
        return

    # Создать необходимые директории
    config.ensure_directories()

    # Инициализировать компоненты
    db = Database(config.DATABASE_PATH)
    await db.connect()

    telegram = TelegramService(
        api_id=config.TELEGRAM_API_ID,
        api_hash=config.TELEGRAM_API_HASH,
        phone=config.TELEGRAM_PHONE,
        session_name=config.SESSION_NAME,
    )
    await telegram.connect()

    bothub = BotHubClient(
        api_key=config.BOTHUB_API_KEY,
        api_url=config.BOTHUB_API_URL,
    )

    collector = MessageCollector(telegram, db)
    digest_gen = DigestGenerator(bothub, db)
    formatter = ReportFormatter(title=config.REPORT_TITLE)

    try:
        # Получить список источников
        sources = config.get_channels()
        logger.info(f"Настроено {len(sources)} источников для мониторинга")

        # Собрать сообщения за вчерашний день
        logger.info("Начало сбора сообщений за вчерашний день...")
        stats = await collector.collect_yesterday(sources)

        logger.info(
            f"Собрано {stats['new_messages']} новых сообщений "
            f"из {stats['total_sources']} источников"
        )

        # Определить период (вчерашний день)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today - timedelta(days=1)
        yesterday_end = today

        # Получить сообщения из БД, сгруппированные по источникам
        messages_grouped = await db.get_messages_grouped_by_source(
            yesterday_start, yesterday_end
        )

        # Разделить на каналы и чаты
        channels_data = {}
        chats_data = {}

        for identifier, messages in messages_grouped.items():
            if not messages:
                continue

            source_type = messages[0]["type"]

            if source_type == "channel":
                channels_data[identifier] = messages
            elif source_type == "chat":
                # Для чатов нужно сгенерировать повестку дня
                source_info = await db.get_source_by_identifier(identifier)

                # Генерация повестки
                logger.info(f"Генерация повестки для {identifier}...")
                digest = await digest_gen.generate_digest_for_chat(
                    identifier, yesterday_start, yesterday_end
                )

                chats_data[identifier] = {
                    "info": source_info,
                    "digest": digest,
                    "messages": messages,
                }

        # Сформировать отчет
        logger.info("Формирование отчета...")
        report = formatter.format_daily_report(
            yesterday_start, channels_data, chats_data
        )

        # Сохранить отчет в БД
        date_str = yesterday_start.strftime("%Y-%m-%d")
        report_id = await db.save_report(date_str, report)
        logger.info(f"Отчет сохранен в БД (ID: {report_id})")

        # Отправить отчет в Telegram
        if send_report:
            logger.info(f"Отправка отчета в {config.REPORT_CHAT_ID}...")
            success = await telegram.send_message(
                config.REPORT_CHAT_ID, report, parse_mode="HTML"
            )

            if success:
                await db.mark_report_sent(report_id)
                logger.info("✅ Отчет успешно отправлен!")
            else:
                logger.error("❌ Не удалось отправить отчет")
        else:
            logger.info("Отчет не отправлен (режим тестирования)")
            # Показать первые 500 символов отчета
            preview = report[:500] + "..." if len(report) > 500 else report
            logger.info(f"Предпросмотр отчета:\n{preview}")

    except Exception as e:
        logger.error(f"Ошибка выполнения: {e}", exc_info=True)
    finally:
        # Закрыть соединения
        await telegram.disconnect()
        await db.disconnect()


async def test_connections():
    """Проверить подключения к Telegram и BotHub."""
    logger.info("Проверка подключений...")

    # Проверить конфигурацию
    errors = config.validate()
    if errors:
        logger.error("Ошибки конфигурации:")
        for error in errors:
            logger.error(f"  - {error}")
        return

    # Telegram
    telegram = TelegramService(
        api_id=config.TELEGRAM_API_ID,
        api_hash=config.TELEGRAM_API_HASH,
        phone=config.TELEGRAM_PHONE,
        session_name=config.SESSION_NAME,
    )

    try:
        await telegram.connect()
        logger.info("✅ Telegram: Подключено")

        # Попробовать получить информацию о первом источнике
        sources = config.get_channels()
        if sources:
            identifier, _ = sources[0]
            info = await telegram.get_entity_info(identifier)
            logger.info(f"✅ Тест получения данных: {info['title']}")

        await telegram.disconnect()
    except Exception as e:
        logger.error(f"❌ Telegram: {e}")

    # BotHub
    bothub = BotHubClient(
        api_key=config.BOTHUB_API_KEY,
        api_url=config.BOTHUB_API_URL,
    )

    try:
        result = await bothub.test_connection()
        if result:
            logger.info("✅ BotHub API: Доступно")
        else:
            logger.error("❌ BotHub API: Недоступно")
    except Exception as e:
        logger.error(f"❌ BotHub API: {e}")


@click.group()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="Уровень логирования",
)
def cli(log_level):
    """Gazeta - Система сбора сообщений из Telegram и формирования дневных сводок."""
    setup_logging(log_level)


@cli.command()
@click.option("--no-send", is_flag=True, help="Не отправлять отчет (только собрать)")
def run(no_send):
    """Запустить сбор сообщений и формирование отчета."""
    send = not no_send
    asyncio.run(collect_and_report(send_report=send))


@cli.command()
def test():
    """Проверить подключения к Telegram и BotHub."""
    asyncio.run(test_connections())


@cli.command()
def stats():
    """Показать статистику базы данных."""

    async def show_stats():
        db = Database(config.DATABASE_PATH)
        await db.connect()

        stats = await db.get_stats()
        logger.info("📊 Статистика базы данных:")
        logger.info(f"  Источников: {stats['sources']}")
        logger.info(f"  Сообщений: {stats['messages']}")
        logger.info(f"  Отчетов: {stats['reports']}")

        await db.disconnect()

    asyncio.run(show_stats())


if __name__ == "__main__":
    cli()
