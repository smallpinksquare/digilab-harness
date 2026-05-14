# digilab

**digilab** 是一个 Python 库，用于将 NAND 门组合逻辑电路的简洁 DSL 表达式综合为面包板接线图（`circuit.txt` + `netlist.json`），并通过真值表自动验证电路正确性。

## 核心功能

- **DSL**：在 Markdown 文件中声明芯片、输入、输出和赋值表达式；支持门级原语（`NAND2`、`NAND4`）、MSI 高层原语（`DECODE3`、`MUX4`、`MUX8`）、字面量常量和中间变量。
- **综合器**：表达式 → `netlist.json` + `circuit.txt`（菊花链扇出 + VCC 输入替换优化）。
- **验证器**：对全部真值表行求值，输出 `verify_report.json`（含通过行数与差异详情）。
- **器件库**：内置 7400、7420、74138、74153、74151；支持通过 `digilab.chips` 入口点扩展第三方芯片。

## 文档目录

| 页面 | 内容 |
|------|------|
| [架构说明](../architecture.md) | 内部 pipeline 与数据流（英文） |
| [DSL 参考](../dsl_reference.md) | 表达式语法、所有原语（英文） |
| [物理接线](../physical_wiring.md) | 菊花链和 VCC 替换原理（英文） |
| [扩展器件](../chip_extension.md) | 内置或插件芯片的添加方法（英文） |
| **Chinese README** | [README.zh-CN.md](../../README.zh-CN.md) |

## 快速开始

```bash
# 克隆仓库并安装
git clone <repo>
cd digilab-harness
pip install -e ".[dev]"
```

写一个表达式文件（`expr.md`）：

```txt
chips:   7400 x 1
inputs:  A, B
outputs: F

F = NAND2(A, B)
```

运行综合与验证：

```bash
digilab synth  --expr expr.md --out /tmp/ex
digilab verify --netlist /tmp/ex/netlist.json --truth /tmp/ex/truth_table.csv --out /tmp/ex
```

查看 [`examples/`](../../examples/README.md) 中的 4 个完整示例。
