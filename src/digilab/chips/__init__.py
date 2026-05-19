"""芯片库基础类型与抽象。

每个具体器件（如 7400、7420）放一个 chip_xxxx.py 文件，继承 ChipSpec，
并在 registry.py 中注册。synthesizer.py 与 verifier.py 不直接 import
具体器件，全部通过 registry 查询，便于扩展。

抽象层级：
  - Pin：芯片上的物理引脚（INPUT/OUTPUT/VCC/GND/NC）
  - Gate：芯片内的"单输出逻辑门"（NAND2/NAND4 等小规模与非门，对应 7400/7420）
  - Block：芯片内的"多输入多输出器件块"（译码器/MUX 等中规模器件，
           对应 74138/74153），与 Gate 平行存在；7400/7420 留空 blocks
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum


class PinType(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    VCC = "VCC"
    GND = "GND"
    NC = "NC"


@dataclass(frozen=True)
class Pin:
    """芯片上的一个物理引脚。"""

    number: int
    type: PinType
    gate_id: int = -1  # 属于第几个门（同芯片内 0,1,2,...）；电源/GND/NC 用 -1
    role: str = ""  # 在该门内的角色：'in0' / 'in1' / ... / 'out'


@dataclass
class Gate:
    """芯片内的一个逻辑门。"""

    gate_id: int
    inputs: list[int]  # 输入引脚号列表（按顺序）
    output: int  # 输出引脚号
    func: Callable[[list[int]], int]  # 逻辑函数：输入位列表 → 输出位


@dataclass
class Block:
    """芯片内的一个多输入多输出器件块（译码器、MUX 等）。

    与 Gate 平行存在；同一片芯片可同时有 gates 和 blocks（罕见），
    74138 / 74153 这类中规模器件 gates 留空，blocks 提供描述。
    """

    block_id: int
    inputs: list[int]  # 信号输入引脚（按表达式参数顺序）
    outputs: list[int]  # 信号输出引脚（按 LHS 索引顺序）
    func: Callable[[list[int]], list[int]]  # 多输出函数：输入位列表 → 输出位列表
    primitive: str  # 关联的高层原语名（"DECODE3" / "MUX4"）
    default_enables: list[tuple[int, str]] = field(default_factory=list)
    """默认使能连线：[(pin_number, "VCC"|"GND"), ...]
    用户不显式写使能时，综合器自动加这些显式 netlist 连线。"""


@dataclass
class ChipSpec:
    """器件型号说明（不是芯片实例）。"""

    model: str
    pins: dict[int, Pin] = field(default_factory=dict)
    gates: list[Gate] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)

    @property
    def vcc_pins(self) -> list[int]:
        return sorted(n for n, p in self.pins.items() if p.type is PinType.VCC)

    @property
    def gnd_pins(self) -> list[int]:
        return sorted(n for n, p in self.pins.items() if p.type is PinType.GND)

    @property
    def nc_pins(self) -> list[int]:
        return sorted(n for n, p in self.pins.items() if p.type is PinType.NC)

    @property
    def num_gates(self) -> int:
        return len(self.gates)

    @property
    def num_blocks(self) -> int:
        return len(self.blocks)

    def gate(self, gate_id: int) -> Gate:
        return self.gates[gate_id]

    def block(self, block_id: int) -> Block:
        return self.blocks[block_id]
