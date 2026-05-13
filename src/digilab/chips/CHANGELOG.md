# chips/CHANGELOG

记录器件库及其配套综合/验证能力的关键增量，按时间倒序。

---

## [Step 5] 新增 74151 + MUX8（双输出 8 选 1）

- 动机：实验 2_1（血型配对）改用 8 选 1 数据选择器实现，4 变量场景下 1 片即可覆盖、零外部门；同时验证"双输出原语"在 Block/Primitive 抽象下的可扩展性。
- 主要文件：
  - `chips/chip_74151.py`（新建：`mux8` 完整逻辑、`_mux8_block_func` Block 视角、`make_spec` + 16 行 `_self_check`）
  - `common/parser.py`（`_PRIMITIVE_OUTPUT_COUNT["MUX8"] = 2`）
  - `chips/registry.py`（注册 74151）
  - `tests/test_smoke.py`（新增第 13 节 8 项 74151/MUX8/血型配对测试）
  - `真值表与逻辑表达式/实验2_1_表达式.md`（改写为 74151 版）
  - `实验2_1/spec.json`（chips 切到 `74151 x 1`）
  - `实验2_1/{netlist.json, circuit.txt, truth_table.csv, actual_truth_table.csv, verify_report.json}`（重新生成）
  - `实验2_1/实验2_1_日志_成功.md`、`实验2_1/实验2_1_物理接线指南.md`（重写）
- 设计要点：
  - MUX8 双输出：`Y, YBAR = MUX8(C, B, A, D0..D7)`；输出顺序 `[Y, Ȳ]`，对应芯片 pin `[5, 6]`
  - 默认使能：`Ē(pin 7) → GND.0`，由 `Block.default_enables` 自动注入
  - 综合器 / 验证器**零改动**：`_emit_primitive` 与统一 `units` 求值已 generic
- 验收标志：
  - pytest 全量通过（34 旧 + 8 新 = 42 项）
  - 实验 2_1 verify 16/16 PASS（单片 74151，零 NAND）
  - 实验 1_1 / 1_2 / 2_2 产物 SHA256 字节级零漂移
  - 74138/74153 单芯片示例与 7400+74138+74153 混用 e2e 仍 PASS
  - 74153 仍保留可用，不受本次升级影响

---

## [Step 4] 文档与日志收口

- 动机：按工单 Step 4 完成最终交付，补齐规范文档、变更记录与总成功日志。
- 主要文件：
  - `harness附录.md`（追加附录 H：扩展能力）
  - `README.md`（追加 §6：当前能力清单）
  - `chips/CHANGELOG.md`（本文件）
  - `实验0_器件扩展/实验0_日志_成功.md`
- 验收标志：
  - pytest 全量通过（34 项）
  - 实验 1_1 / 1_2 产物 SHA256 字节级零漂移
  - `示例_74138` / `示例_74153` / `示例_混用` 端到端均 PASS

---

## [Step 3] 新增 74153 + MUX4 + 跨芯片混用

- 动机：在 Step 2 的 Block/Primitive 抽象上增量接入 74153，多路选择器场景落地并验证跨芯片协同。
- 主要文件：
  - `chips/chip_74153.py`
  - `common/parser.py`（`_PRIMITIVE_OUTPUT_COUNT["MUX4"] = 1`）
  - `chips/registry.py`（注册 74153）
  - `tests/test_smoke.py`（新增 7 项 74153/混用测试）
  - `真值表与逻辑表达式/示例_74153_*.md`
  - `真值表与逻辑表达式/示例_混用_*.md`
- 验收标志：
  - pytest 34 项通过（27 旧 + 7 新）
  - 74153 单芯片示例 8/8 PASS
  - 7400+74138+74153 混用示例 8/8 PASS
  - 实验 1_1 / 1_2 回归产物 SHA256 不变

---

## [Step 2] 新增 74138 + DECODE3 + Block/Primitive 抽象

- 动机：支持中规模多输出器件（译码器），避免把多输出能力硬塞进单输出 `Gate`。
- 主要文件：
  - `common/ast_nodes.py`（新增 `Primitive` + `Assignment.extra_names`）
  - `chips/__init__.py`（新增 `Block` + `ChipSpec.blocks`）
  - `common/parser.py`（多 LHS + `DECODE3` 解析）
  - `chips/chip_74138.py`
  - `chips/registry.py`（注册 74138）
  - `synthesizer.py`（`alloc_block` / `_emit_primitive`）
  - `verifier.py`（统一 `units` 求值）
  - `tests/test_smoke.py`（新增 8 项 74138 测试）
- 验收标志：
  - pytest 27 项通过（19 旧 + 8 新）
  - 74138 端到端示例 8/8 PASS
  - 实验 1_1 / 1_2 回归产物 SHA256 不变

---

## [Step 1] 设计确认轮

- 动机：在不破坏 7400/7420 既有接口的前提下，先明确中规模器件扩展架构与边界。
- 设计结论：
  - AST 引入 `Primitive`，解析支持多 LHS 解构赋值
  - 器件层引入 `Block` 与 `Gate` 并行
  - verifier 从 `gates` 升级为统一 `units` 抽象
  - 默认使能通过 netlist 显式连线记录
- 状态：方案获确认后进入 Step 2 实施。

---

## [历史] 菊花链扇出（Daisy-Chain Fanout）

- 把星型扇出重排为菊花链扇出，提升面包板可布线性。
- 实现位置：`synthesizer.py::_daisy_chain_connections`
- 效果：电气等价（verifier 并查集不变），物理连线更短更规整。

## [历史] VCC 输入替换（VCC Input Substitution）

- 把 NAND 的 `Const(1)` 输入由直接接 VCC 改为借接同门真实信号输入，降低电源干扰风险。
- 实现位置：`synthesizer.py` 的 `Nand` 发射分支
- 保留兜底：全 1 输入时 fallback 仍可接 VCC。

## [历史] 自动 CSE + 中间变量

- 自动公共子表达式复用（结构化 CSE）减少门占用；
- 支持中间变量 `T1 = ...`，提升表达式可读性。
- 实现位置：`synthesizer.py` 缓存 + `parser.py` 的先定义后使用校验。

## [历史] 字面量 0/1 与多行表达式解析

- `Const(0/1)` 映射到 GND/VCC；
- parser 支持 markdown 中跨行表达式与 BOM 输入。
- 对现有实验保持向后兼容。
