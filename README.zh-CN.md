# digilab

[![CI](https://github.com/digilab-harness/digilab/actions/workflows/ci.yml/badge.svg)](https://github.com/digilab-harness/digilab/actions/workflows/ci.yml)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)

**digilab** 是一个 Python 库，能够将 NAND 门组合逻辑电路的简洁 DSL 表达式综合为面包板接线图（`circuit.txt` + `netlist.json`），并通过真值表自动验证电路正确性。

> English README: [README.md](README.md)

---

## 快速开始

```bash
git clone https://github.com/digilab-harness/digilab
cd digilab-harness
pip install -e ".[dev]"
```

写一个表达式文件：

```txt
chips:   7400 x 1
inputs:  A, B
outputs: F

F = NAND2(A, B)
```

综合与验证：

```bash
digilab synth  --expr expr.md --out /tmp/ex
digilab verify --netlist /tmp/ex/netlist.json \
               --truth   /tmp/ex/truth_table.csv \
               --out     /tmp/ex
```

运行所有已注册芯片的自检：

```bash
digilab selftest
```

---

## 支持的芯片

| 型号 | 原语 | 内部功能 |
|------|-----|---------|
| **7400** | `NAND2(a, b)` | 4 个 2 输入与非门 |
| **7420** | `NAND4(a,b,c,d)` | 2 个 4 输入与非门 |
| **74138** | `DECODE3(C,B,A)` → 8 路输出 | 3-8 译码器 |
| **74153** | `MUX4(B,A,C0,C1,C2,C3)` | 4 选 1 数据选择器 |
| **74151** | `MUX8(C,B,A,D0..D7)` → Y, YBAR | 8 选 1 数据选择器（双互补输出） |

第三方芯片可通过 `digilab.chips` [入口点组](docs/chip_extension.md)注册。

---

## 核心特性

- **菊花链扇出**：一个信号驱动多个输入时，生成 `src → d0 → d1 → …` 的链式连接，减少面包板跳线数量。
- **VCC 输入替换**：将接 VCC 的空闲输入改接到同一门内已存在的信号，避免 CMOS 悬空输入带来的不稳定高电平。
- **自动 CSE**：中间变量（`T = NAND2(A,A)`）通过结构性公共子表达式消除自动复用门资源。
- **多 LHS 原语**：具有多输出的 MSI 器件支持自然的多赋值语法（`Y0, …, Y7 = DECODE3(C,B,A)`）。
- **严格类型**：全库 `mypy --strict` 覆盖，包含 `py.typed` 标记。

---

## 开发

```bash
ruff check .
ruff format --check .
mypy src/digilab
pytest
```

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 文档

完整文档在 [`docs/`](docs/index.md)（英文主文档，中文入口见 [`docs/zh/index.md`](docs/zh/index.md)）：

- [架构说明](docs/architecture.md)
- [DSL 参考](docs/dsl_reference.md)
- [物理接线](docs/physical_wiring.md)
- [扩展器件](docs/chip_extension.md)

课程专用产物（实验接线指南、真值表等）保存在 [`course_archive/`](course_archive/README.md)。

---

## 许可证

[BSD 3-Clause](LICENSE) © 2026 digilab contributors
