# Architecture

## Pipeline overview

```
expression file (.md)
       │
       ▼
  digilab.common.parser
       │  parse_program_text / parse_program_file
       │  → Program (chips_decl, inputs, outputs, assignments)
       ▼
  digilab.synthesizer
       │  synthesize(program)
       │  1. _ChipPool: allocates Gate / Block slots from declared chips
       │  2. _emit_node: walks AST, maps each node to a pin
       │  3. Daisy-chain fanout (§ Physical wiring)
       │  4. VCC-input substitution (§ Physical wiring)
       │  → Netlist
       ▼
  Netlist.save(out_dir)
       ├── netlist.json   (JSON: chips, connections)
       └── circuit.txt    (sorted human-readable wiring)
```

Verification runs independently:

```
netlist.json + truth_table.csv
       │
       ▼
  digilab.verifier.verify(netlist, header, rows)
       │  1. UnionFind: merge each Connection into electrical nets
       │  2. _Circuit: build gate/block evaluation graph
       │  3. Topological evaluation for each input row
       │  4. Compare with expected outputs
       ▼
  actual_truth_table.csv + verify_report.json
```

## Module map

```
src/digilab/
├── __init__.py          public API (__version__, synthesize, verify, parse_*)
├── cli.py               digilab synth / verify / selftest
├── synthesizer.py       _ChipPool, _emit_*, synthesize()
├── verifier.py          _UnionFind, _Circuit, verify()
├── chips/
│   ├── __init__.py      PinType, Pin, Gate, Block, ChipSpec
│   ├── chip_7400.py
│   ├── chip_7420.py
│   ├── chip_74138.py    DECODE3 primitive (3-to-8 decoder)
│   ├── chip_74153.py    MUX4 primitive (4-to-1 mux)
│   ├── chip_74151.py    MUX8 primitive (8-to-1 mux, dual output)
│   └── registry.py      _MODULES list + importlib.metadata entry-points
└── common/
    ├── ast_nodes.py     Var, Const, Nand, Primitive, Assignment, Program
    ├── parser.py        tokeniser, _Parser, parse_program_text
    ├── netlist.py       Endpoint, Connection, ChipInstance, Netlist
    └── tt_io.py         parse_md_table, md_file_to_csv, read_csv, write_csv
```

## Key data structures

### AST (`common/ast_nodes.py`)

```python
Node = Var | Const | Nand | Primitive

@dataclass(frozen=True)
class Nand:
    args: Tuple[Node, ...]

@dataclass(frozen=True)
class Primitive:   # DECODE3, MUX4, MUX8, …
    name: str
    args: Tuple[Node, ...]

@dataclass
class Assignment:
    name: str           # first (or only) LHS
    expr: Node
    extra_names: List[str]   # additional LHS for multi-output primitives
```

### Netlist (`common/netlist.py`)

```python
@dataclass(frozen=True)
class Endpoint:
    chip: str    # chip instance name or "INPUT"/"OUTPUT"/"VCC"/"GND"/"NC"
    pin: int | str

@dataclass
class Netlist:
    chips: List[ChipInstance]
    inputs: List[str]
    outputs: List[str]
    connections: List[Connection]   # directed src → dst
```

### ChipSpec / Block (`chips/__init__.py`)

```python
@dataclass
class Block:
    block_id: int
    inputs: List[int]               # pin numbers fed to func
    outputs: List[int]              # pin numbers produced by func
    func: Callable[[List[int]], List[int]]
    primitive: str                  # e.g. "MUX8"
    default_enables: List[Tuple[int, str]]   # [(pin, "GND" or "VCC"), …]
```
