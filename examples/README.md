# Examples

Each example directory contains two files:

| File | Purpose |
|------|---------|
| `expr.md` | Expression definition (chips, inputs, outputs, assignments) |
| `truth_table.md` | Expected truth table for verification |

## Running an example

```bash
# Synthesise
digilab synth --expr examples/01_basic_nand2/expr.md --out /tmp/ex01

# Verify
digilab verify \
  --netlist /tmp/ex01/netlist.json \
  --truth   /tmp/ex01/truth_table.csv \
  --out     /tmp/ex01
```

Or run all four as part of the test suite:

```bash
pytest tests/test_examples_regression.py -v
```

## Example index

| # | Directory | Chips used | Primitives |
|---|-----------|-----------|------------|
| 01 | `01_basic_nand2` | 7400 | NAND2 |
| 02 | `02_bcd_judge_7400_7420` | 7400, 7420 | NAND2, NAND4 |
| 03 | `03_blood_match_74151` | 74151 | MUX8 |
| 04 | `04_generator_ctrl_74138` | 74138, 7420, 7400 | DECODE3, NAND4, NAND2 |
