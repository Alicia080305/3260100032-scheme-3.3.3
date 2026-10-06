"""内置过程（标准函数库）：spec §5 的全部内置函数，装进初始环境。

内置过程和特殊形式的区别（spec §5 开头）：内置过程的**参数先全部求值**，
再交给这里的 Python 函数；而 if / cond / define 这类特殊形式自己决定
求不求值、按什么顺序求值，所以它们住在 evaluator.py 里，不在这里。

数值细节（spec §5，最容易错的两条）：
- `/` 整数相除得**整数商**，且负数商向零截断：`(/ -7 2)` → -3。
- `/` 只有一个参数时是求倒数，结果是**浮点**：`(/ 2)` → 0.5。
"""

import operator
import sys

from environment import Environment
from printer import display_string
from values import (BuiltinProcedure, NIL, Pair, SchemeError, Symbol,
                    is_number, is_true, list_to_pair, pair_to_list)


# ---------------------------------------------------------------- 小工具


def _check_numbers(name, args):
    """内置过程的参数类型检查：要求全是数字，否则报错。"""
    for arg in args:
        if not is_number(arg):
            raise SchemeError("%s 的参数必须是数字，收到了 %r" % (name, arg))


def _int_div(a, b):
    """整数除法，商向零截断（Python 的 // 是向下取整，不符合 spec）。"""
    quotient = abs(a) // abs(b)
    return -quotient if (a < 0) ^ (b < 0) else quotient


def _divide(a, b):
    """一次除法：全整数走整数商，否则走浮点除法。"""
    if b == 0:
        raise SchemeError("除数不能为零")
    if isinstance(a, int) and isinstance(b, int):
        return _int_div(a, b)
    return a / b


def _check_pair(name, value):
    if not isinstance(value, Pair):
        raise SchemeError("%s 的参数必须是点对（非空表），收到了 %r" % (name, value))
    return value


# ---------------------------------------------------------------- 算术


def _add(args):
    _check_numbers("+", args)
    return sum(args)


def _subtract(args):
    _check_numbers("-", args)
    if not args:
        raise SchemeError("- 至少需要一个参数")
    if len(args) == 1:
        return -args[0]                       # 单参数取反
    result = args[0]
    for arg in args[1:]:
        result -= arg
    return result


def _multiply(args):
    _check_numbers("*", args)
    result = 1
    for arg in args:
        result *= arg
    return result


def _divide_all(args):
    _check_numbers("/", args)
    if not args:
        raise SchemeError("/ 至少需要一个参数")
    if len(args) == 1:
        return 1 / args[0]                    # 单参数求倒数，结果是浮点
    result = args[0]
    for arg in args[1:]:
        result = _divide(result, arg)
    return result


def _modulo(args):
    if len(args) != 2:
        raise SchemeError("modulo 需要两个参数")
    a, b = args
    _check_numbers("modulo", args)
    if b == 0:
        raise SchemeError("modulo 的除数不能为零")
    # Python 的 % 与 Scheme 的 modulo 一致：余数符号跟随除数（向下取整取模）。
    # 对比 quotient / `/`：那两个要求商向零截断，所以不能直接用 // 和 %。
    return a % b


def _quotient(args):
    if len(args) != 2:
        raise SchemeError("quotient 需要两个参数")
    a, b = args
    _check_numbers("quotient", args)
    if b == 0:
        raise SchemeError("quotient 的除数不能为零")
    return _int_div(a, b)


def _expt(args):
    if len(args) != 2:
        raise SchemeError("expt 需要两个参数")
    _check_numbers("expt", args)
    return args[0] ** args[1]


def _abs(args):
    if len(args) != 1:
        raise SchemeError("abs 需要一个参数")
    _check_numbers("abs", args)
    return abs(args[0])


# ---------------------------------------------------------------- 比较


def _make_comparison(name, op):
    """生成一个链式比较过程：相邻两两比较，全部成立才为真（spec §5）。"""

    def compare(args):
        if len(args) < 2:
            raise SchemeError("%s 至少需要两个参数" % name)
        for left, right in zip(args, args[1:]):
            if not _compare_one(left, right, op):
                return False
        return True

    return BuiltinProcedure(name, compare)


