# Phase D 独立审查报告

**审查时间**：2026-05-19  
**审查范围**：Phase D — 最终发布准备（CHANGELOG、全量回归、发布收尾）  
**审查人**：L2 独立 readonly subagent（零上下文，从目录树出发）

---

## 1. 总体评价

Phase D 已完成 v0.1.0 全量发布准备。CHANGELOG 填写完整，55 项测试全部通过（含 4 个 examples 回归），ruff/mypy strict 零报错，`run_all.py` SHA256 与基线完全一致。

**评分**：✅ 通过（含修复项，见第 3 节）

---

## 2. 确认通过的检查项

| 检查项 | 结果 |
|---|---|
| `pytest` 55 tests | ✅ PASS |
| `ruff check src/digilab/` | ✅ PASS（修复 UP035/UP006 后） |
| `mypy src/digilab --strict` | ✅ PASS (16 files, 0 issues) |
| `run_all.py` SHA256 回归 | ✅ PASS |
| `CHANGELOG.md` v0.1.0 填写 | ✅ 已填写，含 Python 3.13 CI 条目 |
| `digilab --version` | ✅ 0.1.0 |
| `digilab selftest` | ✅ 动态枚举所有 chip |
| `verifier --truth` 接受 `.md` | ✅ 已实装（md_file_to_csv 自动转换） |

---

## 3. 发现的问题及修复

### 3.1 README Quick Start 与实际 CLI 不一致（已修复）

**问题**：`git clone` 目标目录名与 `cd` 命令不一致；`--truth` 示例引用 `.md` 文件，但原 `verifier.py` 只接受 `.csv`。

**修复**：
- `README.md` 中 `git clone` 统一加 `digilab-harness` 目标目录名参数。
- `verifier.py` `main()` 增加 `.md` 后缀自动检测，调用 `md_file_to_csv` 并生成临时 `truth_table.csv`；`--truth` help 文字更新。
- README 注明 `--truth` 同时接受 `.md` 和 `.csv`。

### 3.2 `verifier.py` 存在大量预存 UP035/UP006 ruff 警告（已修复）

**问题**：`List`, `Dict`, `Tuple`, `Optional`, `Iterator` 等旧式 typing 注解在 `target-version = "py39"` + `UP` 规则下被视为 errors；`chips/__init__.py` 同样。

**修复**：`ruff check --fix --unsafe-fixes` 自动升级全部类型注解；`chips/__init__.py` 中遗留的 `Dict/List/Tuple` import 手动改为 `from collections.abc import Callable`。

---

## 4. 遗留说明

- `pyproject.toml` 中的 GitHub URLs（`https://github.com/digilab-harness/digilab`）是占位符，正式 push 前无需更改，待 GitHub 仓库创建后生效。
- `course_archive/` 已通过 `.gitattributes` 标记为 `linguist-vendored`，不影响 GitHub 语言统计。
- Python 3.13 已加入 CI matrix（`ci.yml`）。

---

## 5. L3 发布建议

所有机械检查已通过，文档、示例、治理文件齐全。  
建议操作：

```bash
cd digilab-harness
git tag v0.1.0
git push origin main --tags
```

> 仓库推送前请先在 GitHub 创建 `digilab-harness/digilab` 仓库，并配置 remote：  
> `git remote add origin https://github.com/digilab-harness/digilab.git`
