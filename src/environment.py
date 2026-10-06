"""环境：变量绑定表 + 指向外层环境的指针。

环境就是"名字 → 值"的一张表。每个环境还有一根指向**外层环境**的针，
查名字时先查自己，查不到就顺着针往外找（spec §9 词法作用域）。

这张针是闭包的关键：lambda 记住定义时所在的环境，调用时才新建一层子环境，
所以闭包能一直看见定义处的变量（spec §4.6、§11 的 008/009 用例）。
"""

from values import SchemeError, Symbol


class Environment:
    """一层环境。parent 为 None 表示全局环境。"""

    __slots__ = ("_table", "parent")

    def __init__(self, parent=None, bindings=None):
        self._table = dict(bindings) if bindings else {}
        self.parent = parent

    @staticmethod
    def _key(name):
        """统一用字符串做键：Symbol 取它的名字，字符串原样使用。

        这样调用方传 Symbol 还是 str 都不会出错（内置库注册、let 绑定、
        函数形参绑定三处写法不同，统一在这一层收口）。
        """
        return name.name if isinstance(name, Symbol) else name

    def define(self, name, value):
        """在当前层绑定（或覆盖）一个名字。define 永远只作用于当前层。"""
        self._table[self._key(name)] = value

    def lookup(self, name):
        """查名字的值：先自己，再逐层向外；找不到就报错。"""
        key = self._key(name)
        env = self
        while env is not None:
            if key in env._table:
                return env._table[key]
            env = env.parent
        raise SchemeError("未绑定的变量：%s" % key)

    def resolve(self, name):
        """返回"拥有这个名字"的那一层环境；不存在则返回 None。

        （这里没有 set!，保留此方法是为了将来扩展赋值时不必改动结构。）
        """
        key = self._key(name)
        env = self
        while env is not None:
            if key in env._table:
                return env
            env = env.parent
        return None

    def child(self, bindings=None):
        """新建一层子环境，外层指向自己（let / 函数调用都用它）。"""
        if bindings is None:
            return Environment(self)
        return Environment(self, {self._key(k): v for k, v in bindings})
