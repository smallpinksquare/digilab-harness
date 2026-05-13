"""真值表 I/O：md ↔ CSV ↔ DataFrame。

CSV 第一行：所有输入变量 → 所有输出变量。
md 表格：第一列为表头，含所有输入与输出列。
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import List, Sequence, Tuple

# 单元格中允许出现的真值
_VALID = {"0", "1", "X", "x", "-"}


def _normalize_cell(s: str) -> str:
    s = s.strip()
    if s in {"-", "x"}:
        return "X"
    if s in _VALID:
        return s.upper() if s != "0" and s != "1" else s
    raise ValueError(f"真值表单元格非法：{s!r}（期望 0/1/X）")


# ---------- md → 行列结构 ----------

def parse_md_table(text: str) -> Tuple[List[str], List[List[str]]]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    table_rows: List[List[str]] = []
    for line in lines:
        if not line.startswith("|"):
            continue
        # 跳过分隔行（| --- | --- |）
        if re.fullmatch(r"\|[\s\-:|]+\|", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        table_rows.append(cells)

    if not table_rows:
        raise ValueError("未在 md 中找到表格")

    header = table_rows[0]
    body = [[_normalize_cell(c) for c in row] for row in table_rows[1:]]

    for i, row in enumerate(body):
        if len(row) != len(header):
            raise ValueError(f"第 {i+2} 行列数 {len(row)} 与表头 {len(header)} 不一致")
    return header, body


# ---------- CSV I/O ----------

def write_csv(path: Path, header: Sequence[str], rows: Sequence[Sequence[str]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(list(header))
        for row in rows:
            w.writerow(list(row))


def read_csv(path: Path) -> Tuple[List[str], List[List[str]]]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        r = list(csv.reader(f))
    if not r:
        raise ValueError(f"空的 CSV：{path}")
    header = r[0]
    body = [[_normalize_cell(c) for c in row] for row in r[1:]]
    return header, body


# ---------- 一站式：md 文件 → CSV 文件 ----------

def md_file_to_csv(md_path: Path, csv_path: Path) -> Tuple[List[str], List[List[str]]]:
    text = Path(md_path).read_text(encoding="utf-8-sig")
    header, body = parse_md_table(text)
    write_csv(csv_path, header, body)
    return header, body


# ---------- 工具 ----------

def split_io(header: Sequence[str], inputs: Sequence[str], outputs: Sequence[str]) -> Tuple[List[int], List[int]]:
    """根据期望的 inputs/outputs 名字列表，从 header 中找出列序号。"""
    in_idx = []
    out_idx = []
    for name in inputs:
        if name not in header:
            raise ValueError(f"真值表缺少输入列 {name!r}（表头 {header}）")
        in_idx.append(header.index(name))
    for name in outputs:
        if name not in header:
            raise ValueError(f"真值表缺少输出列 {name!r}（表头 {header}）")
        out_idx.append(header.index(name))
    return in_idx, out_idx
