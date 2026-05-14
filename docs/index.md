# digilab

**digilab** is a Python library for synthesising NAND-based combinational
logic circuits from a simple expression DSL, verifying them against a truth
table, and producing breadboard-friendly wiring instructions.

## Key features

- **DSL** – declare chips, inputs, outputs, and assignments in a short Markdown
  file.  Supports gate-level primitives (`NAND2`, `NAND4`), high-level MSI
  primitives (`DECODE3`, `MUX4`, `MUX8`), constants, intermediate variables,
  and multi-LHS assignments for multi-output blocks.
- **Synthesiser** – converts expressions → `netlist.json` + `circuit.txt`
  (sorted breadboard wiring with daisy-chain fanout and VCC-substitution).
- **Verifier** – evaluates the netlist for all truth-table rows and emits a
  `verify_report.json` with pass/fail/diff.
- **Chip library** – pluggable; ships 7400, 7420, 74138, 74153, 74151.  Third-
  party chips can be added via the `digilab.chips` entry-point group.

## Documentation pages

| Page | Content |
|------|---------|
| [Architecture](architecture.md) | Internal pipeline and data flow |
| [DSL reference](dsl_reference.md) | Expression syntax, all primitives |
| [Physical wiring](physical_wiring.md) | Daisy-chain and VCC-substitution |
| [Chip extension](chip_extension.md) | Adding built-in or plugin chips |
| **Chinese mirror** | [docs/zh/](zh/index.md) |

## Quick start

```bash
pip install digilab          # once released on PyPI
# or locally:
git clone <repo>
cd digilab-harness
pip install -e ".[dev]"
```

```txt
# expr.md
chips:   7400 x 1
inputs:  A, B
outputs: F

F = NAND2(A, B)
```

```bash
digilab synth  --expr expr.md --out /tmp/ex
digilab verify --netlist /tmp/ex/netlist.json --truth /tmp/ex/truth_table.csv --out /tmp/ex
```

See [`examples/`](../examples/README.md) for four worked examples.
