# бот 3: игры с рейтингом (крестики нолики против бота и угадай число)
import random

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from common import esc, q, reg, safe_edit
from logic import bot_move, winner

COMMANDS = [
    BotCommand(command="start", description="Меню игр"),
    BotCommand(command="ttt", description="Крестики нолики"),
    BotCommand(command="guess", description="Угадай число"),
    BotCommand(command="top", description="Таблица лидеров"),
    BotCommand(command="me", description="Моя статистика"),
]

LEVELS = {"e": "лёгкий", "m": "средний", "h": "сложный"}
SYM = {"x": "X", "o": "O", "-": "·"}


class Guess(StatesGroup):
    play = State()


def menu_kb():
    b = InlineKeyboardBuilder()
    b.button(text="Крестики нолики", callback_data="g:ttt")
    b.button(text="Угадай число", callback_data="g:guess")
    b.button(text="Таблица лидеров", callback_data="g:top")
    b.adjust(1)
    return b.as_markup()


def level_kb():
    b = InlineKeyboardBuilder()
    for k, v in LEVELS.items():
        b.button(text=v.capitalize(), callback_data=f"tn:{k}")
    b.adjust(3)
    return b.as_markup()


def board_kb(level, board, over=False):
    b = InlineKeyboardBuilder()
    for i, c in enumerate(board):
        b.button(text=SYM[c], callback_data="noop" if over or c != "-" else f"tt:{level}:{board}:{i}")
    if over:
        b.button(text="Ещё раз", callback_data="g:ttt")
        b.adjust(3, 3, 3, 1)
    else:
        b.adjust(3)
    return b.as_markup()


def record(user, col):
    q(f"INSERT INTO scores(uid, name, {col}) VALUES(?,?,1) "
      f"ON CONFLICT(uid) DO UPDATE SET name=excluded.name, {col}={col}+1", (user.id, user.full_name))


def top_text():
    rows = q("SELECT name, w, d, l FROM scores WHERE w+d+l>0 ORDER BY w DESC, d DESC, l LIMIT 10")
    best = q("SELECT name, best FROM scores WHERE best IS NOT NULL ORDER BY best, uid LIMIT 5")
    out = ["<b>Крестики нолики</b> (победы ничьи поражения)"]
    out += [f"{i}. {esc(r['name'])}: {r['w']} / {r['d']} / {r['l']}" for i, r in enumerate(rows, 1)] or ["пока пусто"]
    out += ["", "<b>Угадай число</b> (меньше попыток лучше)"]
    out += [f"{i}. {esc(r['name'])}: {r['best']}" for i, r in enumerate(best, 1)] or ["пока пусто"]
    return "\n".join(out)


def router():
    r = Router()

    @r.message(CommandStart())
    async def start(m: Message, state: FSMContext):
        await state.clear()
        reg("games", m.from_user)
        await m.answer("<b>Игры</b>\nВыбирай:", reply_markup=menu_kb())

    # ----- крестики нолики -----
    @r.message(Command("ttt"))
    async def ttt_cmd(m: Message):
        await m.answer("Выбери сложность. Ты играешь X и ходишь первым.", reply_markup=level_kb())

    @r.callback_query(F.data == "g:ttt")
    async def ttt_menu(cb: CallbackQuery):
        await safe_edit(cb.message, "Выбери сложность. Ты играешь X и ходишь первым.", level_kb())
        await cb.answer()

    @r.callback_query(F.data.startswith("tn:"))
    async def ttt_new(cb: CallbackQuery):
        lvl = cb.data[3:]
        await safe_edit(cb.message, f"Уровень: {LEVELS[lvl]}. Твой ход.", board_kb(lvl, "-" * 9))
        await cb.answer()

    @r.callback_query(F.data.startswith("tt:"))
    async def ttt_move(cb: CallbackQuery):
        _, lvl, board, i = cb.data.split(":")
        i = int(i)
        if board[i] != "-" or winner(board):
            return await cb.answer("Сюда нельзя")
        board = board[:i] + "x" + board[i + 1:]
        w = winner(board)
        if not w:
            j = bot_move(board, lvl)
            board = board[:j] + "o" + board[j + 1:]
            w = winner(board)
        if not w:
            await safe_edit(cb.message, f"Уровень: {LEVELS[lvl]}. Твой ход.", board_kb(lvl, board))
            return await cb.answer()
        record(cb.from_user, {"x": "w", "o": "l", "draw": "d"}[w])
        text = {"x": "Ты победил", "o": "Бот победил", "draw": "Ничья"}[w]
        await safe_edit(cb.message, f"{text}. Уровень: {LEVELS[lvl]}.", board_kb(lvl, board, over=True))
        await cb.answer()

    @r.callback_query(F.data == "noop")
    async def noop(cb: CallbackQuery):
        await cb.answer()

    # ----- угадай число -----
    async def begin_guess(m: Message, state: FSMContext):
        await state.set_state(Guess.play)
        await state.update_data(secret=random.randint(1, 100), tries=0)
        await m.answer("Загадал число от 1 до 100. Пиши свои варианты.\nСдаться: /giveup")

    @r.message(Command("guess"))
    async def guess_cmd(m: Message, state: FSMContext):
        await begin_guess(m, state)

    @r.callback_query(F.data == "g:guess")
    async def guess_cb(cb: CallbackQuery, state: FSMContext):
        await begin_guess(cb.message, state)
        await cb.answer()

    @r.message(Command("giveup"))
    async def giveup(m: Message, state: FSMContext):
        data = await state.get_data()
        await state.clear()
        if "secret" in data:
            await m.answer(f"Было число {data['secret']}.", reply_markup=menu_kb())
        else:
            await m.answer("Ты сейчас не играешь.", reply_markup=menu_kb())

    @r.message(Guess.play, F.text)
    async def guess_try(m: Message, state: FSMContext):
        if not m.text.strip().isdigit():
            return await m.answer("Нужно число от 1 до 100")
        n = int(m.text)
        data = await state.get_data()
        tries = data["tries"] + 1
        if n == data["secret"]:
            await state.clear()
            q("INSERT INTO scores(uid, name, best) VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET "
              "name=excluded.name, best=MIN(COALESCE(best, 999), excluded.best)",
              (m.from_user.id, m.from_user.full_name, tries))
            return await m.answer(f"Угадал за {tries}. Рекорд записан.", reply_markup=menu_kb())
        await state.update_data(tries=tries)
        await m.answer(f"Моё число {'больше' if n < data['secret'] else 'меньше'}. Попыток: {tries}")

    # ----- рейтинг -----
    @r.message(Command("top"))
    async def top_cmd(m: Message):
        await m.answer(top_text())

    @r.callback_query(F.data == "g:top")
    async def top_cb(cb: CallbackQuery):
        await cb.message.answer(top_text())
        await cb.answer()

    @r.message(Command("me"))
    async def me(m: Message):
        s = q("SELECT * FROM scores WHERE uid=?", (m.from_user.id,), one=True)
        if not s:
            return await m.answer("Ты ещё не играл")
        await m.answer(f"Крестики нолики: {s['w']} побед {s['d']} ничьих {s['l']} поражений\n"
                       f"Угадай число лучший результат: {s['best'] or 'нет'}")

    return r