def _compare_one(left, right, op):
    """比较一对值：数字比大小，符号/字符串按字典序（spec §5 说支持符号）。"""
    if is_number(left) and is_number(right):
        return op(left, right)
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return op(left.name, right.name)
    if isinstance(left, str) and isinstance(right, str):
        return op(left, right)
    raise SchemeError("无法比较这两个值：%r 和 %r" % (left, right))


def _numeric_equal(left, right):
    """`=` 的特例：数字按数值相等，符号/字符串按内容相等（spec §5）。"""
    if is_number(left) and is_number(right):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name == right.name
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    if left is NIL and right is NIL:
        return True
    if isinstance(left, Pair) and isinstance(right, Pair):
        return _equal(left, right)
    return False


# ---------------------------------------------------------------- 布尔


def _not(args):
    if len(args) != 1:
        raise SchemeError("not 需要一个参数")
    return not is_true(args[0])               # 只有 #f 是假


# ---------------------------------------------------------------- 列表


def _cons(args):
    if len(args) != 2:
        raise SchemeError("cons 需要两个参数")
    return Pair(args[0], args[1])


def _car(args):
    if len(args) != 1:
        raise SchemeError("car 需要一个参数")
    return _check_pair("car", args[0]).car


def _cdr(args):
    if len(args) != 1:
        raise SchemeError("cdr 需要一个参数")
    return _check_pair("cdr", args[0]).cdr


def _list(args):
    return list_to_pair(args)


def _length(args):
    if len(args) != 1:
        raise SchemeError("length 需要一个参数")
    return len(pair_to_list(args[0]))


def _append(args):
    """拼接若干列表。除最后一个参数外都复制一份，最后一个原样接在链尾
    （因此 `(append '(1 2) 3)` 得到 `(1 2 . 3)`，与标准 Scheme 一致）。"""
    if not args:
        return NIL
    items = []
    for value in args[:-1]:
        items.extend(pair_to_list(value))     # 前面的列表都复制一份
    return list_to_pair(items, args[-1])      # 最后一个直接当尾巴接上


def _is_null(args):
    if len(args) != 1:
        raise SchemeError("null? 需要一个参数")
    return args[0] is NIL


def _is_pair(args):
    if len(args) != 1:
        raise SchemeError("pair? 需要一个参数")
    return isinstance(args[0], Pair)          # 空表不是点对


def _is_list(args):
    if len(args) != 1:
        raise SchemeError("list? 需要一个参数")
    node = args[0]
    while isinstance(node, Pair):
        node = node.cdr
    return node is NIL                        # 真列表：链尾必须是空表


# ---------------------------------------------------------------- 谓词


def _is_number_proc(args):
    if len(args) != 1:
        raise SchemeError("number? 需要一个参数")
    return is_number(args[0])


def _is_boolean(args):
    if len(args) != 1:
        raise SchemeError("boolean? 需要一个参数")
    return isinstance(args[0], bool)


def _is_symbol(args):
    if len(args) != 1:
        raise SchemeError("symbol? 需要一个参数")
    return isinstance(args[0], Symbol)


def _is_string(args):
    if len(args) != 1:
        raise SchemeError("string? 需要一个参数")
    return isinstance(args[0], str)


def _is_procedure(args):
    if len(args) != 1:
        raise SchemeError("procedure? 需要一个参数")
    from values import Procedure
    return isinstance(args[0], Procedure)


def _make_numeric_predicate(name, test):
    """生成 zero? / even? / odd? 这类"参数必须是数"的谓词。"""

    def predicate(args):
        if len(args) != 1:
            raise SchemeError("%s 需要一个参数" % name)
        _check_numbers(name, args)
        return test(args[0])

    return BuiltinProcedure(name, predicate)


