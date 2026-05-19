"""逻辑表达式文件的解析器。

文件格式（参见 真值表与逻辑表达式/示例_表达式.md）：

    chips:   7400 x 2, 7420 x 1
    inputs:  A, B, C
    outputs: F, G

    F = NAND2(A, B)
    G = NAND4(A, B, C, NAND2(A, B))

允许：
  - 任意多空行 / 行末注释（# ...）
  - 表达式可嵌套
  - md 文件中的 ``` 围栏会被忽略，方便直接放在 markdown 段落里
  - 大小写不敏感的关键字（chips/inputs/outputs / NAND2 / NAND4）
"""

from __future__ import annotations

import re
from pathlib import Path

from .ast_nodes import Assignment, Const, Nand, Node, Primitive, Program, Var

_HEADER_KEYWORDS = {"chips", "inputs", "outputs"}
_NAND_PATTERN = re.compile(r"^NAND(2|4)$", re.IGNORECASE)

# 已识别的多 I/O 原语名 → 输出数。
# 新增高层原语只需在此登记一行（且对应 chips/<chip_xxx>.py 提供同名 Block）。
_PRIMITIVE_OUTPUT_COUNT = {
    "DECODE3": 8,  # 74138：3 输入地址 → 8 路低有效输出
    "MUX4": 1,  # 74153：4 选 1，多路输入单路输出
    "MUX8": 2,  # 74151：8 选 1，11 路输入双互补输出 (Y, Ȳ)
}


class ParseError(ValueError):
    pass


# ---------- 文件预处理 ----------


def _strip_comment(line: str) -> str:
    if "#" in line:
        line = line[: line.index("#")]
    return line.rstrip()


_HEADER_LINE_RE = re.compile(r"^\s*(chips|inputs|outputs)\s*:", re.IGNORECASE)
# 允许单 LHS（"Y = ..."）与多 LHS（"Y0, Y1, ..., Y7 = ..."）。
_ASSIGN_LINE_RE = re.compile(r"^\s*[A-Za-z_]\w*(\s*,\s*[A-Za-z_]\w*)*\s*=")


def _preprocess(text: str) -> list[str]:
    """挑出 md 文件中真正的"语义行"，并把多行表达式合并为一行。

    规则：
      - 三反引号围栏内：所有非空行都视为有效（除注释）
      - 围栏外：只接受形如 "chips:/inputs:/outputs:" 或 "name = ..." 的行；
        其余（标题、引用、说明文字等）一律忽略
      - 当一行的左右括号未配对时，自动把后续行接入，直到括号平衡
    """
    out: list[str] = []
    in_fence = False
    pending: str = ""

    def _balanced(s: str) -> bool:
        return s.count("(") == s.count(")")

    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue

        cleaned = _strip_comment(raw)
        if not cleaned.strip():
            continue

        if pending:
            pending += " " + cleaned.strip()
            if _balanced(pending):
                out.append(pending)
                pending = ""
            continue

        if not in_fence and not (_HEADER_LINE_RE.match(cleaned) or _ASSIGN_LINE_RE.match(cleaned)):
            continue

        if _balanced(cleaned):
            out.append(cleaned)
        else:
            pending = cleaned

    if pending:
        raise ParseError(f"表达式括号未配对：{pending!r}")
    return out


# ---------- 表达式词法 / 语法 ----------

_TOKEN_RE = re.compile(r"\s*(?:(\d+)|([A-Za-z_]\w*)|([(),])|(.))")


