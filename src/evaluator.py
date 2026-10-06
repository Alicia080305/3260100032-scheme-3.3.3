"""求值器：解释器的心脏（表达式 + 环境 → 值）。

核心是两个互相递归的函数（README §4）：

    evaluate(expr, env)  ──遇到函数调用──→  apply_procedure(proc, args)
          ↑                                          │
          └──────────────── 求值函数体 ───────────────┘

- evaluate：符号去环境查值；数字/布尔/字符串原样返回；括号表达式先看是不是
  特殊形式（if/cond/define/lambda/let/quote/and/or/begin，各自求值顺序见
  spec §4），不是就当函数调用——先求值操作符和全部实参，再交给 apply。
- apply_procedure：内置过程直接调 Python；闭包则新建一层环境（外层指向
  **定义时**的环境）把实参绑到形参上，再回到 evaluate 求值函数体。

这两行递归转起来，解释器就活了。
"""

from procedures import global_environment
from values import (BuiltinProcedure, Closure, NIL, Pair, SchemeError,
                    Symbol, is_true)

# 特殊形式的名字。注意：它们**不是**内置过程，不能当值传来传去。
S_QUOTE = Symbol("quote")
S_IF = Symbol("if")
S_COND = Symbol("cond")
S_AND = Symbol("and")
S_OR = Symbol("or")
S_DEFINE = Symbol("define")
S_LAMBDA = Symbol("lambda")
S_LET = Symbol("let")
S_BEGIN = Symbol("begin")
S_ELSE = Symbol("else")


def evaluate(expr, env):
    """求值一个表达式，返回值。"""
    # ---- 自求值：数字、布尔、字符串、空表 ----
    if isinstance(expr, (int, float, str)) or expr is True or expr is False:
        return expr
    if expr is NIL:
        return NIL

    # ---- 符号：去环境里查它绑定的值 ----
    if isinstance(expr, Symbol):
        return env.lookup(expr.name)

    # ---- 括号表达式 ----
    if isinstance(expr, Pair):
        head = expr.car

        # 特殊形式：各自决定"先算什么、后算什么"
        if head is S_QUOTE:
            return _eval_quote(expr)
        if head is S_IF:
            return _eval_if(expr, env)
        if head is S_COND:
            return _eval_cond(expr, env)
        if head is S_AND:
            return _eval_and(expr, env)
        if head is S_OR:
            return _eval_or(expr, env)
        if head is S_DEFINE:
            return _eval_define(expr, env)
        if head is S_LAMBDA:
            return _eval_lambda(expr, env)
        if head is S_LET:
            return _eval_let(expr, env)
        if head is S_BEGIN:
            return _eval_sequence(list(_pair_iter(expr.cdr)), env)

        # 其余都是函数调用：应用序——先求值操作符和全部实参，再调用
        operator = evaluate(head, env)
        args = [evaluate(arg, env) for arg in _pair_iter(expr.cdr)]
        return apply_procedure(operator, args)

    raise SchemeError("无法求值的表达式：%r" % (expr,))


def apply_procedure(proc, args):
    """调用一个过程。"""
    if isinstance(proc, BuiltinProcedure):
        return proc.fn(args)

    if isinstance(proc, Closure):
        if len(args) != len(proc.params):
            raise SchemeError(
                "过程需要 %d 个参数，实际给了 %d 个" % (len(proc.params), len(args)))
        # 关键：新环境的外层指向闭包**定义时**的环境，这就是词法作用域
        local = proc.env.child(zip(proc.params, args))
        return _eval_sequence(proc.body, local)

    raise SchemeError("这不是一个可以调用的过程：%r" % (proc,))


# ---------------------------------------------------------------- 特殊形式


def _eval_quote(expr):
    """(quote 数据)：原样返回，不求值（spec §4.1）。"""
    rest = expr.cdr
    if rest is NIL or not isinstance(rest, Pair):
        raise SchemeError("quote 需要一个参数")
    return rest.car


def _eval_if(expr, env):
    """(if 测试 真分支 假分支?)：只求值一个分支（spec §4.2）。"""
    parts = list(_pair_iter(expr.cdr))
    if len(parts) not in (2, 3):
        raise SchemeError("if 需要 2 或 3 个部分，收到了 %d 个" % len(parts))
    test = evaluate(parts[0], env)
    if is_true(test):
        return evaluate(parts[1], env)
    if len(parts) == 3:
        return evaluate(parts[2], env)
    return None                                   # 没有假分支且测试为假 → 无值


