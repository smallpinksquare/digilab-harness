"""7420：两个 4 输入与非门。

引脚分配（依据 harness）：
    门0  in: 1, 2, 4, 5      out: 6     （3 是 NC）
    门1  in: 9, 10, 12, 13   out: 8     （11 是 NC）
    电源: 14 = VCC    地: 7 = GND
"""

from __future__ import annotations

from . import ChipSpec, Gate, Pin, PinType


def nand4(bits: list[int]) -> int:
    if len(bits) != 4:
        raise ValueError(f"7420 NAND4 需要 4 个输入，收到 {len(bits)}")
    return 0 if all(b == 1 for b in bits) else 1


def make_spec() -> ChipSpec:
    spec = ChipSpec(model="7420")

    gate_pin_table = [
        (0, [1, 2, 4, 5], 6),
        (1, [9, 10, 12, 13], 8),
    ]

    for gid, ins, out in gate_pin_table:
        for i, pn in enumerate(ins):
            spec.pins[pn] = Pin(number=pn, type=PinType.INPUT, gate_id=gid, role=f"in{i}")
        spec.pins[out] = Pin(number=out, type=PinType.OUTPUT, gate_id=gid, role="out")
        spec.gates.append(Gate(gate_id=gid, inputs=list(ins), output=out, func=nand4))

    spec.pins[3] = Pin(number=3, type=PinType.NC)
    spec.pins[11] = Pin(number=11, type=PinType.NC)

    spec.pins[7] = Pin(number=7, type=PinType.GND)
    spec.pins[14] = Pin(number=14, type=PinType.VCC)

    return spec


SPEC = make_spec()
