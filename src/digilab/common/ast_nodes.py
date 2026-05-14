"""逻辑表达式 AST。

支持的原语：
  - Var(name)         — 变量引用（输入或中间变量）
  - Const(value)      — 字面量 0 或 1（综合时连 GND / VCC）
  - Nand(args)        — 与非门，args 长度 = 2 → 走 7400；= 4 → 走 7420
  - Primitive(name, args) — 高层多 I/O 原语（DECODE3 / MUX4 等）。
                            参数顺序与器件 Block.inputs 对齐；返回多端点时
                            必须以多 LHS 赋值接收（详见 parser）

不做任何代数变换，因为附录 A.2 规定表达式已写成器件原生形式。
所有节点都是 frozen dataclass，可哈希，便于 synthesizer 做结构化 CSE。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Union


@dataclass(frozen=True)
class Var:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Const:
    value: int  # 0 或 1

    def __post_init__(self) -> None:
        if self.value not in (0, 1):
            raise ValueError(f"Const 只允许 0 或 1，得到 {self.value}")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class Nand:
    args: Tuple["Node", ...]

    @property
    def arity(self) -> int:
        return len(self.args)

    def __str__(self) -> str:
        return f"NAND{self.arity}({', '.join(str(a) for a in self.args)})"


@dataclass(frozen=True)
class Primitive:
    """高层多 I/O 原语（DECODE3 / MUX4 等）。

    name 必须为大写规范名，与 chips/<chip_xxx>.py 中 Block.primitive 一致。
    args 顺序与对应器件 Block.inputs 顺序对齐。
    """

    name: str
    args: Tuple["Node", ...]

    @property
    def arity(self) -> int:
        return len(self.args)

    def __str__(self) -> str:
        return f"{self.name}({', '.join(str(a) for a in self.args)})"


Node = Union[Var, Const, Nand, Primitive]


@dataclass
class Assignment:
    """一行赋值：name = expr，或多 LHS：name, n1, n2, ... = expr。

    单 LHS（NAND / 字面量）时 extra_names 为空，name 即变量名。
    多 LHS（多输出 Primitive，如 DECODE3）时：
      - name 仍是第 0 个输出名（对应 Block.outputs[0]）
      - extra_names = [name_1, name_2, ...] 对应 Block.outputs[1:]
      - all_names 给出完整顺序列表
    """

    name: str
    expr: Node
    extra_names: List[str] = field(default_factory=list)

    @property
    def all_names(self) -> List[str]:
        return [self.name, *self.extra_names]


@dataclass
class Program:
    """整份表达式文件解析后的结果。"""

    chips_decl: List[Tuple[str, int]] = field(default_factory=list)  # [(model, count), ...]
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    assignments: List[Assignment] = field(default_factory=list)
