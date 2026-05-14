# DSL Reference

Expression files are plain Markdown.  The parser ignores Markdown fences
(` ``` ` blocks), headings, and comment lines starting with `#`.

## File structure

```txt
chips:   <model> x <count> [, <model> x <count>, ...]
inputs:  <name> [, <name>, ...]
outputs: <name> [, <name>, ...]

[<lhs> = <expr>]
...
```

All three header lines are required.  At least one assignment is required.
Every `outputs:` name must have a corresponding assignment.

---

## Gate-level primitives

### `NAND2(a, b)`

2-input NAND gate.  Allocates one gate from a **7400** chip.

```txt
F = NAND2(A, B)
```

### `NAND4(a, b, c, d)`

4-input NAND gate.  Allocates one gate from a **7420** chip.

```txt
F = NAND4(A, B, C, D)
```

Both primitives can be nested arbitrarily:

```txt
F = NAND2(NAND4(A, B, C, D), NAND2(X, X))
```

---

## Literals

`0` connects the input to **GND**.  
`1` connects the input to another used input of the same gate (physical
VCC-substitution) or to **VCC** if no spare input is available.

```txt
F = NAND4(A, B, C, 1)   # effectively NAND3 with 4th input pulled high
```

---

## Intermediate variables (CSE)

Assign a sub-expression to a name; reuse the name in later expressions.
The synthesiser automatically shares the gate (Common Subexpression Elimination).

```txt
T = NAND2(A, A)   # NOT A
F = NAND2(T, B)
```

Intermediate variables are **not** listed in `outputs:`.

---

## High-level MSI primitives

### `DECODE3(C, B, A)` → 8 outputs

3-to-8 decoder; allocates one **74138** chip.  
Active-low outputs D0–D7.  Default enables are wired automatically.

```txt
chips: 74138 x 1
inputs: C, B, A
outputs: D0, D1, D2, D3, D4, D5, D6, D7

D0, D1, D2, D3, D4, D5, D6, D7 = DECODE3(C, B, A)
```

### `MUX4(B, A, C0, C1, C2, C3)` → 1 output

4-to-1 multiplexer (one channel of a **74153**).

```txt
chips: 74153 x 1
inputs: B, A, C0, C1, C2, C3
outputs: Y

Y = MUX4(B, A, C0, C1, C2, C3)
```

### `MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)` → 2 outputs (Y, YBAR)

8-to-1 multiplexer with complementary outputs; allocates one **74151** chip.  
Both outputs **must** be captured with a 2-name LHS:

```txt
chips: 74151 x 1
inputs: C, B, A, D0, D1, D2, D3, D4, D5, D6, D7
outputs: Y

Y, YBAR = MUX8(C, B, A, D0, D1, D2, D3, D4, D5, D6, D7)
```

If `YBAR` is not listed in `outputs:` it is treated as an internal signal
and the corresponding chip pin is left floating in `circuit.txt`.

---

## Multi-LHS rules

- The number of LHS names must exactly match the primitive's declared output count.
- Multi-output primitives must be **top-level** in an assignment; nesting them
  inside `NAND2`/`NAND4` is a `ParseError`.

---

## Constraints

| Constraint | Enforced by |
|---|---|
| All `outputs` names must be assigned | `parse_program_text` |
| LHS names must not duplicate `inputs` | `parse_program_text` |
| Variables must be defined before use | `parse_program_text` |
| Multi-output primitive must be top-level | `parse_program_text` |
| Chip counts must be sufficient | `synthesizer.synthesize` |
