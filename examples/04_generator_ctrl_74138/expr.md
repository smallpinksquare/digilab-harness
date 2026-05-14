# Example 04 — generator controller (74138 decoder)

Minterms: X = Σm(1,2,3,4,7),  Y = Σm(5,6,7)

Using 74138 active-low outputs D0–D7 plus two NAND gates:

```txt
chips:   74138 x 1, 7420 x 1, 7400 x 1
inputs:  A, B, C
outputs: X, Y

D0, D1, D2, D3, D4, D5, D6, D7 = DECODE3(A, B, C)
X_BAR = NAND4(D0, D5, D6, 1)
X = NAND2(X_BAR, X_BAR)
Y = NAND4(D5, D6, D7, 1)
```
