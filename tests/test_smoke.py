"""端到端 smoke 测试：F = NAND2(A, B)。

只验证 pipeline 能跑通，不落地到 实验x/。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digilab import synthesizer, verifier
from digilab.common.netlist import Endpoint, Netlist
from digilab.common.parser import parse_program_text
from digilab.common.tt_io import md_file_to_csv

# Fixture files live in course_archive/. Phase C will move a curated subset
# into examples/; until then the smoke suite reuses them as-is.
ROOT = Path(__file__).resolve().parent.parent / "course_archive"


# ---------------- 1. parser 单元测试 ----------------


def test_parser_basic():
    text = """
chips:   7400 x 1
inputs:  A, B
outputs: F

F = NAND2(A, B)
"""
    prog = parse_program_text(text)
    assert prog.chips_decl == [("7400", 1)]
    assert prog.inputs == ["A", "B"]
    assert prog.outputs == ["F"]
    assert len(prog.assignments) == 1
    assert prog.assignments[0].name == "F"


def test_parser_in_md_fence():
    text = """
# 标题会被跳过

```
chips:   7400 x 2, 7420 x 1
inputs:  A, B, C, D
outputs: F

F = NAND4(A, B, C, NAND2(A, D))
```
"""
    prog = parse_program_text(text)
    assert prog.chips_decl == [("7400", 2), ("7420", 1)]
    assert prog.outputs == ["F"]


def test_parser_arity_mismatch():
    text = """
chips: 7400 x 1
inputs: A, B
outputs: F
F = NAND2(A, B, A)
"""
    with pytest.raises(Exception):
        parse_program_text(text)


# ---------------- 2. synthesizer 单元测试 ----------------


def test_synthesize_nand2(tmp_path):
    text = """
chips: 7400 x 1
inputs: A, B
outputs: F
F = NAND2(A, B)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)

    nj, ct = netlist.save(tmp_path)
    assert nj.exists() and ct.exists()

    data = json.loads(nj.read_text(encoding="utf-8"))
    assert data["inputs"] == ["A", "B"]
    assert data["outputs"] == ["F"]
    assert data["chips"] == [{"name": "7400_A", "type": "7400"}]

    pairs = {
        (c["from"]["chip"], c["from"]["pin"], c["to"]["chip"], c["to"]["pin"])
        for c in data["connections"]
    }
    # 必须包含的电源 / 地与门连线
    assert ("INPUT", "A", "7400_A", 1) in pairs
    assert ("INPUT", "B", "7400_A", 2) in pairs
    assert ("7400_A", 3, "OUTPUT", "F") in pairs
    assert ("7400_A", 7, "GND", 0) in pairs
    assert ("7400_A", 14, "VCC", 0) in pairs


def test_synthesize_nested(tmp_path):
    text = """
chips: 7400 x 2, 7420 x 1
inputs: A, B, C, D
outputs: F
F = NAND4(NAND2(A, B), NAND2(C, D), A, D)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)
    netlist.save(tmp_path)
    # 至少占用了 1 个 7420 + 2 个 7400 门
    assert any(c.type == "7420" for c in netlist.chips)
    assert any(c.type == "7400" for c in netlist.chips)


# ---------------- 3. circuit.txt 排序 ----------------


def test_circuit_text_sorted(tmp_path):
    text = """
chips: 7400 x 1
inputs: A, B
outputs: F
F = NAND2(A, B)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)
    netlist.save(tmp_path)

    lines = (tmp_path / "circuit.txt").read_text(encoding="utf-8").strip().splitlines()
    # 特殊端点（INPUT）排在最前
    assert lines[0].startswith("INPUT.A")
    assert lines[1].startswith("INPUT.B")
    # 后面是 7400_A 的引脚号升序
    rest = lines[2:]
    chip_lines = [ln for ln in rest if ln.startswith("7400_A")]
    pins = [int(ln.split(".")[1].split(" ")[0]) for ln in chip_lines]
    assert pins == sorted(pins)


# ---------------- 4. 端到端：synth → verify ----------------


