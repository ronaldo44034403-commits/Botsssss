# бот 1: витрина XD с приёмом заявок
import asyncio
import os

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from common import esc, q, reg, safe_edit, stamp

COMMANDS = [BotCommand(command="start", description="Меню"),
            BotCommand(command="cancel", description="Отменить заявку")]

HELLO = "<b>XD</b> кодер\nДелаю ботов сайты и скрипты под ключ.\nВыбери раздел:"
SERVICES = [
    ("Телеграм бот", "заявки магазины игры уведомления"),
    ("Сайт визитка", "быстрый и адаптивный"),
    ("Скрипт", "автоматизация и парсинг"),
    ("Другое", "опиши задачу и обсудим"),
]
PORTFOLIO = []  # сюда свои работы: ("Название", "описание", "https://ссылка")


class Order(StatesGroup):
    desc = State()
    budget = State()


def admin_id():
    return int(os.getenv("ADMIN_ID") or 0)


def is_admin(m):
    return admin_id() and m.from_user.id == admin_id()


def main_kb():
    b = InlineKeyboardBuilder()
    for t, d in (("Услуги", "services"), ("Портфолио", "portfolio"), ("Заказать", "order"), ("Контакты", "contacts")):
        b.button(text=t, callback_data=f"m:{d}")
    b.adjust(2)
    return b.as_markup()


def back_kb(extra=None):
    b = InlineKeyboardBuilder()
    if extra:
        b.button(**extra)
    b.button(text="Назад", callback_data="m:home")
    b.adjust(1)
    return b.as_markup()


def router():
    r = Router()

    @r.message(CommandStart())
    async def start(m: Message, state: FSMContext):
        await state.clear()
        reg("studio", m.from_user)
        await m.answer(HELLO, reply_markup=main_kb())

    @r.message(Command("cancel"))
    async def cancel(m: Message, state: FSMContext):
        await state.clear()
        await m.answer("Отменил. Возвращаю в меню.", reply_markup=main_kb())

    @r.callback_query(F.data == "m:home")
    async def home(cb: CallbackQuery, state: FSMContext):
        await state.clear()
        await safe_edit(cb.message, HELLO, main_kb())
        await cb.answer()

    @r.callback_query(F.data == "m:services")
    async def services(cb: CallbackQuery):
        text = "<b>Что делаю</b>\n" + "\n".join(f"• <b>{t}</b>: {d}" for t, d in SERVICES)
        await safe_edit(cb.message, text, back_kb())
        await cb.answer()

    @r.callback_query(F.data == "m:portfolio")
    async def portfolio(cb: CallbackQuery):
        if PORTFOLIO:
            text = "<b>Работы</b>\n" + "\n".join(
                f'• <a href="{u}">{esc(t)}</a>: {esc(d)}' for t, d, u in PORTFOLIO)
        else:
            text = "Примеры работ покажу в личке: @MR_XD_TON"
        await safe_edit(cb.message, text, back_kb())
        await cb.answer()

    @r.callback_query(F.data == "m:contacts")
    async def contacts(cb: CallbackQuery):
        kb = back_kb(dict(text="Написать в Telegram", url="https://t.me/MR_XD_TON"))
        await safe_edit(cb.message, "Telegram: @MR_XD_TON\nОтвечаю обычно в тот же день.", kb)
        await cb.answer()

    @r.callback_query(F.data == "m:order")
    async def order_start(cb: CallbackQuery):
        b = InlineKeyboardBuilder()
        for i, (t, _) in enumerate(SERVICES):
            b.button(text=t, callback_data=f"svc:{i}")
        b.button(text="Назад", callback_data="m:home")
        b.adjust(2, 2, 1)
        await safe_edit(cb.message, "Что нужно сделать?", b.as_markup())
        await cb.answer()

    @r.callback_query(F.data.startswith("svc:"))
    async def pick(cb: CallbackQuery, state: FSMContext):
        await state.update_data(service=SERVICES[int(cb.data.split(":")[1])][0])
        await state.set_state(Order.desc)
        await safe_edit(cb.message, "Опиши задачу своими словами.\nОтмена: /cancel")
        await cb.answer()

    @r.message(Order.desc, F.text)
    async def got_desc(m: Message, state: FSMContext):
        await state.update_data(desc=m.text[:1500])
        await state.set_state(Order.budget)
        await m.answer("Какой бюджет? Если не знаешь так и напиши.")

    @r.message(Order.budget, F.text)
    async def got_budget(m: Message, state: FSMContext):
        data = await state.get_data()
        await state.clear()
        u = m.from_user
        q("INSERT INTO orders(uid,name,username,service,descr,budget,created) VALUES(?,?,?,?,?,?,?)",
          (u.id, u.full_name, u.username, data.get("service"), data.get("desc"), m.text[:200], stamp()))
        oid = q("SELECT last_insert_rowid() AS i", one=True)["i"]
        who = f"@{u.username}" if u.username else f'<a href="tg://user?id={u.id}">{esc(u.full_name)}</a>'
        if admin_id():
            try:
                await m.bot.send_message(
                    admin_id(),
                    f"<b>Заявка №{oid}</b>\nОт: {who}\nУслуга: {esc(data.get('service'))}\n"
                    f"Бюджет: {esc(m.text[:200])}\n\n{esc(data.get('desc'))}")
            except Exception as e:
                print("не смог написать админу:", e)
        await m.answer(f"Заявка №{oid} принята. XD ответит как только увидит.", reply_markup=main_kb())

    @r.message(Command("orders"))
    async def orders(m: Message):
        if not is_admin(m):
            return await m.answer("Нужен ADMIN_ID в .env. Свой id покажет второй бот командой /id")
        rows = q("SELECT * FROM orders ORDER BY id DESC LIMIT 10")
        if not rows:
            return await m.answer("Заявок пока нет")
        await m.answer("\n\n".join(
            f"<b>№{o['id']}</b> {o['created']}\n{esc(o['name'])} {('@' + o['username']) if o['username'] else ''}\n"
            f"{esc(o['service'])} / {esc(o['budget'])}\n{esc(o['descr'][:200])}" for o in rows))

    @r.message(Command("stats"))
    async def stats(m: Message):
        if not is_admin(m):
            return
        u = q("SELECT COUNT(*) c FROM users WHERE bot='studio'", one=True)["c"]
        o = q("SELECT COUNT(*) c FROM orders", one=True)["c"]
        await m.answer(f"Пользователей: {u}\nЗаявок: {o}")

    @r.message(Command("broadcast"))
    async def broadcast(m: Message, command: CommandObject):
        if not is_admin(m):
            return
        if not command.args:
            return await m.answer("/broadcast текст рассылки")
        ok = bad = 0
        for u in q("SELECT uid FROM users WHERE bot='studio'"):
            try:
                await m.bot.send_message(u["uid"], command.args)
                ok += 1
            except Exception:
                bad += 1
            await asyncio.sleep(0.05)
        await m.answer(f"Отправлено: {ok}\nОшибок: {bad}")

    return r
