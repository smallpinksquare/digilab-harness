# Phase A 独立审查报告

**审查时间：** 2026-05-14  
**审查者：** L2 独立 readonly subagent（由 Agent 落盘）  
**审查范围：** `digilab-harness/`（`src/`、`tests/`、`course_archive/`、`pyproject.toml` 等）

---

## 清单逐项结论

### A1. src layout 完整性

| 子项 | 结论 | 说明 |
|------|------|------|
| `src/digilab/__init__.py` 含 `__version__`、`__all__` | **PASS** | `__version__` 行 13，`__all__` 行 19-25 |
| `src/digilab/chips/__init__.py` 存在 | **PASS** | 存在 |
| `src/digilab/common/__init__.py` 存在 | **PASS** | 存在（subagent 中文路径 glob 误报为 FAIL，Python 实际验证存在） |
| `src/digilab/cli.py` 含 synth/verify/selftest | **PASS** | 三个子命令均实现 |
| `src/digilab/synthesizer.py` 存在 | **PASS** | 存在 |
| `src/digilab/verifier.py` 存在 | **PASS** | 存在 |

### A2. 残留旧 import

| 子项 | 结论 |
|------|------|
| `from chips.` / `import chips` 零命中 | **PASS** |
| `from common.` / `import common` 零命中 | **PASS** |
| `import synthesizer` / `import verifier` 零命中 | **PASS** |
| `sys.path.insert` hack 已删除 | **PASS** |

### A3. pyproject.toml

| 子项 | 结论 |
|------|------|
| `packages = ["src/digilab"]` 覆盖子模块 | **PASS** |
| `requires-python >= 3.9` | **PASS** |
| `license = BSD-3-Clause` | **PASS** |
| `dependencies` networkx/pandas | **PASS** |
| `[project.scripts] digilab = "digilab.cli:main"` | **PASS** |

### A4. course_archive/ 完整性

| 子项 | 结论 | 说明 |
|------|------|------|
| 实验1_1/1_2/2_1/2_2/ | **PASS** | 存在 |
| 实验0_器件扩展/ 实验一/ 实验二/ | **PASS** | 存在 |
| 真值表与逻辑表达式/ 示例_74138/74153/混用/ | **PASS** | 存在 |
| 模拟电路程序harness.md / harness附录.md / 更新工单.md | **PASS** | 存在 |
| 教学计划 PDF | **PASS** | 存在（subagent 中文路径 glob 误报，Python 验证存在 3 个 PDF） |
| run_all.py / run_all.ps1 | **PASS** | 存在 |
| 重塑日志/ | **PASS** | 存在（本文件所在目录） |
| 仓库根无中文课程产物目录 | **PASS** | 根目录只有 src/ tests/ course_archive/ pyproject.toml 等 |

### A5. CLI 可用性

| 子项 | 结论 |
|------|------|
| synth/verify/selftest 子命令实现 | **PASS** |
| synth/verify 委派 synthesizer/verifier.main | **PASS** |
| selftest 调用所有已注册芯片 _self_check | **WARN** — chip_7400/7420 无 _self_check，会被 skip（已知设计）；3 个 MSI 芯片有并通过 |

### A6. synthesizer/verifier.main 错误处理

| 模块 | 结论 | 说明 |
|------|------|------|
| `synthesizer.main` | **PASS** | try/except Exception → stderr + return 1 |
| `verifier.main` | **PASS** | 已在本次修复补充 try/except（与 synthesizer 对称） |

### A7. tests 覆盖

| 子项 | 结论 |
|------|------|
| test_smoke.py 无旧 import / sys.path hack | **PASS** |
| test_cli.py 覆盖 synth/verify/selftest/bad_expr | **PASS** |

---

## 自由审查（清单外发现）

1. **docstring CLI 用法过时**：`synthesizer.py` / `verifier.py` 文件头原写 `python synthesizer.py ...`，已在本次修复更新为 `digilab synth` / `python -m digilab.synthesizer`。
2. **版本双处同步**：`pyproject.toml version` 与 `__init__.__version__` 需长期保持一致，Phase D 可加 CI 校验。
3. **测试 fixture 与 course_archive 耦合**：`test_smoke.py` 中 `ROOT = .../course_archive`，若 sdist 不含 course_archive，这些测试会失败。Phase C 的 examples/ 迁移后需更新 fixture 路径。
4. **占位 URL**：`pyproject.toml` GitHub URLs 为 placeholder，发布前替换。
5. **_CHIP_MODULES 手写列表**：已知技术债，Phase B entry-points 机制解决。

---

## 修复情况

| FAIL/WARN | 是否修复 | 说明 |
|-----------|----------|------|
| common/__init__.py 缺失（误报） | N/A | 实际存在，subagent glob 中文路径问题 |
| 教学计划 PDF 缺失（误报） | N/A | 实际存在 |
| verifier.main 无 try/except | **已修复** | 补充 try/except（与 synthesizer 对称） |
| docstring 旧 CLI 用法 | **已修复** | 更新为 `digilab synth/verify` 与 `python -m` |

---

## 反思（subagent 原文）

若重来 Phase A，优先点：①`common/__init__.py` 存在性写进迁移脚本自检；②course_archive 完整性用脚本化存在性校验而非人工；③CLI selftest 协议从第一天统一（所有 chip 都有或都没有 `_self_check`）；④synthesizer/verifier 异常策略对称，不留单边空白；⑤测试数据尽早从 course_archive 迁到 `tests/fixtures` 或 `examples/`。

---

**Phase A 总体结论：PASS（修复后）**  
实现 todo 全部完成，L1 卡口（47 tests + SHA256 × 8）全绿，所有 FAIL/WARN 已修复或记录为已知技术债。
