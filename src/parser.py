"""语法分析：词（token）列表 → 表达式（嵌套的数据结构）。

流水线的第二步。它把线性的词序列组装成"表达式"——即本解释器真正要
求值的数据：数字、布尔、字符串、符号，以及由 Pair 串成的列表（spec §6）。

两条重要约定：
- `'x` 是 `(quote x)` 的简写，在这里直接改写（spec §4.1）。
- 引号里的数据要转成和 cons 一致的表示（点对链），不能留下 Python 的
  list，否则打印会出问题（spec §11 排错指南最后一条）。
"""

from tokenizer import (LPAREN, RPAREN, QUOTE, DOT, NUMBER, BOOLEAN, STRING,
                       SYMBOL, tokenize)
from values import NIL, Pair, SchemeError, Symbol

# 字符串字面量里的转义序列（spec §3）
_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


class Parser:
    """把 token 列表按顺序读成表达式。用下标游标而不是递归消耗列表，
    避免大程序上的切片开销。"""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def parse_all(self):
        """解析全部顶层表达式（一个文件里可以有多个）。"""
        exprs = []
        while self.pos < len(self.tokens):
            exprs.append(self.parse_expr())
        return exprs

    def peek(self):
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def next(self):
        tok = self.peek()
        if tok is None:
            raise SchemeError("程序在括号还没有闭合时就结束了")
        self.pos += 1
        return tok

    def parse_expr(self):
        tok = self.next()

        if tok.kind == QUOTE:
            # '数据 等价于 (quote 数据)
            return Pair(Symbol("quote"), Pair(self.parse_expr(), NIL))

        if tok.kind == LPAREN:
            return self.parse_list()

        if tok.kind == RPAREN:
            raise SchemeError("多出来的右括号")

        return _atom(tok)

    def parse_list(self):
        """读一个括号内的序列，遇到右括号结束；支持 `(a . b)` 的点对写法。"""
        items = []
        tail = NIL
        while True:
            tok = self.peek()
            if tok is None:
                raise SchemeError("括号没有闭合（缺少右括号）")
            if tok.kind == RPAREN:
                self.next()
                break
            if tok.kind == DOT:
                self.next()
                tail = self.parse_expr()          # 点后面必须是一个完整表达式
                closing = self.peek()
                if closing is None or closing.kind != RPAREN:
                    raise SchemeError("点对写法 `.` 后面必须紧跟右括号")
                self.next()
                break
            items.append(self.parse_expr())

        result = tail
        for item in reversed(items):
            result = Pair(item, result)
        return result


def _atom(tok):
    """把单个 token 变成对应的值。"""
    if tok.kind == NUMBER:
        # 能当整数读就当整数，否则按浮点（spec §5：整数相除要得整数商）
        try:
            return int(tok.text)
        except ValueError:
            return float(tok.text)

    if tok.kind == BOOLEAN:
        return tok.text == "#t"

    if tok.kind == STRING:
        return _unescape(tok.text[1:-1])

    if tok.kind == SYMBOL:
        return Symbol(tok.text)

    raise SchemeError("这里不该出现 `%s`" % tok.text)


def _unescape(raw):
    """还原字符串字面量里的转义：`\\n` → 换行等；未知转义原样保留。"""
    out = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            out.append(_ESCAPES.get(nxt, "\\" + nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def parse(text):
    """对外入口：程序文本 → 顶层表达式列表。"""
    return Parser(tokenize(text)).parse_all()


def parse_tokens(tokens):
    """对外入口：已有 token 列表 → 顶层表达式列表。"""
    return Parser(tokens).parse_all()
