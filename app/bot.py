import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings

router = Router()

MODULES = {
    "🔥 Огонь": "fire",
    "💧 Вода": "water",
    "🧭 Навигация": "navigation",
    "🏕️ Лагерь": "shelter",
    "🩹 Первая помощь": "first_aid",
    "❄️ Зима": "winter",
}


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer(
        "🏕️ TAIGA Survival Bot\n\n"
        "Тренажёр автономности: теория → тест → практика → сценарий.\n\n"
        "Команды:\n"
        "/training — начать тренировку\n"
        "/profile — профиль и навыки\n"
        "/scenario — аварийный сценарий\n"
        "/help — помощь"
    )


@router.message(Command("training"))
async def training(message: Message) -> None:
    text = "Выбери модуль тренировки:\n\n" + "\n".join(
        f"• {name}" for name in MODULES
    )
    await message.answer(text)


@router.message(Command("profile"))
async def profile(message: Message) -> None:
    await message.answer(
        "📊 Профиль\n\n"
        "Навыки пока не оценены. Пройди первую тренировку через /training."
    )


@router.message(Command("scenario"))
async def scenario(message: Message) -> None:
    await message.answer(
        "⚠️ Сценарий ЧС будет генерироваться из проверенной базы ситуаций.\n\n"
        "В критической ситуации приоритет — безопасность, связь со спасателями и эвакуация."
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "/start — запуск\n"
        "/training — тренировка\n"
        "/profile — прогресс\n"
        "/scenario — сценарий ЧС\n"
        "/help — помощь"
    )


async def main() -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
