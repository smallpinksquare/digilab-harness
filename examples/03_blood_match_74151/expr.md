# Example 03 — blood-type compatibility checker (74151 MUX8)

Logic: `F = (¬A1 ∨ B1) ∧ (¬A0 ∨ B0)`
A1A0 encodes the donor's blood type; B1B0 encodes the recipient's.

Mapped onto a single 74151 (8-to-1 MUX) with selector S2 S1 S0 = A1, A0, B1:

```txt
chips:   74151 x 1
inputs:  A1, A0, B1, B0
outputs: F

F, F_BAR = MUX8(A1, A0, B1, 1, 1, B0, B0, 0, 1, 0, B0)
```

`F_BAR` (pin 6, complementary output) is left floating; only `F` (pin 5) is used.
