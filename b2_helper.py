# бот 2: личный помощник (задачи напоминания калькулятор и утилиты)
import asyncio
import base64
import hashlib
import re
import secrets
import string
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BotCommand, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from common import esc, q, reg, safe_edit
from logic import fmt_secs, parse_duration, safe_calc

COMMANDS = [
    BotCommand(command="todo", description="Список задач"),
    BotCommand(command="add", description="Добавить задачу"),
    BotCommand(command="remind", description="Напоминание: /remind 1h30m текст"),
    BotCommand(command="reminders", description="Мои напоминания"),
    BotCommand(command="calc", description="Калькулятор"),
    BotCommand(command="pass", description="Генератор пароля"),
    BotCommand(command="hash", description="Хэши текста"),
    BotCommand(command="b64", description="Base64 enc или dec"),
    BotCommand(command="time", description="Время в городе"),
    BotCommand(command="roll", description="Кубики 2d6"),
    BotCommand(command="id", description="Мой id"),
]

HELP = (
    "<b>Помощник</b>\n"
    "/add текст и /todo список задач\n"
    "/remind 1h30m текст напоминание (s m h d или с м ч д)\n"
    "/calc 2+2*3 калькулятор\n"
    "/pass 20 пароль\n"
    "/hash текст хэши\n"
    "/b64 enc текст или /b64 dec строка\n"
    "/time Asia/Tokyo время в зоне\n"
    "/roll 2d6 кубики\n"
    "/id твой id"
)

_tasks = set()


def todo_view(uid):
    rows = q("SELECT * FROM todos WHERE uid=? ORDER BY done, id", (uid,))
    if not rows:
        return "Список пуст. Добавь: /add купить хлеб", None
    b = InlineKeyboardBuilder()
    lines = []
    for t in rows:
        lines.append(("✔ <s>" if t["done"] else "• ") + esc(t["text"]) + ("</s>" if t["done"] else ""))
        b.button(text=("Вернуть: " if t["done"] else "Готово: ") + t["text"][:24], callback_data=f"td:{t['id']}")
    b.button(text="Убрать выполненные", callback_data="tdclear")
    b.adjust(1)
    return "<b>Задачи</b>\n" + "\n".join(lines), b.as_markup()


async def reminder_loop(bot: Bot):
    while True:
        try:
            for r in q("SELECT * FROM reminders WHERE sent=0 AND at<=?", (int(time.time()),)):
                q("UPDATE reminders SET sent=1 WHERE id=?", (r["id"],))
                await bot.send_message(r["chat_id"], f"Напоминание: {esc(r['text'])}")
        except Exception as e:
            print("напоминания:", e)
        await asyncio.sleep(5)


