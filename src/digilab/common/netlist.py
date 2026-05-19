"""网表数据结构与 JSON I/O。

严格遵守 harness 附录 B：
  - chips: [{name, type}, ...]
  - inputs / outputs: 字符串列表
  - connections: [{from:{chip,pin}, to:{chip,pin}}, ...]

特殊端点用 chip="INPUT" / "OUTPUT" / "VCC" / "GND" / "NC" 表示，pin 字段：
  - INPUT/OUTPUT 时 pin 写变量名（如 "A"）
  - VCC/GND/NC 时 pin 固定为 0（占位，不参与电路语义）

排序规则（附录 B.4）：
  - 芯片实例字典序
  - 同芯片内引脚号升序
  - 端点为 INPUT/OUTPUT/VCC/GND/NC 时排在最前（按 ASCII：GND<INPUT<NC<OUTPUT<VCC）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SPECIAL_ENDPOINTS = {"INPUT", "OUTPUT", "VCC", "GND", "NC"}


@dataclass(frozen=True)
class Endpoint:
    chip: str
    pin: int | str

    def to_dict(self) -> dict[str, Any]:
        return {"chip": self.chip, "pin": self.pin}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Endpoint:
        return Endpoint(chip=d["chip"], pin=d["pin"])

    def is_special(self) -> bool:
        return self.chip in SPECIAL_ENDPOINTS

    def text(self) -> str:
        return f"{self.chip}.{self.pin}"


@dataclass(frozen=True)
class Connection:
    src: Endpoint
    dst: Endpoint

    def to_dict(self) -> dict[str, Any]:
        return {"from": self.src.to_dict(), "to": self.dst.to_dict()}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Connection:
        return Connection(src=Endpoint.from_dict(d["from"]), dst=Endpoint.from_dict(d["to"]))


@dataclass
class ChipInstance:
    name: str  # e.g. "7400_A"
    type: str  # e.g. "7400"

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "type": self.type}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> ChipInstance:
        return ChipInstance(name=d["name"], type=d["type"])


def _endpoint_sort_key(ep: Endpoint) -> tuple[int, str, int, str]:
    """先按是否特殊端点（特殊端点优先），再按 chip 名字典序，
    再按 pin（数字优先于字符串），保证排序稳定。"""
    is_normal = 0 if ep.is_special() else 1
    pin_num = ep.pin if isinstance(ep.pin, int) else 0
    pin_str = ep.pin if isinstance(ep.pin, str) else ""
    return (is_normal, ep.chip, pin_num, pin_str)


def _connection_sort_key(
    c: Connection,
) -> tuple[tuple[int, str, int, str], tuple[int, str, int, str]]:
    return (_endpoint_sort_key(c.src), _endpoint_sort_key(c.dst))


@dataclass
class Netlist:
    chips: list[ChipInstance] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)

    def add_connection(self, src: Endpoint, dst: Endpoint) -> None:
        self.connections.append(Connection(src, dst))

    def sort(self) -> None:
        """按附录 B.4 排序所有列表。"""
        self.chips.sort(key=lambda c: c.name)
        self.connections.sort(key=_connection_sort_key)

    def to_json(self) -> str:
        self.sort()
        d = {
            "chips": [c.to_dict() for c in self.chips],
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "connections": [c.to_dict() for c in self.connections],
        }
        return json.dumps(d, indent=2, ensure_ascii=False)

    def to_circuit_text(self) -> str:
        self.sort()
        return "\n".join(f"{c.src.text()} -> {c.dst.text()}" for c in self.connections) + "\n"

    def save(self, out_dir: Path) -> tuple[Path, Path]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        nj = out_dir / "netlist.json"
        ct = out_dir / "circuit.txt"
        nj.write_text(self.to_json(), encoding="utf-8")
        ct.write_text(self.to_circuit_text(), encoding="utf-8")
        return nj, ct

    @staticmethod
    def from_json(text: str) -> Netlist:
        d = json.loads(text)
        return Netlist(
            chips=[ChipInstance.from_dict(c) for c in d.get("chips", [])],
            inputs=list(d.get("inputs", [])),
            outputs=list(d.get("outputs", [])),
            connections=[Connection.from_dict(c) for c in d.get("connections", [])],
        )

    @staticmethod
    def load(path: Path) -> Netlist:
        return Netlist.from_json(Path(path).read_text(encoding="utf-8"))
