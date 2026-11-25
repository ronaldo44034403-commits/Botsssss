import html
import os
import sqlite3
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def load_env(path=None):
    path = path or os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


DB = sqlite3.connect(os.path.join(HERE, "data.db"), check_same_thread=False)
DB.row_factory = sqlite3.Row
DB.executescript("""
CREATE TABLE IF NOT EXISTS users(bot TEXT, uid INTEGER, name TEXT, joined TEXT, PRIMARY KEY(bot, uid));
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, name TEXT, username TEXT,
  service TEXT, descr TEXT, budget TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS todos(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, text TEXT, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, chat_id INTEGER,
  text TEXT, at INTEGER, sent INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS scores(uid INTEGER PRIMARY KEY, name TEXT, w INTEGER DEFAULT 0, d INTEGER DEFAULT 0,
  l INTEGER DEFAULT 0, best INTEGER);
""")


def q(sql, args=(), one=False):
    cur = DB.execute(sql, args)
    DB.commit()
    rows = cur.fetchall()
    if one:
        return rows[0] if rows else None
    return rows


def esc(s):
    return html.escape(str(s))


def stamp():
    return time.strftime("%d.%m.%Y %H:%M")


def reg(bot_name, user):
    q("INSERT OR IGNORE INTO users(bot, uid, name, joined) VALUES(?,?,?,?)",
      (bot_name, user.id, user.full_name, stamp()))


async def safe_edit(msg, text, kb=None):
    from aiogram.exceptions import TelegramBadRequest
    try:
        await msg.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            raise
