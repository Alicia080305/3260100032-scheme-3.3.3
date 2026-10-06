"""按 spec 逐条自写的验收测试（不是评分器那 12 组，而是自己补的边界）。

评分器只给了 12 组自测用例，正式评分另有隐藏用例。所以这里把 spec 里
每一条规则都写成小程序单独验证，重点是那些"看起来能过、其实容易错"的
地方：负数除法截断、短路求值、let 并行绑定、闭包捕获、eq? 与 equal? 的
区别、只有 #f 为假、display 无值不打印……

运行：python3 tests/spec_tests.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "src", "main.py")

# (说明, 程序, 期望输出)
# 期望输出是"每个顶层表达式一行"，与 spec §2 一致；None 表示只要求不崩溃。
CASES = [
    # ---- §5 算术：整数商与向零截断 ----
    ("整数相除得整数商", "(/ 7 2)", "3\n"),
    ("负数商向零截断", "(quotient -7 2)\n(/ -7 2)", "-3\n-3\n"),
    ("单参数 / 求倒数是浮点", "(/ 2)\n(/ 4)", "0.5\n0.25\n"),
    ("单参数 - 取反", "(- 5)", "-5\n"),
    ("多参数减法", "(- 10 4 1)", "5\n"),
    ("零参数加法乘法", "(+)\n(*)", "0\n1\n"),
    ("modulo 符号跟随除数（与 quotient 的截断方向不同）",
     "(modulo 17 5)\n(modulo -17 5)\n(modulo 17 -5)", "2\n3\n-3\n"),
    ("quotient 向零截断、modulo 向下取整，两者取整方向不同（-3*5+3 = -12）",
     "(quotient -17 5)\n(modulo -17 5)\n(+ (* (quotient -17 5) 5) (modulo -17 5))",
     "-3\n3\n-12\n"),
    ("expt 与 abs", "(expt 2 10)\n(abs (- 5 9))", "1024\n4\n"),

    # ---- §5 比较：链式 ----
    ("链式比较全部成立", "(< 2 3 4)", "#t\n"),
    ("链式比较中间断掉", "(< 2 5 4)", "#f\n"),
    ("= 支持符号", "(= 'a 'a)\n(= 'a 'b)", "#t\n#f\n"),

    # ---- §4.2 / §9 真假 ----
    ("0 是真", "(if 0 'truthy 'falsy)", "truthy\n"),
    ("空表是真", "(if '() 'truthy 'falsy)", "truthy\n"),
    ("只有 #f 是假", "(not 0)\n(not '())\n(not \"\")", "#f\n#f\n#f\n"),
    ("if 无假分支且测试为假 → 无值，不打印", "(if #f 'bad)\n42", "42\n"),

    # ---- §4.3 cond ----
    ("cond 子句无表达式时返回测试值", "(cond ((+ 1 2)) (else 9))", "3\n"),
    ("cond 全不匹配返回无值", "(cond (#f 1))\n5", "5\n"),
    ("cond 多表达式取最后一个", "(cond (#t 1 2 3))", "3\n"),

    # ---- §4.4 短路 ----
    ("and 短路不执行后面", "(and #f (/ 1 0))", "#f\n"),
    ("or 短路不执行后面", "(or 'yes (/ 1 0))", "yes\n"),
    ("and 返回最后一个值", "(and 1 2 'three)", "three\n"),
    ("空 and / 空 or", "(and)\n(or)", "#t\n#f\n"),

    # ---- §4.5 / §4.6 define 与 lambda ----
    ("define 返回符号名", "(define pi 3)", "pi\n"),
    ("函数定义简写", "(define (square x) (* x x))\n(square 7)", "square\n49\n"),
    ("lambda 直接调用", "((lambda (x) (* x 2)) 5)", "10\n"),
    ("函数体多条表达式取最后一条", "(define (f x) (+ x 1) (* x 10))\n(f 3)", "f\n30\n"),

    # ---- §4.7 let 是并行绑定 ----
    ("let 并行绑定：绑定之间互不可见",
     "(define x 100)\n(let ((x 1) (y (+ x 1))) (list x y))",
     "x\n(1 101)\n"),
    ("let 重名时后者生效", "(let ((x 1) (x 2)) x)", "2\n"),
    ("嵌套 let", "(let ((a 1)) (let ((b (+ a 1))) (* a b)))", "2\n"),

    # ---- §4.8 begin ----
    ("begin 顺序执行", "(begin (define z 1) (+ z 41))", "42\n"),

    # ---- §4.1 quote ----
    ("quote 不求值", "'(+ 1 2)\n(quote foo)\n'()", "(+ 1 2)\nfoo\n()\n"),
    ("quote 的数据是点对链", "(car '((1 2) 3))", "(1 2)\n"),

    # ---- §6 列表 ----
    ("点对打印带点", "(cons 1 2)", "(1 . 2)\n"),
    ("cons 到链头", "(cons 1 '(2 3))", "(1 2 3)\n"),
    ("嵌套列表打印", "(list 1 (list 2 3) '())", "(1 (2 3) ())\n"),
    ("append 多个列表", "(append '(1) '(2 3) '(4))", "(1 2 3 4)\n"),
    ("append 空表", "(append '() '())\n(append '(1 2))", "()\n(1 2)\n"),
    ("list? 与 pair? 的区别",
     "(list? '(1 2))\n(list? (cons 1 2))\n(pair? '())\n(pair? '(1))",
     "#t\n#f\n#f\n#t\n"),
    ("length 与 append 不改动原表",
     "(define xs '(1 2))\n(append xs '(3))\n(length xs)",
     "xs\n(1 2 3)\n2\n"),

    # ---- §5 谓词 ----
    ("谓词基本行为",
     "(number? 5)\n(number? 'x)\n(boolean? #t)\n(boolean? 1)\n(symbol? 'x)\n(string? \"s\")",
     "#t\n#f\n#t\n#f\n#t\n#t\n"),
    ("procedure?",
     "(procedure? car)\n(procedure? 1)\n(procedure? (lambda (x) x))",
     "#t\n#f\n#t\n"),
    ("数值谓词", "(zero? 0)\n(zero? 1)\n(even? 8)\n(odd? 7)", "#t\n#f\n#t\n#t\n"),

    # ---- §5 eq? 与 equal? ----
    ("eq? 空表按值、列表按同一性",
     "(eq? '() '())\n(eq? '(1) '(1))", "#t\n#f\n"),
    ("equal? 是结构比较", "(equal? '(1 (2 3)) (list 1 (list 2 3)))", "#t\n"),
    ("equal? 区分布尔与数字", "(equal? #t 1)\n(equal? 1 #t)", "#f\n#f\n"),
    ("equal? 区分符号与字符串", "(equal? 'a \"a\")", "#f\n"),
    ("equal? 区分点对与列表", "(equal? (cons 1 2) '(1 2))", "#f\n"),

    # ---- §8 打印 ----
    ("字符串带引号、转义可见", "\"hello\"\n\"a\\nb\"\n\"q\\\"q\"",
     "\"hello\"\n\"a\\nb\"\n\"q\\\"q\"\n"),
    ("display 不带引号且不换行", "(display \"hi\")\n(display 3)", "hi3"),
    ("display 的结果是 None，不打印", "(display 1)\n(newline)\n2", "1\n2\n"),
    ("display 列表", "(display '(a (b c)))", "(a (b c))"),

    # ---- §7 递归 ----
    ("递归求值阶乘", "(define (fact n) (if (= n 0) 1 (* n (fact (- n 1)))))\n(fact 10)",
     "fact\n3628800\n"),
    ("较深的递归不崩栈", "(define (sum-to n) (if (= n 0) 0 (+ n (sum-to (- n 1)))))\n(sum-to 2000)",
     "sum-to\n2001000\n"),

    # ---- §4.6 闭包 ----
    ("闭包记住定义时的环境",
     "(define (make-adder n) (lambda (x) (+ x n)))\n(define add5 (make-adder 5))\n(add5 10)",
     "make-adder\nadd5\n15\n"),
    ("闭包之间互不影响",
     "(define (make-adder n) (lambda (x) (+ x n)))\n(list ((make-adder 1) 0) ((make-adder 2) 0))",
     "make-adder\n(1 2)\n"),

    # ---- 用语言本身定义高阶函数（map 不内置）----
    ("用语言本身定义 map/filter",
     "(define (map f xs) (if (null? xs) '() (cons (f (car xs)) (map f (cdr xs)))))\n"
     "(map (lambda (x) (* x x)) '(1 2 3))",
     "map\n(1 4 9)\n"),

    # ---- 注释与空白 ----
    ("注释被忽略、多行表达式",
     "; 这是注释\n(+ 1   ; 行内注释\n   2)", "3\n"),
]


def run_case(program):
    """用子进程跑解释器，返回 (退出码, 标准输出, 标准错误)。"""
    proc = subprocess.run([sys.executable, MAIN], input=program,
                          capture_output=True, text=True, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def main():
    passed = failed = 0
    failures = []
    for name, program, expected in CASES:
        code, out, err = run_case(program)
        ok = (code == 0 and out == expected)
        if ok:
            passed += 1
        else:
            failed += 1
            failures.append((name, program, expected, out, err.strip(), code))

    print("spec 自测：%d 通过，%d 失败" % (passed, failed))
    for name, program, expected, out, err, code in failures:
        print("\n--- FAIL: %s ---" % name)
        print("  程序:   %r" % program)
        print("  期望:   %r" % expected)
        print("  实际:   %r" % out)
        if err:
            print("  stderr: %s" % err)
        if code != 0:
            print("  退出码: %d" % code)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
