"""Regression tests for examples/.

Each example is synthesised and then verified end-to-end.  The test
passes when ``verify_report.json`` contains ``"failed": 0``.

These tests serve two purposes:
1. Guard against regressions in the synthesizer / verifier pipeline.
2. Verify that every ``examples/`` entry is runnable as documented.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digilab import synthesizer, verifier
from digilab.common.tt_io import md_file_to_csv

EXAMPLES_ROOT = Path(__file__).resolve().parent.parent / "examples"

# Discover all example directories that contain both required files.
EXAMPLE_DIRS = sorted(
    d
    for d in EXAMPLES_ROOT.iterdir()
    if d.is_dir() and (d / "expr.md").is_file() and (d / "truth_table.md").is_file()
)


@pytest.mark.parametrize("example_dir", EXAMPLE_DIRS, ids=lambda d: d.name)
def test_example_passes(example_dir: Path, tmp_path: Path) -> None:
    expr_md = example_dir / "expr.md"
    truth_md = example_dir / "truth_table.md"

    # Synthesise
    rc = synthesizer.main(["--expr", str(expr_md), "--out", str(tmp_path)])
    assert rc == 0, f"synth failed for {example_dir.name}"
    assert (tmp_path / "netlist.json").is_file()
    assert (tmp_path / "circuit.txt").is_file()

    # Convert truth table md → csv
    csv_path = tmp_path / "truth_table.csv"
    md_file_to_csv(truth_md, csv_path)

    # Verify
    rc = verifier.main([
        "--netlist", str(tmp_path / "netlist.json"),
        "--truth", str(csv_path),
        "--out", str(tmp_path),
    ])
    assert rc == 0, f"verify failed for {example_dir.name}"
    report = json.loads((tmp_path / "verify_report.json").read_text(encoding="utf-8"))
    assert report["failed"] == 0, (
        f"example {example_dir.name}: {report['failed']} row(s) differ\n"
        f"diff={report['diff']}"
    )
