"""词法分析：程序文本 → 一串词（token）。

流水线的第一步，只做"切词"，不做括号配对检查（那是 parser 的事）：

    程序文本 ──词法──→ 词 ──语法──→ 表达式 ──求值──→ 值 ──打印──→ 结果

零件的定义见 spec §3：注释、整数、布尔、符号、字符串、引用简写 '、
括号。零件之间用空白分隔。
"""

from values import SchemeError

# 词的类型（用常量字符串，便于调试时直接打印）
LPAREN = "("
RPAREN = ")"
QUOTE = "'"
DOT = "."
NUMBER = "number"
BOOLEAN = "boolean"
STRING = "string"
SYMBOL = "symbol"

# 空白：空格、换行、制表符、回车（兼容 Windows 的行尾）
_WHITESPACE = " \t\n\r\f\v"
# 遇到这些字符，当前正在读的零件就结束了
_DELIMITERS = _WHITESPACE + "()'\";"


class Token:
    """一个词：类型 + 原始文本。

    字符串保留原始文本（含转义），由 parser 负责还原成真正的字符串值，
    这样"怎么读"和"是什么值"两件事分在两层，各自都简单。
    """

    __slots__ = ("kind", "text")

    def __init__(self, kind, text):
        self.kind = kind
        self.text = text

    def __repr__(self):
        return "Token(%s, %r)" % (self.kind, self.text)


def tokenize(text):
    """把整段程序文本切成 token 列表。

    遇到无法识别的字符（如未闭合的字符串）抛出 SchemeError。
    """
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        # 注释：从 ; 到行尾全部跳过
        if ch == ";":
            while i < n and text[i] != "\n":
                i += 1
            continue

        # 空白：跳过
        if ch in _WHITESPACE:
            i += 1
            continue

        # 括号与引用简写：单字符 token
        if ch in "()'":
            tokens.append(Token(ch, ch))
            i += 1
            continue

        # 字符串：读到匹配的右引号，支持 \n \t \" \\ 四种转义（spec §3）
        if ch == '"':
            start = i
            i += 1
            chars = []
            closed = False
            while i < n:
                c = text[i]
                if c == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    # 保留原始转义序列，交给 parser 还原
                    chars.append(c + nxt)
                    i += 2
                    continue
                if c == '"':
                    i += 1
                    closed = True
                    break
                chars.append(c)
                i += 1
            if not closed:
                raise SchemeError("字符串没有闭合的右引号：%s" % text[start:start + 20])
            tokens.append(Token(STRING, '"' + "".join(chars) + '"'))
            continue

        # 其余：一直读到分隔符为止，再判断它是数字 / 布尔 / 点 / 符号
        start = i
        while i < n and text[i] not in _DELIMITERS:
            i += 1
        word = text[start:i]
        tokens.append(Token(_classify(word), word))

    return tokens


def _classify(word):
    """判断一个裸词（不含引号）属于哪一类。"""
    if word in ("#t", "#f"):
        return BOOLEAN
    if word == ".":
        return DOT
    if _looks_like_number(word):
        return NUMBER
    return SYMBOL


def _looks_like_number(word):
    """是否形如数字（可选负号、可选小数点）。浮点字面量是可选特性（spec §3）。"""
    body = word[1:] if word.startswith("-") else word
    if body == "":
        return False
    if body.count(".") > 1:
        return False
    return all(c.isdigit() or c == "." for c in body)