def _tokenize(s: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(s):
        m = _TOKEN_RE.match(s, i)
        if not m:
            raise ParseError(f"无法解析表达式片段：{s[i:]}")
        num, word, sym, bad = m.groups()
        if num is not None:
            tokens.append(num)
        elif word is not None:
            tokens.append(word)
        elif sym is not None:
            tokens.append(sym)
        elif bad is not None and not bad.isspace():
            raise ParseError(f"非法字符 {bad!r}")
        i = m.end()
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str:
        if self.pos >= len(self.tokens):
            return ""
        return self.tokens[self.pos]

    def consume(self, expected: str = "") -> str:
        if self.pos >= len(self.tokens):
            raise ParseError(f"意外结束，期望 {expected!r}")
        t = self.tokens[self.pos]
        if expected and t != expected:
            raise ParseError(f"期望 {expected!r}，得到 {t!r}")
        self.pos += 1
        return t

    def parse_expr(self) -> Node:
        tok = self.peek()
        if not tok:
            raise ParseError("空表达式")
        # 字面量 0 / 1（连 GND / VCC）
        if tok in ("0", "1"):
            self.consume()
            return Const(value=int(tok))
        # NAND2 / NAND4
        m = _NAND_PATTERN.match(tok)
        if m:
            arity = int(m.group(1))
            self.consume()
            self.consume("(")
            args = [self.parse_expr()]
            while self.peek() == ",":
                self.consume(",")
                args.append(self.parse_expr())
            self.consume(")")
            if len(args) != arity:
                raise ParseError(f"NAND{arity} 需要 {arity} 个参数，得到 {len(args)}")
            return Nand(args=tuple(args))
        # 高层多 I/O 原语：DECODE3 / MUX4 等
        if tok.upper() in _PRIMITIVE_OUTPUT_COUNT:
            name = tok.upper()
            self.consume()
            self.consume("(")
            args = [self.parse_expr()]
            while self.peek() == ",":
                self.consume(",")
                args.append(self.parse_expr())
            self.consume(")")
            return Primitive(name=name, args=tuple(args))
        # 否则是变量
        if not re.match(r"^[A-Za-z_]\w*$", tok):
            raise ParseError(f"非法标识符 {tok!r}")
        self.consume()
        return Var(name=tok)


def _parse_expr_text(text: str) -> Node:
    p = _Parser(_tokenize(text))
    node = p.parse_expr()
    if p.pos != len(p.tokens):
        raise ParseError(f"表达式结尾有多余内容：{p.tokens[p.pos :]}")
    return node


# ---------- 头部声明 ----------


def _parse_chips_decl(value: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        m = re.match(r"^([0-9A-Za-z_]+)\s*[xX*]\s*(\d+)$", item)
        if not m:
            raise ParseError(f"chips 项格式错误：{item!r}（期望 '7400 x 2'）")
        out.append((m.group(1), int(m.group(2))))
    return out


def _parse_id_list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


# ---------- 顶层入口 ----------


def parse_program_text(text: str) -> Program:
    lines = _preprocess(text)
    prog = Program()

    for line in lines:
        if ":" in line and line.split(":", 1)[0].strip().lower() in _HEADER_KEYWORDS:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "chips":
                prog.chips_decl = _parse_chips_decl(value)
            elif key == "inputs":
                prog.inputs = _parse_id_list(value)
            elif key == "outputs":
                prog.outputs = _parse_id_list(value)
            continue

        if "=" in line:
            lhs, rhs = line.split("=", 1)
            names = [s.strip() for s in lhs.split(",")]
            if not names or any(not n for n in names):
                raise ParseError(f"赋值 LHS 不可为空：{line!r}")
            for n in names:
                if not re.match(r"^[A-Za-z_]\w*$", n):
                    raise ParseError(f"非法输出变量名 {n!r}")
            if len(names) != len(set(names)):
                raise ParseError(f"同一行赋值的 LHS 名字重复：{names}")
            expr = _parse_expr_text(rhs)
            # 多 LHS 校验：必须是直接调多输出 Primitive
            if len(names) > 1:
                if not isinstance(expr, Primitive):
                    raise ParseError(
                        f"多 LHS 赋值的右侧必须是多输出原语调用，"
                        f"如 DECODE3(...)；得到 {type(expr).__name__}"
                    )
                expected = _PRIMITIVE_OUTPUT_COUNT.get(expr.name)
                if expected is None:
                    raise ParseError(f"未知多输出原语 {expr.name!r}")
                if len(names) != expected:
                    raise ParseError(
                        f"{expr.name} 输出数为 {expected}，但 LHS 给出 {len(names)} 个名字：{names}"
                    )
            else:
                # 单 LHS 不允许调多输出原语（语义不明确）
                if isinstance(expr, Primitive):
                    expected = _PRIMITIVE_OUTPUT_COUNT.get(expr.name, 1)
                    if expected != 1:
                        raise ParseError(
                            f"原语 {expr.name} 输出 {expected} 路，"
                            f"必须用多 LHS 接收（如 Y0, Y1, ..., Y{expected - 1} = ...）"
                        )
            prog.assignments.append(Assignment(name=names[0], expr=expr, extra_names=names[1:]))
            continue

        raise ParseError(f"无法识别的行：{line!r}")

    if not prog.assignments:
        raise ParseError("未发现任何赋值表达式")
    if not prog.inputs:
        raise ParseError("缺少 inputs 声明")
    if not prog.outputs:
        raise ParseError("缺少 outputs 声明")
    if not prog.chips_decl:
        raise ParseError("缺少 chips 声明")

    # 收集全部 LHS 名字（包含多输出每一路）
    declared_lhs: list[str] = []
    for a in prog.assignments:
        declared_lhs.extend(a.all_names)
    declared_set = set(declared_lhs)
    if len(declared_set) != len(declared_lhs):
        seen: set[str] = set()
        dup: list[str] = []
        for n in declared_lhs:
            if n in seen:
                dup.append(n)
            else:
                seen.add(n)
        raise ParseError(f"赋值 LHS 重复：{sorted(set(dup))}")

    missing = set(prog.outputs) - declared_set
    if missing:
        raise ParseError(f"outputs 中存在未被赋值的变量：{sorted(missing)}")

    # 中间变量与输入名不可冲突
    overlap = declared_set & set(prog.inputs)
    if overlap:
        raise ParseError(f"赋值 LHS 与 inputs 同名：{sorted(overlap)}")

    # 校验"先定后用"：每个表达式中引用的变量必须是 inputs 或前面已定义过的 LHS
    visible = set(prog.inputs)
    for asgn in prog.assignments:
        for v in _collect_var_refs(asgn.expr):
            if v not in visible:
                raise ParseError(
                    f"赋值 {asgn.name!r} 中引用了未定义变量 {v!r}（中间变量必须先定义后引用）"
                )
        for n in asgn.all_names:
            visible.add(n)

    return prog


def _collect_var_refs(node: Node) -> set[str]:
    if isinstance(node, Var):
        return {node.name}
    if isinstance(node, Const):
        return set()
    if isinstance(node, (Nand, Primitive)):
        out: set[str] = set()
        for a in node.args:
            out |= _collect_var_refs(a)
        return out
    return set()


def parse_program_file(path: Path) -> Program:
    return parse_program_text(Path(path).read_text(encoding="utf-8-sig"))
