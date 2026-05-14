"""74LS153：双 4 选 1 数据选择器（Dual 4-to-1 Multiplexer）。

引脚分配（依据 TI SN74LS153 datasheet，标准 DIP-16 封装）：
    1  = 1G̅   （通道 1 低有效使能）
    2  = B     （公共选择位高位）
    3  = 1C3
    4  = 1C2
    5  = 1C1
    6  = 1C0
    7  = 1Y
    8  = GND
    9  = 2Y
    10 = 2C3
    11 = 2C2
    12 = 2C1
    13 = 2C0
    14 = A     （公共选择位低位）
    15 = 2G̅   （通道 2 低有效使能）
    16 = VCC

逻辑：
    使能有效（nG̅=0）时：nY = nC[2*B + A]
    使能无效（nG̅=1）时：nY = 0

本 Step3 仅暴露通道 1 为一个 Block（primitive="MUX4"）：
    MUX4(B, A, C0, C1, C2, C3) -> Y
并默认把 1G̅（pin 1）接 GND，使能有效。
通道 2 本期不分配，相关引脚标记为 NC。
"""

from __future__ import annotations

from typing import List

from . import Block, ChipSpec, Pin, PinType


def mux4(bits: List[int]) -> int:
    """完整 7 输入函数：[B, A, C0, C1, C2, C3, G_BAR] -> Y。"""
    if len(bits) != 7:
        raise ValueError(f"74153 mux4 需要 7 位输入 [B,A,C0,C1,C2,C3,G_BAR]，收到 {len(bits)}")
    b, a, c0, c1, c2, c3, g_bar = bits
    if g_bar == 1:
        return 0
    sel = ((b & 1) << 1) | (a & 1)
    data = [c0, c1, c2, c3]
    return data[sel] & 1


def _mux4_block_func(bits: List[int]) -> List[int]:
    """Block 视角函数：[B,A,C0,C1,C2,C3] -> [Y]，内部默认 G_BAR=0。"""
    if len(bits) != 6:
        raise ValueError(f"MUX4 需要 6 位输入 [B,A,C0,C1,C2,C3]，收到 {len(bits)}")
    b, a, c0, c1, c2, c3 = bits
    return [mux4([b, a, c0, c1, c2, c3, 0])]


def make_spec() -> ChipSpec:
    spec = ChipSpec(model="74153")

    # 通道 1（本期暴露）
    spec.pins[1] = Pin(number=1, type=PinType.INPUT, role="1G_BAR")
    spec.pins[2] = Pin(number=2, type=PinType.INPUT, role="B")
    spec.pins[3] = Pin(number=3, type=PinType.INPUT, role="1C3")
    spec.pins[4] = Pin(number=4, type=PinType.INPUT, role="1C2")
    spec.pins[5] = Pin(number=5, type=PinType.INPUT, role="1C1")
    spec.pins[6] = Pin(number=6, type=PinType.INPUT, role="1C0")
    spec.pins[7] = Pin(number=7, type=PinType.OUTPUT, role="1Y")
    spec.pins[14] = Pin(number=14, type=PinType.INPUT, role="A")

    # 通道 2（本期闲置）
    for pn, role in [
        (9, "2Y"),
        (10, "2C3"),
        (11, "2C2"),
        (12, "2C1"),
        (13, "2C0"),
        (15, "2G_BAR"),
    ]:
        spec.pins[pn] = Pin(number=pn, type=PinType.NC, role=role)

    # 电源
    spec.pins[8] = Pin(number=8, type=PinType.GND)
    spec.pins[16] = Pin(number=16, type=PinType.VCC)

    spec.blocks.append(
        Block(
            block_id=0,
            inputs=[2, 14, 6, 5, 4, 3],  # B, A, C0, C1, C2, C3
            outputs=[7],  # 1Y
            func=_mux4_block_func,
            primitive="MUX4",
            default_enables=[(1, "GND")],  # 1G̅ 默认使能
        )
    )

    return spec


SPEC = make_spec()


def _self_check() -> None:
    """8 行代表性自检：4 种选择 × 使能 on/off。"""
    fails: List[str] = []
    data = [0, 1, 0, 1]
    for sel in range(4):
        b = (sel >> 1) & 1
        a = sel & 1
        exp_on = data[sel]
        got_on = mux4([b, a, data[0], data[1], data[2], data[3], 0])
        if got_on != exp_on:
            fails.append(f"enable=0 sel={sel} expected={exp_on} got={got_on}")
        got_off = mux4([b, a, data[0], data[1], data[2], data[3], 1])
        if got_off != 0:
            fails.append(f"enable=1 sel={sel} expected=0 got={got_off}")
    if fails:
        raise AssertionError("74153 自检失败：\n  " + "\n  ".join(fails))
    print("74153 自检通过：8 行代表性真值表一致")


if __name__ == "__main__":
    _self_check()