async def on_startup(bot: Bot):
    t = asyncio.create_task(reminder_loop(bot))
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def router():
    r = Router()

    @r.message(CommandStart())
    async def start(m: Message):
        reg("helper", m.from_user)
        await m.answer(HELP)

    @r.message(Command("id"))
    async def my_id(m: Message):
        await m.answer(f"твой id: <code>{m.from_user.id}</code>\nчат: <code>{m.chat.id}</code>")

    # ----- задачи -----
    @r.message(Command("add"))
    async def add(m: Message, command: CommandObject):
        if not command.args:
            return await m.answer("пример: /add купить хлеб")
        q("INSERT INTO todos(uid, text) VALUES(?,?)", (m.from_user.id, command.args[:200]))
        text, kb = todo_view(m.from_user.id)
        await m.answer(text, reply_markup=kb)

    @r.message(Command("todo"))
    async def todo(m: Message):
        text, kb = todo_view(m.from_user.id)
        await m.answer(text, reply_markup=kb)

    @r.callback_query(F.data.startswith("td:"))
    async def toggle(cb: CallbackQuery):
        q("UPDATE todos SET done = 1 - done WHERE id=? AND uid=?", (int(cb.data[3:]), cb.from_user.id))
        text, kb = todo_view(cb.from_user.id)
        await safe_edit(cb.message, text, kb)
        await cb.answer()

    @r.callback_query(F.data == "tdclear")
    async def clear(cb: CallbackQuery):
        q("DELETE FROM todos WHERE uid=? AND done=1", (cb.from_user.id,))
        text, kb = todo_view(cb.from_user.id)
        await safe_edit(cb.message, text, kb)
        await cb.answer("Убрал")

    # ----- напоминания -----
    @r.message(Command("remind"))
    async def remind(m: Message, command: CommandObject):
        parts = (command.args or "").split(maxsplit=1)
        secs = parse_duration(parts[0]) if parts else None
        if not secs or len(parts) < 2:
            return await m.answer("пример: /remind 1h30m позвонить маме")
        q("INSERT INTO reminders(uid, chat_id, text, at) VALUES(?,?,?,?)",
          (m.from_user.id, m.chat.id, parts[1][:300], int(time.time()) + secs))
        await m.answer(f"Напомню через {fmt_secs(secs)}")

    @r.message(Command("reminders"))
    async def reminders(m: Message):
        rows = q("SELECT * FROM reminders WHERE uid=? AND sent=0 ORDER BY at LIMIT 15", (m.from_user.id,))
        if not rows:
            return await m.answer("Активных напоминаний нет")
        now = time.time()
        await m.answer("\n".join(f"через {fmt_secs(max(0, x['at'] - now))}: {esc(x['text'])}" for x in rows))

    # ----- утилиты -----
    @r.message(Command("calc"))
    async def calc(m: Message, command: CommandObject):
        if not command.args:
            return await m.answer("пример: /calc (2+3)*4^2")
        try:
            await m.answer(f"<code>{esc(safe_calc(command.args))}</code>")
        except ZeroDivisionError:
            await m.answer("на ноль делить нельзя")
        except Exception as e:
            await m.answer(f"ошибка: {esc(e)}")

    @r.message(Command("pass"))
    async def password(m: Message, command: CommandObject):
        n = int(command.args) if command.args and command.args.strip().isdigit() else 16
        n = max(8, min(n, 64))
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_"
        await m.answer(f"<code>{''.join(secrets.choice(alphabet) for _ in range(n))}</code>")

    @r.message(Command("hash"))
    async def hashes(m: Message, command: CommandObject):
        if not command.args:
            return await m.answer("пример: /hash привет")
        d = command.args.encode()
        await m.answer("\n".join(f"{n}: <code>{getattr(hashlib, n)(d).hexdigest()}</code>"
                                 for n in ("md5", "sha1", "sha256")))

    @r.message(Command("b64"))
    async def b64(m: Message, command: CommandObject):
        parts = (command.args or "").split(maxsplit=1)
        if len(parts) < 2 or parts[0] not in ("enc", "dec"):
            return await m.answer("пример: /b64 enc привет или /b64 dec 0L/RgNC40LLQtdGC")
        try:
            out = (base64.b64encode(parts[1].encode()).decode() if parts[0] == "enc"
                   else base64.b64decode(parts[1]).decode())
            await m.answer(f"<code>{esc(out)}</code>")
        except Exception:
            await m.answer("не получилось раскодировать")

    @r.message(Command("time"))
    async def tz(m: Message, command: CommandObject):
        zones = [command.args.strip()] if command.args else ["UTC", "Europe/Moscow"]
        out = []
        for z in zones:
            try:
                out.append(f"{esc(z)}: {datetime.now(ZoneInfo(z)).strftime('%d.%m.%Y %H:%M:%S')}")
            except Exception:
                out.append(f"{esc(z)}: такой зоны нет. Пример: Europe/Berlin")
        await m.answer("\n".join(out))

    @r.message(Command("roll"))
    async def roll(m: Message, command: CommandObject):
        mt = re.fullmatch(r"(\d{1,2})d(\d{1,4})", (command.args or "1d6").strip().lower())
        if not mt or int(mt[1]) < 1 or int(mt[2]) < 2:
            return await m.answer("пример: /roll 2d6")
        rolls = [secrets.randbelow(int(mt[2])) + 1 for _ in range(int(mt[1]))]
        await m.answer(f"{' + '.join(map(str, rolls))} = <b>{sum(rolls)}</b>")

    @r.message(Command("uuid"))
    async def uid(m: Message):
        await m.answer(f"<code>{uuid.uuid4()}</code>")

    return r
