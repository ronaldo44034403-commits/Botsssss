# запуск: python bots.py (три бота одним процессом)
import asyncio
import logging
import os

from common import load_env

load_env()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import b1_studio
import b2_helper
import b3_games

BOTS = [("BOT1_TOKEN", b1_studio), ("BOT2_TOKEN", b2_helper), ("BOT3_TOKEN", b3_games)]


def make_startup(mod):
    async def startup(bot: Bot):
        await bot.set_my_commands(mod.COMMANDS)
        me = await bot.get_me()
        print(f"бот @{me.username} запущен")
        if hasattr(mod, "on_startup"):
            await mod.on_startup(bot)
    return startup


async def main():
    logging.basicConfig(level=logging.WARNING)
    jobs = []
    for env_name, mod in BOTS:
        token = os.getenv(env_name)
        if not token:
            raise SystemExit(f"нет {env_name} в .env")
        bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        dp.include_router(mod.router())
        dp.startup.register(make_startup(mod))
        jobs.append(dp.start_polling(bot, handle_signals=False))
    res = await asyncio.gather(*jobs, return_exceptions=True)
    for env_name, e in zip(BOTS, res):
        if isinstance(e, Exception):
            print("упал", env_name[0], e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("стоп")