def test_e2e_nand_pipeline(tmp_path):
    expr_md = ROOT / "真值表与逻辑表达式" / "示例_表达式.md"
    truth_md = ROOT / "真值表与逻辑表达式" / "示例_真值表.md"

    out_dir = tmp_path / "smoke"
    # 1) synth
    rc = synthesizer.main(
        [
            "--expr",
            str(expr_md),
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    netlist = Netlist.load(out_dir / "netlist.json")
    assert "F" in netlist.outputs

    # 2) md → csv
    truth_csv = out_dir / "truth_table.csv"
    md_file_to_csv(truth_md, truth_csv)

    # 3) verify
    rc = verifier.main(
        [
            "--netlist",
            str(out_dir / "netlist.json"),
            "--truth",
            str(truth_csv),
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0

    rep = json.loads((out_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert rep["failed"] == 0
    assert rep["passed"] == 4


# ---------------- 5. verifier 检测错误网表 ----------------


def test_verifier_detects_wrong_wiring(tmp_path):
    """手工把 INPUT.B 接到 GND，制造错误，verifier 应该能检测出来。"""
    text = """
chips: 7400 x 1
inputs: A, B
outputs: F
F = NAND2(A, B)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)

    # 篡改：把 INPUT.B → 7400_A.2 这条改为 GND → 7400_A.2
    new_conns = []
    for c in netlist.connections:
        if c.src == Endpoint("INPUT", "B"):
            new_conns.append(type(c)(src=Endpoint("GND", 0), dst=c.dst))
        else:
            new_conns.append(c)
    netlist.connections = new_conns

    out_dir = tmp_path / "bad"
    out_dir.mkdir()
    (out_dir / "netlist.json").write_text(netlist.to_json(), encoding="utf-8")

    truth_md = ROOT / "真值表与逻辑表达式" / "示例_真值表.md"
    truth_csv = out_dir / "truth_table.csv"
    md_file_to_csv(truth_md, truth_csv)

    rc = verifier.main(
        [
            "--netlist",
            str(out_dir / "netlist.json"),
            "--truth",
            str(truth_csv),
            "--out",
            str(out_dir),
        ]
    )
    assert rc != 0
    rep = json.loads((out_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert rep["failed"] > 0


# ---------------- 6. tt_io 单元测试 ----------------


def test_tt_io_md_to_csv(tmp_path):
    md = """
| A | B | F |
|---|---|---|
| 0 | 0 | 1 |
| 1 | 1 | 0 |
"""
    md_path = tmp_path / "t.md"
    csv_path = tmp_path / "t.csv"
    md_path.write_text(md, encoding="utf-8")
    header, rows = md_file_to_csv(md_path, csv_path)
    assert header == ["A", "B", "F"]
    assert rows == [["0", "0", "1"], ["1", "1", "0"]]
    text = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert text[0] == "A,B,F"


# ---------------- 7. 字面量 0/1 ----------------


def test_literal_one_to_vcc(tmp_path):
    """NAND4 的第 4 输入写 1 时：旧行为是接 VCC，新行为（VCC 输入替换）是
    把 pin 5 短接到该门首个真实信号端点（A），物理上避免直接接电源带来的
    高电平不稳定。期望：
      - 没有任何 src=VCC.0 的连线（VCC 仅作为 dst 出现，对应芯片自带 14 引脚）
      - 从 INPUT.A 出发沿连线能到达 7420_A.5（即 A 的菊花链覆盖了原 VCC 的位置）
    """
    text = """
chips: 7420 x 1
inputs: A, B, C
outputs: F

F = NAND4(A, B, C, 1)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)

    vcc_as_src = [c for c in netlist.connections if c.src.chip == "VCC"]
    assert vcc_as_src == [], (
        f"启用 VCC 输入替换后，VCC 不应再作为任何连线的 src，实际仍有：{vcc_as_src}"
    )

    from collections import defaultdict, deque

    adj = defaultdict(list)
    for c in netlist.connections:
        if c.dst.chip in ("VCC", "GND", "NC"):
            continue
        adj[(c.src.chip, c.src.pin)].append((c.dst.chip, c.dst.pin))
    reachable = set()
    q = deque([("INPUT", "A")])
    while q:
        node = q.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        for nxt in adj.get(node, []):
            q.append(nxt)
    assert ("7420_A", 5) in reachable, (
        f"INPUT.A 应通过菊花链能到达 7420_A.5（替代 VCC 拉高），实际可达端点：{reachable}"
    )


def test_literal_zero_to_gnd(tmp_path):
    text = """
chips: 7400 x 1
inputs: A
outputs: F

F = NAND2(A, 0)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)
    pairs = {(c.src.chip, c.src.pin, c.dst.chip, c.dst.pin) for c in netlist.connections}
    assert ("GND", 0, "7400_A", 2) in pairs


def test_vcc_kept_when_all_inputs_are_one(tmp_path):
    """极端 case：NAND4(1,1,1,1) 所有输入都是 Const(1)，没有"真实信号端点"
    可作 proxy，应落到 fallback 路径，VCC.0 仍作为 src 出现接到 7420 输入引脚。
    （此时门输出恒为 0，几乎不会真实出现，但代码必须优雅处理。）"""
    text = """
chips: 7420 x 1
inputs: A
outputs: F

F = NAND4(1, 1, 1, 1)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)

    vcc_to_nand4_input = [
        c
        for c in netlist.connections
        if c.src == Endpoint("VCC", 0) and c.dst.chip == "7420_A" and c.dst.pin in (1, 2, 4, 5)
    ]
    assert len(vcc_to_nand4_input) >= 1, (
        f"全 1 输入时应 fallback 保留 VCC.0 → 7420_A 输入连接，实际：{vcc_to_nand4_input}"
    )


# ---------------- 8. 自动 CSE ----------------


def test_auto_cse_reuses_gate(tmp_path):
    """NAND2(NAND2(B,B), NAND2(B,B)) 应该只生成 2 个 NAND2 门。"""
    text = """
chips: 7400 x 1
inputs: B
outputs: F

F = NAND2(NAND2(B, B), NAND2(B, B))
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)

    # CSE 判据：统计实际占用的 NAND2 门数（= 出现的输出引脚 3/6/8/11 的种类）。
    # 菊花链化后 src 各只出现 1 次，所以"扇出数"判据失效；门复用仍体现在
    # "占用的门输出引脚种类数"上。
    endpoints = set()
    for c in netlist.connections:
        endpoints.add((c.src.chip, c.src.pin))
        endpoints.add((c.dst.chip, c.dst.pin))
    nand2_outputs = {ep for ep in endpoints if ep[0] == "7400_A" and ep[1] in (3, 6, 8, 11)}
    # 顶层 NAND2 + 共享子 NAND2 = 2 个门 = 2 种输出引脚
    assert len(nand2_outputs) == 2, (
        f"CSE 失效：期望占用 2 个 NAND2 门，实际 {len(nand2_outputs)} 个：{nand2_outputs}"
    )


def test_auto_cse_e2e_b3_shared(tmp_path):
    """模拟实验 1_2 的核心场景：~B3 被 2 个 NAND4 共享，4 NAND2 + 2 NAND4 应能装下。"""
    text = """
chips: 7400 x 1, 7420 x 1
inputs: B3, B2, B1, B0
outputs: Y

Y = NAND2(
      NAND4(NAND2(B3, B3), B2, NAND2(B1, B0), 1),
      NAND4(NAND2(B3, B3), NAND2(B2, B2), B1, B0)
    )
"""
    prog = parse_program_text(text)
    # 不抛 SynthError 即可（说明门预算够用）
    netlist = synthesizer.synthesize(prog)
    assert "Y" in netlist.outputs


# ---------------- 8.5 菊花链扇出 ----------------


def test_daisy_chain_fanout(tmp_path):
    """A 经 CSE 后扇出 3 处（NAND2(A,A) 的两个输入 + NAND2(A,B) 的一个输入），
    应被重组为菊花链：INPUT.A -> 第一消费者 -> 第二消费者 -> 第三消费者，
    源自 INPUT.A 的连线只剩 1 条。"""
    text = """
chips: 7400 x 1
inputs: A, B
outputs: F

F = NAND2(NAND2(A, A), NAND2(A, B))
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)

    a_consumers = [c for c in netlist.connections if c.src.chip == "INPUT" and c.src.pin == "A"]

    # 1) INPUT.A 作 src 的连线只剩 1 条（其余都被链化挪到中间链上了）
    assert len(a_consumers) == 1, (
        f"INPUT.A 应只作为 1 条连线的 src（菊花链入口），实际有 {len(a_consumers)} 条："
        f"{[(c.src, c.dst) for c in a_consumers]}"
    )

    # 2) 链路连通性：从 INPUT.A 出发，能沿连线走到所有 3 个 A 消费者
    #    构造邻接表（src -> [dst...]）后做 BFS
    from collections import defaultdict, deque

    adj = defaultdict(list)
    for c in netlist.connections:
        if c.dst.chip in ("VCC", "GND", "NC"):
            continue
        adj[(c.src.chip, c.src.pin)].append((c.dst.chip, c.dst.pin))

    reachable = set()
    q = deque([("INPUT", "A")])
    while q:
        node = q.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        for nxt in adj.get(node, []):
            q.append(nxt)

    # 应能到达 3 个 NAND2 输入引脚（属于 7400_A.{1,2,4,5,9,10,12,13}）
    nand2_input_pins = {1, 2, 4, 5, 9, 10, 12, 13}
    a_consumer_pins = {n for n in reachable if n[0] == "7400_A" and n[1] in nand2_input_pins}
    assert len(a_consumer_pins) == 3, (
        f"菊花链应连通 3 个 A 的消费者引脚，实际连通 {len(a_consumer_pins)} 个：{a_consumer_pins}"
    )


# ---------------- 9. 中间变量语法 ----------------


def test_intermediate_var(tmp_path):
    """T1 = NAND2(A, A) 然后 Y = NAND2(T1, B)：T1 不是 outputs，但能被引用。"""
    text = """
chips: 7400 x 1
inputs: A, B
outputs: Y

T1 = NAND2(A, A)
Y = NAND2(T1, B)
"""
    prog = parse_program_text(text)
    assert prog.outputs == ["Y"]
    assert [a.name for a in prog.assignments] == ["T1", "Y"]

    netlist = synthesizer.synthesize(prog)
    # 应该只有 Y 出现在 OUTPUT 端，不应该有 T1
    out_pins = {c.dst.pin for c in netlist.connections if c.dst.chip == "OUTPUT"}
    assert out_pins == {"Y"}


def test_intermediate_var_undefined_use():
    """引用未定义的中间变量应报错。"""
    text = """
chips: 7400 x 1
inputs: A
outputs: Y

Y = NAND2(T1, A)
"""
    with pytest.raises(Exception, match="未定义"):
        parse_program_text(text)


def test_intermediate_var_use_before_def():
    """先用后定也不允许。"""
    text = """
chips: 7400 x 1
inputs: A, B
outputs: Y

Y = NAND2(T1, B)
T1 = NAND2(A, A)
"""
    with pytest.raises(Exception, match="未定义"):
        parse_program_text(text)


# ---------------- 10. 中间变量 + CSE 端到端验证 ----------------


def test_intermediate_var_e2e_verify(tmp_path):
    """中间变量定义的电路在 verifier 下应正确求值。"""
    text = """
chips: 7400 x 1
inputs: A, B
outputs: F

T1 = NAND2(A, A)
F = NAND2(T1, B)
"""
    prog = parse_program_text(text)
    out_dir = tmp_path / "iv"
    netlist = synthesizer.synthesize(prog)
    netlist.save(out_dir)

    # 期望真值表：F = ~(~A · B) = A + ~B
    truth_md = """
| A | B | F |
|---|---|---|
| 0 | 0 | 1 |
| 0 | 1 | 0 |
| 1 | 0 | 1 |
| 1 | 1 | 1 |
"""
    truth_md_path = out_dir / "tt.md"
    truth_md_path.write_text(truth_md, encoding="utf-8")
    truth_csv = out_dir / "truth_table.csv"
    md_file_to_csv(truth_md_path, truth_csv)

    rc = verifier.main(
        [
            "--netlist",
            str(out_dir / "netlist.json"),
            "--truth",
            str(truth_csv),
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    rep = json.loads((out_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert rep["failed"] == 0
    assert rep["passed"] == 4


# ---------------- 11. 74138（DECODE3）------------------

from digilab.chips import chip_74138, chip_74151, chip_74153  # noqa: E402
from digilab.chips.registry import get_spec  # noqa: E402
from digilab.common.ast_nodes import Primitive  # noqa: E402


def test_chip_74138_self_check():
    """16 行真值表（8 地址 × 使能 on/off）。

    使能 ON：被选中的 Yn̅ = 0，其余 = 1
    使能 OFF（取 G1=0 一种代表）：全 1
    """
    for addr in range(8):
        a = addr & 1
        b = (addr >> 1) & 1
        c = (addr >> 2) & 1
        out = chip_74138.decode3([a, b, c, 1, 0, 0])
        expected = [1] * 8
        expected[addr] = 0
        assert out == expected, f"使能 ON addr={addr:03b} 期望 {expected} 实际 {out}"

    for addr in range(8):
        a = addr & 1
        b = (addr >> 1) & 1
        c = (addr >> 2) & 1
        out = chip_74138.decode3([a, b, c, 0, 0, 0])
        assert out == [1] * 8, f"使能 OFF addr={addr:03b} 期望全 1 实际 {out}"


def test_parse_decode3_multi_lhs():
    """解析多 LHS DECODE3 赋值，断言 AST 结构与名字列表。"""
    text = """
chips:   74138 x 1
inputs:  C, B, A
outputs: Y0, Y1, Y2, Y3, Y4, Y5, Y6, Y7

Y0, Y1, Y2, Y3, Y4, Y5, Y6, Y7 = DECODE3(C, B, A)
"""
    prog = parse_program_text(text)
    assert prog.chips_decl == [("74138", 1)]
    assert len(prog.assignments) == 1
    asgn = prog.assignments[0]
    assert asgn.name == "Y0"
    assert asgn.extra_names == ["Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7"]
    assert asgn.all_names == ["Y0", "Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7"]
    assert isinstance(asgn.expr, Primitive)
    assert asgn.expr.name == "DECODE3"
    assert asgn.expr.arity == 3


def test_parse_multi_lhs_arity_check():
    """多 LHS 名字数 ≠ 8 时 ParseError。"""
    text = """
chips:   74138 x 1
inputs:  C, B, A
outputs: Y0, Y1, Y2

Y0, Y1, Y2 = DECODE3(C, B, A)
"""
    with pytest.raises(Exception, match="DECODE3"):
        parse_program_text(text)


def test_parse_multi_lhs_must_be_primitive():
    """多 LHS 右侧必须是多输出原语，NAND2 不允许。"""
    text = """
chips:   7400 x 1
inputs:  A, B
outputs: Y0, Y1

Y0, Y1 = NAND2(A, B)
"""
    with pytest.raises(Exception, match="多输出原语"):
        parse_program_text(text)


def test_synthesize_decode3(tmp_path):
    """综合 DECODE3 → netlist 含 1 个 74138_A 实例 + Y0..Y7 OUTPUT 连线 + 默认使能 3 条。"""
    text = """
chips:   74138 x 1
inputs:  C, B, A
outputs: Y0, Y1, Y2, Y3, Y4, Y5, Y6, Y7

Y0, Y1, Y2, Y3, Y4, Y5, Y6, Y7 = DECODE3(C, B, A)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)

    assert any(c.type == "74138" and c.name == "74138_A" for c in netlist.chips)

    # 8 个 OUTPUT 连线
    out_pins = {c.dst.pin for c in netlist.connections if c.dst.chip == "OUTPUT"}
    assert out_pins == {"Y0", "Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7"}

    pairs = {(c.src.chip, c.src.pin, c.dst.chip, c.dst.pin) for c in netlist.connections}
    # 默认使能：G1(6) -> VCC, G2A̅(4) -> GND, G2B̅(5) -> GND
    assert ("74138_A", 6, "VCC", 0) in pairs
    assert ("74138_A", 4, "GND", 0) in pairs
    assert ("74138_A", 5, "GND", 0) in pairs

    # 8 路输出引脚 → OUTPUT.<name>（菊花链化后 src 仍是芯片输出引脚）
    spec = get_spec("74138")
    block = spec.block(0)
    for out_pin, name in zip(block.outputs, ["Y0", "Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7"]):
        # 出于菊花链的可能，src 不一定是 chip_pin → OUTPUT，但路径上必有连接，
        # 此处只校验 OUTPUT.<name> 能在某条连线的 dst 出现
        assert any(c.dst == Endpoint(chip="OUTPUT", pin=name) for c in netlist.connections), (
            f"输出 {name} 缺少连线"
        )


def test_decode3_e2e_verify(tmp_path):
    """端到端：DECODE3 综合后 verifier 跑 8 行真值表全 PASS。"""
    text = """
chips:   74138 x 1
inputs:  C, B, A
outputs: Y0, Y1, Y2, Y3, Y4, Y5, Y6, Y7

Y0, Y1, Y2, Y3, Y4, Y5, Y6, Y7 = DECODE3(C, B, A)
"""
    prog = parse_program_text(text)
    out_dir = tmp_path / "dec"
    netlist = synthesizer.synthesize(prog)
    netlist.save(out_dir)

    # 期望真值表（8 行，使能默认 ON）
    truth_md = """
| C | B | A | Y0 | Y1 | Y2 | Y3 | Y4 | Y5 | Y6 | Y7 |
|---|---|---|----|----|----|----|----|----|----|----|
| 0 | 0 | 0 | 0  | 1  | 1  | 1  | 1  | 1  | 1  | 1  |
| 0 | 0 | 1 | 1  | 0  | 1  | 1  | 1  | 1  | 1  | 1  |
| 0 | 1 | 0 | 1  | 1  | 0  | 1  | 1  | 1  | 1  | 1  |
| 0 | 1 | 1 | 1  | 1  | 1  | 0  | 1  | 1  | 1  | 1  |
| 1 | 0 | 0 | 1  | 1  | 1  | 1  | 0  | 1  | 1  | 1  |
| 1 | 0 | 1 | 1  | 1  | 1  | 1  | 1  | 0  | 1  | 1  |
| 1 | 1 | 0 | 1  | 1  | 1  | 1  | 1  | 1  | 0  | 1  |
| 1 | 1 | 1 | 1  | 1  | 1  | 1  | 1  | 1  | 1  | 0  |
"""
    truth_md_path = out_dir / "tt.md"
    truth_md_path.write_text(truth_md, encoding="utf-8")
    truth_csv = out_dir / "truth_table.csv"
    md_file_to_csv(truth_md_path, truth_csv)

    rc = verifier.main(
        [
            "--netlist",
            str(out_dir / "netlist.json"),
            "--truth",
            str(truth_csv),
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    rep = json.loads((out_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert rep["failed"] == 0
    assert rep["passed"] == 8


def test_primitive_not_nestable():
    """多输出 Primitive 不能嵌套到 NAND 内部，综合阶段必须报错。

    注：解析阶段 DECODE3 作为子表达式被 parse_expr 接受为 Primitive 节点；
    单 LHS + 内含多输出 Primitive 这种情况要么在解析阶段拦下，要么在综合
    阶段报错。当前实现：单 LHS + RHS 顶层是多输出 Primitive 由解析器拦下；
    嵌套到 NAND 内部由综合器 _emit_node 拦下。
    """
    # case 1: 嵌套到 NAND 中（综合阶段报错）
    text = """
chips:   7400 x 1, 74138 x 1
inputs:  C, B, A
outputs: F

F = NAND2(DECODE3(C, B, A), B)
"""
    prog = parse_program_text(text)
    with pytest.raises(synthesizer.SynthError, match="不可作为子表达式"):
        synthesizer.synthesize(prog)


def test_register_lookup_74138():
    """registry 应能查到 74138。"""
    spec = get_spec("74138")
    assert spec.model == "74138"
    assert spec.num_blocks == 1
    assert spec.num_gates == 0
    assert spec.block(0).primitive == "DECODE3"
    assert spec.block(0).inputs == [3, 2, 1]
    assert spec.block(0).outputs == [15, 14, 13, 12, 11, 10, 9, 7]


# ---------------- 12. 74153（MUX4）+ 混用 ----------------


def test_chip_74153_self_check():
    """74153 代表性 8 行：4 个 select × 使能 on/off。"""
    data = [0, 1, 0, 1]
    for sel in range(4):
        b = (sel >> 1) & 1
        a = sel & 1
        exp = data[sel]
        got_on = chip_74153.mux4([b, a, data[0], data[1], data[2], data[3], 0])
        assert got_on == exp, f"enable=0 sel={sel} expected={exp} got={got_on}"
        got_off = chip_74153.mux4([b, a, data[0], data[1], data[2], data[3], 1])
        assert got_off == 0, f"enable=1 sel={sel} expected=0 got={got_off}"


def test_parse_mux4_single_lhs():
    """MUX4 是单输出原语，单 LHS 解析应通过。"""
    text = """
chips:   74153 x 1
inputs:  B, A, C0, C1, C2, C3
outputs: M

M = MUX4(B, A, C0, C1, C2, C3)
"""
    prog = parse_program_text(text)
    asgn = prog.assignments[0]
    assert asgn.all_names == ["M"]
    assert isinstance(asgn.expr, Primitive)
    assert asgn.expr.name == "MUX4"
    assert asgn.expr.arity == 6


def test_synthesize_mux4(tmp_path):
    """综合 MUX4：1 个 74153_A + 1Y 接输出 + 默认使能 + 通道2 NC。"""
    text = """
chips:   74153 x 1
inputs:  B, A, C0, C1, C2, C3
outputs: M

M = MUX4(B, A, C0, C1, C2, C3)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)

    assert any(c.type == "74153" and c.name == "74153_A" for c in netlist.chips)
    pairs = {(c.src.chip, c.src.pin, c.dst.chip, c.dst.pin) for c in netlist.connections}
    assert ("74153_A", 7, "OUTPUT", "M") in pairs
    assert ("74153_A", 1, "GND", 0) in pairs  # 默认 1G̅ 使能

    # 通道 2 全部 NC 占位
    for pn in (9, 10, 11, 12, 13, 15):
        assert ("74153_A", pn, "NC", 0) in pairs


def test_mux4_e2e_verify(tmp_path):
    """端到端：MUX4 跑 8 行代表性真值表全 PASS。"""
    text = """
chips:   74153 x 1
inputs:  B, A, C0, C1, C2, C3
outputs: M

M = MUX4(B, A, C0, C1, C2, C3)
"""
    prog = parse_program_text(text)
    out_dir = tmp_path / "mux"
    netlist = synthesizer.synthesize(prog)
    netlist.save(out_dir)

    truth_md = """
| B | A | C0 | C1 | C2 | C3 | M |
|---|---|----|----|----|----|---|
| 0 | 0 | 0  | 1  | 0  | 1  | 0 |
| 0 | 0 | 1  | 0  | 1  | 0  | 1 |
| 0 | 1 | 0  | 1  | 0  | 1  | 1 |
| 0 | 1 | 1  | 0  | 1  | 0  | 0 |
| 1 | 0 | 0  | 1  | 0  | 1  | 0 |
| 1 | 0 | 1  | 0  | 1  | 0  | 1 |
| 1 | 1 | 0  | 1  | 0  | 1  | 1 |
| 1 | 1 | 1  | 0  | 1  | 0  | 0 |
"""
    truth_md_path = out_dir / "tt.md"
    truth_md_path.write_text(truth_md, encoding="utf-8")
    truth_csv = out_dir / "truth_table.csv"
    md_file_to_csv(truth_md_path, truth_csv)

    rc = verifier.main(
        [
            "--netlist",
            str(out_dir / "netlist.json"),
            "--truth",
            str(truth_csv),
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    rep = json.loads((out_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert rep["failed"] == 0
    assert rep["passed"] == 8


def test_register_lookup_74153():
    """registry 应能查到 74153。"""
    spec = get_spec("74153")
    assert spec.model == "74153"
    assert spec.num_blocks == 1
    assert spec.num_gates == 0
    assert spec.block(0).primitive == "MUX4"
    assert spec.block(0).inputs == [2, 14, 6, 5, 4, 3]
    assert spec.block(0).outputs == [7]


def test_mixed_chips_e2e(tmp_path):
    """混用 7400 + 74138 + 74153：F = NOT(C)，8 行全 PASS。"""
    text = """
chips:   7400 x 1, 74138 x 1, 74153 x 1
inputs:  C, B, A
outputs: F

Y0, Y1, Y2, Y3, Y4, Y5, Y6, Y7 = DECODE3(C, B, A)
M = MUX4(B, A, Y0, Y1, Y2, Y3)
F = NAND2(M, M)
"""
    prog = parse_program_text(text)
    out_dir = tmp_path / "mixed"
    netlist = synthesizer.synthesize(prog)
    netlist.save(out_dir)

    truth_md = """
| C | B | A | F |
|---|---|---|---|
| 0 | 0 | 0 | 1 |
| 0 | 0 | 1 | 1 |
| 0 | 1 | 0 | 1 |
| 0 | 1 | 1 | 1 |
| 1 | 0 | 0 | 0 |
| 1 | 0 | 1 | 0 |
| 1 | 1 | 0 | 0 |
| 1 | 1 | 1 | 0 |
"""
    truth_md_path = out_dir / "tt.md"
    truth_md_path.write_text(truth_md, encoding="utf-8")
    truth_csv = out_dir / "truth_table.csv"
    md_file_to_csv(truth_md_path, truth_csv)

    rc = verifier.main(
        [
            "--netlist",
            str(out_dir / "netlist.json"),
            "--truth",
            str(truth_csv),
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    rep = json.loads((out_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert rep["failed"] == 0
    assert rep["passed"] == 8


def test_mux4_at_top_level_only():
    """MUX4 不允许嵌套到 NAND 内部。"""
    text = """
chips:   7400 x 1, 74153 x 1
inputs:  B, A, C0, C1, C2, C3
outputs: F

F = NAND2(MUX4(B, A, C0, C1, C2, C3), B)
"""
    prog = parse_program_text(text)
    with pytest.raises(synthesizer.SynthError, match="不可作为子表达式"):
        synthesizer.synthesize(prog)


# ---------------- 13. 74151（MUX8，双输出）----------------


def test_chip_74151_self_check():
    """74151 自检：8 个 sel × 使能 on/off，Y/Ȳ 互补。"""
    data = [0, 1, 0, 1, 1, 0, 1, 0]
    for sel in range(8):
        a = sel & 1
        b = (sel >> 1) & 1
        c = (sel >> 2) & 1
        on = chip_74151.mux8([c, b, a] + data + [0])
        exp = data[sel]
        assert on == [exp, 1 - exp], f"enable=0 sel={sel} expected=[{exp},{1 - exp}] got={on}"
        off = chip_74151.mux8([c, b, a] + data + [1])
        assert off == [0, 1], f"enable=1 sel={sel} expected=[0,1] got={off}"


def test_register_lookup_74151():
    """registry 应能查到 74151，且 Block 元数据正确。"""
    spec = get_spec("74151")
    assert spec.model == "74151"
    assert spec.num_blocks == 1
    assert spec.num_gates == 0
    block = spec.block(0)
    assert block.primitive == "MUX8"
    assert block.inputs == [9, 10, 11, 4, 3, 2, 1, 15, 14, 13, 12]
    assert block.outputs == [5, 6]
    assert block.default_enables == [(7, "GND")]
    assert "74151" in get_spec("74151").model
    assert spec.vcc_pins == [16]
    assert spec.gnd_pins == [8]


def test_parse_mux8_dual_lhs():
    """MUX8 是双输出原语，必须用 2 个 LHS 名接收。"""
    text = """
chips:   74151 x 1
inputs:  C, B, A, D0, D1, D2, D3, D4, D5, D6, D7
outputs: Y

Y, YBAR = MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)
"""
    prog = parse_program_text(text)
    asgn = prog.assignments[0]
    assert asgn.all_names == ["Y", "YBAR"]
    assert isinstance(asgn.expr, Primitive)
    assert asgn.expr.name == "MUX8"
    assert asgn.expr.arity == 11


def test_parse_mux8_arity_check():
    """LHS 名字数 != 2 时 ParseError。"""
    bad_single = """
chips:   74151 x 1
inputs:  C, B, A, D0, D1, D2, D3, D4, D5, D6, D7
outputs: Y

Y = MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)
"""
    with pytest.raises(Exception, match="MUX8"):
        parse_program_text(bad_single)

    bad_three = """
chips:   74151 x 1
inputs:  C, B, A, D0, D1, D2, D3, D4, D5, D6, D7
outputs: Y, YBAR, EXTRA

Y, YBAR, EXTRA = MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)
"""
    with pytest.raises(Exception, match="MUX8"):
        parse_program_text(bad_three)


def test_parse_mux8_must_be_top_level():
    """MUX8 不可作为 NAND 子表达式。"""
    text = """
chips:   7400 x 1, 74151 x 1
inputs:  C, B, A, D0, D1, D2, D3, D4, D5, D6, D7
outputs: F

F = NAND2(MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7), 1)
"""
    prog = parse_program_text(text)
    with pytest.raises(synthesizer.SynthError, match="不可作为子表达式"):
        synthesizer.synthesize(prog)


def test_synthesize_mux8():
    """综合 MUX8：1 个 74151_A + Y 接 OUTPUT + Ē→GND + 11 个信号输入连线。"""
    text = """
chips:   74151 x 1
inputs:  C, B, A, D0, D1, D2, D3, D4, D5, D6, D7
outputs: Y

Y, YBAR = MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)
"""
    prog = parse_program_text(text)
    netlist = synthesizer.synthesize(prog)

    assert any(c.type == "74151" and c.name == "74151_A" for c in netlist.chips)
    pairs = {(c.src.chip, c.src.pin, c.dst.chip, c.dst.pin) for c in netlist.connections}

    # Y → OUTPUT.Y
    assert ("74151_A", 5, "OUTPUT", "Y") in pairs
    # 默认 Ē 使能：pin 7 → GND
    assert ("74151_A", 7, "GND", 0) in pairs
    # 电源
    assert ("74151_A", 16, "VCC", 0) in pairs
    assert ("74151_A", 8, "GND", 0) in pairs
    # 11 个信号输入：INPUT.{C,B,A,D0..D7} → 74151_A pin {9,10,11,4,3,2,1,15,14,13,12}
    expected_inputs = {
        ("INPUT", "C", "74151_A", 9),
        ("INPUT", "B", "74151_A", 10),
        ("INPUT", "A", "74151_A", 11),
        ("INPUT", "D0", "74151_A", 4),
        ("INPUT", "D1", "74151_A", 3),
        ("INPUT", "D2", "74151_A", 2),
        ("INPUT", "D3", "74151_A", 1),
        ("INPUT", "D4", "74151_A", 15),
        ("INPUT", "D5", "74151_A", 14),
        ("INPUT", "D6", "74151_A", 13),
        ("INPUT", "D7", "74151_A", 12),
    }
    assert expected_inputs.issubset(pairs)


def test_mux8_e2e_verify(tmp_path):
    """端到端：MUX8 跑 8 行真值表（每行选不同 Di）全 PASS。"""
    text = """
chips:   74151 x 1
inputs:  C, B, A, D0, D1, D2, D3, D4, D5, D6, D7
outputs: Y

Y, YBAR = MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)
"""
    prog = parse_program_text(text)
    out_dir = tmp_path / "mux8"
    netlist = synthesizer.synthesize(prog)
    netlist.save(out_dir)

    # 每行只让目标 Di=1，其余=0；输出 Y 应等于该 Di
    truth_md = """
| C | B | A | D0 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | Y |
|---|---|---|----|----|----|----|----|----|----|----|---|
| 0 | 0 | 0 | 1  | 0  | 0  | 0  | 0  | 0  | 0  | 0  | 1 |
| 0 | 0 | 1 | 0  | 1  | 0  | 0  | 0  | 0  | 0  | 0  | 1 |
| 0 | 1 | 0 | 0  | 0  | 1  | 0  | 0  | 0  | 0  | 0  | 1 |
| 0 | 1 | 1 | 0  | 0  | 0  | 1  | 0  | 0  | 0  | 0  | 1 |
| 1 | 0 | 0 | 0  | 0  | 0  | 0  | 1  | 0  | 0  | 0  | 1 |
| 1 | 0 | 1 | 0  | 0  | 0  | 0  | 0  | 1  | 0  | 0  | 1 |
| 1 | 1 | 0 | 0  | 0  | 0  | 0  | 0  | 0  | 1  | 0  | 1 |
| 1 | 1 | 1 | 0  | 0  | 0  | 0  | 0  | 0  | 0  | 1  | 1 |
"""
    truth_md_path = out_dir / "tt.md"
    truth_md_path.write_text(truth_md, encoding="utf-8")
    truth_csv = out_dir / "truth_table.csv"
    md_file_to_csv(truth_md_path, truth_csv)

    rc = verifier.main(
        [
            "--netlist",
            str(out_dir / "netlist.json"),
            "--truth",
            str(truth_csv),
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    rep = json.loads((out_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert rep["failed"] == 0
    assert rep["passed"] == 8


def test_blood_match_74151_e2e(tmp_path):
    """实验 2_1 血型配对：单 74151 跑 16 行真值表全 PASS。"""
    text = """
chips:   74151 x 1
inputs:  A1, A0, B1, B0
outputs: F

F, F_BAR = MUX8(A1, A0, B1, 1, 1, B0, B0, 0, 1, 0, B0)
"""
    prog = parse_program_text(text)
    out_dir = tmp_path / "blood"
    netlist = synthesizer.synthesize(prog)
    netlist.save(out_dir)

    truth_md = """
| A1 | A0 | B1 | B0 | F |
|----|----|----|----|---|
| 0  | 0  | 0  | 0  | 1 |
| 0  | 0  | 0  | 1  | 1 |
| 0  | 0  | 1  | 0  | 1 |
| 0  | 0  | 1  | 1  | 1 |
| 0  | 1  | 0  | 0  | 0 |
| 0  | 1  | 0  | 1  | 1 |
| 0  | 1  | 1  | 0  | 0 |
| 0  | 1  | 1  | 1  | 1 |
| 1  | 0  | 0  | 0  | 0 |
| 1  | 0  | 0  | 1  | 0 |
| 1  | 0  | 1  | 0  | 1 |
| 1  | 0  | 1  | 1  | 1 |
| 1  | 1  | 0  | 0  | 0 |
| 1  | 1  | 0  | 1  | 0 |
| 1  | 1  | 1  | 0  | 0 |
| 1  | 1  | 1  | 1  | 1 |
"""
    truth_md_path = out_dir / "tt.md"
    truth_md_path.write_text(truth_md, encoding="utf-8")
    truth_csv = out_dir / "truth_table.csv"
    md_file_to_csv(truth_md_path, truth_csv)

    rc = verifier.main(
        [
            "--netlist",
            str(out_dir / "netlist.json"),
            "--truth",
            str(truth_csv),
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    rep = json.loads((out_dir / "verify_report.json").read_text(encoding="utf-8"))
    assert rep["failed"] == 0
    assert rep["passed"] == 16
