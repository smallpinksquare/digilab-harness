# digilab

[![CI](https://github.com/digilab-harness/digilab/actions/workflows/ci.yml/badge.svg)](https://github.com/digilab-harness/digilab/actions/workflows/ci.yml)
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)

**digilab** synthesises NAND-based combinational logic circuits from a short
expression DSL, verifies them against a truth table, and produces
breadboard-friendly wiring instructions (`circuit.txt`).

> Chinese README: [README.zh-CN.md](README.zh-CN.md)

---

## Quick start

```bash
git clone https://github.com/digilab-harness/digilab digilab-harness
cd digilab-harness
pip install -e ".[dev]"   # Python ≥ 3.9 required
```

Write a small expression file (`expr.md`):

```txt
chips:   7400 x 1
inputs:  A, B
outputs: F

F = NAND2(A, B)
```

Copy the expected truth table from `examples/01_basic_nand2/truth_table.md`
(or write your own), then synthesise and verify:

```bash
# Synthesise — produces netlist.json + circuit.txt
digilab synth --expr examples/01_basic_nand2/expr.md --out /tmp/ex

# truth_table.md → CSV  (the verifier reads CSV)
digilab verify --netlist /tmp/ex/netlist.json \
               --truth   examples/01_basic_nand2/truth_table.md \
               --out     /tmp/ex
```

> `digilab verify --truth` accepts either a `.md` table file **or** a `.csv`
> file directly.

Run the self-test for all registered chips:

```bash
digilab selftest
```

---

## Supported chips

| Model | Primitive(s) | Gates / Blocks |
|-------|-------------|----------------|
| **7400** | `NAND2(a, b)` | 4 × 2-input NAND |
| **7420** | `NAND4(a,b,c,d)` | 2 × 4-input NAND |
| **74138** | `DECODE3(C,B,A)` → 8 outputs | 3-to-8 decoder |
| **74153** | `MUX4(B,A,C0,C1,C2,C3)` | 4-to-1 mux |
| **74151** | `MUX8(C,B,A,D0..D7)` → Y, YBAR | 8-to-1 mux (dual output) |

Third-party chips can be registered via the `digilab.chips`
[entry-point group](docs/chip_extension.md).

---

## Features

- **Daisy-chain fanout** – a signal driving multiple inputs is routed as a
  chain (`src → d0 → d1 → …`), minimising jump-wire runs on the board.
- **VCC-input substitution** – unused gate inputs that would go to VCC are
  connected to an existing input on the same gate, eliminating noisy floating
  pull-ups.
- **Auto CSE** – intermediate variables (`T = NAND2(A,A)`) are shared
  automatically via structural Common Subexpression Elimination.
- **Multi-LHS primitives** – MSI blocks with multiple outputs use a natural
  multi-assignment syntax (`Y0, …, Y7 = DECODE3(C,B,A)`).
- **Strict typing** – full `mypy --strict` coverage; `py.typed` marker included.

---

## Development

```bash
ruff check .
ruff format --check .
mypy src/digilab
pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

---

## Documentation

Full docs live under [`docs/`](docs/index.md):

- [Architecture](docs/architecture.md)
- [DSL Reference](docs/dsl_reference.md)
- [Physical Wiring](docs/physical_wiring.md)
- [Chip Extension](docs/chip_extension.md)

Course-specific materials (experiments, truth tables, wiring guides) are in
[`course_archive/`](course_archive/README.md).

---

## License

[BSD 3-Clause](LICENSE) © 2026 digilab contributors
