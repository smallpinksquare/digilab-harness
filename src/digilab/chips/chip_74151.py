"""74LS151：8 选 1 数据选择器（8-to-1 Multiplexer，单通道、双互补输出）。

引脚分配（依据 TI SN74LS151 datasheet，标准 DIP-16 封装）：
    1  = D3
    2  = D2
    3  = D1
    4  = D0
    5  = Y     （正常输出）
    6  = Ȳ / W̄ （反相输出）
    7  = Ē     （低有效使能 / strobe）
    8  = GND
    9  = C     （选择位高位 S2）
    10 = B     （选择位中位 S1）
    11 = A     （选择位低位 S0）
    12 = D7
    13 = D6
    14 = D5
    15 = D4
    16 = VCC

逻辑（datasheet 真值表）：
    使能有效（Ē=0）时：
        n = 4·C + 2·B + A
        Y  = D[n]
        Ȳ  = ¬D[n]
    使能无效（Ē=1）时：
        Y = 0，Ȳ = 1

本 harness 中暴露给表达式的高层原语为
    Y, YBAR = MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)
参数顺序按"select 高位 → 低位 → D0..D7"，与 Block.inputs 引脚号
[9, 10, 11, 4, 3, 2, 1, 15, 14, 13, 12] 对齐。

默认使能（用户不显式写使能时）：
    Ē (pin 7) → GND
此连线由 synthesizer 在分配本 Block 时自动加入 netlist。
"""

from __future__ import annotations

from . import Block, ChipSpec, Pin, PinType


def mux8(bits: list[int]) -> list[int]:
    """完整 12 输入函数：[C, B, A, D0..D7, E_BAR] -> [Y, Y_BAR]。"""
    if len(bits) != 12:
        raise ValueError(f"74151 mux8 需要 12 位输入 [C,B,A,D0..D7,E_BAR]，收到 {len(bits)}")
    c, b, a = bits[0], bits[1], bits[2]
    data = bits[3:11]
    e_bar = bits[11]
    if e_bar == 1:
        return [0, 1]
    sel = ((c & 1) << 2) | ((b & 1) << 1) | (a & 1)
    y = data[sel] & 1
    return [y, 1 - y]


def _mux8_block_func(bits: list[int]) -> list[int]:
    """Block 视角函数：[C, B, A, D0..D7] -> [Y, Y_BAR]，内部默认 E_BAR=0。"""
    if len(bits) != 11:
        raise ValueError(f"MUX8 需要 11 位输入 [C,B,A,D0..D7]，收到 {len(bits)}")
    return mux8(list(bits) + [0])


def make_spec() -> ChipSpec:
    spec = ChipSpec(model="74151")

    # 数据输入 D0..D7
    spec.pins[4] = Pin(number=4, type=PinType.INPUT, role="D0")
    spec.pins[3] = Pin(number=3, type=PinType.INPUT, role="D1")
    spec.pins[2] = Pin(number=2, type=PinType.INPUT, role="D2")
    spec.pins[1] = Pin(number=1, type=PinType.INPUT, role="D3")
    spec.pins[15] = Pin(number=15, type=PinType.INPUT, role="D4")
    spec.pins[14] = Pin(number=14, type=PinType.INPUT, role="D5")
    spec.pins[13] = Pin(number=13, type=PinType.INPUT, role="D6")
    spec.pins[12] = Pin(number=12, type=PinType.INPUT, role="D7")
    # 选择输入
    spec.pins[11] = Pin(number=11, type=PinType.INPUT, role="A")
    spec.pins[10] = Pin(number=10, type=PinType.INPUT, role="B")
    spec.pins[9] = Pin(number=9, type=PinType.INPUT, role="C")
    # 使能（默认 Ē=GND）
    spec.pins[7] = Pin(number=7, type=PinType.INPUT, role="E_BAR")
    # 双互补输出
    spec.pins[5] = Pin(number=5, type=PinType.OUTPUT, role="Y")
    spec.pins[6] = Pin(number=6, type=PinType.OUTPUT, role="Y_BAR")
    # 电源 / 地
    spec.pins[8] = Pin(number=8, type=PinType.GND)
    spec.pins[16] = Pin(number=16, type=PinType.VCC)

    spec.blocks.append(
        Block(
            block_id=0,
            inputs=[9, 10, 11, 4, 3, 2, 1, 15, 14, 13, 12],  # C, B, A, D0..D7
            outputs=[5, 6],  # Y, Y_BAR
            func=_mux8_block_func,
            primitive="MUX8",
            default_enables=[(7, "GND")],  # Ē 默认使能
        )
    )

    return spec


SPEC = make_spec()


# ---------- 文件内自检：不依赖 pytest 也能跑 ----------


def _self_check() -> None:
    """16 行真值表（8 地址 × 使能 on/off）。

    使能有效时 Y = D[sel]、Ȳ = ¬Y；使能无效时 Y = 0、Ȳ = 1。
    """
    fails: list[str] = []
    # 取一个不平凡的数据模式 [0, 1, 0, 1, 1, 0, 1, 0]，覆盖所有 D 位
    data = [0, 1, 0, 1, 1, 0, 1, 0]

    # (1) 使能有效：扫 8 个地址
    for sel in range(8):
        a = sel & 1
        b = (sel >> 1) & 1
        c = (sel >> 2) & 1
        out = mux8([c, b, a] + data + [0])
        exp_y = data[sel]
        expected = [exp_y, 1 - exp_y]
        if out != expected:
            fails.append(f"使能 ON sel={sel:03b} 期望 {expected} 实际 {out}")
    # (2) 使能无效：扫 8 个地址，输出应恒为 [0, 1]
    for sel in range(8):
        a = sel & 1
        b = (sel >> 1) & 1
        c = (sel >> 2) & 1
        out = mux8([c, b, a] + data + [1])
        if out != [0, 1]:
            fails.append(f"使能 OFF sel={sel:03b} 期望 [0, 1] 实际 {out}")
    if fails:
        raise AssertionError("74151 自检失败：\n  " + "\n  ".join(fails))
    print("74151 自检通过：16 行真值表全部一致")


if __name__ == "__main__":
    _self_check()
