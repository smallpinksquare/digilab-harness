"""Circuit synthesizer: expression file → circuit.txt + netlist.json.

Input:  expression file (chips declaration, inputs, outputs, assignments)
Output: circuit.txt + netlist.json (sorted per harness spec, incl. VCC/GND/NC)

CLI (via the ``digilab`` package entry-point, preferred)::

    digilab synth --expr <expr.md> --out <out_dir>

Or directly::

    python -m digilab.synthesizer --expr <expr.md> --out <out_dir>
    # Optional: override chips declaration
    python -m digilab.synthesizer --expr <expr.md> --out <out_dir> --chips "7400 x 2, 7420 x 1"
"""

from __future__ import annotations

import argparse
import string
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from .chips.registry import get_spec
from .common.ast_nodes import Const, Nand, Node, Primitive, Program, Var
from .common.netlist import (
    ChipInstance,
    Connection,
    Endpoint,
    Netlist,
    _endpoint_sort_key,
)
from .common.parser import _parse_chips_decl, parse_program_file


class SynthError(RuntimeError):
    pass


# ---------- 芯片实例池 ----------


class _ChipPool:
    """根据 chips 声明开出实例，按 arity / primitive 分配资源。

    资源池有两种：
      - gates：按"输入数量 arity"分组的简单与非门（NAND2 → 7400, NAND4 → 7420）
      - blocks：按"高层原语名 primitive"分组的多输入多输出器件块（DECODE3 → 74138 等）

    完全不硬编码型号；只要某 ChipSpec 的某 Gate 有 N 个输入引脚，
    就视为可用的 NAND-N 门来源；只要某 ChipSpec 的某 Block 提供 primitive=X，
    就视为可用的 X 块来源。新增器件无需修改本类。
    """

    def __init__(self, decl: List[Tuple[str, int]]):
        self.instances: List[ChipInstance] = []
        self._free_gates_by_arity: Dict[int, List[Tuple[str, int]]] = {}
        self._free_blocks_by_primitive: Dict[str, List[Tuple[str, int]]] = {}
        per_model_count: Dict[str, int] = {}
        for model, count in decl:
            for _ in range(count):
                idx = per_model_count.get(model, 0)
                if idx >= len(string.ascii_uppercase):
                    raise SynthError(f"型号 {model} 实例过多（>26）")
                name = f"{model}_{string.ascii_uppercase[idx]}"
                per_model_count[model] = idx + 1
                self.instances.append(ChipInstance(name=name, type=model))
                spec = get_spec(model)
                for g in spec.gates:
                    arity = len(g.inputs)
                    self._free_gates_by_arity.setdefault(arity, []).append((name, g.gate_id))
                for b in spec.blocks:
                    self._free_blocks_by_primitive.setdefault(b.primitive, []).append(
                        (name, b.block_id)
                    )

    def alloc_gate(self, arity: int) -> Tuple[str, int]:
        """分配一个 arity 输入的未占用门。"""
        bucket = self._free_gates_by_arity.get(arity)
        if not bucket:
            raise SynthError(
                f"没有可用的 {arity} 输入与非门；请在 chips 声明中加入提供该 arity 的器件"
            )
        return bucket.pop(0)

    def alloc_block(self, primitive: str) -> Tuple[str, int]:
        """分配一个支持 primitive 的未占用器件块。"""
        bucket = self._free_blocks_by_primitive.get(primitive)
        if not bucket:
            raise SynthError(
                f"没有可用的 {primitive} 器件块；请在 chips 声明中加入提供 {primitive} 的器件"
            )
        return bucket.pop(0)


# ---------- 综合主体 ----------

_VCC_EP = Endpoint(chip="VCC", pin=0)
_GND_EP = Endpoint(chip="GND", pin=0)


