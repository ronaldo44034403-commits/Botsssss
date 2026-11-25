# чистая логика без телеграма чтобы легко тестировать
import ast
import operator as op
import random
import re

OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Mod: op.mod, ast.Pow: op.pow, ast.USub: op.neg, ast.UAdd: op.pos,
}


def _calc(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in OPS:
        a, b = _calc(n.left), _calc(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 100:
            raise ValueError("степень слишком большая")
        return OPS[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and type(n.op) in OPS:
        return OPS[type(n.op)](_calc(n.operand))
    raise ValueError("не понял выражение")


def safe_calc(expr):
    if len(expr) > 100:
        raise ValueError("слишком длинно")
    res = _calc(ast.parse(expr.replace("^", "**").replace(",", "."), mode="eval").body)
    return round(res, 10) if isinstance(res, float) else res


UNITS = {"s": 1, "с": 1, "m": 60, "м": 60, "h": 3600, "ч": 3600, "d": 86400, "д": 86400}


def parse_duration(s):
    s = s.lower().strip()
    if not re.fullmatch(r"(?:\d+[smhdсмчд])+", s):
        return None
    total = sum(int(n) * UNITS[u] for n, u in re.findall(r"(\d+)([smhdсмчд])", s))
    return total if 0 < total <= 365 * 86400 else None


def fmt_secs(n):
    d, r = divmod(int(n), 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = [f"{v} {u}" for v, u in ((d, "д"), (h, "ч"), (m, "мин"), (s, "с")) if v]
    return " ".join(parts) or "0 с"


LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def winner(b):
    for a, c, d in LINES:
        if b[a] != "-" and b[a] == b[c] == b[d]:
            return b[a]
    return "draw" if "-" not in b else None


def _minimax(b, turn):
    w = winner(b)
    if w == "o":
        return 1
    if w == "x":
        return -1
    if w == "draw":
        return 0
    nxt = "x" if turn == "o" else "o"
    s = [_minimax(b[:i] + turn + b[i + 1:], nxt) for i, c in enumerate(b) if c == "-"]
    return max(s) if turn == "o" else min(s)


def bot_move(b, level):
    free = [i for i, c in enumerate(b) if c == "-"]
    if level == "e" or (level == "m" and random.random() < 0.5):
        return random.choice(free)
    scored = [(_minimax(b[:i] + "o" + b[i + 1:], "x"), i) for i in free]
    top = max(s for s, _ in scored)
    return random.choice([i for s, i in scored if s == top])