def _eval_cond(expr, env):
    """(cond (测试 表达式...) ... (else 表达式...))：从上到下找第一个真（§4.3）。"""
    result = None
    for clause in _pair_iter(expr.cdr):
        if not isinstance(clause, Pair):
            raise SchemeError("cond 的每个分支必须是括号包起来的列表")
        test_expr = clause.car
        # else 直接命中；否则求值测试
        hit = test_expr is S_ELSE or is_true(evaluate(test_expr, env))
        if hit:
            body = list(_pair_iter(clause.cdr))
            if not body:
                # 分支里没有表达式 → 返回测试值本身（else 不出现在这种情况）
                return evaluate(test_expr, env) if test_expr is not S_ELSE else None
            return _eval_sequence(body, env)
    return None                                   # 全不匹配 → 无值


def _eval_and(expr, env):
    """(and e1 e2 ...)：短路，遇到 #f 立刻返回 #f，否则返回最后一个（§4.4）。"""
    last = True                                   # (and) → #t
    for sub in _pair_iter(expr.cdr):
        last = evaluate(sub, env)
        if last is False:
            return False                          # 后面的表达式根本不执行
    return last


def _eval_or(expr, env):
    """(or e1 e2 ...)：短路，遇到第一个真值立刻返回它（§4.4）。"""
    for sub in _pair_iter(expr.cdr):
        value = evaluate(sub, env)
        if value is not False:
            return value                          # 后面的表达式根本不执行
    return False                                  # (or) → #f


def _eval_define(expr, env):
    """(define 名 表达式) 或 (define (函数名 参数...) 体...)（§4.5）。

    结果是**被定义的符号名**（顶层会把它打印出来）。
    """
    target = expr.cdr
    if not isinstance(target, Pair) or target.car is NIL:
        raise SchemeError("define 的语法不正确")

    head = target.car

    # 简写形式：(define (f x y) 体...)  ≡  (define f (lambda (x y) 体...))
    if isinstance(head, Pair):
        name = head.car
        if not isinstance(name, Symbol):
            raise SchemeError("函数名必须是符号")
        params = list(_pair_iter(head.cdr))
        body = list(_pair_iter(target.cdr))
        _check_params(params)
        env.define(name.name, Closure(params, body, env, name.name))
        return name

    # 普通形式：(define 名 表达式)
    if not isinstance(head, Symbol):
        raise SchemeError("被定义的名字必须是符号")
    rest = list(_pair_iter(target.cdr))
    if len(rest) != 1:
        raise SchemeError("define 需要一个值表达式")
    env.define(head.name, evaluate(rest[0], env))
    return head


def _eval_lambda(expr, env):
    """(lambda (参数...) 体...)：制造闭包，记住定义时的环境（§4.6）。"""
    target = expr.cdr
    if not isinstance(target, Pair):
        raise SchemeError("lambda 需要参数列表")
    params = list(_pair_iter(target.car)) if isinstance(target.car, Pair) else []
    body = list(_pair_iter(target.cdr))
    _check_params(params)
    return Closure(params, body, env)


def _eval_let(expr, env):
    """(let ((名 表达式)...) 体...)：并行绑定——绑定之间互不可见（§4.7）。"""
    target = expr.cdr
    if not isinstance(target, Pair):
        raise SchemeError("let 需要绑定列表")

    names = []
    values = []
    for binding in _pair_iter(target.car):
        if not isinstance(binding, Pair):
            raise SchemeError("let 的每个绑定必须是 (名 表达式)")
        name = binding.car
        if not isinstance(name, Symbol):
            raise SchemeError("let 绑定的名字必须是符号")
        rest = list(_pair_iter(binding.cdr))
        if len(rest) != 1:
            raise SchemeError("let 的每个绑定只能有一个值表达式")
        # 并行绑定：值全部在**外层**环境里算，绑定之间互不可见（§4.7）
        names.append(name)
        values.append(evaluate(rest[0], env))

    local = env.child(zip(names, values))
    body = list(_pair_iter(target.cdr))
    return _eval_sequence(body, local) if body else None


def _eval_sequence(exprs, env):
    """按顺序求值一串表达式，返回最后一个的值（begin 语义，§4.8）。"""
    result = None
    for expr in exprs:
        result = evaluate(expr, env)
    return result


# ---------------------------------------------------------------- 小工具


def _pair_iter(node):
    """遍历点对链（要求是真列表），逐个产出元素。"""
    while isinstance(node, Pair):
        yield node.car
        node = node.cdr
    if node is not NIL:
        raise SchemeError("这里需要一个真列表")


def _check_params(params):
    """检查形参列表：必须都是符号，且不重复。"""
    seen = set()
    for param in params:
        if not isinstance(param, Symbol):
            raise SchemeError("参数名必须是符号，收到了 %r" % (param,))
        if param.name in seen:
            raise SchemeError("重复的参数名：%s" % param.name)
        seen.add(param.name)


def make_global_environment():
    """新建一个装好内置过程的全局环境（每个测试用例都是全新的）。"""
    return global_environment()
