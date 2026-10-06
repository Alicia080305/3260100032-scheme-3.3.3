"""入口：读文件/标准输入 → 逐行打印结果（spec §2 的 CLI 约定）。

用法：
    python3 src/main.py file1.scm [file2.scm ...]     # 求值文件
    python3 src/main.py                               # 从标准输入读

约定：
- 按顺序求值每一个顶层表达式，**每个结果独占一行**。
- 结果为"无值"（display、newline 等）时不打印。
- 多个文件共享同一个全局环境（后一个文件看得见前一个文件的 define）。

鲁棒性：解释器是深度递归的（evaluate ↔ apply 互相调用），Python 默认的
递归深度和线程栈偏小，深层递归（如 (sum-to 5000)）会 RecursionError 甚至
直接崩栈。这里把主流程放进一个栈更大的线程里运行，并调高递归上限。
"""

import sys
import threading

from evaluator import evaluate, make_global_environment
from parser import parse
from printer import to_string
from values import SchemeError

_RECURSION_LIMIT = 60000
_STACK_BYTES = 64 * 1024 * 1024      # 64 MB，足够几万层递归


def run_program(text, env):
    """求值一段程序文本里的所有顶层表达式。"""
    for expr in parse(text):
        result = evaluate(expr, env)
        if result is not None:                # None = 无值，不打印（spec §2）
            sys.stdout.write(to_string(result) + "\n")


def _run(action):
    """统一的错误出口：mini-Scheme 的错误、文件错误、以及解释器自身的意外
    异常都要报出来——静默退出最难排查。"""
    try:
        action(make_global_environment())
    except SchemeError as err:
        sys.stderr.write("错误：%s\n" % err)
        return 1
    except RecursionError:
        sys.stderr.write("错误：递归层数太深，超出了解释器的能力范围\n")
        return 1
    except (OSError, UnicodeDecodeError) as err:
        sys.stderr.write("无法读取文件：%s\n" % err)
        return 1
    except Exception as err:                  # 兜底：内部 bug 也要暴露
        sys.stderr.write("内部错误：%s: %s\n" % (type(err).__name__, err))
        return 1
    return 0


def run_files(paths):
    """依次求值若干文件，共享同一个全局环境（spec §2）。"""
    def action(env):
        for path in paths:
            with open(path, "r", encoding="utf-8") as handle:
                run_program(handle.read(), env)
    return _run(action)


def run_stdin():
    """从标准输入读一段程序并求值（没有命令行参数时的行为）。"""
    return _run(lambda env: run_program(sys.stdin.read(), env))


def main(argv):
    if argv:
        return run_files(argv)
    return run_stdin()


def _entry():
    """真正的入口：在更大的栈上运行，避免深递归把解释器跑崩。"""
    sys.setrecursionlimit(_RECURSION_LIMIT)
    status = [0]

    def worker():
        try:
            status[0] = main(sys.argv[1:])
        except RecursionError:
            sys.stdout.flush()
            sys.stderr.write("错误：递归层数太深，超出了解释器的能力范围\n")
            status[0] = 1

    try:
        threading.stack_size(_STACK_BYTES)
    except (ValueError, RuntimeError):
        pass                                   # 某些平台不支持设置栈大小，忽略
    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    sys.exit(status[0])


if __name__ == "__main__":
    _entry()
