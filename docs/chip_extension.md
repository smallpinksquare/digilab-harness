# Chip Extension

There are two ways to add support for a new 74-series part.

---

## Option A: built-in (recommended for permanent additions)

1. **Create `src/digilab/chips/chip_<model>.py`**

   Minimal template:

   ```python
   from __future__ import annotations
   from typing import List
   from . import Block, ChipSpec, Gate, Pin, PinType

   def make_spec() -> ChipSpec:
       spec = ChipSpec(model="<model>")
       # Add pins:
       spec.pins[1] = Pin(number=1, type=PinType.INPUT, role="A")
       # …
       spec.pins[8] = Pin(number=8, type=PinType.GND)
       spec.pins[16] = Pin(number=16, type=PinType.VCC)

       # For a gate-based chip (e.g. NAND gates):
       from . import Gate
       def nand2(bits: List[int]) -> int:
           return 1 - (bits[0] & bits[1])

       spec.gates.append(Gate(gate_id=0, inputs=[1, 2], output=3, func=nand2))

       # For an MSI block (e.g. decoder / mux):
       def my_func(bits: List[int]) -> List[int]:
           ...
       spec.blocks.append(
           Block(
               block_id=0,
               inputs=[...],
               outputs=[...],
               func=my_func,
               primitive="MY_PRIMITIVE",
               default_enables=[(7, "GND")],   # optional
           )
       )
       return spec

   SPEC = make_spec()

   def _self_check() -> None:
       # Optional but encouraged: run a quick truth-table check
       ...
   ```

2. **Register in `registry.py`**

   ```python
   from . import chip_mymodel

   _MODULES = [..., chip_mymodel]
   ```

3. **Add DSL primitive name** (if adding a new MSI block):

   In `common/parser.py`, extend `_PRIMITIVE_OUTPUT_COUNT`:

   ```python
   _PRIMITIVE_OUTPUT_COUNT = {
       ...
       "MY_PRIMITIVE": 1,   # or 2, 8, etc.
   }
   ```

4. **Add tests** in `tests/test_smoke.py` following the existing patterns,
   and document in `src/digilab/chips/CHANGELOG.md`.

---

## Option B: plugin package

If you want to distribute a chip without forking the repository, declare an
entry-point in your package's `pyproject.toml`:

```toml
[project.entry-points."digilab.chips"]
my_cool_chip = "my_package.my_chip_module"
```

The value should be either:

- A **module** that has a `SPEC: ChipSpec` attribute, **or**
- A **callable** (function or class) that returns a `ChipSpec`.

```python
# my_package/my_chip_module.py
from digilab.chips import Block, ChipSpec, Pin, PinType

def make_spec() -> ChipSpec:
    spec = ChipSpec(model="MY_CHIP")
    # … fill in pins, blocks …
    return spec

SPEC = make_spec()
```

After `pip install my-package`, `digilab selftest` and `get_spec("MY_CHIP")`
will find your chip automatically.  Built-in model names always win on
conflicts.

---

## Notes

- The `default_enables` list on `Block` is processed by the synthesiser: each
  `(pin_number, "GND"/"VCC")` entry generates an automatic wiring line in
  `circuit.txt` so the user need not write the enable connection explicitly.
- Intermediate (NC) outputs in `Block.outputs` that are not in `program.outputs`
  are left floating in the netlist; they appear as `→ NC` in `circuit.txt`.
