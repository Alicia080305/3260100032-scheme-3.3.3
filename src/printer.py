"""打印：值 → 文本。

流水线的最后一步。两种打印方式（spec §8）：
- to_string：值的"带类型"表示。字符串带引号、内部转义可见，用于打印每个
  顶层表达式的求值结果。
- display_string：给 display 用的表示。字符串不带引号、不转义。

打印规则（spec §8）：整数 42、浮点 0.5、布尔 #t/#f、符号 foo、
字符串 "hello"、真列表 (1 2 3)、点对 (1 . 2)、空表 ()、
过程 #<procedure>。
"""

from values import NIL, Pair, Procedure, Symbol

# 打印字符串时需要反向转义的字符（与 parser._unescape 对应）
_ESCAPES_BACK = {"\n": "\\n", "\t": "\\t", '"': '\\"', "\\": "\\\\"}


def to_string(value):
    """把值转成"看得出类型"的文本。"""
    if value is None:
        return ""                       # 无值（display/newline 的结果）不打印
    if value is True:
        return "#t"
    if value is False:
        return "#f"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _format_float(value)
    if isinstance(value, Symbol):
        return value.name
    if isinstance(value, str):
        return '"' + "".join(_ESCAPES_BACK.get(c, c) for c in value) + '"'
    if value is NIL:
        return "()"
    if isinstance(value, Pair):
        return "(" + _pair_body(value) + ")"
    if isinstance(value, Procedure):
        return "#<procedure>"
    return str(value)


def display_string(value):
    """display 用的表示：字符串不带引号也不转义，其余同 to_string。"""
    if isinstance(value, str):
        return value
    return to_string(value)


def _format_float(num):
    """浮点打印：保持 Python 默认写法（0.5 → 0.5），避免出现科学计数法
    之外的意外格式。整值浮点仍保留一位小数，与 Python 一致。"""
    text = repr(num)
    return text


def _pair_body(pair):
    """拼出括号内部，如 `1 2 3` 或 `1 . 2`（遇到点对时加点）。"""
    parts = []
    node = pair
    while isinstance(node, Pair):
        parts.append(to_string(node.car))
        node = node.cdr
        if node is not NIL and not isinstance(node, Pair):
            # 尾巴不是链也不是空表 → 这是点对，按 `(a . b)` 打印
            parts.append(".")
            parts.append(to_string(node))
            return " ".join(parts)
    return " ".join(parts)
