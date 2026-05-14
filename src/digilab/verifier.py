"""Circuit verifier: netlist + expected truth table → verify report.

Inputs:  netlist.json + truth_table.csv
Process:
  1. Parse netlist; treat each connection as an electrical equivalence class.
  2. Abstract signals (chip, pin) into a gate-level graph.
  3. For each input combination, evaluate gates in topological order.
  4. Compare against expected truth table row by row.
Outputs: actual_truth_table.csv + verify_report.json (diff rows + error locations)

Runs independently from the synthesizer; only depends on netlist.json.

CLI (via ``digilab`` entry-point, preferred)::

    digilab verify --netlist <netlist.json> --truth <truth_table.csv> --out <dir>

Or directly::

    python -m digilab.verifier --netlist <netlist.json> --truth <truth_table.csv> --out <dir>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

from .chips.registry import get_spec
from .common.netlist import Endpoint, Netlist
from .common.tt_io import read_csv, split_io, write_csv


class VerifyError(RuntimeError):
    pass


# ---------- 信号合并：union-find ----------


class _UnionFind:
    def __init__(self) -> None:
        self.parent: Dict[Endpoint, Endpoint] = {}

    def find(self, x: Endpoint) -> Endpoint:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: Endpoint, b: Endpoint) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


# ---------- 网表 → 门级图 ----------


class _Circuit:
    """已编译的电路：信号节点 + 求值单元（unit）列表。

    unit 是 gate 与 block 的统一抽象：
      - kind="gate"：单输出，func 包装为 List[int] -> List[int]（返回 [single]）
      - kind="block"：多输出，func 直接返回 List[int]，按 outs_list 分发
    Topo / 求值循环只看 unit，不区分类型。
    """

    def __init__(
        self,
        netlist: Netlist,
    ) -> None:
        self.netlist = netlist

        # 1. 把所有连接做并查集合并，构造电气网络
        self.uf = _UnionFind()
        for conn in netlist.connections:
            self.uf.union(conn.src, conn.dst)

        # 2. 收集每个信号的所有端点（用于诊断）
        self.signal_endpoints: Dict[Endpoint, Set[Endpoint]] = defaultdict(set)
        for ep in self._all_endpoints():
            self.signal_endpoints[self.uf.find(ep)].add(ep)

        # 3. 对每个芯片实例的每个 gate / block，建一条 unit 记录
        # unit_record: (chip_name, kind, gate_or_block_id, input_signals[],
        #               output_signals[], func: List[int] -> List[int])
        self.units: List[
            Tuple[
                str,
                str,
                int,
                List[Endpoint],
                List[Endpoint],
                Callable[[List[int]], List[int]],
            ]
        ] = []
        for inst in netlist.chips:
            spec = get_spec(inst.type)
            for g in spec.gates:
                in_sigs = [self.uf.find(Endpoint(chip=inst.name, pin=pn)) for pn in g.inputs]
                out_sigs = [self.uf.find(Endpoint(chip=inst.name, pin=g.output))]
                self.units.append(
                    (
                        inst.name,
                        "gate",
                        g.gate_id,
                        in_sigs,
                        out_sigs,
                        _wrap_gate_func(g.func),
                    )
                )
            for b in spec.blocks:
                in_sigs = [self.uf.find(Endpoint(chip=inst.name, pin=pn)) for pn in b.inputs]
                out_sigs = [self.uf.find(Endpoint(chip=inst.name, pin=pn)) for pn in b.outputs]
                self.units.append((inst.name, "block", b.block_id, in_sigs, out_sigs, b.func))

        # 4. INPUT / OUTPUT / VCC / GND 的代表节点
        self.input_signals: Dict[str, Endpoint] = {
            n: self.uf.find(Endpoint(chip="INPUT", pin=n)) for n in netlist.inputs
        }
        self.output_signals: Dict[str, Endpoint] = {}
        for n in netlist.outputs:
            ep = Endpoint(chip="OUTPUT", pin=n)
            if ep not in self.uf.parent:
                raise VerifyError(f"输出 {n} 没有任何驱动连线")
            self.output_signals[n] = self.uf.find(ep)

        self.vcc_signal: Optional[Endpoint] = None
        self.gnd_signal: Optional[Endpoint] = None
        vcc_ep = Endpoint(chip="VCC", pin=0)
        gnd_ep = Endpoint(chip="GND", pin=0)
        if vcc_ep in self.uf.parent:
            self.vcc_signal = self.uf.find(vcc_ep)
        if gnd_ep in self.uf.parent:
            self.gnd_signal = self.uf.find(gnd_ep)

        # 5. 拓扑：每个输出信号映射回驱动它的 unit 下标；冲突即短路
        self.driver_unit_idx: Dict[Endpoint, int] = {}
        for idx, (cn, kind, _gbid, _ins, outs_list, _func) in enumerate(self.units):
            for outs in outs_list:
                if outs in self.driver_unit_idx:
                    raise VerifyError(
                        f"信号 {outs} 同时被两个 unit 驱动："
                        f"{self.driver_unit_idx[outs]} 与 {idx}（短路）"
                    )
                self.driver_unit_idx[outs] = idx

        # 6. 拓扑排序 unit
        self.topo_order: List[int] = self._topo_sort()

    def _all_endpoints(self) -> Iterator[Endpoint]:
        for c in self.netlist.connections:
            yield c.src
            yield c.dst

    def _topo_sort(self) -> List[int]:
        in_deg = [0] * len(self.units)
        children: Dict[int, List[int]] = defaultdict(list)
        for j, (_, _, _, ins_j, _, _) in enumerate(self.units):
            for sig in ins_j:
                drv = self.driver_unit_idx.get(sig)
                if drv is not None:
                    children[drv].append(j)
                    in_deg[j] += 1
        q = deque(i for i, d in enumerate(in_deg) if d == 0)
        order: List[int] = []
        while q:
            i = q.popleft()
            order.append(i)
            for j in children[i]:
                in_deg[j] -= 1
                if in_deg[j] == 0:
                    q.append(j)
        if len(order) != len(self.units):
            raise VerifyError("电路存在反馈环路（拓扑排序失败）")
        return order

    # ---------- 求值 ----------

    def evaluate(self, input_bits: Dict[str, int]) -> Dict[str, int]:
        sig_value: Dict[Endpoint, int] = {}

        for name, val in input_bits.items():
            if name not in self.input_signals:
                raise VerifyError(f"输入变量 {name!r} 不在网表中")
            sig_value[self.input_signals[name]] = val
        if self.vcc_signal is not None:
            sig_value[self.vcc_signal] = 1
        if self.gnd_signal is not None:
            sig_value[self.gnd_signal] = 0

        for idx in self.topo_order:
            cn, kind, _gbid, ins, outs_list, func = self.units[idx]
            if any(s not in sig_value for s in ins):
                # 闲置 unit：输入未被驱动，跳过
                continue
            bits = [sig_value[s] for s in ins]
            out_bits = func(bits)
            if len(out_bits) != len(outs_list):
                raise VerifyError(
                    f"unit {cn}.{kind}#{_gbid} 期望 {len(outs_list)} 路输出，"
                    f"实际返回 {len(out_bits)}"
                )
            for sig, v in zip(outs_list, out_bits):
                sig_value[sig] = v

        result: Dict[str, int] = {}
        for n, sig in self.output_signals.items():
            if sig not in sig_value:
                raise VerifyError(f"输出 {n} 未被求值（信号 {sig} 无驱动）")
            result[n] = sig_value[sig]
        return result


def _wrap_gate_func(
    func: Callable[[List[int]], int],
) -> Callable[[List[int]], List[int]]:
    """把单输出 Gate.func 适配成与 Block.func 同型的 List[int] -> List[int]。"""

    def wrapped(bits: List[int]) -> List[int]:
        return [func(bits)]

    return wrapped


# ---------- 比对 ----------


def verify(
    netlist: Netlist, header: List[str], rows: List[List[str]]
) -> Tuple[List[List[str]], Dict[str, Any]]:
    in_idx, out_idx = split_io(header, netlist.inputs, netlist.outputs)
    circuit = _Circuit(netlist)

    actual_rows: List[List[str]] = []
    diffs: List[Dict[str, Any]] = []
    pass_count = 0

    for r_i, row in enumerate(rows):
        in_bits = {netlist.inputs[k]: int(row[in_idx[k]]) for k in range(len(netlist.inputs))}

        # X 输入：枚举所有可能并取一致结果（不一致则记 X）
        # 这里输入只接受 0/1，X 仅出现在期望输出（任意态）
        actual = circuit.evaluate(in_bits)

        actual_row = list(row)
        ok = True
        for k, name in enumerate(netlist.outputs):
            exp_str = row[out_idx[k]]
            act_val = actual[name]
            actual_row[out_idx[k]] = str(act_val)
            if exp_str == "X":
                continue  # 任意态，不参与比对
            if str(act_val) != exp_str:
                ok = False
                diffs.append(
                    {
                        "row": r_i + 2,  # CSV 含表头，行号从 2 开始
                        "inputs": in_bits,
                        "output": name,
                        "expected": exp_str,
                        "actual": act_val,
                    }
                )
        if ok:
            pass_count += 1
        actual_rows.append(actual_row)

    report: Dict[str, Any] = {
        "total_rows": len(rows),
        "passed": pass_count,
        "failed": len(rows) - pass_count,
        "diff": diffs,
    }
    return actual_rows, report


# ---------- CLI ----------


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="电路验证器：netlist + 期望真值表 → 实际真值表 + 验证报告",
    )
    ap.add_argument("--netlist", required=True, type=Path, help="netlist.json")
    ap.add_argument("--truth", required=True, type=Path, help="truth_table.csv")
    ap.add_argument("--out", required=True, type=Path, help="输出目录")
    args = ap.parse_args(argv)

    try:
        netlist = Netlist.load(args.netlist)
        header, rows = read_csv(args.truth)
        actual_rows, report = verify(netlist, header, rows)
    except Exception as exc:  # noqa: BLE001
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    actual_path = args.out / "actual_truth_table.csv"
    report_path = args.out / "verify_report.json"

    write_csv(actual_path, header, actual_rows)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"写入 {actual_path}")
    print(f"写入 {report_path}")
    print(f"通过 {report['passed']}/{report['total_rows']} 行，失败 {report['failed']} 行")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