def _emit_node(
    node: Node,
    var_endpoints: Dict[str, Endpoint],
    pool: _ChipPool,
    netlist: Netlist,
    cache: Dict[Node, Endpoint],
) -> Endpoint:
    """递归生成节点电路，返回该节点输出的 Endpoint。

    仅处理"单输出"节点（Var / Const / Nand）。多输出原语（Primitive）必须
    在赋值顶层用多 LHS 接收，由 synthesize() 直接调 _emit_primitive，不允许
    嵌套到 NAND 内部——本函数遇到 Primitive 直接报错。

    cache 实现自动 CSE：结构相等（== / hash 相同）的子表达式只生成一个门，
    后续引用都复用同一输出端点（电气扇出）。
    """
    if isinstance(node, Var):
        if node.name not in var_endpoints:
            raise SynthError(f"使用了未声明的变量 {node.name!r}")
        return var_endpoints[node.name]
    if isinstance(node, Const):
        return _VCC_EP if node.value == 1 else _GND_EP
    if isinstance(node, Primitive):
        raise SynthError(
            f"多输出原语 {node.name!r} 不可作为子表达式嵌套到其它节点内；"
            f"必须在赋值顶层用多 LHS 接收（如 Y0, Y1, ... = {node.name}(...)）"
        )
    if isinstance(node, Nand):
        if node in cache:
            return cache[node]
        # 先递归生成所有子节点
        sub_eps = [_emit_node(a, var_endpoints, pool, netlist, cache) for a in node.args]
        # VCC 输入替换：把所有 _VCC_EP 位换成本门首个真实信号端点（非 VCC）。
        # 物理上避免直接接电源导致的高电平不稳定；电气上 NAND(X, ..., X) = NAND(X, ...) 恒等。
        # 全部输入均为 _VCC_EP 的极罕见情况下保留原行为（fallback：门输出恒 0）。
        non_vcc = [ep for ep in sub_eps if ep != _VCC_EP]
        if non_vcc:
            proxy = non_vcc[0]
            sub_eps = [proxy if ep == _VCC_EP else ep for ep in sub_eps]
        # 分配门
        chip_name, gate_id = pool.alloc_gate(arity=node.arity)
        spec = get_spec(_chip_type_of(chip_name, netlist))
        gate = spec.gate(gate_id)
        # 连线：子输出 → 本门各输入
        for child_ep, in_pin in zip(sub_eps, gate.inputs):
            netlist.add_connection(child_ep, Endpoint(chip=chip_name, pin=in_pin))
        out_ep = Endpoint(chip=chip_name, pin=gate.output)
        cache[node] = out_ep
        return out_ep
    raise SynthError(f"未知 AST 节点：{type(node).__name__}")


def _emit_primitive(
    node: Primitive,
    var_endpoints: Dict[str, Endpoint],
    pool: _ChipPool,
    netlist: Netlist,
    cache: Dict[Node, Endpoint],
) -> List[Endpoint]:
    """处理多输出原语（DECODE3 / MUX4 等），返回输出端点列表。

    步骤：
      1. 递归子节点拿到信号输入端点列表（通过 _emit_node，子节点不能再是
         多输出 Primitive）
      2. 分配一个支持该 primitive 的 Block
      3. 把信号输入端点连到 Block.inputs 引脚
      4. 加默认使能连线（block.default_enables）
      5. 返回 Block.outputs 引脚对应的 Endpoint 列表（按 LHS 索引顺序）

    注意：本路径不做 VCC 输入替换——译码器/MUX 的输入与使能都有明确语义，
    不可借接到信号输入。
    """
    sub_eps = [_emit_node(a, var_endpoints, pool, netlist, cache) for a in node.args]

    chip_name, block_id = pool.alloc_block(node.name)
    spec = get_spec(_chip_type_of(chip_name, netlist))
    block = spec.block(block_id)

    if len(sub_eps) != len(block.inputs):
        raise SynthError(
            f"原语 {node.name} 收到 {len(sub_eps)} 个参数，"
            f"但器件 {chip_name} block_id={block_id} 期望 {len(block.inputs)} 个输入"
        )
    for child_ep, in_pin in zip(sub_eps, block.inputs):
        netlist.add_connection(child_ep, Endpoint(chip=chip_name, pin=in_pin))

    # 默认使能：芯片引脚 → VCC.0 / GND.0
    for pin_n, rail in block.default_enables:
        if rail == "VCC":
            netlist.add_connection(Endpoint(chip=chip_name, pin=pin_n), Endpoint(chip="VCC", pin=0))
        elif rail == "GND":
            netlist.add_connection(Endpoint(chip=chip_name, pin=pin_n), Endpoint(chip="GND", pin=0))
        else:
            raise SynthError(f"Block.default_enables 仅支持 'VCC' / 'GND'，得到 {rail!r}")

    return [Endpoint(chip=chip_name, pin=out_pin) for out_pin in block.outputs]


def _chip_type_of(name: str, netlist: Netlist) -> str:
    for c in netlist.chips:
        if c.name == name:
            return c.type
    raise SynthError(f"未知芯片实例：{name}")


