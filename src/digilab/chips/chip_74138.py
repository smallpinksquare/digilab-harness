"""74LS138：3 线-8 线译码器（双使能版本：1 高有效 + 2 低有效）。

引脚分配（依据 TI SN74LS138 datasheet，标准 DIP-16 封装）：
    1  = A   （地址低位 / bit 0）
    2  = B   （地址中位 / bit 1）
    3  = C   （地址高位 / bit 2）
    4  = G2A̅（低有效使能）
    5  = G2B̅（低有效使能）
    6  = G1  （高有效使能）
    7  = Y7̅
    8  = GND
    9  = Y6̅
    10 = Y5̅
    11 = Y4̅
    12 = Y3̅
    13 = Y2̅
    14 = Y1̅
    15 = Y0̅
    16 = VCC

逻辑（datasheet 真值表）：
    使能有效（G1=1 且 G2A̅=0 且 G2B̅=0）时：
        n = 4·C + 2·B + 1·A
        Yn̅ = 0，其余 Ym̅ = 1
    使能无效时所有 Yn̅ = 1

本 harness 中暴露给表达式的高层原语为
    DECODE3(C, B, A)
参数顺序按"高位 → 低位"，与 Block.inputs 引脚号 [3, 2, 1] 对齐。

默认使能（用户不显式写使能时）：
    G1 (pin 6) → VCC
    G2A̅ (pin 4) → GND
    G2B̅ (pin 5) → GND
这三条连线由 synthesizer 在分配本 Block 时自动加入 netlist。
"""

from __future__ import annotations

from typing import List

from . import Block, ChipSpec, Pin, PinType


def decode3(bits: List[int]) -> List[int]:
    """完整 6 输入译码函数：[A, B, C, G1, G2A_BAR, G2B_BAR] → [Y0..Y7]。

    输入位顺序固定为引脚号 [1, 2, 3, 6, 4, 5]（datasheet 自然顺序），
    输出位顺序为 [Y0, Y1, ..., Y7]，对应引脚 [15, 14, 13, 12, 11, 10, 9, 7]。

    使能无效时全部输出为 1。
    """
    if len(bits) != 6:
        raise ValueError(f"74138 decode3 需要 6 位输入 [A,B,C,G1,G2A̅,G2B̅]，收到 {len(bits)}")
    a, b, c, g1, g2a_bar, g2b_bar = bits
    enabled = (g1 == 1) and (g2a_bar == 0) and (g2b_bar == 0)
    if not enabled:
        return [1] * 8
    n = (c & 1) * 4 + (b & 1) * 2 + (a & 1)
    out = [1] * 8
    out[n] = 0
    return out


def _decode3_block_func(addr_bits: List[int]) -> List[int]:
    """Block 暴露给表达式的"用户视角"函数：仅 3 输入地址 [C, B, A] → 8 输出。

    使能信号通过 default_enables 显式连到 VCC/GND，verifier 在并查集合并后
    把它们当作恒定信号求值；本函数因此只接收用户表达式提供的 3 个地址输入。

    Block.inputs = [3, 2, 1]（引脚号 C, B, A），故位顺序与 datasheet 内函数
    [A, B, C, ...] 不一致，本函数把它转回 datasheet 顺序再调用 decode3。
    """
    if len(addr_bits) != 3:
        raise ValueError(f"DECODE3 需要 3 位地址 [C,B,A]，收到 {len(addr_bits)}")
    c, b, a = addr_bits
    # 使能默认有效（G1=1, G2A̅=0, G2B̅=0）
    return decode3([a, b, c, 1, 0, 0])


def make_spec() -> ChipSpec:
    spec = ChipSpec(model="74138")

    # 地址输入
    spec.pins[1] = Pin(number=1, type=PinType.INPUT, gate_id=-1, role="A")
    spec.pins[2] = Pin(number=2, type=PinType.INPUT, gate_id=-1, role="B")
    spec.pins[3] = Pin(number=3, type=PinType.INPUT, gate_id=-1, role="C")
    # 使能输入
    spec.pins[4] = Pin(number=4, type=PinType.INPUT, gate_id=-1, role="G2A_BAR")
    spec.pins[5] = Pin(number=5, type=PinType.INPUT, gate_id=-1, role="G2B_BAR")
    spec.pins[6] = Pin(number=6, type=PinType.INPUT, gate_id=-1, role="G1")
    # 输出 Y0..Y7（注意：Y0 在 pin 15、Y7 在 pin 7）
    spec.pins[15] = Pin(number=15, type=PinType.OUTPUT, gate_id=-1, role="Y0")
    spec.pins[14] = Pin(number=14, type=PinType.OUTPUT, gate_id=-1, role="Y1")
    spec.pins[13] = Pin(number=13, type=PinType.OUTPUT, gate_id=-1, role="Y2")
    spec.pins[12] = Pin(number=12, type=PinType.OUTPUT, gate_id=-1, role="Y3")
    spec.pins[11] = Pin(number=11, type=PinType.OUTPUT, gate_id=-1, role="Y4")
    spec.pins[10] = Pin(number=10, type=PinType.OUTPUT, gate_id=-1, role="Y5")
    spec.pins[9] = Pin(number=9, type=PinType.OUTPUT, gate_id=-1, role="Y6")
    spec.pins[7] = Pin(number=7, type=PinType.OUTPUT, gate_id=-1, role="Y7")
    # 电源 / 地
    spec.pins[8] = Pin(number=8, type=PinType.GND)
    spec.pins[16] = Pin(number=16, type=PinType.VCC)

    spec.blocks.append(
        Block(
            block_id=0,
            inputs=[3, 2, 1],  # C, B, A（高位→低位）
            outputs=[15, 14, 13, 12, 11, 10, 9, 7],  # Y0..Y7
            func=_decode3_block_func,
            primitive="DECODE3",
            default_enables=[(6, "VCC"), (4, "GND"), (5, "GND")],
        )
    )

    return spec


SPEC = make_spec()


# ---------- 文件内自检：不依赖 pytest 也能跑 ----------


def _self_check() -> None:
    """16 行真值表（8 地址 × 使能 on/off）。

    使能有效时被选中的 Yn̅=0，其余=1；使能无效时全部=1。
    """
    fails = []
    # (1) 使能有效：扫 8 个地址
    for addr in range(8):
        a = addr & 1
        b = (addr >> 1) & 1
        c = (addr >> 2) & 1
        out = decode3([a, b, c, 1, 0, 0])
        expected = [1] * 8
        expected[addr] = 0
        if out != expected:
            fails.append(f"使能 ON addr={addr:03b} 期望 {expected} 实际 {out}")
    # (2) 使能无效（G1=0 一种代表）：扫 8 个地址，输出应全 1
    for addr in range(8):
        a = addr & 1
        b = (addr >> 1) & 1
        c = (addr >> 2) & 1
        out = decode3([a, b, c, 0, 0, 0])
        if out != [1] * 8:
            fails.append(f"使能 OFF (G1=0) addr={addr:03b} 期望全 1 实际 {out}")
    if fails:
        raise AssertionError("74138 自检失败：\n  " + "\n  ".join(fails))
    print("74138 自检通过：16 行真值表全部一致")


if __name__ == "__main__":
    _self_check()
