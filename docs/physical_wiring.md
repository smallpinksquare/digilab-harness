# Physical Wiring

`circuit.txt` is designed for direct use on a breadboard.  Two non-trivial
optimisations are applied automatically by the synthesiser.

---

## Daisy-chain fanout

When a signal drives multiple inputs, naïve synthesis would create one wire
from the source to every consumer.  On a breadboard this is awkward and wastes
jump-wire rows.

**digilab** instead builds a *chain*:

```
SOURCE.pin  →  consumer_0.pin
consumer_0.pin  →  consumer_1.pin
consumer_1.pin  →  consumer_2.pin
…
```

The first consumer acts as a relay; downstream consumers tap from their
predecessor.  This minimises the number of wires between distant breadboard
rows and makes debugging easier (you can break the chain at any hop).

### Example

Signal `~B3` feeds three gate inputs:

```
INPUT.B3  →  7400_A.1      (first consumer, becomes new source for the chain)
7400_A.1  →  7420_A.2
7420_A.2  →  7420_A.3
```

---

## VCC-input substitution

NAND gates with a constant-1 input (e.g. `NAND4(A, B, C, 1)` to emulate a
3-input NAND) would normally be wired to VCC.  On CMOS/TTL breadboards this
can be electrically noisy: a floating or weakly-driven input near the high
threshold may switch unexpectedly.

**digilab** instead connects the "constant-1" input to an **already-driven
real input** of the **same gate**, provided one exists.  Since NAND is
monotone, repeating a 0 cannot change the output (0 dominates), and repeating
a 1 is redundant—so the logic is preserved.

### Example

`NAND4(A, B, C, 1)`:  pin 4 of the gate would be VCC.  
Substituted: pin 4 is connected to pin 1 (signal A), which is already driven.

```
# before substitution
VCC  →  7420_A.4

# after substitution (no VCC wire needed)
INPUT.A  →  7420_A.1
7420_A.1 →  7420_A.4   (same chip, same gate, different pin)
```

This eliminates the VCC connection entirely, resulting in a cleaner and more
reliable breadboard assembly.
