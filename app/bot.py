import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal, init_db
from app.models import User, UserSkill, Attempt
from app.services import get_question, calculate_score, level_for_score, random_scenario

router = Router()
MODULES = {
    "fire": "🔥 Огонь", "water": "💧 Вода", "navigation": "🧭 Навигация",
    "shelter": "🏕️ Лагерь", "first_aid": "🩹 Первая помощь", "winter": "❄️ Зима",
}
PENDING: dict[int, dict] = {}


def module_keyboard():
    kb = InlineKeyboardBuilder()
    for key, name in MODULES.items():
        kb.button(text=name, callback_data=f"module:{key}")
    kb.adjust(2)
    return kb.as_markup()


def question_keyboard(question: dict):
    kb = InlineKeyboardBuilder()
    for i, option in enumerate(question["options"]):
        kb.button(text=option, callback_data=f"answer:{question['id']}:{i}")
    kb.adjust(1)
    return kb.as_markup()


async def ensure_user(message: Message) -> User:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=message.from_user.id, username=message.from_user.username,
                        first_name=message.from_user.first_name)
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user


async def ensure_skill(session, user_id: int, module: str) -> UserSkill:
    result = await session.execute(select(UserSkill).where(UserSkill.user_id == user_id, UserSkill.module == module))
    skill = result.scalar_one_or_none()
    if not skill:
        skill = UserSkill(user_id=user_id, module=module)
        session.add(skill)
        await session.flush()
    return skill


@router.message(Command("start"))
async def start(message: Message):
    await ensure_user(message)
    await message.answer(
        "🏕️ <b>TAIGA Survival Bot</b>\n\n"
        "Тренажёр автономности: теория → тест → практика → сценарий.\n\n"
        "Начни с /training. В экстренной ситуации приоритет — безопасность, связь и эвакуация.",
        parse_mode="HTML")


@router.message(Command("training"))
async def training(message: Message):
    await ensure_user(message)
    await message.answer("Выбери модуль:", reply_markup=module_keyboard())


@router.callback_query(F.data.startswith("module:"))
async def module_selected(callback: CallbackQuery):
    module = callback.data.split(":", 1)[1]
    question = get_question(module, 2)
    if not question:
        await callback.answer("Модуль пока пуст", show_alert=True)
        return
    PENDING[callback.from_user.id] = {"module": module, "question": question}
    await callback.message.edit_text(
        f"<b>{MODULES[module]}</b>\n\n{question['question']}",
        reply_markup=question_keyboard(question), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("answer:"))
async def answer(callback: CallbackQuery):
    _, question_id, raw_index = callback.data.split(":")
    pending = PENDING.get(callback.from_user.id)
    if not pending or pending["question"]["id"] != question_id:
        await callback.answer("Задание устарело. Запусти /training заново.", show_alert=True)
        return
    question = pending["question"]
    module = pending["module"]
    selected = int(raw_index)
    correct = selected == question["answer"]
    async with SessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == callback.from_user.id))).scalar_one()
        skill = await ensure_skill(session, user.id, module)
        skill.attempts += 1
        skill.correct += int(correct)
        skill.score = calculate_score(skill.score, correct)
        session.add(Attempt(user_id=user.id, module=module, question_id=question_id,
                            answer=str(selected), is_correct=correct))
        await session.commit()
        score = skill.score
    PENDING.pop(callback.from_user.id, None)
    status = "✅ Правильно" if correct else "❌ Неправильно"
    await callback.message.edit_text(
        f"{status}\n\n<b>Объяснение:</b> {question['explanation']}\n\n"
        f"Навык: <b>{score:.0f}%</b> — {level_for_score(score)}\n\nСледующая тренировка: /training",
        parse_mode="HTML")
    await callback.answer()


@router.message(Command("profile"))
async def profile(message: Message):
    await ensure_user(message)
    async with SessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == message.from_user.id))).scalar_one()
        skills = (await session.execute(select(UserSkill).where(UserSkill.user_id == user.id))).scalars().all()
    if not skills:
        await message.answer("📊 Профиль пока пуст. Пройди тренировку: /training")
        return
    lines = ["📊 <b>Профиль навыков</b>"]
    for skill in skills:
        lines.append(f"{MODULES.get(skill.module, skill.module)}: {skill.score:.0f}% ({skill.correct}/{skill.attempts})")
    avg = sum(s.score for s in skills) / len(skills)
    lines.append(f"\nУровень: <b>{level_for_score(avg)}</b>\nСредний навык: {avg:.0f}%")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("scenario"))
async def scenario(message: Message):
    await ensure_user(message)
    item = random_scenario()
    kb = InlineKeyboardBuilder()
    for i, option in enumerate(item["options"]):
        kb.button(text=option, callback_data=f"scenario:{item['id']}:{i}")
    kb.adjust(1)
    await message.answer(f"⚠️ <b>{item['title']}</b>\n\n{item['text']}\n\nЧто делать первым?",
                         reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("scenario:"))
async def scenario_answer(callback: CallbackQuery):
    _, scenario_id, raw_index = callback.data.split(":")
    # Reload the small trusted scenario dataset instead of trusting callback text.
    from app.services import DATA
    import json
    scenarios = json.loads((DATA / "scenarios.json").read_text(encoding="utf-8"))
    item = next((x for x in scenarios if x["id"] == scenario_id), None)
    if not item:
        await callback.answer("Сценарий не найден", show_alert=True)
        return
    ok = int(raw_index) == item["answer"]
    await callback.message.edit_text(
        ("✅ Верное решение" if ok else "❌ Решение требует исправления") +
        f"\n\n{item['explanation']}\n\nНовый сценарий: /scenario", parse_mode="HTML")
    await callback.answer()


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer("/start — запуск\n/training — тренировка\n/profile — прогресс\n/scenario — ЧС\n/help — помощь")


async def main():
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    for attempt in range(10):
        try:
            await init_db()
            break
        except Exception:
            if attempt == 9:
                raise
            logging.exception("Database unavailable; retrying")
            await asyncio.sleep(3)
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
