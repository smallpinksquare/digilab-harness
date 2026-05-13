# 模拟电路项目

按 [模拟电路程序harness.md](模拟电路程序harness.md) 与 [harness附录.md](harness附录.md) 规范实现的
**电路综合 / 验证 pipeline**。

---

## 1. 目录结构

```
模拟电路项目/
├── chips/                      # 器件库（每型号一个文件）
│   ├── __init__.py             # PinType / Pin / ChipSpec 基类
│   ├── chip_7400.py            # 7400 四 2 输入与非
│   ├── chip_7420.py            # 7420 双 4 输入与非
│   └── registry.py             # 型号 → 类的注册表
├── common/                     # 共享工具
│   ├── netlist.py              # Netlist 数据结构 + JSON I/O + 排序
│   ├── ast_nodes.py            # 表达式 AST
│   ├── parser.py               # 表达式文件解析
│   └── tt_io.py                # 真值表 md ↔ CSV
├── synthesizer.py              # 程序1：表达式 → circuit.txt + netlist.json
├── verifier.py                 # 程序2：netlist + 期望真值表 → 验证报告
├── tests/test_smoke.py         # 端到端 smoke 测试
├── 真值表与逻辑表达式/         # 用户输入文件夹（每个实验放一对 md）
└── 实验x/                      # 每个具体实验的产物（agent 创建）
```

---

## 2. 安装

```bash
pip install -r requirements.txt
```

需要 Python 3.9+。

---

## 3. 使用

### 综合（程序1）

```bash
python synthesizer.py \
    --expr 真值表与逻辑表达式/示例_表达式.md \
    --out 实验示例
```

产出：`实验示例/circuit.txt`、`实验示例/netlist.json`。

### 验证（程序2）

```bash
python verifier.py \
    --netlist 实验示例/netlist.json \
    --truth   实验示例/truth_table.csv \
    --out     实验示例
```

产出：`实验示例/actual_truth_table.csv`、`实验示例/verify_report.json`。

### Smoke 测试

```bash
pytest tests/
```

---

## 4. 表达式文件格式

参见 [真值表与逻辑表达式/README.md](真值表与逻辑表达式/README.md)
和 [真值表与逻辑表达式/示例_表达式.md](真值表与逻辑表达式/示例_表达式.md)。

简要：

```
chips: 7400 x 1
inputs: A, B
outputs: F

F = NAND2(A, B)
```

---

## 5. 扩展新器件

只需在 `chips/` 下新建 `chip_xxxx.py`，继承 `ChipSpec`，并在 `chips/registry.py`
中注册即可。`synthesizer.py` 与 `verifier.py` 无需任何改动。

---

## 6. 当前能力清单（Step 1-4）

### 6.1 已注册器件

- `7400`：四个 2 输入与非门（NAND2）
- `7420`：两个 4 输入与非门（NAND4）
- `74138`：3-8 译码器（高层原语 `DECODE3`）
- `74153`：双 4 选 1 数据选择器（当前暴露通道 1，高层原语 `MUX4`）
- `74151`：8 选 1 数据选择器（双互补输出 Y / Ȳ，高层原语 `MUX8`）

### 6.2 已支持表达式原语

- 门级原语：`NAND2(...)`、`NAND4(...)`
- 高层原语：`DECODE3(C, B, A)`、`MUX4(B, A, C0, C1, C2, C3)`、`MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)`
- 字面量：`0`、`1`（分别映射到 GND / VCC，并支持物理接线优化）
- 中间变量：`T1 = ...`，后续表达式可引用（必须先定义后使用）

### 6.3 多 LHS 语法示例

```txt
chips:   74138 x 1
inputs:  C, B, A
outputs: Y0, Y1, Y2, Y3, Y4, Y5, Y6, Y7

Y0, Y1, Y2, Y3, Y4, Y5, Y6, Y7 = DECODE3(C, B, A)
```

双输出原语 `MUX8` 也用多 LHS 接收：

```txt
chips:   74151 x 1
inputs:  C, B, A, D0, D1, D2, D3, D4, D5, D6, D7
outputs: Y

Y, YBAR = MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)
```

> 多输出原语必须在赋值顶层使用；不允许把 `DECODE3` / `MUX4` / `MUX8` 嵌套到 `NAND2/NAND4` 内部。
> `outputs:` 中未声明的 LHS（如上例的 `YBAR`）会作为内部信号保留，对应芯片输出引脚物理上悬空。

### 6.4 相关文档

- 规范附录（含新增扩展说明）：[harness附录.md](harness附录.md)（见附录 H）
- 器件库变更记录：[chips/CHANGELOG.md](chips/CHANGELOG.md)
