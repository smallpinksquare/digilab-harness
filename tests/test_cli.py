"""CLI end-to-end smoke tests.

Exercises ``digilab.cli.main`` (the same entry-point that ``digilab`` on
the command line calls) with a minimal NAND2 circuit, without touching
any course-archive fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from digilab.cli import main as cli_main

# ------------------------------------------------------------------
# Minimal fixtures (written to tmp_path, no external files needed)
# ------------------------------------------------------------------

EXPR_NAND2 = """\
chips:   7400 x 1
inputs:  A, B
outputs: F

F = NAND2(A, B)
"""

TRUTH_NAND2 = """\
| A | B | F |
|---|---|---|
| 0 | 0 | 1 |
| 0 | 1 | 1 |
| 1 | 0 | 1 |
| 1 | 1 | 0 |
"""


@pytest.fixture()
def nand2_expr(tmp_path: Path) -> Path:
    p = tmp_path / "expr.md"
    p.write_text(EXPR_NAND2, encoding="utf-8")
    return p


@pytest.fixture()
def nand2_truth(tmp_path: Path) -> Path:
    p = tmp_path / "truth.md"
    p.write_text(TRUTH_NAND2, encoding="utf-8")
    return p


# ------------------------------------------------------------------
# digilab --version
# ------------------------------------------------------------------

def test_version():
    with pytest.raises(SystemExit) as exc:
        cli_main(["--version"])
    assert exc.value.code == 0


# ------------------------------------------------------------------
# digilab selftest
# ------------------------------------------------------------------

def test_selftest():
    rc = cli_main(["selftest"])
    assert rc == 0


# ------------------------------------------------------------------
# digilab synth
# ------------------------------------------------------------------

def test_synth(nand2_expr: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    rc = cli_main(["synth", "--expr", str(nand2_expr), "--out", str(out)])
    assert rc == 0
    assert (out / "netlist.json").is_file()
    assert (out / "circuit.txt").is_file()

    # Spot-check netlist structure
    data = json.loads((out / "netlist.json").read_text(encoding="utf-8"))
    assert "chips" in data
    assert "connections" in data


# ------------------------------------------------------------------
# digilab verify
# ------------------------------------------------------------------

def test_verify(nand2_expr: Path, nand2_truth: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    # First synthesize so we have a netlist
    cli_main(["synth", "--expr", str(nand2_expr), "--out", str(out)])

    # Convert truth table md -> csv (verifier expects csv)
    from digilab.common.tt_io import md_file_to_csv
    csv_path = tmp_path / "truth.csv"
    md_file_to_csv(nand2_truth, csv_path)

    rc = cli_main([
        "verify",
        "--netlist", str(out / "netlist.json"),
        "--truth", str(csv_path),
        "--out", str(out),
    ])
    assert rc == 0
    report = json.loads((out / "verify_report.json").read_text(encoding="utf-8"))
    assert report["failed"] == 0
    assert report["passed"] == 4


# ------------------------------------------------------------------
# digilab synth (error path: bad expr triggers SynthError / ParseError)
# ------------------------------------------------------------------

def test_synth_bad_expr(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("chips: 7400 x 1\ninputs: A\noutputs: F\nF = UNKNOWNPRIM(A)\n",
                   encoding="utf-8")
    out = tmp_path / "out"
    # Should exit with non-zero (ParseError or SynthError)
    rc = cli_main(["synth", "--expr", str(bad), "--out", str(out)])
    assert rc != 0