def synthesize(prog: Program) -> Netlist:
    netlist = Netlist(inputs=list(prog.inputs), outputs=list(prog.outputs))

    pool = _ChipPool(prog.chips_decl)
    netlist.chips = list(pool.instances)

    # 输入变量先建虚拟端点：INPUT.<name>
    var_endpoints: Dict[str, Endpoint] = {
        name: Endpoint(chip="INPUT", pin=name) for name in prog.inputs
    }

    # 自动 CSE 缓存：AST node → 已分配门的输出 endpoint
    cache: Dict[Node, Endpoint] = {}

    output_set = set(prog.outputs)

    # 按声明顺序逐个赋值生成
    # - outputs 中的赋值：除生成对应门 / 块外，还需把输出端点连到 OUTPUT.<name>
    # - 中间变量赋值：仅把 LHS 名字注册到 var_endpoints，使后续表达式可引用
    # - 多 LHS（多输出 Primitive）：把每个 LHS 名字绑到对应的 block 输出端点
    for asgn in prog.assignments:
        for n in asgn.all_names:
            if n in var_endpoints:
                raise SynthError(f"变量 {n!r} 重复定义（与输入或前面的变量冲突）")

        if isinstance(asgn.expr, Primitive):
            out_eps = _emit_primitive(asgn.expr, var_endpoints, pool, netlist, cache)
            names = asgn.all_names
            if len(out_eps) != len(names):
                raise SynthError(
                    f"原语 {asgn.expr.name} 输出 {len(out_eps)} 路，但 LHS 给出 {len(names)} 个名字"
                )
            for nm, ep in zip(names, out_eps):
                var_endpoints[nm] = ep
                if nm in output_set:
                    netlist.add_connection(ep, Endpoint(chip="OUTPUT", pin=nm))
        else:
            if asgn.extra_names:
                # 解析阶段已拒绝；此处冗余防御
                raise SynthError(f"赋值 {asgn.name!r} 的右侧不是多输出原语，但给出了多 LHS 名字")
            out_ep = _emit_node(asgn.expr, var_endpoints, pool, netlist, cache)
            var_endpoints[asgn.name] = out_ep
            if asgn.name in output_set:
                netlist.add_connection(out_ep, Endpoint(chip="OUTPUT", pin=asgn.name))

    # 给所有实例补芯片自身定义的 VCC / GND / NC 引脚（附录 B.3）
    for inst in netlist.chips:
        spec = get_spec(inst.type)
        for pn in spec.vcc_pins:
            netlist.add_connection(Endpoint(chip=inst.name, pin=pn), Endpoint(chip="VCC", pin=0))
        for pn in spec.gnd_pins:
            netlist.add_connection(Endpoint(chip=inst.name, pin=pn), Endpoint(chip="GND", pin=0))
        for pn in spec.nc_pins:
            netlist.add_connection(Endpoint(chip=inst.name, pin=pn), Endpoint(chip="NC", pin=0))

    _daisy_chain_connections(netlist)
    netlist.sort()
    return netlist


_POWER_ENDPOINTS = {"VCC", "GND", "NC"}


def _daisy_chain_connections(netlist: Netlist) -> None:
    """把"一驱多"信号的扇出从星型重组为菊花链。

    电气上完全等价（所有端点仍属于同一并查集等价类），物理上对应面包板上
    "从输入开关拉一根线到第一个芯片，再从那里跳到下一个芯片"的接线方式。

    规则：
      - dst 是 VCC / GND / NC 的连接保留原状（电源/地用总线供应，不需链化）
      - 其余按 src 分组；每组按 endpoint 排序键排序消费者后链式重连：
            src -> d0,  d0 -> d1,  d1 -> d2, ...
        d0 即用户所说的"总输入"，是字典序最小的消费者。
    """
    by_src: Dict[Endpoint, List[Endpoint]] = {}
    keep: List[Connection] = []
    for c in netlist.connections:
        if c.dst.chip in _POWER_ENDPOINTS:
            keep.append(c)
        else:
            by_src.setdefault(c.src, []).append(c.dst)

    new_conns: List[Connection] = list(keep)
    for src, dsts in by_src.items():
        ordered = sorted(dsts, key=_endpoint_sort_key)
        prev = src
        for d in ordered:
            new_conns.append(Connection(src=prev, dst=d))
            prev = d

    netlist.connections = new_conns


# ---------- CLI ----------


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="电路综合器：表达式文件 → circuit.txt + netlist.json",
    )
    ap.add_argument("--expr", required=True, type=Path, help="逻辑表达式 md 文件")
    ap.add_argument("--out", required=True, type=Path, help="输出目录（实验x）")
    ap.add_argument(
        "--chips",
        default="",
        help='可选：覆盖表达式文件中的 chips 声明，如 "7400 x 2, 7420 x 1"',
    )
    args = ap.parse_args(argv)

    try:
        prog = parse_program_file(args.expr)
        if args.chips.strip():
            prog.chips_decl = _parse_chips_decl(args.chips)
        netlist = synthesize(prog)
    except Exception as exc:  # noqa: BLE001
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    nj, ct = netlist.save(args.out)
    print(f"写入 {nj}")
    print(f"写入 {ct}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
