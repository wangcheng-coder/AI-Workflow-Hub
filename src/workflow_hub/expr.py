"""只支持比较和与或非的条件表达式。"""

from __future__ import annotations


class ExprError(ValueError):
    pass


class Parser:
    def __init__(self, text: str):
        self.text = text
        self.i = 0

    def parse(self):
        node = self._or()
        self._skip()
        if self.i != len(self.text):
            raise ExprError("表达式有无法识别的内容")
        return node

    def _peek(self) -> str:
        self._skip()
        return self.text[self.i:]

    def _skip(self) -> None:
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1

    def _eat(self, token: str) -> bool:
        if self._peek().startswith(token):
            self.i += len(token)
            return True
        return False

    def _or(self):
        left = self._and()
        while self._eat("||"):
            right = self._and()
            left = ("or", left, right)
        return left

    def _and(self):
        left = self._not()
        while self._eat("&&"):
            right = self._not()
            left = ("and", left, right)
        return left

    def _not(self):
        if self._eat("!"):
            return ("not", self._not())
        return self._cmp()

    def _cmp(self):
        left = self._primary()
        for op in ("==", "!=", "<=", ">=", "<", ">"):
            if self._eat(op):
                return ("cmp", op, left, self._primary())
        return left

    def _primary(self):
        self._skip()
        if self.i >= len(self.text):
            raise ExprError("表达式不完整")
        ch = self.text[self.i]
        if ch in "'\"":
            return self._string(ch)
        if ch.isdigit() or (ch == "-" and self.i + 1 < len(self.text) and self.text[self.i + 1].isdigit()):
            return ("number", self._number())
        if ch == "(":
            self.i += 1
            node = self._or()
            if not self._eat(")"):
                raise ExprError("缺少右括号")
            return node
        if ch.isalpha() or ch == "_":
            start = self.i
            while self.i < len(self.text) and (self.text[self.i].isalnum() or self.text[self.i] == "_"):
                self.i += 1
            word = self.text[start:self.i]
            if word == "true":
                return ("bool", True)
            if word == "false":
                return ("bool", False)
            return ("name", word)
        raise ExprError("不支持的表达式")

    def _string(self, quote: str):
        self.i += 1
        start = self.i
        while self.i < len(self.text) and self.text[self.i] != quote:
            self.i += 1
        if self.i >= len(self.text):
            raise ExprError("字符串没有结束")
        value = self.text[start:self.i]
        self.i += 1
        return ("string", value)

    def _number(self) -> float:
        start = self.i
        if self.text[self.i] == "-":
            self.i += 1
        while self.i < len(self.text) and (self.text[self.i].isdigit() or self.text[self.i] == "."):
            self.i += 1
        return float(self.text[start:self.i])


def evaluate(expression: str, context: dict):
    return _eval(Parser(expression).parse(), context)


def _eval(node, context):
    kind = node[0]
    if kind == "or":
        return bool(_eval(node[1], context) or _eval(node[2], context))
    if kind == "and":
        return bool(_eval(node[1], context) and _eval(node[2], context))
    if kind == "not":
        return not _eval(node[1], context)
    if kind == "cmp":
        left = _eval(node[2], context)
        right = _eval(node[3], context)
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "<": lambda a, b: a < b,
            ">": lambda a, b: a > b,
            "<=": lambda a, b: a <= b,
            ">=": lambda a, b: a >= b,
        }
        try:
            return ops[node[1]](left, right)
        except TypeError as exc:
            raise ExprError("比较的类型不一致") from exc
    if kind == "string":
        return node[1]
    if kind == "number":
        return node[1]
    if kind == "bool":
        return node[1]
    if kind == "name":
        if node[1] not in context:
            raise ExprError(f"上下文没有变量 {node[1]}")
        return context[node[1]]
    raise ExprError("无法计算表达式")