def _eq(args):
    """eq?：符号/数字/布尔/字符串按值比较，列表等复合数据按同一性（spec §5）。"""
    if len(args) != 2:
        raise SchemeError("eq? 需要两个参数")
    left, right = args
    if left is right:
        return True
    if isinstance(left, bool) or isinstance(right, bool):
        return False                          # 布尔只有 #t/#f，上面已判过同一性
    if is_number(left) and is_number(right):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name == right.name        # 符号已驻留，其实前面就命中了
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    return False                              # 列表等：是否同一对象


def _equal_proc(args):
    """equal? 的内置过程包装：参数检查后交给下面的结构比较函数。"""
    if len(args) != 2:
        raise SchemeError("equal? 需要两个参数")
    return _equal(args[0], args[1])


def _equal(left, right):
    """结构相等：逐层比较；先比类型，避免 Python 里 True == 1 的坑。"""
    if isinstance(left, bool) or isinstance(right, bool):
        # (equal? #t 1) 必须为 #f：布尔只和布尔相等
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if is_number(left) and is_number(right):
        return left == right
    if isinstance(left, Symbol) and isinstance(right, Symbol):
        return left.name == right.name
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    if left is NIL and right is NIL:
        return True
    if isinstance(left, Pair) and isinstance(right, Pair):
        return _equal(left.car, right.car) and _equal(left.cdr, right.cdr)
    return left is right


# ---------------------------------------------------------------- 输出


def _display(args):
    """display：打印值（字符串不带引号），不换行，返回"无值"（不打印结果）。"""
    if len(args) != 1:
        raise SchemeError("display 需要一个参数")
    sys.stdout.write(display_string(args[0]))
    return None


def _newline(args):
    if args:
        raise SchemeError("newline 不接受参数")
    sys.stdout.write("\n")
    return None


# ---------------------------------------------------------------- 注册表


def _register(*specs):
    """(名字, Python 函数) → 内置过程对象。"""
    return {name: BuiltinProcedure(name, fn) for name, fn in specs}


# 名字 → 内置过程。数值谓词和比较运算用工厂生成，避免写一堆几乎一样的函数体。
_BUILTIN_TABLE = _register(
    # 算术
    ("+", _add), ("-", _subtract), ("*", _multiply), ("/", _divide_all),
    ("modulo", _modulo), ("quotient", _quotient), ("expt", _expt),
    ("abs", _abs),
    # 布尔与谓词
    ("not", _not),
    ("number?", _is_number_proc), ("boolean?", _is_boolean),
    ("symbol?", _is_symbol), ("string?", _is_string),
    ("procedure?", _is_procedure),
    ("eq?", _eq), ("equal?", _equal_proc),
    # 列表
    ("cons", _cons), ("car", _car), ("cdr", _cdr), ("list", _list),
    ("length", _length), ("append", _append),
    ("null?", _is_null), ("pair?", _is_pair), ("list?", _is_list),
    # 输出
    ("display", _display), ("newline", _newline),
)

# 数值谓词：参数必须是数
_BUILTIN_TABLE["zero?"] = _make_numeric_predicate("zero?", lambda x: x == 0)
_BUILTIN_TABLE["even?"] = _make_numeric_predicate("even?", lambda x: x % 2 == 0)
_BUILTIN_TABLE["odd?"] = _make_numeric_predicate("odd?", lambda x: x % 2 != 0)

# 链式比较：相邻两两比较，全部成立才为真（spec §5）
_BUILTIN_TABLE["="] = _make_comparison("=", _numeric_equal)
_BUILTIN_TABLE["<"] = _make_comparison("<", operator.lt)
_BUILTIN_TABLE[">"] = _make_comparison(">", operator.gt)
_BUILTIN_TABLE["<="] = _make_comparison("<=", operator.le)
_BUILTIN_TABLE[">="] = _make_comparison(">=", operator.ge)


def global_environment():
    """造一个装好全部内置过程的环境（spec §2：初始环境）。"""
    env = Environment()
    for name, proc in _BUILTIN_TABLE.items():
        env.define(Symbol(name), proc)
    return env
