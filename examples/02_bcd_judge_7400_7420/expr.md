# Example 02 — BCD value discriminator (3 ≤ N ≤ 6)

Inputs are the three low-order BCD bits B2 B1 B0 (the high bit B3 is unused
because it does not affect the result for valid BCD codes).

```txt
chips: 7400 x 1, 7420 x 1
inputs: B2, B1, B0
outputs: Y

Y = NAND2(
      NAND2(B2, NAND2(B1, B0)),
      NAND4(NAND2(B2, B2), B1, B0, 1)
    )
```
