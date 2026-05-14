"""course_archive/run_all.py

一键重跑 实验1_1 / 1_2 / 2_1 / 2_2 的 synth + verify，
并对关键产物（circuit.txt / verify_report.json）做 SHA256 校验，
确保与 _baseline_sha256.txt 中记录的迁移前快照字节级一致。

用法（从 digilab-harness/ 根目录 或 course_archive/ 均可）：
    python course_archive/run_all.py
    python course_archive/run_all.py --no-check   # 只跑，不比对 SHA256

退出码：
    0 = 全部通过
    1 = 有实验失败或 SHA256 不匹配
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Locate repo root and baseline file regardless of cwd
SCRIPT = Path(__file__).resolve()
COURSE = SCRIPT.parent                         # course_archive/
REPO = COURSE.parent                           # digilab-harness/
BASELINE = REPO.parent / "_baseline_sha256.txt"  # AI-EE/_baseline_sha256.txt

EXPERIMENTS = ["实验1_1", "实验1_2", "实验2_1", "实验2_2"]

# Products to verify per experiment
VERIFY_PRODUCTS = ["circuit.txt", "verify_report.json"]


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_baseline() -> dict[str, str]:
    """Return {posix-rel-from-AI-EE -> sha256hex}."""
    if not BASELINE.is_file():
        return {}
    result: dict[str, str] = {}
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        result[rel] = digest
    return result


def run_experiment(exp_id: str, check: bool, baseline: dict[str, str]) -> bool:
    exp_dir = COURSE / exp_id
    spec_path = exp_dir / "spec.json"
    if not spec_path.is_file():
        print(f"  [SKIP] {exp_id}: spec.json not found")
        return True

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    expr_md = (exp_dir / spec["expression_file"]).resolve()
    truth_md = (exp_dir / spec["truth_table_file"]).resolve()

    if not expr_md.is_file():
        print(f"  [FAIL] {exp_id}: expr not found: {expr_md}")
        return False
    if not truth_md.is_file():
        print(f"  [FAIL] {exp_id}: truth not found: {truth_md}")
        return False

    # --- synth ---
    from digilab.synthesizer import main as synth_main
    rc = synth_main(["--expr", str(expr_md), "--out", str(exp_dir)])
    if rc != 0:
        print(f"  [FAIL] {exp_id}: synth returned {rc}")
        return False

    # --- verify ---
    from digilab.common.tt_io import md_file_to_csv
    csv_path = exp_dir / "truth_table.csv"
    md_file_to_csv(truth_md, csv_path)

    from digilab.verifier import main as verify_main
    rc = verify_main([
        "--netlist", str(exp_dir / "netlist.json"),
        "--truth", str(csv_path),
        "--out", str(exp_dir),
    ])
    if rc != 0:
        print(f"  [FAIL] {exp_id}: verify returned {rc}")
        return False

    if not check or not baseline:
        print(f"  [OK]   {exp_id}: synth+verify passed (SHA256 check skipped)")
        return True

    # --- SHA256 比对 ---
    ok = True
    for prod in VERIFY_PRODUCTS:
        p = exp_dir / prod
        if not p.is_file():
            print(f"  [WARN] {exp_id}/{prod}: file missing after run")
            continue
        # baseline key 形如 "模拟电路项目/实验1_1/circuit.txt"
        baseline_key = f"模拟电路项目/{exp_id}/{prod}"
        expected = baseline.get(baseline_key)
        if expected is None:
            print(f"  [WARN] {exp_id}/{prod}: not in baseline (new file?)")
            continue
        actual = sha256_of(p)
        if actual == expected:
            print(f"  [OK]   {exp_id}/{prod}: SHA256 match")
        else:
            print(f"  [DIFF] {exp_id}/{prod}: expected {expected[:12]}... actual {actual[:12]}...")
            ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-check", action="store_true",
                    help="skip SHA256 comparison against baseline")
    args = ap.parse_args()

    check = not args.no_check
    baseline = load_baseline() if check else {}

    if check and not baseline:
        print("[WARN] _baseline_sha256.txt not found, SHA256 check skipped")
        check = False

    all_ok = True
    for exp_id in EXPERIMENTS:
        print(f"\n=== {exp_id} ===")
        ok = run_experiment(exp_id, check, baseline)
        if not ok:
            all_ok = False

    print()
    print("=" * 50)
    print("run_all verdict:", "PASS" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
