"""mini-Scheme 运行期的数据类型（流水线上流动的"货物"）。

设计要点（对应 spec §3 词法、§6 列表）：
- 数字直接用 Python 的 int / float；布尔直接用 True / False。
- 符号 Symbol 做"驻留"处理：同名符号全局只有一个实例，这样 eq? 既能按值
  比较也能按同一性比较（spec §5 要求符号按值比较）。
- 列表不是"盒子"，而是由 Pair（点对）串成的链，空表是唯一的 NIL 实例
  （spec §6：`(1 2 3)` 实际是 `(1 . (2 . (3 . ())))`）。
- 只有 #f（Python 的 False）是假，0、()、"" 都是真（spec §9）——因此判断
  真假必须用 is_true()，不能用 Python 的真值测试。
"""

# ---------------------------------------------------------------- 错误类型


class SchemeError(Exception):
    """解释器所有可预期错误的基类（语法错误、未绑定变量、类型错误等）。"""


# ---------------------------------------------------------------- 符号


class Symbol:
    """符号：一个"名字"，可能是变量名，也可能是操作符名。"""

    __slots__ = ("name",)
    _interned = {}

    def __new__(cls, name):
        obj = cls._interned.get(name)
        if obj is None:
            obj = object.__new__(cls)
            obj.name = name
            cls._interned[name] = obj
        return obj

    def __repr__(self):
        return "Symbol(%r)" % (self.name,)


# ---------------------------------------------------------------- 点对与空表


class Pair:
    """点对：car 是第一项，cdr 是第二项（列表的"剩下那段"）。"""

    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def __repr__(self):
        return "Pair(%r, %r)" % (self.car, self.cdr)


class Nil:
    """空表 `()`：链的终点，全局唯一实例（所以所有空表都是同一个对象）。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = object.__new__(cls)
        return cls._instance

    def __repr__(self):
        return "()"


NIL = Nil()


# ---------------------------------------------------------------- 过程


class Procedure:
    """可调用对象的基类，供 `(procedure? x)` 判断。"""


class BuiltinProcedure(Procedure):
    """内置过程：由 Python 函数实现（spec §5 的标准函数库）。"""

    __slots__ = ("name", "fn")

    def __init__(self, name, fn):
        self.name = name
        self.fn = fn


class Closure(Procedure):
    """闭包：lambda 产出的用户函数。

    env 是**定义时**的环境（spec §4.6），这是词法作用域与闭包的关键；
    body 是若干条表达式，调用时按 begin 语义依次求值，返回最后一条的值。
    """

    __slots__ = ("params", "body", "env", "name")

    def __init__(self, params, body, env, name=None):
        self.params = params      # 形参名列表（Python list of Symbol）
        self.body = body          # 函数体表达式列表
        self.env = env            # 定义时捕获的环境
        self.name = name          # 仅用于调试/打印，可选


# ---------------------------------------------------------------- 通用小工具


def is_number(value):
    """是否是数字。注意 Python 里 bool 是 int 的子类，必须排除掉。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_true(value):
    """mini-Scheme 的真假判断：只有 #f 是假，其余（含 0、()、""）都是真。"""
    return value is not False


def pair_to_list(value):
    """把点对链转成 Python 列表；遇到非真列表（如 (1 . 2)）抛错。

    用于 length / append 这类只接受真列表的内置过程。
    """
    result = []
    while isinstance(value, Pair):
        result.append(value.car)
        value = value.cdr
    if value is not NIL:
        raise SchemeError("期望一个真列表，但遇到了非空的非点对值")
    return result


def list_to_pair(items, tail=NIL):
    """Python 列表 → 点对链（tail 允许构造带点的链，如 (1 2 . 3)）。"""
    result = tail
    for item in reversed(items):
        result = Pair(item, result)
    return result
