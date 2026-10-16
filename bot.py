import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-6")
MAX_HISTORY = 20  # сколько последних сообщений помнить на пользователя

SYSTEM_PROMPT = (
    "Ты — LumenAi, дружелюбный и умный ИИ-ассистент в Telegram. "
    "Отвечай на языке пользователя, понятно и по делу. "
    "Если не знаешь ответа — честно скажи об этом."
)

logging.basicConfig(level=logging.INFO)

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
dp = Dispatcher()
ai = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# user_id -> список сообщений [{"role": ..., "content": ...}]
histories: dict[int, list[dict]] = {}


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Привет! Я LumenAi — твой ИИ-ассистент.\n"
        "Просто напиши мне любой вопрос.\n\n"
        "/reset — очистить память диалога\n"
        "/help — помощь"
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "Я отвечаю на вопросы, пишу тексты, помогаю с кодом и идеями.\n"
        "/reset — начать диалог заново."
    )


@dp.message(Command("reset"))
async def reset(message: Message):
    histories.pop(message.from_user.id, None)
    await message.answer("🧹 Память диалога очищена.")


@dp.message(F.text)
async def chat(message: Message):
    user_id = message.from_user.id
    history = histories.setdefault(user_id, [])
    history.append({"role": "user", "content": message.text})
    del history[:-MAX_HISTORY]
    # история должна начинаться с сообщения пользователя
    while history and history[0]["role"] != "user":
        history.pop(0)

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        response = await ai.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=history,
        )
        answer = "".join(b.text for b in response.content if b.type == "text")
    except Exception:
        logging.exception("AI error")
        history.pop()  # убираем неудачный запрос
        await message.answer("⚠️ Что-то пошло не так, попробуй ещё раз позже.")
        return

    history.append({"role": "assistant", "content": answer})

    # Telegram ограничивает сообщение 4096 символами
    for i in range(0, len(answer), 4000):
        await message.answer(answer[i : i + 4000])


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
